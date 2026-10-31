"""HTTP contract for read-only title suggestions, using disposable SQLite fixtures."""
import json
import unittest
import hashlib
from pathlib import Path
from unittest.mock import patch

import analytics_test


class TrackedTitlePreviewTests(unittest.TestCase):
    setUp = analytics_test.AnalyticsTests.setUp
    tearDown = analytics_test.AnalyticsTests.tearDown
    server = analytics_test.AnalyticsTests.server
    request = analytics_test.AnalyticsTests.request

    def test_admin_api_returns_suggestion_without_database_mutations(self):
        admin = self.server(True)
        url = 'https://shop.reolink.com/product/omvi-x16'
        with self.a.connection() as db:
            before = dict(db.execute("SELECT COUNT(*) AS c FROM tracked_links").fetchone())['c']
        expected = {'title': 'Reolink OMVI X16 PoE', 'source': 'schema_product', 'status': 'ok'}
        with patch.object(self.a.url_inspection, 'suggest_title', return_value=expected) as mocked:
            status, body = self.request(admin+'/api/tracked-links/title-preview', {'url': url})
            self.assertEqual(status, 200, body)
            self.assertEqual(json.loads(body), expected)
            mocked.assert_called_once_with(url, current_title='', url_validator=self.a.story_url_valid)
        with self.a.connection() as db:
            after = db.execute("SELECT COUNT(*) AS c FROM tracked_links").fetchone()['c']
            token_count = db.execute("SELECT COUNT(*) AS c FROM tracked_tokens").fetchone()['c']
        self.assertEqual((after, token_count), (before, 0))

    def test_bad_urls_are_rejected_before_inspection(self):
        admin = self.server(True)
        invalid = ['', 'javascript:alert(1)', 'ftp://example.com/a', 'https://links.example/x',
                   'https://user:pass@example.com/private', 'https://example.com/one\nbad',
                   'x'*2001]
        with patch.object(self.a.url_inspection, 'suggest_title') as mocked:
            for value in invalid:
                with self.subTest(value=value):
                    status, _ = self.request(admin+'/api/tracked-links/title-preview', {'url': value})
                    self.assertEqual(status, 400)
            mocked.assert_not_called()

    def test_inspection_failure_is_non_blocking_and_read_only(self):
        admin = self.server(True)
        expected = {'title': '', 'source': '', 'status': 'unavailable'}
        with patch.object(self.a.url_inspection, 'suggest_title', return_value=expected):
            status, body = self.request(admin+'/api/tracked-links/title-preview', {'url': 'https://example.com/dp/B0SOMETHING'})
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body), expected)

    def test_public_api_does_not_expose_title_inspector(self):
        public = self.server(False)
        status, _ = self.request(public+'/api/tracked-links/title-preview', {'url': 'https://example.com'})
        self.assertEqual(status, 404)

    def test_current_title_is_compared_by_engine_without_any_database_write(self):
        admin = self.server(True)
        with self.a.connection() as db:
            before = list(db.iterdump())
        page = self.a.url_inspection.Response(200, 'text/html', b'<h1>Capteur CO MOES</h1>')
        with patch.object(self.a.url_inspection, '_fetch', return_value=(page, 'https://shop.example/item')):
            status, body = self.request(admin+'/api/tracked-links/title-preview', {
                'url': 'https://shop.example/item', 'current_title': 'Capteur CO MOES Zigbee'})
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result['title'], 'Capteur CO MOES Zigbee')
        self.assertEqual(result['status'], 'retained')
        self.assertEqual(result['confidence'], 'medium')
        with self.a.connection() as db:
            self.assertEqual(list(db.iterdump()), before)

    def test_invalid_current_titles_rejected_before_fetch(self):
        admin = self.server(True)
        with patch.object(self.a.url_inspection, 'suggest_title') as mocked:
            for title in [None, {}, 'x'*161]:
                status, _ = self.request(admin+'/api/tracked-links/title-preview', {
                    'url': 'https://shop.example/item', 'current_title': title})
                self.assertEqual(status, 400)
            mocked.assert_not_called()

    def test_real_editorial_preview_is_read_only_even_when_destination_fails(self):
        admin = self.server(True)
        engine = self.a.url_inspection
        with self.a.connection() as db:
            before = list(db.iterdump())
        with patch.object(engine, '_fetch', return_value=(engine.Response(403, 'text/html'), 'https://ko-fi.com/example')):
            status, body = self.request(admin+'/api/tracked-links/title-preview', {
                'url': 'https://ko-fi.com/example', 'current_title': 'Paye moi un cafe'})
        result = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual((result['title'], result['source'], result['status']), ('Paye-moi un café', 'editorial', 'ok'))
        self.assertEqual(result['diagnostics']['destination_decision']['reason'], 'http_403')
        self.assertEqual(result['engine']['fingerprint'], hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest()[:12])
        with self.a.connection() as db:
            self.assertEqual(list(db.iterdump()), before)

    def test_real_api_runs_corrected_engine_and_returns_sanitized_trace(self):
        from title_fetch_regression_test import TransportFixture, FIXTURES, MOES
        admin = self.server(True)
        engine = self.a.url_inspection
        fixture = TransportFixture((FIXTURES/'domadoo-moes.html').read_bytes() + b' ' * engine.MAX_HTML, 'gzip')
        with self.a.connection() as db:
            before = list(db.iterdump())
        with patch.object(engine, '_PinnedHTTPS', fixture.connection), \
             patch.object(engine, '_resolve_before_deadline', return_value='93.184.216.34'):
            status, body = self.request(admin+'/api/tracked-links/title-preview', {'url':MOES, 'current_title':'Capteur CO MOES'})
        result = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(result['title'], 'Capteur CO Zigbee MOES')
        self.assertEqual(result['engine'], {'id':'bounded-metadata-v2',
            'fingerprint':hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest()[:12]})
        self.assertEqual(result['diagnostics']['fetch']['http_status'], 200)
        self.assertEqual(result['diagnostics']['fetch']['content_encoding'], 'gzip')
        self.assertEqual(result['diagnostics']['extraction']['selected_source'], 'schema_product')
        self.assertEqual(result['diagnostics']['decision']['status'], 'ok')
        with self.a.connection() as db:
            self.assertEqual(list(db.iterdump()), before)


if __name__ == '__main__':
    unittest.main()
