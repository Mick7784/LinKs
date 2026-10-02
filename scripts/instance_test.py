import base64, contextlib, importlib.util, io, json, os, sqlite3, tempfile, threading, unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

class InstanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,{'ANALYTICS_DB':str(self.root/'analytics.db'),'UPLOAD_DIR':str(self.root/'uploads'),'ANALYTICS_ORIGIN':'','APP_RELEASE_VERSION':'','APP_RELEASE_ID':''});self.env.start()
        spec=importlib.util.spec_from_file_location('isolated_analytics',Path(__file__).with_name('analytics.py'));self.a=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.a)
        with contextlib.redirect_stdout(io.StringIO()):self.a.init()
        self.servers=[];self.cookie=''
    def tearDown(self):
        for s in self.servers:s.shutdown();s.server_close()
        self.env.stop();self.temp.cleanup()
    def server(self,admin=True):
        s=self.a.serve(0,admin,'127.0.0.1');s.daemon_threads=False;self.servers.append(s);threading.Thread(target=s.serve_forever,daemon=True).start();return 'http://127.0.0.1:'+str(s.server_port)
    def request(self,url,data=None,method=None,headers=None):
        h={'X-Links-Request':'1','Cookie':self.cookie,**(headers or {})}
        try:r=urlopen(Request(url,json.dumps(data).encode() if data is not None else None,h,method=method))
        except HTTPError as e:r=e
        with r:
            body=r.read();cookie=r.headers.get('Set-Cookie')
            if cookie:self.cookie=cookie.split(';')[0]
            try:result=json.loads(body)
            except ValueError:result=body
            return r.status,result,dict(r.headers)
    def setup(self,origin,**changes):
        data={'bootstrap':changes.get('bootstrap') or ((self.root/'setup-code').read_text().strip() if (self.root/'setup-code').exists() else ''),'username':'admin','password':'A-long-test-password','confirmation':'A-long-test-password','name':'Example Creator','description':'','footer_owner':'Example Creator','site_url':origin,'timezone':'Europe/Paris','analytics_enabled':True,'link_title':'Premier lien','link_url':'https://example.com'}
        data.update(changes);return self.request(origin+'/api/setup',data)
    def csrf(self,origin):return self.request(origin+'/api/auth/status')[1]['csrf']
    def test_fresh_setup_is_atomic_neutral_and_bootstrap_once(self):
        admin=self.server();public=self.server(False)
        config=self.a.public_config();self.assertFalse(config['setup_completed']);self.assertEqual(config['links'],[]);self.assertEqual(config['socials'],[]);self.assertEqual(config['profile']['logo'],'');self.assertEqual(config['profile']['footer_quote'],'')
        self.assertEqual(self.request(admin+'/api/content')[0],403)
        code=(self.root/'setup-code').read_text().strip()
        self.assertEqual(self.setup(admin,bootstrap='wrong')[0],400)
        self.assertEqual(self.setup(admin,link_url='javascript:alert(1)')[0],400)
        with self.a.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM admin_accounts').fetchone()[0],0)
        self.assertFalse(self.a.public_config()['setup_completed']);self.assertTrue((self.root/'setup-code').exists())
        status,body,headers=self.setup(admin);self.assertEqual(status,200,body);self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie']);self.assertNotIn('Secure',headers['Set-Cookie'])
        self.assertEqual(self.request(admin+'/api/content')[0],200);self.assertEqual(len(self.a.public_config()['links']),1)
        self.assertFalse((self.root/'setup-code').exists());self.assertEqual(self.setup(admin,bootstrap=code)[0],400)
        with self.a.connection() as db:
            row=db.execute('SELECT password_hash FROM admin_accounts').fetchone();self.assertNotIn('A-long-test-password',row[0]);self.assertTrue(self.a.instance.password_ok('A-long-test-password',row[0]));self.assertEqual(db.execute('SELECT COUNT(*) FROM auth_state').fetchone()[0],0)
        for path in ['/setup','/login','/api/auth/status','/api/settings']:
            self.assertEqual(self.request(public+path)[0],404)
        self.assertNotIn('password_hash',json.dumps(self.a.public_config()))
    def test_login_csrf_logout_and_expiry(self):
        admin=self.server();self.setup(admin);csrf=self.csrf(admin)
        self.assertEqual(self.request(admin+'/api/content',{'type':'classic','internal_name':'X','title':'X','url':'https://example.com'})[0],403)
        self.assertEqual(self.request(admin+'/api/content',{'type':'classic','internal_name':'X','title':'X','url':'https://example.com'},headers={'X-Links-CSRF':csrf})[0],201)
        self.assertEqual(self.request(admin+'/api/auth/logout',{'csrf':csrf})[0],200)
        self.assertEqual(self.request(admin+'/api/content')[0],401)
        self.assertEqual(self.request(admin+'/api/auth/login',{'username':'admin','password':'wrong'})[0],400)
        status,body,headers=self.request(admin+'/api/auth/login',{'username':'admin','password':'A-long-test-password'});self.assertEqual(status,200,body)
        with self.a.connection() as db:db.execute('UPDATE admin_sessions SET expires=0')
        self.assertEqual(self.request(admin+'/api/content')[0],401)
    def test_secure_cookie_and_cross_origin_rejection(self):
        admin=self.server()
        with patch.dict(os.environ,{'ADMIN_ORIGIN':'https://admin.example'}):
            self.assertIn('Secure',self.setup(admin)[2]['Set-Cookie'])
        self.assertEqual(self.request(admin+'/api/auth/login',{'username':'admin','password':'A-long-test-password'},headers={'Origin':'https://evil.example'})[0],403)
    def test_external_mode_keeps_admin_and_local_switch(self):
        admin=self.server();self.setup(admin);csrf=self.csrf(admin)
        data={'mode':'external','csrf':csrf,'current_password':'A-long-test-password'}
        self.assertEqual(self.request(admin+'/api/auth/access',data)[0],400)
        data['confirm_external']=True;self.assertEqual(self.request(admin+'/api/auth/access',data)[0],200);self.cookie=''
        self.assertEqual(self.request(admin+'/api/content')[0],200)
        self.assertEqual(self.request(admin+'/api/auth/access',{'mode':'local','username':'newadmin','password':'Another-long-password','confirmation':'Another-long-password'})[0],200)
        self.cookie='';self.assertEqual(self.request(admin+'/api/content')[0],401)
    def test_analytics_disabled_preserves_content_and_story_redirects(self):
        admin=self.server();public=self.server(False);self.setup(admin,analytics_enabled=False)
        code=(self.a.content_list()[0]['id'])
        with self.a.connection() as db:
            self.a.instance.put(db,'auth.mode','external');promo=self.a.save_content(db,self.a.block_data({'type':'promo','title':'Promo','internal_name':'Promo','url':'https://partner.example','promo_code':'CODE'}))
        self.assertEqual(self.request(admin+'/api/stats')[0],200)
        for event in [{'kind':'view'},{'kind':'click','link':'block:'+code},{'kind':'promo_code_copy','link':'block:'+promo,'code':'CODE'}]:self.assertEqual(self.request(public+'/metrics',event,headers={'Origin':admin})[0],204)
        self.a.record('view','direct-inconnu','')
        with self.a.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM counts').fetchone()[0],0)
    def test_rate_limit_without_ip_or_visitor_tracking(self):
        admin=self.server()
        self.a.AUTH_ATTEMPTS[:]=[self.a.time.monotonic()]*20
        self.assertEqual(self.request(admin+'/api/setup',{})[0],429)
        with self.a.connection() as db:self.assertFalse(any('ip' in row[1] for row in db.execute('PRAGMA table_info(admin_sessions)')))
    def test_backup_restore_all_tables_uploads_and_legacy_preservation(self):
        admin=self.server();self.setup(admin)
        raw=b'\x89PNG\r\n\x1a\nfixture';names=['11111111-1111-4111-8111-111111111111.png','22222222-2222-4222-8222-222222222222.png']
        for name in names:(self.a.UPLOADS/name).write_bytes(raw)
        with self.a.connection() as db:
            self.a.instance.put(db,'profile.logo','/uploads/'+names[0]);self.a.instance.put(db,'profile.avatar','/uploads/'+names[1])
            promo=self.a.save_content(db,self.a.block_data({'type':'promo','internal_name':'Offer','title':'Offer','url':'https://partner.example','promo_code':'OLD','image':'/uploads/'+names[1]}))
        self.a.add_quotes({'text':'Test quote'});story=self.a.story_link(promo)
        self.a.record_promo_copy({'link':'block:'+promo,'code':'OLD','source':'instagram'})
        with self.a.connection() as db:db.execute('UPDATE content_blocks SET archived=1,promo_code=? WHERE id=?',('NEW',promo))
        before=json.loads(self.a.export_backup());self.assertEqual(before['version'],3);self.assertIn('footer_quotes',before['tables']);self.assertEqual(len(before['images']),2)
        # Restore into a separate actual database/storage, not merely the source.
        olddb,olduploads=self.a.DB,self.a.UPLOADS;self.a.DB=str(self.root/'restore'/'analytics.db');self.a.DATA_DIR=Path(self.a.DB).parent;self.a.UPLOADS=self.a.DATA_DIR/'uploads'
        with contextlib.redirect_stdout(io.StringIO()):self.a.init()
        self.cookie=''
        self.assertEqual(self.setup(admin,bootstrap=(self.a.DATA_DIR/'setup-code').read_text().strip(),username='receiver')[0],200)
        self.a.restore_backup(json.loads(json.dumps(before)))
        self.assertEqual(self.request(admin+'/api/content')[0],401)
        self.assertEqual(self.request(admin+'/api/auth/login',{'username':'receiver','password':'A-long-test-password'})[0],200)
        restored=json.loads(self.a.export_backup())
        for table in ['top_buttons','counts','story_links','footer_quotes']:self.assertEqual(restored['tables'][table],before['tables'][table])
        self.assertEqual(len(restored['tables']['content_blocks']),2);item=self.a.content_list(True)[0];self.assertEqual(item['promo_code'],'NEW');self.assertEqual((self.a.UPLOADS/item['image'][9:]).read_bytes(),raw)
        with self.a.connection() as db:
            copy=db.execute("SELECT link FROM counts WHERE kind='promo_code_copy'").fetchone();self.assertEqual(json.loads(copy[0])['code'],'OLD');self.assertEqual(self.a.instance.get(db,'profile.name'),'Example Creator');self.assertEqual(self.a.instance.get(db,'auth.mode'),'local');self.assertEqual(db.execute('SELECT username FROM admin_accounts').fetchone()[0],'receiver')
        legacy=json.loads(json.dumps(restored));legacy['format']='domotik-links-backup';legacy['version']=1;del legacy['tables']['footer_quotes'];del legacy['tables']['story_links'];legacy['tables']['counts']=[];legacy['tables']['settings']=[r for r in legacy['tables']['settings'] if r['key'].startswith('profile.')]
        self.a.restore_backup(legacy);self.assertEqual(len(self.a.quote_list()),1)
        with self.a.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM story_links').fetchone()[0],1);self.assertEqual(db.execute("SELECT COUNT(*) FROM counts WHERE kind='promo_code_copy'").fetchone()[0],1);self.assertEqual(self.a.instance.get(db,'app.timezone'),'Europe/Paris')
    def test_migration_keeps_sqlite_priority_assets_sources_and_is_idempotent(self):
        from fixtures import populate
        populate(self.a);self.a.add_quotes({'text':'Historical quote'})
        with self.a.connection() as db:
            self.a.instance.put(db,'profile.name','Current SQLite name');self.a.instance.put(db,'profile.logo','/assets/legacy-logo.webp');self.a.instance.put(db,'profile.avatar','/assets/legacy-avatar.webp')
            db.execute("DELETE FROM settings WHERE key IN ('app.config_schema_version','app.setup_completed','auth.mode','site.url','analytics.metric_aliases','analytics.source_rules','app.timezone')")
        assets=self.root/'assets';assets.mkdir();(assets/'legacy-logo.webp').write_bytes(b'logo');(assets/'legacy-avatar.webp').write_bytes(b'avatar')
        (self.root/'legacy-instance.json').write_text(json.dumps({'config':{'profile':{'name':'Old static name'},'siteUrl':'https://links.example','latestVideo':{'channelId':'UC'+'x'*22}},'source_rules':[{'key':'site.example','label':'Old source','aliases':['old-site'],'domains':['site.example']}],'metric_aliases':{'Domadoo':'block:legacy-link-3'}}))
        self.a.init();before=json.loads(self.a.export_backup());self.a.init();after=json.loads(self.a.export_backup());self.assertEqual(before['tables'],after['tables'])
        profile=self.a.public_config()['profile'];self.assertEqual(profile['name'],'Current SQLite name');self.assertTrue(profile['setup_completed']);self.assertEqual(profile['timezone'],'Europe/Paris')
        with self.a.connection() as db:self.assertEqual(self.a.instance.get(db,'auth.mode'),'external')
        self.assertEqual(self.a.source_of({'source':'old-site'}),'site.example');self.assertEqual(self.a.source_of({'referrer':'https://site.example/path'}),'site.example')
        admin=self.server();self.cookie='';self.assertEqual(self.request(admin+'/api/content')[0],200);self.assertEqual(self.request(admin+'/assets/legacy-logo.webp')[1],b'logo');self.assertTrue((self.root/'pre-v11-database.db').exists())
    def test_missing_legacy_asset_fails_closed(self):
        with self.a.connection() as db:
            self.a.instance.put(db,'profile.logo','/assets/missing-logo.webp');db.execute("DELETE FROM settings WHERE key='app.config_schema_version'")
        with self.assertRaisesRegex(RuntimeError,'asset historique manquant'):self.a.init()
        with self.a.connection() as db:self.assertIsNone(db.execute("SELECT 1 FROM settings WHERE key='app.config_schema_version'").fetchone())
    def test_preserve_tool_captures_old_image_before_neutralization(self):
        old=self.root/'old-image';(old/'site'/'assets').mkdir(parents=True)
        (old/'site'/'assets'/'logo.webp').write_bytes(b'legacy-logo')
        (old/'links.json').write_text(json.dumps({'profile':{'name':'Legacy creator','logo':'/assets/logo.webp'},'siteUrl':'https://links.example','links':[{'title':'Old link','url':'https://example.com'}],'socials':[]}))
        (old/'analytics.py').write_text("def source_of(data):\n    known={'legacy-site'}\n    aliases={'legacy-site':'site.example'}\n    for domain,name in [('site.example','site.example'),('youtube.com','youtube')]:\n        pass\n")
        spec=importlib.util.spec_from_file_location('preserve',Path(__file__).with_name('preserve-instance.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with contextlib.redirect_stdout(io.StringIO()):module.preserve(old,self.root)
        saved=json.loads((self.root/'legacy-instance.json').read_text());self.assertEqual(saved['source_rules'][0]['aliases'],['legacy-site']);self.assertEqual(saved['metric_aliases'],{'Old link':'block:legacy-link-0'})
        self.assertEqual((self.root/'assets'/'logo.webp').read_bytes(),b'legacy-logo');self.assertTrue((self.root/'pre-v11-volume'/'analytics.db').exists())
        with self.assertRaises(SystemExit):module.preserve(old,self.root)
    def test_public_snapshot_contains_no_access_secrets(self):
        admin=self.server();self.setup(admin);self.a.write_public_fallback()
        saved=json.loads((self.root/'public-fallback.json').read_text());self.assertTrue(saved['setup_completed']);self.assertEqual(saved['profile']['name'],'Example Creator')
        for secret in ['password_hash','bootstrap_hash','csrf','auth_mode','source_rules','A-long-test-password']:
            self.assertNotIn(secret,json.dumps(saved))

if __name__=='__main__':unittest.main()
