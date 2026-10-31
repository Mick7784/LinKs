"""Transactional end-to-end description operations on isolated SQLite fixtures."""
import copy
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import description_workflow as w
import description_search as search
import description_analysis as a
import descriptions as d
import description_search_test as helpers


class WorkflowTests(unittest.TestCase):
    for helper in ('setUp','tearDown','server','request','template','draft','editable','edit_payload','tracking_state','link','reference'):
        locals()[helper]=getattr(helpers.SearchTests,helper)

    def doc(self):
        doc=self.editable();pieces=[];anchors=[]
        for s in doc['template_snapshot']['sections']:
            body='SMLIGHT SMHub Nano MG24\nSONOFF ZBDongle-E' if s['id']=='summary' else '\n'.join(m['heading'] for m in s['merchants'])
            text='\n'.join(x for x in (s['heading'],body) if x) or '#Domotique'
            start=len('\n\n'.join(pieces))+(2 if pieces else 0);pieces.append(text)
            anchors.append({'id':s['id'],'start':start,'end':start+len(text),'quote':text,'status':'confirmed','candidates':[]})
        doc.update(text='\n\n'.join(pieces),sections=anchors,analysis_version=1)
        return self.store(doc)

    def store(self,doc):
        with self.a.connection() as db:return d.editor_document(d.update(db,d.TABLES[1],doc['id'],d.validate_document(doc),doc['revision']))

    def proposal(self,doc,merchant='domadoo',url=None,product='SMLIGHT SMHub Nano MG24'):
        url=url or ('https://www.domadoo.fr/fr/1-hub.html?x=%2B&domid=117' if merchant=='domadoo' else 'https://link.amazon/Exact?tag=keep-21&x=+&x=%2b#😀')
        with self.a.connection() as db:
            result=a.analyze(db,doc,self.a.ORIGIN);pid=next(p['id'] for p in result['products'] if p['name']==product)
            prepared=search.prepare_link(db,doc['id'],{'document':{k:doc[k] for k in ('text','sections','analysis_version','products','selections','manual_order')},'product_id':pid,'merchant':merchant,'url':url,'label':'Mon '+product},self.a.ORIGIN)
            source=db.execute("SELECT id FROM tracking_sources WHERE name='YouTube Description'").fetchone()[0]
        states=doc['selections'].setdefault('merchant_search',{'version':1,'products':{}})['products'];state=states.setdefault(pid,{'query':product,'merchants':{}})
        state['merchants'][merchant]={'prepared':prepared,'url_input':url,'status':'found','selected':True,'source_id':source if merchant=='domadoo' else '', 'link_id':prepared['link_id'],'label':prepared['label'],'section_id':'affiliate','merchant_id':merchant}
        return self.store(doc),'merchant-'+pid+'-'+merchant

    def compare(self,doc):
        with self.a.connection() as db:return w.compare(db,doc['id'],{'expected_revision':doc['revision']},self.a.ORIGIN)

    def apply(self,doc,plan=None,mutation='apply-one'):
        plan=plan or self.compare(doc);request={k:plan[k] for k in ('expected_revision','text_hash','plan_hash')};request['mutation_id']=mutation
        with self.a.connection() as db:
            db.execute('BEGIN IMMEDIATE');result=w.apply(db,doc['id'],request,self.a.ORIGIN)
        return result,request

    def test_preview_read_only_and_real_application_idempotent(self):
        doc,op=self.proposal(self.doc());before=self.tracking_state();plan=self.compare(doc)
        self.assertEqual(before,self.tracking_state());self.assertIn('https://www.domadoo.fr/fr/1-hub.html',plan['after'])
        self.assertTrue(next(o for o in plan['operations'] if o['id']==op)['pending_create'])
        result,request=self.apply(doc,plan);self.assertEqual(result['results'][0]['status'],'applied')
        after=self.tracking_state();self.assertEqual(len(after['tracked_links']),len(before['tracked_links'])+1);self.assertEqual(len(after['tracked_tokens']),len(before['tracked_tokens'])+1)
        self.assertNotIn('https://www.domadoo.fr/fr/1-hub.html',result['document']['text']);self.assertIn(result['results'][0]['url'],result['document']['text'])
        with self.a.connection() as db:again=w.apply(db,doc['id'],request,self.a.ORIGIN)
        self.assertTrue(again['replayed']);self.assertEqual(after,self.tracking_state())
        self.assertEqual(after['counts'],before['counts']);self.assertEqual(after['tracking_sources'],before['tracking_sources'])

    def test_amazon_direct_exact_no_business_writes_and_bare_warning(self):
        doc,op=self.proposal(self.doc(),'amazon','link.amazon/Exact?tag=keep-21&x=+&x=%2b#😀');before=self.tracking_state();plan=self.compare(doc)
        self.assertTrue(any('sans schéma' in x for x in plan['warnings']));result,_=self.apply(doc,plan)
        self.assertIn('link.amazon/Exact?tag=keep-21&x=+&x=%2b#😀',result['document']['text']);self.assertEqual(before,self.tracking_state())

    def test_changed_partner_or_revision_rejects_stale_plan(self):
        doc,op=self.proposal(self.doc());plan=self.compare(doc)
        with self.a.connection() as db:db.execute("UPDATE affiliate_partners SET code='999' WHERE name='Domadoo'")
        self.assertRaises(d.Conflict,self.apply,doc,plan)
        fresh=self.compare(doc);self.assertEqual(next(o for o in fresh['operations'] if o['id']==op)['status'],'obsolete')
        edited=copy.deepcopy(doc);edited['title']='Autre onglet';self.store(edited)
        self.assertRaises(d.Conflict,self.compare,doc)

    def test_partial_failure_rolls_back_only_failed_link_and_can_retry(self):
        doc,domadoo=self.proposal(self.doc());doc,amazon=self.proposal(doc,'amazon');before=self.tracking_state()
        with patch.object(w.tracked_links,'token_link',side_effect=OSError('Publication indisponible')):result,_=self.apply(doc)
        states={r['id']:r['status'] for r in result['results']};self.assertEqual(states[domadoo],'failed');self.assertEqual(states[amazon],'applied')
        self.assertEqual(before,self.tracking_state());self.assertIn('link.amazon/Exact',result['document']['text'])
        result,_=self.apply(result['document'],mutation='retry-one');self.assertEqual(next(r for r in result['results'] if r['id']==domadoo)['status'],'applied')
        self.assertEqual(result['document']['text'].count('link.amazon/Exact'),1)

    def test_historical_publication_reused_and_inline_phrase_preserved(self):
        item,pub=self.link('Hub historique','https://www.domadoo.fr/fr/1-hub.html?domid=117',source='YouTube Post')
        doc=self.doc();old=doc['text'];start=doc['sections'][0]['end'];w.patch(doc,start,start,'\nAvant 😀 '+item['url']+' après, exactement.','summary')
        result=a.analyze
        with self.a.connection() as db:parsed=a.analyze(db,doc,self.a.ORIGIN)
        proposal=next(p for p in parsed['proposals'] if p['kind']=='reuse');doc['selections']['description_analysis']={proposal['id']:{'selected':True,'link_id':item['id'],'source_id':pub['source_id']}}
        doc=self.store(doc);before=self.tracking_state();applied,_=self.apply(doc)
        self.assertIn('Avant 😀 '+pub['url']+' après, exactement.',applied['document']['text']);self.assertEqual(before,self.tracking_state())

    def test_deleted_section_requires_explicit_recreation_and_heading_is_not_guessed(self):
        doc=self.doc();anchor=next(x for x in doc['sections'] if x['id']=='affiliate');w.patch(doc,anchor['start'],anchor['end'],'')
        anchor.update(status='ambiguous',start=None,end=None,quote='',candidates=[]);doc=self.store(doc);doc,op=self.proposal(doc,'amazon')
        plan=self.compare(doc);self.assertEqual(next(o for o in plan['operations'] if o['id']==op)['status'],'obsolete')
        doc['selections']['operations']={op:{'allow_section':True,'section_at':len(doc['text']),'allow_subsection':True}};doc=self.store(doc)
        result,_=self.apply(doc);self.assertEqual(next(r for r in result['results'] if r['id']==op)['status'],'applied');self.assertIn('🟠 Sur Amazon',result['document']['text'])

    def test_explicit_move_and_remove_never_delete_catalogue(self):
        doc=self.doc();url='https://amzn.to/official';w.patch(doc,doc['sections'][0]['end'],doc['sections'][0]['end'],'\nHub : '+url,'summary');doc=self.store(doc)
        with self.a.connection() as db:parsed=a.analyze(db,doc,self.a.ORIGIN)
        move=next(p for p in parsed['proposals'] if p['kind']=='move' and p['url_id']==a.identity('url',url));doc['selections']['description_analysis']={move['id']:{'selected':True}};doc=self.store(doc);before=self.tracking_state()
        moved,_=self.apply(doc);self.assertEqual(next(r for r in moved['results'] if r['id']==move['id'])['status'],'applied')
        text=moved['document']['text'];self.assertGreater(text.index(url),text.index('🟠 Sur Amazon'));self.assertEqual(text.count(url),1)
        doc=moved['document'];doc['selections'].setdefault('operations',{})[a.identity('url',url)]={'selected':True,'action':'remove'};doc=self.store(doc)
        removed,_=self.apply(doc,mutation='remove-url');self.assertNotIn(url,removed['document']['text']);self.assertEqual(before,self.tracking_state())

    def test_finalize_exact_immutable_snapshot_and_restore_copy(self):
        doc,op=self.proposal(self.doc(),'amazon');applied,_=self.apply(doc);doc=applied['document'];plan=self.compare(doc)
        request={k:plan[k] for k in ('expected_revision','text_hash','plan_hash')};request.update(mutation_id='final-one',ignore_remaining=True)
        with self.a.connection() as db:
            result=w.finalize(db,doc['id'],request,self.a.ORIGIN);again=w.finalize(db,doc['id'],request,self.a.ORIGIN)
            self.assertEqual(result['version']['id'],again['version']['id']);self.assertEqual(result['version']['text'],doc['text']);self.assertTrue(result['version']['links'])
            restored=w.restore(db,result['version']['id'],{'mutation_id':'restore-one'});self.assertNotEqual(restored['id'],doc['id']);self.assertEqual(restored['text'],doc['text'])
            self.assertEqual(w.restore(db,result['version']['id'],{'mutation_id':'restore-one'})['id'],restored['id'])
            restored['text']='Nouveau';restored['sections']=[{**x,'status':'ambiguous','start':None,'end':None,'candidates':[]} for x in restored['sections']]
            d.update(db,d.TABLES[1],restored['id'],d.validate_document(restored),restored['revision'])
            self.assertEqual(d.get(db,d.TABLES[2],result['version']['id'])['text'],doc['text'])

    def test_finalization_limit_and_remaining_operations_need_confirmation(self):
        doc,op=self.proposal(self.doc());plan=self.compare(doc);request={k:plan[k] for k in ('expected_revision','text_hash','plan_hash')};request['mutation_id']='final-unapplied'
        with self.a.connection() as db:self.assertRaises(ValueError,w.finalize,db,doc['id'],request,self.a.ORIGIN)
        doc['text']='😀'*5001;doc['sections']=[{**x,'status':'ambiguous','start':None,'end':None,'candidates':[]} for x in doc['sections']];doc=self.store(doc)
        with self.a.connection() as db:self.assertRaises(ValueError,w.finalize,db,doc['id'],{'expected_revision':doc['revision'],'mutation_id':'too-long'},self.a.ORIGIN)

    def test_existing_raw_url_pending_publication_still_requires_application(self):
        doc=self.doc();url='https://www.domadoo.fr/fr/1-hub.html?domid=117';start=doc['sections'][0]['end'];w.patch(doc,start,start,'\nSMLIGHT SMHub Nano MG24 : '+url,'summary');doc=self.store(doc)
        doc,op=self.proposal(doc,url=url);plan=self.compare(doc);operation=next(o for o in plan['operations'] if o['id']==op)
        self.assertEqual(operation['status'],'ready');self.assertEqual(operation['url'],url);self.assertTrue(operation['pending_create'])
        result,_=self.apply(doc,plan);self.assertNotIn(url,result['document']['text']);self.assertIn(next(r['url'] for r in result['results'] if r['id']==op),result['document']['text'])

    def test_parallel_confirmations_allocate_one_link_and_token(self):
        doc,op=self.proposal(self.doc());plan=self.compare(doc);before=self.tracking_state()
        def attempt(i):
            try:return self.apply(doc,plan,mutation='parallel-'+str(i))[0]
            except d.Conflict:return None
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,[1,2]))
        self.assertEqual(sum(r is not None for r in results),1);after=self.tracking_state()
        self.assertEqual(len(after['tracked_links']),len(before['tracked_links'])+1);self.assertEqual(len(after['tracked_tokens']),len(before['tracked_tokens'])+1)

    def test_manual_product_order_precedes_permanent_shop_link(self):
        doc=self.doc();section=next(s for s in doc['sections'] if s['id']=='affiliate');point=doc['text'].index('🟠 Sur Amazon');w.patch(doc,point,point,'✅ Boutique Domadoo : https://www.domadoo.fr/fr/?domid=117\n',section['id']);doc=self.store(doc)
        doc,first=self.proposal(doc);doc,second=self.proposal(doc,url='https://www.domadoo.fr/fr/2-sonoff.html',product='SONOFF ZBDongle-E')
        ids=list(doc['selections']['merchant_search']['products']);doc['manual_order']=list(reversed(ids));doc=self.store(doc)
        result,_=self.apply(doc);text=result['document']['text'];self.assertLess(text.index('Mon SONOFF'),text.index('Mon SMLIGHT'));self.assertLess(text.index('Mon SMLIGHT'),text.index('✅ Boutique Domadoo'));self.assertEqual(text.count('✅ Boutique Domadoo'),1)

    def test_source_disabled_and_removed_proposals_are_obsolete(self):
        doc,op=self.proposal(self.doc());plan=self.compare(doc)
        with self.a.connection() as db:db.execute("UPDATE tracking_sources SET active=0 WHERE name='YouTube Description'")
        self.assertRaises(d.Conflict,self.apply,doc,plan)
        self.assertEqual(next(o for o in self.compare(doc)['operations'] if o['id']==op)['status'],'obsolete')
        doc['selections'].setdefault('description_analysis',{})['removed-url']={'selected':True,'label':'Ancien lien'};doc=self.store(doc)
        self.assertEqual(next(o for o in self.compare(doc)['operations'] if o['id']=='removed-url')['status'],'obsolete')

    def test_duplicate_product_requires_explicit_replacement(self):
        doc=self.doc();point=doc['text'].index('🟠 Sur Amazon')+len('🟠 Sur Amazon');w.patch(doc,point,point,'\nSMLIGHT SMHub Nano MG24 : https://amzn.to/old','affiliate');doc=self.store(doc);doc,op=self.proposal(doc,'amazon','https://amzn.to/new')
        self.assertEqual(next(o for o in self.compare(doc)['operations'] if o['id']==op)['status'],'obsolete')
        doc['selections']['operations']={op:{'target_url_id':a.identity('url','https://amzn.to/old')}};doc=self.store(doc);result,_=self.apply(doc)
        self.assertNotIn('https://amzn.to/old',result['document']['text']);self.assertEqual(result['document']['text'].count('https://amzn.to/new'),1)

    def test_empty_optional_sections_hide_without_removing_custom_text(self):
        doc=self.doc();plan=self.compare(doc);self.assertEqual(next(o for o in plan['operations'] if o['id']=='hide-empty')['status'],'ready')
        result,_=self.apply(doc);text=result['document']['text'];self.assertNotIn('🟠 Sur Amazon',text);self.assertNotIn('🎥 VIDÉO COMPLÉMENTAIRE',text);self.assertIn('🟠 Chez Domadoo',text);self.assertIn('#Domotique',text)

    def test_history_backup_restores_exact_snapshots_despite_catalogue_change(self):
        doc,op=self.proposal(self.doc());result,_=self.apply(doc);doc=result['document'];plan=self.compare(doc)
        request={k:plan[k] for k in ('expected_revision','text_hash','plan_hash')};request.update(mutation_id='snapshot',ignore_remaining=True)
        with self.a.connection() as db:
            version=w.finalize(db,doc['id'],request,self.a.ORIGIN)['version'];backup=d.export_backup(db)
            link=next(l for l in version['links'] if l['link_id']);db.execute('UPDATE tracked_links SET url=? WHERE id=?',('https://example.org/changed',link['link_id']))
            db.execute('DELETE FROM description_versions');d.restore_backup(db,backup)
            self.assertEqual(d.get(db,d.TABLES[2],version['id'])['links'],version['links'])

    def test_private_http_comparison_application_and_versions(self):
        doc,op=self.proposal(self.doc(),'amazon');admin=self.server(True);public=self.server();before=self.tracking_state()
        self.assertEqual(self.request(public+'/api/descriptions/drafts/'+doc['id']+'/compare',{'expected_revision':doc['revision']})[0],404)
        status,raw=self.request(admin+'/api/descriptions/drafts/'+doc['id']+'/compare',{'expected_revision':doc['revision']});self.assertEqual(status,200);plan=json.loads(raw);self.assertEqual(before,self.tracking_state())
        request={k:plan[k] for k in ('expected_revision','text_hash','plan_hash')};request['mutation_id']='http-apply'
        status,raw=self.request(admin+'/api/descriptions/drafts/'+doc['id']+'/apply',request);self.assertEqual(status,200)
        self.assertEqual(self.request(admin+'/api/descriptions/drafts/'+doc['id']+'/apply',request)[0],200)
        self.assertEqual(before,self.tracking_state());self.assertEqual(self.request(admin+'/api/descriptions/drafts/'+doc['id']+'/versions')[0],200)

    def test_unknown_video_requires_explicit_creation_then_reuses_publication(self):
        doc=self.doc();url='https://youtu.be/NewVideo123';w.patch(doc,doc['sections'][0]['end'],doc['sections'][0]['end'],'\nVidéo : '+url,'summary');doc=self.store(doc);ident=a.identity('url',url)
        self.assertEqual(next(o for o in self.compare(doc)['operations'] if o['id']==ident)['status'],'obsolete')
        with self.a.connection() as db:source=db.execute("SELECT id FROM tracking_sources WHERE name='YouTube Post'").fetchone()[0]
        doc['selections']['operations']={ident:{'allow_create':True,'source_id':source,'selected':True}};doc=self.store(doc);before=self.tracking_state();result,_=self.apply(doc)
        self.assertEqual(next(r for r in result['results'] if r['id']==ident)['status'],'applied');after=self.tracking_state();self.assertEqual(len(after['tracked_links']),len(before['tracked_links'])+1)
        self.assertEqual(after['counts'],before['counts'])


if __name__=='__main__':unittest.main()
