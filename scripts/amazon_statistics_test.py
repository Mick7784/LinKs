import unittest,sqlite3,copy,json,hashlib
import affiliation as a
import amazon_affiliation as amazon


def payload(view='category',detail=False,dated=True):
    return dict(csv='Date,Tag,Clics,Commandés,Expédiés,Commission\n10-31-2026,Other,2.0,1.0,1.0,1.25\n10-31-2026,test-21,5.0,2.0,2.0,2.50\n',kind='performance',view=view,contribution='detail' if detail else 'totals',mapping={**({'date':'Date'} if dated else {}),'tracking_id':'Tag','clicks':'Clics','ordered_items':'Commandés','shipped_items':'Expédiés','commission_cents':'Commission'},single_day=not dated,start='2026-10-31',end='2026-10-31',scope='all',decimal='dot',date_format='mdy',confirmed=True)

class StatisticsTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row;a.initialize(self.db)
        self.id=a.add_account(self.db,{'partner':'Amazon','label':'FR','platform':'amazon'})['id']
    def tearDown(self):self.db.close()
    def ingest(self,p):return amazon.ingest(self.db,self.id,p,'2026-11-01T12:00:00Z')
    def test_three_views_count_once_and_tracking_is_separate(self):
        self.ingest(payload());self.ingest(payload('linked_product',True));self.ingest(payload('tracking_id',True,False))
        r=amazon.report(self.db,self.id)
        self.assertEqual(r['totals']['clicks'],7);self.assertEqual(r['totals']['commission_cents'],375)
        self.assertEqual(r['daily'][0]['clicks'],7);self.assertEqual(len(r['tracking']),2)
        self.assertEqual(sum(t['commission_cents'] for t in r['tracking']),375)
        self.assertIsNone(r['totals']['orders']);self.assertFalse(r['loss_tracking'])
        self.assertEqual(amazon.report(self.db,self.id,'2026-11-01')['daily'],[])
        self.assertTrue(self.ingest(payload())['duplicate'])
        correction=payload();correction['csv']=correction['csv'].replace('1.25','1.50');self.ingest(correction)
        self.assertEqual(amazon.report(self.db,self.id)['totals']['commission_cents'],400)
        target=sqlite3.connect(':memory:');target.row_factory=sqlite3.Row
        try:a.restore_backup(target,a.export_backup(self.db));self.assertEqual(amazon.report(target,self.id),amazon.report(self.db,self.id))
        finally:target.close()
    def test_overlapping_references_and_mixed_kinds_are_rejected(self):
        self.ingest(payload())
        with self.assertRaises(ValueError):self.ingest(payload('linked_product'))
        other=payload();other['kind']='earnings';other['mapping']={'date':'Date','commission_cents':'Commission'}
        with self.assertRaises(ValueError):self.ingest(other)
    def test_undated_reference_has_no_daily_curve(self):
        self.ingest(payload('tracking_id',False,False));r=amazon.report(self.db,self.id)
        self.assertEqual(r['daily'],[]);self.assertEqual(r['totals']['clicks'],7)
    def test_legacy_snapshot_without_clicks_still_valid(self):
        p=payload();p['kind']='earnings';p['mapping']={'date':'Date','commission_cents':'Commission'}
        value=amazon.normalize(p)
        for row in value['rows']:del row['clicks']
        value['digest']=hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        amazon.validate_saved(value)

if __name__=='__main__':unittest.main()
