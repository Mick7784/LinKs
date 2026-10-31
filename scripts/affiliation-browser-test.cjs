// Synthetic financial data only. No request is ever sent to a merchant account.
const assert=require('node:assert/strict'),{chromium}=require('playwright-core');
const {spawn,execFileSync}=require('node:child_process'),{mkdtempSync,rmSync}=require('node:fs'),{tmpdir}=require('node:os'),{join,resolve}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-aff-ui-')),db=join(temp,'stats.db'),python=process.env.PYTHON_PATH||'python3',origin='http://127.0.0.1:8081';
 execFileSync(python,[resolve(__dirname,'fixtures.py'),db]);
 const server=spawn(python,[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:db,UPLOAD_DIR:join(temp,'uploads')},stdio:'ignore'});
 let browser;
 try{
   for(let i=0;i<100;i++){try{if((await fetch(origin+'/healthz')).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
   browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
   // Keep the browser outside the fixture month: the test must select its dates before expecting a chart.
   await page.clock.install({time:new Date('2031-02-15T12:00:00Z')});
   page.on('pageerror',e=>errors.push(e.message));await page.goto(origin);await page.click('[data-tab="affiliation"]');
   await page.getByText('Vos revenus apparaîtront après la première synchronisation.').waitFor();
   assert.equal(await page.locator('.aff-card strong').first().textContent(),'—');
   await page.getByRole('button',{name:'Configurer Domadoo',exact:true}).click();await page.getByRole('heading',{name:'Synchronisation quotidienne'}).waitFor();
   assert.equal(await page.locator('#aff-enabled').isChecked(),false);
   let challenge=true,verified=0,closed=0,inflight=0,maxInflight=0,inputs=0,finishInputs;
   const allInputs=new Promise(resolve=>{finishInputs=resolve});
   await page.route('**/api/affiliation/login/**',async route=>{
     inflight++;maxInflight=Math.max(maxInflight,inflight);
     const action=new URL(route.request().url()).pathname.split('/').pop();
     if(action==='verify')verified++;
     if(action==='close')closed++;
     await new Promise(resolve=>setTimeout(resolve,50));
     await route.fulfill({contentType:'application/json',body:JSON.stringify(action==='close'?{active:false}:{active:true,challenge,image:'',location:'https://www.domadoo.fr/fr/affiliation',diagnostic:{browser:'firefox',version:'fixture',session:'restored',stage:challenge?'security_check':'login_form',status:challenge?403:200,ray_id:'0123456789abcdef-CDG'}})});
     inflight--;if(action==='input'&&++inputs===3)finishInputs();
   });
   await page.getByRole('button',{name:'Ouvrir la connexion Domadoo',exact:true}).click();
   await page.locator('#aff-login-challenge').waitFor();assert.equal(await page.locator('#aff-login-verify').isDisabled(),true);
   assert.match(await page.locator('#aff-login-challenge').textContent(),/Une connexion réussie sur votre ordinateur ne connecte pas LinKs/);
   assert.match(await page.locator('#aff-login-status').textContent(),/Session précédente reprise/);
   await page.locator('.aff-connection-diagnostic summary').click();assert.match(await page.locator('#aff-login-diagnostic').textContent(),/firefox/);
   for(const theme of ['light','dark']){await page.locator('#theme-select').selectOption(theme,{force:true});for(const width of [1440,390]){await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Login diagnostic overflow');}}
   await page.setViewportSize({width:1440,height:1000});
   await page.locator('#aff-dialog').evaluate(d=>[...d.querySelectorAll('[data-login-key]')].slice(0,3).forEach(b=>b.click()));
   await allInputs;assert.equal(maxInflight,1,'Screenshot polling and human inputs must be serialized');
   challenge=false;await page.clock.runFor(2600);await page.locator('#aff-login-challenge').waitFor({state:'hidden'});
   assert.equal(await page.locator('#aff-login-verify').isDisabled(),false);assert.equal(verified,0);
   await page.getByRole('button',{name:'Fermer',exact:true}).click();await page.locator('#aff-dialog').waitFor({state:'hidden'});
   assert.equal(closed,1);assert.equal(await page.getByRole('button',{name:'Ouvrir la connexion Domadoo',exact:true}).isDisabled(),false);
   await page.unroute('**/api/affiliation/login/**');
   await page.getByRole('button',{name:'Tous les partenaires',exact:true}).click();await page.getByRole('button',{name:'Gérer les partenaires',exact:true}).click();
   await page.getByRole('button',{name:'Ajouter un partenaire',exact:true}).click();await page.locator('[name="partner"]').fill('Reolink');await page.locator('#aff-add-form [name="label"]').fill('Compte Reolink');await page.locator('[name="platform"]').selectOption('affiliatly');await page.locator('#aff-add-form button').click();await page.locator('.aff-partner').filter({hasText:'Reolink'}).waitFor();
   const seed=`import sys,sqlite3;sys.path.insert(0,${JSON.stringify(__dirname)});import affiliation;from affiliation_test import observation;db=sqlite3.connect(${JSON.stringify(db)});db.row_factory=sqlite3.Row;affiliation.ingest(db,'domadoo',observation());db.commit();db.close()`;
   execFileSync(python,['-c',seed]);
   await page.locator('.aff-partner').filter({hasText:'Domadoo'}).getByRole('button').click();await page.getByRole('button',{name:'Vue d’ensemble',exact:true}).click();
   // Select the synthetic period explicitly, independent of the runner's date.
   await page.locator('#aff-start').fill('2026-10-01');await page.locator('#aff-end').fill('2026-10-31');await page.getByRole('button',{name:'Appliquer',exact:true}).click();
   await page.locator('.aff-chart svg').waitFor();
   await page.getByRole('button',{name:'Ventes et commissions',exact:true}).click();await page.locator('#aff-sales-table tbody tr').first().waitFor();assert.equal(await page.locator('#aff-sales-table tbody tr').count(),20);
   await page.getByRole('button',{name:'Suivante',exact:true}).click();await page.getByText('42 ventes · page 2 / 3').waitFor();
   await page.locator('#aff-sales-table button[data-aff="history"]').first().click();await page.locator('#aff-dialog[open]').waitFor();await page.getByRole('button',{name:'Fermer',exact:true}).click();
   await page.getByRole('button',{name:'Paiements',exact:true}).click();await page.locator('#aff-payments tbody tr').first().waitFor();assert.equal(await page.locator('#aff-payments th').count(),4);
   for(const theme of ['light','dark']){await page.locator('#theme-select').selectOption(theme);for(const width of [1440,390]){await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Horizontal page overflow');}}
   if(process.env.AFFILIATION_QA_DIR){const {mkdirSync}=require('node:fs');mkdirSync(process.env.AFFILIATION_QA_DIR,{recursive:true});await page.getByRole('button',{name:'Vue d’ensemble',exact:true}).click();await page.locator('.aff-chart svg').waitFor();await page.screenshot({path:join(process.env.AFFILIATION_QA_DIR,'mobile.png'),fullPage:true});await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:join(process.env.AFFILIATION_QA_DIR,'desktop.png'),fullPage:true});}
   assert.deepEqual(errors,[]);console.log('Affiliation: empty/data states, partners, filters, pagination, revisions, payments, responsive and themes OK');
 }finally{await browser?.close();server.kill();await new Promise(r=>server.once('exit',r));rmSync(temp,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
