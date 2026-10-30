"""Read-only bulk previews and atomic imports in a disposable LinKs instance."""
import json
import unittest

import analytics_test


class TrackedBatchTests(unittest.TestCase):
    setUp = analytics_test.AnalyticsTests.setUp
    tearDown = analytics_test.AnalyticsTests.tearDown
    server = analytics_test.AnalyticsTests.server
    request = analytics_test.AnalyticsTests.request

    def preview(self, admin, items):
        status, body = self.request(admin+'/api/tracked-links/batch/preview', {'items': items})
        self.assertEqual(status, 200, body)
        return json.loads(body)['items']

    def create(self, admin, items):
        return self.request(admin+'/api/tracked-links/batch/create', {'items': items})

    def prepared(self, url, name, row):
        return {'url': url, 'name': name, 'partner_id': row['partner_id'],
                'expected_url': row['final_url']}

    def stored(self, admin):
        return json.loads(self.request(admin+'/api/tracked-links')[1])['items']

    def test_preview_and_create_three_urls_without_sources_or_platforms(self):
        admin = self.server(True)
        urls = [
            'https://shop.reolink.com/product/omvi-x16',
            'https://www.domadoo.fr/product/zigbee',
            'https://example.com/generic-device',
        ]
        before = self.stored(admin)
        rows = self.preview(admin, [{'url': u} for u in urls])
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(not row['error'] and not row['duplicates'] for row in rows))
        self.assertEqual(rows[0]['final_url'], urls[0]+'?aff=1404')
        self.assertEqual(rows[1]['final_url'], urls[1]+'?domid=117')
        self.assertEqual(rows[2]['final_url'], urls[2])
        self.assertTrue(rows[0]['partner_id'] and rows[1]['partner_id'])
        self.assertEqual(rows[2]['partner_id'], '')
        self.assertEqual(self.stored(admin), before, 'Preview must not write to the database')
        data=[self.prepared(u,n,r) for u,n,r in zip(urls,[
            'Reolink OMVI X16 PoE','Domadoo Capteur Zigbee','Équipement générique'],rows)]
        status,body=self.create(admin,data)
        self.assertEqual(status,201,body)
        self.assertEqual(json.loads(body)['created'],3)
        stored=self.stored(admin)
        self.assertEqual(len(stored),3)
        self.assertEqual({x['name'] for x in stored},{x['name'] for x in data})
        self.assertEqual({x['url'] for x in stored},{x['final_url'] for x in rows})
        self.assertTrue(all('category' not in x for x in stored))
        with self.a.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tracked_tokens').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tracked_link_partners').fetchone()[0],2)

    def test_existing_destination_and_repeated_rows_are_not_created(self):
        admin=self.server(True)
        original='https://shop.reolink.com/product/cam?x=1'
        rows=self.preview(admin,[{'url':original}])
        payload=self.prepared(original,'Premier',rows[0])
        self.assertEqual(self.create(admin,[payload])[0],201)
        repeated=self.preview(admin,[{'url':original},{'url':original},
           {'url':'https://example.com/unique'}])
        self.assertEqual(repeated[0]['duplicates'][0]['name'],'Premier')
        self.assertEqual(repeated[1]['duplicate_of'],0)
        self.assertEqual(repeated[2]['duplicate_of'],None)
        status,_=self.create(admin,[payload])
        self.assertEqual(status,409)
        self.assertEqual(len(self.stored(admin)),1)

    def test_explicit_none_overrides_detected_partner(self):
        admin=self.server(True)
        url='https://www.domadoo.fr/produit'
        rows=self.preview(admin,[{'url':url,'manual_partner':True,'partner_id':''}])
        self.assertEqual(rows[0]['final_url'],url)
        self.assertEqual(rows[0]['partner_id'],'')
        status,body=self.create(admin,[self.prepared(url,'Domadoo direct',rows[0])])
        self.assertEqual(status,201,body)
        self.assertEqual(self.stored(admin)[0]['original_url'],url)

    def test_changes_since_preview_abort_entire_batch(self):
        admin=self.server(True)
        urls=['https://shop.reolink.com/p1','https://example.com/p2']
        rows=self.preview(admin,[{'url':url} for url in urls])
        batch=[self.prepared(url,name,row) for url,name,row in zip(urls,['Caméra','Deux'],rows)]
        with self.a.connection() as db:
            partner=db.execute('SELECT id FROM affiliate_partners WHERE name=?',('Reolink',)).fetchone()[0]
            db.execute('UPDATE affiliate_partners SET code=? WHERE id=?',('CHANGE',partner))
        status,body=self.create(admin,batch)
        self.assertEqual(status,400,body)
        self.assertEqual(self.stored(admin),[])
        self.assertIn('aperçu',json.loads(body)['error'].lower())

    def test_duplicate_inside_selected_batch_is_atomic(self):
        admin=self.server(True)
        url='https://example.com/product?b=2&a=1'
        rows=self.preview(admin,[{'url':url},{'url':'https://example.com/product?a=1&b=2'}])
        batch=[self.prepared(url,'Premier',rows[0]),self.prepared('https://example.com/product?a=1&b=2','Deuxième',rows[1])]
        status,body=self.create(admin,batch)
        self.assertEqual(status,400,body)
        self.assertIn('même destination',json.loads(body)['error'])
        self.assertEqual(self.stored(admin),[])

    def test_failed_row_reports_error_without_blocking_other_previews(self):
        admin=self.server(True)
        rows=self.preview(admin,[{'url':'file:///etc/passwd'},{'url':'https://example.com/p'}])
        self.assertTrue(rows[0]['error'])
        self.assertFalse(rows[1]['error'])
        batch=[self.prepared('https://example.com/p','Un',rows[1]),
               {'url':'javascript:alert(1)','name':'Mauvais','partner_id':'','expected_url':'javascript:alert(1)'}]
        self.assertEqual(self.create(admin,batch)[0],400)
        self.assertEqual(self.stored(admin),[])

    def test_invalid_batch_size_and_missing_partner_are_rejected(self):
        admin=self.server(True)
        for items in ([],[{'url':'https://example.com/x'}]*51):
            self.assertEqual(self.request(admin+'/api/tracked-links/batch/preview',{'items':items})[0],400)
            self.assertEqual(self.create(admin,items)[0],400)
        self.assertEqual(self.create(admin,[{
            'url':'https://example.com/p','name':'Un','expected_url':'https://example.com/p'}])[0],400)
        self.assertEqual(self.stored(admin),[])

    def test_public_service_cannot_preview_or_create(self):
        public=self.server(False)
        for path in ('preview','create'):
            status,_=self.request(public+'/api/tracked-links/batch/'+path,{'items':[{'url':'https://example.com/p'}]})
            self.assertEqual(status,404)


if __name__=='__main__':
    unittest.main()
