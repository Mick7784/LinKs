"""Regression tests for the PulSe Bearer-token bridge.

Run from project root: python3 -m unittest discover -s scripts -p pulse_bridge_test.py
"""
import os
import sqlite3
import unittest
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import analytics


class PulseBridgeTests(unittest.TestCase):
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


if __name__=="__main__":
    unittest.main()
