import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const directory=await mkdtemp(join(tmpdir(),'links-amazon-auth-'));
process.env.AFFILIATION_DATA_DIR=directory;
const {amazonCredentials,amazonTotp,loadAmazonSession,saveAmazonSession,ensureAmazonSession}=await import('./amazon-auth.mjs');
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
