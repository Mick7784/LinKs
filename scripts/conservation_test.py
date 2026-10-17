"""Conservation contracts: copies only, never a production volume."""
import copy,json,unittest
from pathlib import Path
import analytics_test

class ConservationTests(unittest.TestCase):
    setUp=analytics_test.AnalyticsTests.setUp
    tearDown=analytics_test.AnalyticsTests.tearDown
    server=analytics_test.AnalyticsTests.server
    request=analytics_test.AnalyticsTests.request
    redirect=analytics_test.AnalyticsTests.redirect
    promo=analytics_test.AnalyticsTests.promo

    def counts(self):
        with self.a.connection() as db:
            return {(r['day'],r['source'],r['kind'],r['link']):r['total'] for r in db.execute('SELECT * FROM counts')}

    def test_retire_keeps_content_metrics_and_all_published_destinations(self):
        admin=self.server(True);public=self.server();ident=self.promo()
        long=self.a.story_link(ident)['url'].rsplit('/',1)[-1]
        short=self.a.story_link(ident,'youtube')['code']
        for kind in ['click','impression']:self.a.record(kind,'youtube','block:'+ident)
        self.a.record_promo_copy({'link':'block:'+ident,'code':'OLD','source':'youtube'})
        self.redirect(public+'/'+short);before=self.counts()
        self.assertEqual(self.request(admin+'/api/content/'+ident,method='DELETE')[0],204)
        self.assertEqual(self.counts(),before)
        self.assertNotIn(ident,{r['id'] for r in self.a.public_config()['links']})
        self.assertIn(ident,{r['id'] for r in self.a.content_list(True)})
        self.assertEqual(self.redirect(public+'/go/'+long,method='HEAD')[0],302)
        self.assertEqual(self.redirect(public+'/'+short,method='HEAD')[0],302)
        self.assertEqual(self.request(admin+'/api/content/'+ident+'/restore',{})[0],204)
        self.a.record('click','youtube','button:legacy-button-0');before=self.counts()
        self.assertEqual(self.request(admin+'/api/buttons/legacy-button-0',method='DELETE')[0],204)
        self.assertEqual(self.counts(),before)
        self.assertNotIn('legacy-button-0',{r['id'] for r in self.a.button_list()})
        self.assertIn('legacy-button-0',{r['id'] for r in self.a.button_list(True)})

    def test_old_restore_is_conservative_idempotent_and_keeps_new_campaign(self):
        admin=self.server(True);public=self.server()
        self.a.record('view','youtube','')
        old=json.loads(self.a.export_backup());unchanged=copy.deepcopy(old)
        ident=self.promo();short=self.a.story_link(ident,'youtube')['code']
        self.a.record('view','youtube','')
        self.a.record('click','youtube','block:'+ident)
        self.a.record('impression','youtube','block:'+ident)
        self.a.record_promo_copy({'link':'block:'+ident,'code':'NEW','source':'youtube'})
        self.redirect(public+'/'+short)
        before=self.counts()
        self.a.restore_backup(old)
        self.assertEqual(old,unchanged,'Restore must not mutate a reusable backup')
        self.assertEqual(self.counts(),before)
        self.assertEqual(self.redirect(public+'/'+short,method='HEAD')[0],302)
        self.a.restore_backup(old);self.assertEqual(self.counts(),before)
        with self.a.connection() as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(list(db.execute('PRAGMA foreign_key_check')),[])
        self.assertEqual(len(list((self.a.DATA_DIR/'restore-safety').glob('*/analytics.db'))),2)

    def test_restore_never_rolls_back_a_published_destination(self):
        ident=self.promo();short=self.a.story_link(ident,'youtube')['code'];public=self.server()
        old=json.loads(self.a.export_backup())
        with self.a.connection() as db:db.execute('UPDATE content_blocks SET url=? WHERE id=?',('https://partner.example/new',ident))
        self.a.restore_backup(old)
        self.assertEqual(self.redirect(public+'/'+short,method='HEAD')[1]['Location'],'https://partner.example/new')

    def test_retained_upload_after_old_restore_and_archive_survives_cleanup(self):
        from images_test import raster
        import uuid
        old=json.loads(self.a.export_backup());ref='/uploads/'+str(uuid.uuid4())+'.png'
        (self.a.UPLOADS/ref[9:]).write_bytes(raster())
        with self.a.connection() as db:
            ident=self.a.save_content(db,self.a.block_data({'type':'promo','title':'Image','internal_name':'Image','url':'https://example.net','image':ref}))
        admin=self.server(True)
        self.assertEqual(self.request(admin+'/api/content/'+ident+'/archive',{})[0],204)
        self.a.restore_backup(old);self.a.storage_state('empty');self.a.init()
        row=next(x for x in self.a.content_list(True) if x['id']==ident)
        self.assertEqual(row['image'],ref);self.assertTrue((self.a.UPLOADS/ref[9:]).is_file())

    def test_legacy_backup_without_additive_columns_restores(self):
        old=json.loads(self.a.export_backup());old['tables'].pop('tracking_source_keys')
        for table in ['content_blocks','top_buttons']:
            for row in old['tables'][table]:row.pop('retired')
        self.a.restore_backup(old);self.a.init()
        self.assertEqual(len(self.a.content_list()),5)

if __name__=='__main__':unittest.main()
