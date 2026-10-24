"""Affiliate configuration contracts on disposable instance databases."""
import copy
import json
import sqlite3
import unittest
import affiliate_partners as partners
import analytics_test


class PartnerTests(unittest.TestCase):
    setUp = analytics_test.AnalyticsTests.setUp
    tearDown = analytics_test.AnalyticsTests.tearDown
    server = analytics_test.AnalyticsTests.server
    request = analytics_test.AnalyticsTests.request

    def fields(self, **values):
        return {'name': 'Test partenaire', 'code': 'ABC', 'domains': ['shop.example'],
                'template': '{url}?ref={code}', **values}

    def test_defaults_are_once_only_and_preserve_edits_and_deletions(self):
        with self.a.connection() as db:
            initial = partners.rows(db)
            self.assertEqual({row['name']: row['code'] for row in initial}, {'Domadoo': '117', 'Reolink': '1404', 'Sanyipace': 'DomotiK'})
            domadoo = next(row for row in initial if row['name'] == 'Domadoo')
            partners.save(db, self.fields(name='Domadoo', code='CUSTOM'), self.a.now_iso(), domadoo['id'])
            partners.remove(db, next(row['id'] for row in initial if row['name'] == 'Reolink'))
            partners.initialize(db)
            self.assertEqual(len(partners.rows(db)), 2)
            self.assertEqual(next(row['code'] for row in partners.rows(db) if row['name'] == 'Domadoo'), 'CUSTOM')

    def test_literal_formats_and_rejection_of_unsafe_previews(self):
        for template, expected in [('{url}?x={code}', 'https://shop.example/p?x=ABC'),
                                   ('https://redirect.example/{code}?target={url}', 'https://redirect.example/ABC?target=https://shop.example/p'),
                                   ('{url}#{code}', 'https://shop.example/p#ABC'),
                                   ('https://shop.example/ref/{code}', 'https://shop.example/ref/ABC')]:
            fields = partners.partner_input(self.fields(template=template))
            self.assertEqual(partners.build_url(fields['template'], fields['code'], 'https://shop.example/p'), expected)
        self.assertEqual(partners.build_url('{url}#{code}', 'ABC', 'https://shop.example/{code}'), 'https://shop.example/{code}#ABC')
        self.assertEqual(partners.normalize_domains('SHOP.example\nshop.example;autre.example'), ['shop.example', 'autre.example'])
        for template in ['javascript:alert(1)', 'https://shop.example/{unknown}']:
            with self.assertRaises(ValueError): partners.partner_input(self.fields(template=template))
        with self.assertRaises(ValueError): partners.partner_input(self.fields(domains=['https://shop.example/path']))

    def test_http_crud_preview_and_protected_association(self):
        admin = self.server(True)
        status, body = self.request(admin+'/api/affiliate-partners', self.fields())
        self.assertEqual(status, 201, body)
        ident = json.loads(body)['id']
        endpoint = admin+'/api/affiliate-partners/'+ident
        status, body = self.request(endpoint, self.fields(template='https://shop.example/{code}'), method='PUT')
        self.assertEqual(status, 200, body)
        status, body = self.request(admin+'/api/affiliate-partners/preview', self.fields(template='https://shop.example/{code}', test_url='https://product.example/p'))
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)['url'], 'https://shop.example/ABC')
        with self.a.connection() as db:
            link = self.a.tracked_links.create_link(db, {'name': 'Existant', 'url': 'https://shop.example/direct?original=1'}, self.a.story_url_valid, self.a.now_iso())
            before = self.a.tracked_links.list_links(db)
            db.execute('INSERT INTO tracked_link_partners VALUES(?,?)', (link['id'], ident))
        self.assertEqual(self.request(endpoint, method='DELETE')[0], 409)
        with self.a.connection() as db:
            with self.assertRaises(sqlite3.IntegrityError): db.execute('DELETE FROM affiliate_partners WHERE id=?', (ident,))
            self.assertEqual(self.a.tracked_links.list_links(db), before)
            db.execute('DELETE FROM tracked_link_partners WHERE link_id=?', (link['id'],))
        self.assertEqual(self.request(endpoint, method='DELETE')[0], 200)

    def test_backup_roundtrip_and_old_backups_preserve_configuration(self):
        with self.a.connection() as db:
            partner = partners.save(db, self.fields(), self.a.now_iso())
            link = self.a.tracked_links.create_link(db, {'name': 'Historique', 'url': 'https://shop.example/direct'}, self.a.story_url_valid, self.a.now_iso())
            db.execute('INSERT INTO tracked_link_partners VALUES(?,?)', (link['id'], partner['id']))
        backup = json.loads(self.a.export_backup())
        self.a.restore_backup(copy.deepcopy(backup))
        old = copy.deepcopy(backup)
        for table in self.a.PARTNER_BACKUP_TABLES: old['tables'].pop(table)
        self.a.restore_backup(old)
        with self.a.connection() as db:
            self.assertEqual(next(row['code'] for row in partners.rows(db) if row['id'] == partner['id']), 'ABC')
            self.assertEqual(db.execute('SELECT partner_id FROM tracked_link_partners WHERE link_id=?', (link['id'],)).fetchone()[0], partner['id'])
        self.a.init()
        with self.a.connection() as db:
            self.assertTrue(any(row['id'] == partner['id'] for row in partners.rows(db)))


if __name__ == '__main__': unittest.main()
