// Backup transfer through the unchanged Settings UI; synthetic data only.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {mkdtempSync,rmSync,readFileSync}=require('node:fs');
const {tmpdir}=require('node:os'),{join,resolve}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-backup-')),database=join(temp,'analytics.db');
 const python=process.env.PYTHON_PATH||'python3',origin='http://127.0.0.1:8081';
 const fixture=resolve(__dirname,'fixtures/tracked-categories-v1326.sql');
 execFileSync(python,['-c',"import sqlite3,sys;from pathlib import Path;db=sqlite3.connect(sys.argv[1]);db.executescript(Path(sys.argv[2]).read_text(encoding='utf-8'));db.close()",database,fixture]);
 const code="import sys,threading;sys.path.insert(0,'scripts');import analytics as a;from tracked_categories_migration_test import BaselineClock;a.datetime=BaselineClock;a.init();threading.Thread(target=a.serve(3003,False,'127.0.0.1').serve_forever,daemon=True).start();a.serve(8081,True,'127.0.0.1').serve_forever()";
 const server=spawn(python,['-c',code],{cwd:resolve(__dirname,'..'),env:{...process.env,ANALYTICS_DB:database,UPLOAD_DIR:join(temp,'uploads'),APP_RELEASE_VERSION:'V1.326',APP_RELEASE_ID:'bundled:V1.326'},stdio:'ignore'});
 let browser;
 const state=()=>JSON.parse(execFileSync(python,['-c',"import sys,json,sqlite3;sys.path.insert(0,sys.argv[2]);from tracked_categories_migration_test import conservation_state;db=sqlite3.connect(sys.argv[1]);print(json.dumps(conservation_state(db,include_category=True)));db.close()",database,__dirname],{encoding:'utf8'}));
 const safetyCopies=()=>Number(execFileSync(python,['-c',"import sys;from pathlib import Path;print(len(list((Path(sys.argv[1])/'restore-safety').glob('*/analytics.db'))))",temp],{encoding:'utf8'}));
 try{
  let ready=false;for(let attempt=0;attempt<100;attempt++){try{if((await fetch(origin+'/healthz')).ok){ready=true;break}}catch{}await new Promise(resolve=>setTimeout(resolve,100))}assert(ready,'Disposable backend must start');
  const before=state();assert(!before.tracked_links.columns.includes('category'),'Startup physically removes the historical column');
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
  const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true}),errors=[],confirmations=[];
  let approve=false;
  page.on('pageerror',error=>errors.push(error.message));
  page.on('dialog',dialog=>{confirmations.push(dialog.message());return approve?dialog.accept():dialog.dismiss()});
  await page.goto(origin);await page.locator('#chart svg').waitFor();await page.locator('[data-tab="settings"]').click();
  await page.locator('[data-settings-section="maintenance"]').click();await page.locator('#backup-panel').waitFor();
  const downloaded=page.waitForEvent('download');await page.locator('#download-backup').click();const download=await downloaded;
  assert.match(download.suggestedFilename(),/\.json$/);
  const exported=JSON.parse(readFileSync(await download.path(),'utf8'));
  assert.equal(exported.version,3);assert(exported.tables.tracked_links.every(row=>!Object.hasOwn(row,'category')));
  assert.deepEqual(state(),before,'Downloading must not modify any database value');
  let scenario=0;
  for(const width of [1440,390]){await page.setViewportSize({width,height:1000});for(const theme of ['light','dark']){
   await page.selectOption('#theme-select',theme);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Backup controls must fit the viewport');
   const payload=structuredClone(exported);payload.version=[3,3,2,1][scenario];
   if(scenario%2===0)for(const row of payload.tables.tracked_links)row.category='Ancienne valeur à ignorer : YouTube / été';
   const file={name:`backup-${scenario}.json`,mimeType:'application/json',buffer:Buffer.from(JSON.stringify(payload))};
   const initialCopies=safetyCopies(),initialDialogs=confirmations.length;
   approve=false;
   const preview=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/restore/preview');
   await page.locator('#restore-backup').setInputFiles(file);assert.equal((await preview).status(),200);
   await page.waitForFunction(()=>document.getElementById('restore-backup').value==='');
   assert.equal(confirmations.length,initialDialogs+1);assert.match(confirmations.at(-1),/redirection/);
   assert.deepEqual(state(),before,'Cancelling the preview keeps the complete reference');assert.equal(safetyCopies(),initialCopies);
   approve=true;
   await page.locator('#restore-backup').setInputFiles(file);
   await page.locator('#backup-status').filter({hasText:'Sauvegarde restaurée'}).waitFor();
   await page.waitForFunction(()=>document.getElementById('restore-backup').value==='');
   assert.deepEqual(state(),before,'Importing and repeating snapshots keeps all useful and historical values');
   assert.equal(safetyCopies(),initialCopies+1);
   assert.equal(await page.locator('#download-backup').isEnabled(),true);
   if(process.env.UI_SCREENSHOTS)await page.screenshot({path:join(process.env.UI_SCREENSHOTS,`backup-${width}-${theme}.png`),fullPage:true,animations:'disabled'});
   scenario++;
  }}
  const after=await fetch(origin+'/api/backup').then(response=>response.json());
  const canonical=rows=>rows.map(row=>Object.fromEntries(Object.entries(row).sort(([a],[b])=>a.localeCompare(b)))).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));
  for(const table of Object.keys(exported.tables))assert.deepEqual(canonical(after.tables[table]),canonical(exported.tables[table]),table);
  assert(after.tables.tracked_links.every(row=>!Object.hasOwn(row,'category')));
  assert.deepEqual(errors,[]);
  console.log('PASS: real backup download without categories, v1/v2/v3 old/new imports, read-only preview cancellation, safety copies, exact data/counters and historical values after four restores, unchanged Settings desktop/mobile light/dark.');
 }finally{
  await browser?.close();const exited=new Promise(resolve=>server.exitCode!==null?resolve():server.once('exit',resolve));server.kill();await exited;rmSync(temp,{recursive:true,force:true});
 }
})().catch(error=>{console.error(error);process.exitCode=1});
