// Exercise both shipped browsers and encrypted restart persistence, offline,
// with the same non-root, read-only filesystem and tmpfs as production.
import {browserContext,captureSession} from './affiliation-browser.mjs';
import {saveSession,loadSession,createActions} from './affiliation-worker.mjs';
import {PORTAL} from './domadoo.mjs';
import {ensureAuthenticated} from './domadoo-auth.mjs';
const transport=route=>route.fulfill({contentType:'text/html',body:'<h1>LinKs browser ready</h1>'});
for(const engine of ['firefox','chromium']){
 let runtime;
 try{
  runtime=await browserContext(undefined,true,{engine,transport});await runtime.page.goto(PORTAL);
  await runtime.context.addCookies([{name:'synthetic',value:'test-only',url:PORTAL,httpOnly:true,secure:true}]);
  await runtime.page.evaluate(()=>{localStorage.setItem('local','retained');sessionStorage.setItem('session','retained')});
  if((await runtime.page.screenshot({type:'jpeg'})).length<100)throw new Error('Browser rendering failed');
  await saveSession('domadoo',await captureSession(runtime));await runtime.browser.close();
  runtime=await browserContext(await loadSession('domadoo'),false,{engine,transport});await runtime.page.goto(PORTAL);
  if(await runtime.page.locator('h1').textContent()!=='LinKs browser ready')throw new Error('Browser smoke failed');
  if(!((await runtime.context.cookies()).some(c=>c.name==='synthetic'&&c.value==='test-only')))throw new Error('Cookie restart failed');
  if(!await runtime.page.evaluate(()=>localStorage.getItem('local')==='retained'&&sessionStorage.getItem('session')==='retained'))throw new Error('Storage restart failed');
  await runtime.browser.close();
  let posts=0;
  runtime=await browserContext(undefined,false,{engine,transport:route=>{
    if(route.request().method()==='POST'){
      posts++;
      return route.fulfill({contentType:'text/html',headers:{'set-cookie':'synthetic_auth=valid; Path=/; Secure; HttpOnly'},body:'<script>location.replace("/fr/affiliation")</script>'});
    }
    return route.fulfill({contentType:'text/html',body:(route.request().headers().cookie||'').includes('synthetic_auth=valid')?
      '<a id="my_affiliate_link">Synthetic affiliate</a><section id="myaffiliateaccount-summary"><div class="list-group-hover">Synthetic</div></section>':
      '<form method="post" action="/fr/authentification"><input id="field-email" name="email"><input id="field-password" type="password" name="password"><button id="submit-login">Login</button></form>'});
  }});
  await ensureAuthenticated(runtime,()=>({login:'synthetic@example.invalid',password:'TEST-ONLY'}));
  if(posts!==1)throw new Error('Automatic login failed');
  if(await runtime.page.evaluate(()=>fetch('/fr/authentification',{method:'POST'}).then(()=>true).catch(()=>false)))throw new Error('Collection can submit login');
  console.log(`Affiliation ${engine} runtime and encrypted session restart OK: ${process.arch}`);
 }finally{await runtime?.browser.close()}
}
await createActions().action('disconnect',{account:'domadoo'});
