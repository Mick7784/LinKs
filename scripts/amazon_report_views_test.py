import base64
import io
import sqlite3
import unittest
import zipfile
import affiliation as a
import amazon_affiliation as amazon
from amazon_affiliation_test import payload


def archive(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for name,value in files:z.writestr(name,value)
    return {'archive':base64.b64encode(stream.getvalue()).decode()}


class ReportViewsTests(unittest.TestCase):
    def test_archive_selects_text_without_importing(self):
        result=amazon.inspect_archive(archive([('Category.csv',payload()['csv']),('Daily.txt','Date\tClicks\n31/10/2026\t4')]))
        self.assertFalse(result['imported'])
        self.assertEqual(len(result['files']),2)
        self.assertIn('Clicks',result['files'][1]['csv'])

    def test_archive_rejects_unsafe_or_oversized_content(self):
        for files in [[('../escape.csv','x')],[('nested.zip','x')],[('huge.csv','x'*(amazon.LIMIT+1))],[('bad.txt',b'\xff')],[('same.csv','a'),('same.csv','b')]]:
            with self.subTest(files=[name for name,_ in files]):
                with self.assertRaises(ValueError):amazon.inspect_archive(archive(files))

    def test_alternative_views_do_not_replace_or_double_count(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row;a.initialize(db)
        identity=a.add_account(db,{'partner':'Amazon','label':'FR','platform':'amazon'})['id']
        try:
            first={**payload(),'view':'category'}
            amazon.ingest(db,identity,first,'2026-11-01T12:00:00Z')
            for view in ['linked_product','tracking_id','daily_trends','legacy']:
                with self.assertRaises(ValueError):amazon.ingest(db,identity,{**payload(),'view':view},'2026-11-01T13:00:00Z')
            self.assertEqual(amazon.report(db,identity)['totals']['commission_cents'],1234)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM aff_snapshots').fetchone()[0],1)
            self.assertTrue(amazon.ingest(db,identity,first,'2026-11-01T14:00:00Z')['duplicate'])
            target=sqlite3.connect(':memory:');target.row_factory=sqlite3.Row
            try:
                a.restore_backup(target,a.export_backup(db))
                self.assertEqual(amazon.report(target,identity),amazon.report(db,identity))
            finally:target.close()
        finally:db.close()

    def test_daily_trends_date_mapping_is_explicit(self):
        value=amazon.normalize({**payload(),'view':'daily_trends'})
        self.assertEqual(value['rows'][0]['date'],'2026-11-01')
        self.assertEqual(value['view'],'daily_trends')
        self.assertNotIn('view',amazon.normalize(payload()))


if __name__=='__main__':unittest.main()
