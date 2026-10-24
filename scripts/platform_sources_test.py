"""Preferred platform identities with non-destructive history and PulSe aliases."""
import copy
import json
import unittest
from datetime import datetime
import analytics_test
import tracked_links


class PlatformTests(unittest.TestCase):
    setUp = analytics_test.AnalyticsTests.setUp
    tearDown = analytics_test.AnalyticsTests.tearDown
    promo = analytics_test.AnalyticsTests.promo

    def test_migration_preserves_ids_tokens_counters_and_renamed_platforms(self):
        with self.a.connection() as db:
            old = db.execute("SELECT id FROM tracking_sources WHERE name='Instagram Story'").fetchone()['id']
            link = tracked_links.create_link(db, {'name': 'Historique', 'url': 'https://shop.example/old'}, self.a.story_url_valid, self.a.now_iso())
            token = tracked_links.token_link(db, link['id'], old, self.a.ORIGIN, self.a.now_iso())
            db.execute('UPDATE tracked_tokens SET click_total=9 WHERE token=?', (token['token'],))
            day = datetime.now(self.a.PARIS).date().isoformat()
            db.execute('INSERT INTO counts VALUES(?,?,?,?,?)', (day, 'tracked:'+old, 'tracked', 'tracked:'+token['token']+':10', 9))
            # A copied pre-upgrade instance has the original eight source identities.
            db.execute("DELETE FROM tracking_source_keys WHERE key LIKE 'platform:%'")
            db.execute("DELETE FROM tracking_sources WHERE name IN ('Instagram','YouTube')")
            before = {row['id']: dict(row) for row in db.execute('SELECT * FROM tracking_sources')}
            tracked_links.initialize(db)
            for ident, row in before.items(): self.assertEqual(dict(db.execute('SELECT * FROM tracking_sources WHERE id=?', (ident,)).fetchone()), row)
            canonical = tracked_links.platform_source_ids(db, 'instagram')[0]
            self.assertNotEqual(canonical, old)
            self.assertEqual(db.execute("SELECT source_id FROM tracking_source_keys WHERE key='instagram'").fetchone()[0], old)
            tracked_links.edit_source(db, canonical, {'name': 'Mon Instagram'})
            tracked_links.edit_source(db, old, {'name': 'Mes anciennes Stories'})
            tracked_links.initialize(db)
            self.assertEqual(tracked_links.source_rows(db)[0]['id'], canonical)
            self.assertEqual(tracked_links.source_rows(db)[0]['name'], 'Mon Instagram')
            self.assertTrue(next(row['historical'] for row in tracked_links.source_rows(db) if row['id'] == old))
        self.assertEqual(self.a.pulse_story_link({'type': 'independent', 'id': link['id']})['url'], token['url'])
        self.assertEqual(self.a.pulse_stats()['stories'], 9)
        with self.a.connection() as db:
            new = tracked_links.create_link(db, {'name': 'Nouveau', 'url': 'https://shop.example/new'}, self.a.story_url_valid, self.a.now_iso())
        published = self.a.pulse_story_link({'type': 'independent', 'id': new['id']})
        with self.a.connection() as db:
            self.assertEqual(db.execute('SELECT source_id FROM tracked_tokens WHERE token=?', (published['token'],)).fetchone()[0], canonical)
            self.assertEqual(tracked_links.remove_source(db, canonical)['action'], 'archived')
            tracked_links.initialize(db)
            self.assertEqual(db.execute('SELECT active FROM tracking_sources WHERE id=?', (canonical,)).fetchone()[0], 0)
        self.assertEqual(self.a.pulse_story_link({'type': 'independent', 'id': link['id']})['url'], token['url'])
        with self.a.connection() as db:
            third = tracked_links.create_link(db, {'name': 'Après archivage', 'url': 'https://shop.example/third'}, self.a.story_url_valid, self.a.now_iso())
        with self.assertRaises(ValueError): self.a.pulse_story_link({'type': 'independent', 'id': third['id']})

    def test_pulse_campaign_keeps_legacy_alias_and_new_campaign_uses_platform(self):
        legacy = self.promo('Ancienne campagne')
        alias = self.a.story_link(legacy, 'instagram')
        self.assertEqual(self.a.pulse_story_link({'type': 'campaign', 'id': legacy})['url'], alias['url'])
        fresh = self.promo('Nouvelle campagne', 'https://shop.example/new-campaign')
        result = self.a.pulse_story_link({'type': 'campaign', 'id': fresh})
        with self.a.connection() as db:
            canonical = tracked_links.platform_source_ids(db, 'instagram')[0]
            self.assertEqual(db.execute('SELECT source FROM short_aliases WHERE code=?', (result['code'],)).fetchone()[0], 'tracked:'+canonical)
            tracked_links.edit_source(db, canonical, {'name': 'Instagram renommé'})
        self.assertEqual(self.a.pulse_story_link({'type': 'campaign', 'id': fresh})['url'], result['url'])

    def test_platform_bindings_survive_backup_restore_and_old_backup_keys(self):
        with self.a.connection() as db:
            ids = tracked_links.platform_source_ids(db, 'instagram')
            tracked_links.edit_source(db, ids[0], {'name': 'Compte Instagram'})
        snapshot = json.loads(self.a.export_backup())
        old = copy.deepcopy(snapshot)
        old['tables']['tracking_source_keys'] = [row for row in old['tables']['tracking_source_keys'] if not row['key'].startswith('platform:')]
        self.a.restore_backup(old)
        self.a.restore_backup(snapshot)
        with self.a.connection() as db:
            self.assertEqual(tracked_links.platform_source_ids(db, 'instagram'), ids)
            self.assertEqual(tracked_links.source_rows(db)[0]['name'], 'Compte Instagram')
            self.assertEqual(len([row for row in tracked_links.source_rows(db) if row['platform']]), len(tracked_links.PLATFORMS))


if __name__ == '__main__': unittest.main()
