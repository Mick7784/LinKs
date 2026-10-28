"""Public organisation uses disposable SQLite fixtures only."""
import copy,json,unittest
from unittest.mock import patch
import analytics_test

class PageLayoutTests(unittest.TestCase):
    setUp=analytics_test.AnalyticsTests.setUp
    tearDown=analytics_test.AnalyticsTests.tearDown
    server=analytics_test.AnalyticsTests.server
    request=analytics_test.AnalyticsTests.request

    def layout(self):
        with self.a.connection() as db:return self.a.page_layout(db)

    def rows(self,table):
        with self.a.connection() as db:return [dict(r) for r in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]

    def test_legacy_public_order_is_unchanged_until_save(self):
        with self.a.connection() as db:db.execute("UPDATE content_blocks SET priority='high' WHERE id='legacy-link-4'")
        before=self.a.public_config()
        self.assertEqual(before['section_order'],['video','highlight','classic'])
        self.assertEqual(before['links'][0]['id'],'legacy-link-4')
        self.assertEqual(self.layout()['link_ids'],[x['id'] for x in before['links']])
        draft=self.layout();draft['section_order'].reverse();draft['link_ids'].reverse()
        self.assertEqual(before,self.a.public_config())

    def test_save_is_atomic_and_survives_restart_with_history_intact(self):
        campaign=analytics_test.AnalyticsTests.promo(self)
        alias=self.a.story_link(campaign,'youtube')
        self.a.record('click','youtube','block:legacy-link-0')
        before=self.rows('content_blocks');counts=self.rows('counts');layout=self.layout()
        layout['section_order']=['classic','highlight','video'];layout['link_ids'].reverse()
        saved=self.a.save_page_layout(layout);self.a.init()
        self.assertEqual(self.layout(),saved)
        public=self.a.public_config();self.assertEqual(public['section_order'],layout['section_order'])
        self.assertEqual([x['id'] for x in public['links'] if x['type']=='classic'],layout['link_ids'])
        self.assertEqual(self.a.story_link(campaign,'youtube'),alias)
        self.assertEqual(self.rows('counts'),counts)
        after=self.rows('content_blocks')
        for original,current in zip(before,after):
            if original['type']=='classic':original['position']=current['position']
            self.assertEqual(original,current)
        self.assertEqual([x['id'] for x in self.a.content_list() if x['type']=='classic'],layout['link_ids'])
        self.assertEqual(self.a.public_config(snapshot=True)['section_order'],layout['section_order'])

    def test_invalid_or_partial_layout_cannot_publish_either_order(self):
        initial=self.layout();before=self.rows('content_blocks')
        variants=[{'section_order':['classic']},{'section_order':['classic','classic','video']},{'section_order':'classic'}, {'link_ids':initial['link_ids'][:-1]},{'link_ids':initial['link_ids']+['unknown']},{'link_ids':initial['link_ids']*2},{'link_ids':[{}]},{'revision':'stale'}]
        for mutation in variants:
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.a.save_page_layout({**initial,**mutation})
            self.assertEqual(self.layout(),initial);self.assertEqual(self.rows('content_blocks'),before)

    def test_concurrent_creation_or_reordering_requires_reload(self):
        stale=self.layout()
        with self.a.connection() as db:self.a.save_content(db,self.a.block_data({'type':'classic','title':'New','internal_name':'New','url':'https://example.com/new'}))
        with self.assertRaises(ValueError):self.a.save_page_layout(stale)
        stale=self.layout()
        with self.a.connection() as db:db.execute("UPDATE content_blocks SET position=-1 WHERE id='legacy-link-4'")
        with self.assertRaises(ValueError):self.a.save_page_layout(stale)

    def test_transaction_rolls_back_both_orders_on_failure(self):
        initial=self.layout();draft=copy.deepcopy(initial);draft['section_order'].reverse();draft['link_ids'].reverse();before=self.rows('content_blocks')
        with patch.object(self.a,'page_layout',side_effect=[initial,OSError('test failure')]):
            with self.assertRaises(OSError):self.a.save_page_layout(draft)
        self.assertEqual(self.layout(),initial);self.assertEqual(self.rows('content_blocks'),before)

    def test_disabled_links_are_preserved_and_empty_library_is_valid(self):
        with self.a.connection() as db:db.execute("UPDATE content_blocks SET active=0 WHERE id='legacy-link-2'")
        layout=self.layout();self.assertIn('legacy-link-2',layout['link_ids']);layout['link_ids'].reverse();self.a.save_page_layout(layout)
        self.assertNotIn('legacy-link-2',[x['id'] for x in self.a.public_config()['links']])
        with self.a.connection() as db:db.execute('UPDATE content_blocks SET archived=1')
        self.a.save_page_layout(self.layout());self.assertEqual(self.layout()['link_ids'],[])

    def test_api_and_backup_restore_preserve_organisation(self):
        admin=self.server(True);status,body=self.request(admin+'/api/page-layout');self.assertEqual(status,200)
        layout=json.loads(body);layout['section_order'].reverse()
        self.assertEqual(self.request(admin+'/api/page-layout',layout)[0],200)
        backup=json.loads(self.a.export_backup());saved=self.layout()
        self.a.save_page_layout({**saved,'section_order':['video','highlight','classic']})
        self.a.restore_backup(backup)
        self.assertEqual(self.layout(),saved)
        self.assertEqual(self.request(self.server()+'/api/page-layout')[0],404)

if __name__=='__main__':unittest.main()
