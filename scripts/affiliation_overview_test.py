import sqlite3
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import affiliation as a
import affiliation_overview as overview
import amazon_affiliation as amazon


class OverviewTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        a.initialize(self.db)

    def tearDown(self):
        self.db.close()

    def ingest(self, rows, observed='2026-11-02T12:00:00Z', identity='domadoo'):
        payload = {'complete': True, 'currency': 'EUR', 'summary': {k: 0 for k in a.SUMMARY_KEYS}, 'pages': 1, 'vouchers': [],
                   'transactions': [{'provider_id': str(i), 'occurred_at': day+' 12:00:00', 'order_cents': 1000,
                                     'commission_cents': amount, 'currency': 'EUR', 'status': state}
                                    for i, (day, amount, state) in enumerate(rows)]}
        with patch.object(a, 'stamp', return_value=observed):
            a.ingest(self.db, identity, payload)

    def build(self, start='2026-10-30', end='2026-10-31', now='2026-11-02T12:00:00+00:00'):
        accounts = [dict(r) for r in self.db.execute('SELECT a.*,p.name partner FROM aff_accounts a JOIN aff_partners p ON p.id=a.partner_id')]
        return overview.build(self.db, accounts, start, end, datetime.fromisoformat(now))

    def test_unknown_without_snapshot_and_empty_history_are_not_zero(self):
        self.assertIsNone(self.build()['total_cents'])
        self.ingest([])
        self.assertIsNone(self.build()['total_cents'])
        self.assertEqual(self.build()['included_partners'], 0)

    def test_approved_only_zero_and_reconciliation(self):
        self.ingest([('2026-10-29', 100, 'approved'), ('2026-10-31', 400, 'approved'), ('2026-10-31', 900, 'not_approved')])
        result = self.build()
        self.assertEqual([d['cents'] for d in result['daily']], [0, 400])
        self.assertEqual(result['total_cents'], 400)
        self.assertFalse(result['partial'])
        self.assertEqual(sum(p['cents'] for p in result['partners']), result['total_cents'])
        for day in result['daily']:
            self.assertEqual(sum(p['cents'] for p in day['parts']), day['cents'])

    def test_reimports_late_corrections_disappearance_and_negative(self):
        rows = [('2026-10-30', 500, 'approved'), ('2026-10-31', 200, 'approved')]
        self.ingest(rows); self.ingest(rows)
        self.assertEqual(self.build()['total_cents'], 700)
        self.ingest([('2026-10-30', -120, 'approved')])
        self.assertEqual(self.build()['total_cents'], -120)
        self.assertEqual(self.build()['daily'][1]['cents'], 0)

    def test_before_first_sale_after_snapshot_and_today_unknown(self):
        self.ingest([('2026-10-30', 200, 'approved')], '2026-10-31T10:00:00Z')
        result = self.build('2026-10-29', '2026-11-02')
        self.assertEqual([d['cents'] for d in result['daily']], [None, 200, None, None, None])
        self.assertEqual(result['daily'][1]['status'], 'complete')
        self.assertTrue(result['daily'][-1]['provisional'])
        self.assertTrue(result['accounts'][0]['stale'])
        self.assertIsNone(result['comparisons']['previous']['percent'])

    def test_paris_day_at_utc_midnight_and_dst(self):
        self.ingest([('2026-10-24', 100, 'approved'), ('2026-10-25', 250, 'approved')], '2026-10-25T23:30:00Z')
        result = self.build('2026-10-24', '2026-10-26', '2026-10-25T23:45:00+00:00')
        self.assertEqual(result['today'], '2026-10-26')
        self.assertEqual([d['day'] for d in result['daily']], ['2026-10-24','2026-10-25','2026-10-26'])
        self.assertEqual(result['daily'][1]['status'], 'complete')
        self.assertTrue(result['daily'][2]['provisional'])

    def test_previous_adjacent_equal_length_and_calendar_year(self):
        self.ingest([('2025-10-30', 100, 'approved'), ('2025-10-31', 100, 'approved'),
                     ('2026-10-28', 100, 'approved'), ('2026-10-29', 100, 'approved'),
                     ('2026-10-30', 150, 'approved'), ('2026-10-31', 250, 'approved')])
        result = self.build()
        self.assertEqual(result['comparisons']['previous']['percent'], 100)
        self.assertEqual(result['comparisons']['year']['percent'], 100)
        self.assertEqual(result['comparisons']['previous']['start'], '2026-10-28')
        self.assertEqual(result['comparisons']['year']['end'], '2025-10-31')

    def test_zero_negative_or_missing_base_does_not_produce_percentage(self):
        self.ingest([('2026-10-27', 10, 'approved'), ('2026-10-30', 100, 'approved')])
        self.assertIsNone(self.build()['comparisons']['previous']['percent'])
        self.assertIn('nulle', self.build()['comparisons']['previous']['reason'])
        self.ingest([('2026-10-28', -10, 'approved'), ('2026-10-30', 100, 'approved')])
        self.assertIsNone(self.build()['comparisons']['previous']['percent'])
        self.assertIsNone(self.build()['comparisons']['year']['percent'])

    def test_new_account_does_not_create_artificial_growth(self):
        self.ingest([('2025-01-01', 100, 'approved'), ('2026-10-28', 100, 'approved'), ('2026-10-30', 200, 'approved')])
        second = a.add_account(self.db, {'partner':'Second', 'label':'Other', 'platform':'domadoo'})['id']
        self.ingest([('2026-10-30', 500, 'approved')], identity=second)
        result = self.build()
        self.assertEqual(result['total_cents'], 700)
        self.assertEqual(result['included_partners'], 2)
        self.assertIsNone(result['comparisons']['previous']['percent'])
        self.assertFalse(result['comparisons']['previous']['available'])

    def test_partner_without_data_partial_and_multiple_accounts_grouped(self):
        self.ingest([('2026-10-30', 200, 'approved')])
        second = a.add_account(self.db, {'partner':'Domadoo', 'label':'Second', 'platform':'domadoo'})['id']
        self.assertTrue(self.build()['partial'])
        self.ingest([('2026-10-30', 300, 'approved')], identity=second)
        result = self.build()
        self.assertEqual(len(result['partners']), 1)
        self.assertEqual(result['partners'][0]['cents'], 500)

    def test_foreign_currency_excluded_without_zero_imputation(self):
        self.ingest([('2026-10-30', 100, 'approved')])
        self.db.execute("UPDATE aff_transactions SET currency='USD'")
        result = self.build()
        self.assertIsNone(result['daily'][0]['cents'])
        self.assertEqual(result['daily'][0]['parts'][0]['status'], 'partial')
        self.assertTrue(result['partial'])

    def test_amazon_reports_and_views_never_added_to_approved_total(self):
        self.ingest([('2026-10-30', 100, 'approved')])
        identity = a.add_account(self.db, {'partner':'Amazon', 'label':'France', 'platform':'amazon'})['id']
        payload = {'csv':'Date,Commission\n2026-10-30,99.00\n', 'kind':'earnings', 'view':'category',
                   'mapping':{'date':'Date','commission_cents':'Commission'}, 'start':'2026-10-30', 'end':'2026-10-30',
                   'scope':'all', 'decimal':'dot', 'confirmed':True}
        amazon.ingest(self.db, identity, payload, '2026-11-02T10:00:00Z')
        amazon.ingest(self.db, identity, {**payload, 'view':'tracking_id', 'contribution':'detail'}, '2026-11-02T10:00:00Z')
        result = self.build()
        self.assertEqual(result['total_cents'], 100)
        self.assertEqual(result['included_partners'], 1)
        self.assertTrue(result['partial'])
        self.assertIsNone(result['partners'][1]['cents'])
        self.assertEqual(amazon.report(self.db, identity)['totals']['commission_cents'], 9900)

    def test_february_29_is_a_gap_and_reverse_leap_window_not_equal(self):
        self.ingest([('2023-02-28', 100, 'approved'), ('2024-02-29', 200, 'approved')])
        result = self.build('2024-02-28', '2024-03-01')
        self.assertIsNone(result['comparisons']['year']['daily'][1]['day'])
        self.assertIsNone(result['comparisons']['year']['percent'])
        self.assertIsNone(self.build('2025-02-28', '2025-03-01')['comparisons']['year']['percent'])

    def test_all_history_and_bounded_daily_range(self):
        self.ingest([('2026-10-30', 100, 'approved')])
        self.assertEqual(self.build('', '')['start'], '2026-10-30')
        with self.assertRaises(ValueError): self.build('2000-01-01', '2026-10-31')

    def test_existing_account_view_does_not_receive_global_contract(self):
        self.ingest([('2026-10-30', 100, 'approved')])
        self.assertNotIn('overview', a.report(self.db, {'account':'domadoo'}))
        result = a.report(self.db, {'start':'2026-10-30','end':'2026-10-31'})
        self.assertEqual(result['overview']['total_cents'], 100)
        self.assertEqual(result['aggregate'][0]['cents'], 100)


if __name__ == '__main__': unittest.main()
