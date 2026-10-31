"""Local analysis contracts with the supplied SMLIGHT text; outbound IO forbidden."""
import copy
import json
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

import descriptions as d
import description_analysis as analysis
import descriptions_test
import url_inspection


class AnalysisTests(unittest.TestCase):
    setUp=descriptions_test.DescriptionTests.setUp
    tearDown=descriptions_test.DescriptionTests.tearDown
    server=descriptions_test.DescriptionTests.server
    request=descriptions_test.DescriptionTests.request
    template=descriptions_test.DescriptionTests.template
    draft=descriptions_test.DescriptionTests.draft
    editable=descriptions_test.DescriptionTests.editable
    edit_payload=descriptions_test.DescriptionTests.edit_payload
    tracking_state=descriptions_test.DescriptionTests.tracking_state

    def link(self,name,url,source='YouTube Description'):
        with self.a.connection() as db:
            item=self.a.affiliate_partners.save_tracked(db,{'name':name,'url':url},self.a.story_url_valid,self.a.now_iso())
            source_id=db.execute('SELECT id FROM tracking_sources WHERE name=?',(source,)).fetchone()[0]
            pub=self.a.tracked_links.token_link(db,item['id'],source_id,self.a.ORIGIN,self.a.now_iso())
        return item,pub

    def document(self,content):
        doc=self.editable();doc['text']=content
        for anchor in doc['sections']:anchor.update(status='ambiguous',start=None,end=None,candidates=[])
        return doc

    def run_analysis(self,doc):
        with patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')),patch.object(url_inspection,'_fetch',side_effect=AssertionError('No HTTP')):
            with self.a.connection() as db:return analysis.analyze(db,doc,self.a.ORIGIN)

    def reference(self):return (Path(__file__).with_name('fixtures')/'descriptions/smlight.txt').read_text(encoding='utf-8-sig')

    def test_smlight_reference_explicit_only_no_network_and_no_catalogue_changes(self):
        self.link('SMLIGHT SMHub Nano MG24','https://shop.example/hub')
        self.link('Antenne SMLIGHT SMHub Nano MG24','https://shop.example/antenna')
        self.link('Home Assistant','https://shop.example/technology')
        self.link('Zigbee','https://shop.example/zigbee')
        before=self.tracking_state();doc=self.document(self.reference());result=self.run_analysis(doc)
        self.assertEqual(len(result['urls']),10)
        names={p['name'] for p in result['products']}
        self.assertIn('SMLIGHT SMHub Nano',names);self.assertIn('SMLIGHT SMHub Nano MG24',names)
        self.assertIn('Injecteur PoE SMLIGHT 48 V / 24 W',names);self.assertIn('Kit CPL avec Wi-Fi',names)
        self.assertFalse(names&{'Home Assistant','Zigbee','MQTT','Boutique Domadoo','Instagram','Discord AyLabs'})
        self.assertFalse(any('MR1-U' in name or 'Antenne' in name for name in names))
        self.assertFalse(any('Antenne' in item['name'] for p in result['products'] for m in p['matches'] for item in result['catalogue'] if item['id']==m['link_id']))
        self.assertEqual(before,self.tracking_state());self.assertEqual(doc['text'],self.reference())

    def test_alias_token_duplicates_and_historical_sources_without_clicks(self):
        item,old=self.link('SMLIGHT SMHub Nano MG24','https://shop.example/hub')
        with self.a.connection() as db:
            post=db.execute("SELECT id FROM tracking_sources WHERE name='YouTube Post'").fetchone()[0]
            second=self.a.tracked_links.token_link(db,item['id'],post,self.a.ORIGIN,self.a.now_iso())
        text='Résumé 😀\n'+old['url']+' et '+old['url']+'\n'+self.a.ORIGIN+'/go/'+old['token']+'\n'+second['url']
        before=self.tracking_state();result=self.run_analysis(self.document(text))
        self.assertEqual(len(result['urls']),3);self.assertEqual(len(result['urls'][0]['occurrences']),2)
        for url in result['urls']:self.assertEqual(url['matches'][0]['link_id'],item['id']);self.assertEqual(url['kind'],'links')
        reuse=[p for p in result['proposals'] if p['kind']=='reuse'];self.assertEqual(reuse[-1]['source_id'],post)
        self.assertEqual(reuse[0]['source_id'],old['source_id']);self.assertTrue(all(p['selected'] for p in reuse))
        self.assertEqual(before,self.tracking_state())

    def test_external_host_cannot_claim_an_existing_alias_and_revoked_is_identified(self):
        item,pub=self.link('Hub ABC123','https://shop.example/hub')
        doc=self.document('https://evil.example/'+pub['code']+'\n'+pub['url'])
        with self.a.connection() as db:db.execute('UPDATE short_aliases SET revoked=1 WHERE code=?',(pub['code'],))
        result=self.run_analysis(doc);self.assertFalse(result['urls'][0]['matches']);self.assertTrue(result['urls'][1]['known']['revoked'])

    def test_amazon_exact_urls_all_forms_and_unicode_spans(self):
        values=['https://amzn.to/4yj9H0L?tag=exact-21&x=a%2Bb&x=z#Fragment',
                'https://link.amazon/ABC?tag=second-21','https://www.amazon.fr/dp/B012345678?tag=exact-21&v=1.',
                'amzn.to/NoScheme','https://amzn.to/short']
        text='😀 é 👩🏽‍💻 '+values[0]+'\n'+ '\n'.join(values[1:4])+'\n('+values[4]+').'
        result=self.run_analysis(self.document(text));self.assertEqual([u['url'] for u in result['urls']],values)
        self.assertTrue(all(u['amazon'] for u in result['urls']))
        for url in result['urls']:
            for span in url['occurrences']:self.assertEqual(text[span['start']:span['end']],url['url'])
        self.assertTrue(all(p['amazon'] for p in result['proposals'] if p['kind']=='reuse'))

    def test_existing_amazon_redirect_is_recognized_but_never_prepared_silently(self):
        item,pub=self.link('Kit CPL avec Wi-Fi','https://amzn.to/original?tag=keep-21')
        result=self.run_analysis(self.document('Kit CPL avec Wi-Fi : '+pub['url']))
        url=result['urls'][0];self.assertTrue(url['amazon']);self.assertEqual(url['known']['source_id'],pub['source_id'])
        proposal=next(p for p in result['proposals'] if p['kind']=='reuse');self.assertTrue(proposal['blocked_reason']);self.assertEqual(proposal['source_id'],'')
        self.assertEqual(result['catalogue'][0]['url'],item['url'])

    def test_ambiguous_models_and_independent_merchant_defaults(self):
        first,_=self.link('SMLIGHT SMHub Nano MG24','https://www.domadoo.fr/fr/8664-hub.html')
        other,_=self.link('SMLIGHT SMHub Nano MG21','https://www.domadoo.fr/fr/8665-hub.html')
        self.link('SMLIGHT SMHub Nano MG24','https://amzn.to/other')
        doc=self.document('SMLIGHT SMHub Nano\n\n🙏 SOUTENIR LA CHAÎNE DOMOTIK STUDIO\nMerci\n\n🔗 REJOINDRE LA COMMUNAUTÉ\nLiens')
        result=self.run_analysis(doc);product=next(p for p in result['products'] if p['name']=='SMLIGHT SMHub Nano')
        self.assertEqual(len(product['matches']),3);self.assertTrue(all(m['confidence']=='possible' for m in product['matches']))
        additions=[p for p in result['proposals'] if p['kind']=='add'];self.assertEqual(len(additions),2)
        self.assertTrue(all(not p['selected'] and not p['link_id'] for p in additions))
        domadoo=next(p for p in additions if len(p['matches'])==2);self.assertEqual({m['link_id'] for m in domadoo['matches']},{first['id'],other['id']})

    def test_permanent_custom_renamed_and_hashtags_never_supply_products(self):
        doc=self.editable();content='Résumé sans référence.\n\nTitre de soutien renommé\nSMLIGHT SMHub Nano MG24\n\n#SMLIGHT #SMHubNano\n'
        doc['text']=content
        for a in doc['sections']:a.update(status='ambiguous',start=None,end=None,candidates=[])
        anchor=next(a for a in doc['sections'] if a['id']=='support');start=content.index('Titre de soutien');end=content.index('\n\n#')
        anchor.update(status='confirmed',start=start,end=end,quote=content[start:end])
        self.assertEqual(self.run_analysis(doc)['products'],[])

    def test_duplicate_catalogue_records_require_manual_choice(self):
        item,pub=self.link('Hub ABC123','https://shop.example/hub')
        with self.a.connection() as db:
            duplicate=self.a.tracked_links.create_link(db,{'name':'Autre fiche','url':item['url'],'notes':''},self.a.story_url_valid,self.a.now_iso())
        result=self.run_analysis(self.document(item['url']))
        proposal=next(p for p in result['proposals'] if p['kind']=='reuse')
        self.assertEqual(len(proposal['matches']),2);self.assertEqual(proposal['link_id'],'');self.assertEqual(proposal['source_id'],'')
        self.assertTrue(proposal['selected'])

    def test_plain_free_text_and_unmentioned_accessories(self):
        self.link('Antenne SONOFF ZBDongle-E','https://shop.example/antenna')
        result=self.run_analysis(self.document('Je présente le SONOFF ZBDongle-E. Zigbee, MQTT et Home Assistant sont utilisés.'))
        self.assertEqual([p['name'] for p in result['products']],['SONOFF ZBDongle-E'])
        self.assertEqual(result['products'][0]['matches'],[])

    def test_inline_hashtags_and_affiliate_punctuation_stay_exact(self):
        self.link('SONOFF ZBDongle-E','https://shop.example/dongle')
        doc=self.document('🏷️ #SONOFF #ZBDongle-E\nhttps://link.amazon/abc?tag=keep-21&value=end)')
        result=self.run_analysis(doc);self.assertEqual(result['products'],[])
        self.assertEqual(result['urls'][0]['url'],'https://link.amazon/abc?tag=keep-21&value=end)')

    def test_registered_campaign_alias_and_token_are_known_without_redirect(self):
        token='st_1234567890123456';code='ABC123456'
        with self.a.connection() as db:
            db.execute('INSERT INTO story_links VALUES(?,?,?,?,0)',(token,'campaign-id','SMLIGHT',self.a.now_iso()))
            db.execute('INSERT INTO short_aliases VALUES(?,?,?,?,0)',(code,token,'youtube',self.a.now_iso()))
        result=self.run_analysis(self.document(self.a.ORIGIN+'/'+code+'\n'+self.a.ORIGIN+'/go/'+token))
        self.assertTrue(all(u['known']['campaign_id']=='campaign-id' and u['kind']=='links' for u in result['urls']))
        self.assertEqual(result['products'],[])

    def test_moves_are_separate_and_do_not_relocate_permanent_references(self):
        result=self.run_analysis(self.document(self.reference()))
        self.assertFalse(any(p['kind']=='move' for p in result['proposals']))
        item,pub=self.link('Vidéo SMLIGHT MR1-U','https://youtu.be/eRgBHrvzJDw')
        content='Mon test : '+pub['url']+'\nKit CPL : https://amzn.to/example\nAutre : https://example.org/\n\n🙏 SOUTENIR LA CHAÎNE DOMOTIK STUDIO\nMerci\n\n🔗 REJOINDRE LA COMMUNAUTÉ\nLiens'
        result=self.run_analysis(self.document(content));moves=[p for p in result['proposals'] if p['kind']=='move']
        self.assertEqual({p['target_section'] for p in moves},{'affiliate','videos'});self.assertTrue(all(not p['selected'] for p in moves))
        self.assertFalse(any('MR1-U' in p['name'] or p['name']=='Mon test' for p in result['products']))

    def test_local_title_engine_reused_and_written_label_unchanged(self):
        known='MOES - Capteur CO monoxyde de carbone Zigbee Tuya'
        result=url_inspection.suggest_local_title('https://www.domadoo.fr/fr/moes-capteur.html',known_title=known)
        self.assertEqual(result['title'],'Capteur CO Zigbee MOES');self.assertIn('fingerprint',result['engine'])
        self.assertEqual(url_inspection.suggest_local_title('https://amzn.to/example',known_title=known,written_title='Mon choix 😀 EXACT')['title'],'Mon choix 😀 EXACT')

    def test_manual_choices_save_backup_and_read_only_analyze_endpoint(self):
        doc=self.document(self.reference());payload=self.edit_payload(doc)
        payload.update(analysis_version=1,products=[{'id':'manual-ref','kind':'manual-reference','query':'Hub ABC123'}],
                       selections={'description_analysis':{'url-choice':{'selected':False,'label':'Mon intitulé 😀','link_id':'known-id','source_id':'old-source'}}},manual_order=['manual-ref'])
        before=self.tracking_state();admin=self.server(True)
        with self.a.connection() as db,self.assertRaises(ValueError):d.analyze_draft(db,doc['id'],[],self.a.ORIGIN)
        with self.a.connection() as db:prior=d.get(db,d.TABLES[1],doc['id'])
        self.assertEqual(self.request(admin+'/api/descriptions/drafts/'+doc['id']+'/analyze',payload)[0],200)
        with self.a.connection() as db:self.assertEqual(d.get(db,d.TABLES[1],doc['id']),prior)
        self.assertEqual(self.request(admin+'/api/descriptions/drafts/'+doc['id']+'/save',payload)[0],200)
        with self.a.connection() as db:saved=d.get(db,d.TABLES[1],doc['id'])
        for key in ('products','selections','manual_order'):self.assertEqual(saved[key],payload[key])
        backup=json.loads(self.a.export_backup())
        with self.a.connection() as db:db.execute('DELETE FROM description_drafts')
        self.a.restore_backup(backup)
        with self.a.connection() as db:self.assertEqual(d.get(db,d.TABLES[1],doc['id']),saved)
        self.assertEqual(before,self.tracking_state())


if __name__=='__main__':unittest.main()
