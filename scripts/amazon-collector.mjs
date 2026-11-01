// Ordinary browser workflow; all secrets remain inside the affiliation worker.
import {createRequire} from 'node:module';
import {setTimeout as pause} from 'node:timers/promises';
import {browserEngine,VIEWPORT} from './affiliation-browser.mjs';
import {ensureAmazonSession,loadAmazonSession,saveAmazonSession,amazonCredentials} from './amazon-auth.mjs';
import {REPORTS_URL,inspectAmazonPage} from './amazon-portal.mjs';
const require=createRequire(import.meta.url);
export class AmazonCollectionError extends Error{constructor(message,code='amazon_collection'){super(message);this.code=code}}
const stop=(message,code)=>{throw new AmazonCollectionError(message,code)};
function checkAccess(d){if(d.code==='rate_limited')stop('Amazon limite les requêtes (HTTP 429). Aucun nouvel essai automatique.','amazon_http429');if(d.code==='access_denied')stop('Amazon refuse cet accès (HTTP '+d.http_status+').','amazon_access_denied');if(d.code==='intervention_required')intervention()}
const intervention=()=>stop('Intervention Amazon requise. Terminez le contrôle sur Amazon ; aucune protection ne sera contournée.','amazon_intervention');
export function allowedAmazonNavigation(address){
 try{const u=new URL(address);return u.protocol==='https:'&&!u.username&&!u.password&&!u.port&&((u.hostname==='partenaires.amazon.fr'&&(u.pathname==='/home'||u.pathname.startsWith('/home/')))||(u.hostname==='www.amazon.fr'&&['/ap/signin','/ap/mfa'].includes(u.pathname)))}catch{return false}
}
async function unique(locator,state='visible',label='Contrôle attendu'){try{await locator.first().waitFor({state,timeout:15000})}catch{stop(label+' introuvable dans le délai. Présentation Amazon à vérifier.','amazon_control_missing')}if(await locator.count()!==1)stop(label+' ambigu : plusieurs contrôles trouvés. Aucun import.','amazon_page_changed');return locator}
async function reportsReady(page){
 if(new URL(page.url()).origin!=='https://partenaires.amazon.fr'||!new URL(page.url()).pathname.startsWith('/home/reports'))return false;
 return await page.getByRole('button',{name:/^Télécharger (des )?rapports$/i}).count()===1;
}
export async function normalSignIn(page,credentials,{status=()=>200,blocked=()=>false,progress=()=>{}}={}){
 const used=new Set();
 const deadline=Date.now()+60000;
 while(Date.now()<deadline){
  if(blocked()||!allowedAmazonNavigation(page.url()))intervention();
  const d=await inspectAmazonPage(page,status());
  checkAccess(d);
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
  progress(({ap_email:'login',ap_password:'password','auth-mfa-otpcode':'mfa'})[stage.id]);
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
const REPORT_TYPES=[['category','Category',/^(Catégories|Category)$/i],['linked_product','Linked-Product',/^(Produits liés|Linked-Product)$/i],['tracking_id','Tracking-Id',/^(Tracking IDs?|Numéros? de suivi|Tracking-Id)$/i]];
function displayDay(day){return day.split('-').reverse().join('/')}
export async function selectReportPeriod(root,day){
 const combo=root.getByRole('combobox',{name:/période/i});
 // Support the accessible period menu, not a report-type select.
 if(await combo.count()===1&&await combo.evaluate(el=>el.tagName==='SELECT')){
  const period=await unique(combo,'visible','Menu de période'),custom=period.getByRole('option',{name:/personnalis/i});await unique(custom,'attached','Option de période personnalisée');
  await period.selectOption(await custom.getAttribute('value'));
 }else{
  const menu=combo.or(root.getByRole('button',{name:/période/i}));await (await unique(menu)).click();
  await (await unique(root.getByRole('option',{name:/personnalis/i}).or(root.getByRole('menuitem',{name:/personnalis/i})))).click();
 }
 const from=await unique(root.getByLabel(/^(Du|De|Date de début|Début)$/i),'visible','Date de début'),to=await unique(root.getByLabel(/^(Au|À|Date de fin|Fin)$/i),'visible','Date de fin');
 for(const field of [from,to]){
  const type=await field.getAttribute('type'),placeholder=await field.getAttribute('placeholder')||'';
  if(type==='date')await field.fill(day);
  else if(/jj.*mm.*(aaaa|aa)|dd.*mm.*yyyy/i.test(placeholder))await field.fill(displayDay(day));
  else stop('Format du calendrier non reconnu : aucune demande générée.','amazon_period_control');
 }
 const verify=async()=>{
  for(const field of [from,to])if(![day,displayDay(day)].includes(await field.inputValue()))stop('La période affichée diffère de la journée demandée.','amazon_period_mismatch');
 };
 await verify();return verify;
}
export function parisGenerationMinute(now=new Date()){
 const parts=Object.fromEntries(new Intl.DateTimeFormat('fr-FR',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(now).map(p=>[p.type,p.value]));
 return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}
function generationMinute(value){const m=value.match(/^(\d{2}):(\d{2})(?::\d{2})?\s+(\d{2})\/(\d{2})\/(\d{4})$/);return m?`${m[5]}-${m[4]}-${m[3]}T${m[1]}:${m[2]}`:''}
async function reportRows(page){
 // Only visible table rows, never hidden application state or guessed endpoints.
 return page.getByRole('row').evaluateAll(rows=>rows.filter(r=>r.getClientRects().length).map(r=>{
  const cells=[...r.querySelectorAll('td,[role="cell"]')].map(c=>c.textContent.trim());
  const type=cells.find(c=>['Category','Linked-Product','Tracking-Id'].includes(c));
  const generated=cells.find(c=>/^\d{2}:\d{2}(?::\d{2})?\s+\d{2}\/\d{2}\/\d{4}$/.test(c));
  return {type,generated,csv:cells.includes('CSV'),empty:cells.some(c=>/Aucune donnée trouvée/i.test(c)),ready:[...r.querySelectorAll('a,button')].some(a=>/^Télécharger$/i.test(a.textContent.trim()))};
 }).filter(r=>r.type&&r.generated));
}
export async function requestReports(page,day,{progress=()=>{},guard=async()=>{},waitMs=120000,pollMs=1000}={}){
 progress('reports');await guard();
 await (await unique(page.getByRole('button',{name:/^Télécharger (des )?rapports$/i}))).click();
 const root=page; // Amazon's export panel and generated-report list need not be a modal.
 progress('period');const verifyPeriod=await selectReportPeriod(root,day);
 progress('selection');
 // Only the three understood views; do not include unrelated financial reports.
 const other=root.getByRole('checkbox',{name:/^(Top-Sellers|Meilleures ventes|Bounty-Tracking-Id|Bounty-Event|Bounty-Event-Tracking)$/i});
 for(let i=0;i<await other.count();i++)if(await other.nth(i).isVisible()&&await other.nth(i).isChecked())await other.nth(i).uncheck();
 for(const [, ,label] of REPORT_TYPES)await (await unique(root.getByRole('checkbox',{name:label}))).check();
 const csv=root.getByRole('radio',{name:/^CSV$/i});
 if(await csv.count()===1)await csv.check();
 else await (await unique(root.getByRole('combobox',{name:/^Format$/i}))).selectOption({label:'CSV'});
 await verifyPeriod();await guard();
 const requestedMinute=parisGenerationMinute();
 const before=new Set((await reportRows(page)).map(r=>r.type+'|'+r.generated));
 progress('generation');await (await unique(root.getByRole('button',{name:/^Générer des rapports$/i}),'visible','Bouton Générer des rapports')).click();
 progress('waiting');const deadline=Date.now()+waitMs;let chosen;
 while(Date.now()<deadline){
  await guard();
  const rows=(await reportRows(page)).filter(r=>r.csv&&!before.has(r.type+'|'+r.generated)&&generationMinute(r.generated)>=requestedMinute&&generationMinute(r.generated)<=parisGenerationMinute());
  // Bind all three views to one NEW generation, not to the first available link.
  const generations=[...new Set(rows.map(r=>r.generated))];
  if(generations.length>1)stop('Plusieurs nouvelles générations concurrentes : provenance ambiguë, aucun téléchargement.','amazon_generation_ambiguous');
  if(rows.some(r=>r.empty))stop('Amazon indique aucune donnée pour un export demandé. Historique conservé.','amazon_report_empty');
  if(rows.length===3&&REPORT_TYPES.every(([,type])=>rows.filter(r=>r.type===type).length===1)&&rows.every(r=>r.ready)){chosen=rows;break}
  if(rows.length>3)stop('Exports dupliqués : génération ambiguë.','amazon_generation_ambiguous');
  await pause(pollMs);
 }
 if(!chosen)stop('Aucune nouvelle génération complète disponible dans le délai. Les anciens exports ont été ignorés.','amazon_generation_timeout');
 progress('download');const files=[];let fileGeneration;
 for(const [view,type] of REPORT_TYPES){
  await guard();
  const generation=chosen.find(r=>r.type===type).generated;
  const row=await unique(page.getByRole('row').filter({has:page.getByRole('cell',{name:type,exact:true})}).filter({has:page.getByRole('cell',{name:generation,exact:true})}));
  const control=row.getByRole('link',{name:/^Télécharger$/i}).or(row.getByRole('button',{name:/^Télécharger$/i}));
  const pending=page.waitForEvent('download',{timeout:30000});pending.catch(()=>{});
  await (await unique(control)).click();const download=await pending;
  // A generated file must identify its view; do not relabel an unrelated download.
  if(!download.suggestedFilename().startsWith(type+'-')){await download.cancel();await download.delete().catch(()=>{});stop('Nom de fichier différent du rapport demandé.','amazon_report_identity')}
  const suffix=download.suggestedFilename().slice(type.length+1).replace(/\.(zip|csv|txt)$/i,'');
  if(fileGeneration&&fileGeneration!==suffix){await download.cancel();await download.delete().catch(()=>{});stop('Les fichiers ne proviennent pas de la même génération.','amazon_generation_ambiguous')}
  fileGeneration=suffix;
  const bytes=await downloadBytes(download),zip=bytes.subarray(0,2).toString()==='PK';
  files.push({view,archive:zip?bytes.toString('base64'):null,csv:zip?null:new TextDecoder('utf-8',{fatal:true}).decode(bytes)});
 }
 return files;
}
export const AMAZON_STAGES={configuration:'Configuration',browser:'Démarrage du navigateur',portal:'Ouverture du portail',session:'Vérification de session',login:'Identifiant Amazon',password:'Mot de passe Amazon',mfa:'Vérification MFA',reports:'Ouverture des exports',period:'Choix de la période',selection:'Choix des rapports et du format CSV',generation:'Demande de génération',waiting:'Attente des nouveaux exports',download:'Téléchargement des exports',saving:'Enregistrement de session',validation:'Validation et import transactionnel'};
export async function collectAmazon({account,day},{progress=()=>{}}={}){
 if(!/^[a-f0-9]{32}$/.test(account||'')||!/^\d{4}-\d{2}-\d{2}$/.test(day||''))stop('Compte ou date Amazon invalide.');
 let browser,deadline,stage='configuration',expired=false,blocked=false,httpStatus=200;
 const advance=next=>{if(!Object.hasOwn(AMAZON_STAGES,next))throw new Error('Invalid stage');stage=next;progress({stage,message:AMAZON_STAGES[stage]})};
 advance('configuration');
 try{
  const saved=await loadAmazonSession(),engine=browserEngine();
  if(!saved&&!amazonCredentials())stop('Connexion Amazon requise. Configurez AMAZON_LOGIN et AMAZON_PASSWORD côté serveur.','amazon_configuration');
  if(saved&&(saved.account!==account||saved.browser!==engine))stop('Session Amazon associée à un autre compte ou navigateur. Déconnectez-la avant de continuer.','amazon_session_binding');
  advance('browser');
  browser=await require('playwright-core')[engine].launch({headless:true,env:Object.fromEntries(Object.entries(process.env).filter(([k])=>!/SECRET|PASSWORD|TOKEN|LOGIN|API_KEY|CREDENTIAL/i.test(k))),...(engine==='chromium'?{executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium'}:{})});
  deadline=setTimeout(()=>{expired=true;browser.close().catch(()=>{})},480000);deadline.unref();
  const context=await browser.newContext({viewport:VIEWPORT,storageState:saved?.storageState,acceptDownloads:true,serviceWorkers:'block'});

  await context.route('**/*',route=>{
   const r=route.request();if(r.isNavigationRequest()&&!allowedAmazonNavigation(r.url())){blocked=true;return route.abort()}
   return route.continue();
  });
  const page=await context.newPage();page.setDefaultTimeout(15000);
  page.on('response',r=>{if(r.request().isNavigationRequest()&&!r.request().frame().parentFrame())httpStatus=r.status()});
  advance('portal');
  await page.goto(REPORTS_URL,{waitUntil:'domcontentloaded',timeout:30000});
  const capture=async()=>({account,browser:engine,storageState:await context.storageState({indexedDB:true})});
  advance('session');
  await ensureAmazonSession({verify:async()=>{
   if(blocked)return 'additional_check';const d=await inspectAmazonPage(page,httpStatus);
   checkAccess(d);
   return await reportsReady(page)?'authenticated':['login_required','otp_required'].includes(d.code)?'expired':'additional_check';
  },signIn:credentials=>normalSignIn(page,credentials,{status:()=>httpStatus,blocked:()=>blocked,progress:advance}),capture});
  if(!await reportsReady(page))stop('Accès aux rapports Amazon non confirmé.');
  const files=await requestReports(page,day,{progress:advance,guard:async()=>{if(blocked)intervention();const d=await inspectAmazonPage(page,httpStatus);checkAccess(d);}});
  if(blocked||!allowedAmazonNavigation(page.url()))intervention();
  advance('saving');
  await saveAmazonSession(await capture());
  advance('validation');
  return {day,files,complete:true};
 }catch(error){
  let known=error;for(let i=0;i<4&&known?.cause;i++){if(known instanceof AmazonCollectionError)break;known=known.cause}
  const code=known instanceof AmazonCollectionError?known.code:expired?'amazon_deadline':blocked?'amazon_navigation_blocked':error.name==='TimeoutError'?'amazon_timeout':'amazon_step_failed';
  const reason=known instanceof AmazonCollectionError?known.message:expired?'Durée maximale de huit minutes dépassée.':blocked?'Navigation hors du parcours autorisé. Intervention requise.':error.name==='TimeoutError'?'Délai dépassé en attendant le contrôle ou le téléchargement Amazon.':/^(Conflit MFA :|Connexion Amazon requise\.|Configurer AMAZON_LOGIN|Session Amazon illisible\.|Vérification Amazon requise\.)/.test(error.message)?error.message:'Opération interrompue à cette étape ; vérifier la disponibilité du navigateur et la présentation du portail.';
  throw new AmazonCollectionError(AMAZON_STAGES[stage]+' ['+code+'] : '+reason,code);
 }
 finally{clearTimeout(deadline);await browser?.close()}
}
