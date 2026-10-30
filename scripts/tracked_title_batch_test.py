"""Atomic title-only bulk updates on disposable LinKs databases."""
import json
import unittest
import analytics_test


class BatchTitleTests(unittest.TestCase):
    setUp = analytics_test.AnalyticsTests.setUp
    tearDown = analytics_test.AnalyticsTests.tearDown
    server = analytics_test.AnalyticsTests.server
    request = analytics_test.AnalyticsTests.request

    def create(self, admin, name, url):
        status, body = self.request(admin+'/api/tracked-links', {'name': name, 'url': url, 'notes': 'Note conservée'})
        self.assertEqual(status, 201, body)
        return json.loads(body)

    def update(self, admin, *rows):
        return self.request(admin+'/api/tracked-links/titles/bulk-update', {'items': list(rows)})

    def change(self, row, name):
        return {'id': row['id'], 'name': name, 'expected_name': row['name'],
                'expected_updated_at': row['updated_at']}

    def read(self, admin, ident):
        return next(row for row in json.loads(self.request(admin+'/api/tracked-links')[1])['items'] if row['id'] == ident)

    def test_names_only_preserve_affiliation_original_urls_tokens_and_clicks(self):
        admin = self.server(True)
        origin = 'https://shop.reolink.com/camera'
        partners = json.loads(self.request(admin+'/api/affiliate-partners')[1])['items']
        partner = next(row for row in partners if row['name'] == 'Reolink')
        target = origin+'?aff=1404'
        status, body = self.request(admin+'/api/tracked-links', {
            'name': 'Ancien nom caméra', 'url': origin, 'partner_id': partner['id'],
            'expected_url': target, 'notes': 'Texte conservé'})
        self.assertEqual(status, 201, body)
        ident = json.loads(body)['id']
        source = json.loads(self.request(admin+'/api/tracking-sources')[1])['items'][0]
        status, body = self.request(admin+'/api/tracked-links/'+ident+'/token', {'source_id': source['id']})
        self.assertEqual(status, 200, body)
        token = json.loads(body)
        with self.a.connection() as db:
            db.execute('UPDATE tracked_tokens SET click_total=9 WHERE link_id=?', (ident,))
        before = self.read(admin, ident)
        status, body = self.update(admin, self.change(before, 'Reolink OMVI X16 PoE'))
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)['updated'], 1)
        after = self.read(admin, ident)
        for key in ('id', 'url', 'original_url', 'notes', 'partner_id', 'sources', 'clicks', 'created_at', 'archived', 'enabled'):
            self.assertEqual(after[key], before[key], key)
        self.assertEqual(after['name'], 'Reolink OMVI X16 PoE')
        status, body = self.request(admin+'/api/tracked-links/'+ident+'/token', {'source_id': source['id']})
        self.assertEqual(json.loads(body), token)
        self.assertEqual(after['url'], target)

    def test_two_updates_are_all_or_nothing_if_one_title_was_edited(self):
        admin = self.server(True)
        self.create(admin,'Avant 1','https://example.com/product-one')
        self.create(admin,'Avant 2','https://example.com/product-two')
        items = json.loads(self.request(admin+'/api/tracked-links')[1])['items']
        first,second = items[0],items[1]
        with self.a.connection() as db:
            db.execute('UPDATE tracked_links SET name=? WHERE id=?', ('Modifié ailleurs',second['id']))
        status, body = self.update(admin,self.change(first,'Nouveau 1'),self.change(second,'Nouveau 2'))
        self.assertEqual(status,400,body)
        self.assertIn('changé',json.loads(body)['error'])
        self.assertEqual(self.read(admin,first['id'])['name'],first['name'])
        self.assertEqual(self.read(admin,second['id'])['name'],'Modifié ailleurs')

    def test_revision_conflict_rejects_even_if_title_did_not_change(self):
        admin = self.server(True)
        self.create(admin,'Avant','https://example.com/a')
        item = json.loads(self.request(admin+'/api/tracked-links')[1])['items'][0]
        with self.a.connection() as db:
            db.execute('UPDATE tracked_links SET updated_at=? WHERE id=?',('2027-01-01T00:00:00Z',item['id']))
        status,_ = self.update(admin,self.change(item,'Après'))
        self.assertEqual(status,400)
        self.assertEqual(self.read(admin,item['id'])['name'],'Avant')

    def test_invalid_batches_and_archived_links_do_not_mutate(self):
        admin = self.server(True)
        self.create(admin,'Original','https://example.com/a')
        row = json.loads(self.request(admin+'/api/tracked-links')[1])['items'][0]
        valid = self.change(row,'Nouveau')
        for payload in (
            {'items':[]},{'items':[valid,valid]},
            {'items':[{**valid,'name':''}]},
            {'items':[{**valid,'name':'x'*161}]},
            {'items':[{**valid,'id':'bad'}]},
            {'items':[{'id':row['id'],'name':'Sans contrôle'}]},
            {'items':'invalid'}
        ):
            status,_=self.request(admin+'/api/tracked-links/titles/bulk-update',payload)
            self.assertEqual(status,400,payload)
            self.assertEqual(self.read(admin,row['id'])['name'],'Original')
        self.assertEqual(self.request(admin+'/api/tracked-links/'+row['id']+'/archive',{})[0],200)
        status,_=self.update(admin,valid)
        self.assertEqual(status,400)
        self.assertEqual(self.read(admin,row['id'])['name'],'Original')

    def test_public_instance_rejects_batch_mutation(self):
        public = self.server(False)
        self.assertEqual(self.request(public+'/api/tracked-links/titles/bulk-update',{'items':[]})[0],404)


if __name__ == '__main__':
    unittest.main()
