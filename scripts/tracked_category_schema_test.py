"""Physical category removal and recovery, exclusively on disposable databases."""
import importlib.util
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import tracked_links
from tracked_categories_migration_test import FIXTURE, AFFILIATE, conservation_state


class CategorySchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='links-schema-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = self.root / 'analytics.db'
        self.load()

    def load(self):
        with closing(sqlite3.connect(self.database)) as db:
            db.executescript(FIXTURE.read_text(encoding='utf-8'))

    def dump(self, path=None):
        with closing(sqlite3.connect(path or self.database)) as db:
            return '\n'.join(db.iterdump())

    def copies(self):
        return sorted(self.root.glob('pre-category-removal/*/analytics.db'))

    def assert_unchanged(self, before):
        self.assertEqual(self.dump(), before)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertIn('category', {row[1] for row in db.execute('PRAGMA table_info(tracked_links)')})

    def test_native_drop_preserves_all_business_data_constraints_indexes_and_other_categories(self):
        media = self.root / 'uploads' / 'media.webp'
        media.parent.mkdir()
        media.write_bytes(b'Unchanged media bytes')
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE INDEX tracked_name_lookup ON tracked_links(name)')
            db.execute('CREATE TABLE unrelated(category, payload BLOB)')
            db.executemany('INSERT INTO unrelated VALUES(?,?)', [('same', b'\x00\xff')]*2 + [('été', None)])
            db.execute('UPDATE tracked_links SET notes=? WHERE id=?', ('Texte category à conserver', AFFILIATE))
            before = conservation_state(db)
            foreign_keys = list(db.execute('PRAGMA foreign_key_list(tracked_link_partners)'))
            identities = list(db.execute('SELECT rowid,id FROM tracked_links ORDER BY rowid'))
        original = self.dump()
        target = tracked_links.remove_legacy_category(self.database)
        self.assertEqual(self.copies(), [target])
        self.assertEqual(self.dump(target), original, 'The full original schema, including categories, remains restorable')
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(conservation_state(db), before)
            self.assertNotIn('category', {row[1] for row in db.execute('PRAGMA table_info(tracked_links)')})
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(list(db.execute('PRAGMA foreign_key_check')), [])
            self.assertEqual(list(db.execute('PRAGMA foreign_key_list(tracked_link_partners)')), foreign_keys)
            self.assertEqual(list(db.execute('SELECT rowid,id FROM tracked_links ORDER BY rowid')), identities)
            self.assertEqual(list(db.execute('SELECT * FROM unrelated')), [('same', b'\x00\xff')]*2 + [('été', None)])
            self.assertTrue(db.execute("SELECT 1 FROM sqlite_master WHERE name='tracked_name_lookup'").fetchone())
            db.execute('PRAGMA foreign_keys=ON')
            for sql in ["UPDATE tracked_links SET name=NULL WHERE id='"+AFFILIATE+"'",
                        "UPDATE tracked_links SET archived=2 WHERE id='"+AFFILIATE+"'",
                        "DELETE FROM tracked_links WHERE id='"+AFFILIATE+"'"]:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)
                db.rollback()
        self.assertEqual(media.read_bytes(), b'Unchanged media bytes')

    def test_backup_includes_committed_wal_pages_without_a_file_copy(self):
        with closing(sqlite3.connect(self.database)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('PRAGMA wal_autocheckpoint=0')
            writer.execute('UPDATE tracked_tokens SET click_total=click_total+123')
            writer.execute('UPDATE tracked_links SET notes=? WHERE id=?', ('Dernière écriture dans WAL', AFFILIATE))
            writer.commit()
            self.assertGreater(Path(str(self.database)+'-wal').stat().st_size, 0)
            before = self.dump()
            target = tracked_links.remove_legacy_category(self.database)
            self.assertEqual(self.dump(target), before)
            with closing(sqlite3.connect(self.database)) as current, closing(sqlite3.connect(target)) as saved:
                self.assertEqual(conservation_state(current), conservation_state(saved))

    def test_repeated_migration_does_not_write_or_create_another_backup(self):
        target = tracked_links.remove_legacy_category(self.database)
        contents = self.database.read_bytes()
        backup = target.read_bytes()
        for _ in range(3):
            self.assertIsNone(tracked_links.remove_legacy_category(self.database))
            self.assertEqual(self.database.read_bytes(), contents)
            self.assertEqual(target.read_bytes(), backup)
            self.assertEqual(self.copies(), [target])

    def test_original_backup_can_be_restored_and_migrated_again(self):
        before = self.dump()
        target = tracked_links.remove_legacy_category(self.database)
        restored = self.root / 'restored.db'
        with closing(sqlite3.connect(target)) as source, closing(sqlite3.connect(restored)) as receiver:
            source.backup(receiver)
        self.assertEqual(self.dump(restored), before)
        tracked_links.remove_legacy_category(restored)
        with closing(sqlite3.connect(self.database)) as current, closing(sqlite3.connect(restored)) as receiver:
            self.assertEqual(conservation_state(current), conservation_state(receiver))

    def test_missing_database_and_new_install_never_create_the_retired_column_or_a_backup(self):
        fresh = self.root / 'fresh.db'
        self.assertIsNone(tracked_links.remove_legacy_category(fresh))
        self.assertFalse(fresh.exists())
        with patch.dict(os.environ, {'ANALYTICS_DB': str(fresh), 'UPLOAD_DIR': str(self.root/'uploads')}):
            spec = importlib.util.spec_from_file_location('fresh_category_schema_api', Path(__file__).with_name('analytics.py'))
            app = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(app)
            with patch('builtins.print'):
                app.init()
                app.init()
            with app.connection() as db:
                self.assertNotIn('category', {row['name'] for row in db.execute('PRAGMA table_info(tracked_links)')})
                self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0], 1)
        self.assertEqual(self.copies(), [])

    def test_empty_link_table_also_migrates(self):
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('DELETE FROM tracked_link_partners')
            db.execute('DELETE FROM tracked_tokens')
            db.execute('DELETE FROM tracked_links')
            before = conservation_state(db)
        tracked_links.remove_legacy_category(self.database)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(conservation_state(db), before)
            self.assertNotIn('category', {row[1] for row in db.execute('PRAGMA table_info(tracked_links)')})

    def test_unsupported_sqlite_fails_before_backup_or_schema_changes(self):
        before = self.dump()
        with patch.object(sqlite3, 'sqlite_version_info', (3, 34, 0)):
            with self.assertRaisesRegex(RuntimeError, 'minimum requis'):
                tracked_links.remove_legacy_category(self.database)
        self.assert_unchanged(before)
        self.assertEqual(self.copies(), [])

    def test_bad_references_blank_names_and_unknown_column_shapes_fail_closed(self):
        changes = ["UPDATE tracked_tokens SET link_id='missing' WHERE token=(SELECT token FROM tracked_tokens LIMIT 1)",
                   "UPDATE tracked_links SET name='   '",
                   'ALTER TABLE tracked_links DROP COLUMN category; ALTER TABLE tracked_links ADD COLUMN category INTEGER NOT NULL DEFAULT 0']
        for index, sql in enumerate(changes):
            with self.subTest(sql=sql):
                self.database = self.root / ('invalid-'+str(index)+'.db')
                self.load()
                with closing(sqlite3.connect(self.database)) as db:
                    db.executescript(sql)
                before = self.dump()
                with self.assertRaises(RuntimeError):
                    tracked_links.remove_legacy_category(self.database)
                self.assert_unchanged(before)
                self.assertEqual(self.copies(), [])

    def test_unexpected_category_indexes_views_and_triggers_are_not_silently_removed(self):
        definitions = ['CREATE INDEX custom_category ON tracked_links(category)',
                       'CREATE VIEW custom_view AS SELECT category FROM tracked_links',
                       'CREATE VIEW custom_star AS SELECT * FROM tracked_links',
                       'CREATE TRIGGER custom_trigger AFTER UPDATE ON tracked_links BEGIN SELECT new.category; END']
        for index, sql in enumerate(definitions):
            with self.subTest(sql=sql):
                self.database = self.root / ('dependency-'+str(index)+'.db')
                self.load()
                with closing(sqlite3.connect(self.database)) as db:
                    db.execute(sql)
                before = self.dump()
                with self.assertRaisesRegex(RuntimeError, 'Dépendance SQLite'):
                    tracked_links.remove_legacy_category(self.database)
                self.assert_unchanged(before)
                self.assertEqual(self.copies(), [])

    def test_backup_directory_failure_prevents_any_drop(self):
        before = self.dump()
        with patch.object(Path, 'mkdir', side_effect=PermissionError('Backup directory unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'Backup directory unavailable'):
                tracked_links.remove_legacy_category(self.database)
        self.assert_unchanged(before)
        self.assertEqual(self.copies(), [])

    def test_failed_or_incorrect_backups_are_never_marked_valid_and_never_allow_drop(self):
        connect = sqlite3.connect
        for incorrect in (False, True):
            class BackupFailure(sqlite3.Connection):
                def backup(source, target, **kwargs):
                    if not incorrect:
                        raise OSError('Backup interrupted')
                    super().backup(target, **kwargs)
                    target.execute("UPDATE tracked_links SET notes='Incomplete backup'")
                    target.commit()
            before = self.dump()
            with self.subTest(incorrect=incorrect), patch.object(sqlite3, 'connect', side_effect=lambda *args, **kwargs: connect(*args, **kwargs, factory=BackupFailure)):
                with self.assertRaises(RuntimeError):
                    tracked_links.remove_legacy_category(self.database)
            self.assert_unchanged(before)
            self.assertEqual(self.copies(), [])

    def test_failure_after_drop_rolls_back_and_keeps_a_verified_backup_for_retry(self):
        compare = tracked_links._category_compare
        def fail_after_drop(db, saved, removed=False):
            if removed:
                self.assertNotIn('category', {row[1] for row in db.execute('PRAGMA table_info(tracked_links)')})
                raise ValueError('Post-drop verification interrupted')
            return compare(db, saved, removed)
        before = self.dump()
        with patch.object(tracked_links, '_category_compare', side_effect=fail_after_drop):
            with self.assertRaisesRegex(RuntimeError, 'Post-drop verification interrupted'):
                tracked_links.remove_legacy_category(self.database)
        self.assert_unchanged(before)
        first = self.copies()[0]
        self.assertEqual(self.dump(first), before)
        tracked_links.remove_legacy_category(self.database)
        self.assertEqual(len(self.copies()), 2)
        self.assertEqual(self.dump(first), before, 'Retry never overwrites the first verified backup')

    def test_real_comparison_detects_changes_to_values_rows_and_other_table_schemas(self):
        compare = tracked_links._category_compare
        changes = ["UPDATE tracked_links SET url='https://example.org/changed'",
                   'UPDATE tracked_tokens SET click_total=click_total+1',
                   'DELETE FROM counts', 'ALTER TABLE counts ADD COLUMN unexpected TEXT']
        for sql in changes:
            def tamper(db, saved, removed=False):
                if removed:
                    db.execute(sql)
                return compare(db, saved, removed)
            before = self.dump()
            with self.subTest(sql=sql), patch.object(tracked_links, '_category_compare', side_effect=tamper):
                with self.assertRaises(RuntimeError):
                    tracked_links.remove_legacy_category(self.database)
            self.assert_unchanged(before)

    def test_commit_failure_rolls_back_the_drop(self):
        connect = sqlite3.connect
        class CommitFailure(sqlite3.Connection):
            def commit(db):
                if db.isolation_level is None:
                    raise sqlite3.OperationalError('Commit failed')
                return super().commit()
        before = self.dump()
        with patch.object(sqlite3, 'connect', side_effect=lambda *args, **kwargs: connect(*args, **kwargs, factory=CommitFailure)):
            with self.assertRaisesRegex(RuntimeError, 'Commit failed'):
                tracked_links.remove_legacy_category(self.database)
        self.assert_unchanged(before)
        self.assertEqual(self.dump(self.copies()[0]), before)

    def test_failed_migration_stops_startup_before_other_initializers(self):
        before = self.dump()
        with patch.dict(os.environ, {'ANALYTICS_DB': str(self.database), 'UPLOAD_DIR': str(self.root/'uploads')}):
            spec = importlib.util.spec_from_file_location('failed_category_startup_api', Path(__file__).with_name('analytics.py'))
            app = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(app)
            with patch.object(tracked_links, '_category_compare', side_effect=ValueError('Safety check failed')), \
                 patch.object(tracked_links, 'initialize') as initialize:
                with self.assertRaisesRegex(RuntimeError, 'Safety check failed'):
                    app.init()
                initialize.assert_not_called()
        self.assert_unchanged(before)

    def test_external_writers_cannot_change_the_snapshot_during_backup(self):
        connect = sqlite3.connect
        probe = []
        database = self.database
        class ProbeBackup(sqlite3.Connection):
            def backup(source, target, **kwargs):
                with closing(connect(database, timeout=0.01)) as writer:
                    try:
                        writer.execute('UPDATE tracked_tokens SET click_total=0')
                    except sqlite3.OperationalError as error:
                        probe.append(str(error))
                    else:
                        self.fail('A concurrent write must remain blocked')
                return super().backup(target, **kwargs)
        before = self.dump()
        with patch.object(sqlite3, 'connect', side_effect=lambda *args, **kwargs: connect(*args, **kwargs, factory=ProbeBackup)):
            target = tracked_links.remove_legacy_category(self.database)
        self.assertEqual(len(probe), 1)
        self.assertIn('locked', probe[0])
        self.assertEqual(self.dump(target), before)

    def test_abrupt_process_exit_after_drop_recovers_the_original_database(self):
        code = '''import os,sys
sys.path.insert(0,sys.argv[1])
import tracked_links
compare=tracked_links._category_compare
def interrupt(db,saved,removed=False):
    if removed: os._exit(23)
    return compare(db,saved,removed)
tracked_links._category_compare=interrupt
tracked_links.remove_legacy_category(sys.argv[2])
'''
        for mode in ('DELETE', 'WAL'):
            with self.subTest(journal_mode=mode):
                self.database = self.root / (mode+'.db')
                self.load()
                with closing(sqlite3.connect(self.database)) as db:
                    self.assertEqual(db.execute('PRAGMA journal_mode='+mode).fetchone()[0].upper(), mode)
                before = self.dump()
                result = subprocess.run([sys.executable, '-B', '-c', code, str(Path(__file__).parent), str(self.database)], capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 23, result.stderr)
                self.assert_unchanged(before)
                tracked_links.remove_legacy_category(self.database)
                with closing(sqlite3.connect(self.database)) as db:
                    self.assertNotIn('category', {row[1] for row in db.execute('PRAGMA table_info(tracked_links)')})


if __name__ == '__main__':
    unittest.main()
