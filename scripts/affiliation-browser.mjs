import {createRequire} from 'node:module';
import {PORTAL,PortalError,allowedPortalRequest,authenticationStage} from './domadoo.mjs';
const require=createRequire(import.meta.url);
export const VIEWPORT={width:1100,height:760};
export function browserEngine(){
  const engine=process.env.AFFILIATION_BROWSER||'firefox';
  if(!['firefox','chromium'].includes(engine))throw new PortalError('AFFILIATION_BROWSER doit être firefox ou chromium.','browser_configuration');
  return engine;
}
// Never include arbitrary paths, query parameters, fragments, headers or bodies
// in diagnostics: login redirects and challenge URLs can contain credentials.
export function requestTarget(address){
  try{
    const u=new URL(address);
    if(['www.domadoo.fr','domadoo.fr'].includes(u.hostname)){
      if(u.pathname.startsWith('/cdn-cgi/challenge-platform/'))return 'domadoo:verification';
      if(u.pathname==='/fr/authentification')return 'domadoo:authentification';
      if(u.pathname==='/fr/affiliation')return 'domadoo:affiliation';
      if(u.pathname==='/fr/mon-compte')return 'domadoo:mon-compte';
      if(u.pathname==='/fr/'||u.pathname==='/')return 'domadoo:accueil';
      return 'domadoo:autre';
    }
    if(u.hostname==='challenges.cloudflare.com')return 'cloudflare:verification';
    if(['www.google.com','www.gstatic.com','www.recaptcha.net'].includes(u.hostname))return 'google:verification';
  }catch{}
  return 'externe';
}
export function safeFailure(error){
  const value=String(error?.message||error||'');
  if(/blockedbyclient|BLOCKED_BY_CLIENT/i.test(value))return 'request_policy';
  if(/timeout|timed.out/i.test(value))return 'timeout';
  if(/NAME_NOT_RESOLVED|UNKNOWN_HOST/i.test(value))return 'dns';
  if(/CERT_|SSL_|SEC_ERROR/i.test(value))return 'tls';
  if(/CONNECTION_|CONNECTION REFUSED|NS_ERROR_NET/i.test(value))return 'network';
  if(/closed|crash/i.test(value))return 'browser_closed';
  return 'navigation_failed';
}
export function restoredState(saved,engine){
  if(!saved)return {session:'new'};
  // V1.4–V1.4.2 stored a Chromium storageState without an envelope. Do not
  // transplant browser-bound cookies into Firefox or silently fall back engines.
  const previous=saved.browser||(saved.cookies&&saved.origins?'chromium':null);
  if(!previous)return {session:'unreadable'};
  if(previous!==engine)return {session:'browser_changed'};
  const state=saved.storageState||saved,sessionStorage=saved.sessionStorage||[];
  if(!Array.isArray(state.cookies)||!Array.isArray(state.origins)||!Array.isArray(sessionStorage)||
    sessionStorage.some(entry=>!Array.isArray(entry.entries)||entry.entries.some(pair=>!Array.isArray(pair)||pair.length!==2||pair.some(v=>typeof v!=='string'))))return {session:'unreadable'};
  return {session:'restored',state,sessionStorage};
}
export async function captureSession(runtime){
  const sessionStorage=await runtime.page.evaluate(()=>{
    if(!['https://www.domadoo.fr','https://domadoo.fr'].includes(location.origin))return [];
    return [{origin:location.origin,entries:Object.entries(window.sessionStorage)}];
  });
  return {version:2,browser:runtime.engine,storageState:await runtime.context.storageState({indexedDB:true}),sessionStorage};
}
export async function browserContext(saved,human=false,{engine=browserEngine(),transport}={}){
  if(!['firefox','chromium'].includes(engine))throw new PortalError('Navigateur non pris en charge.','browser_configuration');
  const options=engine==='chromium'?{executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--disable-dev-shm-usage']}:
    {firefoxUserPrefs:{'signon.rememberSignons':false,'browser.formfill.enable':false}};
  let browser;
  const browserEnv=Object.fromEntries(Object.entries(process.env).filter(([key])=>!['DOMADOO_LOGIN','DOMADOO_PASSWORD'].includes(key)));
  try{browser=await require('playwright-core')[engine].launch({headless:true,timeout:20000,env:browserEnv,...options})}
  catch{throw new PortalError(`Démarrage ${engine} impossible. Vérifier l’image officielle et la mémoire disponible. Aucun accès au portail tenté.`,'browser_launch')}
  try{
    const restored=restoredState(saved,engine);
    const diagnostic={browser:engine,version:browser.version(),mode:'headless',session:restored.session,started_at:new Date().toISOString(),stage:'opening',status:null,ray_id:null,challenge_response:false,navigation:[],blocked:[],failures:[],http_errors:[],navigation_error:null,policy_navigation:null};
    let authenticating=false;
    const record=(list,value)=>{if(JSON.stringify(list.at(-1))!==JSON.stringify(value)){list.push(value);if(list.length>8)list.shift()}};
    const context=await browser.newContext({viewport:VIEWPORT,storageState:restored.state,acceptDownloads:false,serviceWorkers:'block',
      // A closed local proxy is a second barrier for fixture redirects: Firefox
      // rejects route.fulfill itself in Playwright's offline emulation mode.
      ...(transport?{proxy:{server:'http://127.0.0.1:9'}}:{})});
    await context.addInitScript(entries=>{
      for(const entry of entries)if(entry.origin===location.origin&&sessionStorage.length===0&&['https://www.domadoo.fr','https://domadoo.fr'].includes(location.origin))
        for(const [key,value] of entry.entries)sessionStorage.setItem(key,value);
    },restored.sessionStorage||[]);
    // Test transport is dependency injection only; no configurable portal URL or
    // production environment switch can weaken the request policy.
    if(transport)await context.route('**/*',transport);
    await context.route('**/*',route=>{
      const request=route.request(),navigation=request.isNavigationRequest()&&!request.frame().parentFrame();
      if(!allowedPortalRequest(request.url(),{human,authenticating,method:request.method(),mainNavigation:navigation})){
        const blocked={target:requestTarget(request.url()),method:['GET','HEAD','POST'].includes(request.method())?request.method():'OTHER',navigation};
        record(diagnostic.blocked,blocked);
        if(navigation)diagnostic.policy_navigation=blocked;
        return route.abort('blockedbyclient');
      }
      return route.fallback();
    });
    context.on('page',page=>{if(context.pages().length>1)page.close().catch(()=>{})});
    const page=await context.newPage();page.setDefaultTimeout(15000);page.setDefaultNavigationTimeout(30000);
    page.on('request',request=>{
      if(request.isNavigationRequest()&&!request.frame().parentFrame()){
        diagnostic.status=null;diagnostic.ray_id=null;diagnostic.challenge_response=false;diagnostic.navigation_error=null;
        diagnostic.policy_navigation=null;
        const previous=request.redirectedFrom();
        if(previous)record(diagnostic.navigation,{target:requestTarget(request.url()),redirected_from:requestTarget(previous.url())});
      }
    });
    page.on('response',response=>{
      const request=response.request();
      if(response.status()>=400)record(diagnostic.http_errors,{target:requestTarget(response.url()),status:response.status()});
      if(request.isNavigationRequest()&&!request.frame().parentFrame()){
        diagnostic.status=response.status();
        diagnostic.challenge_response=response.headers()['cf-mitigated']==='challenge';
        record(diagnostic.navigation,{target:requestTarget(response.url()),status:response.status()});
        // Only this expressly non-secret correlation header is read; never log
        // cookies, Set-Cookie, Location, request headers or submitted fields.
        const ray=response.headers()['cf-ray'];
        diagnostic.ray_id=typeof ray==='string'&&/^[a-f0-9]{16,32}(?:-[A-Z]{3})?$/i.test(ray)?ray:null;
      }
    });
    page.on('requestfailed',request=>{
      const reason=safeFailure(request.failure()?.errorText);
      record(diagnostic.failures,{target:requestTarget(request.url()),reason});
      if(request.isNavigationRequest()&&!request.frame().parentFrame())diagnostic.navigation_error=reason;
    });
    return {browser,context,page,engine,diagnostic,setAuthenticating:value=>{authenticating=value===true}};
  }catch(error){await browser.close();throw error}
}
export async function connectionDiagnostic(runtime){
  let stage;
  try{stage=await authenticationStage(runtime.page)}catch{stage=runtime.page.isClosed()?'browser_closed':'loading'}
  if(runtime.diagnostic.challenge_response&&stage!=='connected')stage='security_check';
  if(runtime.diagnostic.policy_navigation&&!['connected','security_check','verification','form_error'].includes(stage))stage='request_policy';
  if(stage==='unknown'&&runtime.diagnostic.status>=400)stage='http_error';
  if(stage==='unknown'&&runtime.diagnostic.navigation_error)stage='navigation_error';
  runtime.diagnostic.stage=stage;
  return {...runtime.diagnostic,observed_at:new Date().toISOString()};
}
export async function openPortal(runtime){
  runtime.diagnostic.navigation_error=null;
  try{await runtime.page.goto(PORTAL,{waitUntil:'domcontentloaded'})}
  catch(error){runtime.diagnostic.navigation_error=safeFailure(error)}
  // A navigation timeout must not destroy the still usable page. The person can
  // see the actual state and continue; no retry or challenge solving is done.
  return connectionDiagnostic(runtime);
}
export function diagnosticMessage(d){
  const labels={security_check:'contrôle de sécurité du portail',verification:'double vérification',login_form:'formulaire de connexion (session absente ou expirée)',form_error:'formulaire signalant une erreur',request_policy:'navigation bloquée par LinKs',http_error:'réponse HTTP refusée',navigation_error:'navigation interrompue',browser_closed:'navigateur fermé',unknown:'page non reconnue',loading:'page en chargement',connected:'espace affilié reconnu'};
  return `Étape : ${labels[d.stage]||d.stage} ; navigateur : ${d.browser} ${d.version} ; session : ${d.session} ; HTTP : ${d.status??'inconnu'}${d.ray_id?' ; Ray ID : '+d.ray_id:''}${d.navigation_error?' ; navigation : '+d.navigation_error:''}${d.policy_navigation?' ; navigation bloquée par LinKs : '+d.policy_navigation.target:''}.`;
}
