// Server-only preparation for an Amazon Associates portal adapter. No portal
// navigation is enabled until the access method and permission are verified.
import {createHmac} from 'node:crypto';
import {loadSession,saveSession,deleteSession} from './affiliation-worker.mjs';

const SESSION_ACCOUNT='amazon-portal';
const MFA_ACCOUNT='amazon-mfa';

export function amazonCredentials(env=process.env){
  const login=env.AMAZON_LOGIN?.trim();
  const password=env.AMAZON_PASSWORD;
  const mfaSecret=env.AMAZON_MFA_SECRET?.replace(/[\s-]/g,'').toUpperCase();
  if(!login&&!password&&!mfaSecret)return null;
  if(!login||!password)throw new Error('Configurer AMAZON_LOGIN et AMAZON_PASSWORD ensemble côté serveur.');
  if(mfaSecret)decodeBase32(mfaSecret);
  return {login,password,mfaSecret:mfaSecret||null};
}

function decodeBase32(secret){
  if(!/^[A-Z2-7]+$/.test(secret))throw new Error('AMAZON_MFA_SECRET doit être une clé Base32 valide.');
  let bits=0,value=0;
  const bytes=[];
  for(const char of secret){
    value=(value<<5)|'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'.indexOf(char);
    bits+=5;
    if(bits>=8){bits-=8;bytes.push((value>>>bits)&255)}
    value&=(1<<bits)-1;
  }
  if(!bytes.length||value!==0)throw new Error('AMAZON_MFA_SECRET doit être une clé Base32 valide.');
  return Buffer.from(bytes);
}

// RFC 6238: six-digit SHA-1 TOTP, 30-second period. Keep the code server-side.
export function amazonTotp(secret,now=Date.now()){
  if(!Number.isSafeInteger(now)||now<0)throw new Error('Horodatage TOTP invalide.');
  const key=decodeBase32(secret.replace(/[\s-]/g,'').toUpperCase());
  const counter=Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(now/30000)));
  const digest=createHmac('sha1',key).update(counter).digest();
  const offset=digest.at(-1)&15;
  return ((digest.readUInt32BE(offset)&0x7fffffff)%1000000).toString().padStart(6,'0');
}

export async function loadAmazonSession(){
  try{return await loadSession(SESSION_ACCOUNT)}
  catch(error){if(error.code==='ENOENT')return null;throw new Error('Session Amazon illisible. Une reconnexion est nécessaire.')}
}

export async function saveAmazonSession(state){
  if(!state||typeof state!=='object'||Array.isArray(state))throw new Error('Session Amazon invalide.');
  await saveSession(SESSION_ACCOUNT,state);
}

async function mfaRecord(pending=false){
  try{return await loadSession(MFA_ACCOUNT,pending)}
  catch(error){if(error.code==='ENOENT')return null;throw new Error('Clé MFA chiffrée illisible. Remplacez-la sur le serveur.')}
}

async function activeMfaSecret(){
  const record=await mfaRecord();
  return record?.secret||null;
}

function mfaCode(secret){
  const now=Date.now();
  return {code:amazonTotp(secret,now),remainingMs:30000-now%30000};
}

// Responses contain state and short-lived OTP only, never the TOTP seed.
export async function amazonMfaAction(action,data={},env=process.env){
  if(action==='status')return {active:Boolean(await activeMfaSecret()||env.AMAZON_MFA_SECRET),pending:Boolean(await mfaRecord(true)),environment:Boolean(env.AMAZON_MFA_SECRET)};
  if(action==='preview'){
    const secret=typeof data.secret==='string'?data.secret.replace(/[\s-]/g,'').toUpperCase():'';
    if(secret.length!==52)throw new Error('La clé MFA Amazon doit contenir exactement 52 caractères Base32.');
    decodeBase32(secret);
    await saveSession(MFA_ACCOUNT,{secret},true);
    return {pending:true,...mfaCode(secret)};
  }
  if(action==='code'){
    const record=await mfaRecord(true);
    if(!record?.secret)throw new Error('Aucune clé MFA en attente de confirmation.');
    return {pending:true,...mfaCode(record.secret)};
  }
  if(action==='confirm'){
    if(data.confirmed!==true)throw new Error('Confirmez d’abord l’activation sur le site Amazon.');
    const record=await mfaRecord(true);
    if(!record?.secret)throw new Error('Aucune clé MFA en attente de confirmation.');
    await saveSession(MFA_ACCOUNT,record);
    await deleteSession(MFA_ACCOUNT,true);
    return {active:true,pending:false,environment:Boolean(env.AMAZON_MFA_SECRET)};
  }
  if(action==='cancel'){
    await deleteSession(MFA_ACCOUNT,true);
    return {pending:false,active:Boolean(await activeMfaSecret()||env.AMAZON_MFA_SECRET),environment:Boolean(env.AMAZON_MFA_SECRET)};
  }
  if(action==='remove'){
    if(env.AMAZON_MFA_SECRET)throw new Error('Retirez d’abord AMAZON_MFA_SECRET de la configuration serveur.');
    await deleteSession(MFA_ACCOUNT,true);
    await deleteSession(MFA_ACCOUNT);
    return {active:false,pending:false,environment:false};
  }
  throw new Error('Action MFA Amazon inconnue.');
}

// The future portal adapter must distinguish an ordinary expired session from
// an additional security check. One normal sign-in attempt is allowed; neither
// a rejected login nor an extra check is retried or bypassed.
export async function ensureAmazonSession(adapter,env=process.env){
  const saved=await loadAmazonSession();
  if(saved){
    let status;
    try{status=await adapter.verify(saved)}catch{throw new Error('Vérification de la session Amazon interrompue.')}
    if(status==='authenticated')return saved;
    if(status!=='expired')throw new Error('Vérification Amazon requise. Connexion automatique suspendue.');
  }
  const credentials=amazonCredentials(env);
  if(!credentials)throw new Error('Connexion Amazon requise. Identifiants serveur absents.');
  const mfaSecret=await activeMfaSecret()||credentials.mfaSecret;
  let result;
  try{result=await adapter.signIn({login:credentials.login,password:credentials.password,
    totp:()=>mfaSecret?amazonTotp(mfaSecret):null})}
  catch{throw new Error('Connexion Amazon interrompue. Vérification manuelle requise.')}
  if(result?.status!=='authenticated')throw new Error('Connexion Amazon non confirmée. Vérification manuelle requise.');
  let state;
  try{state=await adapter.capture()}catch{throw new Error('Session Amazon non enregistrée. Vérification manuelle requise.')}
  await saveAmazonSession(state);
  return state;
}
