import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {normalSignIn,requestReports,allowedAmazonNavigation,parisGenerationMinute} from './amazon-collector.mjs';
const {chromium}=createRequire(import.meta.url)('playwright-core');
const launch=()=>chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
test('ordinary email/password/TOTP sequence reaches report page without extra login',async()=>{
 const browser=await launch();let step=0;const sent=[];
 try{
  const page=await browser.newPage();
  await page.route('**/*',async route=>{
   if(route.request().method()==='POST'){sent.push(route.request().postData());step++}
   const fields=['ap_email','ap_password','auth-mfa-otpcode'];
   const html=step===3?'<button>Télécharger rapports</button>':`<form method="post" action="/ap/signin"><input name="value" id="${fields[step]}" ${step===1?'type="password"':''}><input type="submit"></form>`;
   if(step===3&&!route.request().url().includes('/home/reports'))return route.fulfill({contentType:'text/html; charset=utf-8',body:'<script>location.href="https://partenaires.amazon.fr/home/reports"</script>'});
   await route.fulfill({contentType:'text/html; charset=utf-8',body:html});
  });
  await page.goto('https://www.amazon.fr/ap/signin');
  assert.equal((await normalSignIn(page,{login:'fixture-user',password:'fixture-password',totp:()=> '123456'})).status,'authenticated');
  assert.equal(sent.length,3);assert.equal(sent[2],'value=123456');
 }finally{await browser.close()}
});
test('CAPTCHA stops before sending credentials; unsafe destinations rejected',async()=>{
 const browser=await launch();
 try{const page=await browser.newPage();await page.route('**/*',r=>r.fulfill({contentType:'text/html',body:'<input id="captchacharacters"><input type="password">'}));await page.goto('https://www.amazon.fr/ap/signin');
 await assert.rejects(normalSignIn(page,{login:'fixture',password:'fixture',totp:()=>{throw Error('must not run')}}),{code:'amazon_intervention'});
 for(const url of ['http://www.amazon.fr/ap/signin','https://evil.test/home','https://www.amazon.fr/ap/cvf','https://partenaires.amazon.fr/homeevil'])assert.equal(allowedAmazonNavigation(url),false);
 }finally{await browser.close()}
});
const reportHtml=(generate=true)=>`<label>Tracking IDs<select><option value="tag">test-21</option><option value="all">Tous les Tracking IDs</option></select></label><button>Télécharger rapports</button><label for="period">Période</label><select id="period"><option value="month">Ce mois</option><option value="custom">Personnalisée</option></select><label>Du<input type="date"></label><label>Au<input type="date"></label><label><input type="checkbox">Category</label><label><input type="checkbox">Linked-Product</label><label><input type="checkbox">Tracking-Id</label><label><input type="radio" name="format" checked>XLSX</label><label><input type="radio" name="format">CSV</label><button onclick="${generate?"setTimeout(()=>document.querySelector('tbody').insertAdjacentHTML('beforeend',window.newRows),100)":"void 0"}">Générer des rapports</button><table><tbody>${rows('10:00 31/10/2026','old')}</tbody></table><script>window.newRows=${JSON.stringify(rows(generatedNow(),'new'))}</script>`;
function generatedNow(){const m=parisGenerationMinute().match(/(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2})/);return `${m[4]} ${m[3]}/${m[2]}/${m[1]}`}
function rows(time,batch){return ['Category','Linked-Product','Tracking-Id'].map(type=>`<tr><td>${type}</td><td>CSV</td><td>${time}</td><td><a href="/home/export?type=${type}&batch=${batch}">Télécharger</a></td></tr>`).join('')}
async function reportPage(browser,generate=true){
 const page=await browser.newPage({acceptDownloads:true});const requests=[];
 await page.route('**/*',route=>{
  const url=new URL(route.request().url());
  if(url.pathname==='/home/export'){requests.push(url.searchParams.get('batch'));return route.fulfill({headers:{'content-type':'text/csv','content-disposition':`attachment; filename="${url.searchParams.get('type')}-01nov2026-120000.csv"`},body:'Date,clics\n10-31-2026,2\n'})}
  return route.fulfill({contentType:'text/html; charset=utf-8',body:reportHtml(generate)});
 });
 await page.goto('https://partenaires.amazon.fr/home/reports');return {page,requests};
}
test('checkboxes, CSV and async generation download only the new batch',async()=>{
 const browser=await launch();try{
  const {page,requests}=await reportPage(browser),stages=[];
  const files=await requestReports(page,'2026-10-31',{progress:s=>stages.push(s),pollMs:25,waitMs:3000});
  assert.equal(files.length,3);assert.deepEqual(requests,['new','new','new']);
  assert.equal(await page.getByLabel('CSV',{exact:true}).isChecked(),true);
  assert.equal(await page.getByLabel('Du',{exact:true}).inputValue(),'2026-10-31');
  assert.deepEqual(stages,['reports','period','selection','generation','waiting','download']);
 }finally{await browser.close()}
});
test('old available reports never satisfy a new generation',async()=>{
 const browser=await launch();try{
  const {page,requests}=await reportPage(browser,false);
  await assert.rejects(requestReports(page,'2026-10-31',{pollMs:20,waitMs:100}),{code:'amazon_generation_timeout'});
  assert.equal(requests.length,0);
 }finally{await browser.close()}
});
