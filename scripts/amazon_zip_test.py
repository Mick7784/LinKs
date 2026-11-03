"""Synthetic exports only: no merchant identities or real report contents."""
import sqlite3
import unittest

import affiliation as aff
import amazon_affiliation as amazon
from amazon_report_views_test import archive
from amazon_affiliation_test import payload
import affiliation_overview_test as overview_tests


def category(amount='51,87', start='2026-10-30', end='2026-10-31', scope='all'):
    return f'Période: {start} → {end}\nScope: {scope}\nCurrency: EUR\nCatégorie;Clics;Articles commandés;Articles expédiés;Revenus totaux\nMaison;20;4;3;{amount}\n'


def daily():
    return 'Scope: all\nCurrency: EUR\nDate;Clics;Articles commandés;Articles expédiés;Revenus totaux\n10-30-2026;8;1;1;20.00\n10-31-2026;12;3;2;31.869999999999997\n'


class ZipTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row;aff.initialize(self.db)
        self.id=aff.add_account(self.db,{'partner':'Amazon','label':'Synthetic FR','platform':'amazon'})['id']

    def tearDown(self):self.db.close()

    def ingest(self, files, **kwargs):
        return amazon.ingest_archive(self.db,self.id,{**archive(files),**kwargs},'2026-11-02T12:00:00Z')

    def report(self,*args):return amazon.report(self.db,self.id,*args)

    def count(self):return self.db.execute('SELECT count(*) FROM aff_snapshots').fetchone()[0]

    def test_multiple_views_one_reference_per_metric_and_reliable_daily(self):
        result=self.ingest([('Category.csv',category()),('Daily-Trends.txt',daily()),('Linked-Product.csv',category().replace('Catégorie','Titre du produit')),('Tracking-Id.csv',category().replace('Catégorie','Tracking ID').replace('Maison','synthetic-21'))])
        self.assertTrue(result['imported']);self.assertEqual(len(result['files']),4)
        r=self.report();self.assertEqual(r['totals']['commission_cents'],5187)
        self.assertEqual(r['totals']['clicks'],20)
        self.assertEqual([d['commission_cents'] for d in r['daily']],[2000,3187])
        self.assertIsNone(r['undated_totals']['commission_cents'])
        self.assertEqual(len(r['tracking']),1)

    def test_period_totals_are_not_dated_or_prorated(self):
        self.ingest([('Category.csv',category())]);r=self.report()
        self.assertEqual(r['totals']['commission_cents'],5187);self.assertEqual(r['daily'],[])
        self.assertIsNone(r['rows'][0]['date']);self.assertEqual(r['undated_totals']['commission_cents'],5187)
        self.assertIsNone(self.report('2026-10-31','2026-10-31')['totals']['commission_cents'])
        self.assertTrue(self.report('2026-10-31','2026-10-31')['excluded_period_reports'])
        self.assertEqual(self.report('2026-10-01','2026-11-01')['totals']['commission_cents'],5187)

    def test_same_archive_and_old_archive_after_correction_are_noops(self):
        files=[('Category.csv',category())];data=archive(files)
        first=amazon.ingest_archive(self.db,self.id,data,'2026-11-02T12:00:00Z')
        self.assertTrue(first['imported'])
        self.assertTrue(amazon.ingest_archive(self.db,self.id,data,'2026-11-02T12:00:00Z')['duplicate'])
        self.ingest([('Category.csv',category('52,01'))])
        self.assertTrue(amazon.ingest_archive(self.db,self.id,data,'2026-11-02T12:00:00Z')['duplicate'])
        self.assertEqual(self.count(),2);self.assertEqual(self.report()['totals']['commission_cents'],5201)

    def test_legacy_manual_reference_is_replaced_without_losing_history(self):
        p=payload();p.update(start='2026-10-30',end='2026-10-31');p['csv']=p['csv'].replace('01/11/2026','31/10/2026')
        amazon.ingest(self.db,self.id,p,'2026-11-02T10:00:00Z')
        result=self.ingest([('Category.csv',category())])
        self.assertEqual(result['replaced'],1);self.assertEqual(self.count(),2)
        self.assertEqual(len(amazon.active_reports(self.db,self.id)),1)
        self.assertEqual(self.report()['totals']['commission_cents'],5187)

    def test_incompatible_overlap_and_scope_block_all_files(self):
        self.ingest([('Category.csv',category())])
        for other in [category(start='2026-10-29'),category(scope='synthetic-21')]:
            with self.assertRaisesRegex(ValueError,'Chevauchement incompatible'):
                self.ingest([('Category.csv',other)])
            self.assertEqual(self.count(),1)
        with self.assertRaisesRegex(ValueError,'Chevauchement incompatible dans le ZIP'):
            self.ingest([('Category.csv',category(start='2026-10-29')),('other/Category.csv',category())])

    def test_correction_retires_old_detail_even_when_its_kind_changes(self):
        self.ingest([('Category.csv',category()),('Tracking-Id.csv',category().replace('Catégorie','Tracking ID').replace('Maison','synthetic-21'))])
        self.ingest([('Category.csv',category('52,00'))])
        self.assertEqual(self.report()['tracking'],[])
        self.assertEqual(self.report()['totals']['commission_cents'],5200)

    def test_replacement_cannot_discard_an_existing_metric(self):
        self.ingest([('Category.csv',category())])
        text='Période: 2026-10-30 → 2026-10-31\nScope: all\nCurrency: EUR\nCatégorie;Revenus totaux\nMaison;52,00\n'
        with self.assertRaisesRegex(ValueError,'indicateurs à remplacer'):self.ingest([('Category.csv',text)])
        self.assertEqual(self.report()['totals']['clicks'],20)

    def test_invalid_member_and_write_failure_are_atomic(self):
        self.ingest([('Category.csv',category())]);before=aff.export_backup(self.db)
        with self.assertRaises(ValueError):self.ingest([('Category.csv',category('52,00')),('bad.csv','bad')])
        self.assertEqual(aff.export_backup(self.db),before)
        self.db.execute("CREATE TRIGGER zip_failure BEFORE INSERT ON aff_snapshots WHEN NEW.summary LIKE '%Daily-Trends%' BEGIN SELECT RAISE(ABORT, 'synthetic disk failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.ingest([('Category.csv',category('52,00')),('Daily-Trends.csv',daily())])
        self.assertEqual(aff.export_backup(self.db),before)

    def test_missing_metadata_requests_only_missing_information(self):
        text='Catégorie;Revenus totaux\nMaison;51,87\n'
        files=[('Category.csv',text)]
        result=self.ingest(files);self.assertFalse(result['imported']);self.assertEqual(self.count(),0)
        self.assertEqual(result['needs'][0]['fields'],['start','end','scope','currency'])
        result=self.ingest(files,coverage={'Category.csv':{'start':'2026-10-30','end':'2026-10-31','scope':'all','currency':'EUR'}})
        self.assertTrue(result['imported']);self.assertEqual(self.report()['daily'],[])

    def test_dates_repeated_headers_missing_values_and_float_rounding(self):
        text=daily();header=text.splitlines()[2]
        text=text.replace('10-31-2026',header+'\n10-31-2026').replace(';12;3;2;',';-;3;2;')
        self.ingest([('Daily-Trends.csv',text)])
        self.assertEqual(self.report()['totals']['commission_cents'],5187)
        self.assertEqual(self.report()['totals']['clicks'],8)

    def test_currency_and_invented_precision_rejected(self):
        for text in [category().replace('EUR','USD'),category('1,234'),daily().replace('10-30-2026','13-30-2026')]:
            with self.assertRaises(ValueError):self.ingest([('Category.csv',text)])
        self.assertEqual(self.count(),0)

    def test_tabs_currency_symbols_and_filename_period(self):
        text='Scope: all\nCatégorie\tRevenus totaux (EUR)\nMaison\t1 234,56 €\n'
        self.ingest([('Category_2026-10-30_2026-10-31.txt',text)])
        self.assertEqual(self.report()['totals']['commission_cents'],123456)

    def test_divergent_daily_view_stays_out_of_commission_chart(self):
        result=self.ingest([('Category.csv',category()),('Daily-Trends.csv',daily().replace('20.00','21.00'))])
        self.assertTrue(result['warnings'])
        self.assertEqual(self.report()['totals']['commission_cents'],5187)
        self.assertTrue(all(d['commission_cents'] is None for d in self.report()['daily']))
        self.assertEqual(self.report()['undated_totals']['commission_cents'],5187)

    def test_large_archive_and_unsafe_inputs(self):
        text=category()+'\n'*1100000
        self.assertGreater(len(text),1024*1024)
        # Stored archive avoids the deliberate zip-bomb compression-ratio guard.
        import io,zipfile,base64
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:z.writestr('Category.csv',text)
        result=amazon.ingest_archive(self.db,self.id,{'archive':base64.b64encode(stream.getvalue()).decode()},'2026-11-02T12:00:00Z')
        self.assertTrue(result['imported'])
        for files in [[('../evil.csv',category())],[('bomb.csv','a'*(2*1024*1024))],[('nested.zip','x')]]:
            with self.assertRaises(ValueError):self.ingest(files)

    def test_backups_roundtrip_and_domadoo_is_unchanged(self):
        before=[dict(r) for r in self.db.execute("SELECT * FROM aff_accounts WHERE id='domadoo'")]
        self.ingest([('Category.csv',category())]);self.ingest([('Category.csv',category('52,00'))])
        bundle=aff.export_backup(self.db);target=sqlite3.connect(':memory:');target.row_factory=sqlite3.Row
        try:
            aff.restore_backup(target,bundle)
            self.assertEqual(amazon.report(target,self.id),self.report())
        finally:target.close()
        self.assertEqual(before,[dict(r) for r in self.db.execute("SELECT * FROM aff_accounts WHERE id='domadoo'")])
        self.assertEqual(self.db.execute('SELECT count(*) FROM aff_transactions').fetchone()[0],0)


class ZipOverviewTests(unittest.TestCase):
    setUp=overview_tests.OverviewTests.setUp
    tearDown=overview_tests.OverviewTests.tearDown
    ingest=overview_tests.OverviewTests.ingest
    build=overview_tests.OverviewTests.build

    def test_different_tracking_scopes_prevent_comparison(self):
        self.ingest([('2026-10-28',100,'approved'),('2026-10-30',100,'approved')])
        identity=aff.add_account(self.db,{'partner':'Amazon','label':'Synthetic','platform':'amazon'})['id']
        for day,scope in [('2026-10-28','first-21'),('2026-10-30','second-21')]:
            text=f'Scope: {scope}\nCurrency: EUR\nDate;Commission\n{day};1.00\n'
            amazon.ingest_archive(self.db,identity,archive([('Daily-Trends.csv',text)]),'2026-11-02T12:00:00Z')
        result=self.build()
        self.assertIsNone(result['comparisons']['previous']['daily'][0]['cents'])
        self.assertIsNone(result['comparisons']['previous']['percent'])

    def test_unknown_amount_does_not_establish_complete_day(self):
        self.ingest([('2026-10-30',100,'approved')])
        identity=aff.add_account(self.db,{'partner':'Amazon','label':'Synthetic','platform':'amazon'})['id']
        text='Scope: all\nCurrency: EUR\nDate;Commission\n2026-10-30;1.00\n2026-10-30;-\n'
        amazon.ingest_archive(self.db,identity,archive([('Daily-Trends.csv',text)]),'2026-11-02T12:00:00Z')
        self.assertEqual(self.build()['daily'][0]['status'],'partial')

    def test_declared_period_plus_approved_is_6179_without_fake_bars(self):
        self.ingest([('2026-10-30',992,'approved')])
        identity=aff.add_account(self.db,{'partner':'Amazon','label':'Synthetic','platform':'amazon'})['id']
        amazon.ingest_archive(self.db,identity,archive([('Category.csv',category())]),'2026-11-02T12:00:00Z')
        result=self.build();self.assertEqual(result['total_cents'],6179)
        self.assertEqual(result['undated_cents'],5187)
        self.assertEqual(sum(d['cents'] or 0 for d in result['daily']),992)
        self.assertTrue(result['partial']);self.assertIsNone(result['comparisons']['previous']['percent'])
        self.assertEqual([p['cents'] for p in result['partners']],[992,5187])
        self.assertEqual(self.build('2026-10-31','2026-10-31')['total_cents'],0)


if __name__=='__main__':unittest.main()
