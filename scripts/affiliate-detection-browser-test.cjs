// Detection, explicit overrides and destination snapshots on disposable data.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {mkdtempSync,rmSync}=require('node:fs'),{tmpdir}=require('node:os'),{join,resolve}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-detection-')),python=process.env.PYTHON_PATH||'python3',origin='http://127.0.0.1:8081',publicOrigin='http://127.0.0.1:3003',db=join(temp,'stats.db');
 execFileSync(python,[resolve(__dirname,'fixtures.py'),db,publicOrigin]);
 // Simulate an instance already initialized by step 3, before the domain repair.
 execFileSync(python,['-c',"import sqlite3,sys,json;db=sqlite3.connect(sys.argv[1]);db.execute(\"UPDATE affiliate_partners SET domains=? WHERE name='Sanyipace'\",(json.dumps(['sanyipace.com','sanyipace.eu','custom.example']),));db.execute(\"DELETE FROM settings WHERE key='affiliate.sanyipace_domain_v1'\");db.commit()",db]);
 const server=spawn(python,[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:db,UPLOAD_DIR:join(temp,'uploads')},stdio:'ignore'});
 let browser;
 const api=async(path,data,method=data?'POST':'GET')=>{const response=await fetch(origin+path,{method,headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(response.ok,await response.clone().text());return response.json()};
 try{
  for(let i=0;i<100;i++){try{if((await fetch(origin+'/healthz')).ok)break}catch{}await new Promise(r=>setTimeout(r,100));}
  const partners=(await api('/api/affiliate-partners')).items,reolink=partners.find(row=>row.name==='Reolink'),domadoo=partners.find(row=>row.name==='Domadoo'),sanyipace=partners.find(row=>row.name==='Sanyipace');
  assert.deepEqual(sanyipace.domains,['sanyipacetoilet.com','custom.example']);
  const legacy=await api('/api/tracked-links',{name:'Déjà publié',url:'https://www.domadoo.fr/historique?direct=1'});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.route('https://shop.reolink.com/**',route=>route.fulfill({body:'Destination test'}));
  const page=await context.newPage(),errors=[];let approve=true,confirmations=[];
  page.on('pageerror',error=>errors.push(error.message));page.on('dialog',dialog=>{confirmations.push(dialog.message());return approve?dialog.accept():dialog.dismiss()});
  await page.goto(origin);await page.locator('#chart svg').waitFor();await page.click('[data-tab="tracked-links"]');
  const legacyRow=page.locator(`[data-tracked-id="${legacy.id}"]`);await legacyRow.waitFor();await legacyRow.locator('[data-tracked-action="edit"]').click();
  await page.waitForFunction(url=>document.getElementById('tracked-final-link').getAttribute('href')===url,legacy.url);
  assert.equal(await page.inputValue('#tracked-partner'),'');await page.fill('#tracked-form [name="notes"]','Mise à jour sans changer la destination');await page.click('#tracked-form [type="submit"]');await page.locator('#tracked-dialog').waitFor({state:'hidden'});assert.equal(confirmations.length,0);
  await page.click('[data-action="new-tracked"]');await page.fill('#tracked-form [name="name"]','Caméra affiliée');
  const preview=async url=>page.waitForFunction(expected=>document.getElementById('tracked-final-link').getAttribute('href')===expected,url);
  await page.fill('#tracked-form [name="url"]','https://eu.sanyipacetoilet.com/produit');await preview('https://eu.sanyipacetoilet.com/produit?ref=DomotiK');assert.equal(await page.inputValue('#tracked-partner'),sanyipace.id);
  // An older slow response must not overwrite the latest detection or preview.
  await page.route('**/api/tracked-links/preview',async route=>{const data=route.request().postDataJSON();if(data.url.includes('shop.reolink.com'))await new Promise(resolve=>setTimeout(resolve,250));await route.continue()});
  await page.fill('#tracked-form [name="url"]','https://shop.reolink.com/first');await page.fill('#tracked-form [name="url"]','https://eu.sanyipacetoilet.com/latest');await preview('https://eu.sanyipacetoilet.com/latest?ref=DomotiK');await page.waitForTimeout(300);assert.equal(await page.inputValue('#tracked-partner'),sanyipace.id);await page.unroute('**/api/tracked-links/preview');
  await page.selectOption('#tracked-partner',domadoo.id);await preview('https://eu.sanyipacetoilet.com/latest?domid=117');await page.fill('#tracked-form [name="url"]','https://other.example/manual');await preview('https://other.example/manual?domid=117');
  await page.selectOption('#tracked-partner','');await page.fill('#tracked-form [name="url"]','https://shop.reolink.com/camera');await preview('https://shop.reolink.com/camera');assert.equal(await page.inputValue('#tracked-partner'),'');
  await page.selectOption('#tracked-partner',reolink.id);const original='https://shop.reolink.com/camera',savedUrl=original+'?aff=1404';await preview(savedUrl);
  const popupPromise=context.waitForEvent('page');await page.click('#tracked-final-link');const popup=await popupPromise;await popup.waitForLoadState();assert.equal(popup.url(),savedUrl);assert.equal(await popup.evaluate(()=>window.opener),null);await popup.close();
  await page.click('#tracked-form [type="submit"]');await page.locator('#tracked-dialog').waitFor({state:'hidden'});
  const saved=(await api('/api/tracked-links')).items.find(row=>row.name==='Caméra affiliée');assert.equal(saved.url,savedUrl);assert.equal(saved.original_url,original);assert.equal(saved.partner_id,reolink.id);
  const source=(await api('/api/tracking-sources')).items[0],token=await api(`/api/tracked-links/${saved.id}/token`,{source_id:source.id});
  const head=async()=>fetch(publicOrigin+new URL(token.url).pathname,{method:'HEAD',redirect:'manual'});
  assert.equal((await head()).headers.get('location'),savedUrl);
  await api('/api/affiliate-partners/'+reolink.id,{...reolink,code:'UPDATED'},'PUT');assert.equal((await head()).headers.get('location'),savedUrl);
  const row=page.locator(`[data-tracked-id="${saved.id}"]`);await row.locator('[data-tracked-action="edit"]').click();await preview(savedUrl);assert.equal(await page.inputValue('#tracked-form [name="url"]'),original);
  await page.fill('#tracked-form [name="notes"]','Garder la destination publiée');await page.click('#tracked-form [type="submit"]');await page.locator('#tracked-dialog').waitFor({state:'hidden'});assert.equal(confirmations.length,0);assert.equal((await head()).headers.get('location'),savedUrl);
  await row.locator('[data-tracked-action="edit"]').click();await page.click('#tracked-recalculate');const updatedUrl=original+'?aff=UPDATED';await preview(updatedUrl);
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:900});for(const theme of ['light','dark']){await page.selectOption('#theme-select',theme);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));if(process.env.UI_SCREENSHOTS&&width!==320){await page.waitForTimeout(200);await page.screenshot({path:join(process.env.UI_SCREENSHOTS,`detection-${width}-${theme}.png`),fullPage:true});}}}
  approve=false;await page.click('#tracked-form [type="submit"]');await page.waitForFunction(()=>!document.querySelector('#tracked-form [type="submit"]').disabled);assert(await page.locator('#tracked-dialog').isVisible());assert.equal((await head()).headers.get('location'),savedUrl);assert(confirmations.at(-1).includes(savedUrl)&&confirmations.at(-1).includes(updatedUrl));
  approve=true;await page.click('#tracked-form [type="submit"]');await page.locator('#tracked-dialog').waitFor({state:'hidden'});assert.equal((await head()).headers.get('location'),updatedUrl);assert.equal((await api(`/api/tracked-links/${saved.id}/token`,{source_id:source.id})).url,token.url);
  await row.locator('[data-tracked-action="edit"]').click();await page.selectOption('#tracked-partner','');await preview(original);await page.click('#tracked-form [type="submit"]');await page.locator('#tracked-dialog').waitFor({state:'hidden'});
  const direct=(await api('/api/tracked-links')).items.find(item=>item.id===saved.id);assert.equal(direct.url,original);assert.equal(direct.original_url,original);assert.equal(direct.partner_id,'');assert.equal(direct.clicks,saved.clicks);
  assert.equal((await api('/api/tracked-links')).items.find(item=>item.id===legacy.id).url,legacy.url);assert.deepEqual(errors,[]);
  console.log('PASS: initialized domain migration, subdomain detection/latest preview, manual/None overrides, generated/original persistence, explicit confirmation/cancel, unchanged published URLs after code edits, stable short URLs/history, responsive themes.');
 }finally{await browser?.close();const exited=new Promise(resolve=>server.once('exit',resolve));server.kill();await exited;rmSync(temp,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1});
