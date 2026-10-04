import base64, importlib.util, json, os, tempfile, threading, unittest, uuid
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from fixtures import prepare,populate
from images_test import raster
import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'ANALYTICS_DB':str(self.root/'db.sqlite'),'UPLOAD_DIR':str(self.root/'uploads'),'APP_RELEASE_VERSION':'','APP_RELEASE_ID':''});self.env.start()
        prepare(os.environ['ANALYTICS_DB'])
        spec=importlib.util.spec_from_file_location('storage_api',Path(__file__).with_name('analytics.py'));self.a=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.a);self.a.init();populate(self.a)
        self.server=self.a.serve(0,True,'127.0.0.1');threading.Thread(target=self.server.serve_forever,daemon=True).start();self.url='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.env.stop();self.tmp.cleanup()
    def request(self,path,data=None):
        try:
            with urlopen(Request(self.url+path,json.dumps(data).encode() if data is not None else None,{'Content-Type':'application/json','X-Links-Request':'1'})) as response:return response.status,response.read()
        except HTTPError as exc:return exc.code,exc.read()
    def file(self):
        ref='/uploads/'+str(uuid.uuid4())+'.png';(self.a.UPLOADS/ref[9:]).write_bytes(raster());return ref
    def scan(self,now=100,action='scan'):
        with self.a.connection() as db:return storage.scan(db,self.a.UPLOADS,action,now)
    def test_grace_reuse_and_new_orphan_period(self):
        ref=self.file();self.assertEqual(self.scan()['unused'],1)
        self.scan(now=100+storage.GRACE_SECONDS-1);self.assertTrue((self.a.UPLOADS/ref[9:]).exists())
        with self.a.connection() as db:
            row=dict(db.execute("SELECT * FROM content_blocks WHERE id='legacy-link-0'").fetchone())
            self.a.save_content(db,self.a.block_data({**row,'image':ref}),'legacy-link-0')
        with self.a.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM upload_trash').fetchone()[0],0)
        self.assertEqual(self.scan(now=100+storage.GRACE_SECONDS+1)['used'],1)
        with self.a.connection() as db:db.execute("UPDATE content_blocks SET image='' WHERE id='legacy-link-0'")
        start=200+storage.GRACE_SECONDS;self.scan(now=start)
        self.assertTrue((self.a.UPLOADS/ref[9:]).exists());self.scan(now=start+storage.GRACE_SECONDS)
        self.assertFalse((self.a.UPLOADS/ref[9:]).exists())
    def test_shared_inactive_archived_profile_shortcut_and_theme_references(self):
        refs=[self.file() for _ in range(5)]
        with self.a.connection() as db:
            db.execute("UPDATE content_blocks SET image=?,active=0 WHERE id='legacy-link-0'",(refs[0],))
            db.execute("UPDATE content_blocks SET image=?,archived=1 WHERE id='legacy-link-1'",(refs[1],))
            db.execute("UPDATE settings SET value=? WHERE key='profile.avatar'",(refs[2],))
            db.execute("UPDATE top_buttons SET custom_icon=?,active=0 WHERE id='legacy-button-0'",(refs[3],))
        with self.a.connection() as db:
            self.a.themes.save(db,{'theme':{'id':str(uuid.uuid4()),'name':'Inactive','tokens':{'--links-page-image':refs[4]}}},self.a.UPLOADS)
        orphan=self.file();system=self.a.UPLOADS/'system.webp';system.write_bytes(b'never managed')
        result=self.scan(action='empty');self.assertEqual(result['used'],5);self.assertEqual(result['deleted'],1)
        self.assertFalse((self.a.UPLOADS/orphan[9:]).exists());self.assertTrue(system.exists())
        for ref in refs:self.assertTrue((self.a.UPLOADS/ref[9:]).exists())
    def test_archive_preserves_statistics_and_shared_file(self):
        ref=self.file();self.a.record('click','youtube','block:legacy-link-0')
        with self.a.connection() as db:
            item={'type':'promo','internal_name':'Archive test','title':'Offer','url':'https://example.com','image':ref,'promo_code':'SAVE10'}
            key=self.a.save_content(db,self.a.block_data(item));db.execute("UPDATE content_blocks SET image=? WHERE id='legacy-link-0'",(ref,))
        self.a.record('click','instagram','block:'+key);self.a.record('impression','youtube','block:'+key)
        self.a.record_promo_copy({'link':'block:'+key,'code':'SAVE10','source':'instagram'})
        story=self.a.story_link(key)
        with self.a.connection() as db:before=[dict(r) for r in db.execute('SELECT * FROM counts')]
        self.assertEqual(self.request('/api/content/'+key+'/archive',{})[0],204)
        row=next(x for x in self.a.content_list(True) if x['id']==key)
        self.assertEqual(row['image'],'');self.assertEqual(row['promo_code'],'SAVE10');self.assertEqual(row['clicks'],1)
        self.assertEqual(self.a.story_link(key),story)
        with self.a.connection() as db:self.assertEqual(before,[dict(r) for r in db.execute('SELECT * FROM counts')])
        self.scan(action='empty');self.assertTrue((self.a.UPLOADS/ref[9:]).exists())
    def test_old_backup_version_images_and_atomic_invalid_restore(self):
        ref=self.file()
        with self.a.connection() as db:db.execute("UPDATE content_blocks SET image=? WHERE id='legacy-link-0'",(ref,))
        backup=json.loads(self.a.export_backup())
        for row in backup['tables']['settings']:
            if row['key']=='app.version':row['value']='V1.3'
            if row['key']=='app.release_id':row['value']='bundled:V1.3'
        self.a.restore_backup(backup)
        with self.a.connection() as db:self.assertEqual(self.a.instance.get(db,'app.version'),self.a.software_version())
        self.assertEqual(self.a.public_config()['profile']['app_version'],self.a.software_version())
        invalid=json.loads(self.a.export_backup());name=next(iter(invalid['images']));invalid['images'][name]=base64.b64encode(b'\x89PNG\r\n\x1a\n').decode()
        before=self.a.content_list()
        with self.assertRaises(ValueError):self.a.restore_backup(invalid)
        self.assertEqual(before,self.a.content_list())
    def test_health_and_http_boundaries(self):
        self.assertEqual(self.request('/healthz')[0],200)
        with self.a.connection() as db:db.execute('ALTER TABLE counts RENAME TO broken_counts')
        self.assertEqual(self.request('/healthz')[0],503)
        with self.a.connection() as db:db.execute('ALTER TABLE broken_counts RENAME TO counts')
        self.assertEqual(self.request('/api/app-version',{'app_version':'V1.3'})[0],404)
        for purpose in ['', 'icon']:
            self.assertEqual(self.request('/api/upload',{'type':'image/png','data':base64.b64encode(b'\x89PNG\r\n\x1a\n').decode(),'purpose':purpose})[0],400)
        self.assertEqual(self.request('/api/upload',{'type':'image/png','data':base64.b64encode(raster()).decode()})[0],201)
        self.assertEqual(self.request('/api/storage')[0],200)
        self.assertEqual(self.request('/api/storage',{'action':'empty'})[0],200)
        self.assertEqual(self.request('/api/storage',{'action':'invalid'})[0],400)
    def test_external_image_policy_preserves_backup_compatibility(self):
        item={'internal_name':'Test','title':'Test','url':'https://example.com','image':'https://elsewhere.example/a.png'}
        with self.assertRaises(ValueError):self.a.block_data(item)
        self.assertEqual(self.a.block_data(item,allow_legacy_image=True)['image'],item['image'])
        item['image']='https://i.ytimg.com/vi/test/default.jpg';self.a.block_data(item)

if __name__=='__main__':unittest.main()
