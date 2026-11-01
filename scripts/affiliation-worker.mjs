import http from 'node:http';
import {randomBytes,createCipheriv,createDecipheriv,timingSafeEqual} from 'node:crypto';
import {mkdir,readFile,writeFile,rename,unlink} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {PortalError,isConnected,collect} from './domadoo.mjs';
import {ensureAuthenticated,environmentCredentials} from './domadoo-auth.mjs';
import {browserContext,browserEngine,captureSession,connectionDiagnostic,diagnosticMessage,openPortal,restoredState,VIEWPORT} from './affiliation-browser.mjs';
const root=process.env.AFFILIATION_DATA_DIR||'/data/affiliation';
const token=process.env.AFFILIATION_WORKER_TOKEN;
const filename=(account,pending=false)=>path.join(root,account+(pending?'.pending-session':'.session'));
async function key(){
  await mkdir(root,{recursive:true,mode:0o700});
  const file=path.join(root,'session.key');
  try{return await readFile(file)}catch(error){if(error.code!=='ENOENT')throw error}
  try{await writeFile(file,randomBytes(32),{mode:0o600,flag:'wx'})}catch(error){if(error.code!=='EEXIST')throw error}
  return readFile(file);
}
export async function saveSession(account,state,pending=false){
  const iv=randomBytes(12),cipher=createCipheriv('aes-256-gcm',await key(),iv);
  const data=Buffer.concat([cipher.update(JSON.stringify(state)),cipher.final()]);
  const temp=filename(account,pending)+'.tmp';
  await writeFile(temp,Buffer.concat([iv,cipher.getAuthTag(),data]),{mode:0o600});await rename(temp,filename(account,pending));
}
export async function loadSession(account,pending=false){
  const data=await readFile(filename(account,pending)),decipher=createDecipheriv('aes-256-gcm',await key(),data.subarray(0,12));
  decipher.setAuthTag(data.subarray(12,28));
  return JSON.parse(Buffer.concat([decipher.update(data.subarray(28)),decipher.final()]).toString());
}
const forget=(account,pending=false)=>unlink(filename(account,pending)).catch(error=>{if(error.code!=='ENOENT')throw error});
export const deleteSession=forget;
// A controller owns one browser. The factory parameter lets offline regression
// tests exercise the real lifecycle without an external account or endpoint.
export function createActions(openBrowser=browserContext){
let login=null,busy=false;
async function closeLogin({remember=true}={}){
  const active=login;login=null;
  if(active)try{
    if(remember)await saveSession(active.account,{...await captureSession(active),saved_at:Date.now()},true);
  }finally{await active.browser.close()}
}
async function loginState(){
  if(!login)return {active:false};
  const diagnostic=await connectionDiagnostic(login);
  if(diagnostic.stage==='connected'){
    await saveSession(login.account,await captureSession(login));await forget(login.account,true);
    await closeLogin({remember:false});return {active:false,connected:true,diagnostic};
  }
  if(Date.now()>login.expires){await closeLogin();return {active:false,expired:true}}
  return {active:true,challenge:['security_check','verification'].includes(diagnostic.stage),diagnostic,
    image:(await login.page.screenshot({type:'jpeg',quality:65})).toString('base64'),...VIEWPORT,
    location:diagnostic.navigation.at(-1)?.target==='domadoo:authentification'?'https://www.domadoo.fr/fr/authentification':'https://www.domadoo.fr/fr/affiliation'};
}
async function action(name,data){
  if(!/^(domadoo|[a-f0-9]{32})$/.test(data.account||''))throw new PortalError('Compte invalide.');
  if(busy)throw new PortalError('Navigateur occupé par une synchronisation.');
  if(name.startsWith('amazon/mfa/')){
    const {amazonMfaAction}=await import('./amazon-auth.mjs');
    try{return await amazonMfaAction(name.slice('amazon/mfa/'.length),data)}
    catch(error){
      const safe=/^(La clé en attente|La clé MFA Amazon|AMAZON_MFA_SECRET doit|Aucune clé MFA|Confirmez d’abord|Retirez d’abord|Clé MFA chiffrée illisible|Action MFA Amazon inconnue)/.test(error.message);
      throw new PortalError(safe?error.message:'Configuration MFA Amazon indisponible.','amazon_mfa');
    }
  }
  if(name==='collect'){
    if(login)throw new PortalError('Terminer ou fermer la connexion humaine avant de synchroniser.');
    busy=true;let runtime;
    try{
      let state;try{state=await loadSession(data.account)}catch{/* Missing/corrupt state may be replaced by a successful automatic login. */}
      if(restoredState(state,browserEngine()).session!=='restored')state=undefined;
      if(!state&&!environmentCredentials(data.account))throw new PortalError('Reconnexion requise : session absente ou incompatible. Ouvrir la connexion humaine ou configurer DOMADOO_LOGIN et DOMADOO_PASSWORD côté serveur.','session_unreadable');
      runtime=await openBrowser(state);
      await ensureAuthenticated(runtime,()=>environmentCredentials(data.account));
      const result=await collect(runtime.page,{currentPage:true});
      await saveSession(data.account,await captureSession(runtime));await forget(data.account,true);return result;
    }catch(error){
      if(!runtime)throw error;
      const d=await connectionDiagnostic(runtime);
      if(['security_check','verification'].includes(d.stage)){
        // Keep only encrypted browser state for the existing human fallback.
        // Never replace a validated session or return a password/form capture.
        await saveSession(data.account,{...await captureSession(runtime),saved_at:Date.now()},true).catch(()=>{});
      }
      const reconnect=['login_form','form_error','verification'].includes(d.stage)?'Reconnexion requise. ':'';
      const message=error instanceof PortalError?error.message:'Lecture interrompue. Dernier relevé conservé.';
      throw new PortalError(reconnect+message+' '+diagnosticMessage(d),error.code||'collection_failed');
    }finally{await runtime?.browser.close();busy=false}
  }
  if(name==='disconnect'){
    if(login?.account===data.account)await closeLogin({remember:false});
    await forget(data.account);await forget(data.account,true);return {connected:false};
  }
  if(name==='login/start'){
    if(login)throw new PortalError('Une fenêtre de connexion est déjà ouverte.');
    let state,unreadable=false;
    for(const pending of [true,false])try{
      const candidate=await loadSession(data.account,pending);
      if(!pending||candidate.saved_at>Date.now()-24*60*60*1000){state=candidate;break}
    }catch(error){if(error.code!=='ENOENT')unreadable=true}
    const runtime=await openBrowser(state,true);
    if(!state&&unreadable)runtime.diagnostic.session='unreadable';
    login={...runtime,account:data.account,expires:Date.now()+15*60*1000};
    try{await openPortal(login);return await loginState()}
    catch(error){await closeLogin({remember:false});throw error}
  }
  if(!login)return {active:false};
  if(login.account!==data.account)throw new PortalError('Un autre compte utilise la fenêtre de connexion.');
  if(name==='login/close'){await closeLogin();return {active:false}}
  if(name==='login/verify'){
    // Do not reset an outstanding security check with another navigation.
    const d=await connectionDiagnostic(login);
    if(['security_check','verification','login_form','form_error','connected'].includes(d.stage))return loginState();
    await openPortal(login);return loginState();
  }
  if(name==='login/state')return loginState();
  if(name==='login/input'){
    // Stop accepting clicks immediately after login; never expose an interactive
    // authenticated affiliate account where payment/profile actions could be clicked.
    if(await isConnected(login.page))return loginState();
    if(Date.now()>login.expires){await closeLogin();return {active:false,expired:true}}
    const {kind}=data;
    if(kind==='click'&&Number.isFinite(data.x)&&Number.isFinite(data.y)&&data.x>=0&&data.x<1100&&data.y>=0&&data.y<760)await login.page.mouse.click(data.x,data.y);
    else if(kind==='text'&&typeof data.text==='string'&&data.text.length<=500)await login.page.keyboard.insertText(data.text);
    else if(kind==='key'&&['Tab','Shift+Tab','Enter','Backspace','Delete','ArrowDown','ArrowUp','ControlOrMeta+A','Escape'].includes(data.key))await login.page.keyboard.press(data.key);
    else if(kind==='scroll'&&Number.isFinite(data.delta))await login.page.mouse.wheel(0,Math.max(-600,Math.min(600,data.delta)));
    else throw new PortalError('Commande de saisie invalide.');
    return loginState();
  }
  throw new PortalError('Action inconnue.');
}
return {action,close:closeLogin,expire:async()=>{if(login&&Date.now()>login.expires)await closeLogin()}};
}
export function serve(){
  if(!token||token.length<32)throw new Error('Internal worker token required');
  let inputBusy=false;const controller=createActions();
  const server=http.createServer(async(req,res)=>{
    res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
    const supplied=Buffer.from(req.headers.authorization||''),expected=Buffer.from('Bearer '+token);
    if(req.method!=='POST'||supplied.length!==expected.length||!timingSafeEqual(supplied,expected)){res.writeHead(403);res.end('{}');return}
    if(inputBusy){res.writeHead(409);res.end(JSON.stringify({error:'Navigateur occupé.'}));return}
    inputBusy=true;
    let bytes=0,chunks=[];
    try{
      for await(const chunk of req){bytes+=chunk.length;if(bytes>8192)throw new PortalError('Commande trop longue.');chunks.push(chunk)}
      const data=JSON.parse(Buffer.concat(chunks).toString());
      const result=await controller.action(req.url.slice(1),data);res.end(JSON.stringify(result));
    }catch(error){res.writeHead(400);res.end(JSON.stringify({error:error instanceof PortalError?error.message:'Navigateur indisponible ou structure du portail modifiée. Dernier relevé conservé.',code:error instanceof PortalError?error.code:'browser_error'}))}
    finally{inputBusy=false;chunks=[]}
  });
  server.requestTimeout=35000;
  const cleanup=setInterval(()=>{if(!inputBusy){inputBusy=true;controller.expire().catch(()=>{}).finally(()=>{inputBusy=false})}},30000);cleanup.unref();
  process.on('SIGTERM',()=>{controller.close().finally(()=>process.exit(0))});
  server.listen(3004,'127.0.0.1');return server;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))serve();
