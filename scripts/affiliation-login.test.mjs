import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {browserContext,captureSession,connectionDiagnostic,requestTarget,safeFailure,restoredState,browserEngine,openPortal} from './affiliation-browser.mjs';
import {PORTAL,authenticationStage,assertPortal} from './domadoo.mjs';
const directory=await mkdtemp(join(tmpdir(),'links-login-test-'));
process.env.AFFILIATION_DATA_DIR=directory;
const {saveSession,loadSession,createActions}=await import('./affiliation-worker.mjs');
test.after(()=>rm(directory,{recursive:true,force:true}));
const form='<form action="/fr/authentification" method="post"><input id="field-email"><input id="field-password" type="password"><button id="submit-login">Connexion</button></form>';
const connected='<section id="myaffiliateaccount-summary"><div class="list-group-hover">Synthetic affiliate account</div></section>';

test('engine configuration, legacy compatibility and diagnostic redaction',()=>{
  delete process.env.AFFILIATION_BROWSER;assert.equal(browserEngine(),'firefox');
  process.env.AFFILIATION_BROWSER='invalid';assert.throws(browserEngine,/AFFILIATION_BROWSER/);delete process.env.AFFILIATION_BROWSER;
  assert.equal(restoredState({cookies:[],origins:[]},'firefox').session,'browser_changed');
  assert.equal(restoredState({cookies:[],origins:[]},'chromium').session,'restored');
  assert.equal(restoredState({unexpected:true},'firefox').session,'unreadable');
  assert.equal(requestTarget('https://www.domadoo.fr/cdn-cgi/challenge-platform/SECRET?token=SECRET'),'domadoo:verification');
  assert.equal(requestTarget('https://SECRET@example.org/SECRET?email=PRIVATE'),'externe');
  assert.equal(safeFailure(new Error('net::ERR_CERT_AUTHORITY_INVALID https://secret')),'tls');
  assert.equal(safeFailure(new Error('Timeout https://secret')),'timeout');
});

for(const engine of ['firefox','chromium'])test(`${engine}: authenticated cookies, localStorage, IndexedDB and sessionStorage survive encrypted restart`,{timeout:60000},async()=>{
 let runtime;
 const transport=route=>route.fulfill({contentType:'text/html',body:form});
 try{
  runtime=await browserContext(undefined,true,{engine,transport});await runtime.page.goto(PORTAL);
  await runtime.context.addCookies([{name:'test_session',value:'SYNTHETIC-COOKIE',url:PORTAL,httpOnly:true,secure:true}]);
  await runtime.page.evaluate(async()=>{
    localStorage.setItem('local','SYNTHETIC-LOCAL');sessionStorage.setItem('session','SYNTHETIC-SESSION');
    await new Promise((resolve,reject)=>{const req=indexedDB.open('synthetic',1);req.onupgradeneeded=()=>req.result.createObjectStore('auth');req.onerror=reject;req.onsuccess=()=>{const db=req.result,tx=db.transaction('auth','readwrite');tx.objectStore('auth').put('SYNTHETIC-IDB','key');tx.oncomplete=()=>{db.close();resolve()}}});
  });
  const state=await captureSession(runtime);await saveSession('domadoo',state);await runtime.browser.close();
  const ciphertext=await readFile(join(directory,'domadoo.session'));assert.equal(ciphertext.includes('SYNTHETIC'),false);
  runtime=await browserContext(await loadSession('domadoo'),false,{engine,transport});await runtime.page.goto(PORTAL);
  assert.equal(runtime.diagnostic.session,'restored');
  assert.equal((await runtime.context.cookies()).find(c=>c.name==='test_session')?.value,'SYNTHETIC-COOKIE');
  assert.deepEqual(await runtime.page.evaluate(async()=>({local:localStorage.getItem('local'),session:sessionStorage.getItem('session'),idb:await new Promise(resolve=>{const req=indexedDB.open('synthetic',1);req.onsuccess=()=>{const db=req.result,r=db.transaction('auth').objectStore('auth').get('key');r.onsuccess=()=>{db.close();resolve(r.result)}}})})),{local:'SYNTHETIC-LOCAL',session:'SYNTHETIC-SESSION',idb:'SYNTHETIC-IDB'});
  assert.equal(JSON.stringify(await connectionDiagnostic(runtime)).includes('SYNTHETIC'),false);
  await runtime.page.evaluate(()=>sessionStorage.setItem('session','UPDATED'));await runtime.page.goto(PORTAL);
  assert.equal(await runtime.page.evaluate(()=>sessionStorage.getItem('session')),'UPDATED','do not overwrite the live session on navigation');
 }finally{await runtime?.browser.close()}
});

