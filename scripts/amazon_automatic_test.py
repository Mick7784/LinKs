"""Synthetic ZIPs, in-memory databases; no supplier access."""
import json
import sqlite3
import unittest
import affiliation as aff
import amazon_affiliation as amazon
import amazon_imports as auto
from amazon_collection_test import batch, DAY
from amazon_report_views_test import archive
from amazon_zip_test import category, ZipTests
from amazon_affiliation_test import payload

def daily(rows):
    return 'Scope: all\nCurrency: EUR\nDate;Commission\n'+''.join(f'{day};{amount}\n' for day,amount in rows)

class AutomaticTests(unittest.TestCase):
    setUp=ZipTests.setUp
    tearDown=ZipTests.tearDown
    count=ZipTests.count
    report=ZipTests.report
    def ingest(self,files):return auto.ingest(self.db,self.id,{**archive(files),'filename':'exports.zip'},'2026-11-03T12:00:00Z')

    def test_known_reference_still_ranks_a_new_complement_in_the_same_zip(self):
        source=category()
        self.ingest([('Category.csv',source)])
        complement=category('1,00').replace('Catégorie','Titre du produit')
        result=self.ingest([('Category.csv',source),('Product.csv',complement)])
        self.assertEqual(result['files'][0]['reference_metrics'],[])
        self.assertEqual(self.report()['totals']['commission_cents'],5187)

    def test_zip_without_provider_revision_cannot_replace_manual_totals(self):
        data=payload()
        amazon.ingest(self.db,self.id,data,'2026-11-02T10:00:00Z')
        result=self.ingest([('unseen.csv',daily([('2026-11-01','9.00')]))])
        self.assertFalse(result['imported'])
        self.assertTrue(result['pending'])
        self.assertEqual(self.report()['totals']['commission_cents'],1234)

    def test_zip_with_invalid_financial_member_cannot_apply_correction(self):
        self.ingest([('Category.csv',category())])
        broken=category().replace('Revenus totaux','Remboursements (EUR)')
        result=self.ingest([('Category.csv',category('52,00')),('Broken.csv',broken)])
        self.assertFalse(result['imported'])
        self.assertIn('Remboursements',result['reasons'][0])
        self.assertEqual(self.report()['totals']['commission_cents'],5187)

    def test_zip_rejects_unknown_currency_and_invalid_digit_grouping(self):
        for text in (category().replace('Currency: EUR','Currency: NOK'),
                     category('1,2.34'),
                     category().replace('Revenus totaux\n','Revenus totaux;Devise\n').replace('51,87\n','51,87;GBP\n')):
            result=self.ingest([('Category.csv',text)])
            self.assertFalse(result['imported'])
            self.assertEqual(result['state'],'unusable')
        self.assertIsNone(self.report()['totals']['commission_cents'])

    def test_zip_preserves_return_columns_and_rejects_ambiguous_returns(self):
        text='Scope: all\nCurrency: EUR\nDate;Clics;Articles retournés;Commission\n2026-10-30;813;2;51.87\n2026-10-31;0;0;-1\n2026-11-01;0;;0\n'
        self.assertTrue(self.ingest([('A.csv',text)])['imported'])
        self.assertEqual(self.report()['totals']['returned_items'],2)
        self.assertEqual([row['returned_items'] for row in self.report()['daily']],[2,0,None])
        conflicting=text.replace('Articles retournés;','Articles retournés;Returned Items;').replace(';2;51.87',';2;3;51.87').replace(';0;-1',';0;0;-1').replace(';;0',';;;0')
        self.assertFalse(self.ingest([('conflicting.csv',conflicting)])['imported'])
        self.assertEqual(self.report()['totals']['returned_items'],2)

    def test_csv_and_reordered_zip_share_observation_history(self):
        text='Date;Commission\n2026-10-30;10.00\n2026-10-31;12.34\n'
        data=dict(csv=text,kind='earnings',start='2026-10-30',end='2026-10-31',scope='all',
                  mapping={'date':'Date','commission_cents':'Commission'},decimal='dot',confirmed=True)
        correction=daily([('2026-10-30','10'),('2026-10-31','13')])
        self.assertTrue(self.ingest([('original.csv',daily([('2026-10-30','10'),('2026-10-31','12.34')]))])['imported'])
        self.assertTrue(self.ingest([('correction.csv',correction)])['imported'])
        reordered={**data,'csv':'Date;Commission\n2026-10-31;12.3400\n2026-10-30;10\n'}
        self.assertTrue(amazon.ingest(self.db,self.id,reordered,'2026-11-04T10:00:00Z')['duplicate'])
        self.assertEqual(self.report()['totals']['commission_cents'],2300)
        self.assertEqual(self.report()['reports'][0]['source'],'amazon-zip')

    def test_unsupported_financial_column_keeps_original_out_of_totals(self):
        text='Scope: all\nCurrency: EUR\nDate;Commission;Remboursements (EUR)\n2026-10-30;51.87;2\n'
        result=self.ingest([('A.csv',text)])
        self.assertEqual(result['state'],'unusable')
        self.assertIn('Remboursements (EUR)',result['reasons'][0])
        self.assertIsNone(self.report()['totals']['commission_cents'])

    def test_native_annual_export_marker_is_not_a_commission_day(self):
        text='Date,catégorie,taux de conversion direct,articles retournés,revenus totaux\n11-02-2026,Maison,4,1,12.34\n'
        result=self.ingest([('Category-03nov2026.csv',text)])
        self.assertTrue(result['pending']);self.assertEqual(self.report()['daily'],[])
        self.assertTrue(any('repère' in reason for reason in result['reasons']))
        value,missing,_=amazon.auto_report({'name':'Category.csv','csv':text},{'start':'2026-01-01','end':'2026-11-02','scope':'all','currency':'EUR'})
        self.assertIsNone(missing);self.assertEqual(value['date_basis'],'confirmed_period')
        self.assertIsNone(value['rows'][0]['date']);self.assertEqual(value['start'],'2026-01-01')
        self.assertEqual(value['rows'][0]['commission_cents'],1234)

    def test_native_linked_product_keeps_product_title_and_view(self):
        text='Date,catégorie,titre du produit,ASIN,taux de conversion direct,articles retournés,revenus totaux\n11-02-2026,Maison,Produit test,B000000001,4,1,12.34\n'
        value,missing,_=amazon.auto_report({'name':'renamed.csv','csv':text},{'start':'2026-01-01','end':'2026-11-02','scope':'all','currency':'EUR'})
        self.assertIsNone(missing);self.assertEqual(value['view'],'linked_product')
        self.assertEqual(value['rows'][0]['title'],'Produit test');self.assertIsNone(value['rows'][0]['date'])

    def test_windows_1252_zip_and_binary_rejection(self):
        import base64,io,zipfile
        def packed(raw):
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as z:z.writestr('Category.csv',raw)
            return {'archive':base64.b64encode(stream.getvalue()).decode()}
        text='Date,catégorie,revenus totaux\n11-02-2026,Électricité,12.34\n'
        self.assertEqual(amazon.inspect_archive(packed(text.encode('cp1252')))['files'][0]['csv'],text)
        with self.assertRaises(ValueError):amazon.inspect_archive(packed(b'\x00\x01\xff'))

    def test_upload_date_never_changes_daily_export_dates(self):
        self.ingest([('03nov2026.csv',daily([('2026-09-12','1'),('2026-10-05','2')]))])
        self.assertEqual([r['date'] for r in self.report()['daily']],['2026-09-12','2026-10-05'])

    def test_repair_existing_stats_preserves_history_and_unrelated_reports(self):
        from unittest.mock import patch
        p=payload();amazon.ingest(self.db,self.id,p,'2026-11-03T12:00:00Z')
        bad=amazon.active_reports(self.db,self.id)[0]
        self.ingest([('daily.csv',daily([('2026-09-12','2')]))])
        before=aff.export_backup(self.db)
        with patch.object(amazon,'MISDATED_ANNUAL_EXPORTS',{amazon.financial_rows_fingerprint(bad)}):
            report=self.report()
            self.assertEqual(report['totals']['commission_cents'],200)
            self.assertEqual([r['date'] for r in report['daily']],['2026-09-12'])
            self.assertEqual(len(report['quarantined_reports']),1)
            self.assertEqual(before,aff.export_backup(self.db))
            target=sqlite3.connect(':memory:');target.row_factory=sqlite3.Row
            try:
                aff.restore_backup(target,before)
                self.assertEqual(amazon.report(target,self.id)['totals']['commission_cents'],200)
            finally:target.close()
            # An explicitly covered period remains valid and is never dated.
            aggregate={**bad,'date_basis':'confirmed_period','rows':[{**r,'date':None} for r in bad['rows']]}
            self.assertFalse(amazon.misdated_annual_export(aggregate))

    def test_complement_separate_zip_does_not_replace_totals(self):
        self.ingest([('Category.csv',category())])
        result=self.ingest([('Tracking.csv',category().replace('Catégorie','Tracking ID').replace('Maison','tag-21'))])
        self.assertTrue(result['imported']);self.assertEqual(result['files'][0]['reference_metrics'],[])
        self.assertEqual(self.report()['totals']['commission_cents'],5187)
        self.assertEqual(self.report()['tracking'][0]['commission_cents'],5187)

    def test_correction_and_repacked_old_file_never_reactivate_history(self):
        self.ingest([('a.csv',category())]);self.ingest([('b.csv',category('52,00'))])
        self.assertEqual(self.report()['totals']['commission_cents'],5200)
        n=self.count();self.assertTrue(self.ingest([('renamed.csv',category())])['duplicate'])
        # A newly packaged original is retained, without adding a financial report.
        self.assertEqual(n+1,self.count());self.assertEqual(self.report()['totals']['commission_cents'],5200)
        self.assertEqual(self.db.execute("SELECT count(*) FROM aff_snapshots WHERE source='amazon-zip'").fetchone()[0],2)

    def test_rolling_daily_window_preserves_uncovered_days(self):
        self.ingest([('a.csv',daily([('2026-10-29','1'),('2026-10-30','2')]))])
        self.ingest([('b.csv',daily([('2026-10-30','3'),('2026-10-31','4')]))])
        r=self.report();self.assertEqual(r['totals']['commission_cents'],800)
        self.assertEqual([d['commission_cents'] for d in r['daily']],[100,300,400])

    def test_unknown_file_retained_once_and_survives_backup(self):
        files=[('Tracking.csv','Tracking ID;Commission\ntag-21;12.34\n')]
        result=self.ingest(files);self.assertTrue(result['pending']);self.assertIsNone(self.report()['totals']['commission_cents'])
        self.assertTrue(self.ingest(files)['duplicate']);self.assertEqual(self.count(),1)
        bundle=aff.export_backup(self.db);target=sqlite3.connect(':memory:');target.row_factory=sqlite3.Row
        try:
            aff.restore_backup(target,bundle)
            pending=auto.pending_reports(target,self.id);self.assertEqual(len(pending),1)
            saved=json.loads(target.execute('SELECT summary FROM aff_snapshots').fetchone()[0])['amazon_pending']
            self.assertEqual(amazon.inspect_archive(saved)['files'][0]['csv'],files[0][1])
        finally:target.close()

    def test_unknown_does_not_expose_raw_archive_in_overview(self):
        self.ingest([('x.csv','Date;Commission\n2026-10-30;1\n')])
        report=aff.report(self.db,{})
        self.assertNotIn('UEsDB',json.dumps(report));self.assertIsNone(next(a for a in report['accounts'] if a['id']==self.id)['snapshot'])

    def test_ambiguous_aggregates_and_scopes_stay_out_of_totals(self):
        self.ingest([('a.csv',category())])
        for text in [category('100',start='2026-10-29'),category('100',scope='tag-21')]:
            self.assertTrue(self.ingest([('b.csv',text)])['pending'])
            self.assertEqual(self.report()['totals']['commission_cents'],5187)

    def test_update_one_metric_preserves_other_metrics(self):
        self.ingest([('a.csv',category())])
        text='Période: 2026-10-30 → 2026-10-31\nScope: all\nCurrency: EUR\nCatégorie;Commission\nMaison;52\n'
        self.assertTrue(self.ingest([('a.csv',text)])['imported'])
        self.assertEqual(self.report()['totals']['commission_cents'],5200);self.assertEqual(self.report()['totals']['clicks'],20)

    def test_transaction_failure_preserves_last_report(self):
        self.ingest([('a.csv',category())]);before=aff.export_backup(self.db)
        self.db.execute("CREATE TRIGGER fail BEFORE INSERT ON aff_snapshots BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.ingest([('a.csv',category('52'))])
        self.assertEqual(aff.export_backup(self.db),before)

    def test_type_comes_from_content_and_negative_correction(self):
        r=self.ingest([('Tracking-Id.csv',category('-1,00'))])
        self.assertEqual(r['files'][0]['view'],'category');self.assertEqual(self.report()['totals']['commission_cents'],-100)

    def test_csv_disjoint_metrics_accepted(self):
        amazon.ingest(self.db,self.id,payload(),'2026-11-03T12:00:00Z')
        p={**payload(),'kind':'performance','csv':'Date;Clics\n01/11/2026;8\n','mapping':{'date':'Date','clicks':'Clics'}}
        amazon.ingest(self.db,self.id,p,'2026-11-03T12:00:00Z')
        self.assertEqual(self.report()['totals']['clicks'],8);self.assertEqual(self.report()['totals']['commission_cents'],1234)

    def test_tracking_details_do_not_hide_other_day(self):
        p={**payload(),'view':'tracking_id'}
        amazon.ingest(self.db,self.id,p,'2026-11-03T12:00:00Z')
        p.update(contribution='detail',start='2026-11-02',end='2026-11-02',csv=p['csv'].replace('01/11','02/11').replace('12,34','5,00'))
        amazon.ingest(self.db,self.id,p,'2026-11-03T12:00:00Z')
        self.assertEqual(self.report()['tracking'][0]['commission_cents'],1734)

    def test_csv_correction_cannot_double_count_a_different_metric_set(self):
        amazon.ingest(self.db,self.id,payload(),'2026-11-03T12:00:00Z')
        p=payload();p['mapping'].pop('shipped_items');p['csv']=p['csv'].replace('12,34','15,00')
        with self.assertRaisesRegex(ValueError,'conserver les indicateurs'):amazon.ingest(self.db,self.id,p,'2026-11-03T13:00:00Z')
        self.assertEqual(self.report()['totals']['commission_cents'],1234)

    def test_partial_tracking_detail_never_adds_to_overlapping_aggregate(self):
        self.ingest([('Tracking.csv',category('12,34',start='2026-11-01',end='2026-11-02').replace('Catégorie','Tracking ID').replace('Maison','site-21'))])
        p={**payload(),'view':'tracking_id','contribution':'detail','start':'2026-11-02','end':'2026-11-02'}
        p['csv']=p['csv'].replace('01/11','02/11').replace('12,34','5,00')
        amazon.ingest(self.db,self.id,p,'2026-11-03T12:00:00Z')
        r=self.report();self.assertEqual(r['tracking'][0]['commission_cents'],500);self.assertTrue(r['tracking_partial'])
        self.assertEqual(r['totals']['commission_cents'],1234)

    def test_portal_requires_explicit_scope_proof(self):
        p=batch();amazon.ingest_portal_batch(self.db,self.id,p,DAY,'test-21','2026-11-03T12:00:00Z')
        before=aff.export_backup(self.db);p.pop('scope')
        with self.assertRaisesRegex(ValueError,'périmètre|Périmètre'):amazon.ingest_portal_batch(self.db,self.id,p,DAY,'test-21','2026-11-03T12:00:00Z')
        self.assertEqual(aff.export_backup(self.db),before)

    def test_divergent_portal_views_preserve_previous_snapshot(self):
        p=batch();p['files'][0]['csv']=p['files'][0]['csv'].replace('1.25','12.50')
        with self.assertRaisesRegex(ValueError,'divergent'):amazon.ingest_portal_batch(self.db,self.id,p,DAY,'test-21','2026-11-03T12:00:00Z')
        self.assertEqual(self.count(),0)

del ZipTests
if __name__=='__main__':unittest.main()
