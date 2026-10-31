import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {browserContext,captureSession,connectionDiagnostic,requestTarget,safeFailure,restoredState,browserEngine,openPortal} from './affiliation-browser.mjs';
import {PORTAL,authenticationStage,assertPortal} from './domadoo.mjs';
import {ensureAuthenticated,environmentCredentials} from './domadoo-auth.mjs';
const directory=await mkdtemp(join(tmpdir(),'links-login-test-'));
process.env.AFFILIATION_DATA_DIR=directory;
const {saveSession,loadSession,createActions}=await import('./affiliation-worker.mjs');
test.after(()=>rm(directory,{recursive:true,force:true}));
// Tests must never inherit a developer's actual optional merchant credentials.
delete process.env.DOMADOO_LOGIN;delete process.env.DOMADOO_PASSWORD;
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

const autoForm='<form action="/fr/authentification?back=%2Ffr%2Faffiliation" method="post"><input name="back" type="hidden" value="/fr/affiliation"><input name="csrf" type="hidden" value="SYNTHETIC-CSRF"><input id="field-email" name="email"><input id="field-password" name="password" type="password"><button id="submit-login" name="submitLogin">Connexion</button></form>';
const autoConnected='<a id="my_affiliate_link">Synthetic account</a>'+connected;
const syntheticCredentials={login:'synthetic@example.invalid',password:'SYNTHETIC-PASSWORD'};
function automaticFixture({mode='success',accountPage=autoConnected}={}){
 const state={posts:0,submitted:null,mode};
 state.transport=async route=>{
   const request=route.request();
   if(request.method()==='POST'){
     state.posts++;state.submitted=new URLSearchParams(request.postData());
     if(state.mode==='cloudflare')return route.fulfill({status:403,headers:{'cf-mitigated':'challenge','cf-ray':'0123456789abcdef-CDG'},contentType:'text/html',body:'<h2>Performing security verification</h2>'});
     if(state.mode==='error')return route.fulfill({contentType:'text/html',body:'<div class="alert-danger">SYNTHETIC PRIVATE ERROR</div>'+autoForm});
     if(state.mode==='mfa')return route.fulfill({contentType:'text/html',body:'<input autocomplete="one-time-code">'});
     if(state.mode==='blocked')return route.fulfill({contentType:'text/html',body:'<script>location.replace("/fr/mon-compte?token=PRIVATE")</script>'});
     if(state.mode==='http')return route.fulfill({status:403,contentType:'text/html',body:'Forbidden'});
     // A browser navigation exercises the same allowlist without letting HTTP
     // redirect follow-ups escape the fixture transport (covered separately).
     state.mode='success';
     return route.fulfill({contentType:'text/html',headers:{'set-cookie':'synthetic_auth=valid; Path=/; Secure; HttpOnly'},body:'<script>location.replace("/fr/affiliation")</script>'});
   }
   const valid=(request.headers().cookie||'').includes('synthetic_auth=valid')&&state.mode!=='expired';
   return route.fulfill({contentType:'text/html; charset=utf-8',body:valid?accountPage:state.mode==='changed'?autoForm.replace('/fr/authentification?','/fr/identite?'):autoForm});
 };
 return state;
}

test('automatic form authentication, session reuse and expired session renewal; collection cannot POST',{timeout:60000},async()=>{
 const fixture=automaticFixture();let runtime;
 try{
  runtime=await browserContext(undefined,false,{transport:fixture.transport});
  assert.deepEqual(await ensureAuthenticated(runtime,()=>syntheticCredentials),{authenticated:true});
  assert.equal(fixture.posts,1);assert.equal(fixture.submitted.get('password'),syntheticCredentials.password);assert.equal(fixture.submitted.get('email'),syntheticCredentials.login);
  assert.equal(fixture.submitted.get('csrf'),'SYNTHETIC-CSRF');assert.equal(fixture.submitted.get('back'),'/fr/affiliation');
  const state=await captureSession(runtime);await runtime.browser.close();
  runtime=await browserContext(state,false,{transport:fixture.transport});
  assert.deepEqual(await ensureAuthenticated(runtime,()=>{throw new Error('Valid session must not need credentials')}),{authenticated:false});
  assert.equal(fixture.posts,1);
  const sent=await runtime.page.evaluate(()=>fetch('/fr/authentification',{method:'POST'}).then(()=>true).catch(()=>false));
  assert.equal(sent,false);assert.equal(fixture.posts,1,'authentication permission must be revoked before collection');
  await runtime.context.clearCookies();
  await ensureAuthenticated(runtime,()=>syntheticCredentials);assert.equal(fixture.posts,2);
  assert(!JSON.stringify(await connectionDiagnostic(runtime)).match(/SYNTHETIC|synthetic@example|PRIVATE/));
 }finally{await runtime?.browser.close()}
});

test('automatic login distinguishes challenge, form rejection, MFA, policy and HTTP errors without resubmission',{timeout:60000},async()=>{
 for(const [mode,code] of [['cloudflare','security_check'],['error','authentication_rejected'],['mfa','authentication_verification'],['blocked','request_policy'],['http','authentication_http_error'],['changed','authentication_form_changed']]){
  const fixture=automaticFixture({mode}),runtime=await browserContext(undefined,false,{transport:fixture.transport});
  try{
   await assert.rejects(()=>ensureAuthenticated(runtime,()=>syntheticCredentials,{timeoutMs:5000}),e=>e.code===code&&!/SYNTHETIC|PRIVATE|synthetic@example/.test(e.message));
   assert.equal(fixture.posts,mode==='changed'?0:1);
   const sent=await runtime.page.evaluate(()=>fetch('/cdn-cgi/challenge-platform/synthetic',{method:'POST'}).then(()=>true).catch(()=>false)).catch(()=>false);
   assert.equal(sent,false);assert.equal(fixture.posts,mode==='changed'?0:1);
   const d=await connectionDiagnostic(runtime);assert(!JSON.stringify(d).match(/SYNTHETIC|PRIVATE|synthetic@example/));
   if(mode==='blocked')assert.equal(d.policy_navigation.target,'domadoo:mon-compte');
  }finally{await runtime.browser.close()}
 }
});

