import unittest
import amazon_affiliation as a

class RealFormatTests(unittest.TestCase):
    def data(self):
        return dict(csv='Date,Montant,Montant,Articles\n10-31-2026,19.559999999999995,250.0,-\n',kind='earnings',view='linked_product',mapping={'date':'Date','commission_cents':'Montant [colonne 2]','shipped_items':'Articles'},start='2026-10-31',end='2026-10-31',scope='all',decimal='dot',date_format='mdy')
    def test_duplicate_columns_missing_quantity_and_float_noise(self):
        r=a.normalize(self.data())['rows'][0]
        self.assertEqual(r['commission_cents'],1956)
        self.assertIsNone(r['shipped_items'])
        self.assertEqual(r['date'],'2026-10-31')
    def test_real_fractional_cent_is_rejected(self):
        d=self.data();d['csv']=d['csv'].replace('19.559999999999995','1.234')
        with self.assertRaises(ValueError):a.normalize(d)
    def test_missing_date_requires_explicit_single_day(self):
        d=self.data();del d['mapping']['date']
        with self.assertRaises(ValueError):a.normalize(d)
        d['single_day']=True
        self.assertEqual(a.normalize(d)['date_basis'],'confirmed_single_day')
        d['start']='2026-10-30'
        with self.assertRaises(ValueError):a.normalize(d)
    def test_date_format_is_not_silently_guessed(self):
        d=self.data();del d['date_format']
        with self.assertRaises(ValueError):a.normalize(d)

if __name__=='__main__':unittest.main()
