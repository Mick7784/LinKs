import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {normalSignIn,requestReports,allowedAmazonNavigation} from './amazon-collector.mjs';
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
test('bounded downloads are requested for the chosen date and all tracking IDs',async()=>{
 const browser=await launch();let exports=0;
 try{
  const page=await browser.newPage({acceptDownloads:true});
  await page.route('**/*',route=>{
   if(route.request().url().includes('/home/download')){exports++;return route.fulfill({headers:{'content-type':'text/csv','content-disposition':'attachment; filename="report.csv"'},body:'Date,clics\n10-31-2026,2\n'})}
   return route.fulfill({contentType:'text/html; charset=utf-8',body:`<button onclick="document.querySelector('dialog').showModal()">Télécharger rapports</button><dialog><label>Du<input type="date"></label><label>Au<input type="date"></label><label for="type">Type de rapport</label><select id="type"><option>Catégories</option><option>Produits liés</option><option>Tracking ID</option></select><label for="tracking">Tracking ID</label><select id="tracking"><option value="single">Un</option><option value="all">Tous</option></select><button onclick="location.href='/home/download'">Générer</button><button onclick="document.querySelector('dialog').close()">Fermer</button></dialog>`});
  });
  await page.goto('https://partenaires.amazon.fr/home/reports');
  const files=await requestReports(page,'2026-10-31');assert.equal(files.length,3);assert.equal(exports,3);assert.equal(files[0].csv,'Date,clics\n10-31-2026,2\n');
  assert.equal(await page.getByLabel('Du',{exact:true}).inputValue(),'2026-10-31');
  assert.equal(await page.getByLabel('Tracking ID',{exact:true}).inputValue(),'all');
 }finally{await browser.close()}
});

