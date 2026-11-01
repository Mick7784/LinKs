import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const root=await mkdtemp(join(tmpdir(),'links-amazon-status-'));
process.env.AFFILIATION_DATA_DIR=root;process.env.AFFILIATION_WORKER_TOKEN='synthetic-worker-token-for-concurrency-test';
const {createActions,serve}=await import('./affiliation-worker.mjs');
test.after(()=>rm(root,{recursive:true,force:true}));
test('HTTP MFA/progress reads remain available during collection without unlocking mutations',async()=>{
 let finish,entered;const gate=new Promise(r=>{finish=r}),started=new Promise(r=>{entered=r});
 const account='a'.repeat(32),controller=createActions(undefined,async(data,{progress})=>{
  progress({stage:'waiting',message:'Attente des nouveaux exports'});entered();await gate;return {complete:true};
 });
 const pending=await controller.action('amazon/mfa/preview',{account,secret:'A'.repeat(52)});
 const server=serve(controller,0);await new Promise(r=>server.once('listening',r));
 const call=(action,data={})=>fetch(`http://127.0.0.1:${server.address().port}/${action}`,{method:'POST',headers:{Authorization:'Bearer '+process.env.AFFILIATION_WORKER_TOKEN,'Content-Type':'application/json'},body:JSON.stringify({account,...data})});
 let collection;
 try{
  collection=call('amazon/collect',{run:7,day:'2026-10-31'});await started;
  assert.equal((await call('amazon/mfa/status')).status,200);
  assert.equal((await call('amazon/mfa/code',{version:pending.version})).status,200);
  const status=await (await call('amazon/status',{run:7})).json();assert.equal(status.stage,'waiting');
  assert.equal((await (await call('amazon/status',{run:8})).json()).stage,'queued');
  assert.equal((await call('amazon/mfa/remove')).status,409);
  assert.equal((await call('amazon/disconnect')).status,409);
  finish();assert.equal((await collection).status,200);
 }finally{finish();await collection;await new Promise(r=>server.close(r))}
});

test('authentication preserves typed diagnostics without returning raw browser exceptions',async()=>{
 const {ensureAmazonSession,saveAmazonSession}=await import('./amazon-auth.mjs');
 const {AmazonCollectionError}=await import('./amazon-collector.mjs');
 const expected=new AmazonCollectionError('Amazon refuse cet accès (HTTP 403).','amazon_access_denied');
 await saveAmazonSession({storageState:{cookies:[],origins:[]}});
 await assert.rejects(ensureAmazonSession({verify:async()=>{throw expected}},{}),error=>error.cause===expected);
 const {deleteSession}=await import('./affiliation-worker.mjs');await deleteSession('amazon-portal');
 await assert.rejects(ensureAmazonSession({signIn:async()=>{throw expected}},{AMAZON_LOGIN:'fixture',AMAZON_PASSWORD:'fixture'}),error=>error.cause===expected);
});
