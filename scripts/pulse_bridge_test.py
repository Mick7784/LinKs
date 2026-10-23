"""Regression tests for the PulSe Bearer-token bridge.

Run from project root: python3 -m unittest discover -s scripts -p pulse_bridge_test.py
"""
import os
import sqlite3
import unittest
import tempfile
import threading
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import analytics
from fixtures import prepare


@contextmanager
def isolated_database():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        prepare(root/'stats.db')
        with patch.object(analytics,'DB',str(root/'stats.db')),patch.object(analytics,'DATA_DIR',root), \
             patch.object(analytics,'UPLOADS',root/'uploads'),patch.object(analytics,'ORIGIN','https://links.example'), \
             patch.object(analytics,'PARIS',ZoneInfo('Europe/Paris')):
            analytics.init()
            yield


class PulseBridgeTests(unittest.TestCase):
    def test_video_link_is_specific_stable_and_counted_only_on_real_open(self):
        video_id='abcdefghijk'
        video={'title':'Vidéo test','url':'https://youtu.be/'+video_id}
        with isolated_database(),patch.object(analytics,'latest_video',return_value=video):
            first=analytics.pulse_story_link({'type':'youtube','id':video_id})
            again=analytics.pulse_story_link({'type':'youtube','id':video_id})
            self.assertEqual(first['url'],again['url'])
            with analytics.connection() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM tracked_tokens').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT COALESCE(SUM(total),0) FROM counts').fetchone()[0],0)
                self.assertEqual(db.execute('SELECT url FROM tracked_links').fetchone()[0],
                                 'https://www.youtube.com/watch?v='+video_id)
            class NoRedirect(HTTPRedirectHandler):
                def redirect_request(self,*args):return None
            server=analytics.serve(0,False,'127.0.0.1')
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            try:
                url='http://127.0.0.1:'+str(server.server_port)+'/'+first['code']
                for method,expected in [('HEAD',0),('GET',1)]:
                    try:response=build_opener(NoRedirect).open(Request(url,method=method,headers={'User-Agent':'Mozilla/5.0'}))
                    except HTTPError as exc:response=exc
                    with response:
                        self.assertEqual(response.code,302)
                        self.assertEqual(response.headers['Location'],'https://www.youtube.com/watch?v='+video_id)
                    self.assertEqual(analytics.pulse_stats()['stories'],expected)
            finally:server.shutdown();server.server_close();worker.join()
            with patch.object(analytics,'latest_video',return_value={'title':'Nouvelle','url':'https://youtu.be/12345678901'}):
                with self.assertRaises(ValueError):analytics.pulse_story_link({'type':'youtube','id':video_id})
            with analytics.connection() as db:
                self.assertEqual(db.execute('SELECT url FROM tracked_links').fetchone()[0],
                                 'https://www.youtube.com/watch?v='+video_id)
                db.execute('UPDATE tracked_links SET archived=1')
            with self.assertRaises(ValueError):analytics.pulse_story_link({'type':'youtube','id':video_id})

    def test_video_does_not_accept_arbitrary_urls_or_create_links_without_source(self):
        with isolated_database():
            for video in [None,{'url':'https://evil.test/watch?v=abcdefghijk'},
                          {'url':'https://www.youtube.com/watch?v=other123456'}]:
                with patch.object(analytics,'latest_video',return_value=video):
                    with self.assertRaises(ValueError):analytics.pulse_story_link({'type':'youtube','id':'abcdefghijk'})
            with analytics.connection() as db:db.execute('UPDATE tracking_sources SET active=0')
            with patch.object(analytics,'latest_video',return_value={'url':'https://youtu.be/abcdefghijk'}):
                with self.assertRaises(ValueError):analytics.pulse_story_link({'type':'youtube','id':'abcdefghijk'})
            with analytics.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM tracked_links').fetchone()[0],0)

    def test_token_is_disabled_by_default_and_constant_time_compared(self):
        with patch.dict(os.environ, {"PULSE_BRIDGE_TOKEN": ""}):
            self.assertFalse(analytics.pulse_token_ready())
            self.assertFalse(analytics.pulse_authenticated("Bearer something"))
        value="s"*64
        with patch.dict(os.environ, {"PULSE_BRIDGE_TOKEN": value}):
            self.assertTrue(analytics.pulse_token_ready())
            self.assertTrue(analytics.pulse_authenticated("Bearer "+value))
            self.assertFalse(analytics.pulse_authenticated("Bearer "+value[:-1]+"x"))
            self.assertFalse(analytics.pulse_authenticated("Basic "+value))
            self.assertFalse(analytics.pulse_authenticated(value))

    def test_only_active_private_tracked_links_are_listed(self):
        db=sqlite3.connect(":memory:")
        db.row_factory=sqlite3.Row
        db.execute("""CREATE TABLE tracked_links (
          id TEXT,name TEXT,url TEXT,category TEXT,enabled INTEGER,archived INTEGER,
          created_at TEXT)""")
        rows=[
            ("active","Active","https://example.org/a","Produit",1,0,"2026-01-01"),
            ("disabled","Disabled","https://example.org/b","Produit",0,0,"2026-01-02"),
            ("archived","Archived","https://example.org/c","Produit",1,1,"2026-01-03")]
        db.executemany("INSERT INTO tracked_links VALUES(?,?,?,?,?,?,?)",rows)
        @contextmanager
        def conn():
            yield db
        with patch.object(analytics,"connection",conn):
            result=analytics.pulse_links()["links"]
        self.assertEqual([r["id"] for r in result],["active"])
        self.assertTrue(result[0]["enabled"])
        self.assertFalse(result[0]["archived"])
        db.close()

    def test_story_link_accepts_active_featured_and_rejects_classic(self):
        db=sqlite3.connect(":memory:")
        db.row_factory=sqlite3.Row
        db.execute("""CREATE TABLE content_blocks (
            id TEXT, type TEXT, retired INTEGER, archived INTEGER,
            draft INTEGER, active INTEGER, start_at TEXT, end_at TEXT)""")
        db.executemany("INSERT INTO content_blocks VALUES(?,?,?,?,?,?,?,?)", [
            ("featured1","featured",0,0,0,1,None,None),
            ("classic1","classic",0,0,0,1,None,None),
            ("disabled1","promo",0,0,0,0,None,None)])
        @contextmanager
        def conn():
            yield db
        with patch.object(analytics,"connection",conn), patch.object(analytics,"story_link",return_value={"url":"https://links.example/test"}) as called:
            result=analytics.pulse_story_link({"type":"campaign","id":"featured1"})
            self.assertEqual(result["url"],"https://links.example/test")
            called.assert_called_once_with("featured1","instagram")
            for ident in ("classic1","disabled1","unknown"):
                with self.assertRaises(ValueError):
                    analytics.pulse_story_link({"type":"campaign","id":ident})
        db.close()

    def test_daily_stats_include_clicks_stories_and_tracked_with_zero_days(self):
        db=sqlite3.connect(":memory:")
        db.row_factory=sqlite3.Row
        db.executescript("""CREATE TABLE counts(day TEXT,source TEXT,kind TEXT,link TEXT,total INTEGER);
        CREATE TABLE tracked_tokens(token TEXT,source_id TEXT);
        CREATE TABLE tracking_sources(id TEXT,name TEXT);""")
        day=datetime.now(ZoneInfo("UTC")).date().isoformat()
        db.executemany("INSERT INTO counts VALUES(?,?,?,?,?)",[
            (day,"site","click","block:x",2),
            (day,"instagram","story","story:st_token",3),
            (day,"tracked:source1","tracked","tracked:tk_token",4),
            (day,"site","view","",100)])
        db.execute("INSERT INTO tracked_tokens VALUES(?,?)",("tk_token","source1"))
        db.execute("INSERT INTO tracking_sources VALUES(?,?)",("source1","Instagram Story"))
        @contextmanager
        def conn():
            yield db
        with patch.object(analytics,"connection",conn),patch.object(analytics,"PARIS",ZoneInfo("UTC")):
            stats=analytics.pulse_stats()
        self.assertEqual(stats["today"],9)
        self.assertEqual(stats["last7"],9)
        self.assertEqual(stats["stories"],7)
        self.assertEqual(len(stats["days"]),7)
        self.assertEqual(sum(r["clicks"] for r in stats["days"]),9)
        db.close()

    def test_thirty_days_preserves_last7_and_excludes_outside_window(self):
        db=sqlite3.connect(":memory:")
        db.row_factory=sqlite3.Row
        db.executescript("""CREATE TABLE counts(day TEXT,source TEXT,kind TEXT,link TEXT,total INTEGER);
        CREATE TABLE tracked_tokens(token TEXT,source_id TEXT);
        CREATE TABLE tracking_sources(id TEXT,name TEXT);""")
        today=datetime.now(analytics.PARIS).date()
        for age,kind,total in [(0,'click',2),(6,'story',3),(7,'click',5),
                               (29,'story',7),(30,'click',100),(0,'view',1000)]:
            db.execute("INSERT INTO counts VALUES(?,?,?,?,?)",
                       ((today-timedelta(days=age)).isoformat(),'site',kind,'test',total))
        @contextmanager
        def conn():
            yield db
        with patch.object(analytics,"connection",conn):
            week=analytics.pulse_stats()
            month=analytics.pulse_stats('30')
        self.assertEqual(week['total'],5)
        self.assertEqual(month['total'],17)
        self.assertEqual(month['last7'],week['last7'])
        self.assertEqual(month['today'],2)
        self.assertEqual(month['stories'],10)
        self.assertEqual(len(month['days']),30)
        self.assertEqual(month['days'][0]['date'],(today-timedelta(days=29)).isoformat())
        self.assertEqual(month['days'][1]['clicks'],0)
        self.assertEqual(month['days'][-1]['date'],today.isoformat())
        db.close()

    def test_invalid_period_is_rejected_before_database_access(self):
        with patch.object(analytics,'connection') as conn:
            for period in ('',0,1,29,31,'30 OR 1=1',None,True):
                with self.assertRaises(ValueError):analytics.pulse_stats(period)
            conn.assert_not_called()

    def test_http_period_validation_and_authentication(self):
        handler=object.__new__(analytics.Handler)
        handler.server=type('Server',(),{'admin':True})()
        handler.headers={'Authorization':'Bearer '+'s'*64}
        handler.json=lambda status,data:(status,data)
        handler.send=lambda status:status
        with patch.dict(os.environ,{'PULSE_BRIDGE_TOKEN':'s'*64}), \
             patch.object(analytics,'pulse_stats',return_value={'period':30}) as stats:
            handler.path='/api/pulse/stats?days=30'
            self.assertEqual(handler.pulse_bridge_get(),(200,{'period':30}))
            stats.assert_called_once_with('30')
            handler.path='/api/pulse/stats?days=7&days=30'
            self.assertEqual(handler.pulse_bridge_get()[0],400)
            handler.headers={}
            self.assertEqual(handler.pulse_bridge_get()[0],401)


if __name__=="__main__":
    unittest.main()
