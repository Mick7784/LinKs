"""Real HTTP + SQLite tests of the scoped bridge over the shared LinKs engine."""
import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from analytics_test import AnalyticsTests
import affiliate_partners
import tracked_links


class PulseManagerTests(unittest.TestCase):
    setUpBase = AnalyticsTests.setUp
    tearDownBase = AnalyticsTests.tearDown
    server = AnalyticsTests.server
    request = AnalyticsTests.request
    redirect = AnalyticsTests.redirect

    def setUp(self):
        self.setUpBase()
        self.secret = 'fixture-pulse-bridge-'*3
        self.env = patch.dict(os.environ, {'PULSE_BRIDGE_TOKEN': self.secret})
        self.env.start()
        self.admin = self.server(True)
        self.public = self.server(False)

    def tearDown(self):
        self.env.stop()
        self.tearDownBase()

    def call(self, action, data=None, auth=True):
        status, body = self.request(self.admin+'/api/pulse/'+action, data,
            headers={'Content-Type':'application/json', **({'Authorization':'Bearer '+self.secret} if auth else {})})
        return status, json.loads(body) if body else {}

    def preview(self, name='Produit', url='https://shop.example/a', **extra):
        status, result = self.call('link-preview', {'name':name,'url':url,'partner_id':'',**extra})
        self.assertEqual(status, 200, result)
        return result

    def save(self, preview, **extra):
        return self.call('link-save', {**preview['receipt'], **extra})

    def test_access_receipts_projection_and_schema(self):
        with self.a.connection() as db:
            schema = list(map(tuple, db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY name')))
        for action, data in [('link-manager',None),('link-preview',{}),('link-save',{}),('link-token',{})]:
            self.assertEqual(self.call(action, data, auth=False)[0],401)
            self.assertEqual(self.request(self.public+'/api/pulse/'+action, data, headers={'Authorization':'Bearer '+self.secret,'Content-Type':'application/json'})[0],404)
        status, catalog = self.call('link-manager')
        self.assertEqual(status,200)
        self.assertEqual(catalog['version'],1)
        self.assertNotIn('template',json.dumps(catalog));self.assertNotIn(self.secret,json.dumps(catalog));self.assertNotIn('category',json.dumps(catalog))
        for data in [{'name':'','url':'https://shop.example','partner_id':''},{'name':'x','url':'javascript:alert(1)','partner_id':''},{'name':'x','url':self.a.ORIGIN+'/a','partner_id':''}]:
            self.assertEqual(self.call('link-preview',data)[0],400)
        p=self.preview()
        self.assertEqual(self.save(p,proof='wrong')[0],409)
        self.assertEqual(self.save(p,name='tampered')[0],409)
        self.assertEqual(self.save(p,expires=0)[0],409)
        self.assertEqual(self.save(p)[0],200)
        with self.a.connection() as db:
            self.assertEqual(schema,list(map(tuple, db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY name'))))

    def test_detection_manual_none_and_changed_rules(self):
        catalog=self.call('link-manager')[1]
        ids={p['name']:p['id'] for p in catalog['partners']}
        detected=self.preview(url='https://www.domadoo.fr/product',detect=True)
        self.assertEqual(detected['preview']['partner_id'],ids['Domadoo'])
        self.assertEqual(detected['preview']['url'],'https://www.domadoo.fr/product?domid=117')
        manual=self.preview(url='https://www.domadoo.fr/product',partner_id=ids['Reolink'])
        self.assertEqual(manual['preview']['url'],'https://www.domadoo.fr/product?aff=1404')
        direct=self.preview(url='https://www.domadoo.fr/product',partner_id='')
        self.assertEqual(direct['preview']['url'],'https://www.domadoo.fr/product')
        with self.a.connection() as db:db.execute('UPDATE affiliate_partners SET code=? WHERE id=?',('CHANGED',ids['Reolink']))
        self.assertEqual(self.save(manual)[0],400,'rules changed since preview: refuse stale final URL')
        first=self.save(detected)[1]['item']
        with self.a.connection() as db:db.execute('UPDATE affiliate_partners SET code=? WHERE id=?',('NEW',ids['Domadoo']))
        unchanged=self.preview(name='Renommé',url=first['original_url'],id=first['id'],revision=first['revision'],partner_id=first['partner_id'])
        self.assertEqual(unchanged['preview']['url'],first['url'])
        self.assertFalse(unchanged['preview']['changed'])
        self.assertEqual(self.save(unchanged)[0],200)

    def test_explicit_destination_tokens_and_existing_statistics(self):
        first=self.save(self.preview())[1]['item'];source=self.call('link-manager')[1]['sources'][0]['id']
        token=lambda expected:self.call('link-token',{'id':first['id'],'source_id':source,'expected_url':expected})
        status,short=token(first['url']);self.assertEqual(status,200);self.assertNotIn('token',short)
        self.assertEqual(short,token(first['url'])[1])
        from urllib.parse import urlsplit
        path=urlsplit(short['url']).path
        self.assertEqual(self.redirect(self.public+path)[0],302)
        with self.a.connection() as db:before=list(map(tuple,db.execute('SELECT * FROM counts')));tokens=list(map(tuple,db.execute('SELECT * FROM tracked_tokens')))
        changed=self.preview(url='https://shop.example/new',id=first['id'],revision=first['revision'])
        self.assertTrue(changed['preview']['changed']);self.assertEqual(self.save(changed)[0],400)
        saved=self.save(changed,confirm_destination=True)[1]['item']
        self.assertEqual(self.redirect(self.public+path,method='HEAD')[1]['Location'],saved['url'])
        self.assertEqual(token(first['url'])[0],409)
        self.assertEqual(token(saved['url'])[1],short)
        self.assertEqual(self.save(changed,confirm_destination=True)[0],409,'stale edit refused')
        with self.a.connection() as db:
            self.assertEqual(before,list(map(tuple,db.execute('SELECT * FROM counts'))));self.assertEqual(tokens,list(map(tuple,db.execute('SELECT * FROM tracked_tokens'))))
            db.execute('UPDATE tracking_sources SET active=0 WHERE id=?',(source,))
        self.assertEqual(token(saved['url'])[0],400)

    def test_duplicate_race_and_reuse(self):
        p=self.preview();barrier=threading.Barrier(2)
        def save(_):barrier.wait();return self.save(p)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(save,range(2)))
        self.assertEqual(sorted(r[0] for r in results),[200,409])
        duplicate=next(r[1] for r in results if r[0]==409)
        self.assertEqual(duplicate['code'],'DUPLICATE')
        again=self.preview();self.assertTrue(again['preview']['duplicate_confirmation_required'])
        self.assertEqual(self.save(again,allow_duplicate=True,duplicate_ids=[duplicate['duplicates'][0]['id']])[0],409)
        self.assertEqual(len(self.call('link-manager')[1]['items']),1)
        ident=duplicate['duplicates'][0]['id'];source=self.call('link-manager')[1]['sources'][0]['id']
        self.assertEqual(self.call('link-token',{'id':ident,'source_id':source,'expected_url':p['preview']['url']})[0],200)


if __name__=='__main__':unittest.main()
