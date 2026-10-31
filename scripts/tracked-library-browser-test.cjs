// Real library journey on a disposable database, including old published URLs.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {mkdtempSync,rmSync}=require('node:fs');
const {tmpdir}=require('node:os');
const {join,resolve}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-library-')),origin='http://127.0.0.1:8081',publicOrigin='http://127.0.0.1:3003';
 const python=process.env.PYTHON_PATH||'python3';
 execFileSync(python,[resolve(__dirname,'fixtures.py'),join(temp,'stats.db'),publicOrigin]);
 const legacyCategory='Classement historique unique',legacyId='1'.repeat(32);
 // Only this disposable test database is given an old column before server startup.
 execFileSync(python,['-c',"import sqlite3,sys;db=sqlite3.connect(sys.argv[1]);db.execute(\"ALTER TABLE tracked_links ADD COLUMN category TEXT NOT NULL DEFAULT ''\");db.execute(\"INSERT INTO tracked_links(id,name,url,notes,created_at,updated_at,category) VALUES(?,?,?,?,?,?,?)\",(sys.argv[2],'Lien historique','https://example.com/old','Référence durable','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z',sys.argv[3]));db.commit();db.close()",join(temp,'stats.db'),legacyId,legacyCategory]);
 const server=spawn(python,[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:'ignore'});
 let browser;
 const api=async(path,data)=>{const response=await fetch(origin+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(response.ok,await response.clone().text());return response.json()};
 try{
  for(let i=0;i<100;i++){try{if((await fetch(origin+'/healthz')).ok)break}catch{}await new Promise(r=>setTimeout(r,100));}
  await api('/api/content',{type:'promo',title:'Campagne conservée',internal_name:'Campagne conservée',url:'https://example.com/campaign'});
  const existing=(await api('/api/tracked-links')).items.find(row=>row.id===legacyId);assert(existing,'Startup keeps the old link');
  assert.equal(Object.hasOwn(existing,'category'),false);
  const sources=await api('/api/tracking-sources'),source=sources.items.find(row=>row.active);
  const token=await api(`/api/tracked-links/${existing.id}/token`,{source_id:source.id});
  const redirect=async path=>{const response=await fetch(publicOrigin+path,{redirect:'manual'});assert.equal(response.status,302);return response.headers.get('location')};
  const shortPath=new URL(token.url).pathname,legacyPath='/go/'+token.token;
  assert.equal(await redirect(legacyPath),'https://example.com/old');
  const history=(await api('/api/tracked-links')).items.find(row=>row.id===existing.id);
  const publicBefore=await fetch(publicOrigin+'/api/public-config').then(r=>r.json());
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
  const context=await browser.newContext({viewport:{width:1600,height:1000}});
  await context.route('**/api/tracked-links/*/check-destination',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({status:'valid',http_status:200})}));
  await context.route('https://example.com/**',route=>route.fulfill({body:'Destination de test'}));
  await context.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:async value=>{window.copiedLink=value}}}));
  const page=await context.newPage(),errors=[],writes=[];page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{if(['POST','PUT'].includes(request.method())&&/\/api\/tracked-links(?:\/[a-f0-9]{32})?$/.test(new URL(request.url()).pathname))writes.push(request.postDataJSON())});
  page.on('dialog',dialog=>dialog.accept());
  await page.goto(origin);await page.locator('#chart svg').waitFor();
  const nav=async id=>{if(await page.locator('#menu-toggle').isVisible())await page.locator('#menu-toggle').click();await page.locator(`[data-tab="${id}"]`).click();await page.locator(`#${id}.active`).waitFor()};
  const checkEditor=async stage=>{
   assert.equal(await page.locator('#tracked-form [name="category"]').count(),0);
   assert.equal(await page.locator('#tracked-form [name="name"]').evaluate(input=>input.required&&input.maxLength===160),true);
   for(const width of [1600,390]){await page.setViewportSize({width,height:900});for(const theme of ['light','dark']){
    await page.selectOption('#theme-select',theme);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${stage} overflow at ${width}px`);
    assert(await page.locator('#tracked-dialog').evaluate(dialog=>dialog.scrollWidth<=dialog.clientWidth),`${stage} dialog overflow at ${width}px`);
    if(process.env.UI_SCREENSHOTS)await page.screenshot({path:join(process.env.UI_SCREENSHOTS,`${stage}-${width}-${theme}.png`),fullPage:true,animations:'disabled'});
   }}
   await page.setViewportSize({width:1600,height:1000});await page.selectOption('#theme-select','light');
  };
  await nav('tracked-links');const row=page.locator(`[data-tracked-id="${existing.id}"]`);await row.waitFor();
  assert.equal(await page.locator('#tracked-category,#tracked-form [name="category"]').count(),0);
  assert(!/catégorie/i.test(await page.locator('#tracked-search').getAttribute('placeholder')));
  assert(!(await row.textContent()).includes(legacyCategory));
  assert.match(await row.textContent(),new RegExp(`${history.clicks} clic`));
  for(const query of ['historique','example.com/old','durable']){await page.fill('#tracked-search',query);assert(await row.isVisible());}
  await page.fill('#tracked-search',legacyCategory);assert.equal(await page.locator('#tracked-list .tracked-item').count(),0,'Old classifications do not participate in search');
  await page.fill('#tracked-search','absent');assert.equal(await page.locator('#tracked-list .tracked-item').count(),0);await page.fill('#tracked-search','');
  await row.locator('[data-tracked-action="copy"]').click();await page.waitForFunction(()=>window.copiedLink);assert.equal(await page.evaluate(()=>window.copiedLink),token.url);
  // A slow refresh must never expose the previous destination after saving.
  await page.route('**/api/tracked-links',async route=>{if(route.request().method()==='GET')await new Promise(resolve=>setTimeout(resolve,300));await route.continue()});
  await row.locator('[data-tracked-action="edit"]').click();
  await page.locator('#tracked-dialog').waitFor({state:'visible'});
  assert.equal(await page.locator('#tracked-form [name="name"]').inputValue(),'Lien historique');assert.equal(await page.locator('#tracked-form [name="notes"]').inputValue(),'Référence durable');
  await page.waitForFunction(()=>!document.querySelector('#tracked-form [type="submit"]').disabled);await checkEditor('edit');
  await page.fill('#tracked-form [name="url"]','https://example.com/new');await page.click('#tracked-form [type="submit"]');await page.locator('#tracked-dialog').waitFor({state:'hidden'});
  const popupPromise=context.waitForEvent('page');await row.locator('[data-tracked-action="open"]').click();const popup=await popupPromise;await popup.waitForLoadState();assert.equal(popup.url(),'https://example.com/new');assert.equal(await popup.evaluate(()=>window.opener),null);await popup.close();
  await page.unroute('**/api/tracked-links');
  assert.equal((await api('/api/tracked-links')).items.find(item=>item.id===existing.id).clicks,history.clicks,'Preview must not count clicks');
  assert.equal(execFileSync(python,['-c',"import sqlite3,sys;db=sqlite3.connect(sys.argv[1]);assert 'category' not in {row[1] for row in db.execute('PRAGMA table_info(tracked_links)')};print('absent');db.close()",join(temp,'stats.db')],{encoding:'utf8'}).trim(),'absent','Startup and edits do not retain or recreate the category column');
  assert.equal(await redirect(shortPath),'https://example.com/new');assert.equal(await redirect(legacyPath),'https://example.com/new');
  assert.equal((await api(`/api/tracked-links/${existing.id}/token`,{source_id:source.id})).url,token.url);
  await row.locator('[data-tracked-action="disable"]').click();await page.waitForFunction(()=>document.querySelector('[data-tracked-action="enable"]'));await page.selectOption('#tracked-status','active');assert.equal(await page.locator('#tracked-list .tracked-item').count(),0);await page.selectOption('#tracked-status','disabled');assert(await row.isVisible());
  await row.locator('[data-tracked-action="enable"]').click();await row.waitFor({state:'hidden'});await page.selectOption('#tracked-status','current');await row.waitFor();
  await row.locator('[data-tracked-action="archive"]').click();await row.waitFor({state:'hidden'});await page.selectOption('#tracked-status','archived');await row.waitFor();assert.equal(await redirect(shortPath),'https://example.com/new');
  await row.locator('[data-tracked-action="restore"]').click();await row.waitFor({state:'hidden'});await page.selectOption('#tracked-status','current');await row.waitFor();
  await page.click('#tracked-manage-sources');await page.fill('#tracked-source-form [name="name"]','Newsletter test');await page.click('#tracked-source-form [type="submit"]');
  const sourceRow=page.locator('[data-source-id]').filter({has:page.locator('input[value="Newsletter test"]')});await sourceRow.waitFor();
  await sourceRow.locator('input').fill('Newsletter renommée');await sourceRow.locator('[data-source-action="rename"]').click();await page.locator('input[value="Newsletter renommée"]').waitFor();await page.click('[data-close-sources]');
  await row.locator('select').selectOption({label:'Newsletter renommée'});await row.locator('[data-tracked-action="copy"]').click();await page.waitForFunction(old=>window.copiedLink!==old,token.url);const secondUrl=await page.evaluate(()=>window.copiedLink);
  await page.click('#tracked-manage-sources');const usedSource=page.locator('[data-source-id]').filter({has:page.locator('input[value="Newsletter renommée"]')});await usedSource.locator('[data-source-action="remove"]').click();await usedSource.locator('[data-source-action="restore"]').waitFor();assert.equal(await redirect(new URL(secondUrl).pathname),'https://example.com/new');await usedSource.locator('[data-source-action="restore"]').click();await usedSource.locator('[data-source-action="remove"]').waitFor();await page.click('[data-close-sources]');
  await page.click('[data-action="new-tracked"]');await page.locator('#tracked-dialog').waitFor({state:'visible'});assert.equal(await page.locator('#tracked-form [name="url"]').evaluate(input=>input===document.activeElement),true);
  await page.fill('#tracked-form [name="url"]','https://example.com/created');await page.waitForFunction(()=>!document.querySelector('#tracked-form [type="submit"]').disabled);
  const beforeInvalid=writes.length;await page.click('#tracked-form [type="submit"]');assert.equal(writes.length,beforeInvalid);assert(await page.locator('#tracked-dialog').isVisible());assert.equal(await page.locator('#tracked-form').evaluate(form=>form.checkValidity()),false);
  await page.fill('#tracked-form [name="name"]','Nouveau lien');await checkEditor('create');
  await page.locator('#tracked-form [name="notes"]').focus();await page.keyboard.press('Tab');assert.equal(await page.locator('#tracked-form .dialog-actions [data-close-tracked]').evaluate(button=>button===document.activeElement),true);
  await page.keyboard.press('Tab');assert.equal(await page.locator('#tracked-form [type="submit"]').evaluate(button=>button===document.activeElement),true);
  await page.click('#tracked-form [type="submit"]');await page.locator('#tracked-dialog').waitFor({state:'hidden'});
  assert.equal(await page.locator('#tracked-list .tracked-item').count(),2);await page.fill('#tracked-search','Nouveau lien');assert.match(await page.locator('#tracked-list .tracked-item').textContent(),/Nouveau lien/);await page.fill('#tracked-search','');
  for(const width of [1600,768,390,320]){await page.setViewportSize({width,height:900});for(const theme of ['light','dark']){await page.selectOption('#theme-select',theme);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Overflow at ${width}px`);if(process.env.UI_SCREENSHOTS&&(width===1600||width===390))await page.screenshot({path:join(process.env.UI_SCREENSHOTS,`library-${width}-${theme}.png`),fullPage:true,animations:'disabled'});}}
  await nav('content');assert.equal(await page.locator('#content [data-action="new-tracked"],#content #tracked-list').count(),0);await nav('campaigns');assert(await page.locator('[data-action="new-campaign"]').isVisible());await page.locator('.share-picker select').first().waitFor();assert(await page.locator('.share-picker select').first().locator('option').filter({hasText:'Newsletter renommée'}).count());
  await nav('tracked-links');await row.waitFor();await row.locator('[data-open-statistics]').click();await page.locator('#statistics.active').waitFor();assert.equal(await page.inputValue('#analysis-search'),'Lien historique');
  for(let i=0;i<20;i++)await api('/api/tracked-links',{name:'Pagination '+i,url:'https://example.com/'+i});
  await nav('tracked-links');await page.locator('#tracked-list .collection-pagination').waitFor();assert.equal(await page.locator('#tracked-list .tracked-item').count(),20);await page.getByRole('button',{name:'Suivant',exact:true}).click();assert.equal(await page.locator('#tracked-list .tracked-item').count(),2);
  assert.deepEqual(await fetch(publicOrigin+'/api/public-config').then(r=>r.json()),publicBefore);assert.deepEqual(errors,[]);
  assert(writes.length>=2);assert(writes.every(fields=>!Object.hasOwn(fields,'category')),'Browser writes do not send a category');
  console.log('PASS: migrated historical link, physically absent category column, category-free library and forms, required name and keyboard focus, CRUD, status/search/pagination, copy/open, source lifecycle, old/short URLs and counters, campaigns, statistics access, desktop/mobile light/dark.');
 }finally{if(browser)await browser.close();const exited=new Promise(resolve=>server.once('exit',resolve));server.kill();await exited;rmSync(temp,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1});
