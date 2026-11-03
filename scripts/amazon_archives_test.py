"""Archive lifecycle tests use synthetic evidence, never the production VPS."""
import copy
import json
import sqlite3
import unittest
from unittest.mock import patch

import affiliation as aff
import amazon_affiliation as amazon
import amazon_imports as auto
from amazon_report_views_test import archive
from amazon_zip_test import ZipTests, category
from amazon_affiliation_test import payload

STAMP='2026-11-03T12:00:00Z'


class ArchiveTests(unittest.TestCase):
    setUp=ZipTests.setUp
    tearDown=ZipTests.tearDown
    report=ZipTests.report

    def ingest(self,files):
        return auto.ingest(self.db,self.id,{**archive(files),'filename':'reports.zip'},STAMP)

    def legacy(self,files):
        data={**archive(files),'filename':'old.zip'}
        return auto.retain(self.db,self.id,data,amazon.inspect_archive(data),['Ancien moteur : colonnes ambiguës.'],STAMP)['id']

    def snapshots(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM aff_snapshots WHERE source!='amazon-pending'")]

    def test_legacy_reprocessing_uses_stored_original_and_is_idempotent(self):
        ident=self.legacy([('Linked-Product.csv',category().replace('Catégorie','Titre du produit;Catégorie').replace('Maison','Lampe;Maison'))])
        original=auto.saved_archive(self.db,self.id,ident)['archive']
        self.assertTrue(auto.reprocess(self.db,self.id,ident,STAMP)['imported'])
        before=self.snapshots()
        self.assertTrue(auto.reprocess(self.db,self.id,ident,STAMP)['duplicate'])
        self.assertEqual(before,self.snapshots());self.assertEqual(self.report()['totals']['commission_cents'],5187)
        saved=auto.saved_archive(self.db,self.id,ident)
        self.assertEqual(saved['archive'],original);self.assertEqual(saved['state'],'active')
        self.assertEqual(saved['attempts'][0]['reasons'],['Ancien moteur : colonnes ambiguës.'])
        auto.validate_pending(saved)

    def test_equivalent_duplicate_columns_resolved_by_position_and_format(self):
        text='Période: 2026-10-30 → 2026-10-31\nScope: all\nCurrency: EUR\nTitre du produit;Catégorie;Commission;Commission\nLampe;Maison;1,20;1.20\n'
        result=self.ingest([('Linked.csv',text)])
        self.assertTrue(result['imported']);self.assertEqual(self.report()['totals']['commission_cents'],120)
        saved=auto.saved_archive(self.db,self.id,result['id'])
        self.assertEqual(saved['diagnostics'][0]['columns'][2]['role'],'commission_cents')
        self.assertIsNone(saved['diagnostics'][0]['columns'][3]['role'])
        self.assertTrue(saved['diagnostics'][0]['corrections'])

    def test_empty_duplicate_selects_only_populated_column(self):
        text=category().replace('Revenus totaux','Revenus totaux;Revenus totaux').replace('51,87',';51,87')
        self.assertTrue(self.ingest([('Linked.csv',text)])['imported'])
        self.assertEqual(self.report()['totals']['commission_cents'],5187)

    def test_conflicting_duplicate_amounts_never_selected_by_position(self):
        for other in ('52','oops','USD 51.87'):
            with self.subTest(other=other):
                text=category().replace('Revenus totaux','Revenus totaux;Revenus totaux').replace('51,87','51,87;'+other)
                r=self.ingest([('Linked.csv',text)])
                self.assertTrue(r['pending']);self.assertEqual(r['state'],'unusable')
                self.assertIn('6 « Revenus totaux »',r['reasons'][0])
                self.assertIsNone(self.report()['totals']['commission_cents'])

    def test_conflicting_duplicate_titles_and_dates_remain_blocked(self):
        for text in ['Scope: all\nCurrency: EUR\nDate;Date;Commission\n2026-10-30;2026-10-31;1\n',
                     category().replace('Catégorie','Titre du produit;Titre du produit').replace('Maison','A;B')]:
            self.assertTrue(self.ingest([('report.csv',text)])['pending'])
        self.assertEqual(self.snapshots(),[])

    def test_top_sellers_preamble_delimiters_encodings_and_unknown(self):
        for sep in (';',',','\t'):
            for encoding in ('utf-8-sig','utf-16','cp1252'):
                text='Amazon\nClassement des produits\n'+sep.join(['Rang','ASIN','Titre du produit'])+'\n'+sep.join(['1','B000000001','Éclairage'])+'\n'
                r=self.ingest([('Top-Sellers.txt',text.encode(encoding))])
                self.assertEqual(r['state'],'complementary');self.assertFalse(r['imported'])
                d=auto.saved_archive(self.db,self.id,r['id'])['diagnostics'][0]
                self.assertEqual(d['header_row'],3);self.assertEqual(d['delimiter'],sep)
        r=self.ingest([('Top-Sellers.csv','Unknown;Format\nA;B\n')])
        self.assertEqual(r['state'],'unusable');self.assertIsNone(self.report()['totals']['commission_cents'])

    def test_top_sellers_with_financial_evidence_uses_regular_validation(self):
        text=category().replace('Catégorie','Rank;ASIN').replace('Maison','1;B000000001')
        self.assertTrue(self.ingest([('Top-Sellers.csv',text)])['imported'])
        self.assertEqual(self.report()['totals']['commission_cents'],5187)

    def test_financial_period_report_without_named_view(self):
        text='Période: 2026-10-30 → 2026-10-31\nScope: all\nCurrency: EUR\nCommission;Note\n1.20;Observation\n'
        result=self.ingest([('report.csv',text)])
        self.assertTrue(result['imported']);self.assertEqual(result['files'][0]['view'],'legacy')
        self.assertEqual(self.report()['totals']['commission_cents'],120)

    def test_empty_metrics_are_complementary_and_invalid_rank_stays_blocked(self):
        self.assertEqual(self.ingest([('Category.csv',category().replace('20;4;3;51,87','-;-;-;-'))])['state'],'complementary')
        self.assertEqual(self.ingest([('Top.csv','Rank;ASIN\nwrong;123')])['state'],'unusable')
        self.assertIsNone(self.report()['totals']['commission_cents'])

    def test_partial_zip_processes_reliable_files_without_double_counting(self):
        r=self.ingest([('Category.csv',category()),('Unknown.csv','Something;Else\n1;2\n')])
        self.assertTrue(r['imported']);self.assertTrue(r['pending']);self.assertEqual(self.report()['totals']['commission_cents'],5187)
        before=self.snapshots()
        again=auto.reprocess(self.db,self.id,r['id'],STAMP)
        self.assertTrue(again['pending']);self.assertFalse(again['imported']);self.assertEqual(before,self.snapshots())

    def test_batch_skips_ignored_and_complementary_and_keeps_failures(self):
        first=self.legacy([('Category.csv',category())])
        ignored=self.legacy([('Other.csv',category('100'))])
        auto.ignore(self.db,self.id,ignored,STAMP)
        bad=self.ingest([('Unknown.csv','Unknown;Data\na;b')])
        complementary=self.ingest([('Top.csv','Rank;ASIN\n1;B000000001')])
        result=auto.reprocess_pending(self.db,self.id,STAMP)
        self.assertEqual({r['id'] for r in result['results']},{first,bad['id']})
        self.assertEqual(self.report()['totals']['commission_cents'],5187)
        self.assertEqual(auto.saved_archive(self.db,self.id,ignored)['state'],'ignored')
        self.assertEqual(auto.saved_archive(self.db,self.id,complementary['id'])['state'],'complementary')
        self.assertTrue(auto.reprocess(self.db,self.id,ignored,STAMP)['imported'])
        self.assertEqual(self.report()['totals']['commission_cents'],10000)

    def test_ignore_partial_archive_does_not_remove_already_imported_totals(self):
        r=self.ingest([('Category.csv',category()),('Unknown.csv','x;y\n1;2')])
        auto.ignore(self.db,self.id,r['id'],STAMP)
        self.assertEqual(self.report()['totals']['commission_cents'],5187)
        self.assertEqual(auto.pending_reports(self.db,self.id),[])
        self.assertEqual(auto.ingest(self.db,self.id,auto.saved_archive(self.db,self.id,r['id']),STAMP)['state'],'ignored')

    def test_replaced_history_never_reactivated(self):
        first=self.ingest([('Category.csv',category())])
        self.ingest([('Category.csv',category('52'))])
        before=self.snapshots()
        self.assertEqual(auto.reprocess(self.db,self.id,first['id'],STAMP)['state'],'replaced')
        self.assertEqual(before,self.snapshots());self.assertEqual(self.report()['totals']['commission_cents'],5200)
        self.assertEqual(auto.report_history(self.db,self.id)[0]['state'],'replaced')

    def test_overlap_reanalysis_retains_previous_financial_state(self):
        self.ingest([('Category.csv',category())])
        r=self.ingest([('Category.csv',category('90',start='2026-10-29'))])
        before=self.snapshots()
        self.assertTrue(auto.reprocess(self.db,self.id,r['id'],STAMP)['pending'])
        self.assertEqual(before,self.snapshots());self.assertEqual(self.report()['totals']['commission_cents'],5187)

    def test_old_pending_archive_cannot_overwrite_a_newer_reference(self):
        ident=self.legacy([('Category.csv',category('10'))])
        auto.ingest(self.db,self.id,archive([('New.csv',category('52'))]),'2026-11-04T12:00:00Z')
        before=self.snapshots()
        result=auto.reprocess(self.db,self.id,ident,'2026-11-05T12:00:00Z')
        self.assertTrue(result['pending']);self.assertIn('plus récente',result['reasons'][0])
        self.assertEqual(before,self.snapshots());self.assertEqual(self.report()['totals']['commission_cents'],5200)

    def test_batch_preserves_order_of_original_receipt(self):
        first=self.legacy([('Old.csv',category('10'))])
        second=self.legacy([('New.csv',category('52'))])
        self.db.execute('UPDATE aff_snapshots SET observed_at=? WHERE id=?',('2026-11-04T12:00:00Z',second))
        result=auto.reprocess_pending(self.db,self.id,'2026-11-05T12:00:00Z')
        self.assertEqual([r['id'] for r in result['results']],[first,second])
        self.assertEqual(self.report()['totals']['commission_cents'],5200)
        self.assertEqual(len(self.snapshots()),2)

    def test_quarantined_original_dates_are_never_reused(self):
        amazon.ingest(self.db,self.id,payload(),STAMP)
        bad=amazon.active_reports(self.db,self.id)[0]
        before=self.snapshots()
        with patch.object(amazon,'MISDATED_ANNUAL_EXPORTS',{amazon.financial_rows_fingerprint(bad)}):
            item=auto.report_history(self.db,self.id)[0]
            self.assertEqual(item['state'],'excluded');self.assertIsNone(item['archive_id'])
            self.assertIn('aucune période fiable',item['reason'])
            auto.reprocess_pending(self.db,self.id,STAMP)
            self.assertIsNone(self.report()['totals']['commission_cents']);self.assertEqual(before,self.snapshots())

    def test_aggregate_with_file_period_reprocesses_without_daily_amounts(self):
        text='Période: 2026-01-01 → 2026-11-02\nScope: all\nCurrency: EUR\nDate;Catégorie;Taux de conversion direct;Articles retournés;Revenus totaux\n11-02-2026;Maison;4;1;12.34\n'
        ident=self.legacy([('Category.csv',text)])
        self.assertTrue(auto.reprocess(self.db,self.id,ident,STAMP)['imported'])
        self.assertEqual(self.report()['daily'],[]);self.assertEqual(self.report()['undated_totals']['commission_cents'],1234)

    def test_aggregate_without_period_remains_excluded(self):
        text='Scope: all\nCurrency: EUR\nDate;Catégorie;Taux de conversion direct;Articles retournés;Revenus totaux\n11-02-2026;Maison;4;1;12.34\n'
        ident=self.legacy([('Category-2026-11-03.csv',text)])
        self.assertTrue(auto.reprocess(self.db,self.id,ident,STAMP)['pending'])
        self.assertIsNone(self.report()['totals']['commission_cents'])

    def test_roundtrip_backup_keeps_originals_states_diagnostics_and_exclusions(self):
        r=self.ingest([('Category.csv',category())]);bad=self.ingest([('Unknown.csv','a;b\nx;y')])
        auto.ignore(self.db,self.id,bad['id'],STAMP);self.db.commit()
        bundle=aff.export_backup(self.db)
        target=sqlite3.connect(':memory:');target.row_factory=sqlite3.Row
        try:
            aff.restore_backup(target,bundle)
            self.assertEqual(auto.archives(target,self.id),auto.archives(self.db,self.id))
            self.assertTrue(auto.reprocess(target,self.id,r['id'],STAMP)['duplicate'])
            self.assertEqual(amazon.report(target,self.id)['totals']['commission_cents'],5187)
            broken=copy.deepcopy(bundle)
            for row in broken['tables']['aff_snapshots']:
                v=json.loads(row['summary'])
                if 'amazon_pending' in v:v['amazon_pending']['digest']='0'*64;row['summary']=json.dumps(v);break
            with self.assertRaises(ValueError):aff.restore_backup(target,broken)
        finally:target.close()

    def test_failed_reprocess_rolls_back_analysis_and_financial_writes(self):
        ident=self.legacy([('Category.csv',category())]);before=aff.export_backup(self.db)
        self.db.execute("CREATE TRIGGER fail BEFORE UPDATE ON aff_snapshots BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError):auto.reprocess(self.db,self.id,ident,STAMP)
        self.assertEqual(before,aff.export_backup(self.db))

    def test_account_boundary_and_read_only_diagnostic(self):
        ident=self.legacy([('Category.csv',category())]);self.db.commit()
        other=aff.add_account(self.db,{'partner':'Amazon','label':'Other','platform':'amazon'})['id'];self.db.commit()
        before=aff.export_backup(self.db)
        result=aff.post(lambda:self.db,'amazon/archive-diagnostic',{'account':self.id,'id':ident})
        self.assertNotIn('archive',result);self.assertEqual(before,aff.export_backup(self.db))
        for endpoint in ('amazon/reanalyze','amazon/archive-diagnostic','amazon/pending-archive','amazon/ignore-archive'):
            with self.assertRaises(ValueError):aff.post(lambda:self.db,endpoint,{'account':other,'id':ident})
        r=aff.post(lambda:self.db,'amazon/reanalyze',{'account':self.id,'id':ident})
        self.assertTrue(r['imported'])
        overview=aff.report(self.db,{'account':self.id})
        self.assertNotIn('UEsDB',json.dumps(overview));self.assertNotIn('attempts',overview['amazon'][0]['archives'][0])


del ZipTests
if __name__=='__main__':unittest.main()
