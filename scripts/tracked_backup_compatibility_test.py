"""Backup contracts on synthetic databases, including legacy startup migration."""
import base64
import copy
import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing, contextmanager
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from images_test import raster
import tracked_categories_migration_test as baseline
from tracked_categories_migration_test import (
    AFFILIATE, DIRECT, FIXTURE, LEGACY_INSTAGRAM, conservation_state, ordered_rows,
)


class TrackedBackupCompatibilityTests(unittest.TestCase):
    setUp = baseline.CategoryConservationBaselineTests.setUp
    state = baseline.CategoryConservationBaselineTests.state
    assert_integrity = baseline.CategoryConservationBaselineTests.assert_integrity

    def full_state(self):
        with self.app.connection() as db:
            return conservation_state(db, include_category=True)

    def layout(self):
        with self.app.connection() as db:
            return [tuple(row) for row in db.execute('PRAGMA table_info(tracked_links)')]

    def files(self):
        result = {}
        for path in self.app.DATA_DIR.rglob('*'):
            if path.name in {Path(self.app.DB).name, Path(self.app.DB).name+'-wal', Path(self.app.DB).name+'-shm'}:
                continue
            result[str(path.relative_to(self.app.DATA_DIR))] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        return result

    def payload(self, version=3, legacy=False):
        data = json.loads(self.app.export_backup())
        data['version'] = version
        if legacy:
            with closing(sqlite3.connect(':memory:')) as historical:
                historical.executescript(FIXTURE.read_text(encoding='utf-8'))
                categories = dict(historical.execute('SELECT id,category FROM tracked_links'))
            for index, row in enumerate(data['tables']['tracked_links']):
                if legacy is True or index % 2 == 0:
                    row['category'] = categories[row['id']]
        return data

    @contextmanager
    def receiver(self, category, populated=True):
        """Create a separate receiving schema directly, never ALTER a database."""
        with tempfile.TemporaryDirectory(prefix='recv-', dir=self.root) as directory:
            root = Path(directory)
            database = root / 'analytics.db'
            (root / 'uploads').mkdir()
            with closing(sqlite3.connect(':memory:')) as source, closing(sqlite3.connect(database)) as target:
                source.executescript(FIXTURE.read_text(encoding='utf-8'))
                tables = list(source.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"))
                for name, sql in tables:
                    if name == 'tracked_links' and not category:
                        field = "category TEXT NOT NULL DEFAULT '', "
                        self.assertIn(field, sql)
                        sql = sql.replace(field, '', 1)
                    target.execute(sql)
                if populated:
                    for name, _ in tables:
                        columns = [row[1] for row in target.execute('PRAGMA table_info("'+name+'")')]
                        selected = ','.join('"'+column+'"' for column in columns)
                        rows = list(source.execute('SELECT '+selected+' FROM "'+name+'"'))
                        target.executemany('INSERT INTO "'+name+'" ('+selected+') VALUES ('+','.join('?' for _ in columns)+')', rows)
                for row in source.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"):
                    target.execute(row[0])
                target.commit()
                self.assertEqual(list(target.execute('PRAGMA foreign_key_check')), [])
            with patch.object(self.app, 'DB', str(database)), patch.object(self.app, 'DATA_DIR', root), \
                 patch.object(self.app, 'UPLOADS', root / 'uploads'):
                if populated:
                    self.app.init()
                yield

    def assert_preview_unchanged(self, data):
        before = self.full_state()
        files = self.files()
        original = copy.deepcopy(data)
        with patch.object(self.app, 'restore_safety', side_effect=AssertionError('Preview must not create a safety copy')):
            summary = self.app.restore_backup(data, preview=True)
        self.assertEqual(summary['published_redirects'], 10)
        self.assertEqual(summary['counter_total'], 108)
        self.assertEqual(self.full_state(), before)
        self.assertEqual(self.files(), files)
        self.assertEqual(data, original)

    def test_export_removes_only_the_retired_field_and_never_changes_the_database(self):
        with self.app.connection() as db:
            db.execute('UPDATE tracked_links SET notes=? WHERE id=?', ('Texte category à conserver : {"category":"notes"}', AFFILIATE))
            db.execute('UPDATE tracked_links SET url=? WHERE id=?', ('https://example.org/direct?category=keep#category', DIRECT))
        before = self.full_state()
        schema = self.layout()
        exported = json.loads(self.app.export_backup())
        self.assertEqual((exported['format'], exported['version']), ('links-backup', 3))
        self.assertEqual(set(exported['tables']), set(self.app.BACKUP_TABLES))
        for table, rows in exported['tables'].items():
            expected = copy.deepcopy(before[table]['rows'])
            if table == 'tracked_links':
                for row in expected:
                    row.pop('category', None)
                self.assertTrue(all('category' not in row for row in rows))
            self.assertEqual(ordered_rows(table, rows), expected, table)
        self.assertEqual(self.full_state(), before)
        self.assertEqual(self.layout(), schema)

    def test_versions_one_two_three_accept_old_new_and_mixed_rows_on_both_schemas(self):
        cases = [self.payload(version, legacy) for version in (1, 2, 3) for legacy in (True, False, 'mixed')]
        for category in (True, False):
            with self.subTest(category_column=category), self.receiver(category):
                before = self.full_state()
                layout = self.layout()
                for data in cases:
                    with self.subTest(version=data['version'], keys=[set(row) for row in data['tables']['tracked_links']]):
                        self.assert_preview_unchanged(data)
                        original = copy.deepcopy(data)
                        for _ in range(2):
                            self.app.restore_backup(data)
                            self.app.init()
                            self.assertEqual(self.full_state(), before)
                            self.assertEqual(self.layout(), layout)
                            self.assertEqual(data, original)
                            self.assertTrue(all('category' not in row for row in json.loads(self.app.export_backup())['tables']['tracked_links']))
                        self.assert_integrity()

    def test_pre_tracking_versions_keep_links_sources_aliases_partners_and_history(self):
        cases = []
        for version in (1, 2):
            data = self.payload(version)
            for table in ('tracking_sources', 'tracked_links', 'tracked_tokens', 'tracking_source_keys',
                          'short_aliases', 'affiliate_partners', 'tracked_link_partners', 'campaign_partners', 'story_links', 'footer_quotes'):
                data['tables'].pop(table)
            data['tables']['counts'] = [row for row in data['tables']['counts'] if row['kind'] in {'view', 'click', 'impression'}]
            cases.append(data)
        for category in (True, False):
            with self.subTest(category_column=category), self.receiver(category):
                before = self.full_state()
                for data in cases:
                    self.assert_preview_unchanged(data)
                    for _ in range(2):
                        self.app.restore_backup(data)
                        self.assertEqual(self.full_state(), before)
                self.assert_integrity()

    def test_empty_receivers_restore_all_useful_data_without_importing_categories(self):
        cases = [self.payload(legacy=legacy) for legacy in (True, False)]
        for category in (True, False):
            for data in cases:
                with self.subTest(category_column=category, legacy='category' in data['tables']['tracked_links'][0]), \
                     self.receiver(category, populated=False):
                    for _ in range(2):
                        self.app.restore_backup(data)
                        self.app.init()
                        self.assertEqual(self.state(), self.before)
                        self.assertFalse(any(row[1]=='category' for row in self.layout()))
                        self.assert_integrity()

    def test_obsolete_category_values_are_discarded_instead_of_validated_or_stored(self):
        data = self.payload(legacy=True)
        for category in (True, False):
            with self.subTest(category_column=category), self.receiver(category):
                before = self.full_state()
                for obsolete in (None, 17, ['ignored'], {'ignored': True}, 'x'*17000):
                    variant = copy.deepcopy(data)
                    variant['tables']['tracked_links'][0]['category'] = obsolete
                    original = copy.deepcopy(variant)
                    self.app.restore_backup(variant)
                    self.assertEqual(self.full_state(), before)
                    self.assertEqual(variant, original)

    def test_new_published_link_restores_identity_provenance_and_exact_counters(self):
        new_id = '60000000000000000000000000000001'
        token, code = 'tk_'+'N'*16, 'Restore01'
        origin = 'https://shop.reolink.com/new?color=blue#details'
        destination = 'https://shop.reolink.com/new?color=blue&aff=1404#details'
        data = self.payload(legacy=True)
        row = copy.deepcopy(next(row for row in data['tables']['tracked_links'] if row['id']==AFFILIATE))
        row.update(id=new_id, name='Lien publié restauré', url=destination, notes='Origine et statistiques conservées', category='À ignorer')
        association = copy.deepcopy(data['tables']['tracked_link_partners'][0])
        association.update(link_id=new_id, original_url=origin)
        tracked = {'token': token, 'link_id': new_id, 'source_id': LEGACY_INSTAGRAM, 'click_total': 4, 'created_at': row['created_at']}
        alias = {'code': code, 'target_token': token, 'source': 'tracked:'+LEGACY_INSTAGRAM, 'created_at': row['created_at'], 'revoked': 0}
        count = {'day': '2026-10-28', 'source': alias['source'], 'kind': 'tracked', 'link': 'tracked:'+token+':09', 'total': 4}
        additions = {'tracked_links': row, 'tracked_link_partners': association, 'tracked_tokens': tracked, 'short_aliases': alias, 'counts': count}
        expected = copy.deepcopy(self.before)
        for table, item in additions.items():
            data['tables'][table].append(copy.deepcopy(item))
            clean = {key: value for key, value in item.items() if table!='tracked_links' or key!='category'}
            expected[table]['rows'] = ordered_rows(table, expected[table]['rows'] + [clean])
        original = copy.deepcopy(data)
        for category in (True, False):
            with self.subTest(category_column=category), self.receiver(category):
                for _ in range(2):
                    self.app.restore_backup(data)
                    self.assertEqual(self.state(), expected)
                    self.assertEqual(data, original)
                with self.app.connection() as db:
                    self.assertEqual(dict(self.app.tracked_links.find_destination(db, token))['url'], destination)
                    self.assertEqual(self.app.short_urls.lookup(db, code)['target_token'], token)
                    self.assertEqual(self.app.affiliate_partners.link_metadata(db, new_id, destination)['original_url'], origin)
                    self.assertNotIn('category',[column['name'] for column in db.execute('PRAGMA table_info(tracked_links)')])
                self.assert_integrity()

    def test_unknown_missing_invalid_and_conflicting_data_remain_rejected_atomically(self):
        data = self.payload(legacy=True)
        mutations = [
            lambda payload: payload['tables']['tracked_links'][0].update(category_id='unknown'),
            lambda payload: payload['tables']['top_buttons'][0].update(category='unrelated unknown field'),
            lambda payload: payload['tables']['tracked_links'][0].pop('notes'),
            lambda payload: payload['tables']['tracked_links'][0].pop('name'),
            lambda payload: payload['tables']['tracked_links'][0].update(name='   '),
            lambda payload: payload['tables']['tracked_links'][0].update(url='javascript:invalid'),
            lambda payload: payload['tables']['tracked_tokens'][0].update(click_total=-1),
            lambda payload: payload['tables']['tracked_tokens'][0].update(link_id=DIRECT),
            lambda payload: payload['tables']['short_aliases'][0].update(target_token='tk_'+'Z'*16),
            lambda payload: payload['tables']['tracked_links'].append(copy.deepcopy(payload['tables']['tracked_links'][0])),
            lambda payload: payload['tables'].pop('tracked_tokens'),
            lambda payload: payload.update(instance_id='f'*32),
            lambda payload: payload.update(version=4),
        ]
        for category in (True, False):
            with self.subTest(category_column=category), self.receiver(category):
                before, files = self.full_state(), self.files()
                for index, mutate in enumerate(mutations):
                    for preview in (True, False):
                        with self.subTest(case=index, preview=preview):
                            invalid = copy.deepcopy(data)
                            mutate(invalid)
                            original = copy.deepcopy(invalid)
                            with patch.object(self.app, 'restore_safety', side_effect=AssertionError('Invalid data must fail before safety copy')), self.assertRaises(ValueError):
                                self.app.restore_backup(invalid, preview=preview)
                            self.assertEqual(self.full_state(), before)
                            self.assertEqual(self.files(), files)
                            self.assertEqual(invalid, original)
                self.assert_integrity()

    def test_media_failure_rolls_back_data_and_keeps_the_pre_restore_sqlite_copy(self):
        data = self.payload(legacy=True)
        name = '70000000-0000-0000-0000-000000000001.png'
        data['images'][name] = base64.b64encode(raster()).decode('ascii')
        data['tables']['content_blocks'][0]['image'] = '/uploads/'+name
        original = copy.deepcopy(data)
        for category in (True, False):
            with self.subTest(category_column=category), self.receiver(category):
                before = self.full_state()
                with patch.object(self.app.storage, 'write', side_effect=OSError('Simulated full disk')), self.assertRaises(OSError):
                    self.app.restore_backup(data)
                self.assertEqual(self.full_state(), before)
                self.assertEqual(data, original)
                self.assertEqual(list(self.app.UPLOADS.iterdir()), [])
                saved = list((self.app.DATA_DIR/'restore-safety').glob('*/analytics.db'))
                self.assertEqual(len(saved), 1)
                with closing(sqlite3.connect(saved[0])) as db:
                    self.assertEqual(conservation_state(db, include_category=True), before)
                self.assert_integrity()

    def test_http_export_preview_restore_and_rejection_keep_existing_contracts(self):
        server = self.app.serve(0, True, '127.0.0.1')
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        origin = 'http://127.0.0.1:'+str(server.server_port)
        def request(path, data=None):
            body = json.dumps(data).encode() if data is not None else None
            try:
                response = urlopen(Request(origin+path, body, {'Content-Type':'application/json', 'X-Links-Request':'1'}), timeout=5)
            except HTTPError as error:
                response = error
            with response:
                return response.code, json.loads(response.read())
        try:
            before = self.full_state()
            status, exported = request('/api/backup')
            self.assertEqual(status, 200)
            self.assertEqual(exported['version'], 3)
            self.assertTrue(all('category' not in row for row in exported['tables']['tracked_links']))
            legacy = self.payload(legacy=True)
            self.assertEqual(request('/api/restore/preview', legacy)[0], 200)
            self.assertEqual(self.full_state(), before)
            self.assertEqual(request('/api/restore', legacy)[0], 200)
            self.assertEqual(self.full_state(), before)
            invalid = copy.deepcopy(exported)
            invalid['tables']['tracked_links'][0].pop('notes')
            self.assertEqual(request('/api/restore', invalid)[0], 400)
            self.assertEqual(self.full_state(), before)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__':
    unittest.main()
