"""Step 2.1: conservation baseline, before any category-removal implementation.

The frozen V1.326 SQL is synthetic and deliberately still contains categories.
Only disposable databases are opened. The reference stays frozen while current
startup migrations run on its disposable copies.
Run: python3 -m unittest discover -s scripts -p tracked_categories_migration_test.py
"""
import copy
import importlib.util
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


FIXTURE = Path(__file__).with_name('fixtures') / 'tracked-categories-v1326.sql'
TABLE_KEYS = {
    'content_blocks': ('id',), 'top_buttons': ('id',), 'settings': ('key',),
    'counts': ('day', 'source', 'kind', 'link'), 'story_links': ('token',),
    'footer_quotes': ('id',), 'tracking_sources': ('id',), 'tracked_links': ('id',),
    'tracked_tokens': ('token',), 'short_aliases': ('code',),
    'tracking_source_keys': ('key',), 'affiliate_partners': ('id',),
    'tracked_link_partners': ('link_id',), 'campaign_partners': ('campaign_id',),
    'user_files': ('name',), 'upload_trash': ('name',),
}
AFFILIATE = '20000000000000000000000000000001'
DIRECT = '20000000000000000000000000000002'
DUPLICATE = '20000000000000000000000000000003'
ARCHIVED = '20000000000000000000000000000004'
DISABLED = '20000000000000000000000000000005'
VIDEO = 'dbd29cffcd1a536ea699c99ee087ea31'
CAMPAIGN = '30000000-0000-0000-0000-000000000001'
LEGACY_INSTAGRAM = '00000000000000000000000000000001'
PLATFORM_INSTAGRAM = '00000000000000000000000000000009'
PRIMARY_TOKEN = 'tk_0000000000000001'
PRIMARY_CODE = '000000002'
VIDEO_TOKEN = 'tk_0000000000000015'
VIDEO_CODE = '000000016'
ORIGINAL = 'https://shop.reolink.com/Produit?variant=a%2Bb&variant=c+d#d%C3%A9tails'
DESTINATION = 'https://shop.reolink.com/Produit?variant=a%2Bb&variant=c+d&aff=1404#d%C3%A9tails'
VIDEO_DATA = {'title': 'Un autre titre pour la même vidéo', 'url': 'https://youtu.be/abcdefghijk'}


def ordered_rows(table, rows):
    return sorted(rows, key=lambda row: tuple(row[key] for key in TABLE_KEYS[table]))


def conservation_state(db, include_category=False):
    """Keep every business column and exact value, except the one retired field.

    Columns are included even for empty tables, so lost columns cannot pass as an
    unchanged empty list. Primary-key ordering never relies on SQLite row order.
    """
    result = {}
    for table in sorted(TABLE_KEYS):
        columns = sorted(row[1] for row in db.execute('PRAGMA table_info("' + table + '")'))
        if table == 'tracked_links' and not include_category:
            columns = [column for column in columns if column != 'category']
        if not columns:
            raise AssertionError('Missing baseline table: ' + table)
        selected = ','.join('"' + column + '"' for column in columns)
        rows = [dict(zip(columns, row)) for row in db.execute('SELECT ' + selected + ' FROM "' + table + '"')]
        result[table] = {'columns': columns, 'rows': ordered_rows(table, rows)}
    return result


class BaselineClock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 10, 29, 11, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)


class CategoryConservationBaselineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='links-cat-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root / 'analytics.db'
        with closing(sqlite3.connect(self.database)) as db:
            db.executescript(FIXTURE.read_text(encoding='utf-8'))
            self.before = conservation_state(db)
        environment = patch.dict(os.environ, {
            'ANALYTICS_DB': str(self.database), 'UPLOAD_DIR': str(self.root / 'uploads'),
            'APP_RELEASE_VERSION': 'V1.326', 'APP_RELEASE_ID': 'bundled:V1.326',
        })
        environment.start()
        self.addCleanup(environment.stop)
        spec = importlib.util.spec_from_file_location('category_baseline_api', Path(__file__).with_name('analytics.py'))
        self.app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.app)
        clock = patch.object(self.app, 'datetime', BaselineClock)
        clock.start()
        self.addCleanup(clock.stop)
        self.app.init()

    def state(self):
        with self.app.connection() as db:
            return conservation_state(db)

    def assert_integrity(self):
        with self.app.connection() as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(list(db.execute('PRAGMA foreign_key_check')), [])
            self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0], 1)

    def public_server(self):
        server = self.app.serve(0, False, '127.0.0.1')
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def stop():
            server.shutdown()
            server.server_close()
            worker.join()
        self.addCleanup(stop)
        return 'http://127.0.0.1:' + str(server.server_port)

    def redirect(self, origin, path, method='HEAD'):
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, *args):
                return None
        opener = build_opener(ProxyHandler({}), NoRedirect)
        try:
            response = opener.open(Request(origin + path, method=method, headers={'User-Agent': 'Mozilla/5.0'}), timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.code, response.headers.get('Location')

    def test_historical_fixture_is_repeatable_and_covers_required_cases(self):
        with closing(sqlite3.connect(':memory:')) as db:
            db.executescript(FIXTURE.read_text(encoding='utf-8'))
            self.assertEqual(conservation_state(db), self.before)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(list(db.execute('PRAGMA foreign_key_check')), [])
            full = conservation_state(db, include_category=True)
        links = {row['id']: row for row in full['tracked_links']['rows']}
        self.assertEqual(set(links), {AFFILIATE, DIRECT, DUPLICATE, ARCHIVED, DISABLED, VIDEO})
        self.assertEqual(links[AFFILIATE]['category'], 'Éclairage / été')
        self.assertEqual(links[DIRECT]['category'], '')
        self.assertEqual(links[VIDEO]['category'], 'YouTube')
        self.assertEqual(links[AFFILIATE]['name'], 'Caméra été — façade')
        self.assertEqual(links[AFFILIATE]['url'], DESTINATION)
        self.assertEqual(links[DUPLICATE]['url'], DESTINATION)
        self.assertEqual((links[ARCHIVED]['archived'], links[ARCHIVED]['enabled']), (1, 1))
        self.assertEqual((links[DISABLED]['archived'], links[DISABLED]['enabled']), (0, 0))
        self.assertEqual(links[VIDEO]['url'], 'https://www.youtube.com/watch?v=abcdefghijk')
        self.assertEqual(len(full['tracked_tokens']['rows']), 8)
        self.assertEqual(len(full['short_aliases']['rows']), 13)
        self.assertEqual(len(full['story_links']['rows']), 2)
        self.assertEqual(len(full['content_blocks']['rows']), 3)
        campaign = next(row for row in full['content_blocks']['rows'] if row['id'] == CAMPAIGN)
        self.assertEqual((campaign['start_at'], campaign['end_at']),
                         ('2026-10-01T00:00:00Z', '2026-11-30T23:00:00Z'))
        partner = next(row for row in full['affiliate_partners']['rows'] if row['name'] == 'Reolink')
        self.assertEqual(partner['code'], 'CURRENT1404')
        self.assertEqual({row['kind'] for row in full['counts']['rows']},
                         {'view', 'click', 'impression', 'story', 'tracked', 'promo_code_copy'})
        self.assertIn('2001-01-01', {row['day'] for row in full['counts']['rows']})
        self.assertTrue(any(row['click_total'] == 0 for row in full['tracked_tokens']['rows']))
        self.assertTrue(any(row['click_total'] > 2**40 for row in full['tracked_tokens']['rows']))

    def test_reference_excludes_only_the_legacy_link_category(self):
        with closing(sqlite3.connect(':memory:')) as db:
            db.executescript(FIXTURE.read_text(encoding='utf-8'))
            full = conservation_state(db, include_category=True)
            for table, content in full.items():
                expected = copy.deepcopy(content)
                if table == 'tracked_links':
                    expected['columns'].remove('category')
                    for row in expected['rows']:
                        row.pop('category')
                self.assertEqual(self.before[table], expected, table)
            db.execute('UPDATE tracked_links SET category=? WHERE id=?', ('Autre classement', AFFILIATE))
            self.assertEqual(conservation_state(db), self.before)
            changes = [
                ('UPDATE tracked_links SET notes=? WHERE id=?', ('Notes altérées', AFFILIATE)),
                ('UPDATE tracked_links SET url=? WHERE id=?', ('https://example.org/changed', AFFILIATE)),
                ('UPDATE tracked_links SET enabled=0 WHERE id=?', (AFFILIATE,)),
                ('UPDATE tracked_link_partners SET original_url=? WHERE link_id=?', ('https://example.org/origin', AFFILIATE)),
                ('UPDATE tracked_tokens SET click_total=0 WHERE token=?', (PRIMARY_TOKEN,)),
                ('UPDATE tracked_tokens SET link_id=? WHERE token=?', (DIRECT, PRIMARY_TOKEN)),
                ('UPDATE short_aliases SET revoked=1 WHERE code=?', (PRIMARY_CODE,)),
                ('UPDATE tracking_source_keys SET source_id=? WHERE key=?', (PLATFORM_INSTAGRAM, 'instagram')),
                ('UPDATE counts SET total=1 WHERE kind=?', ('tracked',)),
                ('UPDATE content_blocks SET promo_code=? WHERE id=?', ('CHANGED', CAMPAIGN)),
                ('UPDATE campaign_partners SET final_url=? WHERE campaign_id=?', ('https://example.org/campaign', CAMPAIGN)),
            ]
            for statement, parameters in changes:
                with self.subTest(statement=statement):
                    db.execute('SAVEPOINT sensitivity')
                    try:
                        db.execute(statement, parameters)
                        self.assertNotEqual(conservation_state(db), self.before)
                    finally:
                        db.execute('ROLLBACK TO sensitivity')
                        db.execute('RELEASE sensitivity')

    def test_two_startups_preserve_every_useful_column_and_value(self):
        self.assertEqual(self.state(), self.before)
        self.app.init()
        self.assertEqual(self.state(), self.before)
        self.assert_integrity()

    def test_missing_blank_or_invalid_names_never_create_a_link(self):
        for fields in ({}, {'name': ''}, {'name': '   '}, {'name': None}, {'name': 'x' * 161}):
            with self.subTest(fields=fields):
                with self.app.connection() as db, self.assertRaisesRegex(ValueError, 'name'):
                    self.app.affiliate_partners.save_tracked(
                        db, {'url': 'https://example.org/new-destination', **fields},
                        self.app.story_url_valid, self.app.now_iso())
                self.assertEqual(self.state(), self.before)

    def test_reads_keep_names_destinations_partners_duplicates_and_period_totals(self):
        with self.app.connection() as db:
            links = {row['id']: row for row in self.app.affiliate_partners.list_tracked(db, '2026-10-01', '2026-10-29')}
            duplicates = self.app.tracked_links.duplicate_destinations(db, DESTINATION)
        self.assertEqual({row['id'] for row in duplicates}, {AFFILIATE, DUPLICATE})
        self.assertEqual(links[AFFILIATE]['name'], 'Caméra été — façade')
        self.assertEqual(links[AFFILIATE]['url'], DESTINATION)
        self.assertEqual(links[AFFILIATE]['original_url'], ORIGINAL)
        self.assertTrue(links[AFFILIATE]['partner_id'])
        self.assertEqual(links[DIRECT]['partner_id'], '')
        self.assertEqual(links[AFFILIATE]['clicks'], 1099511627795)
        self.assertEqual(links[AFFILIATE]['period_clicks'], 7)
        report = self.app.report('2026-10-01', '2026-10-29')
        self.assertEqual(sum(row['total'] for row in report['tracked']), 7)
        self.assertEqual(sum(row['total'] for row in report['stories']), 5)
        self.assertEqual(report['promo_code_copies'][0]['code'], 'OLD10')
        self.assertEqual({row['id'] for row in self.app.pulse_links()['links']}, {AFFILIATE, DIRECT, DUPLICATE, VIDEO})
        for period in (7, 30):
            stats = self.app.pulse_stats(period)
            self.assertEqual((stats['today'], stats['total'], stats['last7'], stats['stories']), (22, 22, 22, 12))
            self.assertEqual(len(stats['days']), period)
        public = self.app.public_config()
        self.assertTrue(all(ident not in json.dumps(public) for ident in (AFFILIATE, DIRECT, VIDEO)))
        self.assertEqual(self.state(), self.before)

    def test_reusing_sources_and_pulse_video_keeps_tokens_aliases_and_counters(self):
        with self.app.connection() as db:
            links = {row['id']: row for row in db.execute('SELECT * FROM tracked_links')}
            active_sources = {row['id'] for row in db.execute('SELECT * FROM tracking_sources WHERE active=1')}
            for token in db.execute('SELECT * FROM tracked_tokens').fetchall():
                link = links[token['link_id']]
                if link['archived'] or not link['enabled'] or token['source_id'] not in active_sources:
                    continue
                reused = self.app.tracked_links.token_link(db, token['link_id'], token['source_id'], self.app.ORIGIN, self.app.now_iso())
                self.assertEqual(reused['token'], token['token'])
        independent = self.app.pulse_story_link({'type': 'independent', 'id': AFFILIATE})
        self.assertEqual((independent['token'], independent['code']), (PRIMARY_TOKEN, PRIMARY_CODE))
        with patch.object(self.app, 'latest_video', return_value=VIDEO_DATA):
            for _ in range(2):
                reused = self.app.pulse_story_link({'type': 'youtube', 'id': 'abcdefghijk'})
                self.assertEqual((reused['token'], reused['code']), (VIDEO_TOKEN, VIDEO_CODE))
        for ident in (ARCHIVED, DISABLED):
            with self.assertRaises(ValueError):
                self.app.pulse_story_link({'type': 'independent', 'id': ident})
        self.assertEqual(self.state(), self.before)

    def test_existing_long_and_short_redirects_preserve_exact_targets_and_flags(self):
        origin = self.public_server()
        with self.app.connection() as db:
            tracked = {row['token']: dict(row) for row in db.execute('SELECT t.token,l.url,l.enabled FROM tracked_tokens t JOIN tracked_links l ON l.id=t.link_id')}
            stories = {row['token']: dict(row) for row in db.execute('SELECT s.token,b.url FROM story_links s JOIN content_blocks b ON b.id=s.promotion_id')}
            aliases = [dict(row) for row in db.execute('SELECT * FROM short_aliases ORDER BY code')]
        for token, item in {**tracked, **stories}.items():
            with self.subTest(token=token):
                expected = (302, item['url']) if item.get('enabled', 1) else (410, None)
                self.assertEqual(self.redirect(origin, '/go/' + token), expected)
        for alias in aliases:
            with self.subTest(code=alias['code']):
                item = tracked.get(alias['target_token']) or stories[alias['target_token']]
                expected = (410, None) if alias['revoked'] or not item.get('enabled', 1) else (302, item['url'])
                self.assertEqual(self.redirect(origin, '/' + alias['code']), expected)
        self.assertEqual(self.state(), self.before, 'HEAD and URL inspection must not count clicks')
        self.assertEqual(self.redirect(origin, '/' + PRIMARY_CODE, method='GET'), (302, DESTINATION))
        expected = copy.deepcopy(self.before)
        next(row for row in expected['tracked_tokens']['rows'] if row['token'] == PRIMARY_TOKEN)['click_total'] += 1
        next(row for row in expected['counts']['rows'] if row['day'] == '2026-10-29' and row['kind'] == 'tracked')['total'] += 1
        self.assertEqual(self.state(), expected, 'One real opening changes only its two counters')

    def test_backup_preview_and_invalid_input_do_not_change_the_reference(self):
        backup = json.loads(self.app.export_backup())
        original = copy.deepcopy(backup)
        files_before = {path.relative_to(self.root) for path in self.root.rglob('*')}
        summary = self.app.restore_backup(backup, preview=True)
        self.assertEqual(summary['published_redirects'], 10)
        self.assertEqual(self.state(), self.before)
        self.assertEqual({path.relative_to(self.root) for path in self.root.rglob('*')}, files_before)
        self.assertEqual(backup, original)
        invalid = copy.deepcopy(backup)
        invalid['tables']['tracked_links'][0]['name'] = ''
        with self.assertRaises(ValueError):
            self.app.restore_backup(invalid)
        self.assertEqual(self.state(), self.before)
        self.assertEqual({path.relative_to(self.root) for path in self.root.rglob('*')}, files_before)
        self.assert_integrity()

    def test_repeated_backup_restore_preserves_the_reference_and_input(self):
        backup = json.loads(self.app.export_backup())
        original = copy.deepcopy(backup)
        for table in self.app.BACKUP_TABLES:
            rows = [{key: value for key, value in row.items() if table != 'tracked_links' or key != 'category'}
                    for row in backup['tables'][table]]
            self.assertEqual(ordered_rows(table, rows), self.before[table]['rows'], table)
        for _ in range(2):
            self.app.restore_backup(backup)
            self.app.init()
            self.assertEqual(self.state(), self.before)
            self.assertEqual(backup, original)
            self.assert_integrity()

    def test_older_backup_cannot_erase_published_links_or_reduce_counters(self):
        older = json.loads(self.app.export_backup())
        tables = older['tables']
        removed = {row['token'] for row in tables['tracked_tokens'] if row['link_id'] == DIRECT}
        tables['tracked_links'] = [row for row in tables['tracked_links'] if row['id'] != DIRECT]
        tables['tracked_tokens'] = [row for row in tables['tracked_tokens'] if row['token'] not in removed]
        tables['short_aliases'] = [row for row in tables['short_aliases'] if row['target_token'] not in removed]
        for row in tables['tracked_tokens']:
            row['click_total'] = 0
        for row in tables['tracking_sources']:
            row['story_click_total'] = 0
        for row in tables['counts']:
            row['total'] = 1
        original = copy.deepcopy(older)
        for _ in range(2):
            self.app.restore_backup(older)
            self.assertEqual(self.state(), self.before)
            self.assertEqual(older, original)
        self.assert_integrity()


if __name__ == '__main__':
    unittest.main()
