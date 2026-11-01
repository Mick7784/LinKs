// Ordinary browser workflow; all secrets remain inside the affiliation worker.
import {createRequire} from 'node:module';
import {setTimeout as pause} from 'node:timers/promises';
import {browserEngine,VIEWPORT} from './affiliation-browser.mjs';
import {ensureAmazonSession,loadAmazonSession,saveAmazonSession,amazonCredentials} from './amazon-auth.mjs';
import {REPORTS_URL,inspectAmazonPage} from './amazon-portal.mjs';
const require=createRequire(import.meta.url);
export class AmazonCollectionError extends Error{constructor(message,code='amazon_collection'){super(message);this.code=code}}
const stop=(message,code)=>{throw new AmazonCollectionError(message,code)};
const intervention=()=>stop('Intervention Amazon requise. Terminez le contrôle sur Amazon ; aucune protection ne sera contournée.','amazon_intervention');
export function allowedAmazonNavigation(address){
 try{const u=new URL(address);return u.protocol==='https:'&&!u.username&&!u.password&&!u.port&&((u.hostname==='partenaires.amazon.fr'&&(u.pathname==='/home'||u.pathname.startsWith('/home/')))||(u.hostname==='www.amazon.fr'&&['/ap/signin','/ap/mfa'].includes(u.pathname)))}catch{return false}
}
async function unique(locator){if(await locator.count()!==1)stop('Présentation Amazon non reconnue : contrôle unique attendu. Aucune donnée importée.','amazon_page_changed');return locator}
async function reportsReady(page){
 if(new URL(page.url()).origin!=='https://partenaires.amazon.fr'||!new URL(page.url()).pathname.startsWith('/home/reports'))return false;
 return await page.getByRole('button',{name:/^Télécharger (des )?rapports$/i}).count()===1;
}
export async function normalSignIn(page,credentials,{status=()=>200,blocked=()=>false}={}){
 const used=new Set();
 const deadline=Date.now()+60000;
 while(Date.now()<deadline){
  if(blocked()||!allowedAmazonNavigation(page.url()))intervention();
  const d=await inspectAmazonPage(page,status());
  if(['intervention_required','access_denied','rate_limited'].includes(d.code))intervention();
  if(await reportsReady(page))return {status:'authenticated'};
  const stage=await page.evaluate(()=>{
   if(location.origin!=='https://www.amazon.fr'||!['/ap/signin','/ap/mfa'].includes(location.pathname))return null;
   const field=document.querySelector('#auth-mfa-otpcode')||document.querySelector('#ap_password')||document.querySelector('#ap_email');
   if(!field)return null;const form=field.form;
   if(!form)return null;const action=new URL(form.action,location.href);
   if(action.origin!==location.origin||!['/ap/signin','/ap/mfa'].includes(action.pathname)||form.method.toLowerCase()!=='post'||!['','_self'].includes(form.target))return null;
   const submits=[...form.querySelectorAll('input[type="submit"],button[type="submit"]')];
   if(submits.length!==1)return null;
   const submit=submits[0],target=new URL(submit.getAttribute('formaction')||form.action,location.href);
   if(target.origin!==location.origin||!['/ap/signin','/ap/mfa'].includes(target.pathname)||(submit.getAttribute('formmethod')||form.method).toLowerCase()!=='post'||!['','_self'].includes(submit.getAttribute('formtarget')||form.target))return null;
   return {id:field.id};
  });
  if(!stage){await pause(300);continue}
  if(used.has(stage.id)){await pause(300);continue}
  used.add(stage.id);
  const value=stage.id==='ap_email'?credentials.login:stage.id==='ap_password'?credentials.password:credentials.totp();
  if(!value)intervention();
  try{
   const field=await unique(page.locator('#'+stage.id));await field.fill(value);
   const form=field.locator('xpath=ancestor::form');
   await (await unique(form.locator('input[type="submit"],button[type="submit"]'))).click();
  }catch(error){if(error instanceof AmazonCollectionError)throw error;stop('Connexion Amazon interrompue. Vérifiez le compte ou terminez la connexion sur Amazon.','amazon_login_failed')}
  await pause(500);
 }
 stop('Connexion Amazon non confirmée. Vérifiez les identifiants ou les contrôles demandés sur Amazon.','amazon_login_failed');
}
async function downloadBytes(download){
 const stream=await download.createReadStream();if(!stream)stop('Téléchargement Amazon indisponible.');
 const chunks=[];let size=0;
 try{for await(const chunk of stream){size+=chunk.length;if(size>1024*1024){await download.cancel();stop('Rapport Amazon supérieur à 1 Mo. Import manuel nécessaire.')}chunks.push(chunk)}
 if(await download.failure())stop('Téléchargement Amazon incomplet.');return Buffer.concat(chunks)}finally{stream.destroy();await download.delete().catch(()=>{})}
}
export async function requestReports(page,day){
 const files=[];
 for(const [view,label] of [['category','Catégories'],['linked_product','Produits liés'],['tracking_id','Tracking ID']]){
  await (await unique(page.getByRole('button',{name:/^Télécharger (des )?rapports$/i}))).click();
  const dialog=await unique(page.getByRole('dialog'));
  // These accessible controls must be confirmed on the real account. Never use
  // hidden endpoints, guess a report job ID or download a previous unrelated job.
  const from=await unique(dialog.getByLabel(/^(Du|Date de début)$/i));
  const to=await unique(dialog.getByLabel(/^(Au|Date de fin)$/i));
  if(await from.getAttribute('type')!=='date'||await to.getAttribute('type')!=='date')stop('Sélecteur de période Amazon à adapter au compte réel.','amazon_page_changed');
  await from.fill(day);await to.fill(day);
  const select=await unique(dialog.getByLabel(/^Type de rapport$/i));await select.selectOption({label});
  const tracking=await unique(dialog.getByLabel(/^Tracking ID$/i));
  const all=tracking.getByRole('option',{name:/^(Tous|Tous les Tracking IDs|Tous les numéros de suivi|All)$/i});
  await unique(all);await tracking.selectOption(await all.getAttribute('value'));
  if(!await all.evaluate(option=>option.selected))stop('Périmètre de Tracking IDs non confirmé.');
  if(await from.inputValue()!==day||await to.inputValue()!==day)stop('La période Amazon sélectionnée ne correspond pas à la demande.');
  const pending=page.waitForEvent('download',{timeout:120000});
  // Handle the rejection immediately even when the click itself fails.
  pending.catch(()=>{});
  await (await unique(dialog.getByRole('button',{name:/^(Générer|Télécharger)$/i}))).click();
  const download=await pending;
  const bytes=await downloadBytes(download);
  files.push({view,archive:bytes.subarray(0,2).toString()==='PK'?bytes.toString('base64'):null,csv:bytes.subarray(0,2).toString()==='PK'?null:new TextDecoder('utf-8',{fatal:true}).decode(bytes)});
  if(await dialog.isVisible())await (await unique(dialog.getByRole('button',{name:/^Fermer$/i}))).click();
 }
 return files;
}
export async function collectAmazon({account,day}){
 if(!/^[a-f0-9]{32}$/.test(account||'')||!/^\d{4}-\d{2}-\d{2}$/.test(day||''))stop('Compte ou date Amazon invalide.');
 let browser,deadline;
 try{
  const saved=await loadAmazonSession(),engine=browserEngine();
  if(!saved&&!amazonCredentials())stop('Connexion Amazon requise. Configurez AMAZON_LOGIN et AMAZON_PASSWORD côté serveur.','amazon_configuration');
  if(saved&&(saved.account!==account||saved.browser!==engine))stop('Session Amazon associée à un autre compte ou navigateur. Déconnectez-la avant de continuer.','amazon_session_binding');
  browser=await require('playwright-core')[engine].launch({headless:true,env:Object.fromEntries(Object.entries(process.env).filter(([k])=>!/SECRET|PASSWORD|TOKEN|LOGIN|API_KEY|CREDENTIAL/i.test(k))),...(engine==='chromium'?{executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium'}:{})});
  deadline=setTimeout(()=>{browser.close().catch(()=>{})},480000);deadline.unref();
  const context=await browser.newContext({viewport:VIEWPORT,storageState:saved?.storageState,acceptDownloads:true,serviceWorkers:'block'});
  let blocked=false,httpStatus=200;
  await context.route('**/*',route=>{
   const r=route.request();if(r.isNavigationRequest()&&!allowedAmazonNavigation(r.url())){blocked=true;return route.abort()}
   return route.continue();
  });
  const page=await context.newPage();page.setDefaultTimeout(15000);
  page.on('response',r=>{if(r.request().isNavigationRequest()&&!r.request().frame().parentFrame())httpStatus=r.status()});
  await page.goto(REPORTS_URL,{waitUntil:'domcontentloaded',timeout:30000});
  const capture=async()=>({account,browser:engine,storageState:await context.storageState({indexedDB:true})});
  await ensureAmazonSession({verify:async()=>{
   if(blocked)return 'additional_check';const d=await inspectAmazonPage(page,httpStatus);
   if(['intervention_required','access_denied','rate_limited'].includes(d.code))return 'additional_check';
   return await reportsReady(page)?'authenticated':d.code==='login_required'?'expired':'additional_check';
  },signIn:credentials=>normalSignIn(page,credentials,{status:()=>httpStatus,blocked:()=>blocked}),capture});
  if(!await reportsReady(page))stop('Accès aux rapports Amazon non confirmé.');
  const files=await requestReports(page,day);
  if(blocked||!allowedAmazonNavigation(page.url()))intervention();
  await saveAmazonSession(await capture());
  return {day,files,complete:true};
 }catch(error){if(error instanceof AmazonCollectionError)throw error;if(/^(Conflit MFA :|Connexion Amazon requise\.|Configurer AMAZON_LOGIN|Session Amazon illisible\.)/.test(error.message))stop(error.message,'amazon_configuration');stop('Parcours Amazon interrompu : connexion, contrôle supplémentaire ou présentation des rapports à vérifier. Aucun import effectué.','amazon_intervention')}
 finally{clearTimeout(deadline);await browser?.close()}
}
