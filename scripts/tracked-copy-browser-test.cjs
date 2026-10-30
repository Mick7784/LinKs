// Copy checks: delayed clipboard activation, verdicts, fallback in modal, preservation.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {mkdtempSync,rmSync}=require('node:fs'),{tmpdir}=require('node:os'),{join,resolve}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-copy-')),python=process.env.PYTHON_PATH||'python3';
 const origin='http://127.0.0.1:8081',db=join(temp,'stats.db');
 execFileSync(python,[resolve(__dirname,'fixtures.py'),db]);
 const server=spawn(python,[resolve(__dirname,'analytics.py')],{
  env:{...process.env,ANALYTICS_DB:db,UPLOAD_DIR:join(temp,'uploads')},stdio:'ignore'
 });
 let browser;
 const api=async(path,data)=>{
  const r=await fetch(origin+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});
  assert(r.ok,await r.clone().text());return r.json();
 };
 try{
  let ready=false;
  for(let i=0;i<100;i++){try{if((await fetch(origin+'/healthz')).ok){ready=true;break}}catch{}await new Promise(r=>setTimeout(r,100));}
  assert(ready,'Test server must start');
  const link=await api('/api/tracked-links',{name:'Caméra à partager',url:'https://shop.reolink.com/product/camera?aff=1404'});
  const sources=(await api('/api/tracking-sources')).items;
  const token=await api(`/api/tracked-links/${link.id}/token`,{source_id:sources[0].id});
  execFileSync(python,['-c',"import sqlite3,sys;db=sqlite3.connect(sys.argv[1]);db.execute('UPDATE tracked_tokens SET click_total=7 WHERE link_id=?',(sys.argv[2],));db.commit()",db,link.id]);
  const before=(await api('/api/tracked-links')).items;
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
  const context=await browser.newContext({viewport:{width:1440,height:900}});
  // Simulate browsers which only accept write() during the initiating gesture.
  await context.addInitScript(()=>{
   window.copyMode='deferred';window.copies=[];window.copyAttempts=[];
   Object.defineProperty(navigator,'clipboard',{value:{
    write:async items=>{
     window.copyAttempts.push(['write',navigator.userActivation.isActive]);
     if(window.copyMode!=='deferred')throw Error('Clipboard write unavailable');
     if(!navigator.userActivation.isActive)throw Error('Missing user activation');
     const blob=await items[0].getType('text/plain');window.copies.push(await blob.text());
    },
    writeText:async value=>{
     window.copyAttempts.push(['writeText']);
     if(window.copyMode!=='text')throw Error('Text write denied');
     window.copies.push(value);
    }
   },configurable:true});
   document.execCommand=command=>{
    window.copyAttempts.push(['exec',document.activeElement?.tagName]);
    if(window.copyMode==='denied')return false;
    if(command!=='copy'||document.activeElement?.tagName!=='TEXTAREA')return false;
    window.copies.push(document.activeElement.value);return true;
   };
  });
  const page=await context.newPage(),errors=[],dialogs=[];
  let verdict={status:'valid',http_status:200},networkFailure=false,approve=false,tokenCalls=0;
  page.on('pageerror',e=>errors.push(e.message));
  page.on('dialog',async d=>{dialogs.push({type:d.type(),message:d.message(),value:d.defaultValue()});if(d.type()==='confirm'&&approve)await d.accept();else await d.dismiss()});
  page.on('request',r=>{if(r.url().endsWith('/token'))tokenCalls++});
  await context.route('**/api/tracked-links/*/check-destination',async route=>{
   assert.equal(route.request().method(),'POST');
   assert.deepEqual(route.request().postDataJSON(),{});
   // Clipboard reservation must precede the asynchronous health check.
   assert.equal((await page.evaluate(()=>window.copyAttempts))[0][0],'write');
   if(networkFailure)return route.abort();
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(verdict)});
  });
  await page.goto(origin);await page.locator('#chart svg').waitFor();
  await page.locator('[data-tab="tracked-links"]').click();
  const row=page.locator(`[data-tracked-id="${link.id}"]`),copy=row.locator('[data-tracked-action="copy"]');
  await row.waitFor();await page.selectOption('#source-'+link.id,sources[0].id);
  const reset=async mode=>page.evaluate(mode=>{window.copyMode=mode;window.copies=[];window.copyAttempts=[]},mode);
  const copied=async expected=>page.waitForFunction(value=>window.copies.at(-1)===value,expected);
  for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:900});
   for(const theme of ['light','dark']){
    await page.selectOption('#theme-select',theme);await reset('deferred');
    await copy.click();await copied(token.url);
    await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('Lien permanent copié'));
    assert.deepEqual(await page.evaluate(()=>window.copyAttempts),[['write',true]]);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   }
  }
  assert.equal(dialogs.length,0);
  for(const code of [403,429,500,null]){
   verdict={status:'unknown',http_status:code};await reset('deferred');
   await copy.click();await copied(token.url);
   await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('Vérification impossible'));
  }
  networkFailure=true;await reset('deferred');await copy.click();await copied(token.url);networkFailure=false;
  assert.equal(dialogs.length,0,'Unknown checks must copy without a prompt');
  for(const code of [404,410]){
   verdict={status:'broken',http_status:code};approve=false;await reset('deferred');
   const previousTokens=tokenCalls;
   await copy.click();await page.waitForFunction(()=>document.querySelector('#notice').textContent==='Copie annulée.');
   assert.equal(tokenCalls,previousTokens,'Cancelled broken link must not create a token');
   assert.deepEqual(await page.evaluate(()=>window.copies),[]);
   assert(dialogs.at(-1).message.startsWith('Attention, lien HS ! Vérifie la destination.'));
   approve=true;await reset('deferred');await copy.click();await copied(token.url);
  }
  verdict={status:'valid',http_status:200};
  await reset('text');await copy.click();await copied(token.url);
  assert.deepEqual((await page.evaluate(()=>window.copyAttempts)).map(x=>x[0]),['write','writeText']);
  await reset('fallback');await copy.click();await copied(token.url);
  assert.deepEqual((await page.evaluate(()=>window.copyAttempts)).map(x=>x[0]),['write','writeText','exec']);
  // The same path inside duplicate reuse must keep the fallback within its modal.
  await page.evaluate(id=>window.LinksTracking.reuseEntity(id),link.id);
  await page.locator('#tracked-reuse-dialog').waitFor();
  await page.selectOption('#tracked-reuse-source',sources[0].id);
  await reset('fallback');await page.locator('#tracked-reuse-copy').click();await copied(token.url);
  await page.waitForFunction(()=>document.querySelector('#tracked-reuse-url').hidden===false);
  assert.equal(await page.locator('#tracked-reuse-url').getAttribute('href'),token.url);
  assert.deepEqual(await page.evaluate(()=>window.copyAttempts.at(-1)),['exec','TEXTAREA']);
  assert.deepEqual((await api('/api/tracked-links')).items,before,'No destination, affiliation, source or click changes');
  await page.selectOption('#tracked-reuse-source',sources[1].id);
  verdict={status:'unknown',http_status:403};await reset('fallback');
  const dialogCount=dialogs.length;
  await page.locator('#tracked-reuse-copy').click();
  await page.waitForFunction(()=>window.copies.length===1);
  const newToken=await api(`/api/tracked-links/${link.id}/token`,{source_id:sources[1].id});
  assert.equal(await page.evaluate(()=>window.copies[0]),newToken.url);
  assert.notEqual(newToken.url,token.url);assert.equal(dialogs.length,dialogCount);
  const after=(await api('/api/tracked-links')).items.find(x=>x.id===link.id);
  assert.equal(after.url,link.url);assert.equal(after.clicks,7);assert.equal(after.sources.length,2);
  assert.equal((await api(`/api/tracked-links/${link.id}/token`,{source_id:sources[0].id})).url,token.url);
  // Absolute clipboard denial must never claim success; keep the existing manual recovery.
  verdict={status:'valid',http_status:200};await reset('denied');
  await page.locator('#tracked-reuse-copy').click();
  await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('refusé la copie automatique'));
  assert.equal(dialogs.at(-1).type,'prompt');assert.equal(dialogs.at(-1).value,newToken.url);
  assert.deepEqual(await page.evaluate(()=>window.copies),[]);
  assert.deepEqual(errors,[]);
  // Also exercise Chromium's real clipboard with a response beyond transient activation.
  const native=await browser.newContext({permissions:['clipboard-read','clipboard-write']});
  await native.route('**/api/tracked-links/*/check-destination',async route=>{
   await new Promise(resolve=>setTimeout(resolve,5500));
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({status:'unknown',http_status:429})});
  });
  const real=await native.newPage();
  real.on('pageerror',e=>errors.push(e.message));
  real.on('dialog',async d=>{errors.push('Unexpected native clipboard dialog: '+d.message());await d.dismiss()});
  await real.goto(origin);await real.locator('#chart svg').waitFor();
  await real.locator('[data-tab="tracked-links"]').click();
  await real.selectOption('#source-'+link.id,sources[0].id);
  await real.locator(`[data-tracked-id="${link.id}"] [data-tracked-action="copy"]`).click();
  await real.waitForFunction(()=>document.querySelector('#notice').textContent.includes('Lien permanent copié'));
  assert.equal(await real.evaluate(()=>navigator.clipboard.readText()),token.url);
  // Real execCommand fallback must work inside the duplicate dialog as well.
  await native.unroute('**/api/tracked-links/*/check-destination');
  await native.route('**/api/tracked-links/*/check-destination',route=>route.fulfill({
   status:200,contentType:'application/json',body:JSON.stringify({status:'unknown',http_status:403})
  }));
  await real.evaluate(()=>{navigator.clipboard.write=async()=>{throw Error('Denied')};navigator.clipboard.writeText=async()=>{throw Error('Denied')}});
  await real.evaluate(id=>window.LinksTracking.reuseEntity(id),link.id);
  await real.locator('#tracked-reuse-dialog').waitFor();
  await real.selectOption('#tracked-reuse-source',sources[1].id);
  await real.locator('#tracked-reuse-copy').click();
  await real.waitForFunction(()=>document.querySelector('#notice').textContent.includes('Lien permanent copié'));
  assert.equal(await real.evaluate(()=>navigator.clipboard.readText()),newToken.url);
  assert.deepEqual(errors,[]);await native.close();
  console.log('PASS: valid/unknown auto-copy, GET-confirmed broken confirmation/cancel, gesture reservation, clipboard fallbacks, modal reuse, stable sources/tokens/clicks, mobile and themes.');
 }finally{
  await browser?.close();const exited=new Promise(resolve=>server.once('exit',resolve));server.kill();await exited;
  rmSync(temp,{recursive:true,force:true});
 }
})().catch(error=>{console.error(error);process.exitCode=1});
