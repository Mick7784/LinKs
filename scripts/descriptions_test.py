"""Phase 1 contracts: preservation, references, concurrency and backup integration."""
import copy
import json
import threading
import unittest
from pathlib import Path

import analytics_test
import descriptions as d


class DescriptionTests(unittest.TestCase):
    setUp = analytics_test.AnalyticsTests.setUp
    tearDown = analytics_test.AnalyticsTests.tearDown
    server = analytics_test.AnalyticsTests.server
    request = analytics_test.AnalyticsTests.request

    def template(self):
        with self.a.connection() as db:return d.get(db,d.TABLES[0],d.DEFAULT_ID)

    def draft(self):
        t=self.template()
        with self.a.connection() as db:return d.create_draft(db,{'template_id':t['id'],'template_revision':t['revision'],'title':'Vidéo SMLIGHT'},self.a.ORIGIN)

    def linked_template(self):
        template=self.template()
        with self.a.connection() as db:
            for section in template['sections']:
                for owner in [section,*section['merchants']]:
                    for binding in owner['links']:
                        row=self.a.affiliate_partners.save_tracked(db,{'name':binding['id'],'url':binding['reference_url']},self.a.story_url_valid,self.a.now_iso())
                        source=db.execute("SELECT id FROM tracking_sources WHERE name='YouTube Description'").fetchone()[0]
                        token=self.a.tracked_links.token_link(db,row['id'],source,self.a.ORIGIN,self.a.now_iso())
                        binding.update(link_id=row['id'],source_id=source)
            return d.write(db,'templates/'+template['id']+'/save',{**template,'expected_revision':template['revision']},self.a.ORIGIN)

    def tracking_state(self):
        with self.a.connection() as db:
            return {t:[tuple(row) for row in db.execute('SELECT * FROM '+t)] for t in ('tracked_links','tracked_tokens','tracking_sources','tracking_source_keys','short_aliases','counts','affiliate_partners')}

    def test_reference_seed_has_exact_seven_sections_and_only_permanent_copy(self):
        t=self.template();sections=t['sections']
        self.assertEqual([s['id'] for s in sections],['summary','support','affiliate','videos','chapters','community','hashtags'])
        self.assertEqual([s['mode'] for s in sections],['manual','permanent','smart','smart','manual','permanent','manual'])
        self.assertEqual([s['hide_if_empty'] for s in sections],[False,False,False,True,True,False,True])
        fixture=Path(__file__).with_name('fixtures')/'descriptions/smlight.txt'
        original=fixture.read_text(encoding='utf-8-sig')
        self.assertIn('SMLIGHT SMHub Nano MG24',original)
        self.assertIn('https://amzn.to/4yj9H0L',original)
        self.assertNotIn('amzn.to',json.dumps(t))
        self.assertNotIn('Injecteur PoE',json.dumps(t))
        self.assertEqual(sections[0]['text'],'')
        for s in sections:
            if s['text']:self.assertIn(s['text'],original)
            if s['after_text']:self.assertIn(s['after_text'],original)
        self.a.init();self.assertEqual(self.template(),t)

    def test_preview_missing_bindings_never_uses_reference_urls_and_has_no_side_effects(self):
        before=self.tracking_state()
        with self.a.connection() as db:
            preview=d.render(db,self.template(),self.a.ORIGIN)
        self.assertEqual(len(preview['problems']),4)
        self.assertNotIn('https://',preview['text'])
        self.assertIn('🟠 Chez Domadoo',preview['text'])
        self.assertNotIn('🟠 Sur Amazon',preview['text'])
        self.assertEqual(before,self.tracking_state())

    def test_historical_youtube_aliases_reused_without_changing_tokens_or_counters(self):
        t=self.linked_template();before=self.tracking_state()
        with self.a.connection() as db:
            preview=d.render(db,t,self.a.ORIGIN)
            self.assertFalse(preview['problems'])
            catalogue=d.catalogue(db)
            self.assertTrue(any(p['source_name']=='YouTube Description' for item in catalogue['items'] for p in item['publications']))
            for section in t['sections']:
                for owner in [section,*section['merchants']]:
                    for binding in owner['links']:
                        url,problem=d.resolved_link(db,binding,self.a.ORIGIN)
                        self.assertIsNone(problem);self.assertIn(url,preview['text'])
            self.draft();self.draft()
        self.assertEqual(before,self.tracking_state())

    def test_template_edits_deletion_and_restart_cannot_rewrite_draft(self):
        t=self.linked_template();draft=self.draft()
        with self.a.connection() as db:
            t['sections'].reverse();t['sections'][0]['heading']='Titre modifié librement'
            saved=d.write(db,'templates/'+t['id']+'/save',{**t,'expected_revision':t['revision']},self.a.ORIGIN)
            self.assertEqual(d.get(db,d.TABLES[1],draft['id']),draft)
            d.write(db,'templates/'+t['id']+'/delete',{'expected_revision':saved['revision']},self.a.ORIGIN)
        self.a.init()
        with self.a.connection() as db:
            self.assertFalse(d.rows(db,d.TABLES[0]));self.assertEqual(d.get(db,d.TABLES[1],draft['id']),draft)

    def test_save_conflict_preserves_winner_and_manual_order(self):
        t=self.template();barrier=threading.Barrier(2);results=[]
        def save(name):
            barrier.wait()
            try:
                with self.a.connection() as db:
                    db.execute('BEGIN IMMEDIATE')
                    d.write(db,'templates/'+t['id']+'/save',{**t,'name':name,'expected_revision':t['revision']},self.a.ORIGIN)
                results.append('ok')
            except d.Conflict:results.append('conflict')
        threads=[threading.Thread(target=save,args=(name,)) for name in ('Premier','Second')]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertCountEqual(results,['ok','conflict'])
        self.assertEqual(self.template()['revision'],t['revision']+1)
        with self.a.connection() as db:
            with self.assertRaises(d.Conflict):d.create_draft(db,{'title':'Périmé','template_id':t['id'],'template_revision':t['revision']},self.a.ORIGIN)

    def test_amazon_binding_cannot_silently_become_redirect_or_rewrite_affiliation(self):
        t=self.linked_template();binding=t['sections'][1]['links'][0]
        url='https://amzn.to/4yj9H0L?tag=original-21&x=a%2Bb&x=z#fragment'
        with self.a.connection() as db:
            db.execute('UPDATE tracked_links SET url=? WHERE id=?',(url,binding['link_id']))
        before=self.tracking_state()
        with self.a.connection() as db:
            value,problem=d.resolved_link(db,binding,self.a.ORIGIN)
            self.assertIsNone(value);self.assertIn('insertion directe',problem)
        self.assertEqual(before,self.tracking_state())

    def test_backup_roundtrip_preview_legacy_and_conflicts_are_non_destructive(self):
        self.linked_template();draft=self.draft();backup=json.loads(self.a.export_backup());original=copy.deepcopy(backup)
        with self.a.connection() as db:before=d.export_backup(db)
        summary=self.a.restore_backup(backup,preview=True)
        self.assertEqual(summary['descriptions']['conflicts'],0)
        with self.a.connection() as db:self.assertEqual(d.export_backup(db),before)
        self.a.restore_backup(backup);self.assertEqual(backup,original)
        legacy=copy.deepcopy(backup);legacy.pop('descriptions');self.a.restore_backup(legacy)
        with self.a.connection() as db:self.assertEqual(d.export_backup(db),before)
        # A newer draft has its own exact text and order; restoring the old snapshot
        # recovers a separate draft, without changing the open editor's revision.
        newer={**draft,'text':'Texte manuel 😀 https://amzn.to/4yj9H0L','manual_order':['b','a']}
        with self.a.connection() as db:
            saved=d.update(db,d.TABLES[1],draft['id'],d.validate_document(newer),draft['revision'])
        preview=self.a.restore_backup(backup,preview=True)
        self.assertEqual(preview['descriptions']['recovered'],1)
        with self.a.connection() as db:self.assertEqual(len(d.rows(db,d.TABLES[1])),1)
        self.a.restore_backup(backup);self.a.restore_backup(backup)
        with self.a.connection() as db:
            self.assertEqual(d.get(db,d.TABLES[1],draft['id']),saved)
            restored=d.rows(db,d.TABLES[1]);self.assertEqual(len(restored),2)
            self.assertTrue(any(x['text']==draft['text'] for x in restored))

    def test_restore_to_empty_tables_and_immutable_versions(self):
        draft=self.draft()
        version=d.validate_document({**draft,'description_id':draft['id'],'finalized_at':d.stamp(),'links':[],'status':'finalized'},True)
        with self.a.connection() as db:
            saved=d.insert(db,d.TABLES[2],version);snapshot=d.export_backup(db)
            for table in reversed(d.TABLES):db.execute('DELETE FROM '+table)
            d.restore_backup(db,snapshot)
            self.assertEqual(d.export_backup(db),snapshot)
        corrupt=copy.deepcopy(snapshot)
        row=corrupt['tables'][d.TABLES[2]][0];payload=json.loads(row['payload']);payload['text']='Altéré';row['payload']=d.packed(payload)
        with self.assertRaises(ValueError):
            with self.a.connection() as db:d.restore_backup(db,corrupt)
        with self.a.connection() as db:self.assertEqual(d.get(db,d.TABLES[2],saved['id'])['text'],version['text'])

    def test_invalid_backup_rolls_back_all_description_rows(self):
        backup=json.loads(self.a.export_backup());before=self.template()
        backup['descriptions']['tables'][d.TABLES[0]][0]['payload']='{"name":"broken"}'
        with self.assertRaises(ValueError):self.a.restore_backup(backup)
        self.assertEqual(self.template(),before)
        incomplete=json.loads(self.a.export_backup());del incomplete['descriptions']['tables'][d.TABLES[1]]
        with self.assertRaises(ValueError):self.a.restore_backup(incomplete)

    def test_http_private_routes_validation_and_conflict(self):
        admin=self.server(True);public=self.server();t=self.template()
        self.assertEqual(self.request(public+'/api/descriptions/templates')[0],404)
        self.assertEqual(self.request(public+'/api/descriptions/templates',t)[0],404)
        self.assertEqual(self.request(admin+'/api/descriptions/templates')[0],200)
        url=admin+'/api/descriptions/templates/'+t['id']+'/save'
        payload={**t,'name':'Nouveau nom','expected_revision':t['revision']}
        self.assertEqual(self.request(url,payload)[0],200)
        self.assertEqual(self.request(url,payload)[0],409)
        invalid=copy.deepcopy(t);invalid['sections'][1]['id']=invalid['sections'][0]['id']
        self.assertEqual(self.request(admin+'/api/descriptions/templates',invalid)[0],400)
        status,raw=self.request(admin+'/api/descriptions/templates',{'name':'Vide','platform':'youtube','sections':[]})
        self.assertEqual(status,200,raw)


if __name__=='__main__':unittest.main()
