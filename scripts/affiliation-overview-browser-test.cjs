// Real local app + disposable synthetic database. No merchant network traffic.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process'),{mkdtempSync,rmSync,mkdirSync}=require('node:fs'),{join}=require('node:path'),{tmpdir}=require('node:os');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-overview-'));let browser,server;
 try{
  server=spawn(process.env.PYTHON_PATH||'python3',['-u','-B','-c',`import os
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch
from fixtures import prepare,populate
prepare(os.environ['ANALYTICS_DB'])
import analytics as a
import affiliation as aff
import affiliation_overview as overview
a.init();populate(a)
original=overview.build
overview.build=lambda db,accounts,start='',end='':original(db,accounts,start,end,datetime(2026,11,2,12,tzinfo=timezone.utc))
s=a.serve(0,True,'127.0.0.1')
a.ORIGIN='http://127.0.0.1:'+str(s.server_port)
with a.connection() as db:
 a.instance.put(db,'site.url',a.ORIGIN)
 a.instance.put(db,'video.enabled','false')
 second=aff.add_account(db,{'partner':'Partenaire de test','label':'Compte fictif','platform':'domadoo'})['id']
 amazon=aff.add_account(db,{'partner':'Amazon','label':'France fictif','platform':'amazon'})['id']
 for identity in ['domadoo',second]:
  rows=[]
  for i in range((date(2026,11,2)-date(2025,8,1)).days+1):
   day=(date(2025,8,1)+timedelta(days=i)).isoformat()
   amount=(i%11+2)*50 if identity=='domadoo' else (i%5+1)*70
   if day=='2026-10-06' and identity==second:amount=-80
   if day=='2026-10-07':amount=-120
   if day=='2026-10-08':amount=0
   rows.append({'provider_id':str(i),'occurred_at':day+' 12:00:00','order_cents':10000,'commission_cents':amount,'currency':'EUR','status':'approved'})
  with patch.object(aff,'stamp',return_value='2026-11-02T12:00:00Z'):
   aff.ingest(db,identity,{'complete':True,'currency':'EUR','pages':1,'vouchers':[],'summary':{k:0 for k in aff.SUMMARY_KEYS},'transactions':rows})
print(a.ORIGIN,flush=True)
s.serve_forever()`],{cwd:__dirname,env:{...process.env,PYTHONIOENCODING:'utf-8',ANALYTICS_DB:join(temp,'db.sqlite'),UPLOAD_DIR:join(temp,'uploads')},stdio:['ignore','pipe','pipe']});
  let logs='';server.stderr.on('data',b=>logs+=b);
  const origin=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error(logs||'Server timeout')),20000);server.on('error',reject);server.stdout.on('data',b=>{output+=b;const m=output.match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0])}});server.on('exit',()=>{clearTimeout(timer);reject(Error(logs))})});
  const api=async(path,data)=>{const r=await fetch(origin+'/api/affiliation/'+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(r.ok,await r.clone().text());return r.json()};
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
  page.setDefaultTimeout(10000);await page.clock.install({time:new Date('2026-11-02T12:00:00Z')});
  page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.request().url().startsWith(origin)?r.continue():r.abort());
  let requests=0;page.on('request',r=>{if(r.url().includes('/api/affiliation/overview?'))requests++});
  await page.goto(origin);await page.locator('[data-tab=affiliation]').click();await page.locator('[data-overview-total]').waitFor();
  assert.equal(await page.locator('#aff-period').inputValue(),'30');
  assert.equal(await page.locator('#aff-start').inputValue(),'2026-10-04');assert.equal(await page.locator('#aff-end').inputValue(),'2026-11-02');
  assert.equal(await page.locator('[data-overview-date]').count(),30);
  assert.equal(await page.locator('.aff-overview-kpis .aff-card').count(),3);
  assert.equal(await page.getByRole('heading',{name:'Mes partenaires',exact:true}).count(),0);
  assert.match(await page.locator('.aff-overview-coverage').innerText(),/2 \/ 3 partenaires/);
  const previousTotal=await page.locator('[data-overview-total]').innerText(),beforeRequests=requests;
  await page.locator('#aff-start').fill('2026-10-01');await page.locator('#aff-end').fill('2026-10-30');
  assert.equal(requests,beforeRequests);assert.equal(await page.locator('[data-overview-total]').innerText(),previousTotal);
  await page.locator('[data-aff=range]').click();await page.waitForFunction(()=>document.querySelector('[data-overview-date]')?.dataset.overviewDate==='2026-10-01');
  const model=(await api('overview?start=2026-10-01&end=2026-10-30')).overview;
  const money=n=>new Intl.NumberFormat('fr-FR',{style:'currency',currency:'EUR'}).format(n/100).replace(/\s/g,'');
  assert.equal((await page.locator('[data-overview-total]').textContent()).replace(/\s/g,''),money(model.total_cents));
  assert.equal(model.total_cents,model.daily.reduce((n,d)=>n+d.cents,0));
  await page.evaluate(()=>{window.qaPeriod=document.querySelector('[data-overview-period]');window.qaPeriodHTML=qaPeriod.innerHTML;window.qaTotal=document.querySelector('[data-overview-total]').textContent});
  await page.locator('[data-overview-date="2026-10-05"]').click();
  assert.match(await page.locator('[data-overview-day] h2').innerText(),/05\/10\/2026/);
  await page.locator('[data-overview-date="2026-10-06"]').focus();await page.keyboard.press('Space');
  assert.match(await page.locator('[data-overview-day]').innerText(),/Corrections négatives/);
  assert.equal(await page.locator('[data-overview-date="2026-10-06"]').getAttribute('aria-pressed'),'true');
  assert(await page.evaluate(()=>document.activeElement.dataset.overviewDate==='2026-10-06'));
  await page.keyboard.press('ArrowRight');await page.keyboard.press('Enter');
  assert.match(await page.locator('[data-overview-day] h2').innerText(),/07\/10\/2026/);
  assert.match(await page.locator('[data-overview-day] .aff-overview-ring strong').innerText(),/-2,40/);
  const zero=Number(await page.locator('.aff-zero').getAttribute('y1'));
  const negative=page.locator('[data-overview-date="2026-10-07"] .aff-daily-bar');
  assert.equal(Number(await negative.getAttribute('y')),zero);assert(Number(await negative.getAttribute('height'))>0);
  assert(await page.locator('[data-overview-compare=previous]').isDisabled(),'Amazon without coverage prevents a misleading comparison');
  assert(await page.locator('[data-overview-compare=year]').isDisabled());
  assert.equal(await page.locator('[data-overview-date="2026-10-07"]').getAttribute('aria-pressed'),'true');
  await page.locator('[data-overview-compare=none]').click();assert.equal(await page.locator('.aff-comparison-line').count(),0);
  assert(await page.evaluate(()=>qaPeriod===document.querySelector('[data-overview-period]')&&qaPeriod.innerHTML===qaPeriodHTML&&qaTotal===document.querySelector('[data-overview-total]').textContent),'Day and comparison must not rebuild or recalculate the period donut');
  await page.locator('[data-overview-date="2026-10-08"]').click();assert.match(await page.locator('[data-overview-day]').innerText(),/Total connu à 0/);
  await page.locator('[data-overview-date="2026-10-05"]').click();
  for(const theme of ['dark','light']){
   await page.locator('#theme-select').selectOption(theme,{force:true});
   for(const width of [1440,390]){
    await page.setViewportSize({width,height:1100});await page.clock.runFor(350);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No horizontal document overflow');
    if(process.env.AFFILIATION_QA_DIR){mkdirSync(process.env.AFFILIATION_QA_DIR,{recursive:true});await page.screenshot({path:join(process.env.AFFILIATION_QA_DIR,`affiliation-${theme}-${width}.png`),fullPage:true,animations:'disabled'});}
   }
  }
  await page.setViewportSize({width:1440,height:1100});
  await page.getByRole('navigation',{name:'Partenaires affiliation'}).getByRole('button',{name:'Domadoo',exact:true}).click();
  await page.getByRole('button',{name:'Ventes et commissions',exact:true}).click();await page.locator('#aff-sales-table tbody tr').first().waitFor();
  await page.getByRole('button',{name:'Paiements',exact:true}).click();await page.locator('#aff-payments').waitFor();
  await page.getByRole('button',{name:'Connexion et synchronisation',exact:true}).click();await page.locator('#aff-settings-form').waitFor();
  await page.getByRole('navigation',{name:'Partenaires affiliation'}).getByRole('button',{name:'Amazon',exact:true}).click();
  await page.getByRole('button',{name:'Rapports Amazon',exact:true}).waitFor();assert(await page.getByRole('button',{name:'Importer un ZIP Amazon',exact:true}).first().isVisible());
  await page.getByRole('button',{name:'Vue d’ensemble générale',exact:true}).click();await page.locator('[data-overview-total]').waitFor();
  for(let i=0;i<8;i++)await api('accounts',{partner:`Partenaire supplémentaire ${i}`,label:'Synthétique',platform:'affiliatly'});
  await page.evaluate(()=>window.LinksAffiliation.load());
  assert(await page.locator('.aff-partner-tabs').evaluate(n=>n.scrollWidth>n.clientWidth),'Partner tabs scroll instead of growing the page');
  const last=page.locator('.aff-partner-tabs button').last();await last.focus();assert(await last.isVisible());
  await page.locator('#aff-start').fill('2020-01-01');await page.locator('#aff-end').fill('2020-01-03');await page.locator('[data-aff=range]').click();
  await page.waitForFunction(()=>document.querySelector('[data-overview-date]')?.dataset.overviewDate==='2020-01-01');
  assert.equal(await page.locator('[data-overview-total]').innerText(),'N/D');assert.equal(await page.locator('.aff-unknown').count(),3);assert(await page.locator('[data-overview-compare=year]').isDisabled());
  await page.locator('#aff-start').fill('2026-11-02');await page.locator('#aff-end').fill('2026-11-02');await page.locator('[data-aff=range]').click();
  await page.waitForFunction(()=>document.querySelector('[data-overview-date]')?.dataset.overviewDate==='2026-11-02');
  assert.match(await page.locator('[data-overview-day]').innerText(),/provisoire/);
  assert.deepEqual(errors,[]);
  console.log('PASS overview: Apply, 30 Paris days, totals, signed amounts, zero/unknown, keyboard/focus, independent donuts, comparison selection, responsive themes, tab overflow, existing partner pages.');
 }finally{if(browser)await browser.close();if(server){server.kill();if(server.exitCode===null)await new Promise(r=>server.once('exit',r))}rmSync(temp,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exitCode=1});
