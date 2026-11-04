"""Disposable database tests for the new read-only projection and HTTP contract."""
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
import analytics_test
import statistics_workspace


class StatisticsWorkspaceTests(unittest.TestCase):
    setUp = analytics_test.AnalyticsTests.setUp
    tearDown = analytics_test.AnalyticsTests.tearDown
    server = analytics_test.AnalyticsTests.server
    request = analytics_test.AnalyticsTests.request

    def project(self, chosen='2026-11-03', now=None, period='30'):
        at=now or datetime(2026,11,3,12,tzinfo=timezone.utc)
        with self.a.connection() as db:
            blocks=[dict(row) for row in db.execute('SELECT * FROM content_blocks')]
            campaigns=[{**row,'status':self.a.status_of(row,at)} for row in blocks if row['type'] in self.a.CAMPAIGN_TYPES]
            return statistics_workspace.workspace(db,now=at,zone=self.a.PARIS,selected=chosen,period=period,
                aliases=self.a.metric_aliases(db),labels={'block:legacy-link-2':'Renommé'},campaigns=campaigns,
                selection=self.a.select_campaigns(blocks,at),sources={})

    def put(self, rows):
        with self.a.connection() as db:db.executemany('INSERT INTO counts VALUES(?,?,?,?,?)',rows)

    def tracked(self, name='Même titre'):
        with self.a.connection() as db:
            item=self.a.tracked_links.create_link(db,{'name':name,'url':'https://example.org/test'},self.a.story_url_valid,self.a.now_iso())
            source=db.execute('SELECT id FROM tracking_sources LIMIT 1').fetchone()[0]
            token=self.a.tracked_links.token_link(db,item['id'],source,'https://links.example',self.a.now_iso())['token']
            return item['id'],token

    def test_independent_metrics_canonical_aliases_multi_origins_homonyms_and_read_only(self):
        a,token_a=self.tracked();b,token_b=self.tracked()
        self.put([('2026-11-03','youtube','view','page',30),('2026-11-03','youtube','click','Amazon',2),
            ('2026-11-03','youtube','click','block:legacy-link-2',3),
            ('2026-11-03','youtube','tracked','tracked:'+token_a+':10',8),
            ('2026-11-03','instagram','tracked','tracked:'+token_a+':11',3),
            ('2026-11-03','discord','tracked','tracked:'+token_a+':12',1),
            ('2026-11-03','shared-unknown','tracked','tracked:'+token_b+':10',7),
            ('2026-11-02','youtube','view','page',10)])
        with self.a.connection() as db:before='\n'.join(db.iterdump())
        result=self.project()
        self.assertEqual(result['overview']['visits']['total'],30)
        self.assertEqual(result['overview']['public']['total'],5)
        self.assertEqual(result['overview']['tracked']['total'],19)
        self.assertEqual(result['overview']['campaigns']['total'],0)
        items=result['details']['tracked']['items'];self.assertEqual(len(items),2)
        self.assertEqual(items[0]['id'],a);self.assertEqual(items[0]['sources'],{'youtube':8,'instagram':3,'discord':1})
        self.assertEqual(items[1]['sources'],{'shared-unknown':7})
        self.assertEqual(result['details']['public']['items'][0]['id'],'block:legacy-link-2')
        self.assertEqual(result['previous_visits'],10)
        for detail in result['details'].values():
            self.assertEqual(detail['total'],sum(detail['sources'].values()))
            self.assertEqual(detail['total'],sum(item['total'] for item in detail['items']))
        with self.a.connection() as db:self.assertEqual(before,'\n'.join(db.iterdump()))

    def test_orphans_and_empty_days_preserved(self):
        self.put([('2026-11-03','','tracked','tracked:tk_abcdefghijklmnop:10',4),
                  ('2026-11-03','instagram-story','story','story:st_abcdefghijklmnop:10',6)])
        result=self.project();self.assertEqual(result['details']['tracked']['sources'],{'unknown':4})
        self.assertEqual(result['details']['campaigns']['total'],6)
        self.assertEqual(self.project('2001-01-01')['details']['tracked']['items'],[])

    def test_monthly_points_match_daily_cards_including_the_first_comparison(self):
        _, token = self.tracked()
        self.put([('2026-10-04','youtube','view','page',4),
                  ('2026-10-05','youtube','view','page',6),
                  ('2026-10-05','youtube','click','Amazon',7),
                  ('2026-10-05','instagram','tracked','tracked:'+token+':11',3),
                  ('2026-10-05','youtube','tracked','tracked:'+token+':10',5),
                  ('2026-10-05','instagram','story','story:st_abcdefghijklmnop:10',2),
                  ('2026-10-05','youtube','story','story:st_abcdefghijklmnop:11',4)])
        result = self.project('2026-10-05')
        first, empty = result['series'][:2]
        self.assertEqual(first['day'], '2026-10-05')
        self.assertEqual(first['previous_visits'], 4)
        for metric in ('visits','public','tracked','campaigns'):
            self.assertEqual(first[metric], result['details'][metric]['total'])
        self.assertEqual(first['tracked_sources'], {'youtube':5,'instagram':3})
        self.assertEqual(first['campaign_count'], 1)
        self.assertEqual(first['top_campaigns'][0]['total'], 6)
        self.assertEqual(empty['previous_visits'], 6)
        self.assertEqual(empty['tracked_sources'], {})
        self.assertEqual(empty['top_campaigns'], [])

    def test_codes_group_hours_and_sources_but_keep_distinct_codes(self):
        def snapshot(code, hour):
            return json.dumps({'id':'retired-campaign','name':'Offre historique',
                               'code':code,'timestamp':hour})
        self.put([('2026-11-03','youtube','promo_code_copy',snapshot('TEST10','10:00'),3),
                  ('2026-11-03','youtube','promo_code_copy',snapshot('TEST10','11:00'),4),
                  ('2026-11-03','instagram','promo_code_copy',snapshot('TEST10','12:00'),2),
                  ('2026-11-03','youtube','promo_code_copy',snapshot('TEST20','10:00'),5)])
        with self.a.connection() as db:before='\n'.join(db.iterdump())
        result=self.project()
        detail=result['details']['copies']
        self.assertEqual(detail['total'],14)
        self.assertEqual(detail['sources'],{'youtube':12,'instagram':2})
        self.assertEqual(len(detail['items']),2)
        self.assertEqual(detail['items'][0]['name'],'Offre historique · TEST10')
        self.assertEqual(detail['items'][0]['total'],9)
        self.assertEqual(result['detail_series'][-1]['copies'],14)
        self.assertEqual(result['series'][-1]['copies'],14)
        self.assertEqual(self.project('2001-01-01')['details']['copies']['total'],0)
        with self.a.connection() as db:self.assertEqual(before,'\n'.join(db.iterdump()))

    def test_period_totals_cover_30_days_for_every_metric_and_selected_day_stays_separate(self):
        _, token = self.tracked()
        code = json.dumps({'id':'campaign','name':'Offre','code':'TEST10','timestamp':'10:00'})
        keys = [('view','page'),('click','Amazon'),('tracked','tracked:'+token+':10'),
                ('story','story:st_abcdefghijklmnop:10'),('promo_code_copy',code)]
        self.put([(day,source,kind,key,total)
                  for day,source,total in [('2026-10-04','youtube',100),('2026-10-05','youtube',2),
                                            ('2026-11-02','instagram',3),('2026-11-03','youtube',4)]
                  for kind,key in keys])
        result = self.project('2026-11-02')
        for metric, report in result['period_details'].items():
            self.assertEqual(report['total'],9,metric)
            self.assertEqual(report['sources'],{'youtube':6,'instagram':3})
            self.assertEqual(len(report['items']),2 if metric=='visits' else 1)
            self.assertEqual(sum(row[metric] for row in result['series']),9)
            self.assertEqual(result['details'][metric]['total'],3)
        monthly = self.project('2026-11-02',period='month')
        self.assertTrue(all(report['total']==7 for report in monthly['period_details'].values()))
        self.assertTrue(all(report['total']==100 for report in result['previous_period_details'].values()))
        self.assertEqual(result['comparison'],{'from':'2026-09-05','to':'2026-10-04','days':30})
        self.assertTrue(all(report['total']==0 for report in result['previous_details'].values()))

    def test_campaign_performance_and_partner_metadata_use_recorded_sources_and_current_links(self):
        ident, token = self.tracked()
        with self.a.connection() as db:
            partner=db.execute("SELECT id FROM affiliate_partners WHERE name='Domadoo'").fetchone()[0]
            db.execute('INSERT INTO tracked_link_partners(link_id,partner_id) VALUES(?,?)',(ident,partner))
            campaign=self.a.save_content(db,self.a.block_data({'type':'promo','internal_name':'Offre',
                'title':'Offre','url':'https://example.org/offer'}))
        snapshot=json.dumps({'id':campaign,'name':'Offre','code':'TEST10','timestamp':'10:00'})
        self.put([('2026-11-03','youtube','impression','block:'+campaign,100),
                  ('2026-11-03','youtube','click','block:'+campaign,20),
                  ('2026-11-03','youtube','promo_code_copy',snapshot,5),
                  ('2026-11-02','instagram','impression','block:'+campaign,40),
                  ('2026-11-02','instagram','promo_code_copy',snapshot,2),
                  ('2026-11-03','youtube','tracked','tracked:'+token+':10',8),
                  ('2026-11-02','youtube','tracked','tracked:'+token+':10',4)])
        with self.a.connection() as db:before='\n'.join(db.iterdump())
        result=self.project()
        self.assertEqual(result['performance'][0]['sources'],{'youtube':{'impressions':100,'clicks':20,'copies':5}})
        self.assertEqual(result['period_performance'][0]['sources']['instagram'],{'impressions':40,'clicks':0,'copies':2})
        self.assertEqual(result['details']['tracked']['items'][0]['partner_id'],partner)
        self.assertEqual(result['previous_details']['tracked']['total'],4)
        self.assertEqual(result['details']['copies']['items'][0]['campaign_id'],campaign)
        with self.a.connection() as db:self.assertEqual(before,'\n'.join(db.iterdump()))

    def test_campaign_eligibility_zero_to_four_and_archived(self):
        ids=[]
        for n in range(5):
            result=self.project();self.assertEqual(result['active_count'],n)
            self.assertEqual(len(result['active_campaigns']),min(3,n))
            self.assertTrue(all(item['total']==0 for item in result['active_campaigns']))
            if n<4:
                with self.a.connection() as db:
                    ident=self.a.save_content(db,self.a.block_data({'type':'promo','internal_name':'Campagne '+str(n),'title':'Offre','url':'https://example.org/offer'}))
                    ids.append(ident)
        with self.a.connection() as db:
            db.execute('UPDATE content_blocks SET archived=1 WHERE id=?',(ids[0],))
            db.execute("UPDATE content_blocks SET end_at='2026-10-01T00:00:00Z' WHERE id=?",(ids[1],))
            db.execute("UPDATE content_blocks SET start_at='2027-01-01T00:00:00Z' WHERE id=?",(ids[2],))
            db.execute('UPDATE content_blocks SET draft=1 WHERE id=?',(ids[3],))
        self.assertEqual(self.project()['active_count'],0)

    def test_dst_historical_local_days_and_month_boundary(self):
        self.put([(day,'youtube','view','page',n) for day,n in [('2026-03-28',1),('2026-03-29',2),('2026-03-30',3),('2026-10-24',4),('2026-10-25',5),('2026-10-26',6)]])
        for day,total in [('2026-03-29',2),('2026-10-25',5)]:
            result=self.project(day);self.assertEqual(result['details']['visits']['total'],total)
            self.assertEqual(result['detail_series'][-1]['visits'],total)
        at=datetime(2026,10,31,23,30,tzinfo=timezone.utc)
        result=self.project('2026-11-01',at,'month')
        self.assertEqual(result['today'],'2026-11-01');self.assertEqual(len(result['series']),1)
        with self.assertRaises(ValueError):self.project('2026-11-04')
        with self.assertRaises(ValueError):self.project(period='invalid')

    def test_http_auth_static_files_and_validations(self):
        origin=self.server(True)
        for path in ['/api/stats/workspace','/statistics-workspace.js','/statistics-workspace.css']:
            self.assertEqual(self.request(origin+path)[0],200,path)
        self.assertEqual(self.request(origin+'/api/stats/workspace?date=bad')[0],400)
        self.assertEqual(self.request(origin+'/api/stats/workspace?period=bad')[0],400)
        self.assertEqual(self.request(self.server(False)+'/api/stats/workspace')[0],404)
        with self.a.connection() as db:db.execute("UPDATE settings SET value='local' WHERE key='auth.mode'")
        self.assertEqual(self.request(origin+'/api/stats/workspace')[0],401)

    def test_collection_boundaries_across_both_clock_changes(self):
        # Exercise the unchanged collector, including the repeated autumn hour.
        instants=['2026-03-28T22:59:59+00:00','2026-03-28T23:00:00+00:00',
                  '2026-03-29T00:59:59+00:00','2026-03-29T01:00:00+00:00',
                  '2026-03-29T21:59:59+00:00','2026-03-29T22:00:00+00:00',
                  '2026-10-24T21:59:59+00:00','2026-10-24T22:00:00+00:00',
                  '2026-10-25T00:30:00+00:00','2026-10-25T01:30:00+00:00',
                  '2026-10-25T22:59:59+00:00','2026-10-25T23:00:00+00:00']
        for value in instants:
            at=datetime.fromisoformat(value)
            with patch.object(self.a,'datetime') as clock:
                clock.now.side_effect=lambda zone:at.astimezone(zone)
                self.a.record('view','youtube','page')
        expected={'2026-03-28':1,'2026-03-29':4,'2026-03-30':1,
                  '2026-10-24':1,'2026-10-25':4,'2026-10-26':1}
        for day,total in expected.items():self.assertEqual(self.project(day)['details']['visits']['total'],total)


if __name__=='__main__':unittest.main()
