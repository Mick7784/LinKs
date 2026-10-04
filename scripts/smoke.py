"""Smoke-test a disposable Docker image through its real public/admin endpoints."""
import http.cookiejar,json,os,sys
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
