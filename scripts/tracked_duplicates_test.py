"""Equivalent final destinations, explicit exceptions and serialized writes."""
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
import analytics_test
import tracked_links


class DuplicateTests(unittest.TestCase):
    setUp = analytics_test.AnalyticsTests.setUp
    tearDown = analytics_test.AnalyticsTests.tearDown
    server = analytics_test.AnalyticsTests.server
    request = analytics_test.AnalyticsTests.request

    def create(self, admin, name, url, **options):
        return self.request(admin+'/api/tracked-links', {'name': name, 'url': url, **options})

    def test_conservative_equivalence_preserves_affiliation_and_repeated_values(self):
        key = tracked_links.canonical_destination
        self.assertEqual(key('https://SHOP.example:443/%7eproduct?aff=117&x=1#code'),
                         key('https://shop.example/~product?x=1&aff=117#code'))
        self.assertEqual(key('https://shop.example'), key('https://shop.example/'))
        self.assertEqual(key('https://shop.example/p?a=1&b=2&a=3'), key('https://shop.example/p?a=1&a=3&b=2'))
        for left, right in [('?aff=117', '?aff=118'), ('?ref=CODE', '?ref=code'), ('?a=1&a=2', '?a=2&a=1'),
                            ('?aff=a+b', '?aff=a%20b'), ('?aff=a%26b', '?aff=a&b'), ('#code1', '#code2'),
                            ('?flag', '?flag='), ('?aff=117&utm_source=a', '?aff=117')]:
            self.assertNotEqual(key('https://shop.example/p'+left), key('https://shop.example/p'+right))
        self.assertNotEqual(key('https://shop.example/p'), key('http://shop.example/p'))

    def test_final_partner_preview_excludes_current_link_and_not_source_tokens(self):
        admin = self.server(True)
        final = 'https://www.domadoo.fr/produit?domid=117'
        status, body = self.create(admin, 'Produit existant', final)
        self.assertEqual(status, 201, body)
        ident = json.loads(body)['id']
        partner = next(row for row in json.loads(self.request(admin+'/api/affiliate-partners')[1])['items'] if row['name'] == 'Domadoo')
        status, body = self.request(admin+'/api/tracked-links/preview', {'url': 'https://www.domadoo.fr/produit', 'partner_id': partner['id'], 'apply_partner': True})
        preview = json.loads(body)
        self.assertEqual(preview['url'], final)
        self.assertEqual([row['id'] for row in preview['duplicates']], [ident])
        self.assertTrue(preview['duplicate_confirmation_required'])
        status, body = self.request(admin+'/api/tracked-links/preview', {'url': final, 'partner_id': '', 'link_id': ident})
        self.assertEqual(json.loads(body)['duplicates'], [])
        sources = json.loads(self.request(admin+'/api/tracking-sources')[1])['items'][:2]
        urls = [json.loads(self.request(admin+'/api/tracked-links/'+ident+'/token', {'source_id': source['id']})[1])['url'] for source in sources]
        self.assertNotEqual(*urls)
        self.assertEqual(len(json.loads(self.request(admin+'/api/tracked-links')[1])['items']), 1)

    def test_exception_is_explicit_and_scoped_to_the_current_matches(self):
        admin = self.server(True)
        first = json.loads(self.create(admin, 'Premier', 'https://shop.example/p?ref=A&x=1')[1])
        target = 'https://shop.example/p?x=1&ref=A'
        status, body = self.create(admin, 'Deuxième', target)
        self.assertEqual(status, 409, body)
        self.assertEqual(json.loads(body)['duplicates'][0]['name'], 'Premier')
        self.assertEqual(self.create(admin, 'Deuxième', target, allow_duplicate=True)[0], 409)
        status, body = self.create(admin, 'Deuxième', target, allow_duplicate=True, duplicate_ids=[first['id']])
        self.assertEqual(status, 201, body)
        # A newly appeared third-party match invalidates an older confirmation.
        self.assertEqual(self.create(admin, 'Troisième', target, allow_duplicate=True, duplicate_ids=[first['id']])[0], 409)
        self.assertEqual(len(json.loads(self.request(admin+'/api/tracked-links')[1])['items']), 2)

    def test_modification_is_checked_and_existing_duplicates_remain_editable(self):
        admin = self.server(True)
        first = json.loads(self.create(admin, 'Premier', 'https://shop.example/a?aff=117')[1])
        second = json.loads(self.create(admin, 'Deuxième', 'https://shop.example/b')[1])
        endpoint = admin+'/api/tracked-links/'+second['id']
        fields = {'name': 'Deuxième', 'url': first['url'], 'partner_id': '', 'expected_url': first['url'],
                  'previous_url': second['url'], 'confirm_destination': True}
        self.assertEqual(self.request(endpoint, fields, method='PUT')[0], 409)
        self.assertEqual(self.request(endpoint, {**fields, 'allow_duplicate': True, 'duplicate_ids': [first['id']]}, method='PUT')[0], 200)
        # A title-only change does not introduce another duplicate.
        fields.update(name='Deuxième renommé', previous_url=first['url'], confirm_destination=False)
        self.assertEqual(self.request(endpoint, fields, method='PUT')[0], 200)
        self.request(admin+'/api/tracked-links/'+first['id']+'/archive', {})
        preview = json.loads(self.request(admin+'/api/tracked-links/preview', {'url': first['url'], 'partner_id': '', 'link_id': second['id']})[1])
        self.assertTrue(preview['duplicates'][0]['archived'])
        self.assertFalse(preview['duplicate_confirmation_required'])

    def test_simultaneous_creations_are_serialized(self):
        admin = self.server(True)
        barrier = threading.Barrier(2)
        def create(index):
            barrier.wait()
            return self.create(admin, 'Concurrent '+str(index), ['https://shop.example/p?aff=117&x=1', 'https://shop.example/p?x=1&aff=117'][index])[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(create, [0, 1])), [201, 409])
        self.assertEqual(len(json.loads(self.request(admin+'/api/tracked-links')[1])['items']), 1)

    def test_simultaneous_destination_changes_are_serialized(self):
        admin = self.server(True)
        existing = [json.loads(self.create(admin, 'Lien '+str(index), 'https://shop.example/'+str(index))[1]) for index in range(2)]
        barrier = threading.Barrier(2)
        def update(index):
            barrier.wait()
            return self.request(admin+'/api/tracked-links/'+existing[index]['id'], {'name': existing[index]['name'], 'url': 'https://shop.example/target?ref=CODE'}, method='PUT')[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(update, [0, 1])), [200, 409])
        rows = json.loads(self.request(admin+'/api/tracked-links')[1])['items']
        self.assertEqual(sum(row['url'].endswith('target?ref=CODE') for row in rows), 1)


if __name__ == '__main__': unittest.main()
