"""Automatic expiry against disposable SQLite, including concurrent writers."""
import json
import sqlite3
import threading
import unittest
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import analytics as a
import analytics_test
import campaign_selection_test
from images_test import raster

END='2020-01-02T00:00:00Z'


class CampaignLifecycleTests(unittest.TestCase):
    create=campaign_selection_test.CampaignSelectionTests.create
    server=campaign_selection_test.CampaignSelectionTests.server
    request=campaign_selection_test.CampaignSelectionTests.request
    redirect=analytics_test.AnalyticsTests.redirect

    def setUp(self):
        campaign_selection_test.CampaignSelectionTests.setUp(self)
        self.stack.enter_context(patch.object(a,'CAMPAIGN_WAKE',threading.Event()))

    def expired(self,name='Expired',**extra):return self.create(name,**{'end_at':END,**extra})

    def tables(self):
        with a.connection() as db:
            return {table:[dict(r) for r in db.execute('SELECT * FROM '+table)]
                    for table in ['content_blocks','counts','story_links','short_aliases']}

    def test_every_lifetime_activity_kind_archives_and_preserves_exact_history(self):
        ids=[]
        for kind in ['impression','click','story','promo_code_copy']:
            ident=self.expired(kind);ids.append(ident)
            if kind=='story':
                token=a.story_link(ident)['url'].rsplit('/',1)[-1]
                a.record(kind,'youtube','story:'+token+':12','2000-01-01')
            elif kind=='promo_code_copy':
                a.record_promo_copy({'link':'block:'+ident,'code':'OLD10','source':'youtube'})
                with a.connection() as db:db.execute("UPDATE counts SET day='2000-01-01' WHERE kind='promo_code_copy'")
            else:a.record(kind,'youtube','block:'+ident,'2000-01-01')
        before=self.tables()
        # Collection being disabled now must not hide historical activity.
        with a.connection() as db:a.instance.put(db,'analytics.enabled','false')
        result=a.cleanup_campaigns(END)
        self.assertEqual(set(result['archived_ids']),set(ids));self.assertEqual(result['deleted_ids'],[])
        after=self.tables()
        for table in ['counts','story_links','short_aliases']:self.assertEqual(after[table],before[table])
        for old,row in zip(before['content_blocks'],after['content_blocks']):
            self.assertEqual({k:v for k,v in row.items() if k not in {'archived','updated_at'}},
                             {k:v for k,v in old.items() if k not in {'archived','updated_at'}})
        self.assertEqual(a.content_list(),[])
        archives={row['id']:row for row in a.content_list(True)}
        self.assertEqual(set(archives),set(ids))
        self.assertEqual(archives[ids[0]]['impressions'],1)
        self.assertEqual(archives[ids[1]]['clicks'],1)
        report=a.report('2000-01-01','2000-01-01')
        self.assertEqual(sum(r['total'] for r in report['stories']),1)
        self.assertEqual(sum(r['total'] for r in report['promo_code_copies']),1)
        self.assertEqual(a.campaign_selection(END)['eligible_ids'],[])
        self.assertEqual(a.public_config()['links'],[])

    def test_no_activity_or_reference_deletes_and_cleans_only_calendar_metadata(self):
        ident=self.expired(calendar_timed=True);permanent=self.create('Permanent',calendar_timed=True)
        before=self.tables()
        result=a.cleanup_campaigns(END)
        self.assertEqual(result['deleted_ids'],[ident]);self.assertEqual(result['archived_ids'],[])
        self.assertEqual([r['id'] for r in self.tables()['content_blocks']],[permanent])
        fallback=json.loads((a.DATA_DIR/'public-fallback.json').read_text(encoding='utf-8'))
        self.assertEqual([row['id'] for row in fallback['links']],[permanent])
        for table in ['counts','story_links','short_aliases']:self.assertEqual(self.tables()[table],before[table])
        with a.connection() as db:self.assertEqual(json.loads(a.instance.get(db,'admin.calendar_timed')),[permanent])

    def test_zero_click_long_and_short_links_are_archived_and_still_redirect(self):
        ids=[self.expired('Long'),self.expired('Short',type='featured')]
        long=a.story_link(ids[0])['url'].rsplit('/',1)[-1]
        short=a.story_link(ids[1],'youtube')['code']
        public=self.server(False)
        before=self.tables()
        self.assertEqual(a.cleanup_campaigns(END)['archived_ids'],sorted(ids))
        for path in ['/go/'+long,'/'+short]:
            status,headers=self.redirect(public+path,method='HEAD')
            self.assertEqual(status,302);self.assertEqual(headers['Location'],'https://partner.example/offer')
        after=self.tables()
        for table in ['counts','story_links','short_aliases']:self.assertEqual(after[table],before[table])
        backup=json.loads(a.export_backup());a.restore_backup(backup)
        self.assertEqual(self.redirect(public+'/'+short,method='HEAD')[0],302)
        self.assertEqual(a.cleanup_campaigns(END)['archived_ids'],[])

    def test_deleted_and_revoked_publications_still_protect_identity(self):
        ident=self.expired();a.story_link(ident,'instagram')
        with a.connection() as db:
            db.execute('UPDATE story_links SET deleted=1');db.execute('UPDATE short_aliases SET revoked=1')
        before=self.tables()
        self.assertEqual(a.cleanup_campaigns(END)['archived_ids'],[ident])
        for table in ['counts','story_links','short_aliases']:self.assertEqual(self.tables()[table],before[table])

    def test_legacy_metric_aliases_preserve_history_and_zero_stat_references(self):
        with_stat=self.expired('Historical click');without_stat=self.expired('Reserved alias')
        with a.connection() as db:
            a.instance.put(db,'analytics.metric_aliases',json.dumps({'Old name':'block:'+with_stat,'Reserved':'block:'+without_stat}))
        a.record('click','youtube','Old name','2000-01-01')
        self.assertEqual(set(a.cleanup_campaigns(END)['archived_ids']),{with_stat,without_stat})
        self.assertEqual(next(r for r in a.content_list(True) if r['id']==with_stat)['clicks'],1)

    def test_declared_references_are_preserved_even_with_cascading_foreign_key(self):
        ident=self.expired()
        with a.connection() as db:
            db.execute('CREATE TABLE campaign_reference(campaign_id TEXT REFERENCES content_blocks(id) ON DELETE CASCADE)')
            db.execute('INSERT INTO campaign_reference VALUES(?)',(ident,))
        self.assertEqual(a.cleanup_campaigns(END)['archived_ids'],[ident])
        with a.connection() as db:self.assertEqual(db.execute('SELECT campaign_id FROM campaign_reference').fetchone()[0],ident)

    def test_permanent_classic_draft_archived_and_retired_are_not_expired(self):
        untouched=[self.create('Permanent'),self.create('Open start',type='featured',start_at='2000-01-01T00:00:00Z'),
                   self.expired('Classic',type='classic'),self.expired('Draft',draft=True)]
        archived=self.expired('Already archived');retired=self.expired('Retired');disabled=self.expired('Disabled',active=False)
        with a.connection() as db:
            db.execute('UPDATE content_blocks SET archived=1 WHERE id=?',(archived,))
            db.execute('UPDATE content_blocks SET retired=1,archived=1 WHERE id=?',(retired,))
        before={r['id']:r for r in self.tables()['content_blocks']}
        self.assertEqual(a.cleanup_campaigns(END)['deleted_ids'],[disabled])
        after={r['id']:r for r in self.tables()['content_blocks']}
        for ident in untouched+[archived,retired]:self.assertEqual(after[ident],before[ident])

    def test_timezone_and_exact_deadline_use_instance_zone_for_historical_naive_end(self):
        ident=self.expired('Historical Paris')
        with a.connection() as db:db.execute("UPDATE content_blocks SET end_at='2026-10-25T03:00:00' WHERE id=?",(ident,))
        early=a.cleanup_campaigns('2026-10-25T01:59:59Z')
        self.assertEqual(early['deleted_ids'],[]);self.assertEqual(early['next_delay'],1)
        self.assertEqual(a.cleanup_campaigns('2026-10-25T03:00:00+01:00')['deleted_ids'],[ident])
        spring=self.expired('Spring',end_at='2026-03-29T03:00:00+02:00')
        self.assertEqual(a.cleanup_campaigns('2026-03-29T00:59:59Z')['deleted_ids'],[])
        self.assertEqual(a.cleanup_campaigns('2026-03-29T01:00:00Z')['deleted_ids'],[spring])

    def test_repeated_cleanup_and_restart_do_not_change_archived_history(self):
        archived=self.expired('With activity');deleted=self.expired('Unused')
        a.record('impression','youtube','block:'+archived,'2000-01-01')
        first=a.cleanup_campaigns(END);before=self.tables()
        self.assertEqual(first['archived_ids'],[archived]);self.assertEqual(first['deleted_ids'],[deleted])
        for _ in range(2):
            a.init();result=a.cleanup_campaigns('2020-02-01T00:00:00Z')
            self.assertEqual(result['archived_ids'],[]);self.assertEqual(result['deleted_ids'],[])
            self.assertEqual(self.tables(),before)

    def test_images_are_kept_for_archives_and_other_owners_with_normal_orphan_grace(self):
        def image():
            ref='/uploads/'+str(uuid.uuid4())+'.png';(a.UPLOADS/ref[9:]).write_bytes(raster());return ref
        shared,archived_image,unused=image(),image(),image()
        self.expired('Deleted shared owner',image=shared);self.create('Permanent shared owner',image=shared)
        archive=self.expired('Archived image',image=archived_image);a.record('click','youtube','block:'+archive)
        self.expired('Unused image',image=unused)
        a.cleanup_campaigns(END)
        self.assertTrue(all((a.UPLOADS/ref[9:]).is_file() for ref in [shared,archived_image,unused]))
        with a.connection() as db:
            a.storage.scan(db,a.UPLOADS,'cleanup',now=100)
            self.assertEqual({r[0] for r in db.execute('SELECT name FROM upload_trash')},{unused[9:]})
            a.storage.scan(db,a.UPLOADS,'cleanup',now=100+a.storage.GRACE_SECONDS)
        self.assertTrue((a.UPLOADS/shared[9:]).is_file());self.assertTrue((a.UPLOADS/archived_image[9:]).is_file())
        self.assertFalse((a.UPLOADS/unused[9:]).exists())

    def test_concurrent_cleanups_apply_each_action_once(self):
        archived=self.expired('With history');deleted=self.expired('Unused')
        a.record('click','youtube','block:'+archived)
        barrier=threading.Barrier(6);results=[];errors=[]
        def run():
            try:barrier.wait();results.append(a.cleanup_campaigns(END))
            except Exception as exc:errors.append(exc)
        threads=[threading.Thread(target=run) for _ in range(6)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(10);self.assertFalse(thread.is_alive())
        self.assertEqual(errors,[])
        self.assertEqual([ident for result in results for ident in result['archived_ids']],[archived])
        self.assertEqual([ident for result in results for ident in result['deleted_ids']],[deleted])

    def test_external_sqlite_writer_is_serialized_before_cleanup_snapshot(self):
        ident=self.expired();started=threading.Event();result=[];errors=[]
        with closing(sqlite3.connect(a.DB)) as external:
            external.execute('BEGIN IMMEDIATE')
            external.execute("INSERT INTO counts VALUES('2000-01-01','youtube','impression',?,1)",('block:'+ident,))
            def run():
                started.set()
                try:result.append(a.cleanup_campaigns(END))
                except Exception as exc:errors.append(exc)
            thread=threading.Thread(target=run);thread.start();self.assertTrue(started.wait(2))
            external.commit();thread.join(10)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(result[0]['archived_ids'],[ident])

    def test_late_metrics_are_validated_atomically_with_cleanup(self):
        accepted=self.expired('Accepted metric');deleted=self.expired('Deleted first')
        a.record('impression','youtube','block:'+accepted,validate=True)
        a.cleanup_campaigns(END)
        with self.assertRaises(ValueError):a.record('click','youtube','block:'+deleted,validate=True)
        with self.assertRaises(ValueError):a.record_promo_copy({'link':'block:'+deleted,'code':'OLD10'})
        self.assertEqual([r['id'] for r in a.content_list(True)],[accepted])
        self.assertNotIn('block:'+deleted,json.dumps(self.tables()['counts']))

    def test_concurrent_period_extension_is_seen_before_expiry_decision(self):
        ident=self.expired();started=threading.Event();results=[];errors=[]
        with closing(sqlite3.connect(a.DB)) as external:
            external.execute('BEGIN IMMEDIATE')
            external.execute("UPDATE content_blocks SET end_at='2099-01-01T00:00:00Z' WHERE id=?",(ident,))
            def run():
                started.set()
                try:results.append(a.cleanup_campaigns(END))
                except Exception as exc:errors.append(exc)
            worker=threading.Thread(target=run);worker.start();self.assertTrue(started.wait(2))
            external.commit();worker.join(10)
        self.assertFalse(worker.is_alive());self.assertEqual(errors,[])
        self.assertEqual(results[0]['deleted_ids'],[]);self.assertEqual(results[0]['archived_ids'],[])
        self.assertEqual(a.campaign_selection(END)['eligible_ids'],[ident])

    def test_bad_history_rolls_back_and_failed_fallback_is_retried(self):
        ident=self.expired()
        with a.connection() as db:db.execute("INSERT INTO counts VALUES('2000-01-01','youtube','promo_code_copy','broken',1)")
        with self.assertRaises(ValueError):a.cleanup_campaigns(END)
        self.assertEqual([r['id'] for r in self.tables()['content_blocks']],[ident])
        with a.connection() as db:db.execute('DELETE FROM counts')
        with patch.object(a,'write_public_fallback',side_effect=OSError('disk temporarily unavailable')):
            with self.assertRaises(OSError):a.cleanup_campaigns(END)
        with patch.object(a,'write_public_fallback',wraps=a.write_public_fallback) as refresh:
            result=a.cleanup_campaigns(END);refresh.assert_called_once()
        self.assertEqual(result['deleted_ids'],[]);self.assertTrue((a.DATA_DIR/'public-fallback.json').is_file())

    def test_worker_expires_without_any_http_request_and_recovers_from_error(self):
        end=(datetime.now(timezone.utc)+timedelta(seconds=.4)).isoformat()
        ident=self.create('Automatic',end_at=end);done=threading.Event();stop=threading.Event();original=a.cleanup_campaigns
        def cleanup():
            result=original()
            if ident in result['deleted_ids']:done.set()
            return result
        with patch.object(a,'cleanup_campaigns',side_effect=cleanup):
            worker=threading.Thread(target=a.campaign_worker,args=(stop,),daemon=True);worker.start()
            try:self.assertTrue(done.wait(5),'Background worker did not expire the campaign')
            finally:stop.set();a.CAMPAIGN_WAKE.set();worker.join(5)
        self.assertFalse(worker.is_alive());self.assertEqual(self.tables()['content_blocks'],[])
        # A failed cycle logs and retries rather than killing the worker.
        stop=threading.Event()
        with patch.object(a,'cleanup_campaigns',side_effect=[sqlite3.OperationalError('busy'),{'next_delay':30}]) as run, \
             patch('builtins.print'):
            # Stop on the second wait; the first failure must not end the loop.
            def wait(_timeout):
                if run.call_count==2:stop.set()
                return True
            with patch.object(a.CAMPAIGN_WAKE,'wait',side_effect=wait):a.campaign_worker(stop)
            self.assertEqual(run.call_count,2)


if __name__=='__main__':unittest.main()
