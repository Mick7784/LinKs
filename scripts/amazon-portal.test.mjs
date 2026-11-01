import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)('playwright-core');
const directory=await mkdtemp(join(tmpdir(),'links-amazon-session-'));
process.env.AFFILIATION_DATA_DIR=directory;
const {saveAmazonSession,loadAmazonSession,ensureAmazonSession}=await import('./amazon-auth.mjs');
const {inspectAmazonPage}=await import('./amazon-portal.mjs');
test.after(()=>rm(directory,{recursive:true,force:true}));
test('verified session rotates without another login and failed capture preserves saved state',async()=>{
 await saveAmazonSession({cookies:['old']});let login=0;
 const adapter={verify:async()=> 'authenticated',capture:async()=>({cookies:['rotated']}),signIn:async()=>{login++}};
 await ensureAmazonSession(adapter,{});
 assert.deepEqual(await loadAmazonSession(),{cookies:['rotated']});assert.equal(login,0);
 adapter.capture=async()=>{throw new Error('PRIVATE_COOKIE')};
 await assert.rejects(ensureAmazonSession(adapter,{}),error=>!error.message.includes('PRIVATE_COOKIE'));
 assert.deepEqual(await loadAmazonSession(),{cookies:['rotated']});
});
test('read-only browser diagnostic never claims login or collection success',async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
 try{
  const page=await browser.newPage();
  for(const [html,status,expected] of [['<input type="password">',200,'login_required'],['<input autocomplete="one-time-code">',200,'otp_required'],['<input id="captchacharacters"><input type="password">',200,'intervention_required'],['',403,'access_denied'],['',429,'rate_limited'],['<table><tr><td>Reports</td></tr></table>',200,'unverified']]){
   await page.setContent(html);const result=await inspectAmazonPage(page,status);
   assert.equal(result.code,expected);assert.equal(result.connected,false);assert.equal(result.collection_enabled,false);
  }
 }finally{await browser.close()}
});
