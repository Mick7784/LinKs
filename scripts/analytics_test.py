from images_test import raster
import base64, importlib.util, json, os, tempfile, threading, unittest
from datetime import date
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
from pathlib import Path
from fixtures import prepare,populate

class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        os.environ['ANALYTICS_DB']=self.tmp.name+'/stats.db'
        os.environ['UPLOAD_DIR']=self.tmp.name+'/uploads'
        prepare(os.environ['ANALYTICS_DB'])
        spec=importlib.util.spec_from_file_location('analytics',Path(__file__).with_name('analytics.py'))
        self.a=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.a);self.a.init();populate(self.a)
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
            with urlopen(Request(url,json.dumps(data).encode() if data is not None else None,{'X-Links-Request':'1',**(headers or {})},method=method)) as r:return r.status,r.read()
        except HTTPError as e:return e.code,e.read()
    def promo(self,name='Domadoo - Aquara days',url='https://partner.example/offer?aff=117'):
        with self.a.connection() as db:
            return self.a.save_content(db,self.a.block_data({'type':'promo','internal_name':name,'title':'Offre publique','url':url}))
    def redirect(self,url,method=None,agent='Mozilla/5.0',headers=None):
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self,*args):return None
        try:
            response=build_opener(NoRedirect).open(Request(url,headers={'User-Agent':agent,**(headers or {})},method=method))
        except HTTPError as exc:response=exc
        with response:return response.code,dict(response.headers)

    def test_private_tracked_links_sources_permanent_tokens_and_history(self):
        admin=self.server(True);public=self.server()
        status,body=self.request(admin+'/api/tracked-links',{'name':'Chargeur UGREEN','url':'https://shop.example/first'})
        self.assertEqual(status,201,body);link_id=json.loads(body)['id']
        self.assertNotIn('category',json.loads(body))
        self.assertNotIn(link_id,json.dumps(self.a.public_config()))
        sources=json.loads(self.request(admin+'/api/tracking-sources')[1])['items']
        self.assertTrue(any(x['name']=='Instagram Story' for x in sources))
        status,body=self.request(admin+'/api/tracking-sources',{'name':'YouTube Post perso'})
        self.assertEqual(status,201,body);source_id=json.loads(body)['id']
        endpoint=admin+'/api/tracked-links/'+link_id+'/token'
        status,body=self.request(endpoint,{'source_id':source_id});self.assertEqual(status,200,body)
        generated=json.loads(body);url=generated['url'];token=generated['token'];code=generated['code']
        self.assertRegex(token,r'^tk_[A-Za-z0-9_-]{16}$')
        self.assertRegex(code,r'^[A-Za-z0-9_-]{9}$')
        self.assertEqual(url,self.a.ORIGIN+'/'+code)
        self.assertEqual(json.loads(self.request(endpoint,{'source_id':source_id})[1])['url'],url)
        self.assertEqual(self.redirect(public+'/'+code)[0],302)
        self.assertEqual(self.redirect(public+'/'+code,method='HEAD')[0],302)
        self.assertEqual(self.redirect(public+'/go/'+token)[0],302)
        self.assertEqual(self.redirect(public+'/go/'+token,method='HEAD')[0],302)
        self.assertEqual(self.redirect(public+'/go/'+token,agent='Googlebot')[0],302)
        rows=json.loads(self.request(admin+'/api/tracked-links')[1])['items']
        item=next(x for x in rows if x['id']==link_id)
        self.assertNotIn('category',item)
        self.assertEqual(item['clicks'],2)
        self.assertEqual(item['sources'][0]['name'],'YouTube Post perso')
        day=self.a.datetime.now(self.a.PARIS).date().isoformat()
        report=self.a.report(day,day)
        self.assertEqual(sum(x['total'] for x in report['tracked']),2)
        self.assertEqual(len(report['stories']),0)
        self.assertEqual(sum(x['total'] for x in report['rows']),0)
        status,_=self.request(admin+'/api/tracked-links/'+link_id,{'name':'Chargeur UGREEN','url':'https://shop.example/second'},method='PUT')
        self.assertEqual(status,200)
        self.assertEqual(self.redirect(public+'/go/'+token)[1]['Location'],'https://shop.example/second')
        self.assertEqual(json.loads(self.request(endpoint,{'source_id':source_id})[1])['url'],url)
        source_endpoint=admin+'/api/tracking-sources/'+source_id
        self.assertEqual(self.request(source_endpoint,method='DELETE')[0],200)
        archived=next(x for x in json.loads(self.request(admin+'/api/tracking-sources')[1])['items'] if x['id']==source_id)
        self.assertFalse(archived['active'])
        self.assertEqual(archived['clicks'],3)
        self.assertEqual(self.redirect(public+'/go/'+token)[0],302)
        self.assertEqual(self.request(source_endpoint+'/restore',{},method='POST')[0],200)
        self.assertEqual(self.request(source_endpoint,{'name':'YouTube communautaire'},method='PUT')[0],200)
        self.assertEqual(self.redirect(public+'/go/'+token)[0],302)
        self.assertEqual(self.request(admin+'/api/tracked-links/'+link_id+'/archive',{})[0],200)
        self.assertEqual(self.redirect(public+'/go/'+token)[0],302)
        self.assertEqual(self.request(admin+'/api/tracked-links/'+link_id+'/disable',{})[0],200)
        self.assertEqual(self.redirect(public+'/go/'+token)[0],410)
        self.assertEqual(self.request(admin+'/api/tracked-links/'+link_id+'/enable',{})[0],200)
        self.assertEqual(self.request(admin+'/api/tracked-links/'+link_id+'/restore',{})[0],200)
        self.assertEqual(self.redirect(public+'/go/'+token)[0],302)
        backup=json.loads(self.a.export_backup())
        self.a.restore_backup(backup)
        self.assertEqual(self.redirect(public+'/go/'+token)[0],302)
        old=dict(backup);old['tables']=dict(backup['tables'])
        for table in self.a.TRACKING_BACKUP_TABLES:old['tables'].pop(table)
        old['tables']['counts']=[row for row in backup['tables']['counts'] if row['kind']!='tracked']
        self.a.restore_backup(old)
        self.assertEqual(self.redirect(public+'/go/'+token)[0],302)
        self.assertGreaterEqual(next(x for x in json.loads(self.request(admin+'/api/tracked-links')[1])['items'] if x['id']==link_id)['clicks'],5)
        self.a.init()
        self.assertEqual(self.redirect(public+'/go/'+token)[0],302)

    def test_categories_are_ignored_without_recreating_the_column_or_changing_share_urls(self):
        admin=self.server(True);public=self.server()
        with self.a.connection() as db:
            columns=[row['name'] for row in db.execute('PRAGMA table_info(tracked_links)')]
            self.assertNotIn('category',columns)
            partner=next(row for row in self.a.affiliate_partners.rows(db) if row['name']=='Reolink')
            source=self.a.tracked_links.source_rows(db)[0]['id']
        expected_keys={'id','name','url','notes','archived','enabled','created_at','updated_at',
                       'sources','clicks','period_clicks','partner_id','original_url'}
        identifiers=[]
        for affiliated in (False,True):
            for index,legacy_field in enumerate(({}, {'category':'Ancienne catégorie'}, {'category':{'obsolete':True}})):
                with self.subTest(affiliated=affiliated,legacy_field=legacy_field):
                    origin='https://shop.reolink.com/product-'+str(int(affiliated))+'-'+str(index)+'?x=a%2Bb&x=c+d#details'
                    destination=origin.replace('#','&aff=1404#') if affiliated else origin
                    fields={'name':'Lien identifié '+str(index),'url':origin,'notes':'Notes conservées : été + %2B.'}
                    if affiliated:fields.update(partner_id=partner['id'],expected_url=destination)
                    status,body=self.request(admin+'/api/tracked-links',{**fields,**legacy_field})
                    self.assertEqual(status,201,body);saved=json.loads(body);ident=saved['id'];identifiers.append(ident)
                    self.assertNotIn('category',saved)
                    self.assertEqual((saved['name'],saved['url']),(fields['name'],destination))
                    with self.a.connection() as db:
                        row=db.execute('SELECT * FROM tracked_links WHERE id=?',(ident,)).fetchone()
                        self.assertNotIn('category',row.keys(),'Legacy request fields must not be stored')
                        created_at=row['created_at']
                    token=json.loads(self.request(admin+'/api/tracked-links/'+ident+'/token',{'source_id':source})[1])
                    with self.a.connection() as db:
                        db.execute('UPDATE tracked_tokens SET click_total=9 WHERE token=?',(token['token'],))
                    update={**fields,'name':'Nom mis à jour '+str(index),'category':['ignored'],
                            'previous_url':destination}
                    status,body=self.request(admin+'/api/tracked-links/'+ident,update,method='PUT')
                    self.assertEqual(status,200,body);self.assertNotIn('category',json.loads(body))
                    current=next(row for row in json.loads(self.request(admin+'/api/tracked-links')[1])['items'] if row['id']==ident)
                    self.assertEqual(set(current),expected_keys)
                    self.assertEqual((current['name'],current['url'],current['original_url'],current['notes'],current['clicks']),
                                     (update['name'],destination,origin,fields['notes'],9))
                    self.assertEqual(current['partner_id'],partner['id'] if affiliated else '')
                    self.assertEqual(current['created_at'],created_at)
                    reused=json.loads(self.request(admin+'/api/tracked-links/'+ident+'/token',{'source_id':source})[1])
                    self.assertEqual(reused,token)
                    self.assertEqual(self.redirect(public+'/'+token['code'],method='HEAD')[1]['Location'],destination)
        self.a.init()
        with self.a.connection() as db:
            self.assertEqual([row['name'] for row in db.execute('PRAGMA table_info(tracked_links)')],columns)
        backup=json.loads(self.a.export_backup())
        self.assertTrue(all('category' not in row for row in backup['tables']['tracked_links']))
        with self.a.connection() as db:
            self.assertEqual(len(identifiers),6)
            self.assertNotIn('category',[row['name'] for row in db.execute('PRAGMA table_info(tracked_links)')])

    def test_tracked_link_http_writes_keep_name_required_without_categories(self):
        admin=self.server(True)
        valid={'name':'Nom obligatoire','url':'https://example.org/required-name','notes':'À conserver'}
        ident=json.loads(self.request(admin+'/api/tracked-links',valid)[1])['id']
        before=json.loads(self.request(admin+'/api/tracked-links')[1])
        for invalid in ({},{'name':''},{'name':'   '},{'name':None},{'name':'x'*161}):
            for method,path in [('POST','/api/tracked-links'),('PUT','/api/tracked-links/'+ident)]:
                with self.subTest(invalid=invalid,method=method):
                    status,body=self.request(admin+path,{'url':valid['url'],'notes':valid['notes'],**invalid},method=method)
                    self.assertEqual(status,400,body)
                    self.assertEqual(json.loads(self.request(admin+'/api/tracked-links')[1]),before)

    def test_opaque_campaign_alias_is_stable_source_bound_and_legacy_safe(self):
        admin=self.server(True);public=self.server();promotion=self.promo()
        endpoint=admin+'/api/content/'+promotion+'/story-link'
        status,body=self.request(endpoint,{'source':'youtube'})
        self.assertEqual(status,200,body)
        short=json.loads(body)['url'];code=short.rsplit('/',1)[-1]
        self.assertRegex(code,r'^[A-Za-z0-9_-]{9}$')
        self.assertNotIn('utm_source',short);self.assertNotIn('/go/',short)
        self.assertEqual(json.loads(self.request(endpoint,{'source':'youtube'})[1])['url'],short)
        insta=json.loads(self.request(endpoint,{'source':'instagram'})[1])['url']
        self.assertNotEqual(short,insta)
        old=json.loads(self.request(endpoint,{})[1])['url'];legacy=old.rsplit('/',1)[-1]
        self.assertEqual(self.redirect(public+'/'+code)[1]['Location'],'https://partner.example/offer?aff=117')
        self.assertEqual(self.redirect(public+'/'+insta.rsplit('/',1)[-1])[0],302)
        self.assertEqual(self.redirect(public+'/'+code,method='HEAD')[0],302)
        self.assertEqual(self.redirect(public+'/'+code,agent='Googlebot')[0],302)
        self.assertEqual(self.redirect(public+'/go/'+legacy+'?utm_source=youtube')[0],302)
        today=self.a.datetime.now(self.a.PARIS).date().isoformat()
        reports=self.a.report(today,today)
        self.assertEqual(sum(r['total'] for r in reports['stories']),3)
        self.assertEqual(sum(r['total'] for r in self.a.report(today,today,'youtube')['stories']),2)
        self.assertEqual(sum(r['total'] for r in self.a.report(today,today,'instagram')['stories']),1)
        self.assertEqual(len({r['token'] for r in reports['stories']}),1)
        self.assertEqual(self.a.story_link(promotion)['url'],old)
        with self.a.connection() as db:db.execute("UPDATE content_blocks SET url=? WHERE id=?",('https://partner.example/new-destination',promotion))
        self.assertEqual(self.redirect(public+'/'+code)[1]['Location'],'https://partner.example/new-destination')
        backup=json.loads(self.a.export_backup())
        self.assertIn('short_aliases',backup['tables'])
        self.a.restore_backup(backup)
        self.assertEqual(self.redirect(public+'/'+code)[0],302)
        original=dict(backup);original['tables']=dict(backup['tables']);del original['tables']['short_aliases']
        original['tables']['counts']=[r for r in original['tables']['counts'] if r['kind']!='story']
        self.a.restore_backup(original)
        self.assertEqual(self.redirect(public+'/'+code)[0],302)
        self.assertEqual(self.redirect(public+'/go/'+legacy+'?utm_source=youtube')[0],302)
        self.assertGreaterEqual(sum(r['total'] for r in self.a.report(today,today)['stories']),4)

    def test_zero_click_published_short_alias_remains_reserved_and_active(self):
        admin=self.server(True);public=self.server()
        link=json.loads(self.request(admin+'/api/tracked-links',{'name':'Sans clic','url':'https://shop.example/item'})[1])
        source=json.loads(self.request(admin+'/api/tracking-sources',{'name':'Source éphémère'})[1])
        payload=json.loads(self.request(admin+'/api/tracked-links/'+link['id']+'/token',{'source_id':source['id']})[1])
        code=payload['code'];self.assertEqual(self.redirect(public+'/'+code,method='HEAD')[0],302)
        self.assertEqual(self.request(admin+'/api/tracking-sources/'+source['id'],method='DELETE')[0],200)
        self.assertEqual(self.redirect(public+'/'+code)[0],302)
        with self.a.connection() as db:self.assertEqual(db.execute("SELECT revoked FROM short_aliases WHERE code=?",(code,)).fetchone()[0],0)
        self.a.restore_backup(json.loads(self.a.export_backup()))
        self.assertEqual(self.redirect(public+'/'+code)[0],302)

    def test_custom_sources_on_campaigns_are_retained_after_clicks(self):
        admin=self.server(True);public=self.server();campaign_id=self.promo()
        source=json.loads(self.request(admin+'/api/tracking-sources',{'name':'Blog partenaire'})[1])
        link=json.loads(self.request(admin+'/api/content/'+campaign_id+'/story-link',{})[1])['url']
        local_link=public+'/go/'+link.rsplit('/go/',1)[-1]
        status,headers=self.redirect(local_link+'?utm_source=src_'+source['id'])
        self.assertEqual(status,302)
        sources=json.loads(self.request(admin+'/api/tracking-sources')[1])['items']
        selected=next(row for row in sources if row['id']==source['id'])
        self.assertEqual(selected['clicks'],1)
        day=self.a.datetime.now(self.a.PARIS).date().isoformat()
        report=self.a.report(day,day)
        self.assertEqual(len(report['stories']),1)
        self.assertEqual(report['stories'][0]['source'],'tracked:'+source['id'])
        self.assertEqual(report['source_names']['tracked:'+source['id']],'Blog partenaire')
        result=json.loads(self.request(admin+'/api/tracking-sources/'+source['id'],method='DELETE')[1])
        self.assertEqual(result['action'],'archived')
        self.assertEqual(self.redirect(local_link+'?utm_source=src_'+source['id'])[0],302)
        backup=json.loads(self.a.export_backup());self.a.restore_backup(backup)
        selected=next(row for row in json.loads(self.request(admin+'/api/tracking-sources')[1])['items'] if row['id']==source['id'])
        self.assertEqual(selected['clicks'],2)

    def test_report_resolves_configured_source_keys_and_unambiguous_aliases(self):
        rules=[{'key':'youtube-post','label':'YouTube Post','aliases':['track.194726hflqjr','old-youtube','ambiguous'],'domains':[]},
               {'key':'partner','label':'Partenaire','aliases':['ambiguous','youtube-post'],'domains':[]}]
        day='2026-10-25'
        with self.a.connection() as db:
            self.a.instance.put(db,'analytics.source_rules',json.dumps(rules))
        for key in ['track.194726hflqjr','old-youtube','ambiguous','track.unknown']:
            self.a.record('view',key,'',day)
        before=json.loads(self.a.export_backup())['tables']
        report=self.a.report(day,day)
        self.assertEqual(report['source_names']['track.194726hflqjr'],'YouTube Post')
        self.assertEqual(report['source_names']['youtube-post'],'YouTube Post')
        self.assertEqual(report['source_names']['old-youtube'],'YouTube Post')
        self.assertNotIn('ambiguous',report['source_names'])
        self.assertNotIn('track.unknown',report['source_names'])
        self.assertEqual({row['source'] for row in report['rows']},
                         {'track.194726hflqjr','old-youtube','ambiguous','track.unknown'})
        self.assertEqual(sum(row['total'] for row in self.a.report(day,day,'track.194726hflqjr')['rows']),1)
        self.assertEqual(json.loads(self.a.export_backup())['tables'],before)

    def test_report_shared_sources_use_stable_bindings_without_guessing_history(self):
        campaign=self.promo();token=self.a.story_link(campaign)['url'].rsplit('/',1)[-1]
        day='2026-10-25'
        with self.a.connection() as db:
            source_id=db.execute("SELECT source_id FROM tracking_source_keys WHERE key='youtube'").fetchone()[0]
            db.execute("UPDATE tracking_sources SET name='YouTube Post renommé',active=0 WHERE id=?",(source_id,))
            # A new namesake must not take ownership of the old identity.
            db.execute("INSERT INTO tracking_sources VALUES(?,?,1,0,?)",('a'*32,'YouTube Post',self.a.now_iso()))
            link=self.a.tracked_links.create_link(db,{'name':'Lien suivi','url':'https://shop.example/report'},self.a.story_url_valid,self.a.now_iso())
            other=db.execute("SELECT id FROM tracking_sources WHERE name='YouTube Description'").fetchone()[0]
            tracked=self.a.tracked_links.token_link(db,link['id'],other,self.a.ORIGIN,self.a.now_iso())
        keys=['youtube','tracked:'+source_id,'instagram-story','shared-unknown','tracked:'+'b'*32]
        for key in keys:self.a.record('story',key,'story:'+token+':10',day)
        self.a.record('tracked','tracked:'+other,'tracked:'+tracked['token']+':10',day)
        self.a.record('click','youtube','block:'+campaign,day)
        before=json.loads(self.a.export_backup())['tables']
        report=self.a.report(day,day);stories={row['source']:row for row in report['stories']}
        for key in keys[:2]:self.assertEqual(stories[key]['source_name'],'YouTube Post renommé')
        for key in keys[2:]:self.assertIsNone(stories[key]['source_name'])
        self.assertNotIn('youtube',report['source_names'])  # Public traffic remains generic YouTube.
        self.assertEqual(report['tracked'][0]['source_name'],'YouTube Description')
        self.assertEqual(sum(row['total'] for row in report['stories']),5)
        self.assertEqual(len(self.a.report(day,day,'youtube')['stories']),1)
        self.assertEqual(json.loads(self.a.export_backup())['tables'],before)
        with self.a.connection() as db:db.execute("UPDATE tracking_source_keys SET source_id=NULL WHERE key='youtube'")
        unresolved=next(row for row in self.a.report(day,day)['stories'] if row['source']=='youtube')
        self.assertIsNone(unresolved['source_name'])  # Do not guess from the new namesake.

    def test_zero_click_source_with_published_token_is_archived(self):
        admin=self.server(True);public=self.server()
        link=json.loads(self.request(admin+'/api/tracked-links',{'name':'Sans clic','url':'https://shop.example/item'})[1])
        source=json.loads(self.request(admin+'/api/tracking-sources',{'name':'Essai zéro clic'})[1])
        token=json.loads(self.request(admin+'/api/tracked-links/'+link['id']+'/token',{'source_id':source['id']})[1])['token']
        result=json.loads(self.request(admin+'/api/tracking-sources/'+source['id'],method='DELETE')[1])
        self.assertEqual(result['action'],'archived')
        self.assertEqual(self.redirect(public+'/go/'+token)[0],302)
        self.a.init()
        sources=json.loads(self.request(admin+'/api/tracking-sources')[1])['items']
        self.assertTrue(any(x['id']==source['id'] and not x['active'] for x in sources))

    def test_story_complete_journey_and_preserved_page_metrics(self):
        admin=self.server(True);public=self.server();item_id=self.promo()
        endpoint=admin+'/api/content/'+item_id+'/story-link'
        status,body=self.request(endpoint,{});self.assertEqual(status,200)
        link=json.loads(body)['url'];token=link.rsplit('/',1)[-1]
        self.assertRegex(token,r'^st_[A-Za-z0-9_-]{16}$')
        self.assertEqual(json.loads(self.request(endpoint,{})[1])['url'],link)
        self.a.init();self.assertEqual(self.a.story_link(item_id)['url'],link)
        day=self.a.datetime.now(self.a.PARIS).date().isoformat()
        self.a.record('view','instagram','',day);self.a.record('click','instagram','block:'+item_id,day)
        code,headers=self.redirect(public+'/go/'+token)
        self.assertEqual(code,302);self.assertEqual(headers['Location'],'https://partner.example/offer?aff=117')
        self.assertEqual(headers['Cache-Control'],'no-store')
        report=self.a.report(day,day)
        self.assertEqual(sum(x['total'] for x in report['rows']),2)
        self.assertEqual(sum(x['total'] for x in report['stories']),1)
        row=report['stories'][0];self.assertEqual(row['label'],'Domadoo - Aquara days');self.assertEqual(row['promotion_id'],item_id);self.assertRegex(row['hour'],r'^\d{2}$')
        self.assertEqual(len(self.a.report(day,day,'shared-unknown')['stories']),1)
        self.assertEqual(self.a.report(day,day,'instagram')['stories'],[])
        self.assertEqual(self.a.report(day,day,'youtube')['stories'],[])
        self.assertEqual(self.a.report('2000-01-01','2000-01-01')['stories'],[])
        with self.a.connection() as db:db.execute('UPDATE content_blocks SET url=?,internal_name=? WHERE id=?',('https://partner.example/new?aff=117','Promotion renommée',item_id))
        self.assertEqual(self.redirect(public+'/go/'+token)[1]['Location'],'https://partner.example/new?aff=117')
        self.assertEqual(self.a.report(day,day)['stories'][0]['label'],'Promotion renommée')
        self.assertEqual(self.request(admin+'/api/content/'+item_id+'/archive',{})[0],204)
        self.assertEqual(self.redirect(public+'/go/'+token)[0],302)
        self.assertEqual(sum(x['total'] for x in self.a.report(day,day)['stories']),3)
        self.assertEqual(self.request(admin+'/api/content/'+item_id,method='DELETE')[0],204)
        self.assertEqual(self.redirect(public+'/go/'+token,method='HEAD')[0],302)
        self.assertEqual(self.a.report(day,day)['stories'][0]['label'],'Promotion renommée')
        self.assertEqual(sum(x['total'] for x in self.a.report(day,day)['stories']),3)

    def test_shared_links_keep_stable_tokens_and_attribute_platforms(self):
        item_id=self.promo();base=self.a.story_link(item_id)['url'];token=base.rsplit('/',1)[-1]
        public=self.server();day=self.a.datetime.now(self.a.PARIS).date().isoformat()
        for platform in ('instagram','youtube','facebook'):
            self.assertEqual(self.redirect(public+'/go/'+token+'?utm_source='+platform)[0],302)
            self.assertEqual(self.a.report(day,day,platform)['stories'][0]['source'],platform)
        self.assertEqual(self.redirect(public+'/go/'+token+'?utm_source=unknown')[0],302)
        self.assertEqual(self.a.report(day,day,'shared-unknown')['stories'][0]['total'],1)
        self.assertEqual(self.a.story_link(item_id)['url'],base)
        with self.a.connection() as db:
            db.execute("INSERT INTO counts VALUES(?,?,?,?,?)",(day,'instagram-story','story','story:'+token+':01',13))
        legacy=self.a.report(day,day,'instagram-story')['stories']
        self.assertEqual(sum(row['total'] for row in legacy),13)
        self.assertEqual(sum(row['total'] for row in self.a.report(day,day)['stories']),17)

    def test_story_concurrency_unique_codes_and_no_bot_counts(self):
        admin=self.server(True);item_id=self.promo();results=[]
        threads=[threading.Thread(target=lambda:results.append(self.a.story_link(item_id)['url'])) for _ in range(8)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(len(set(results)),1)
        token=results[0].rsplit('/',1)[-1];url=self.server()+'/go/'+token
        for agent in ['facebookexternalhit/1.1','meta-externalagent','Googlebot','HeadlessChrome']:
            self.assertEqual(self.redirect(url,agent=agent)[0],302)
        self.assertEqual(self.redirect(url,method='HEAD')[0],302)
        with self.a.connection() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM counts WHERE kind='story'").fetchone()[0],0)
        for invalid in ['missing','st_'+'x'*16]:self.assertEqual(self.redirect(self.server()+'/go/'+invalid)[0],404)
        second=self.promo('Une autre promotion')
        self.assertNotEqual(self.a.story_link(second)['url'],results[0])
        status,body=self.request(admin+'/api/content/'+item_id+'/duplicate',{});self.assertEqual(status,201)
        self.assertNotEqual(self.a.story_link(json.loads(body)['id'])['url'],results[0])

    def test_restore_before_story_creation_keeps_published_link_usable(self):
        item_id=self.promo()
        before=json.loads(self.a.export_backup())
        link=self.a.story_link(item_id)['url']
        self.a.restore_backup(before)
        self.assertEqual(self.a.story_link(item_id)['url'],link)
        public=self.server()
        self.assertEqual(self.redirect(public+'/go/'+link.rsplit('/',1)[-1])[0],302)

    def test_story_invalid_destination_and_backup_compatibility(self):
        item_id=self.promo();link=self.a.story_link(item_id)['url'];token=link.rsplit('/',1)[-1];public=self.server()
        for url in ['', 'mailto:a@example.com','https://links.example/go/'+token,'https://partner.example:bad','https://partner.example/\nheader']:
            with self.a.connection() as db:db.execute('UPDATE content_blocks SET url=? WHERE id=?',(url,item_id))
            with self.assertRaises(ValueError):self.a.story_link(item_id)
            self.assertEqual(self.redirect(public+'/go/'+token)[0],410)
        with self.a.connection() as db:db.execute('UPDATE content_blocks SET url=? WHERE id=?',('https://partner.example/été?aff=117',item_id))
        self.assertEqual(self.redirect(public+'/go/'+token)[1]['Location'],'https://partner.example/%C3%A9t%C3%A9?aff=117')
        day=self.a.datetime.now(self.a.PARIS).date().isoformat()
        backup=json.loads(self.a.export_backup());self.a.restore_backup(backup)
        self.assertEqual(self.a.story_link(item_id)['url'],link)
        self.assertEqual(sum(x['total'] for x in self.a.report(day,day)['stories']),1)
        legacy=json.loads(self.a.export_backup());legacy['version']=1;del legacy['tables']['story_links'];legacy['tables']['counts']=[x for x in legacy['tables']['counts'] if x['kind']!='story']
        self.a.restore_backup(legacy)
        self.assertEqual(self.a.story_link(item_id)['url'],link)
        self.assertEqual(sum(x['total'] for x in self.a.report(day,day)['stories']),1)
        bad=json.loads(self.a.export_backup());bad['tables']['story_links'][0]['promotion_id']='different'
        with self.assertRaises(ValueError):self.a.restore_backup(bad)
        self.assertEqual(self.a.story_link(item_id)['url'],link)

    def test_aggregation_persistence_and_dates(self):
        self.a.record('view','youtube','','2026-09-30');self.a.record('view','youtube','','2026-09-30');self.a.record('click','instagram','Amazon','2026-09-30')
        self.a.init()
        rows=self.a.report('2026-09-30','2026-09-30')['rows']
        self.assertEqual(sum(r['total'] for r in rows),3)
        self.assertEqual(self.a.report('2026-09-30','2026-09-30','youtube')['rows'][0]['total'],2)
        self.assertEqual(self.a.report('2026-09-29','2026-09-29')['rows'],[])
        with self.assertRaises(ValueError):self.a.report('2026-10-01','2026-09-01')
    def test_legacy_clicks_share_identity_without_changing_history(self):
        day='2026-09-30'
        for source,key in [('youtube','Domadoo'),('instagram','block:legacy-link-3'),
                           ('youtube','Réseau · Me contacter par e-mail'),('youtube','button:legacy-button-2')]:
            self.a.record('click',source,key,day)
        self.a.record('view','youtube','',day)
        with self.a.connection() as db:
            db.execute("UPDATE content_blocks SET title='Domadoo renommé' WHERE id='legacy-link-3'")
            db.execute("UPDATE top_buttons SET label='Contact' WHERE id='legacy-button-2'")
            before=[tuple(r) for r in db.execute('SELECT * FROM counts ORDER BY kind,link,source')]
        rows=self.a.report(day,day)['rows']
        grouped={}
        for row in rows:
            if row['kind']=='click':grouped[row['link']]=grouped.get(row['link'],0)+row['total']
        self.assertEqual(grouped,{'block:legacy-link-3':2,'button:legacy-button-2':2})
        self.assertEqual(sum(r['total'] for r in rows),5)
        self.assertEqual({r['label'] for r in rows if r['link']=='block:legacy-link-3'},{'Domadoo renommé'})
        self.assertEqual(sum(r['total'] for r in self.a.report(day,day,'instagram')['rows']),1)
        self.assertEqual(next(x for x in self.a.content_list() if x['id']=='legacy-link-3')['clicks'],2)
        self.assertEqual(next(x for x in self.a.button_list() if x['id']=='legacy-button-2')['clicks'],2)
        with self.a.connection() as db:
            self.assertEqual(before,[tuple(r) for r in db.execute('SELECT * FROM counts ORDER BY kind,link,source')])

    def test_same_title_blocks_and_ambiguous_legacy_labels_stay_separate(self):
        admin=self.server(True)
        item={'type':'classic','internal_name':'Autre Domadoo','title':'Domadoo','url':'https://example.com'}
        status,body=self.request(admin+'/api/content',item)
        self.assertEqual(status,201)
        new_id=json.loads(body)['id']
        for key in ['Domadoo','block:legacy-link-3','block:'+new_id]:self.a.record('click','youtube',key,'2026-09-30')
        items={x['id']:x for x in self.a.content_list()}
        self.assertEqual(items['legacy-link-3']['clicks'],2)
        self.assertEqual(items[new_id]['clicks'],1)
        rows=self.a.report('2026-09-30','2026-09-30')['rows']
        self.assertEqual({r['link'] for r in rows},{'block:legacy-link-3','block:'+new_id})
        # Persisted aliases remain stable even when the static config is neutral.
        with self.a.connection() as db:self.assertEqual(self.a.metric_aliases(db)['Domadoo'],'block:legacy-link-3')
        with self.a.connection() as db:
            db.execute("DELETE FROM content_blocks WHERE id='legacy-link-3'")
            self.assertNotIn('Domadoo',self.a.metric_aliases(db))

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
        self.assertEqual(config['profile']['name'],'Test Creator')
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
        with self.a.connection() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM counts WHERE link=?",('block:'+item_id,)).fetchone()[0],1)

    def test_image_upload_is_persistent_and_publicly_readable(self):
        admin=self.server(True)
        png=base64.b64encode(raster()).decode()
        status,body=self.request(admin+'/api/upload',{'type':'image/png','data':png},{'Content-Type':'application/json'})
        self.assertEqual(status,201)
        path=json.loads(body)['url']
        self.assertEqual(self.request(admin+path)[0],200)
        self.assertEqual(self.request(self.server()+path)[0],200)

    def test_promotion_overlap_is_advisory_and_edit_exclusion(self):
        admin=self.server(True)
        base={'type':'promo','internal_name':'Promo','title':'Offre','description':'','url':'https://example.com','icon':'website','image':'','badge':'Promo','cta':'Voir','priority':'normal','active':True,'draft':False,'start_at':'2099-01-01T00:00:00Z'}
        ids=[]
        for index,end in enumerate(['2099-01-05T00:00:00Z','2099-01-06T00:00:00Z','2099-01-07T00:00:00Z']):
            item={**base,'internal_name':'Promo '+str(index+1),'end_at':end}
            status,body=self.request(admin+'/api/content',item,{'Content-Type':'application/json'})
            self.assertEqual(status,201);ids.append(json.loads(body)['id'])
        candidate={**base,'internal_name':'Quatrième','start_at':'2099-01-02T00:00:00Z','end_at':'2099-01-03T00:00:00Z'}
        status,body=self.request(admin+'/api/promotions/check',candidate,{'Content-Type':'application/json'})
        check=json.loads(body);self.assertEqual(status,200);self.assertTrue(check['allowed']);self.assertEqual(check['maximum'],4)
        self.assertIsNone(check['next_start'])
        self.assertEqual(self.request(admin+'/api/content',candidate,{'Content-Type':'application/json'})[0],201)
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
        self.assertEqual(row['label'],'Communauté')

    def test_promotion_restore_and_atomic_replacement(self):
        admin=self.server(True)
        base={'type':'promo','internal_name':'Promo','title':'Offre','url':'https://example.com','start_at':'2099-01-01T00:00:00Z','end_at':'2099-02-01T00:00:00Z'}
        ids=[]
        for i in range(3):
            status,body=self.request(admin+'/api/content',{**base,'internal_name':str(i)})
            self.assertEqual(status,201);ids.append(json.loads(body)['id'])
        self.request(admin+'/api/content/'+ids[0]+'/archive',{})
        status,body=self.request(admin+'/api/content',base);self.assertEqual(status,201)
        self.assertEqual(self.request(admin+'/api/content/'+ids[0]+'/restore',{})[0],204)
        self.assertFalse(next(x for x in self.a.content_list() if x['id']==ids[0])['archived'])
        # Failure occurs after disabling the old promotion inside the transaction.
        self.assertEqual(self.request(admin+'/api/promotions/replace',{'replace_id':ids[1],'content':{**base,'id':'missing'}})[0],400)
        self.assertTrue(next(x for x in self.a.content_list() if x['id']==ids[1])['active'])
        self.assertEqual(self.request(admin+'/api/promotions/replace',{'replace_id':ids[1],'content':base})[0],200)
        self.assertFalse(next(x for x in self.a.content_list() if x['id']==ids[1])['active'])
        self.assertEqual(len([x for x in self.a.content_list() if x['type']=='promo' and x['active']]),4)

    def test_backup_roundtrip_including_images_and_counts(self):
        name='12345678-1234-1234-1234-123456789abc.png'
        raw=raster();(self.a.UPLOADS/name).write_bytes(raw)
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
        backup['images'][name]=base64.b64encode(raster()).decode()
        backup['tables']['content_blocks'][0]['title']='Changed'
        backup['tables']['content_blocks'][0]['image']='/uploads/'+name
        before=self.a.content_list()
        with patch.object(Path,'write_bytes',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.a.restore_backup(backup)
        self.assertEqual(self.a.content_list(),before)


    def test_quotes_import_preview_duplicates_and_persistence(self):
        admin=self.server(True)
        status,body=self.request(admin+'/api/quotes/analyze',{'text':' Alpha \nAlpha\nBeta\n '})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body),{'detected':3,'new':2,'duplicates':1,'allowed':2,'excess':0,'added':0})
        self.assertEqual(self.a.quote_list(),[])
        status,body=self.request(admin+'/api/quotes',{'text':' Alpha \nAlpha\nBeta\n '})
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['new'],2)
        self.assertTrue(all(q['active'] for q in self.a.quote_list()))
        self.assertEqual(self.a.add_quotes({'text':'Alpha\nGamma'})['new'],1)
        self.a.init();self.assertEqual(len(self.a.quote_list()),3)
        self.assertEqual(self.a.quote_entries({'text':'Line 1\nLine 2||| Another '}),['Line 1\nLine 2','Another'])
        self.assertEqual(self.a.quote_entries({'text':'One\nquote','single':True}),['One\nquote'])
        for text in ['', '  ', 'x'*1001]:
            self.assertEqual(self.request(admin+'/api/quotes',{'text':text})[0],400)

    def test_quotes_toggle_delete_and_public_selection(self):
        admin=self.server(True);public=self.server(False)
        self.assertEqual(self.a.public_config()['profile']['footer_quote'],'')
        self.a.add_quotes({'text':'<script>alert(1)</script>','single':True})
        item=self.a.quote_list()[0];url=admin+'/api/quotes/'+item['id']
        self.assertEqual(self.a.public_config()['profile']['footer_quote'],item['text'])
        self.assertEqual(self.request(url,{'active':False},method='PUT')[0],204)
        self.assertEqual(self.a.public_config()['profile']['footer_quote'],'')
        self.assertEqual(self.request(url,{'active':'false'},method='PUT')[0],400)
        self.assertEqual(self.request(url,{'active':True},method='PUT')[0],204)
        self.assertEqual(self.a.public_config()['profile']['footer_quote'],item['text'])
        for path,method,data in [('/api/quotes','GET',None),('/api/quotes','POST',{'text':'No'}),('/api/quotes/'+item['id'],'PUT',{'active':False}),('/api/quotes/'+item['id'],'DELETE',None)]:
            self.assertEqual(self.request(public+path,data,method=method)[0],404)
        self.assertEqual(self.request(url,method='DELETE')[0],204)
        self.assertEqual(self.a.quote_list(),[])
        self.assertEqual(self.request(url,method='DELETE')[0],404)


    def test_software_version_is_not_manually_editable(self):
        from unittest.mock import patch
        admin=self.server(True)
        self.assertEqual(self.request(admin+'/api/app-version',{'app_version':'V2.001'})[0],404)
        with patch.dict(os.environ,{'APP_RELEASE_VERSION':'V1.302','APP_RELEASE_ID':'release-a'}):
            self.a.init()
            backup=json.loads(self.a.export_backup())
            self.assertEqual(backup['software_version'],'V1.302')
            for row in backup['tables']['settings']:
                if row['key']=='app.version':row['value']='V1.3'
            self.a.restore_backup(backup)
            self.assertEqual(self.a.public_config()['profile']['app_version'],'V1.302')

    def test_bundled_version_applied_once(self):
        with self.a.connection() as db:
            db.execute("UPDATE settings SET value='V1.1' WHERE key='app.version'")
            db.execute("DELETE FROM settings WHERE key='app.release_id'")
        self.a.init()
        self.assertEqual(self.a.public_config()['profile']['app_version'],(self.a.ROOT/'VERSION').read_text().strip())
        with self.a.connection() as db:db.execute("UPDATE settings SET value='V2.1' WHERE key='app.version'")
        self.a.init()
        self.assertEqual(self.a.public_config()['profile']['app_version'],(self.a.ROOT/'VERSION').read_text().strip())

    def test_release_increment_keeps_major(self):
        spec=importlib.util.spec_from_file_location('release_version',Path(__file__).with_name('release-version.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for old,new in [('V1.046','V1.047'),('V1.2','V1.201'),('V2.001','V2.002')]:
            self.assertEqual(module.next_version(old),new)
        self.assertEqual(module.choose('ordinary commit',current='V1.201'),'V1.202')
        self.assertEqual(module.choose('Release V1.046'),'V1.046')


    def test_quote_capacity_preview_partial_and_clear(self):
        admin=self.server(True)
        self.a.add_quotes({'text':'\n'.join('Quote '+str(i) for i in range(285))})
        data={'text':'\n'.join('New '+str(i) for i in range(20))}
        status,body=self.request(admin+'/api/quotes/analyze',data)
        summary=json.loads(body);self.assertEqual(status,200)
        self.assertEqual((summary['new'],summary['allowed'],summary['excess']),(20,15,5))
        self.assertEqual(len(self.a.quote_list()),285)
        status,body=self.request(admin+'/api/quotes',{**data,'limit':15})
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['added'],15)
        self.assertEqual(len(self.a.quote_list()),300)
        self.assertEqual(self.request(admin+'/api/quotes',{'text':'Extra','single':True})[0],400)
        self.assertEqual(self.a.add_quotes({'text':'Bulk extra'})['added'],0)
        self.assertEqual(len(self.a.quote_list()),300)
        with self.a.connection() as db:db.execute('UPDATE footer_quotes SET active=0')
        self.assertEqual(self.a.add_quotes({'text':'Inactive still counts'})['added'],0)
        self.assertEqual(self.request(admin+'/api/quotes',method='DELETE')[0],204)
        self.assertEqual(self.a.quote_list(),[])
        self.assertEqual(self.a.public_config()['profile']['footer_quote'],'')
        self.assertEqual(self.a.add_quotes({'text':'After clear'})['added'],1)


    def test_saved_trailing_slash_origin_is_normalized_on_restart(self):
        origin=self.a.ORIGIN
        with self.a.connection() as db:db.execute("UPDATE settings SET value=? WHERE key='site.url'",(origin+'/',))
        self.a.init()
        self.assertEqual(self.a.ORIGIN,origin)
        public=self.server()
        self.assertEqual(self.request(public+'/metrics',{'kind':'view'},{'Origin':origin,'Content-Type':'application/json'})[0],204)
        self.assertEqual(self.request(public+'/metrics',{'kind':'view'},{'Origin':'https://foreign.example','Content-Type':'application/json'})[0],403)

    def test_promo_code_copy_snapshot_filters_and_history(self):
        public=self.server(False);item={'id':self.promo(),'internal_name':'Domadoo - Aquara days'}
        with self.a.connection() as db:db.execute("UPDATE content_blocks SET promo_code='OLD' WHERE id=?",(item['id'],))
        payload={'kind':'promo_code_copy','link':'block:'+item['id'],'code':'OLD','source':'instagram'}
        headers={'Origin':self.a.ORIGIN,'User-Agent':'Mozilla/5.0'}
        self.assertEqual(self.request(public+'/metrics',payload,headers)[0],204)
        self.assertEqual(self.request(public+'/metrics',payload,headers)[0],204)
        with self.a.connection() as db:
            db.execute("UPDATE content_blocks SET promo_code='NEW',internal_name='Renamed',archived=1 WHERE id=?",(item['id'],))
            db.execute("INSERT INTO counts VALUES('2001-01-01','instagram','promo_code_copy',?,99)",(json.dumps({'id':item['id'],'name':'Old','code':'EXCLUDED','timestamp':'2001-01-01T00:00:00+00:00'}),))
        day=self.a.datetime.now(self.a.PARIS).date().isoformat()
        report=self.a.report(day,day,'instagram')
        self.assertEqual(sum(x['total'] for x in report['promo_code_copies']),2)
        self.assertEqual(report['promo_code_copies'][0]['code'],'OLD')
        self.assertEqual(report['promo_code_copies'][0]['name'],item['internal_name'])
        self.assertFalse(any(x['kind']=='click' for x in report['rows']))
        self.assertEqual(self.a.report(day,day,'youtube')['promo_code_copies'],[])
        self.a.record('impression','instagram','block:'+item['id'],day)
        report=self.a.report(day,day,'instagram')
        self.assertEqual(report['campaign_metrics'][0]['total'],1)
        self.assertEqual(report['campaign_metrics'][0]['kind'],'impression')
        backup=json.loads(self.a.export_backup());self.a.restore_backup(backup)
        self.assertEqual(sum(x['total'] for x in self.a.report(day,day)['promo_code_copies']),2)
        self.assertEqual(self.request(public+'/metrics',{**payload,'code':''},headers)[0],400)

    def test_admin_section_preferences_are_private_and_backup_safe(self):
        admin=self.server(True)
        before=json.loads(self.request(admin+'/api/settings')[1])
        order=['highlight','classic','video']
        self.assertEqual(self.request(admin+'/api/settings',{'content_order':order})[0],204)
        after=json.loads(self.request(admin+'/api/settings')[1])
        self.assertEqual(after['content_order'],order)
        self.assertEqual(after['name'],before['name'])
        self.assertNotIn('content_order',self.a.public_config()['profile'])
        backup=json.loads(self.a.export_backup());self.a.restore_backup(backup)
        self.assertEqual(json.loads(self.request(admin+'/api/settings')[1])['content_order'],order)
        for invalid in [['classic','classic','video'],['classic'],[{},'video','classic']]:
            self.assertEqual(self.request(admin+'/api/settings',{'content_order':invalid})[0],400)
        self.assertEqual(self.request(admin+'/api/settings',{'video_enabled':False})[0],204)
        final=json.loads(self.request(admin+'/api/settings')[1])
        self.assertFalse(final['video_enabled']);self.assertEqual(final['name'],before['name'])

    def test_shortcuts_additive_migration_and_legacy_backup(self):
        with self.a.connection() as db:
            db.execute("INSERT INTO counts VALUES('2026-10-04','direct','click','button:legacy-button-2',7)")
            db.execute("UPDATE top_buttons SET active=0 WHERE id='legacy-button-1'")
            before=[tuple(r) for r in db.execute('SELECT id,icon,label,url,position,active,created_at,updated_at FROM top_buttons ORDER BY position')]
            db.execute('ALTER TABLE top_buttons DROP COLUMN custom_icon')
        self.a.init();self.a.init()
        with self.a.connection() as db:
            self.assertEqual(before,[tuple(r) for r in db.execute('SELECT id,icon,label,url,position,active,created_at,updated_at FROM top_buttons ORDER BY position')])
            self.assertTrue(all(not r[0] for r in db.execute('SELECT custom_icon FROM top_buttons')))
        self.assertEqual(self.a.button_list()[2]['clicks'],7)
        backup=json.loads(self.a.export_backup())
        for row in backup['tables']['top_buttons']:row.pop('custom_icon')
        self.a.restore_backup(backup)
        self.assertEqual(self.a.button_list()[2]['clicks'],7)
        self.assertEqual(self.a.button_list()[2]['id'],'legacy-button-2')

    def test_shortcut_upload_validation_and_portable_backup(self):
        admin=self.server(True)
        for mime,raw in [('image/svg+xml',b'<svg/>'),('image/png',b'not an image'),('image/webp',b'RIFFxxxxWEBP'+b'x'*(1024*1024))]:
            self.assertEqual(self.request(admin+'/api/upload',{'type':mime,'data':base64.b64encode(raw).decode(),'purpose':'icon'})[0],400)
        raw=(Path(__file__).parent.parent/'site/assets/link-shopping.webp').read_bytes()
        status,body=self.request(admin+'/api/upload',{'type':'image/webp','data':base64.b64encode(raw).decode(),'purpose':'icon'});self.assertEqual(status,201)
        image=json.loads(body)['url']
        for url in ['https://example.com','http://example.com','mailto:test@example.com','tel:+33123456789','#contact']:
            status,body=self.request(admin+'/api/buttons',{'icon':'email','label':url,'url':url,'custom_icon':image});self.assertEqual(status,201,body)
        for url in ['javascript:alert(1)','# bad']:
            self.assertEqual(self.request(admin+'/api/buttons',{'icon':'mail','label':'Bad','url':url})[0],400)
        backup=json.loads(self.a.export_backup());self.a.restore_backup(backup)
        for item in self.a.button_list()[3:]:
            self.assertEqual(item['icon'],'mail');self.assertEqual((self.a.UPLOADS/item['custom_icon'].split('/')[-1]).read_bytes(),raw)

    def test_public_schedule_boundary_excludes_private_campaigns_and_preserves_counts(self):
        from datetime import datetime,timedelta,timezone
        now=datetime.now(timezone.utc)
        start=(now+timedelta(hours=2)).isoformat().replace('+00:00','Z')
        private_start=(now+timedelta(hours=1)).isoformat().replace('+00:00','Z')
        with self.a.connection() as db:
            self.a.save_content(db,self.a.block_data({'type':'promo','internal_name':'Scheduled','title':'Scheduled','url':'https://example.com','start_at':start}))
            self.a.save_content(db,self.a.block_data({'type':'promo','internal_name':'Private draft','title':'Private draft','url':'https://example.com','start_at':private_start,'draft':True}))
            before=[tuple(row) for row in db.execute('SELECT * FROM counts')]
        config=self.a.public_config()
        self.assertEqual(config['next_campaign_change'],start)
        self.assertNotIn('Private draft',json.dumps(config))
        self.assertNotIn('Scheduled',json.dumps(config))
        with self.a.connection() as db:self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM counts')],before)

if __name__=='__main__':unittest.main()



