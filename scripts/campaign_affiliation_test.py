"""Campaigns and tracked links share the same partner engine; no production data."""
import copy
import json
import unittest
from unittest.mock import patch
import os

import analytics_test
import affiliate_partners as partners


class CampaignAffiliationTests(unittest.TestCase):
    setUp=analytics_test.AnalyticsTests.setUp
    tearDown=analytics_test.AnalyticsTests.tearDown
    server=analytics_test.AnalyticsTests.server
    request=analytics_test.AnalyticsTests.request
    redirect=analytics_test.AnalyticsTests.redirect

    def configured(self):
        with self.a.connection() as db:return {row['name']:row for row in partners.rows(db)}

    def preview(self,data,ident=None):
        with self.a.connection() as db:return partners.preview_campaign(db,data,ident,self.a.valid_url)

    def save(self,data,ident=None,allow=False):
        result=self.preview(data,ident)
        payload={'type':'promo','title':'Campagne affiliée','url':data['url'],**data,
                 'partner_id':result['partner_id'],'detect':False,'expected_url':result['url'],
                 'previous_url':result['previous_url'],'confirm_destination':result['changed'],
                 'allow_duplicate':allow,'duplicate_ids':sorted(row['kind']+':'+row['id'] for row in result['duplicates'])}
        with self.a.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            return self.a.save_content_request(db,payload,ident)

    def campaign(self,ident):return next(row for row in self.a.content_list() if row['id']==ident)

    def test_auto_detects_all_existing_partners_with_real_domain_boundaries(self):
        configured=self.configured()
        for name,domain,suffix in [('Domadoo','www.domadoo.fr','domid=117'),('Reolink','shop.reolink.com','aff=1404'),('Sanyipace','eu.sanyipacetoilet.com','ref=DomotiK')]:
            raw='https://'+domain+'/product?color=blue#specs'
            data={'url':raw,'detect':True,'apply_partner':True}
            result=self.preview(data);self.assertEqual(result['partner_id'],configured[name]['id'])
            self.assertEqual(result['url'],'https://'+domain+'/product?color=blue&'+suffix+'#specs')
            ident=self.save(data);row=self.campaign(ident)
            self.assertEqual((row['original_url'],row['url'],row['partner_id']),(raw,result['url'],configured[name]['id']))
        for host in ['notreolink.com','reolink.com.other.example']:
            self.assertEqual(self.preview({'url':'https://'+host+'/p','detect':True})['partner_id'],'')

    def test_manual_partner_none_and_partner_changes_always_use_original(self):
        configured=self.configured();raw='https://shop.reolink.com/p?variant=1#info'
        data={'url':raw,'partner_id':configured['Domadoo']['id'],'apply_partner':True}
        ident=self.save(data);self.assertEqual(self.campaign(ident)['url'],raw.replace('#info','&domid=117#info'))
        data['partner_id']=configured['Reolink']['id'];self.save(data,ident)
        self.assertEqual(self.campaign(ident)['url'],'https://shop.reolink.com/p?variant=1&aff=1404#info')
        data['partner_id']='';self.save(data,ident)
        row=self.campaign(ident);self.assertEqual(row['url'],raw);self.assertEqual(row['partner_id'],'');self.assertTrue(row['affiliate_configured'])
        self.save({**data,'apply_partner':False,'title':'Rename only'},ident)
        self.assertEqual(self.campaign(ident)['url'],raw)

    def test_complex_queries_fragments_and_existing_codes_are_idempotent_for_both_flows(self):
        template='{url}?aff={code}';raw='https://shop.reolink.com/p?x=a%2Bb&x=c+d&aff=old&aff=older&empty=#section?keep=1'
        expected='https://shop.reolink.com/p?x=a%2Bb&x=c+d&empty=&aff=1404#section?keep=1'
        self.assertEqual(partners.build_url(template,'1404',raw),expected)
        self.assertEqual(partners.build_url(template,'1404',expected),expected)
        self.assertEqual(partners.build_url('{url}&aff={code}','1404','https://shop.reolink.com/p#x'),'https://shop.reolink.com/p?aff=1404#x')
        self.assertEqual(partners.build_url('{url}#{code}','ABC','https://shop.example/p?x=1#old'),'https://shop.example/p?x=1#ABC')
        data={'url':raw,'partner_id':self.configured()['Reolink']['id'],'apply_partner':True}
        with self.a.connection() as db:
            self.assertEqual(partners.preview_tracked(db,data)['url'],self.preview(data)['url'])
        ident=self.save(data);self.save({**data,'url':expected},ident)
        self.assertEqual(self.campaign(ident)['url'],expected)

    def test_custom_wrappers_encode_nested_query_and_fragments_without_reprocessing_tokens(self):
        raw='https://product.example/p?x=1&token=a%2Bb#details'
        with self.a.connection() as db:
            custom=partners.save(db,{'name':'Wrapper','code':'A&B','domains':['product.example'],
                'template':'https://redirect.example/{code}?target={url}'},self.a.now_iso())
        data={'url':raw,'partner_id':custom['id'],'apply_partner':True}
        final=self.preview(data)['url']
        self.assertEqual(partners.build_url(custom['template'],custom['code'],final),final)
        self.assertEqual(final,'https://redirect.example/A&B?target=https://product.example/p%3Fx%3D1%26token%3Da%252Bb%23details')
        ident=self.save(data);self.assertEqual(self.campaign(ident)['original_url'],raw)
        self.save({**data,'url':final},ident)
        self.assertEqual(self.campaign(ident)['url'],final)
        self.assertEqual(self.campaign(ident)['original_url'],raw)
        self.assertEqual(partners.build_url('{url}?ref={code}','A&B#C','https://product.example/p'),'https://product.example/p?ref=A%26B%23C')

    def test_unchanged_edit_and_partner_rule_changes_preserve_published_destination(self):
        partner=self.configured()['Reolink'];data={'url':'https://reolink.com/p','partner_id':partner['id'],'apply_partner':True}
        ident=self.save(data);before=self.campaign(ident)
        with self.a.connection() as db:partners.save(db,{**partner,'code':'NEW'},self.a.now_iso(),partner['id'])
        self.save({**data,'apply_partner':False,'title':'Renamed'},ident)
        self.assertEqual(self.campaign(ident)['url'],before['url'])
        self.save(data,ident);self.assertEqual(self.campaign(ident)['url'],'https://reolink.com/p?aff=NEW')
        for _ in range(2):self.save({**data,'apply_partner':False},ident)
        self.assertEqual(self.campaign(ident)['url'].count('aff='),1)

    def test_stale_preview_and_destination_replacement_require_existing_guards(self):
        admin=self.server(True);partner=self.configured()['Reolink'];data={'type':'promo','title':'Race','url':'https://reolink.com/p','partner_id':partner['id'],'apply_partner':True}
        result=self.preview(data)
        with self.a.connection() as db:partners.save(db,{**partner,'code':'NEW'},self.a.now_iso(),partner['id'])
        self.assertEqual(self.request(admin+'/api/content',{**data,'expected_url':result['url']})[0],400)
        ident=self.save(data);current=self.campaign(ident);changed={**data,'url':'https://reolink.com/other'};result=self.preview(changed,ident)
        payload={**changed,'expected_url':result['url'],'previous_url':current['url']}
        self.assertEqual(self.request(admin+'/api/content/'+ident,payload,method='PUT')[0],400)
        self.assertEqual(self.campaign(ident)['url'],current['url'])
        self.assertEqual(self.request(admin+'/api/content/'+ident,{**payload,'confirm_destination':True},method='PUT')[0],204)

    def test_final_duplicates_find_campaigns_and_tracked_links_without_losing_statistics(self):
        partner=self.configured()['Reolink'];data={'url':'https://reolink.com/p?x=1','partner_id':partner['id'],'apply_partner':True}
        existing=self.save(data);self.a.record('click','youtube','block:'+existing,'2000-01-01')
        tracked=json.loads(self.request(self.server(True)+'/api/tracked-links',{'name':'Existing tracked','url':self.campaign(existing)['url']})[1])
        result=self.preview(data);self.assertEqual({(r['kind'],r['id']) for r in result['duplicates']},{('campaign',existing),('tracked',tracked['id'])})
        with self.assertRaises(ValueError):self.save(data)
        self.save({**data,'apply_partner':False,'title':'Reused existing campaign'},existing)
        self.assertEqual(self.campaign(existing)['clicks'],1)
        exceptional=self.save(data,allow=True)
        self.assertNotEqual(exceptional,existing);self.assertEqual(self.campaign(existing)['clicks'],1)
        self.assertEqual(self.campaign(exceptional)['clicks'],0)

    def test_public_shared_and_pulse_destinations_use_final_url_with_stable_tokens(self):
        partner=self.configured()['Domadoo'];data={'url':'https://domadoo.fr/p?variant=1#details','partner_id':partner['id'],'apply_partner':True}
        ident=self.save(data);public=self.server();short=self.a.story_link(ident,'youtube');long=self.a.story_link(ident)
        self.a.record('click','youtube','block:'+ident);self.a.record('impression','youtube','block:'+ident)
        counts=json.loads(self.a.export_backup())['tables']['counts']
        self.assertEqual(next(r for r in self.a.public_config()['links'] if r['id']==ident)['url'],self.campaign(ident)['url'])
        self.assertEqual(self.redirect(public+'/'+short['code'],method='HEAD')[1]['Location'],'https://domadoo.fr/p?variant=1&domid=117#details')
        self.save({**data,'url':'https://domadoo.fr/new#more'},ident)
        self.assertEqual(self.a.story_link(ident,'youtube'),short);self.assertEqual(self.a.story_link(ident),long)
        self.assertEqual(self.redirect(public+'/'+short['code'],method='HEAD')[1]['Location'],'https://domadoo.fr/new?domid=117#more')
        with patch.dict(os.environ,{'PULSE_BRIDGE_TOKEN':'x'*64}):
            status,body=self.request(self.server(True)+'/api/pulse/story-link',{'type':'campaign','id':ident},{'Authorization':'Bearer '+'x'*64,'Content-Type':'application/json'})
            self.assertEqual(status,200,body)
        self.assertEqual(json.loads(self.a.export_backup())['tables']['counts'],counts)

    def test_historical_featured_and_legacy_api_never_retrofit_affiliation(self):
        admin=self.server(True);raw='https://reolink.com/p?aff=historical#raw'
        status,body=self.request(admin+'/api/content',{'type':'featured','title':'Legacy','url':raw})
        self.assertEqual(status,201);ident=json.loads(body)['id'];before=self.campaign(ident)
        for _ in range(2):self.a.init()
        self.assertFalse(self.campaign(ident)['affiliate_configured'])
        self.assertEqual(self.preview({'url':raw,'partner_id':'','apply_partner':False},ident)['url'],raw)
        self.assertEqual(self.request(admin+'/api/content/'+ident,{**before,'title':'Rename only'},method='PUT')[0],204)
        self.assertEqual(self.campaign(ident)['url'],raw);self.assertEqual(self.campaign(ident)['type'],'featured')
        self.assertEqual(self.campaign(ident)['partner_id'],'')

    def test_backups_old_restore_and_partner_removal_keep_latest_provenance(self):
        old=json.loads(self.a.export_backup());partner=self.configured()['Domadoo'];data={'url':'https://domadoo.fr/p','partner_id':partner['id'],'apply_partner':True}
        ident=self.save(data);short=self.a.story_link(ident,'youtube');backup=json.loads(self.a.export_backup())
        self.save({**data,'url':'https://domadoo.fr/new'},ident);current=self.campaign(ident)
        for snapshot in [copy.deepcopy(backup),copy.deepcopy(old)]:
            snapshot['tables'].pop('campaign_partners',None)
            self.a.restore_backup(snapshot)
            row=next(r for r in self.a.content_list()+self.a.content_list(True) if r['id']==ident)
            self.assertEqual((row['url'],row['original_url'],row['partner_id']),(current['url'],current['original_url'],partner['id']))
            self.assertEqual(self.a.story_link(ident,'youtube'),short)
        self.assertEqual(self.request(self.server(True)+'/api/affiliate-partners/'+partner['id'],method='DELETE')[0],409)

    def test_preview_is_private_read_only_and_owned_metadata_does_not_block_unused_expiry(self):
        admin=self.server(True);data={'url':'https://reolink.com/p','detect':True,'apply_partner':True}
        before=json.loads(self.a.export_backup())['tables'];files=set(self.a.DATA_DIR.rglob('*'))
        self.assertEqual(self.request(admin+'/api/content/preview',data)[0],200)
        self.assertEqual(json.loads(self.a.export_backup())['tables'],before);self.assertEqual(set(self.a.DATA_DIR.rglob('*')),files)
        self.assertEqual(self.request(self.server()+'/api/content/preview',data)[0],404)
        ident=self.save({**data,'end_at':'2000-01-02T00:00:00Z'})
        self.assertEqual(self.a.cleanup_campaigns()['deleted_ids'],[ident])
        with self.a.connection() as db:self.assertIsNone(db.execute('SELECT 1 FROM campaign_partners WHERE campaign_id=?',(ident,)).fetchone())


if __name__=='__main__':unittest.main()
