import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)('playwright');
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import assert from 'node:assert/strict';
const directory=await mkdtemp(join(tmpdir(),'links-mfa-browser-'));
process.env.AFFILIATION_DATA_DIR=directory;
const {amazonMfaAction}=await import('./amazon-auth.mjs');
const source=await readFile(new URL('../admin/affiliation.js',import.meta.url),'utf8');
const helper=source.slice(source.indexOf(' function setupAmazonMfa('),source.indexOf(' function renderAmazon('));
let browser;
try{
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
 const pages=[];
 for(let i=0;i<2;i++){
  const page=await browser.newPage();pages.push(page);
  await page.exposeFunction('mfaRequest',async(action,data)=>amazonMfaAction(action.split('/').at(-1),data,{}));
  await page.setContent('<form id="aff-mfa-form"><input id="aff-mfa-secret"><button>Preview</button></form><p id="aff-mfa-state"></p><div id="aff-mfa-code-box"><strong id="aff-mfa-code"></strong><p id="aff-mfa-countdown"></p><input type="checkbox" id="aff-mfa-confirm-check"><button id="aff-mfa-confirm">Confirm</button><button id="aff-mfa-copy">Copy</button><button id="aff-mfa-cancel">Cancel</button></div><div id="aff-mfa-manage"><button id="aff-mfa-replace">Replace</button><button id="aff-mfa-remove">Remove</button></div>');
  await page.addScriptTag({content:`const $=id=>document.getElementById(id);let renderVersion=1,account='test',tab='connection',mfaTimer;const request=window.mfaRequest,say=()=>{};${helper};setupAmazonMfa('test');`});
  await page.waitForFunction(()=>document.getElementById('aff-mfa-state').textContent==='Aucune clé MFA enregistrée.');
 }
 for(const [index,page] of pages.entries()){
  await page.locator('#aff-mfa-secret').fill(index?'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQGEZA':'A'.repeat(52));
  await page.locator('#aff-mfa-form button').click();
  await page.waitForFunction(()=>/^\d{6}$/.test(document.getElementById('aff-mfa-code').textContent));
  assert.equal(await page.locator('#aff-mfa-secret').inputValue(),'');
  await page.locator('#aff-mfa-confirm-check').check();
 }
 await pages[0].locator('#aff-mfa-confirm').click();
 await pages[0].waitForFunction(()=>document.getElementById('aff-mfa-state').textContent.includes('autre onglet'));
 assert.equal((await amazonMfaAction('status',{},{})).active,false);
 await pages[1].locator('#aff-mfa-confirm').click();
 await pages[1].waitForFunction(()=>document.getElementById('aff-mfa-state').textContent.includes('activée'));
 assert.equal((await amazonMfaAction('status',{},{})).active,true);
 console.log('PASS MFA browser: two tabs, secret cleared, OTP shown, stale confirmation refused, current confirmation accepted.');
}finally{await browser?.close();await rm(directory,{recursive:true,force:true})}