test('credentials are optional, complete, scoped to the built-in account, and never returned by a missing-session error',async()=>{
 assert.equal(environmentCredentials('domadoo',{}),null);
 assert.throws(()=>environmentCredentials('domadoo',{DOMADOO_LOGIN:'PRIVATE'}),e=>e.code==='credentials_configuration'&&!e.message.includes('PRIVATE'));
 assert.equal(environmentCredentials('a'.repeat(32),{DOMADOO_LOGIN:'PRIVATE',DOMADOO_PASSWORD:'SECRET'}),null);
 const controller=createActions(()=>{throw new Error('Browser must not start')});
 await controller.action('disconnect',{account:'domadoo'});
 await assert.rejects(()=>controller.action('collect',{account:'domadoo'}),e=>e.code==='session_unreadable');
});

test('worker preserves the valid session on failure and checkpoints the automatic challenge for human fallback',{timeout:30000},async()=>{
 process.env.DOMADOO_LOGIN=syntheticCredentials.login;process.env.DOMADOO_PASSWORD=syntheticCredentials.password;
 const fixture=automaticFixture({mode:'cloudflare'});let runtime;
 const controller=createActions(async(state,human)=>runtime=await browserContext(state,human,{transport:fixture.transport}));
 try{
  await controller.action('disconnect',{account:'domadoo'});
  await saveSession('domadoo',{version:2,browser:'firefox',storageState:{cookies:[],origins:[]},sessionStorage:[]});
  const previous=await readFile(join(directory,'domadoo.session'));
  await assert.rejects(()=>controller.action('collect',{account:'domadoo'}),e=>e.code==='security_check'&&!e.message.includes('SYNTHETIC'));
  assert.equal(fixture.posts,1);assert.deepEqual(await readFile(join(directory,'domadoo.session')),previous);
  const pending=await loadSession('domadoo',true);assert(pending.saved_at);assert(!JSON.stringify(pending).includes(syntheticCredentials.password));
  const fallback=await controller.action('login/start',{account:'domadoo'});assert.equal(fallback.active,true);assert.equal(fallback.diagnostic.session,'restored');
  assert.equal(fixture.posts,1,'human fallback must not resubmit the configured password');
 }finally{delete process.env.DOMADOO_LOGIN;delete process.env.DOMADOO_PASSWORD;await controller.close({remember:false});await controller.action('disconnect',{account:'domadoo'})}
});

test('worker collects financial data after first automatic login, restores it after restart and renews an expired session',{timeout:60000},async()=>{
 const rows=[['Clics','1'],['Clics uniques','1'],['Ventes en attente','0'],['Ventes approuvées','1'],['Gains','1,23 €'],['Clics','1'],['Clics uniques','1'],['Ventes approuvées','1'],['Total des gains','1,23 €'],['Total des paiements','0,00 €'],['Paiements en attente','0,00 €'],['Solde','1,23 €']];
 const accountPage='<a id="my_affiliate_link">Synthetic account</a><section id="myaffiliateaccount-summary">Last 30 days Total'+rows.map(([label,value])=>`<div class="list-group-hover">${label}<span class="pull-xs-right">${value}</span></div>`).join('')+'</section>'+[
  ['sales-commissions',['ID','Date','Total de la commande','Votre commission','Approuvé'],'<tr><td>123</td><td>2026-10-21 12:00:00</td><td>12,30 €</td><td>1,23 €</td><td>check</td></tr>'],
  ['myvouchers',['Créé à','Code','Montant','Approuvé','Utilisé'],'']
 ].map(([id,headers,body])=>`<section id="myaffiliateaccount-${id}"><table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></section>`).join('');
 const fixture=automaticFixture({accountPage}),factory=(state,human)=>browserContext(state,human,{transport:fixture.transport});
 let controller=createActions(factory);
 process.env.DOMADOO_LOGIN=syntheticCredentials.login;process.env.DOMADOO_PASSWORD=syntheticCredentials.password;
 try{
  await controller.action('disconnect',{account:'domadoo'});
  const first=await controller.action('collect',{account:'domadoo'});
  assert.equal(first.complete,true);assert.equal(first.transactions[0].commission_cents,123);assert.equal(first.summary.balance,123);assert.equal(fixture.posts,1);
  assert(!JSON.stringify(first).includes('SYNTHETIC'));assert(!(await readFile(join(directory,'domadoo.session'))).includes('SYNTHETIC'));
  controller=createActions(factory);delete process.env.DOMADOO_PASSWORD;
  assert.deepEqual(await controller.action('collect',{account:'domadoo'}),first,'valid stored session works even without configured password');assert.equal(fixture.posts,1);
  process.env.DOMADOO_PASSWORD=syntheticCredentials.password;fixture.mode='expired';
  assert.deepEqual(await controller.action('collect',{account:'domadoo'}),first);assert.equal(fixture.posts,2);
 }finally{delete process.env.DOMADOO_LOGIN;delete process.env.DOMADOO_PASSWORD;await controller.close({remember:false});await controller.action('disconnect',{account:'domadoo'})}
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
