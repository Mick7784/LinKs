import json, unittest, threading, os
from datetime import datetime
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import analytics as a
from pulse_bridge_test import isolated_database

class TodayTests(unittest.TestCase):
    def test_daily_snapshot_dst_midnight_and_read_only(self):
        with isolated_database():
            for instant,day,previous in [('2026-03-29T22:01:00+00:00','2026-03-30','2026-03-29'),('2026-10-25T23:01:00+00:00','2026-10-26','2026-10-25'),('2026-10-30T23:00:00+00:00','2026-10-31','2026-10-30')]:
                with a.connection() as db:
                    db.execute('DELETE FROM counts')
                    db.executemany('INSERT INTO counts VALUES(?,?,?,?,?)',[(day,'web','click','x',3),(day,'web','story','x',4),(day,'web','view','x',90),(previous,'web','click','x',8)])
                    before=list(db.iterdump())
                result=a.pulse_today(datetime.fromisoformat(instant))
                self.assertEqual((result['date'],result['yesterday_date'],result['today'],result['yesterday']),(day,previous,7,8))
                self.assertEqual(result['comparison'],'yesterday-full-day')
                self.assertEqual(result['top_links'],[])
                with a.connection() as db:self.assertEqual(list(db.iterdump()),before)
    def test_rankings_use_daily_not_lifetime_and_never_expose_urls(self):
        with isolated_database():
            a.pulse_story_link
            with patch.object(a,'latest_video',return_value={'title':'Test & été','url':'https://youtu.be/abcdefghijk'}):created=a.pulse_story_link({'type':'youtube','id':'abcdefghijk'})
            with a.connection() as db:
                db.execute('UPDATE tracked_tokens SET click_total=999')
                db.execute("INSERT INTO counts VALUES(?,?,?,?,?)",('2026-10-30','test','tracked','tracked:'+created['token'],5))
            result=a.pulse_today(datetime.fromisoformat('2026-10-30T12:00:00+00:00'))
            self.assertEqual((result['today'],result['tracked_total']), (5,5))
            self.assertEqual(result['top_links'][0]['clicks'],5)
            self.assertEqual(result['sources'][0]['clicks'],5)
            self.assertNotIn(created['token'],json.dumps(result))
            self.assertNotIn('https:',json.dumps(result))
    def test_zero_timezone_and_disabled_collection(self):
        with isolated_database():
            self.assertEqual(a.pulse_today()['today'],0)
            with a.connection() as db:a.instance.put(db,'analytics.enabled','false')
            self.assertFalse(a.pulse_today()['analytics_enabled'])
            with a.connection() as db:a.instance.put(db,'app.timezone','UTC')
            self.assertEqual(a.pulse_today(),{'version':1,'available':False,'reason':'timezone'})
    def test_private_bounded_get(self):
        with isolated_database(),patch.dict(os.environ,{'PULSE_BRIDGE_TOKEN':'x'*64}):
            for admin in [False,True]:
                server=a.serve(0,admin,'127.0.0.1');threading.Thread(target=server.serve_forever,daemon=True).start()
                try:
                    base='http://127.0.0.1:'+str(server.server_port)+'/api/pulse/today'
                    for suffix,auth,method,expected in [('',False,'GET',401 if admin else 404),('',True,'GET',200 if admin else 404),('?days=999',True,'GET',400 if admin else 404),('',True,'POST',415 if admin else 404)]:
                        try:r=urlopen(Request(base+suffix,method=method,headers={'Authorization':'Bearer '+'x'*64} if auth else {}))
                        except HTTPError as exc:r=exc
                        with r:self.assertEqual(r.status,expected)
                finally:server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()
