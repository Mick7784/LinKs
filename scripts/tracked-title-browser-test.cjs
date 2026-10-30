// Browser regression: existing tracked editor, partner preview, and manual naming.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {mkdtempSync,rmSync}=require('node:fs');
const {tmpdir}=require('node:os');
const {join,resolve}=require('node:path');

(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-title-'));
 const origin='http://127.0.0.1:8081',publicOrigin='http://127.0.0.1:3003';
 const python=process.env.PYTHON_PATH||'python3';
 execFileSync(python,[resolve(__dirname,'fixtures.py'),join(temp,'stats.db'),publicOrigin]);
 const server=spawn(python,[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:'ignore'});
 let browser;
 try{
  let ready=false;
  for(let n=0;n<100;n++){
   try{if((await fetch(origin+'/healthz')).ok){ready=true;break}}catch{}
   await new Promise(done=>setTimeout(done,100));
  }
  assert(ready,'Admin instance did not start');
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
  const context=await browser.newContext({viewport:{width:1500,height:950}});
  let requests=0;
  await context.route('**/api/tracked-links/title-preview',async route=>{
   requests++;
   const url=route.request().postDataJSON().url;
   if(url.endsWith('/old'))await new Promise(done=>setTimeout(done,950));
   const name=url.endsWith('/two')?'Produit Deux':url.endsWith('/three')?'Produit Trois':url.endsWith('/old')?'Produit Ancien':url.endsWith('/empty')?'':'Produit Un';
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
    title:name,status:name?'ok':'unavailable',source:name?'open_graph':''
   })});
  });
  const page=await context.newPage(),errors=[];
  page.on('pageerror',err=>errors.push(err.message));
  await page.goto(origin);
  await page.locator('#chart svg').waitFor();
  if(await page.locator('#menu-toggle').isVisible())await page.locator('#menu-toggle').click();
  await page.locator('[data-tab="tracked-links"]').click();
  await page.locator('#tracked-links.active').waitFor();

  const name=page.locator('#tracked-form [name="name"]'),url=page.locator('#tracked-form [name="url"]');
  await page.locator('[data-action="new-tracked"]').click();
  await page.locator('#tracked-dialog').waitFor({state:'visible'});
  await url.fill('https://example.com/one');
  await page.waitForFunction(()=>document.querySelector('#tracked-form [name="name"]').value==='Produit Un');
  assert.match(await page.locator('#tracked-title-suggestion-status').textContent(),/Nom proposé automatiquement/);
  await url.fill('https://example.com/two');
  await page.waitForFunction(()=>document.querySelector('#tracked-form [name="name"]').value==='Produit Deux');

  // A manual title is sticky, even when the URL changes or an earlier response arrives.
  await name.fill('Titre choisi manuellement');
  await url.fill('https://example.com/three');
  await page.waitForTimeout(700);
  assert.equal(await name.inputValue(),'Titre choisi manuellement');
  const countAfterManual=requests;

  // Clearing the name opts back into suggestions.
  await name.fill('');
  await page.waitForFunction(()=>document.querySelector('#tracked-form [name="name"]').value==='Produit Trois');
  assert(requests>countAfterManual);

  // Older in-flight suggestions cannot overwrite a newer URL's title.
  await url.fill('https://example.com/old');
  await page.waitForTimeout(540);
  await url.fill('https://example.com/two');
  await page.waitForFunction(()=>document.querySelector('#tracked-form [name="name"]').value==='Produit Deux');
  await page.waitForTimeout(1050);
  assert.equal(await name.inputValue(),'Produit Deux');

  // Detection failure never prevents entering a name manually.
  await url.fill('https://example.com/empty');
  await page.waitForFunction(()=>document.querySelector('#tracked-title-suggestion-status').textContent.includes('Titre non détecté'));
  assert.equal(await name.inputValue(),'');
  await name.fill('Mon titre personnel');
  await page.waitForFunction(()=>!document.querySelector('#tracked-form [type="submit"]').disabled);
  await page.locator('#tracked-form [type="submit"]').click();
  await page.locator('#tracked-dialog').waitFor({state:'hidden'});
  const row=page.locator('#tracked-list .tracked-item').filter({hasText:'Mon titre personnel'});
  await row.waitFor();

  // Editing an existing link must never replace its saved name.
  await row.locator('[data-tracked-action="edit"]').click();
  await page.locator('#tracked-dialog').waitFor({state:'visible'});
  assert.equal(await name.inputValue(),'Mon titre personnel');
  const beforeEdit=requests;
  await url.fill('https://example.com/one');
  await page.waitForTimeout(700);
  assert.equal(await name.inputValue(),'Mon titre personnel');
  assert.equal(requests,beforeEdit,'No automatic analysis in the existing-link editor');
  await page.locator('[data-close-tracked]').first().click();
  await page.locator('#tracked-dialog').waitFor({state:'hidden'});

  assert.deepEqual(errors,[]);
  console.log('PASS: automatic title, manual override, stale response, failure fallback, edit preservation, and existing form flow.');
 }finally{
  if(browser)await browser.close();
  const finished=new Promise(done=>server.once('exit',done));server.kill();await finished;
  rmSync(temp,{recursive:true,force:true});
 }
})().catch(error=>{console.error(error);process.exitCode=1});
