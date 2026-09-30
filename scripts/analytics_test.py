import base64, importlib.util, json, os, tempfile, threading, unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path

class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ['ANALYTICS_DB']=self.tmp.name+'/stats.db'
        os.environ['STATS_PASSWORD']='test-password-only-123456'
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
    def test_admin_private_and_fail_closed(self):
        url=self.server(True)
        self.assertEqual(self.request(url+'/api/stats')[0],401)
        h={'Authorization':'Basic '+base64.b64encode(b'admin:test-password-only-123456').decode()}
        self.assertEqual(self.request(url+'/api/stats',headers=h)[0],200)
        self.assertEqual(self.request(url+'/',headers=h)[0],200)
        self.a.PASSWORD=''
        self.assertEqual(self.request(url+'/api/stats',headers=h)[0],401)
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

if __name__=='__main__':unittest.main()
