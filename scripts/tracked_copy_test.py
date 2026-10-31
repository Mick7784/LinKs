"""Private, read-only destination checks and preservation of published links."""
import json
import socket
import time
import unittest
from unittest.mock import patch

import analytics_test
import url_inspection_test as inspection

_resolve=socket.getaddrinfo
def resolver(host,port,*args,**kwargs):
    if host=='127.0.0.1':return _resolve(host,port,*args,**kwargs)
    return inspection.public_resolver(host,port,**kwargs)


class TrackedCopyTests(unittest.TestCase):
    setUp = analytics_test.AnalyticsTests.setUp
    tearDown = analytics_test.AnalyticsTests.tearDown
    server = analytics_test.AnalyticsTests.server
    request = analytics_test.AnalyticsTests.request
    redirect = analytics_test.AnalyticsTests.redirect

    def link(self, admin):
        url='https://shop.reolink.com/camera?aff=1404'
        status,body=self.request(admin+'/api/tracked-links',{'name':'Caméra','url':url})
        self.assertEqual(status,201,body)
        return json.loads(body)

    def snapshot(self):
        with self.a.connection() as db:
            return list(db.iterdump())

    def test_verdicts_use_stored_affiliate_url_and_preserve_all_data(self):
        admin=self.server(True)
        link=self.link(admin)
        sources=json.loads(self.request(admin+'/api/tracking-sources')[1])['items']
        endpoint=admin+'/api/tracked-links/'+link['id']
        token=json.loads(self.request(endpoint+'/token',{'source_id':sources[0]['id']})[1])
        with self.a.connection() as db:
            db.execute('UPDATE tracked_tokens SET click_total=7 WHERE token=?',(token['token'],))
        before=self.snapshot()
        # Exercise the real engine through HTTP, including negative HEAD confirmation.
        for head,get,status in [(200,200,'valid'),(404,200,'valid'),(404,404,'broken'),
                               (410,410,'broken'),(403,403,'unknown'),(429,429,'unknown'),
                               (500,500,'unknown'),(503,503,'unknown')]:
            calls=[]
            def request(target,ip,method,limit,*,deadline):
                self.assertGreater(deadline,time.monotonic())
                calls.append((target.url,method))
                return inspection.reply(head if method=='HEAD' else get)
            with patch.object(self.a.url_inspection.socket,'getaddrinfo',side_effect=resolver), \
                 patch.object(self.a.url_inspection,'_request_once',side_effect=request):
                code,body=self.request(endpoint+'/check-destination',{'url':'https://evil.example/arbitrary'})
            self.assertEqual(code,200,body)
            self.assertEqual(json.loads(body)['status'],status)
            self.assertTrue(all(url==link['url'] for url,method in calls))
            self.assertEqual([method for url,method in calls],['HEAD'] if head==200 else ['HEAD','GET'])
            self.assertEqual(self.snapshot(),before)
        self.assertEqual(json.loads(self.request(endpoint+'/token',{'source_id':sources[0]['id']})[1]),token)
        public=self.server(False)
        for path in ('/'+token['code'],'/go/'+token['token']):
            status,headers=self.redirect(public+path,method='HEAD')
            self.assertEqual(status,302)
            self.assertEqual(headers['Location'],link['url'])
        self.assertEqual(self.snapshot(),before)

    def test_timeouts_and_unsafe_redirects_are_unknown_without_tracking(self):
        admin=self.server(True)
        link=self.link(admin)
        endpoint=admin+'/api/tracked-links/'+link['id']+'/check-destination'
        before=self.snapshot()
        for destination in (self.a.ORIGIN+'/published-code','http://127.0.0.1/private'):
            with patch.object(self.a.url_inspection.socket,'getaddrinfo',side_effect=resolver), \
                 patch.object(self.a.url_inspection,'_request_once',return_value=inspection.reply(302,location=destination)) as remote:
                status,body=self.request(endpoint,{})
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)['status'],'unknown')
            self.assertEqual(remote.call_count,1)
        for error in (TimeoutError(),OSError('offline')):
            with patch.object(self.a.url_inspection.socket,'getaddrinfo',side_effect=resolver), \
                 patch.object(self.a.url_inspection,'_request_once',side_effect=error):
                self.assertEqual(json.loads(self.request(endpoint,{})[1])['status'],'unknown')
        self.assertEqual(self.snapshot(),before)

    def test_only_authenticated_admin_post_can_inspect_existing_id(self):
        admin=self.server(True)
        link=self.link(admin)
        public=self.server(False)
        path='/api/tracked-links/'+link['id']+'/check-destination'
        with patch.object(self.a.url_inspection,'check_destination') as inspect:
            for method in ('GET','POST','PUT','DELETE'):
                self.assertEqual(self.request(public+path,{} if method=='POST' else None,method=method)[0],404)
            self.assertEqual(self.request(admin+path)[0],404)
            self.assertEqual(self.request(admin+'/api/tracked-links/'+'0'*32+'/check-destination',{})[0],404)
            self.assertEqual(self.request(admin+path,{},headers={'X-Links-Request':''})[0],403)
            with self.a.connection() as db:self.a.instance.put(db,'auth.mode','local')
            self.assertEqual(self.request(admin+path,{})[0],401)
            inspect.assert_not_called()


if __name__=='__main__':
    unittest.main()
