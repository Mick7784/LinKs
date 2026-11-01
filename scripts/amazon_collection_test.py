import copy,sqlite3,unittest
import affiliation as a
import amazon_affiliation as amazon

DAY='2026-10-31'
def batch():
    common='clics,articles commandés,articles expédiés,revenus totaux'
    return dict(day=DAY,complete=True,files=[
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
        original=amazon.ingest
        calls=[]
        def fail_late(*args):
            calls.append(1)
            if len(calls)==2:raise ValueError('overlap')
            return original(*args)
        from unittest.mock import patch
        with patch.object(amazon,'ingest',side_effect=fail_late):
            with self.assertRaises(ValueError):self.ingest(p)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM aff_snapshots').fetchone()[0],0)
if __name__=='__main__':unittest.main()