test('human form POST and redirect remain allowed; unsafe destinations and automated POST are blocked',{timeout:60000},async()=>{
 for(const human of [true,false]){
  let posts=0;const runtime=await browserContext(undefined,human,{transport:route=>{
    const r=route.request();
    if(r.method()==='POST'){posts++;return route.fulfill({status:302,headers:{location:PORTAL+'?back=PRIVATE'},body:''})}
    return route.fulfill({contentType:'text/html',body:form,headers:{'cf-ray':'0123456789abcdef-CDG'}});
  }});
  try{
    await runtime.page.goto(PORTAL);
    await runtime.page.locator('#field-password').fill('SYNTHETIC-PASSWORD');
    const stopped=runtime.page.waitForEvent('requestfailed',{timeout:10000});
    await runtime.page.locator('#submit-login').click();
    await stopped;
    // Playwright routes intercept only the first request in an HTTP redirect
    // chain. The closed local proxy guarantees the redirected URL cannot escape
    // fixtures. Verify the observed redirect, then serve its landing page.
    if(human)assert(runtime.diagnostic.navigation.some(n=>n.redirected_from==='domadoo:authentification'));
    await runtime.page.goto(PORTAL);
    assert.equal(posts,human?1:0);
    if(human){
      await runtime.page.evaluate(()=>fetch('https://example.org/SECRET?token=PRIVATE',{method:'POST',body:'SYNTHETIC-PASSWORD'}).catch(()=>{}));
      const d=await connectionDiagnostic(runtime);
      assert(d.navigation.some(n=>n.redirected_from==='domadoo:authentification'));assert.equal(d.ray_id,'0123456789abcdef-CDG');
      assert(d.blocked.some(n=>n.target==='externe'));assert(!JSON.stringify(d).match(/PRIVATE|SECRET|PASSWORD|example.org/));
      await assert.rejects(()=>runtime.page.goto('https://www.domadoo.fr/fr/identite?token=PRIVATE'));
      assert(runtime.diagnostic.blocked.some(n=>n.navigation&&n.target==='domadoo:autre'));
    }
  }finally{await runtime.browser.close()}
 }
});

test('security checks, form errors, MFA and HTTP rejection stay distinct and verify never reloads a challenge',{timeout:60000},async()=>{
 let runtime,body='<h2>Performing security verification</h2>',status=403,navigations=0;
 const controller=createActions(async(state,human)=>runtime=await browserContext(state,human,{transport:route=>{navigations++;return route.fulfill({status,contentType:'text/html',body})}}));
 try{
  await controller.action('disconnect',{account:'domadoo'});
  let result=await controller.action('login/start',{account:'domadoo'});
  assert.equal(result.diagnostic.stage,'security_check');assert.equal(result.diagnostic.session,'new');
  assert.equal(result.challenge,true);await controller.action('login/verify',{account:'domadoo'});assert.equal(navigations,1);
  await assert.rejects(()=>assertPortal(runtime.page),e=>e.code==='security_check'&&!e.message.includes('Reconnexion requise'));
  await runtime.page.setContent(form);assert.equal(await authenticationStage(runtime.page),'login_form');
  const beforeVerify=runtime.page.url();await controller.action('login/verify',{account:'domadoo'});assert.equal(runtime.page.url(),beforeVerify);assert.equal(navigations,1);
  await runtime.page.setContent('<form><input type="password"><p class="alert-danger">SYNTHETIC PRIVATE ERROR</p></form>');
  assert.equal(await authenticationStage(runtime.page),'form_error');
  await runtime.page.setContent('<input autocomplete="one-time-code">');assert.equal(await authenticationStage(runtime.page),'verification');
  body='<h1>Forbidden</h1>';await openPortal(runtime);assert.equal((await connectionDiagnostic(runtime)).stage,'http_error');
  assert(runtime.diagnostic.http_errors.some(e=>e.status===403));
  const goto=runtime.page.goto.bind(runtime.page);runtime.page.goto=async()=>{throw new Error('Timeout with SECRET')};
  const timed=await openPortal(runtime);assert.equal(timed.navigation_error,'timeout');assert.equal(runtime.page.isClosed(),false);runtime.page.goto=goto;
 }finally{await controller.close({remember:false})}
});

test('reopen resumes a pending encrypted session; promotion, restart and disconnect preserve correct state',{timeout:60000},async()=>{
 let runtime;const factory=async(state,human)=>runtime=await browserContext(state,human,{transport:route=>route.fulfill({contentType:'text/html',body:form})});
 let controller=createActions(factory);
 try{
  await controller.action('disconnect',{account:'domadoo'});
  await controller.action('login/start',{account:'domadoo'});
  await runtime.page.evaluate(()=>sessionStorage.setItem('checkpoint','SYNTHETIC-CHECKPOINT'));
  await controller.action('login/close',{account:'domadoo'});
  await assert.rejects(()=>loadSession('domadoo'));assert.equal((await readFile(join(directory,'domadoo.pending-session'))).includes('SYNTHETIC'),false);
  controller=createActions(factory);const resumed=await controller.action('login/start',{account:'domadoo'});
  assert.equal(resumed.diagnostic.session,'restored');assert.equal(await runtime.page.evaluate(()=>sessionStorage.getItem('checkpoint')),'SYNTHETIC-CHECKPOINT');
  await runtime.page.setContent(connected);
  const accepted=await controller.action('login/state',{account:'domadoo'});assert.equal(accepted.connected,true);
  const valid=await readFile(join(directory,'domadoo.session'));await assert.rejects(()=>loadSession('domadoo',true));
  const restarted=await controller.action('login/start',{account:'domadoo'});assert.equal(restarted.diagnostic.session,'restored');
  await controller.action('login/close',{account:'domadoo'});assert.deepEqual(await readFile(join(directory,'domadoo.session')),valid,'an incomplete login must not replace the validated session');
  await controller.action('disconnect',{account:'domadoo'});await assert.rejects(()=>loadSession('domadoo'));await assert.rejects(()=>loadSession('domadoo',true));
  await writeFile(join(directory,'domadoo.session'),'broken');
  const unreadable=await controller.action('login/start',{account:'domadoo'});assert.equal(unreadable.diagnostic.session,'unreadable');
 }finally{await controller.close({remember:false})}
});
