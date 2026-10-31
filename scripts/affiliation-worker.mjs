import http from 'node:http';
import {randomBytes,createCipheriv,createDecipheriv,timingSafeEqual} from 'node:crypto';
import {mkdir,readFile,writeFile,rename,unlink} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {PORTAL,PortalError,isConnected,collect,allowedPortalRequest,securityChallenge} from './domadoo.mjs';
const require=createRequire(import.meta.url);
const root=process.env.AFFILIATION_DATA_DIR||'/data/affiliation';
let login=null,busy=false;
const token=process.env.AFFILIATION_WORKER_TOKEN;
const filename=account=>path.join(root,account+'.session');
async function key(){
  await mkdir(root,{recursive:true,mode:0o700});
  const file=path.join(root,'session.key');
  try{return await readFile(file)}catch(error){if(error.code!=='ENOENT')throw error}
  try{await writeFile(file,randomBytes(32),{mode:0o600,flag:'wx'})}catch(error){if(error.code!=='EEXIST')throw error}
  return readFile(file);
}
export async function saveSession(account,state){
  const iv=randomBytes(12),cipher=createCipheriv('aes-256-gcm',await key(),iv);
  const data=Buffer.concat([cipher.update(JSON.stringify(state)),cipher.final()]);
  const temp=filename(account)+'.tmp';
  await writeFile(temp,Buffer.concat([iv,cipher.getAuthTag(),data]),{mode:0o600});await rename(temp,filename(account));
}
export async function loadSession(account){
  const data=await readFile(filename(account)),decipher=createDecipheriv('aes-256-gcm',await key(),data.subarray(0,12));
  decipher.setAuthTag(data.subarray(12,28));
  return JSON.parse(Buffer.concat([decipher.update(data.subarray(28)),decipher.final()]).toString());
}
async function browserContext(state,human=false){
  const {chromium}=require('playwright-core');
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--disable-dev-shm-usage']});
  try{
    const context=await browser.newContext({viewport:{width:1100,height:760},storageState:state,acceptDownloads:false,serviceWorkers:'block'});
    // Fixed portal only. Block intranet/localhost, arbitrary browsing and all
    // state-changing portal requests during unattended collection.
    await context.route('**/*',route=>{
      const request=route.request();
      if(!allowedPortalRequest(request.url(),{human,method:request.method(),mainNavigation:request.isNavigationRequest()&&request.frame().parentFrame()===null}))return route.abort();
      return route.continue();
    });
    context.on('page',page=>{if(context.pages().length>1)page.close().catch(()=>{})});
    const page=await context.newPage();page.setDefaultTimeout(15000);page.setDefaultNavigationTimeout(30000);
    return {browser,context,page};
  }catch(error){await browser.close();throw error}
}
async function closeLogin(){const active=login;login=null;if(active)await active.browser.close()}
async function loginState(){
  if(!login)return {active:false};
  if(await isConnected(login.page)){
    await saveSession(login.account,await login.context.storageState());await closeLogin();return {active:false,connected:true};
  }
  if(Date.now()>login.expires){await closeLogin();return {active:false,expired:true}}
  return {active:true,challenge:await securityChallenge(login.page),image:(await login.page.screenshot({type:'jpeg',quality:65})).toString('base64'),width:1100,height:760,
    location:new URL(login.page.url()).origin+new URL(login.page.url()).pathname};
}
async function action(name,data){
  if(!/^(domadoo|[a-f0-9]{32})$/.test(data.account||''))throw new PortalError('Compte invalide.');
  if(busy)throw new PortalError('Navigateur occupé par une synchronisation.');
  if(name==='collect'){
    if(login)throw new PortalError('Terminer ou fermer la connexion humaine avant de synchroniser.');
    busy=true;let runtime;
    try{
      let state;try{state=await loadSession(data.account)}catch{throw new PortalError('Reconnexion requise : ouvrir une connexion humaine Domadoo.')}
      runtime=await browserContext(state);
      const result=await collect(runtime.page);
      await saveSession(data.account,await runtime.context.storageState());return result;
    }finally{await runtime?.browser.close();busy=false}
  }
  if(name==='disconnect'){
    if(login?.account===data.account)await closeLogin();
    await unlink(filename(data.account)).catch(error=>{if(error.code!=='ENOENT')throw error});return {connected:false};
  }
  if(name==='login/start'){
    if(login)throw new PortalError('Une fenêtre de connexion est déjà ouverte.');
    const runtime=await browserContext(undefined,true);
    login={...runtime,account:data.account,expires:Date.now()+15*60*1000};
    try{await login.page.goto(PORTAL,{waitUntil:'domcontentloaded'});return await loginState()}
    catch(error){await closeLogin();throw error}
  }
  if(!login)return {active:false};
  if(login.account!==data.account)throw new PortalError('Un autre compte utilise la fenêtre de connexion.');
  if(name==='login/close'){await closeLogin();return {active:false}}
  if(name==='login/verify'){
    // Do not reset an outstanding security check with another navigation.
    if(await securityChallenge(login.page))return loginState();
    await login.page.goto(PORTAL,{waitUntil:'domcontentloaded'});return loginState();
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
export function serve(){
  if(!token||token.length<32)throw new Error('Internal worker token required');
  let inputBusy=false;
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
      const result=await action(req.url.slice(1),data);res.end(JSON.stringify(result));
    }catch(error){res.writeHead(400);res.end(JSON.stringify({error:error instanceof PortalError?error.message:'Navigateur indisponible ou structure du portail modifiée. Dernier relevé conservé.'}))}
    finally{inputBusy=false;chunks=[]}
  });
  server.requestTimeout=35000;
  const cleanup=setInterval(()=>{if(login&&Date.now()>login.expires)closeLogin().catch(()=>{})},30000);cleanup.unref();
  process.on('SIGTERM',()=>{closeLogin().finally(()=>process.exit(0))});
  server.listen(3004,'127.0.0.1');return server;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))serve();
