// Exercise the real admin with a disposable database; never use production data.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { spawn, execFileSync } = require('node:child_process');
const { mkdtempSync, rmSync, mkdirSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join, resolve } = require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-admin-'));
 const origin='http://127.0.0.1:8081';
 const server=spawn(process.env.PYTHON_PATH||'python3',[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:'inherit'});
 let browser;
 const request=async(path,data,method='POST')=>{const r=await fetch(origin+path,{method,headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});if(!r.ok)throw Error(await r.text());return r.status===204?null:r.json()};
 try{
  for(let i=0;i<100;i++){try{if((await fetch(origin+'/healthz')).ok)break}catch{}await new Promise(r=>setTimeout(r,100));if(i===99)throw Error('Backend did not start')}
  execFileSync(process.env.PYTHON_PATH||'python3',['-c',"import sqlite3,sys;from datetime import datetime,timedelta;from zoneinfo import ZoneInfo;db=sqlite3.connect(sys.argv[1]);today=datetime.now(ZoneInfo('Europe/Paris')).date();rows=[((today-timedelta(days=i)).isoformat(),'youtube',kind,link,total) for i in range(7) for kind,link,total in [('view','',80+i*23),('click','Amazon',30+i*8)]];db.executemany('INSERT INTO counts VALUES(?,?,?,?,?)',rows);db.commit()",join(temp,'stats.db')]);
  const longName='Campagne DomotiK Studio avec un nom très long pour contrôler la lisibilité et les actions sur mobile';
  const promo=await request('/api/content',{type:'promo',internal_name:longName,title:'Offre partenaire',promo_code:'DOMOTIK10',description:'Description historique conservée',badge:'Partenaire',cta:'CTA historique',url:'https://partner.example/offer',active:true});
  const other=await request('/api/content',{type:'classic',internal_name:'Guide Home Assistant',title:'Guide',url:'https://example.com/guide'});
  await request('/api/buttons',{icon:'youtube',label:'YouTube',url:'https://youtube.com/@DomotiKStudio'});
  const beforePublic=await fetch('http://127.0.0.1:3003/api/public-config').then(r=>r.json());
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox']}: {})});
  const context=await browser.newContext({colorScheme:'light'});
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin);await page.waitForSelector('.campaign-card');
  assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
  await page.selectOption('#theme-select','dark');await page.reload();
  assert.equal(await page.locator('#theme-select').inputValue(),'dark');assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
  await page.emulateMedia({colorScheme:'light'});assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
  await page.selectOption('#theme-select','system');await page.emulateMedia({colorScheme:'dark'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark');
  await page.emulateMedia({colorScheme:'light'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');
  await page.reload();assert.equal(await page.locator('#theme-select').inputValue(),'system');
  assert.deepEqual(await fetch('http://127.0.0.1:3003/api/public-config').then(r=>r.json()),beforePublic,'Admin theme changed public configuration');
  // A browser that refuses storage must still support theme selection.
  const noStorage=await browser.newContext();await noStorage.addInitScript(()=>{Storage.prototype.getItem=()=>{throw Error('blocked')};Storage.prototype.setItem=()=>{throw Error('blocked')}});
  const fallback=await noStorage.newPage();await fallback.goto(origin);await fallback.selectOption('#theme-select','dark');assert.equal(await fallback.locator('html').getAttribute('data-theme'),'dark');await noStorage.close();
  const nav=async id=>{if(await page.locator('#menu-toggle').isVisible())await page.locator('#menu-toggle').click();const endpoint={dashboard:'/api/stats',content:'/api/content',buttons:'/api/buttons',archives:'/api/content?archived=1',settings:'/api/settings'}[id];await Promise.all([page.waitForResponse(r=>r.url().includes(endpoint)&&r.status()===200),page.locator(`[data-tab="${id}"]`).click()]);await page.waitForSelector(`#${id}.active`)};
  const overflow=async()=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
  for(const width of [1440,1024,768,390,320]){
   await page.setViewportSize({width,height:1000});
   for(const theme of ['light','dark']){
    await page.selectOption('#theme-select',theme);
    for(const id of ['dashboard','content','buttons','archives','settings']){
     await nav(id);await overflow();
     if(id==='content'){
      await page.waitForSelector('#content-list .list-item');
      const item=page.locator(`[data-id="${promo.id}"]`);await item.locator('summary').click();assert(await item.locator('[data-action="duplicate"]').isVisible());
      await page.keyboard.press('Escape');assert.equal(await item.locator('details').getAttribute('open'),null);
      await item.locator('[data-action="edit"]').click();await page.waitForSelector('#block-dialog[open]');await overflow();
      const sizes=await page.locator('#block-dialog').evaluate(d=>({scroll:d.scrollWidth,client:d.clientWidth}));assert(sizes.scroll<=sizes.client,'Modal overflow');
      assert.equal(await page.locator('#block-form [name="internal_name"]').inputValue(),longName);
      await page.locator('#block-dialog .icon-button').click();
     }
     if(id==='buttons'){await page.locator('[data-action="new-button"]').click();assert(await page.locator('#button-dialog').isVisible());await overflow();await page.locator('#button-dialog .icon-button').click()}
    }
   }
  }
  await page.setViewportSize({width:1440,height:1000});await nav('content');
  const campaign=page.locator(`[data-id="${promo.id}"]`);
  await campaign.locator('[data-action="edit"]').click();
  for(const field of ['description','icon','badge','cta'])assert(await page.locator('#block-form [name="'+field+'"]').isHidden(),'Hidden promo field '+field);
  for(const field of ['internal_name','title','promo_code','url','start_at','end_at','active','draft','priority'])assert(await page.locator('#block-form [name="'+field+'"]').isVisible(),'Kept promo field '+field);
  const preview=page.frameLocator('#block-preview iframe');
  assert.equal(await preview.locator('.offer-title').textContent(),'Offre partenaire');
  assert((await preview.locator('.offer-code').textContent()).includes('DOMOTIK10'));
  await page.locator('#block-form [name="promo_code"]').fill('');
  await preview.locator('.offer-code').waitFor({state:'detached'});assert.equal(await preview.locator('.offer-code').count(),0);
  await page.locator('#block-form [name="promo_code"]').fill('DOMOTIK10');
  if(process.env.ADMIN_SCREENSHOTS){for(const width of [390,1440]){await page.setViewportSize({width,height:1000});await page.locator('#block-dialog').screenshot({path:join(process.env.ADMIN_SCREENSHOTS,'promo-editor-'+width+'.png')})}await page.setViewportSize({width:1440,height:1000})}
  await page.locator('#block-form [name="internal_name"]').fill('Promo renommée');
  await page.locator('#block-dialog button[value="default"]').click();await page.waitForFunction(()=>!document.getElementById('block-dialog').open);
  const kept=(await request('/api/content',undefined,'GET')).items.find(x=>x.id===promo.id);assert.equal(kept.title,'Offre partenaire');assert.equal(kept.promo_code,'DOMOTIK10');assert.equal(kept.description,'Description historique conservée');assert.equal(kept.cta,'CTA historique');assert.equal(kept.badge,'Partenaire');
  await page.locator('[data-action="new-block"]').click();await page.selectOption('#block-form [name="type"]','promo');
  await page.locator('#block-form [name="internal_name"]').fill('Nouvelle promo minimale');await page.locator('#block-form [name="url"]').fill('https://partner.example/new');await page.locator('#block-form [name="draft"]').check();
  await page.locator('#block-dialog button[value="default"]').click();await page.waitForFunction(()=>!document.getElementById('block-dialog').open);
  assert.equal((await request('/api/content',undefined,'GET')).items.find(x=>x.internal_name==='Nouvelle promo minimale').title,'Nouvelle promo minimale');
  const item=page.locator(`[data-id="${other.id}"]`);
  await item.locator('[data-action="edit"]').click();await page.locator('#block-form [name="title"]').fill('Guide mis à jour');await page.locator('#block-dialog button[value="default"]').click();await page.waitForFunction(()=>!document.getElementById('block-dialog').open);assert.equal((await request('/api/content',undefined,'GET')).items.find(x=>x.id===other.id).title,'Guide mis à jour');
  await item.locator('summary').click();await item.locator('[data-action="duplicate"]').click();await page.waitForFunction(()=>document.getElementById('notice').textContent==='Bloc dupliqué en brouillon.');
  const result=await request('/api/content',undefined,'GET');assert(result.items.some(x=>x.draft&&x.internal_name.includes('Guide')));
  await nav('buttons');await page.locator('[data-action="new-button"]').click();await page.locator('#button-form [name="label"]').fill('Site Studio');await page.locator('#button-form [name="url"]').fill('https://domotik-studio.fr');await page.locator('#button-dialog button[value="default"]').click();await page.waitForFunction(()=>!document.getElementById('button-dialog').open);const added=(await request('/api/buttons',undefined,'GET')).items.find(x=>x.label==='Site Studio');assert(added);
  const previousOrder=(await request('/api/buttons',undefined,'GET')).items.map(x=>x.id);await page.locator(`[data-id="${added.id}"] [data-action="up"]`).click();await page.waitForFunction(()=>document.getElementById('notice').textContent==='Nouvel ordre enregistré.');assert.equal((await request('/api/buttons',undefined,'GET')).items.findIndex(x=>x.id===added.id),previousOrder.indexOf(added.id)-1);
  await nav('settings');await page.locator('#settings-form [name="tagline"]').fill('Maison connectée');await page.locator('#settings-form button').click();await page.waitForFunction(()=>document.getElementById('notice').textContent==='Réglages enregistrés.');
  assert.equal((await request('/api/settings',undefined,'GET')).tagline,'Maison connectée');
  await nav('dashboard');await page.waitForSelector('#chart svg');await Promise.all([page.waitForResponse(r=>r.url().includes('/api/stats')&&r.status()===200),page.selectOption('#period','90')]);await page.waitForFunction(()=>document.querySelector('#chart svg')?.getAttribute('aria-label').includes('semaine'));await page.locator('.chart-bucket').first().focus();await page.keyboard.press('ArrowRight');assert.match(await page.locator('#chart-detail').textContent(),/visites/);
  const lum=hex=>{const clean=hex.trim().replace('#','');const c=(clean.length===3?clean.split('').map(x=>x+x).join(''):clean).match(/../g).map(x=>parseInt(x,16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722};
  for(const mode of ['light','dark']){await page.selectOption('#theme-select',mode);const colors=await page.evaluate(()=>{const css=getComputedStyle(document.documentElement);return Object.fromEntries(['text','muted','surface','bg','accent','accent-soft'].map(x=>[x,css.getPropertyValue('--'+x)]))});for(const [fg,bg] of [['text','surface'],['muted','surface'],['muted','bg'],['accent','accent-soft']]){const a=lum(colors[fg]),b=lum(colors[bg]);assert((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5,mode+' contrast '+fg+'/'+bg)}}
  const changedPublic=await fetch('http://127.0.0.1:3003/api/public-config').then(r=>r.json());assert.equal(changedPublic.theme,beforePublic.theme);
  assert.equal(await page.evaluate(()=>localStorage.getItem('theme')),null);
  assert.deepEqual(errors,[]);
  if(process.env.ADMIN_SCREENSHOTS){mkdirSync(process.env.ADMIN_SCREENSHOTS,{recursive:true});for(const theme of ['light','dark']){await page.selectOption('#theme-select',theme);await page.screenshot({animations:'disabled',path:join(process.env.ADMIN_SCREENSHOTS,`admin-${theme}.png`),fullPage:true})}await page.setViewportSize({width:390,height:844});await page.screenshot({animations:'disabled',path:join(process.env.ADMIN_SCREENSHOTS,'admin-mobile.png'),fullPage:true})}
  console.log('Admin themes, system changes, storage fallback, five viewport sizes, all views/modals, action menu, duplication, settings, chart keyboard and independent public config: OK');
 }finally{if(browser)await browser.close();server.kill();await new Promise(r=>server.exitCode!==null?r():server.once('exit',r));rmSync(temp,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
