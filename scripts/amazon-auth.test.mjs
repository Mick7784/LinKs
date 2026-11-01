import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const directory=await mkdtemp(join(tmpdir(),'links-amazon-auth-'));
process.env.AFFILIATION_DATA_DIR=directory;
const {amazonCredentials,amazonTotp,loadAmazonSession,saveAmazonSession,ensureAmazonSession,amazonMfaAction}=await import('./amazon-auth.mjs');
const {createActions}=await import('./affiliation-worker.mjs');
test.after(()=>rm(directory,{recursive:true,force:true}));
const env={AMAZON_LOGIN:'test@example.invalid',AMAZON_PASSWORD:'synthetic-password',AMAZON_MFA_SECRET:'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'};

test('optional credentials and standard RFC 6238 TOTP',()=>{
  assert.equal(amazonCredentials({}),null);
  assert.equal(amazonCredentials({AMAZON_LOGIN:'a',AMAZON_PASSWORD:'b'}).mfaSecret,null);
});

test('TOTP and malformed configuration',()=>{
  assert.equal(amazonTotp(env.AMAZON_MFA_SECRET,59000),'287082');
  assert.throws(()=>amazonCredentials({AMAZON_LOGIN:'a'}),/ensemble/);
  assert.throws(()=>amazonCredentials({...env,AMAZON_MFA_SECRET:'bad!'}),/Base32/);
  assert.equal(amazonCredentials(env).login,env.AMAZON_LOGIN);
});

test('encrypted Amazon session is separate and normal reconnect happens once',async()=>{
  assert.equal(await loadAmazonSession(),null);
  const saved={cookies:[{name:'synthetic',value:'PRIVATE-SESSION'}]};
  await saveAmazonSession(saved);
  const disk=await readFile(join(directory,'amazon-portal.session'));
  assert.equal(disk.includes(Buffer.from('PRIVATE-SESSION')),false);
  assert.deepEqual(await loadAmazonSession(),saved);
  let signs=0;
  const adapter={verify:async()=> 'expired',signIn:async({login,password,totp})=>{
    signs++;
    assert.equal(login,env.AMAZON_LOGIN);
    assert.equal(password,env.AMAZON_PASSWORD);
    assert.equal(typeof totp(),'string');
    return {status:'authenticated'};
  },capture:async()=>({cookies:[{name:'fresh',value:'NEW-SESSION'}]})};
  assert.equal((await ensureAmazonSession(adapter,env)).cookies[0].value,'NEW-SESSION');
  assert.equal(signs,1);
  assert.deepEqual((await loadAmazonSession()).cookies,[{name:'fresh',value:'NEW-SESSION'}]);
  adapter.verify=async()=> 'authenticated';
  await ensureAmazonSession(adapter,env);
  assert.equal(signs,1);
  adapter.verify=async()=> 'additional_check';
  await assert.rejects(ensureAmazonSession(adapter,env),/suspendue/);
  assert.equal(signs,1);
  adapter.verify=async()=> 'expired';
  adapter.signIn=async()=>{throw new Error('PRIVATE-SESSION '+env.AMAZON_PASSWORD)};
  await assert.rejects(ensureAmazonSession(adapter,env),error=>!error.message.includes(env.AMAZON_PASSWORD));
});

test('MFA seed is encrypted, never returned, confirmed locally, replaceable and removable',async()=>{
  const secret='GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZA';
  assert.equal(secret.length,52);
  const first=await amazonMfaAction('preview',{secret},{});
  assert.match(first.code,/^\d{6}$/);
  assert.equal(JSON.stringify(first).includes(secret),false);
  assert.equal((await readFile(join(directory,'amazon-mfa.pending-session'))).includes(Buffer.from(secret)),false);
  assert.equal((await amazonMfaAction('status',{},{})).pending,true);
  const routed=await createActions().action('amazon/mfa/code',{account:'a'.repeat(32)});
  assert.match(routed.code,/^\d{6}$/);
  assert.equal(JSON.stringify(routed).includes(secret),false);
  await assert.rejects(amazonMfaAction('confirm',{},{}),/Confirmez/);
  const confirmed=await amazonMfaAction('confirm',{confirmed:true,version:first.version},{});
  assert.deepEqual(confirmed,{active:true,pending:false,environment:false});
  assert.equal(JSON.stringify(confirmed).includes(secret),false);
  assert.equal((await readFile(join(directory,'amazon-mfa.session'))).includes(Buffer.from(secret)),false);
  assert.equal((await amazonMfaAction('status',{},{})).active,true);
  const replacement='A'.repeat(52);
  const next=await amazonMfaAction('preview',{secret:replacement},{});
  assert.equal((await amazonMfaAction('status',{},{})).active,true);
  await amazonMfaAction('cancel',{version:next.version},{});
  assert.equal((await amazonMfaAction('status',{},{})).active,true);
  await assert.rejects(amazonMfaAction('remove',{},env),/Retirez/);
  await amazonMfaAction('remove',{},{});
  assert.deepEqual(await amazonMfaAction('status',{},{}),{active:false,pending:false,environment:false,conflict:false,source:'none'});
});

test('concurrent pending versions and conflicting sources fail closed',async()=>{
 const key='A'.repeat(52),other='GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZA';
 const [first,second]=await Promise.all([amazonMfaAction('preview',{secret:key},{}),amazonMfaAction('preview',{secret:other},{})]);
 await assert.rejects(amazonMfaAction('confirm',{confirmed:true,version:first.version},{}),/autre onglet/);
 await assert.rejects(amazonMfaAction('code',{version:first.version},{}),/autre onglet/);
 await amazonMfaAction('confirm',{confirmed:true,version:second.version},{});
 const configuration={...env,AMAZON_MFA_SECRET:key};
 const status=await amazonMfaAction('status',{},configuration);
 assert.equal(status.conflict,true);assert.equal(status.active,false);
 await assert.rejects(ensureAmazonSession({},configuration),/Conflit MFA/);
 await assert.rejects(amazonMfaAction('preview',{secret:key},configuration),/Retirez/);
 assert.equal((await amazonMfaAction('status',{},{})).source,'links');
 assert.equal((await amazonMfaAction('status',{}, {...configuration,AMAZON_MFA_SECRET:other})).source,'environment');
 await amazonMfaAction('remove',{},{});
});
