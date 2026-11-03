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
  const csv='Date,Tag,clics,articles commandés,articles expédiés,revenus totaux\n10-31-2026,test-21,7,3,2,3.75\n';
  const payload={account:account.id,csv,kind:'performance',view:'category',mapping:{date:'Date',clicks:'clics',ordered_items:'articles commandés',shipped_items:'articles expédiés',commission_cents:'revenus totaux'},start:'2026-10-31',end:'2026-10-31',scope:'all',date_format:'mdy',decimal:'dot',confirmed:true};
  await api('amazon/import',payload);
  await api('amazon/import',{...payload,view:'tracking_id',contribution:'detail',mapping:{...payload.mapping,tracking_id:'Tag'}});
  await page.goto(origin);await page.locator('[data-tab=affiliation]').click();await page.getByRole('button',{name:'Gérer les partenaires',exact:true}).click();
  await page.locator('.aff-partner').filter({hasText:'France test'}).getByRole('button',{name:'Voir les détails'}).click();
  await page.locator('.aff-card').filter({hasText:'Clics Amazon'}).waitFor();
  assert.equal(await page.locator('.aff-card').filter({hasText:'Clics Amazon'}).locator('strong').innerText(),'7');
  assert.match(await page.locator('section.panel').filter({has:page.getByRole('heading',{name:'Évolution quotidienne',exact:true})}).innerText(),/2026-10-31/);
  assert.match(await page.locator('section.panel').filter({has:page.getByRole('heading',{name:'Répartition par Tracking ID',exact:true})}).innerText(),/test-21/);
  const nav=page.getByRole('navigation',{name:'Rubriques affiliation'});
  assert.deepEqual(await nav.getByRole('button').allTextContents(),['Vue d’ensemble','Rapports et imports','Connexion']);
  assert.equal(await page.getByRole('heading',{name:'Lignes de rapports Amazon',exact:true}).count(),0);
  assert.equal(await page.locator('.aff-card').count(),4);
  if(process.env.AMAZON_UI_SHOTS)await page.screenshot({path:join(process.env.AMAZON_UI_SHOTS,'amazon-vue-ensemble.png'),fullPage:true});
  await nav.getByRole('button',{name:'Rapports et imports',exact:true}).click();
  await page.getByRole('heading',{name:'Rapports actifs · 1',exact:true}).waitFor();
  assert.equal(await page.locator('#aff-period').isVisible(),false);
  assert.equal(await page.locator('.aff-card').count(),0);
  assert.equal(await page.getByRole('heading',{name:'Évolution quotidienne',exact:true}).count(),0);
  await page.getByText('Lignes détaillées · période sélectionnée dans la vue d’ensemble',{exact:true}).click();
  assert.match(await page.locator('#aff-content table').innerText(),/3,75/);
  await nav.getByRole('button',{name:'Connexion',exact:true}).click();
  await page.locator('[data-portal-state]').waitFor();
  assert.equal(await page.getByRole('heading',{name:/^Rapports actifs/}).count(),0);
  assert.equal(await page.locator('#aff-amazon-probe').isVisible(),false);
  await page.getByText('Accès API avancé',{exact:true}).click();
  assert(await page.locator('#aff-amazon-probe').isVisible());
  await page.getByText('Authentification à deux facteurs',{exact:true}).click();
  assert(await page.locator('#aff-mfa-state').isVisible());
  // Empty state and recovery: an existing report outside the selected interval.
  await nav.getByRole('button',{name:'Vue d’ensemble',exact:true}).click();
  await page.locator('#aff-start').fill('2020-01-01');await page.locator('#aff-end').fill('2020-01-02');await page.locator('[data-aff=range]').click();
  await page.getByRole('heading',{name:'Aucune donnée sur cette période',exact:true}).waitFor();
  assert.equal(await page.locator('#aff-content table').count(),0);
  await page.getByRole('button',{name:'Afficher tout l’historique',exact:true}).click();
  await page.locator('.aff-card').filter({hasText:'Commissions déclarées'}).waitFor();
  assert.match(await page.locator('.aff-card').filter({hasText:'Commissions déclarées'}).innerText(),/3,75/);
  // Pending files expose the blocking reason directly in the archive manager.
  let unavailable=false;
  await page.route('**/api/affiliation/overview?*',async route=>{const response=await route.fetch(),body=await response.json();for(const r of body.amazon||[]){r.pending=[{id:999,filename:'Archive-annuelle-à-vérifier.zip',observed_at:'2026-11-03T12:00:00Z',reasons:['Période absente du fichier.']}];if(unavailable){r.reports=[];r.rows=[];r.daily=[];r.tracking=[];for(const k of Object.keys(r.totals))r.totals[k]=null}}await route.fulfill({response,json:body})});
  await page.evaluate(()=>window.LinksAffiliation.load());
  await page.getByRole('button',{name:'Voir les rapports',exact:true}).click();
  await page.getByRole('heading',{name:'Archives nécessitant une attention · 1',exact:true}).waitFor();
  assert(await page.getByText('Période absente du fichier.',{exact:true}).isVisible());
  for(const width of [390,768,1440]){
   await page.setViewportSize({width,height:960});
   await nav.getByRole('button',{name:'Connexion',exact:true}).click();
   await page.locator('[data-portal-state]').waitFor();
   await nav.getByRole('button',{name:'Rapports et imports',exact:true}).click();
   await page.getByRole('heading',{name:'Archives nécessitant une attention · 1',exact:true}).waitFor();
   await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo(0,0)});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No document overflow at '+width);
   assert(await nav.getByRole('button',{name:'Connexion',exact:true}).isVisible());
   if(process.env.AMAZON_UI_SHOTS&&width===390)await page.screenshot({path:join(process.env.AMAZON_UI_SHOTS,'amazon-rapports-mobile.png'),fullPage:true});
   if(process.env.AMAZON_UI_SHOTS&&width===1440)await page.screenshot({path:join(process.env.AMAZON_UI_SHOTS,'amazon-rapports-desktop.png'),fullPage:true});
  }
  unavailable=true;await page.evaluate(()=>window.LinksAffiliation.load());
  await nav.getByRole('button',{name:'Vue d’ensemble',exact:true}).click();
  await page.getByRole('heading',{name:'Aucune statistique exploitable pour le moment',exact:true}).waitFor();
  assert.equal(await page.locator('.aff-card').count(),0);assert.equal(await page.locator('#aff-content table').count(),0);
  await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo(0,0)});
  if(process.env.AMAZON_UI_SHOTS)await page.screenshot({path:join(process.env.AMAZON_UI_SHOTS,'amazon-vue-ensemble-sans-donnees.png'),fullPage:true});
  assert.deepEqual(errors,[]);console.log('PASS Amazon navigation: three distinct sections, totals, imports, API/MFA disclosures, period recovery, pending/empty states, 390/768/1440px.');
 }finally{if(browser)await browser.close();if(server){server.kill();if(server.exitCode===null)await new Promise(r=>server.once('exit',r))}rmSync(temp,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exitCode=1});
