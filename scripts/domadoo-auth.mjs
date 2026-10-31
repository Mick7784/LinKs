import {setTimeout as pause} from 'node:timers/promises';
import {PortalError} from './domadoo.mjs';
import {openPortal,connectionDiagnostic} from './affiliation-browser.mjs';

// These global credentials belong only to the built-in Domadoo account. Never
// attach the same remote financial account to another configured reporting ID.
export function environmentCredentials(account,env=process.env){
  if(account!=='domadoo')return null;
  const login=env.DOMADOO_LOGIN?.trim(),password=env.DOMADOO_PASSWORD;
  if(!login&&!password)return null;
  if(!login||!password)throw new PortalError('Configurer ensemble DOMADOO_LOGIN et DOMADOO_PASSWORD côté serveur, ou utiliser la connexion humaine.','credentials_configuration');
  return {login,password};
}

function failure(d){
  const stage=d.status>=400&&!['security_check','verification','form_error','request_policy'].includes(d.stage)?'http_error':d.stage;
  const errors={
    security_check:['Contrôle de sécurité Domadoo/Cloudflare : connexion automatique suspendue. Ouvrir la connexion humaine pour toute vérification demandée.','security_check'],
    verification:['Reconnexion requise : vérification supplémentaire demandée. Ouvrir la connexion humaine.','authentication_verification'],
    form_error:['Le formulaire Domadoo signale une erreur. Vérifier la configuration ou ouvrir la connexion humaine. Aucun nouvel envoi automatique pendant cette tentative.','authentication_rejected'],
    request_policy:['Navigation bloquée par LinKs pendant la connexion. Consulter le diagnostic ; aucun élargissement automatique des autorisations.','request_policy'],
    http_error:['Connexion Domadoo refusée par une réponse HTTP. Dernier relevé conservé.','authentication_http_error'],
    navigation_error:['Navigation Domadoo interrompue pendant la connexion. Dernier relevé conservé.','authentication_navigation_error'],
    browser_closed:['Navigateur fermé pendant la connexion. Dernier relevé conservé.','authentication_navigation_error']
  };
  if(errors[stage])throw new PortalError(...errors[stage]);
}

// Ordinary browser form submission only: no internal endpoint, handcrafted POST,
// challenge solver, stealth injection or automatic retry of a rejected login.
export async function ensureAuthenticated(runtime,credentials,{timeoutMs=60000}={}){
  let d=await openPortal(runtime);
  if(d.stage==='connected')return {authenticated:false};
  failure(d);
  if(d.stage!=='login_form')throw new PortalError('Page de connexion Domadoo non reconnue. Ouvrir la connexion humaine.','authentication_page_changed');
  const secret=credentials();
  if(!secret)throw new PortalError('Reconnexion requise : ouvrir la connexion humaine ou configurer DOMADOO_LOGIN et DOMADOO_PASSWORD côté serveur.','authentication_required');
  const formOK=await runtime.page.evaluate(()=>{
    const password=document.querySelector('#field-password'),email=document.querySelector('#field-email'),button=document.querySelector('#submit-login');
    const form=password?.form;
    if(!form||email?.form!==form||button?.form!==form||password.type!=='password')return false;
    const action=new URL(button.getAttribute('formaction')||form.action,location.href);
    const allowedBack=value=>{
      if(!value)return true;
      try{const u=new URL(value,location.href);return u.origin===location.origin&&u.pathname==='/fr/affiliation'}catch{return false}
    };
    return location.protocol==='https:'&&['www.domadoo.fr','domadoo.fr'].includes(location.hostname)&&
      ['/fr/authentification','/fr/affiliation'].includes(location.pathname)&&
      (button.getAttribute('formmethod')||form.method).toLowerCase()==='post'&&
      !action.username&&!action.password&&action.origin===location.origin&&action.pathname==='/fr/authentification'&&
      ['','_self'].includes(button.getAttribute('formtarget')||form.target)&&
      allowedBack(action.searchParams.get('back'))&&allowedBack(form.querySelector('[name=back]')?.value);
  });
  if(!formOK)throw new PortalError('Formulaire Domadoo modifié ou destination non autorisée : aucun identifiant transmis.','authentication_form_changed');
  runtime.setAuthenticating(true);
  try{
    // Never return a raw Playwright exception: fill errors may contain the value.
    try{
      await runtime.page.locator('#field-email').fill(secret.login);
      await runtime.page.locator('#field-password').fill(secret.password);
    }catch{throw new PortalError('Saisie automatique impossible. Ouvrir la connexion humaine.','authentication_input_error')}
    const deadline=Date.now()+timeoutMs;
    try{await runtime.page.locator('#submit-login').click({timeout:Math.min(15000,timeoutMs)})}catch{/* Inspect the actual landing page, not the raw navigation exception. */}
    do{
      d=await connectionDiagnostic(runtime);
      if(d.stage==='connected'&&await runtime.page.locator('#my_affiliate_link').isVisible())return {authenticated:true};
      failure(d);
      if(Date.now()>=deadline)break;
      await pause(200);
    }while(true);
    throw new PortalError('Connexion Domadoo non confirmée dans le délai prévu. Ouvrir la connexion humaine ; aucun nouvel envoi automatique pendant cette tentative.','authentication_timeout');
  }finally{
    runtime.setAuthenticating(false);
    // Clear a rejected form before any optional human handoff; no screenshot or
    // form value is ever returned from the automatic flow.
    await runtime.page.locator('#field-password').evaluateAll(nodes=>nodes.forEach(n=>{n.value=''})).catch(()=>{});
  }
}
