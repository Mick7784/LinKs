import base64, importlib.util, json, os, tempfile, threading, unittest
from datetime import date
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path

class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ['ANALYTICS_DB']=self.tmp.name+'/stats.db'
        os.environ['UPLOAD_DIR']=self.tmp.name+'/uploads'
        spec=importlib.util.spec_from_file_location('analytics',Path(__file__).with_name('analytics.py'))
        self.a=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.a);self.a.init()
        self.servers=[]
    def tearDown(self):
        for s in self.servers:s.shutdown();s.server_close()
        self.tmp.cleanup()
    def server(self,admin=False):
        s=self.a.serve(0,admin,'127.0.0.1');self.servers.append(s)
        threading.Thread(target=s.serve_forever,daemon=True).start()
        return 'http://127.0.0.1:'+str(s.server_port)
    def request(self,url,data=None,headers=None,method=None):
        try:
            with urlopen(Request(url,json.dumps(data).encode() if data is not None else None,headers or {},method=method)) as r:return r.status,r.read()
        except HTTPError as e:return e.code,e.read()
    def test_aggregation_persistence_and_dates(self):
        self.a.record('view','youtube','','2026-09-30');self.a.record('view','youtube','','2026-09-30');self.a.record('click','instagram','Amazon','2026-09-30')
        self.a.init()
        rows=self.a.report('2026-09-30','2026-09-30')['rows']
        self.assertEqual(sum(r['total'] for r in rows),3)
        self.assertEqual(self.a.report('2026-09-30','2026-09-30','youtube')['rows'][0]['total'],2)
        self.assertEqual(self.a.report('2026-09-29','2026-09-29')['rows'],[])
        with self.assertRaises(ValueError):self.a.report('2026-10-01','2026-09-01')
    def test_admin_vpn_access_without_password(self):
        url=self.server(True)
        self.assertEqual(self.request(url+'/healthz'),(200,b'ok'))
        self.assertEqual(self.request(url+'/api/stats')[0],200)
        self.assertEqual(self.request(url+'/')[0],200)
        public=self.server()
        for path in ['/', '/api/stats', '/app.js', '/style.css']:
            self.assertEqual(self.request(public+path)[0],404)
    def test_ingestion_no_stats_route_and_validation(self):
        url=self.server();event={'kind':'click','link':'latest-video','source':'youtube'}
        self.assertEqual(self.request(url+'/api/stats')[0],404)
        self.assertEqual(self.request(url+'/metrics',event)[0],403)
        headers={'Origin':self.a.ORIGIN}
        self.assertEqual(self.request(url+'/metrics',event,headers)[0],204)
        event['link']='unknown'
        self.assertEqual(self.request(url+'/metrics',event,headers)[0],400)
        self.assertEqual(self.request(url+'/metrics',{'kind':'view','source':{}},headers)[0],400)
    def test_source_attribution(self):
        self.assertEqual(self.a.source_of({'source':'ig','referrer':'https://google.fr/search?q=private'}),'instagram')
        self.assertEqual(self.a.source_of({'referrer':'https://l.instagram.com/secret'}),'instagram')
        self.assertEqual(self.a.source_of({}),'direct-inconnu')
        self.assertEqual(self.a.source_of({'referrer':self.a.ORIGIN}),'direct-inconnu')
        self.assertEqual(self.a.source_of({'referrer':'https://fakeinstagram.com/'}),'autre-site')
    def test_concurrent_counts(self):
        threads=[threading.Thread(target=lambda:self.a.record('view','youtube','')) for _ in range(20)]
        for t in threads:t.start()
        for t in threads:t.join()
        with self.a.connection() as db:self.assertEqual(db.execute('SELECT SUM(total) FROM counts').fetchone()[0],20)

    def test_seed_public_config_and_scheduling(self):
        config=self.a.public_config()
        self.assertEqual(config['profile']['name'],'DomotiK Studio')
        self.assertEqual(config['links'][0]['id'],'legacy-link-0')
        self.assertEqual(config['socials'][0]['metricKey'],'button:legacy-button-0')
        with self.a.connection() as db:
            db.execute("UPDATE content_blocks SET start_at='2999-01-01T00:00:00Z' WHERE id='legacy-link-0'")
        self.assertNotIn('legacy-link-0',[x['id'] for x in self.a.public_config()['links']])

    def test_content_crud_archive_and_existing_counts(self):
        admin=self.server(True)
        item={'type':'promo','internal_name':'Promo test','title':'Offre','description':'Test','url':'https://example.com','icon':'website','image':'','badge':'Promo','cta':'Voir','active':True,'draft':False,'start_at':None,'end_at':None}
        status,body=self.request(admin+'/api/content',item,{'Content-Type':'application/json'})
        self.assertEqual(status,201);item_id=json.loads(body)['id']
        public=self.server()
        self.assertEqual(self.request(public+'/metrics',{'kind':'click','link':'block:'+item_id},{'Origin':self.a.ORIGIN,'Content-Type':'application/json'})[0],204)
        self.assertIn(item_id,[x['id'] for x in self.a.content_list()])
        self.assertEqual(next(x for x in self.a.content_list() if x['id']==item_id)['clicks'],1)
        self.assertEqual(self.request(admin+'/api/content/'+item_id+'/archive',{}, {'Content-Type':'application/json'})[0],204)
        self.assertNotIn(item_id,[x['id'] for x in self.a.public_config()['links']])
        self.assertEqual(self.request(admin+'/api/content/'+item_id,headers={},method='DELETE')[0],204)
        with self.a.connection() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM counts WHERE link=?",('block:'+item_id,)).fetchone()[0],0)

    def test_image_upload_is_persistent_and_publicly_readable(self):
        admin=self.server(True)
        png=base64.b64encode(b'\x89PNG\r\n\x1a\nminimal-test').decode()
        status,body=self.request(admin+'/api/upload',{'type':'image/png','data':png},{'Content-Type':'application/json'})
        self.assertEqual(status,201)
        path=json.loads(body)['url']
        self.assertEqual(self.request(admin+path)[0],200)
        self.assertEqual(self.request(self.server()+path)[0],200)

    def test_promotion_limit_next_slot_and_edit_exclusion(self):
        admin=self.server(True)
        base={'type':'promo','internal_name':'Promo','title':'Offre','description':'','url':'https://example.com','icon':'website','image':'','badge':'Promo','cta':'Voir','priority':'normal','active':True,'draft':False,'start_at':'2099-01-01T00:00:00Z'}
        ids=[]
        for index,end in enumerate(['2099-01-05T00:00:00Z','2099-01-06T00:00:00Z','2099-01-07T00:00:00Z']):
            item={**base,'internal_name':'Promo '+str(index+1),'end_at':end}
            status,body=self.request(admin+'/api/content',item,{'Content-Type':'application/json'})
            self.assertEqual(status,201);ids.append(json.loads(body)['id'])
        candidate={**base,'internal_name':'Quatrième','start_at':'2099-01-02T00:00:00Z','end_at':'2099-01-03T00:00:00Z'}
        status,body=self.request(admin+'/api/promotions/check',candidate,{'Content-Type':'application/json'})
        check=json.loads(body);self.assertEqual(status,200);self.assertFalse(check['allowed']);self.assertEqual(check['maximum'],4)
        self.assertEqual(check['next_start'],'2099-01-05T00:00:00Z')
        self.assertEqual(self.request(admin+'/api/content',candidate,{'Content-Type':'application/json'})[0],400)
        edited={**candidate,'id':ids[0]}
        self.assertTrue(json.loads(self.request(admin+'/api/promotions/check',edited,{'Content-Type':'application/json'})[1])['allowed'])

    def test_visible_promotion_impression_is_recorded(self):
        public=self.server();headers={'Origin':self.a.ORIGIN,'Content-Type':'application/json'}
        self.assertEqual(self.request(public+'/metrics',{'kind':'impression','link':'block:legacy-link-0'},headers)[0],204)
        item=next(x for x in self.a.content_list() if x['id']=='legacy-link-0')
        self.assertEqual(item['impressions'],1)
        self.assertNotIn('impression',{row['kind'] for row in self.a.report(date.today().isoformat(),date.today().isoformat())['rows']})

    def test_seed_runs_only_once_even_after_everything_deleted(self):
        with self.a.connection() as db:
            db.execute('DELETE FROM content_blocks');db.execute('DELETE FROM top_buttons')
        self.a.init()
        self.assertEqual(self.a.content_list(),[]);self.assertEqual(self.a.button_list(),[])

    def test_report_resolves_labels_without_changing_metric_keys(self):
        self.a.record('click','youtube','block:legacy-link-0','2026-09-30')
        row=self.a.report('2026-09-30','2026-09-30')['rows'][0]
        self.assertEqual(row['link'],'block:legacy-link-0')
        self.assertEqual(row['label'],self.a.CONFIG['links'][0]['title'])

    def test_promotion_restore_and_atomic_replacement(self):
        admin=self.server(True)
        base={'type':'promo','internal_name':'Promo','title':'Offre','url':'https://example.com','start_at':'2099-01-01T00:00:00Z','end_at':'2099-02-01T00:00:00Z'}
        ids=[]
        for i in range(3):
            status,body=self.request(admin+'/api/content',{**base,'internal_name':str(i)})
            self.assertEqual(status,201);ids.append(json.loads(body)['id'])
        self.request(admin+'/api/content/'+ids[0]+'/archive',{})
        status,body=self.request(admin+'/api/content',base);self.assertEqual(status,201)
        self.assertEqual(self.request(admin+'/api/content/'+ids[0]+'/restore',{})[0],400)
        self.assertTrue(next(x for x in self.a.content_list(True) if x['id']==ids[0])['archived'])
        # Failure occurs after disabling the old promotion inside the transaction.
        self.assertEqual(self.request(admin+'/api/promotions/replace',{'replace_id':ids[1],'content':{**base,'id':'missing'}})[0],400)
        self.assertTrue(next(x for x in self.a.content_list() if x['id']==ids[1])['active'])
        self.assertEqual(self.request(admin+'/api/promotions/replace',{'replace_id':ids[1],'content':base})[0],200)
        self.assertFalse(next(x for x in self.a.content_list() if x['id']==ids[1])['active'])
        self.assertEqual(len([x for x in self.a.content_list() if x['type']=='promo' and x['active']]),3)

    def test_backup_roundtrip_including_images_and_counts(self):
        name='12345678-1234-1234-1234-123456789abc.png'
        raw=b'\x89PNG\r\n\x1a\nbackup-test';(self.a.UPLOADS/name).write_bytes(raw)
        with self.a.connection() as db:
            db.execute('UPDATE content_blocks SET image=? WHERE id=?',('/uploads/'+name,'legacy-link-0'))
        self.a.record('click','youtube','block:legacy-link-0')
        admin=self.server(True);public=self.server()
        status,body=self.request(admin+'/api/backup');self.assertEqual(status,200)
        backup=json.loads(body)
        self.assertEqual(self.request(public+'/api/backup')[0],404)
        self.assertEqual(self.request(public+'/api/restore',backup)[0],404)
        with self.a.connection() as db:db.execute('DELETE FROM counts');db.execute('DELETE FROM content_blocks')
        status,body=self.request(admin+'/api/restore',backup);self.assertEqual(status,200,body)
        restored=next(x for x in self.a.content_list() if x['id']=='legacy-link-0')
        self.assertEqual(restored['clicks'],1)
        self.assertEqual((self.a.UPLOADS/restored['image'].split('/')[-1]).read_bytes(),raw)
        self.assertEqual((self.a.UPLOADS/name).read_bytes(),raw)
        self.a.init();self.assertEqual(len(self.a.content_list()),len(backup['tables']['content_blocks']))

    def test_invalid_backup_preserves_current_database(self):
        backup=json.loads(self.a.export_backup())
        backup['tables']['settings'].append(dict(backup['tables']['settings'][0]))
        before=self.a.content_list()
        # A duplicate fails after DELETE statements, so this tests rollback.
        status,_=self.request(self.server(True)+'/api/restore',backup)
        self.assertEqual(status,400);self.assertEqual(self.a.content_list(),before)
        self.a.init();self.assertEqual(self.a.content_list(),before)
        backup=json.loads(self.a.export_backup());backup['images']['../escape.png']='eA=='
        self.assertEqual(self.request(self.server(True)+'/api/restore',backup)[0],400)
        self.assertEqual(self.a.content_list(),before)

    def test_failed_image_write_rolls_back_restore(self):
        from unittest.mock import patch
        backup=json.loads(self.a.export_backup())
        name='12345678-1234-1234-1234-123456789abc.png'
        backup['images'][name]=base64.b64encode(b'image').decode()
        backup['tables']['content_blocks'][0]['title']='Changed'
        backup['tables']['content_blocks'][0]['image']='/uploads/'+name
        before=self.a.content_list()
        with patch.object(Path,'write_bytes',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.a.restore_backup(backup)
        self.assertEqual(self.a.content_list(),before)

if __name__=='__main__':unittest.main()


