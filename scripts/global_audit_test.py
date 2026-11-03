"""Regression cases from the November audit, disposable fixtures only."""
import json
import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from analytics_test import AnalyticsTests
from description_workflow_test import WorkflowTests
from description_search_test import SearchTests
import descriptions
import url_inspection
from url_inspection_test import reply,public_resolver

class IntegrityTests(unittest.TestCase):
    for name in ('setUp','tearDown','server','request','promo','redirect'):
        locals()[name]=getattr(AnalyticsTests,name)

    def test_failed_commit_never_returns_success(self):
        admin=self.server(True);original=self.a.connection
        @contextmanager
        def fail():
            with original() as db:
                yield db
                if db.in_transaction:raise sqlite3.OperationalError('fixture commit failure')
        with patch.object(self.a,'connection',fail):
            status,body=self.request(admin+'/api/tracked-links',{'name':'Uncommitted','url':'https://shop.example/item'})
        self.assertEqual(status,503,body)
        with original() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM tracked_links WHERE name='Uncommitted'").fetchone()[0],0)

    def test_valid_large_source_rules_backup_preview_and_restore(self):
        rules=[{'key':f's{i}','label':'Source','aliases':['a'*120]*20,'domains':['d'*120]*20} for i in range(30)]
        value=self.a.instance.source_rules(rules);self.assertGreater(len(value),16384)
        with self.a.connection() as db:self.a.instance.put(db,'analytics.source_rules',value)
        bundle=json.loads(self.a.export_backup());self.a.restore_backup(bundle,preview=True)
        self.a.restore_backup(bundle)
        with self.a.connection() as db:self.assertEqual(self.a.instance.get(db,'analytics.source_rules'),value)

    def test_closed_setup_does_not_consume_login_budget(self):
        admin=self.server(True)
        for _ in range(20):self.assertEqual(self.request(admin+'/api/setup/check',{})[0],400)
        self.assertEqual(self.a.AUTH_ATTEMPTS,[])
        for _ in range(20):self.assertTrue(self.a.auth_attempt_allowed('/api/auth/login','client-a'))
        self.assertFalse(self.a.auth_attempt_allowed('/api/auth/login','client-a'))
        self.assertTrue(self.a.auth_attempt_allowed('/api/auth/login','client-b'))
        self.assertTrue(self.a.auth_attempt_allowed('/api/setup','client-a'))

    def test_legacy_campaign_uses_same_alias_projection(self):
        with self.a.connection() as db:db.execute("UPDATE content_blocks SET type='promo' WHERE id='legacy-link-3'")
        self.a.record('click','youtube','Domadoo');self.a.record('click','youtube','block:legacy-link-3')
        day=self.a.datetime.now(self.a.PARIS).date().isoformat();r=self.a.report(day,day)
        self.assertEqual(sum(m['total'] for m in r['campaign_metrics']),2)

    def test_youtube_campaign_is_not_an_instagram_story(self):
        public=self.server();ident=self.promo();link=self.a.story_link(ident,'youtube')
        from urllib.parse import urlsplit
        self.assertEqual(self.redirect(public+urlsplit(link['url']).path)[0],302)
        self.assertEqual(self.a.pulse_stats()['total'],1);self.assertEqual(self.a.pulse_stats()['stories'],0)
        link=self.a.story_link(ident,'instagram');self.redirect(public+urlsplit(link['url']).path)
        self.assertEqual(self.a.pulse_stats()['stories'],1)
        self.a.record('story','instagram-story','story:uncertain')
        self.assertEqual(self.a.pulse_stats()['stories'],1)  # Historical generic shares have no proven platform.

class DescriptionTests(unittest.TestCase):
    for name in ('setUp','tearDown','server','request','template','draft','editable','edit_payload','tracking_state','link','reference','doc','store','proposal','compare'):
        locals()[name]=getattr(WorkflowTests,name)

    def test_automatic_duplicate_has_stable_partner(self):
        url='https://www.domadoo.fr/fr/1-hub.html?domid=117'
        self.link('SMLIGHT SMHub Nano MG24',url)
        doc,ident=self.proposal(self.doc(),url=url)
        op=next(o for o in self.compare(doc)['operations'] if o['id']==ident)
        self.assertNotEqual(op['status'],'obsolete')

class MerchantTests(unittest.TestCase):
    for name in ('setUp','tearDown','server','request','template','draft','editable','edit_payload','tracking_state','link','document','reference','payload','prepare'):
        locals()[name]=getattr(SearchTests,name)
    def test_uuid_amazon_section_has_explicit_business_identity(self):
        doc,p=self.payload()
        for section in doc['template_snapshot']['sections']:
            for sub in section['merchants']:
                if sub['id']=='amazon':sub.update(id='custom-amazon-uuid',merchant='amazon')
        doc['template_snapshot']=descriptions.validate_template(doc['template_snapshot'])
        with self.a.connection() as db:descriptions.update(db,descriptions.TABLES[1],doc['id'],descriptions.validate_document(doc),doc['revision'])
        result=self.prepare(doc,p,'amazon','https://amzn.to/fixture')
        self.assertTrue(any(p['merchant_id']=='custom-amazon-uuid' for p in result['placements']))

class TitleTests(unittest.TestCase):
    def test_html_model_conflicting_with_slug_is_not_silent_success(self):
        result=url_inspection.suggest_title('https://shop.example/reolink-rlc-810a',requester=lambda *args:reply(html='<title>Reolink RLC-820A</title>'),resolver=public_resolver)
        self.assertEqual(result['status'],'unavailable')

del AnalyticsTests,WorkflowTests,SearchTests
if __name__=='__main__':unittest.main()
