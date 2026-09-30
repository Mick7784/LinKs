import base64, importlib.util, json, os, tempfile, threading, unittest
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
    def request(self,url,data=None,headers=None):
        try:
            with urlopen(Request(url,json.dumps(data).encode() if data is not None else None,headers or {})) as r:return r.status,r.read()
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

    def test_image_upload_is_persistent_and_publicly_readable(self):
        admin=self.server(True)
        png=base64.b64encode(b'\x89PNG\r\n\x1a\nminimal-test').decode()
        status,body=self.request(admin+'/api/upload',{'type':'image/png','data':png},{'Content-Type':'application/json'})
        self.assertEqual(status,201)
        path=json.loads(body)['url']
        self.assertEqual(self.request(admin+path)[0],200)
        self.assertEqual(self.request(self.server()+path)[0],200)

if __name__=='__main__':unittest.main()


