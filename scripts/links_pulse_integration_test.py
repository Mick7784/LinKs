"""Cross-PR regressions: admin batch/title operations and the private PulSe bridge."""
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import urlsplit

import pulse_manager_test


class LinksPulseIntegrationTests(unittest.TestCase):
    # Reuse only the disposable HTTP/SQLite fixture, without collecting its tests.
    setUpBase = pulse_manager_test.PulseManagerTests.setUpBase
    tearDownBase = pulse_manager_test.PulseManagerTests.tearDownBase
    setUp = pulse_manager_test.PulseManagerTests.setUp
    tearDown = pulse_manager_test.PulseManagerTests.tearDown
    server = pulse_manager_test.PulseManagerTests.server
    request = pulse_manager_test.PulseManagerTests.request
    redirect = pulse_manager_test.PulseManagerTests.redirect
    call = pulse_manager_test.PulseManagerTests.call
    preview = pulse_manager_test.PulseManagerTests.preview
    save = pulse_manager_test.PulseManagerTests.save

    def admin_call(self, path, data=None):
        status, body = self.request(self.admin+'/api/tracked-links'+path, data)
        return status, json.loads(body) if body else {}

    def batch(self, *urls):
        status, value = self.admin_call('/batch/preview', {'items': [{'url': url} for url in urls]})
        self.assertEqual(status, 200, value)
        return {'items': [{'url': url, 'name': 'Lot '+str(i), 'partner_id': row['partner_id'],
                           'expected_url': row['final_url']}
                          for i, (url, row) in enumerate(zip(urls, value['items']))]}

    def title(self, item, name):
        return self.admin_call('/titles/bulk-update', {'items': [{
            'id': item['id'], 'name': name, 'expected_name': item['name'],
            'expected_updated_at': item['updated_at']}]})

    def snapshot(self):
        return json.loads(self.a.export_backup())['tables']

    def test_batch_and_pulse_duplicate_race_is_atomic(self):
        url = 'https://www.domadoo.fr/race?x=a%2Bb&x=c+d#details'
        batch = self.batch(url, 'https://shop.example/companion')
        preview = self.preview(url=url, detect=True)
        barrier = threading.Barrier(2)
        def run(operation):
            barrier.wait(timeout=5)
            return operation()
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(run, lambda: self.admin_call('/batch/create', batch))
            b = pool.submit(run, lambda: self.save(preview))
            admin, pulse = a.result(), b.result()
        self.assertIn((admin[0], pulse[0]), [(201, 409), (409, 200)])
        loser = pulse if admin[0] == 201 else admin
        self.assertEqual(len(loser[1]['duplicates']), 1)
        if admin[0] == 201:
            self.assertEqual(loser[1]['code'], 'DUPLICATE')
        items = self.call('link-manager')[1]['items']
        self.assertEqual(len(items), 2 if admin[0] == 201 else 1)
        self.assertEqual(sum(row['url'] == preview['preview']['url'] for row in items), 1)
        # Replaying either receipt cannot add a link after a lost successful response.
        self.assertEqual(self.save(preview)[0], 409)
        self.assertEqual(self.admin_call('/batch/create', batch)[0], 409)
        self.assertEqual(self.call('link-manager')[1]['items'], items)

    def test_bulk_title_invalidates_pulse_receipt_and_reverse(self):
        item = self.save(self.preview())[1]['item']
        pending = self.preview(name='PulSe pending', url=item['original_url'],
                               id=item['id'], revision=item['revision'])
        self.assertEqual(self.title(item, 'Titre LinKs')[0], 200)
        self.assertEqual(self.save(pending)[0], 409)
        current = self.call('link-manager')[1]['items'][0]
        self.assertEqual(current['name'], 'Titre LinKs')
        pending = self.preview(name='Titre PulSe', url=current['original_url'],
                               id=current['id'], revision=current['revision'])
        self.assertEqual(self.save(pending)[0], 200)
        self.assertEqual(self.title(current, 'Titre périmé')[0], 400)
        self.assertEqual(self.call('link-manager')[1]['items'][0]['name'], 'Titre PulSe')

    def test_concurrent_title_and_pulse_edit_have_one_winner(self):
        item = self.save(self.preview())[1]['item']
        pending = self.preview(name='Titre PulSe', url=item['original_url'],
                               id=item['id'], revision=item['revision'])
        barrier = threading.Barrier(2)
        def run(operation):
            barrier.wait(timeout=5)
            return operation()
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(run, lambda: self.title(item, 'Titre LinKs'))
            b = pool.submit(run, lambda: self.save(pending))
            admin, pulse = a.result(), b.result()
        self.assertIn((admin[0], pulse[0]), [(200, 409), (400, 200)])
        saved = self.call('link-manager')[1]['items'][0]
        self.assertEqual(saved['name'], 'Titre LinKs' if admin[0] == 200 else 'Titre PulSe')
        self.assertEqual(saved['url'], item['url'])

    def test_title_inspection_and_bridge_preserve_all_historical_data(self):
        url = 'https://www.domadoo.fr/legacy?x=a%2Bb&x=c+d#details'
        item = self.save(self.preview(name='Historique', url=url, detect=True))[1]['item']
        sources = self.call('link-manager')[1]['sources']
        tokens = []
        for platform in ('youtube', 'instagram', 'discord'):
            source = next(row for row in sources if row['platform'] == platform)
            data = {'id': item['id'], 'source_id': source['id'], 'expected_url': item['url']}
            status, short = self.call('link-token', data)
            self.assertEqual(status, 200)
            self.assertEqual(self.redirect(self.public+urlsplit(short['url']).path)[0], 302)
            tokens.append((data, short))
        before = self.snapshot()
        self.assertEqual(self.title(item, 'Titre analysé')[0], 200)
        with patch.object(self.a.url_inspection, 'check_destination',
                          return_value={'status': 'valid'}) as inspect:
            self.assertEqual(self.admin_call('/'+item['id']+'/check-destination',
                                            {'url': 'https://ignored.example'})[0], 200)
            inspect.assert_called_once_with(item['url'], url_validator=self.a.story_url_valid)
        for data, short in tokens:
            self.assertEqual(self.call('link-token', data)[1], short)
            status, headers = self.redirect(self.public+urlsplit(short['url']).path, method='HEAD')
            self.assertEqual(status, 302)
            self.assertEqual(headers['Location'], item['url'])
        for days in (7, 30):
            self.assertEqual(self.call('insights?days='+str(days))[1]['tracked_total'], 3)
        after = self.snapshot()
        for tables in (before, after):
            for row in tables['tracked_links']:
                row.pop('name')
                row.pop('updated_at')
        self.assertEqual(after, before, 'Only title and update timestamp may change')

    def test_bridge_bearer_does_not_authorize_new_admin_routes(self):
        item = self.save(self.preview())[1]['item']
        paths = ['/batch/preview', '/batch/create', '/titles/bulk-update',
                 '/title-preview', '/'+item['id']+'/check-destination']
        bearer = {'Authorization': 'Bearer '+self.secret, 'Content-Type': 'application/json'}
        with self.a.connection() as db:
            self.a.instance.put(db, 'auth.mode', 'local')
        before = self.snapshot()
        with patch.object(self.a.url_inspection, 'check_destination') as check, \
             patch.object(self.a.url_inspection, 'suggest_title') as suggest:
            for path in paths:
                self.assertEqual(self.request(self.admin+'/api/tracked-links'+path, {}, headers=bearer)[0], 401)
                self.assertEqual(self.request(self.public+'/api/tracked-links'+path, {}, headers=bearer)[0], 404)
            check.assert_not_called()
            suggest.assert_not_called()
        self.assertEqual(self.call('link-manager')[0], 200)
        self.assertEqual(self.call('link-manager', auth=False)[0], 401)
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
