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
    redirect = analytics_test.AnalyticsTests.redirect

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
            db.execute('INSERT INTO tracked_link_partners(link_id,partner_id) VALUES(?,?)', (link['id'], ident))
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
            db.execute('INSERT INTO tracked_link_partners(link_id,partner_id) VALUES(?,?)', (link['id'], partner['id']))
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

    def test_sanyipace_upgrade_preserves_custom_fields_and_is_once_only(self):
        with self.a.connection() as db:
            row = next(row for row in partners.rows(db) if row['name'] == 'Sanyipace')
            db.execute('UPDATE affiliate_partners SET name=?,code=?,template=?,domains=? WHERE id=?',
                       ('Mon Sanyipace', 'PERSO', '{url}#{code}', json.dumps(['sanyipace.com', 'sanyipace.eu', 'personnel.example']), row['id']))
            db.execute('DELETE FROM settings WHERE key=?', (partners.SANYIPACE_MIGRATION,))
            partners.initialize(db)
            upgraded = next(value for value in partners.rows(db) if value['id'] == row['id'])
            self.assertEqual(upgraded['domains'], ['sanyipacetoilet.com', 'personnel.example'])
            self.assertEqual((upgraded['name'], upgraded['code'], upgraded['template']), ('Mon Sanyipace', 'PERSO', '{url}#{code}'))
            db.execute('UPDATE affiliate_partners SET domains=? WHERE id=?', (json.dumps(['sanyipace.eu', 'extra.example']), row['id']))
            db.execute('DELETE FROM settings WHERE key=?', (partners.SANYIPACE_MIGRATION,))
            partners.initialize(db)
            self.assertEqual(next(value['domains'] for value in partners.rows(db) if value['id'] == row['id']), ['sanyipacetoilet.com', 'extra.example'])
            db.execute('UPDATE affiliate_partners SET domains=? WHERE id=?', (json.dumps(['custom.example']), row['id']))
            db.execute('DELETE FROM settings WHERE key=?', (partners.SANYIPACE_MIGRATION,))
            partners.initialize(db)
            self.assertEqual(next(value['domains'] for value in partners.rows(db) if value['id'] == row['id']), ['custom.example'])
            db.execute('UPDATE affiliate_partners SET domains=? WHERE id=?', (json.dumps(['sanyipace.com', 'sanyipace.eu']), row['id']))
            partners.initialize(db)
            self.assertEqual(next(value['domains'] for value in partners.rows(db) if value['id'] == row['id']), ['sanyipace.com', 'sanyipace.eu'])

    def test_detection_uses_domain_boundaries_and_longest_match(self):
        with self.a.connection() as db:
            reolink = next(row for row in partners.rows(db) if row['name'] == 'Reolink')
            self.assertEqual(partners.detect(db, 'https://SHOP.Reolink.com/product'), reolink['id'])
            for domain in ['notreolink.com', 'reolink.com.other.example', 'amazon.example']:
                self.assertEqual(partners.detect(db, 'https://'+domain+'/p'), '')
            specific = partners.save(db, self.fields(domains=['shop.reolink.com']), self.a.now_iso())
            self.assertEqual(partners.detect(db, 'https://eu.shop.reolink.com/p'), specific['id'])

    def test_generated_destination_snapshots_confirmation_and_preview_races(self):
        admin = self.server(True)
        reolink = next(row for row in json.loads(self.request(admin+'/api/affiliate-partners')[1])['items'] if row['name'] == 'Reolink')
        fields = {'name': 'Caméra', 'url': 'https://shop.reolink.com/camera', 'partner_id': reolink['id'], 'apply_partner': True}
        expected = fields['url']+'?aff=1404'
        status, body = self.request(admin+'/api/tracked-links', {**fields, 'expected_url': expected})
        self.assertEqual(status, 201, body)
        ident = json.loads(body)['id']
        endpoint = admin+'/api/tracked-links/'+ident
        with self.a.connection() as db:
            source = self.a.tracked_links.source_rows(db)[0]
            token = self.a.tracked_links.token_link(db, ident, source['id'], 'https://links.example', self.a.now_iso())
            db.execute('UPDATE tracked_tokens SET click_total=7 WHERE link_id=?', (ident,))
            partners.save(db, {**reolink, 'code': 'NEW'}, self.a.now_iso(), reolink['id'])
        unchanged = {**fields, 'name': 'Caméra renommée', 'apply_partner': False, 'expected_url': expected, 'previous_url': expected}
        self.assertEqual(self.request(endpoint, unchanged, method='PUT')[0], 200)
        current = next(row for row in json.loads(self.request(admin+'/api/tracked-links')[1])['items'] if row['id'] == ident)
        self.assertEqual((current['url'], current['original_url'], current['clicks']), (expected, fields['url'], 7))
        changed = {**fields, 'expected_url': fields['url']+'?aff=NEW', 'previous_url': expected}
        self.assertEqual(self.request(endpoint, changed, method='PUT')[0], 400, 'A generated replacement requires confirmation')
        self.assertEqual(self.request(endpoint, {**changed, 'confirm_destination': True}, method='PUT')[0], 200)
        with self.a.connection() as db:
            self.assertEqual(self.a.tracked_links.token_link(db, ident, source['id'], 'https://links.example', self.a.now_iso())['url'], token['url'])
            self.assertEqual(db.execute('SELECT click_total FROM tracked_tokens WHERE link_id=?', (ident,)).fetchone()[0], 7)
            partners.save(db, {**reolink, 'code': 'LATEST'}, self.a.now_iso(), reolink['id'])
        stale = {**changed, 'previous_url': changed['expected_url'], 'confirm_destination': True}
        self.assertEqual(self.request(endpoint, stale, method='PUT')[0], 400, 'A code changed since preview must not be silently applied')
        direct = {**fields, 'partner_id': '', 'expected_url': fields['url'], 'previous_url': changed['expected_url'], 'confirm_destination': True}
        self.assertEqual(self.request(endpoint, direct, method='PUT')[0], 200)
        with self.a.connection() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM tracked_link_partners WHERE link_id=?', (ident,)).fetchone())

    def test_old_partner_backup_schema_and_original_url_survive_restore(self):
        with self.a.connection() as db:
            partner = partners.rows(db)[0]
            fields = {'name': 'Origine', 'url': 'https://product.example/raw', 'partner_id': partner['id'], 'apply_partner': True}
            preview = partners.preview_tracked(db, fields)
            saved = partners.save_tracked(db, {**fields, 'expected_url': preview['url']}, self.a.story_url_valid, self.a.now_iso())
        snapshot = json.loads(self.a.export_backup())
        old = copy.deepcopy(snapshot)
        for row in old['tables']['tracked_link_partners']: row.pop('original_url')
        self.a.restore_backup(old)
        with self.a.connection() as db:
            self.assertEqual(partners.link_metadata(db, saved['id'], saved['url'])['original_url'], fields['url'])


    def test_partner_statistics_chain_uses_explicit_ids_and_preserves_short_links(self):
        admin, public = self.server(True), self.server()
        configured = {row['name']: row for row in json.loads(self.request(admin+'/api/affiliate-partners')[1])['items']}
        source = json.loads(self.request(admin+'/api/tracking-sources')[1])['items'][0]['id']
        day = self.a.datetime.now(self.a.PARIS).date().isoformat()
        cases = [('Domadoo', 'https://www.domadoo.fr/p', '?domid=117'),
                 ('Reolink', 'https://reolink.com/p', '?aff=1404'),
                 ('Sanyipace', 'https://sanyipacetoilet.com/p', '?ref=DomotiK')]
        for name, origin, suffix in cases:
            partner = configured[name]
            status, body = self.request(admin+'/api/tracked-links', {'name':name+' associé', 'url':origin,
                'partner_id':partner['id'], 'expected_url':origin+suffix})
            self.assertEqual(status, 201, body)
            ident = json.loads(body)['id']
            status, body = self.request(admin+'/api/tracked-links/'+ident+'/token', {'source_id':source})
            self.assertEqual(status, 200, body)
            short = json.loads(body)
            for path, method in [('/'+short['code'], 'GET'), ('/go/'+short['token'], 'HEAD'), ('/go/'+short['token'], 'GET')]:
                status, headers = self.redirect(public+path, method=method)
                self.assertEqual((status, headers['Location']), (302, origin+suffix))
            if name == 'Domadoo': self.assertEqual(self.request(admin+'/api/tracked-links/'+ident+'/archive', {})[0], 200)
            with self.a.connection() as db:
                db.execute('UPDATE tracked_tokens SET click_total=999 WHERE token=?', (short['token'],))
                db.execute('INSERT INTO counts VALUES(?,?,?,?,?)', ('2020-01-01','tracked:'+source,'tracked','tracked:'+short['token']+':10',7))
            link = next(row for row in json.loads(self.request(admin+'/api/tracked-links')[1])['items'] if row['id']==ident)
            self.assertEqual((link['partner_id'], link['clicks']), (partner['id'], 999))
            report = json.loads(self.request(admin+'/api/stats?start='+day+'&end='+day)[1])
            self.assertEqual(sum(row['total'] for row in report['tracked'] if row['link_id']==ident), 2)
            self.assertEqual(self.request(admin+'/api/tracked-links/'+ident+'/token', {'source_id':source})[0], 400 if name=='Domadoo' else 200)
            with self.a.connection() as db:
                alias = db.execute('SELECT code FROM short_aliases WHERE target_token=?', (short['token'],)).fetchone()
                self.assertEqual(alias['code'], short['code'])
        for index, label in enumerate(['API historique', 'Choix sans partenaire']):
            destination = 'https://reolink.com/direct-'+str(index)+'?aff=custom'
            fields = {} if index==0 else {'partner_id':'', 'expected_url':destination}
            status, body = self.request(admin+'/api/tracked-links', {'name':label,'url':destination, **fields})
            self.assertEqual(status, 201, body)
            ident=json.loads(body)['id']
            link=next(row for row in json.loads(self.request(admin+'/api/tracked-links')[1])['items'] if row['id']==ident)
            self.assertEqual((link['partner_id'],link['url']), ('',destination))


if __name__ == '__main__': unittest.main()
