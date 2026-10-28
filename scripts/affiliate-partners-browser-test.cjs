// Partner configuration only: existing tracked destinations must stay untouched.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {mkdtempSync,rmSync}=require('node:fs'),{tmpdir}=require('node:os'),{join,resolve}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-partners-')),python=process.env.PYTHON_PATH||'python3',origin='http://127.0.0.1:8081',db=join(temp,'stats.db');
 execFileSync(python,[resolve(__dirname,'fixtures.py'),db]);
 const server=spawn(python,[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:db,UPLOAD_DIR:join(temp,'uploads')},stdio:'ignore'});
 let browser;
 const api=async(path,data)=>{const response=await fetch(origin+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(response.ok,await response.clone().text());return response.json()};
 try{
  for(let i=0;i<100;i++){try{if((await fetch(origin+'/healthz')).ok)break}catch{}await new Promise(r=>setTimeout(r,100));}
  const existing=await api('/api/tracked-links',{name:'Affiliation directe',url:'https://example.com/direct?tag=UNCHANGED'});
  const before=await api('/api/tracked-links');
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.route('https://redirect.example/**',route=>route.fulfill({body:'Vérification manuelle'}));
  const page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));page.on('dialog',dialog=>dialog.accept());
  const nav=async()=>{if(await page.locator('#menu-toggle').isVisible())await page.click('#menu-toggle');await page.click('[data-tab="tracked-links"]');await page.locator('#partner-list [data-partner-id]').first().waitFor()};
  await page.goto(origin);await page.locator('#chart svg').waitFor();await nav();
  const defaults=(await api('/api/affiliate-partners')).items;assert.equal(defaults.length,3);
  for(const row of defaults)assert(await page.locator(`[data-partner-id="${row.id}"]`).isVisible());
  const domadoo=defaults.find(row=>row.name==='Domadoo'),domadooRow=page.locator(`[data-partner-id="${domadoo.id}"]`);
  await domadooRow.locator('[data-partner-action="edit"]').click();
  await page.waitForFunction(()=>document.getElementById('partner-preview').textContent==='https://domadoo.fr/?domid=117');
  await page.fill('#partner-form [name="code"]','CUSTOM');await page.fill('#partner-form [name="domains"]','DOMADOO.fr\nautre.example');
  await page.fill('#partner-form [name="template"]','https://redirect.example/{code}?target={url}');await page.fill('#partner-form [name="test_url"]','https://shop.example/produit?x=1#fiche');
  const finalUrl='https://redirect.example/CUSTOM?target=https://shop.example/produit%3Fx%3D1%23fiche';
  await page.waitForFunction(url=>document.getElementById('partner-preview-link').getAttribute('href')===url,finalUrl);
  const popupPromise=context.waitForEvent('page');await page.click('#partner-preview-link');const popup=await popupPromise;await popup.waitForLoadState();assert.equal(popup.url(),finalUrl);assert.equal(new URL(popup.url()).searchParams.get('target'),'https://shop.example/produit?x=1#fiche');assert.equal(new URL(popup.url()).hash,'');assert.equal(await popup.evaluate(()=>window.opener),null);await popup.close();
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:900});for(const theme of ['light','dark']){await page.selectOption('#theme-select',theme);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert(await page.locator('#partner-form [type="submit"]').isVisible());if(process.env.UI_SCREENSHOTS&&width!==320){await page.waitForTimeout(200);await page.screenshot({path:join(process.env.UI_SCREENSHOTS,`partners-${width}-${theme}.png`),fullPage:true});}}}
  await page.fill('#partner-form [name="template"]','javascript:alert(1)');await page.waitForFunction(()=>document.getElementById('partner-preview').textContent.includes('HTTP(S)'));assert(await page.locator('#partner-preview-link').isHidden());
  await page.fill('#partner-form [name="template"]','https://redirect.example/{code}?target={url}');await page.click('#partner-form [type="submit"]');await page.locator('#partner-dialog').waitFor({state:'hidden'});
  await page.reload();await page.locator('#chart svg').waitFor();await nav();
  const saved=(await api('/api/affiliate-partners')).items.find(row=>row.id===domadoo.id);assert.equal(saved.code,'CUSTOM');assert.deepEqual(saved.domains,['domadoo.fr','autre.example']);
  await page.click('#partner-add');await page.fill('#partner-form [name="name"]','Partenaire temporaire');await page.fill('#partner-form [name="code"]','FREE');await page.fill('#partner-form [name="template"]','{url}#{code}');await page.fill('#partner-form [name="test_url"]','https://shop.example/p');await page.waitForFunction(()=>document.getElementById('partner-preview').textContent==='https://shop.example/p#FREE');await page.click('#partner-form [type="submit"]');await page.locator('#partner-dialog').waitFor({state:'hidden'});
  const temporary=page.locator('[data-partner-id]').filter({hasText:'Partenaire temporaire'});await temporary.waitFor();await temporary.locator('[data-partner-action="delete"]').click();await temporary.waitFor({state:'hidden'});
  execFileSync(python,['-c',"import sqlite3,sys;db=sqlite3.connect(sys.argv[1]);db.execute('INSERT INTO tracked_link_partners(link_id,partner_id) VALUES(?,?)',(sys.argv[2],sys.argv[3]));db.commit()",db,existing.id,domadoo.id]);
  await page.evaluate(()=>LinksTracking.loadPartners());assert(await domadooRow.locator('[data-partner-action="delete"]').isDisabled());
  const after=await api('/api/tracked-links');assert.equal(after.items[0].url,before.items[0].url);assert.equal(after.items[0].clicks,before.items[0].clicks);assert.equal(after.items[0].partner_id,domadoo.id);assert.equal(await page.locator('#tracked-form [name="partner_id"]').count(),1);assert.deepEqual(errors,[]);
  console.log('PASS: initial partners, dynamic literal preview/manual link, CRUD, persistence, association protection, responsive themes, direct affiliate URLs unchanged.');
 }finally{await browser?.close();const exited=new Promise(resolve=>server.once('exit',resolve));server.kill();await exited;rmSync(temp,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1});
