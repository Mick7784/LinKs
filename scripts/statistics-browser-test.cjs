// Isolated regression: large histories, bounded DOM, shared widgets and safe text.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process'),{mkdtempSync,rmSync,mkdirSync}=require('node:fs'),{tmpdir}=require('node:os'),{join,resolve}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-statistics-')),database=join(temp,'stats.db'),python=process.env.PYTHON_PATH||'python3',origin='http://127.0.0.1:8081';
 execFileSync(python,[resolve(__dirname,'fixtures.py'),database]);
 const server=spawn(python,[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:database,UPLOAD_DIR:join(temp,'uploads')},stdio:'ignore'});let browser;
 const api=async(path,data,method=data?'POST':'GET')=>{const response=await fetch(origin+path,{method,headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(response.ok,await response.clone().text());return response.status===204?null:response.json()};
 try{
  for(let i=0;i<100;i++){try{if((await fetch(origin+'/healthz')).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
  const campaign=await api('/api/content',{type:'promo',internal_name:'Historique conservé',title:'Historique conservé',url:'https://example.com/history'});
  await api('/api/content/'+campaign.id+'/archive',{});
  execFileSync(python,['-c',`import sqlite3,sys;from datetime import datetime;from zoneinfo import ZoneInfo
db=sqlite3.connect(sys.argv[1]);day=datetime.now(ZoneInfo('Europe/Paris')).date().isoformat();db.executemany('INSERT INTO counts VALUES(?,?,?,?,?)',[(day,'youtube','click','Lien '+str(i).zfill(3),i+1) for i in range(503)]+[(day,'youtube','view','',100),(day,'instagram','click','<img src=x onerror=alert(1)>',1),('2020-01-01','youtube','view','',7)]);db.commit()`,database]);
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin);await page.locator('#chart svg').waitFor();
  assert.equal(await page.locator('#dashboard .analytics-kpis article').count(),5);assert.equal(await page.locator('#dashboard #story-list,#dashboard #sources,#dashboard #promo-planning').count(),0);
  await page.evaluate(()=>document.querySelector('#analytics-summary').dataset.identity='same');
  await page.locator('[data-open-statistics=all]').click();await page.locator('#statistics #chart svg').waitFor();
  assert.equal(await page.locator('#statistics #analytics-summary').getAttribute('data-identity'),'same');
  await page.locator('#top-links [role=status]').filter({hasText:'504 résultats'}).waitFor();assert.equal(await page.locator('#top-links .engagement-row').count(),20);
  await page.locator('#top-links button').filter({hasText:'Suivant'}).click();assert((await page.locator('#top-links [role=status]').textContent()).includes('2 / 26'));
  await page.locator('#analysis-search').fill('Lien 001');assert.equal(await page.locator('#top-links .engagement-row').count(),1);assert.equal(await page.locator('#top-links .engagement-value strong').textContent(),'2');
  await page.locator('#analysis-search').fill('<img');assert.equal(await page.locator('#top-links img').count(),0);assert((await page.locator('#top-links').textContent()).includes('<img'));
  await page.locator('#analysis-search').fill('');await page.selectOption('#analysis-sort','name');assert((await page.locator('#top-links .engagement-copy strong').first().textContent()).startsWith('<img'));
  await page.selectOption('#analysis-scope','campaigns');assert(await page.locator('[data-analysis=public]').isHidden());assert((await page.locator('#campaign-details').textContent()).includes('Historique conservé'));
  await page.selectOption('#period','custom');await page.locator('#stats-start').fill('2020-01-01');await page.locator('#stats-end').fill('2020-01-01');await page.waitForFunction(()=>document.querySelector('#views').textContent==='7');
  await page.selectOption('#period','14');await page.selectOption('#source','instagram');await page.waitForFunction(()=>document.querySelector('#clicks').textContent==='1');assert.equal(await page.locator('#views').textContent(),'0');
  await page.selectOption('#source','');await page.selectOption('#analysis-scope','all');
  for(const width of [1440,768,390,320]){await page.setViewportSize({width,height:900});for(const theme of ['light','dark']){await page.selectOption('#theme-select',theme);await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),JSON.stringify(await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,nodes:[...document.querySelectorAll('#statistics *')].filter(n=>n.getBoundingClientRect().right>innerWidth+1).map(n=>[n.tagName,n.id,n.className,Math.round(n.getBoundingClientRect().right)]).slice(0,12)}))));if(process.env.STATISTICS_SCREENSHOTS&&[1440,390].includes(width)){mkdirSync(process.env.STATISTICS_SCREENSHOTS,{recursive:true});await page.screenshot({path:join(process.env.STATISTICS_SCREENSHOTS,`statistics-${width}-${theme}.png`),fullPage:true,animations:'disabled'})}}}
  assert.equal(await page.locator('#analytics-summary').count(),1);assert.deepEqual(errors,[]);
  console.log('PASS statistics: 504 links, paging/search/sort/scopes, archived campaign, historical dates, source isolation, XSS text, shared DOM, four widths and both themes');
 }finally{if(browser)await browser.close();server.kill();await new Promise(r=>server.exitCode!==null?r():server.once('exit',r));rmSync(temp,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
