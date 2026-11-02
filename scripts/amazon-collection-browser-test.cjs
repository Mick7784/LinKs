// One targeted import journey, disposable database, no Amazon/network access.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process'),{mkdtempSync,rmSync}=require('node:fs'),{join}=require('node:path'),{tmpdir}=require('node:os');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-amazon-'));let browser,server;
 try{
  server=spawn(process.env.PYTHON_PATH||'python3',['-u','-B','-c',`import os
from fixtures import prepare,populate
prepare(os.environ['ANALYTICS_DB'])
import analytics as a
a.init();populate(a)
attempts=0
def unavailable(action,data=None,timeout=40):
 global attempts
 if action=='amazon/mfa/status':return dict(active=True,pending=False,environment=False,conflict=False,source='links')
 if action=='amazon/status':return dict(run=data['run'],stage='waiting',message='Attente des nouveaux exports')
 if action=='amazon/collect':
  attempts+=1
  if attempts==2:
   import time
   time.sleep(4)
  if attempts==3:
   from amazon_collection_test import batch
   return batch()
 raise ValueError('Génération [amazon_generation_timeout] : Aucun nouvel export. Test local sans connexion.')
a.affiliation.worker=unavailable
s=a.serve(0,True,'127.0.0.1')
a.ORIGIN='http://127.0.0.1:'+str(s.server_port)
with a.connection() as db:
 a.instance.put(db,'site.url',a.ORIGIN)
 a.instance.put(db,'video.enabled','false')
print(a.ORIGIN,flush=True)
s.serve_forever()`],{cwd:__dirname,env:{...process.env,PYTHONIOENCODING:'utf-8',ANALYTICS_DB:join(temp,'db.sqlite'),UPLOAD_DIR:join(temp,'uploads')},stdio:['ignore','pipe','pipe']});
  let logs='';server.stderr.on('data',b=>logs+=b);
  const origin=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error(logs||'Server timeout')),20000);server.on('error',reject);server.stdout.on('data',b=>{output+=b;const m=output.match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0])}});server.on('exit',()=>{clearTimeout(timer);reject(Error(logs))})});
  const api=async(path,data)=>{const r=await fetch(origin+'/api/affiliation/'+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(r.ok,await r.clone().text());return r.json()};
  const account=await api('accounts',{partner:'Amazon','label':'France test','platform':'amazon'});
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.request().url().startsWith(origin)?r.continue():r.abort());
  await page.goto(origin);await page.locator('[data-tab=affiliation]').click();await page.getByRole('button',{name:'Gérer les partenaires',exact:true}).click();
  await page.locator('.aff-partner').filter({hasText:'France test'}).getByRole('button',{name:'Voir les détails'}).click();
  await page.getByRole('button',{name:'Connexion',exact:true}).click();
  await page.locator('[data-portal-day]').fill('2026-10-31');await page.locator('[data-portal-tag]').fill('test-21');
  await page.locator('[data-portal-sync]').click();
  await page.getByRole('alert').filter({hasText:'Génération [amazon_generation_timeout]'}).waitFor();
  assert.equal(await page.locator('[data-portal-sync]').isEnabled(),true);
  assert.equal(await page.locator('[data-portal-day]').inputValue(),'2026-10-31');
  assert.equal(await page.locator('[data-portal-tag]').inputValue(),'test-21');
  const overview=await api('overview');const current=overview.accounts.find(a=>a.id===account.id);
  assert.equal(current.portal_last_success,null);assert.equal(current.enabled,0);assert.equal(current.running,false);
  await page.locator('[data-portal-sync]').click();
  await page.locator('[data-portal-state]').filter({hasText:'Synchronisation en cours'}).waitFor();
  assert.equal(await page.locator('[data-portal-error]').isVisible(),false);
  assert.match(await page.locator('[data-portal-history]').innerText(),/Dernière erreur historique/);
  assert.match(await page.locator('[data-portal-state]').innerText(),/Attente des nouveaux exports/);
  assert.doesNotMatch(await page.locator('#aff-mfa-state').innerText(),/occupé/);
  await page.locator('[data-portal-state]').filter({hasText:'Dernière tentative échouée'}).waitFor();
  assert.equal(await page.locator('[data-portal-sync]').isEnabled(),true);
  await page.locator('[data-portal-sync]').click();
  await page.locator('[data-portal-state]').filter({hasText:'Dernière synchronisation réussie'}).waitFor();
  assert.equal(await page.locator('[data-portal-error]').isVisible(),false);
  assert.equal(await page.locator('[data-portal-day]').inputValue(),'2026-10-31');
  assert.deepEqual(errors,[]);console.log('PASS états Amazon : ancien échec, tentative en cours et étape, nouvel échec, réussite et sélection conservée.');
 }finally{if(browser)await browser.close();if(server){server.kill();if(server.exitCode===null)await new Promise(r=>server.once('exit',r))}rmSync(temp,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exitCode=1});
