import copy
import os
import sqlite3
import unittest
from unittest.mock import patch
import affiliation as a
import amazon_affiliation as amazon
from affiliation_test import observation


def payload():
    return {'csv':'Date;Tag;ASIN;Produit;Articles;Commission\n01/11/2026;site-21;B012345678;Écran;2;12,34\n',
            'header_row':1,'kind':'earnings','start':'2026-11-01','end':'2026-11-01','scope':'all','decimal':'comma',
            'mapping':{'date':'Date','tracking_id':'Tag','asin':'ASIN','title':'Produit','shipped_items':'Articles','commission_cents':'Commission'},'confirmed':True}


class AmazonTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row;a.initialize(self.db)
        self.identity=a.add_account(self.db,{'partner':'Amazon','label':'France','platform':'amazon'})['id']
    def tearDown(self):self.db.close()
    def ingest(self,value):return amazon.ingest(self.db,self.identity,value,'2026-11-02T10:00:00Z')
    def test_import_preserves_dimensions_and_unknowns(self):
        self.ingest(payload());r=amazon.report(self.db,self.identity)
        self.assertEqual(r['totals']['commission_cents'],1234);self.assertEqual(r['totals']['shipped_items'],2)
        self.assertIsNone(r['totals']['orders']);self.assertIsNone(r['totals']['payment_cents'])
        self.assertEqual(r['rows'][0]['tracking_id'],'site-21');self.assertFalse(r['loss_tracking'])
        self.assertEqual(a.report(self.db,{})['amazon'][0]['totals'],r['totals'])
        self.assertEqual(a.report(self.db,{})['losses'],[])
    def test_repeat_and_correction_keep_history_without_double_count(self):
        self.ingest(payload());self.assertTrue(self.ingest(payload())['duplicate'])
        corrected=payload();corrected['csv']=corrected['csv'].replace('12,34','-1,25');self.ingest(corrected)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM aff_snapshots').fetchone()[0],2)
        self.assertEqual(amazon.report(self.db,self.identity)['totals']['commission_cents'],-125)
    def test_overlap_and_tracking_scope_are_not_double_counted(self):
        self.ingest(payload())
        other=payload();other['start']='2026-10-01'
        with self.assertRaises(ValueError):self.ingest(other)
        other=payload();other['scope']='site-21'
        with self.assertRaises(ValueError):self.ingest(other)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM aff_snapshots').fetchone()[0],1)
    def test_new_window_and_missing_product_never_create_loss(self):
        self.ingest(payload());other=payload();other.update(start='2026-11-02',end='2026-11-02')
        other['csv']=other['csv'].replace('01/11/2026','02/11/2026').replace('B012345678','B098765432');self.ingest(other)
        self.assertEqual(a.report(self.db,{})['losses'],[])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM aff_transactions').fetchone()[0],0)
        self.assertEqual(amazon.report(self.db,self.identity,'2026-11-02','2026-11-02')['totals']['commission_cents'],1234)
    def test_invalid_import_changes_nothing(self):
        self.ingest(payload())
        for change in [{'confirmed':False},{'start':'2026-11-03'},{'scope':'another-21'},{'mapping':{'date':'Date','commission_cents':'Missing'}},{'csv':payload()['csv'].replace('12,34','1,234')}]:
            with self.assertRaises(ValueError):self.ingest({**payload(),**change})
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM aff_snapshots').fetchone()[0],1)
    def test_orders_are_not_commissions_or_payments(self):
        value=payload();value['kind']='orders';value['mapping']={'date':'Date','ordered_items':'Articles','tracking_id':'Tag'};self.ingest(value)
        r=amazon.report(self.db,self.identity)['totals'];self.assertEqual(r['ordered_items'],2);self.assertIsNone(r['orders']);self.assertIsNone(r['commission_cents'])
    def test_backup_roundtrip_and_domadoo_unchanged(self):
        a.ingest(self.db,'domadoo',observation(2));before=a.report(self.db,{'account':'domadoo'})
        self.ingest(payload());after=a.report(self.db,{'account':'domadoo'})
        for key in ('aggregate','daily','losses','coverage','amazon'):self.assertEqual(after[key],before[key])
        self.assertEqual(next(x for x in after['accounts'] if x['id']=='domadoo'),next(x for x in before['accounts'] if x['id']=='domadoo'))
        with self.assertRaises(ValueError):a.ingest(self.db,self.identity,observation())
        bundle=a.export_backup(self.db);target=sqlite3.connect(':memory:');target.row_factory=sqlite3.Row;a.initialize(target)
        try:
            a.restore_backup(target,bundle)
            self.assertEqual(amazon.report(target,self.identity),amazon.report(self.db,self.identity))
            self.assertEqual(a.report(target,{'account':'domadoo'})['aggregate'],before['aggregate'])
        finally:target.close()
        broken=copy.deepcopy(bundle);broken['tables']['aff_snapshots'][-1]['summary']='{"amazon":{}}'
        with self.assertRaises(ValueError):a.restore_backup(self.db,broken)
    def test_old_backup_remains_accepted(self):
        legacy=sqlite3.connect(':memory:');legacy.row_factory=sqlite3.Row;a.initialize(legacy)
        target=sqlite3.connect(':memory:');target.row_factory=sqlite3.Row;a.initialize(target)
        try:
            a.ingest(legacy,'domadoo',observation());bundle=a.export_backup(legacy)
            self.assertEqual(set(bundle['tables']),set(a.TABLES));a.restore_backup(target,bundle)
            self.assertEqual(a.transactions(target,{})['total'],42)
        finally:legacy.close();target.close()
    def test_api_errors_never_echo_secrets(self):
        with patch.object(amazon,'build_opener',side_effect=RuntimeError('SECRET_TOKEN')):
            with self.assertRaises(ValueError) as error:amazon.read_json('https://creatorsapi.amazon',b'',{})
            self.assertNotIn('SECRET_TOKEN',str(error.exception))
    def test_api_probe_keeps_credentials_server_side(self):
        env={f'AMAZON_CREATORS_{self.identity.upper()}_'+k:v for k,v in [('CREDENTIAL_ID','id-secret'),('CREDENTIAL_SECRET','secret-secret'),('VERSION','3.2')]}
        with patch.dict(os.environ,env),patch.object(amazon,'read_json',side_effect=[{'access_token':'token-secret'},{'reports':[{'filename':'earnings.csv','reportType':'CREATOR_CENTRAL','size':123,'lastModified':'2026-11-01'}]}]) as http:
            reports,headers=amazon.list_reports(self.identity)
            self.assertNotIn('secret',str(reports));self.assertEqual(headers['x-marketplace'],'www.amazon.fr')
            self.assertEqual(http.call_args_list[1].args[0],'https://creatorsapi.amazon/reports/v1/listReports')
    def test_get_report_rejects_unknown_files_and_remote_destinations(self):
        with patch.object(amazon,'list_reports',return_value=([{'filename':'ok.csv','reportType':'CREATOR_CENTRAL'}],{})):
            with self.assertRaises(ValueError):amazon.retrieve_report(self.identity,'missing.csv','CREATOR_CENTRAL')
            with patch.object(amazon,'read_json',return_value={'url':'http://127.0.0.1/secret'}):
                with self.assertRaises(ValueError):amazon.retrieve_report(self.identity,'ok.csv','CREATOR_CENTRAL')


if __name__=='__main__':unittest.main()
