"""Conservation contracts: copies only, never a production volume."""
import copy,json,unittest,sqlite3,os,hashlib,shutil,importlib.util
from contextlib import closing
from unittest.mock import patch
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

    def test_renaming_legacy_source_preserves_cumulative_identity_and_alias(self):
        admin=self.server(True);public=self.server();ident=self.promo()
        short=self.a.story_link(ident,'youtube')['code']
        with self.a.connection() as db:
            source=next(r for r in self.a.tracked_links.source_rows(db) if r['name']=='YouTube Post')
        self.assertEqual(self.request(admin+'/api/tracking-sources/'+source['id'],{'name':'Chaîne renommée'},method='PUT')[0],200)
        for _ in range(2):self.assertEqual(self.redirect(public+'/'+short)[0],302)
        with self.a.connection() as db:
            current=next(r for r in self.a.tracked_links.source_rows(db) if r['id']==source['id'])
            self.assertEqual(current['clicks'],2)
        self.assertEqual(json.loads(self.request(admin+'/api/tracking-sources/'+source['id'],method='DELETE')[1])['action'],'archived')
        old=json.loads(self.a.export_backup());self.a.restore_backup(old);self.a.init()
        self.assertEqual(self.redirect(public+'/'+short,method='HEAD')[0],302)

    def test_privacy_headers_skip_every_collection_route_without_blocking_navigation(self):
        public=self.server();ident=self.promo();story=self.a.story_link(ident)['url'].rsplit('/',1)[-1]
        code=self.a.story_link(ident,'youtube')['code']
        with self.a.connection() as db:
            source=self.a.tracked_links.source_rows(db)[0]['id']
            tracked=self.a.tracked_links.create_link(db,{'name':'Private','url':'https://example.net'},self.a.story_url_valid,self.a.now_iso())
            token=self.a.tracked_links.token_link(db,tracked['id'],source,self.a.ORIGIN,self.a.now_iso())
        before=self.counts()
        for headers in [{'DNT':'1'},{'Sec-GPC':'1'}]:
            for path in ['/go/'+story,'/'+code,'/go/'+token['token'],'/'+token['code']]:
                self.assertEqual(self.redirect(public+path,headers=headers)[0],302)
            self.assertEqual(self.request(public+'/metrics',{'kind':'view'},{'Origin':self.a.ORIGIN,**headers})[0],204)
        self.assertEqual(self.counts(),before)

    def test_safe_historical_svg_roundtrip_rejects_active_content(self):
        assets=self.a.DATA_DIR/'assets';assets.mkdir(exist_ok=True)
        safe=b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h1v1Z"/></svg>'
        (assets/'legacy.svg').write_bytes(safe)
        backup=json.loads(self.a.export_backup());self.a.restore_backup(backup)
        self.assertEqual((assets/'legacy.svg').read_bytes(),safe)
        import base64
        for unsafe in [b'<svg onload="alert(1)"/>',b'<svg><script/></svg>',b'<svg><image href="https://example.org"/></svg>',b'<!DOCTYPE svg><svg/>']:
            bad=copy.deepcopy(backup);bad['assets']['legacy.svg']=base64.b64encode(unsafe).decode()
            before=self.counts()
            with self.assertRaises(ValueError):self.a.restore_backup(bad)
            self.assertEqual(self.counts(),before)

    def test_collecting_today_never_purges_historical_counters(self):
        self.a.record('click','youtube','block:legacy-link-0','2001-01-01')
        before=self.counts();self.a.record('view','youtube','')
        for key,total in before.items():self.assertEqual(self.counts()[key],total)

    def test_preview_is_read_only_and_foreign_history_is_refused(self):
        old=json.loads(self.a.export_backup());self.a.record('view','youtube','')
        before=self.counts();files=set(self.a.DATA_DIR.rglob('*'))
        result=self.a.restore_backup(old,preview=True)
        self.assertEqual(result['counter_total'],sum(before.values()))
        self.assertEqual(self.counts(),before);self.assertEqual(set(self.a.DATA_DIR.rglob('*')),files)
        old['instance_id']='a'*32
        with self.assertRaisesRegex(ValueError,'autre instance'):self.a.restore_backup(old)
        self.assertEqual(self.counts(),before)

    def test_additive_migration_on_a_copy_preserves_original_volume(self):
        ident=self.promo();short=self.a.story_link(ident,'youtube')['code']
        self.a.record('view','youtube','');self.a.record('click','youtube','block:'+ident)
        source=self.a.DATA_DIR/'old-volume';source.mkdir()
        with self.a.connection() as db,closing(sqlite3.connect(source/'analytics.db')) as saved:db.backup(saved)
        with closing(sqlite3.connect(source/'analytics.db')) as db,db:
            db.execute('DROP TABLE tracking_source_keys')
            for table in ['content_blocks','top_buttons']:db.execute('ALTER TABLE '+table+' DROP COLUMN retired')
        original=hashlib.sha256((source/'analytics.db').read_bytes()).hexdigest()
        copied=self.a.DATA_DIR/'volume-copy';shutil.copytree(source,copied)
        tables=['content_blocks','top_buttons','counts','story_links','tracking_sources','tracked_links','tracked_tokens','short_aliases']
        with closing(sqlite3.connect(source/'analytics.db')) as db:
            db.row_factory=sqlite3.Row;before={t:[dict(r) for r in db.execute('SELECT * FROM '+t)] for t in tables}
        with patch.dict(os.environ,{'ANALYTICS_DB':str(copied/'analytics.db'),'UPLOAD_DIR':str(copied/'uploads')}):
            spec=importlib.util.spec_from_file_location('migration_copy',Path(__file__).with_name('analytics.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            module.init();module.init()
            with module.connection() as db:
                for table in tables:
                    after=[{k:r[k] for k in row} for row,r in zip(before[table],db.execute('SELECT * FROM '+table))]
                    self.assertEqual(before[table],after,table)
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],len(before[table]))
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(list(db.execute('PRAGMA foreign_key_check')),[])
                self.assertEqual(db.execute('SELECT code FROM short_aliases').fetchone()[0],short)
        self.assertTrue((copied/'pre-v1310-database.db').is_file())
        self.assertEqual(hashlib.sha256((source/'analytics.db').read_bytes()).hexdigest(),original)

if __name__=='__main__':unittest.main()
