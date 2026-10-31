// End-to-end task paths on disposable data. Never touches a deployed instance.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {mkdtempSync,rmSync,mkdirSync}=require('node:fs');
const {tmpdir}=require('node:os'),{join,resolve}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-ergonomics-')),python=process.env.PYTHON_PATH||'python3',origin='http://127.0.0.1:8081',db=join(temp,'stats.db');
 execFileSync(python,[resolve(__dirname,'fixtures.py'),db]);
 const server=spawn(python,[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:db,UPLOAD_DIR:join(temp,'uploads')},stdio:'ignore'});let browser;
 const api=async(path,body)=>{const response=await fetch(origin+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:body?JSON.stringify(body):undefined});assert(response.ok);return response.status===204?null:response.json()};
 try{
  for(let i=0;i<100;i++){try{if((await fetch(origin+'/healthz')).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
  const campaign=await api('/api/content',{type:'promo',internal_name:'Campagne repère',title:'Campagne repère',url:'https://example.com/offer',permanent:true});
  await api('/api/tracked-links',{name:'Lien repère',url:'https://example.com/reference'});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await context.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copiedLink=text}}}));
  await page.route('**/api/tracked-links/*/check-destination',route=>route.fulfill({json:{status:'valid',http_status:200}}));
  await page.route('**/api/tracked-links/title-preview',route=>route.fulfill({json:{status:'ok',title:'Titre proposé'}}));
  await page.goto(origin);await page.locator('#chart svg').waitFor();
  const publicBefore=await fetch('http://127.0.0.1:3003/api/public-config').then(r=>r.json());
  const nav=async id=>{if(await page.locator('#menu-toggle').isVisible())await page.locator('#menu-toggle').click();await page.locator(`[data-tab="${id}"]`).click();await page.locator(`#${id}.active`).waitFor()};
  assert.deepEqual(await page.locator('.nav-group').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('aria-label'))),['Analyser','Gérer les liens','Composer la page','Administrer']);
  await page.locator('[data-quick-create="tracked"]').click();await page.locator('#tracked-dialog[open]').waitFor();assert.equal(await page.evaluate(()=>document.activeElement.name),'url');
  await page.locator('#tracked-form [name=url]').fill('https://example.com/new');await page.waitForFunction(()=>document.querySelector('#tracked-form [name=name]').value==='Titre proposé');
  await page.locator('#tracked-form [name=name]').fill('Lien créé depuis l’accueil');await page.locator('#tracked-form button[type=submit]').click();
  await page.locator('#tracked-saved:visible').waitFor();assert(await page.locator('#tracked-links.active').isVisible());
  await page.selectOption('#tracked-saved-source',{label:'YouTube'});await page.locator('#tracked-saved-copy').click();await page.waitForFunction(()=>Boolean(window.copiedLink));
  const copied=await page.evaluate(()=>window.copiedLink);assert.equal(new URL(copied).origin,"https://links.example");assert.match(new URL(copied).pathname,/^\/[A-Za-z0-9_-]+$/);
  const redirect=await fetch('http://127.0.0.1:3003'+new URL(copied).pathname,{redirect:'manual'});assert.equal(redirect.status,302);assert.equal(redirect.headers.get('location'),'https://example.com/new');
  await page.locator('[data-management-jump="tracked-links-partners"]').click();assert.equal(await page.evaluate(()=>document.activeElement.id),'tracked-links-partners-heading');
  await nav('dashboard');await page.locator(`[data-edit-campaign="${campaign.id}"]`).click();await page.locator('#block-dialog[open]').waitFor();assert.equal(await page.locator('#block-form [name=title]').inputValue(),'Campagne repère');await page.keyboard.press('Escape');
  await nav('campaigns');const order=await page.evaluate(()=>document.querySelector('#campaigns-list').getBoundingClientRect().top<document.querySelector('#campaign-planning').getBoundingClientRect().top);assert(order);
  await page.locator('[data-management-jump="campaign-planning"]').click();assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Planning des promotions');
  await nav('statistics');await page.locator('#chart svg').waitFor();assert(await page.locator('#analysis-search').isVisible());assert(await page.locator('#statistics-filter-context').isVisible());
  await page.locator('[data-metric-scope=tracked]').click();assert.equal(await page.locator('#analysis-scope').inputValue(),'tracked');assert.equal(await page.locator('#daily-category').inputValue(),'tracked');
  await page.locator('.daily-inspect-action').click();assert.equal(await page.evaluate(()=>document.activeElement.id),'daily-detail-title');
  await page.locator('[data-statistics-jump=statistics-partners]').click();assert(await page.locator('#statistics-partners').getAttribute('open')!==null);
  await page.fill('#analysis-search','introuvable');await page.locator('#analysis-reset').click();assert.equal(await page.locator('#analysis-search').inputValue(),'');
  const totals=await page.locator('.statistics-kpis strong').allTextContents();
  const directory=process.env.ERGONOMICS_SCREENSHOTS;if(directory)mkdirSync(directory,{recursive:true});
  for(const width of [320,360,390,768,1024,1440]){
   await page.setViewportSize({width,height:1000});
   for(const theme of ['light','dark']){
    await page.selectOption('#theme-select',theme);
    for(const id of ['dashboard','statistics','tracked-links','campaigns','permanent-links','content','buttons','appearance','archives','settings']){
     await nav(id);await page.waitForTimeout(80);
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${id} overflow ${width} ${theme}`);
     assert.equal(await page.locator('.tabs [aria-current=page]').getAttribute('data-tab'),id);
     if(width<761&&['statistics','tracked-links','campaigns'].includes(id))assert.equal(await page.locator('.mobile-shortcuts [aria-current=page]').getAttribute('data-mobile-view'),id);
     if(directory&&[390,1440].includes(width)&&['dashboard','statistics','tracked-links','campaigns','content','settings'].includes(id))await page.screenshot({path:join(directory,`${id}-${width}-${theme}.png`),fullPage:true,animations:'disabled'});
    }
   }
  }
  await page.setViewportSize({width:360,height:800});await page.locator('[data-mobile-view=statistics]').click();assert(await page.locator('#statistics.active').isVisible());assert.deepEqual(await page.locator('.statistics-kpis strong').allTextContents(),totals);
  await page.emulateMedia({reducedMotion:'reduce'});await page.locator('[data-mobile-view=tracked-links]').focus();await page.keyboard.press('Enter');assert(await page.locator('#tracked-links.active').isVisible());
  await page.selectOption('#theme-select','system');await page.reload();assert.equal(await page.locator('#theme-select').inputValue(),'system');
  assert.deepEqual(await fetch('http://127.0.0.1:3003/api/public-config').then(r=>r.json()),publicBefore,'navigation and tracked creation preserve public configuration');
  assert.deepEqual(errors,[]);console.log('PASS ergonomics: direct creation/copy, metric/day navigation, campaign sheet, partners, 6 widths × 2 themes × 10 views, public data unchanged');
 }finally{if(browser)await browser.close();server.kill();await new Promise(r=>server.once('exit',r));rmSync(temp,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exit(1)});
