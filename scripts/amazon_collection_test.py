import copy,sqlite3,unittest
import affiliation as a
import amazon_affiliation as amazon

DAY='2026-10-31'
def batch():
    common='clics,articles commandés,articles expédiés,revenus totaux'
    return dict(day=DAY,complete=True,scope={'value':'all','verified':True,'method':'portal_tracking_filter'},files=[
        dict(view='category',csv='Date,catégorie,'+common+'\n10-31-2026,Test,2,1,1,1.25\n'),
        dict(view='linked_product',csv='Date,titre du produit,ASIN,'+common+'\n10-31-2026,Test,B000,2,1,1,1.25\n'),
        dict(view='tracking_id',csv='Numéro de suivi,'+common+'\ntest-21,2,1,1,1.25\n')])
class Collection(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row;a.initialize(self.db)
        self.id=a.add_account(self.db,dict(partner='Amazon',label='FR',platform='amazon'))['id']
    def tearDown(self):self.db.close()
    def ingest(self,p):return amazon.ingest_portal_batch(self.db,self.id,p,DAY,'test-21','2026-11-01T12:00:00Z')
    def test_repeat_is_idempotent_and_views_do_not_add(self):
        self.ingest(batch());self.assertTrue(all(r['duplicate'] for r in self.ingest(batch())))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM aff_snapshots').fetchone()[0],3)
        r=amazon.report(self.db,self.id);self.assertEqual(r['totals']['commission_cents'],125)
        self.assertEqual(r['tracking'][0]['clicks'],2)
    def test_older_portal_batch_cannot_restore_replaced_totals(self):
        self.ingest(batch())
        corrected=batch()
        for file in corrected['files']:
            file['csv']=file['csv'].replace('1.25','1.30')
        self.ingest(corrected)
        self.assertTrue(all(r['duplicate'] for r in self.ingest(batch())))
        self.assertEqual(amazon.report(self.db,self.id)['totals']['commission_cents'],130)
    def test_inactive_reference_blocks_new_details_from_an_old_portal_batch(self):
        self.ingest(batch())
        corrected=batch()
        for file in corrected['files']:
            file['csv']=file['csv'].replace('1.25','1.30')
        self.ingest(corrected)
        old=batch()
        old['files'][2]['csv']=old['files'][2]['csv'].replace('2,1,1,1.25','1,1,1,1.25')+'other-21,1,0,0,0\n'
        self.assertTrue(all(r['duplicate'] for r in self.ingest(old)))
        self.assertEqual(amazon.report(self.db,self.id)['tracking'][0]['commission_cents'],130)
    def test_portal_returns_are_preserved_and_compared(self):
        value=batch()
        for file in value['files']:
            header, row=file['csv'].splitlines()
            file['csv']=header+',Articles retournés\n'+row+',2\n'
        self.ingest(value)
        report=amazon.report(self.db,self.id)
        self.assertEqual(report['totals']['returned_items'],2)
        self.assertEqual(report['tracking'][0]['returned_items'],2)
        self.assertTrue(all(r['source']=='amazon-portal' for r in report['reports']))
        value['files'][1]['csv']=value['files'][1]['csv'].replace('1.25,2','1.25,3')
        with self.assertRaisesRegex(ValueError,'divergent'):
            self.ingest(value)
    def test_wrong_period_tag_partial_or_columns_preserve_history(self):
        self.ingest(batch())
        for change in ['period','tag','partial','columns']:
            p=batch()
            if change=='period':p['files'][0]['csv']=p['files'][0]['csv'].replace('10-31','10-30')
            if change=='tag':p['files'][2]['csv']=p['files'][2]['csv'].replace('test-21','other-21')
            if change=='partial':p['complete']=False
            if change=='columns':p['files'][1]['csv']=p['files'][1]['csv'].replace('ASIN','Unknown')
            with self.assertRaises(ValueError):self.ingest(p)
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM aff_snapshots').fetchone()[0],3)
    def test_late_overlap_rolls_back_first_view(self):
        p=batch();file=p['files'][2]
        original=amazon.store_csv
        calls=[]
        def fail_late(*args):
            calls.append(1)
            if len(calls)==2:raise ValueError('overlap')
            return original(*args)
        from unittest.mock import patch
        with patch.object(amazon,'store_csv',side_effect=fail_late):
            with self.assertRaises(ValueError):self.ingest(p)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM aff_snapshots').fetchone()[0],0)
if __name__=='__main__':unittest.main()
