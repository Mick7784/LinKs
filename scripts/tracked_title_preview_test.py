"""HTTP contract for read-only title suggestions, using disposable SQLite fixtures."""
import json
import unittest
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
            mocked.assert_called_once_with(url)
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


if __name__ == '__main__':
    unittest.main()
