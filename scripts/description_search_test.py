"""Merchant preparation: simulated providers only, no outbound dependency."""
import copy
import json
import socket
import unittest
from unittest.mock import patch

import description_analysis as analysis
import description_search as search
import descriptions as d
import description_analysis_test as analysis_tests


class SearchTests(unittest.TestCase):
    for helper in ('setUp','tearDown','server','request','template','draft','editable','edit_payload','tracking_state','link','document','reference'):
        locals()[helper]=getattr(analysis_tests.AnalysisTests,helper)

    def payload(self,content='SMLIGHT SMHub Nano MG24',query=None):
        doc=self.document(content)
        with self.a.connection() as db:result=analysis.analyze(db,doc,self.a.ORIGIN)
        product=next(p for p in result['products'] if p['name']=='SMLIGHT SMHub Nano MG24')
        return doc,{'document':{'text':doc['text'],'sections':doc['sections']},'product_id':product['id'],'query':query or product['name']}

    def run_search(self,doc,payload):
        with patch.object(socket,'getaddrinfo',side_effect=AssertionError('No network')):
            with self.a.connection() as db:return search.search_product(db,doc['id'],payload,self.a.ORIGIN)

    def prepare(self,doc,payload,merchant='domadoo',url='https://www.domadoo.fr/fr/8664-hub.html',**extra):
        with patch.object(socket,'getaddrinfo',side_effect=AssertionError('No network')):
            with self.a.connection() as db:return search.prepare_link(db,doc['id'],{**payload,'merchant':merchant,'url':url,**extra},self.a.ORIGIN)

    def test_smlight_catalogue_and_explicit_urls_read_only(self):
        self.link('SMLIGHT SMHub Nano MG24','https://www.domadoo.fr/fr/8664-hub.html?domid=117')
        self.link('SMLIGHT SMHub Nano MG24','https://amzn.to/already')
        doc,p=self.payload(self.reference());before=self.tracking_state()
        with patch.object(search,'merchant_search',side_effect=AssertionError('Catalogue first')):result=self.run_search(doc,p)
        self.assertEqual(set(result['merchants']),{'domadoo','amazon'})
        self.assertTrue(all(v['status']=='existing' for v in result['merchants'].values()))
        self.assertEqual(before,self.tracking_state())

    def test_multiple_results_simulated_and_independent_errors(self):
        doc,p=self.payload()
        def provider(merchant,query):
            if merchant=='amazon':raise OSError('Unavailable')
            return {'status':'found','message':'','results':[{'title':'Hub MG24','reference':'MG24','url':'https://www.domadoo.fr/fr/1-hub.html'},{'title':'Hub MG21','reference':'MG21','url':'https://www.domadoo.fr/fr/2-hub.html'}]}
        with patch.object(search,'merchant_search',side_effect=provider):result=self.run_search(doc,p)
        self.assertEqual(len(result['merchants']['domadoo']['results']),2)
        self.assertEqual(result['merchants']['amazon']['status'],'error')
        self.assertTrue(all('selected' not in v for v in result['merchants']['domadoo']['results']))

    def test_assisted_default_and_no_match_provider(self):
        doc,p=self.payload();result=self.run_search(doc,p)
        self.assertEqual(result['merchants']['domadoo']['status'],'search_required')
        self.assertEqual(result['merchants']['amazon']['status'],'amazon_link_required')
        with patch.object(search,'merchant_search',return_value={'status':'no_match','results':[],'message':'Aucun résultat'}):
            self.assertTrue(all(m['status']=='no_match' for m in self.run_search(doc,p)['merchants'].values()))
        self.assertIn('s=SMLIGHT+MG24',search.search_url('domadoo','SMLIGHT MG24'))

    def test_global_retry_requests_only_unresolved_merchants(self):
        doc,p=self.payload()
        with patch.object(search,'merchant_search',wraps=search.merchant_search) as provider:
            result=self.run_search(doc,{**p,'merchants':['amazon']})
        self.assertEqual(set(result['merchants']),{'amazon'});provider.assert_called_once_with('amazon',p['query'])

    def test_domadoo_shared_preview_one_affiliate_parameter_and_duplicates(self):
        url='https://www.domadoo.fr/fr/8664-hub.html?x=A%2Bb&domid=117&domid=117#ref'
        item,pub=self.link('Hub existant','https://www.domadoo.fr/fr/8664-hub.html?x=A%2Bb&domid=117#ref')
        doc,p=self.payload();before=self.tracking_state();result=self.prepare(doc,p,url=url)
        self.assertEqual(result['url'].count('domid='),1);self.assertIn('x=A%2Bb',result['url'])
        self.assertEqual(result['original_url'],url);self.assertEqual(result['link_id'],item['id'])
        self.assertEqual(result['sources'][0]['url'],pub['url'])
        self.assertEqual(result['placements'][0]['merchant_id'],'domadoo')
        self.assertEqual(before,self.tracking_state())

    def test_amazon_exact_short_long_bare_and_no_partner_engine(self):
        doc,p=self.payload()
        with patch.object(search.affiliate_partners,'preview_tracked',side_effect=AssertionError('No Amazon rule')):
            for url in ['https://amzn.to/aB12','link.amazon/Ab_C?tag=exact-21','https://www.amazon.fr/dp/B0TEST?tag=exact-21&x=A%2Bb&x=+&ref_=😀#part']:
                result=self.prepare(doc,p,'amazon',url)
                self.assertEqual(result['url'],url);self.assertEqual(result['original_url'],url)
                self.assertEqual(result['mode'],'direct');self.assertEqual(result['sources'],[]);self.assertEqual(result['partner_id'],'')

    def test_existing_destination_never_reaffiliated_by_preparation(self):
        url='https://www.domadoo.fr/fr/8664-hub.html?domid=historical'
        item,_=self.link('SMLIGHT SMHub Nano MG24',url);doc,p=self.payload();before=self.tracking_state()
        for options in ({},{'link_id':item['id']}):
            result=self.prepare(doc,p,url=url,**options)
            self.assertEqual(result['url'],url);self.assertEqual(result['link_id'],item['id'])
        self.assertEqual(before,self.tracking_state())

    def test_invalid_destinations_no_redirect_or_wrong_merchant(self):
        doc,p=self.payload()
        for merchant,url in [('amazon','https://amazon.evil/dp/fake'),('amazon','https://www.amazon.fr/s?k=hub'),('amazon','https://amzn.to/a '),('amazon','https://links.example/go/token'),('domadoo','https://www.domadoo.fr/fr/recherche?s=hub'),('domadoo','https://example.org/hub'),('amazon','javascript:alert(1)')]:
            with self.subTest(url=url),self.assertRaises(ValueError):self.prepare(doc,p,merchant,url)

    def test_catalogue_multiple_duplicates_manual_choice_and_historical_sources(self):
        url='https://www.domadoo.fr/fr/8664-hub.html?domid=117'
        one,pub=self.link('SMLIGHT SMHub Nano MG24',url)
        with self.a.connection() as db:
            duplicate=self.a.tracked_links.create_link(db,{'name':'Autre fiche','url':url},self.a.story_url_valid,self.a.now_iso())
            source=db.execute("SELECT id FROM tracking_sources WHERE name='YouTube Post'").fetchone()[0]
            self.a.tracked_links.token_link(db,one['id'],source,self.a.ORIGIN,self.a.now_iso())
        doc,p=self.payload();result=self.prepare(doc,p,url=url)
        self.assertEqual(result['link_id'],'');self.assertEqual(len(result['duplicates']),2)
        result=self.prepare(doc,p,url=url,link_id=one['id'])
        self.assertEqual(result['link_id'],one['id']);self.assertEqual({s['name'] for s in result['sources']},{'YouTube Post','YouTube Description'})

    def test_corrected_keywords_do_not_create_products_or_accessories(self):
        self.link('SMLIGHT SMHub Nano MG21','https://amzn.to/mg21');self.link('Antenne SMLIGHT SMHub Nano MG24','https://amzn.to/antenna')
        doc,p=self.payload(query='SMLIGHT SMHub Nano MG21');result=self.run_search(doc,p)
        self.assertEqual(result['product_id'],p['product_id']);self.assertEqual(result['merchants']['amazon']['results'][0]['reference'],'SMLIGHT SMHub Nano MG21')
        p['product_id']='invented';self.assertRaises(ValueError,self.run_search,doc,p)

    def test_prepared_title_local_only_and_partner_missing(self):
        doc,p=self.payload();result=self.prepare(doc,p,label='Mon hub 😀 corrigé')
        self.assertEqual(result['label'],'Mon hub 😀 corrigé')
        with self.a.connection() as db:db.execute('DELETE FROM affiliate_partners')
        self.assertRaises(ValueError,self.prepare,doc,p)

    def test_state_revision_backup_restore_and_invalid_amazon(self):
        doc,p=self.payload();prepared=self.prepare(doc,p,'amazon','https://link.amazon/X?tag=stay-21')
        state={'version':1,'products':{p['product_id']:{'query':p['query'],'merchants':{'amazon':{'status':'found','url_input':prepared['url'],'prepared':prepared,'selected':True,'label':'Choix 😀','section_id':'affiliate','merchant_id':'amazon'}}}}}
        payload=self.edit_payload(doc);payload.update(analysis_version=1,products=[],selections={'merchant_search':state},manual_order=[p['product_id']])
        with self.a.connection() as db:
            saved=d.save_draft(db,doc['id'],payload);backup=d.export_backup(db)
            self.assertRaises(d.Conflict,d.save_draft,db,doc['id'],{**payload,'mutation_id':'different'})
            db.execute('DELETE FROM description_drafts');d.restore_backup(db,backup)
            self.assertEqual(d.get(db,d.TABLES[1],doc['id'])['selections']['merchant_search'],state)
        invalid=copy.deepcopy(state);invalid['products'][p['product_id']]['merchants']['amazon']['prepared']['url']='https://amzn.to/changed'
        self.assertRaises(ValueError,search.validate_state,invalid)
        # Clients from phase 2 omit all analysis fields and must preserve research.
        with self.a.connection() as db:
            saved=d.save_draft(db,doc['id'],{'title':saved['title'],'text':saved['text'],'sections':saved['sections'],'expected_revision':saved['revision'],'mutation_id':'older-client'})
        self.assertEqual(saved['selections']['merchant_search'],state)

    def test_http_endpoints_read_only_invalid_and_error(self):
        doc,p=self.payload();server=self.server(True);before=self.tracking_state()
        status,result=self.request(server+'/api/descriptions/drafts/'+doc['id']+'/search',p)
        self.assertEqual(status,200)
        status,result=self.request(server+'/api/descriptions/drafts/'+doc['id']+'/prepare',{**p,'merchant':'amazon','url':'https://amzn.to/official'})
        self.assertEqual(status,200);self.assertEqual(json.loads(result)['url'],'https://amzn.to/official')
        self.assertEqual(before,self.tracking_state())
        for path in ('search','prepare'):
            status,_=self.request(server+'/api/descriptions/drafts/'+doc['id']+'/'+path,[])
            self.assertEqual(status,400)


if __name__=='__main__':unittest.main()
