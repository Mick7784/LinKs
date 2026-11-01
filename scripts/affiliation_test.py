import copy
import json
import sqlite3
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
import affiliation as a
from instance_test import InstanceTests

def observation(n=42):
    return {'complete':True,'currency':'EUR','summary':{k:0 for k in a.SUMMARY_KEYS},'pages':7,'vouchers':[{'issued_on':'2025-12-11','amount_cents':4200,'approved':True,'used':True}],
            'transactions':[{'provider_id':str(i),'occurred_at':'2026-10-21 12:00:00','order_cents':12999,'commission_cents':-123 if i==1 else 123,'currency':'EUR','status':'approved' if i%2 else 'not_approved'} for i in range(1,n+1)]}

class FinancialTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row;a.initialize(self.db)
    def tearDown(self):self.db.close()
    def test_repeatable_migration_empty_is_unknown(self):
        a.initialize(self.db);self.assertFalse(a.report(self.db,{})['has_data']);self.assertEqual(len(a.report(self.db,{})['accounts']),1)
    def test_idempotence_negative_corrections_and_disappearance(self):
        value=observation();a.ingest(self.db,'domadoo',value);a.ingest(self.db,'domadoo',value)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM aff_revisions').fetchone()[0],42)
        value['transactions'][0]['commission_cents']=-222;value['transactions'][0]['status']='not_approved';value['transactions'].pop()
        a.ingest(self.db,'domadoo',value)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM aff_revisions').fetchone()[0],44)
        self.assertEqual(self.db.execute("SELECT commission_cents FROM aff_transactions WHERE provider_id='1'").fetchone()[0],-222)
        self.assertEqual(a.transactions(self.db,{'status':'missing'})['total'],1)
        self.assertEqual(len(a.transactions(self.db,{'page':'2'})['items']),20)
    def test_invalid_observation_preserves_valid_snapshot(self):
        original=observation();a.ingest(self.db,'domadoo',original)
        cases=[]
        for key,value in [('complete',False),('currency','USD'),('summary',{}),('pages',0)]:
            candidate=copy.deepcopy(original);candidate[key]=value;cases.append(candidate)
        duplicate=copy.deepcopy(original);duplicate['transactions'].append(duplicate['transactions'][0]);cases.append(duplicate)
        for field,value in [('commission_cents',1.2),('status','rejected'),('occurred_at','2026-02-30 10:00:00')]:
            candidate=copy.deepcopy(original);candidate['transactions'][0][field]=value;cases.append(candidate)
        for candidate in cases:
            with self.assertRaises(ValueError):a.ingest(self.db,'domadoo',candidate)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM aff_snapshots').fetchone()[0],1)
    def test_search_dates_pagination_and_separate_accounts(self):
        a.ingest(self.db,'domadoo',observation())
        new=a.add_account(self.db,{'partner':'Other brand','label':'Second account','platform':'domadoo'})['id']
        a.ingest(self.db,new,observation(1))
        self.assertEqual(a.transactions(self.db,{'search':'1'})['total'],14)
        self.assertEqual(a.transactions(self.db,{'page':'3'})['total'],42)
        self.assertEqual(len(a.transactions(self.db,{'page':'3'})['items']),2)
        self.assertFalse(a.report(self.db,{'start':'2026-11-01'})['aggregate'])
        self.assertEqual(a.report(self.db,{})['coverage']['ready'],2)
        with self.assertRaises(ValueError):a.add_account(self.db,{'partner':'x','label':'x','platform':'http://localhost'})
    def test_recovery_and_daily_timezone(self):
        self.db.execute("INSERT INTO aff_runs(account_id,started_at,status) VALUES('domadoo','2026-10-31','running')")
        a.recover(self.db);self.assertEqual(self.db.execute('SELECT status FROM aff_runs').fetchone()[0],'failed')
        due=a.next_due(4,'Europe/Paris',datetime(2026,10,24,5,tzinfo=timezone.utc))
        self.assertEqual(due,'2026-10-25T03:00:00Z')
        a.configure(self.db,{'enabled':True,'hour':4,'zone':'Europe/Paris'})
        self.assertEqual(a.account(self.db,'domadoo')['enabled'],1)
    def test_immediate_losses_first_date_reappearance_and_backup(self):
        original=observation(2)
        original['transactions'][0]['commission_cents']=100
        original['transactions'][1]['commission_cents']=200
        empty=observation(0)
        with patch.object(a,'stamp',return_value='2026-10-30T12:00:00Z'):
            a.ingest(self.db,'domadoo',original)
        # Invalid/incomplete observations and a failed run cannot create losses.
        with self.assertRaises(ValueError):
            a.ingest(self.db,'domadoo',{**empty,'complete':False})
        self.db.execute("INSERT INTO aff_runs(account_id,started_at,status) VALUES('domadoo','2026-10-31','failed')")
        self.assertEqual(a.report(self.db,{})['losses'],[])
        with patch.object(a,'stamp',return_value='2026-10-31T23:30:00Z'):
            a.ingest(self.db,'domadoo',empty)
        # Both statuses disappear immediately. Paris date is November 1, not October 31.
        query={'start':'2026-11-01','end':'2026-11-01'}
        self.assertEqual(a.report(self.db,query)['losses'],[{'account_id':'domadoo','sales':2,'cents':300}])
        self.assertEqual(a.report(self.db,{'end':'2026-10-31'})['losses'],[])
        items=a.transactions(self.db,{**query,'status':'lost'})['items']
        self.assertEqual(len(items),2)
        self.assertEqual({r['status'] for r in items},{'approved','not_approved'})
        self.assertEqual({r['first_missing_at'] for r in items},{'2026-10-31T23:30:00Z'})
        with patch.object(a,'stamp',return_value='2026-11-02T12:00:00Z'):
            a.ingest(self.db,'domadoo',empty)
        self.assertEqual(a.report(self.db,query)['losses'][0]['sales'],2)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM aff_revisions').fetchone()[0],4)
        returned=copy.deepcopy(original);returned['transactions']=returned['transactions'][:1]
        returned['transactions'][0].update(status='not_approved',commission_cents=175)
        with patch.object(a,'stamp',return_value='2026-11-03T12:00:00Z'):
            a.ingest(self.db,'domadoo',returned)
        self.assertEqual(a.report(self.db,query)['losses'][0]['cents'],200)
        actual=a.transactions(self.db,{'status':'not_approved','search':'1'})['items'][0]
        self.assertEqual((actual['present'],actual['commission_cents']),(1,175))
        with patch.object(a,'stamp',return_value='2026-11-04T12:00:00Z'):
            a.ingest(self.db,'domadoo',empty)
        self.assertEqual(a.report(self.db,query)['losses'][0],{'account_id':'domadoo','sales':2,'cents':375})
        self.assertEqual(a.report(self.db,{'start':'2026-11-04'})['losses'],[])
        target=sqlite3.connect(':memory:');target.row_factory=sqlite3.Row;a.initialize(target)
        try:
            a.restore_backup(target,a.export_backup(self.db))
            self.assertEqual(a.report(target,query)['losses'],a.report(self.db,query)['losses'])
        finally:target.close()

    def test_loss_ids_are_scoped_to_account(self):
        other=a.add_account(self.db,{'partner':'Other','label':'Other','platform':'domadoo'})['id']
        a.ingest(self.db,'domadoo',observation(1));a.ingest(self.db,other,observation(1))
        a.ingest(self.db,'domadoo',observation(0))
        self.assertEqual(a.report(self.db,{'account':other})['losses'],[])
        self.assertEqual(a.report(self.db,{})['losses'],[{'account_id':'domadoo','sales':1,'cents':-123}])
    def test_no_voucher_secrets_in_snapshot(self):
        data=observation();data['vouchers'][0]['code']='SECRET'
        with self.assertRaises(ValueError):a.ingest(self.db,'domadoo',data)
    def test_backup_restore_history_without_session_or_automatic_collection(self):
        a.ingest(self.db,'domadoo',observation());a.configure(self.db,{'enabled':True})
        bundle=a.export_backup(self.db)
        target=sqlite3.connect(':memory:');target.row_factory=sqlite3.Row;a.initialize(target)
        try:
            self.assertIn('restauré',a.restore_backup(target,bundle))
            self.assertEqual(a.transactions(target,{})['total'],42)
            self.assertEqual(a.account(target,'domadoo')['enabled'],0)
            self.assertEqual(a.account(target,'domadoo')['session_state'],'disconnected')
            altered=observation();altered['transactions'][0]['commission_cents']=-999;a.ingest(target,'domadoo',altered)
            self.assertEqual(a.restore_backup(target,bundle),'conservé')
            self.assertEqual(target.execute("SELECT commission_cents FROM aff_transactions WHERE provider_id='1'").fetchone()[0],-999)
            broken=copy.deepcopy(bundle);broken['tables']['aff_accounts'][0]['id']='../escape'
            with self.assertRaises(ValueError):a.restore_backup(target,broken)
        finally:target.close()

class SecurityTests(InstanceTests):
    # Run only module-specific HTTP checks, without inheriting the full instance suite.
    def test_affiliation_is_private_and_csrf_protected(self):
        admin=self.server();public=self.server(False)
        self.assertEqual(self.request(admin+'/api/affiliation/overview')[0],403)
        self.assertEqual(self.request(public+'/api/affiliation/overview')[0],404)
        self.assertEqual(self.setup(admin)[0],200)
        self.assertEqual(self.request(admin+'/api/affiliation/overview')[0],200)
        self.assertEqual(self.request(admin+'/api/affiliation/settings',{'enabled':True})[0],403)
        status,body,_=self.request(admin+'/api/affiliation/settings',{'enabled':True},headers={'X-Links-CSRF':self.csrf(admin)})
        self.assertEqual(status,200,body)
        self.assertEqual(self.request(public+'/api/affiliation/sync',{})[0],404)
        self.assertEqual(self.request(admin+'/api/pulse/affiliation')[0],404)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(FinancialTests)
    suite.addTest(SecurityTests('test_affiliation_is_private_and_csrf_protected'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
