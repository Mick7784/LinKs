// Read-only portal diagnostics. Never submits credentials, OTPs or report jobs.
import {createRequire} from 'node:module';
import {browserEngine,VIEWPORT,safeFailure} from './affiliation-browser.mjs';
const require=createRequire(import.meta.url);
export const REPORTS_URL='https://partenaires.amazon.fr/home/reports';
const MESSAGES={login_required:'Amazon demande une connexion. Aucun identifiant transmis.',otp_required:'Amazon demande un code MFA. Aucun code transmis par ce diagnostic.',intervention_required:'Amazon demande une intervention. Diagnostic arrêté sans contournement.',access_denied:'Amazon refuse cet accès HTTP. Cela ne démontre pas une interdiction contractuelle.',rate_limited:'Amazon limite les requêtes. Aucun nouvel essai automatique.',unverified:'Page reçue, mais accès au magasin France et parcours de téléchargement non validés.',navigation_blocked:'Redirection hors du parcours public vérifié : navigation arrêtée.',network_error:'Navigation impossible. Aucun accès authentifié confirmé.'};
export async function inspectAmazonPage(page,status){
 const flags=await page.evaluate(()=>({
  challenge:Boolean(document.querySelector('input[name="cvf_captcha_input"],#captchacharacters,iframe[src*="captcha"],form[action*="validateCaptcha"]')),
  otp:Boolean(document.querySelector('input[autocomplete="one-time-code"],#auth-mfa-otpcode')),
  login:Boolean(document.querySelector('input[type="password"],#ap_email,input[name="email"]'))
 }));
 const code=flags.challenge?'intervention_required':status===429?'rate_limited':[401,403].includes(status)?'access_denied':flags.otp?'otp_required':flags.login?'login_required':'unverified';
 return {code,message:MESSAGES[code],http_status:status||null,connected:false,collection_enabled:false};
}
export async function probeAmazonPortal({engine=browserEngine()}={}){
 if(!['chromium','firefox'].includes(engine))throw new Error('Navigateur non pris en charge.');
 const env=Object.fromEntries(Object.entries(process.env).filter(([key])=>!/SECRET|PASSWORD|TOKEN|LOGIN|API_KEY|CREDENTIAL/i.test(key)));
 let browser;
 try{
  browser=await require('playwright-core')[engine].launch({headless:true,env,...(engine==='chromium'?{executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium'}:{})});
  const context=await browser.newContext({viewport:VIEWPORT,acceptDownloads:false,serviceWorkers:'block'});
  let blocked=false;
  await context.route('**/*',route=>{
   const req=route.request();let u;try{u=new URL(req.url())}catch{return route.abort()}
   if(!['GET','HEAD'].includes(req.method()))return route.abort();
   if(req.isNavigationRequest()){
    const allowed=u.protocol==='https:'&&!u.username&&!u.password&&((u.hostname==='partenaires.amazon.fr'&&u.pathname==='/home/reports')||(u.hostname==='www.amazon.fr'&&['/ap/signin','/ap/mfa'].includes(u.pathname)));
    if(!allowed){blocked=true;return route.abort()}
   }
   return route.continue();
  });
  const page=await context.newPage();
  let response;
  try{response=await page.goto(REPORTS_URL,{waitUntil:'domcontentloaded',timeout:30000})}
  catch(error){return {code:blocked?'navigation_blocked':'network_error',message:MESSAGES[blocked?'navigation_blocked':'network_error'],reason:safeFailure(error),connected:false,collection_enabled:false}}
  if(blocked)return {code:'navigation_blocked',message:MESSAGES.navigation_blocked,connected:false,collection_enabled:false};
  return await inspectAmazonPage(page,response?.status());
 }catch{return {code:'network_error',message:'Diagnostic navigateur indisponible.',connected:false,collection_enabled:false}}
 finally{await browser?.close()}
}
