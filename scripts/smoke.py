"""Smoke-test a disposable Docker image through its real public/admin endpoints."""
import http.cookiejar,json,os,sys,hashlib
from pathlib import Path
from urllib.request import Request,build_opener,HTTPCookieProcessor,HTTPRedirectHandler
from urllib.error import HTTPError

public=sys.argv[1];admin=sys.argv[2];bootstrap=sys.argv[3]
opener=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
def call(origin,path,data=None,csrf=''):
    response=opener.open(Request(origin+path,json.dumps(data).encode() if data is not None else None,{'Content-Type':'application/json','X-Links-Request':'1','X-Links-CSRF':csrf,'Origin':origin}))
    with response:
        body=response.read();return json.loads(body) if body else None
for path in ['/brand.svg','/mark.svg']:
    with opener.open(admin+path) as response:assert b'<svg' in response.read()
config=call(public,'/api/public-config');assert not config['setup_completed'];assert not config['links'];assert not config['socials']
call(admin,'/api/setup',{'bootstrap':bootstrap,'username':'smoke-admin','password':'A-long-smoke-password','confirmation':'A-long-smoke-password','name':'Smoke test','link_title':'First link','link_url':'https://example.com','site_url':public,'timezone':'UTC','analytics_enabled':True})
csrf=call(admin,'/api/auth/status')['csrf'];assert csrf
# Exercise the actual packaged API without any external request. A metadata IP is
# rejected before DNS/network, but the result must identify this exact engine file.
title_probe=call(admin,'/api/tracked-links/title-preview',{'url':'http://169.254.169.254/private','current_title':'Titre conservé'},csrf)
expected_engine=hashlib.sha256((Path(__file__).parent/'url_inspection.py').read_bytes()).hexdigest()[:12]
assert title_probe['engine']=={'id':'bounded-metadata-v2','fingerprint':expected_engine},title_probe.get('engine')
assert title_probe['reason']=='blocked_destination' and title_probe['title']=='Titre conservé'
assert title_probe['diagnostics']['fetch']['stage']=='security'
assert call(admin,'/api/storage')['grace_days']==7
assert call(admin,'/api/storage',{'action':'cleanup'},csrf)['unused']==0
for path in ['/uploads.js','/storage.js']:
    with opener.open(admin+path) as response:assert response.status==200
with opener.open(admin+'/shortcuts.js') as response:assert b'LinksShortcuts' in response.read()
assert len(call(admin,'/api/content')['items'])==1
call(public,'/metrics',{'kind':'view','source':'youtube'})
promo=call(admin,'/api/content',{'type':'promo','internal_name':'Smoke offer','title':'Offer','url':'https://partner.example','promo_code':'TEST10'},csrf)['id']
call(public,'/metrics',{'kind':'promo_code_copy','link':'block:'+promo,'code':'TEST10','source':'instagram'})
call(admin,'/api/quotes',{'text':'Smoke quote'},csrf)
backup=call(admin,'/api/backup');assert backup['version']==3;assert len(backup['tables']['footer_quotes'])==1;assert any(x['kind']=='promo_code_copy' for x in backup['tables']['counts'])
assert call(admin,'/api/content/'+promo+'/story-link',{},csrf)['url'].startswith(public+'/go/')
call(admin,'/api/settings',{'name':'Smoke test','analytics_enabled':False},csrf)
before=call(admin,'/api/backup')['tables']['counts'];call(public,'/metrics',{'kind':'view'});assert call(admin,'/api/backup')['tables']['counts']==before
call(admin,'/api/restore',backup,csrf)
call(admin,'/api/auth/login',{'username':'smoke-admin','password':'A-long-smoke-password'})
assert call(admin,'/api/quotes')['items'][0]['text']=='Smoke quote'
print('Fresh image: bootstrap, setup, login, content, copies, quotes, Stories, analytics off and restore OK')
