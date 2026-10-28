// Real campaign affiliation and duplicate reuse; disposable data, no external shops.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process'),{mkdtempSync,rmSync}=require('node:fs');
const {tmpdir}=require('node:os'),{join,resolve}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-campaign-affiliation-')),origin='http://127.0.0.1:8081',publicOrigin='http://127.0.0.1:3003',python=process.env.PYTHON_PATH||'python3';let browser;
 execFileSync(python,[resolve(__dirname,'fixtures.py'),join(temp,'stats.db'),publicOrigin]);
 const backend=spawn(python,[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:'ignore'});
 const api=async(path,data,method=data?'POST':'GET')=>{const r=await fetch(origin+path,{method,headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(r.ok,await r.clone().text());return r.status===204?null:r.json()};
 const metric=async id=>{const response=await fetch(publicOrigin+'/metrics',{method:'POST',headers:{Origin:publicOrigin,'Content-Type':'application/json','User-Agent':'Mozilla/5.0'},body:JSON.stringify({kind:'click',link:'block:'+id,source:'youtube'})});assert.equal(response.status,204)};
 const head=async url=>{const response=await fetch(publicOrigin+new URL(url).pathname,{method:'HEAD',redirect:'manual'});assert.equal(response.status,302);return response.headers.get('location')};
 try{
  for(let i=0;i<100;i++){try{if((await fetch(origin+'/healthz')).ok)break}catch{}await new Promise(r=>setTimeout(r,100));if(i===99)throw Error('Backend did not start')}
  const configured=(await api('/api/affiliate-partners')).items,reolink=configured.find(x=>x.name==='Reolink'),domadoo=configured.find(x=>x.name==='Domadoo'),sanyipace=configured.find(x=>x.name==='Sanyipace');
  const legacyUrl='https://www.domadoo.fr/history?domid=custom#keep';
  const legacy=await api('/api/content',{type:'featured',title:'Offre historique',internal_name:'Repère historique conservé',url:legacyUrl});await metric(legacy.id);
  const legacyAlias=await api('/api/content/'+legacy.id+'/story-link',{source:'youtube'});
  const duplicateTracked=await api('/api/tracked-links',{name:'Lien suivi existant',url:'https://shop.reolink.com/duplicate?aff=1404#spec'});
  const source=(await api('/api/tracking-sources')).items[0];const trackedAlias=await api('/api/tracked-links/'+duplicateTracked.id+'/token',{source_id:source.id});
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}: {})});
  const context=await browser.newContext({viewport:{width:1440,height:1100},permissions:['clipboard-read','clipboard-write'],reducedMotion:'reduce'});
  for(const domain of ['shop.reolink.com','eu.sanyipacetoilet.com','www.domadoo.fr'])await context.route('https://'+domain+'/**',route=>route.fulfill({contentType:'text/html',body:'<title>Destination de test</title>'}));
  const page=await context.newPage(),errors=[],confirmations=[];let approve=true;
  page.on('pageerror',error=>errors.push(error.message));page.on('dialog',async dialog=>{confirmations.push(dialog.message());approve?await dialog.accept():await dialog.dismiss()});
  const fields=page.locator('#block-form'),final=page.locator('#campaign-final-link');
  const preview=async url=>page.waitForFunction(expected=>document.getElementById('campaign-final-link').getAttribute('href')===expected,url);
  const save=async()=>{await fields.locator('button[value=default]').click();await page.waitForFunction(()=>!document.getElementById('block-dialog').open)};
  const content=async()=>{if(await page.locator('#menu-toggle').isVisible())await page.locator('#menu-toggle').click();await page.locator('[data-tab=content]').click()};
  await page.goto(origin);await page.locator('#chart svg').waitFor();await content();await page.locator('[data-action=new-campaign]').click();
  await fields.locator('[name=title]').fill('Caméra affiliée');await fields.locator('[name=url]').fill('https://shop.reolink.com/product?x=1#details');
  await preview('https://shop.reolink.com/product?x=1&aff=1404#details');assert.equal(await page.locator('#campaign-partner').inputValue(),reolink.id);
  await page.route('**/api/content/preview',async route=>{if(route.request().postDataJSON().url.includes('/slow'))await new Promise(r=>setTimeout(r,300));await route.continue()});
  const slowResponse=page.waitForResponse(r=>r.url().endsWith('/api/content/preview')&&r.request().postDataJSON().url.includes('/slow'));
  const slowRequest=page.waitForRequest(r=>r.url().endsWith('/api/content/preview')&&r.postDataJSON().url.includes('/slow'));
  await fields.locator('[name=url]').fill('https://shop.reolink.com/slow');await slowRequest;
  await fields.locator('[name=url]').fill('https://eu.sanyipacetoilet.com/latest');await preview('https://eu.sanyipacetoilet.com/latest?ref=DomotiK');assert.equal(await page.locator('#campaign-partner').inputValue(),sanyipace.id);await slowResponse;await page.unroute('**/api/content/preview');
  await page.selectOption('#campaign-partner',domadoo.id);await preview('https://eu.sanyipacetoilet.com/latest?domid=117');
  await page.selectOption('#campaign-partner','');await fields.locator('[name=url]').fill('https://shop.reolink.com/none');await preview('https://shop.reolink.com/none');assert.equal(await page.locator('#campaign-partner').inputValue(),'');
  const original='https://shop.reolink.com/p?aff=OLD&x=a%2Bb#details',destination='https://shop.reolink.com/p?x=a%2Bb&aff=1404#details';
  await page.selectOption('#campaign-partner',reolink.id);await fields.locator('[name=url]').fill(original);await preview(destination);
  const popupPromise=context.waitForEvent('page');await final.click();const popup=await popupPromise;await popup.waitForLoadState();assert.equal(popup.url(),destination);assert.equal(await popup.evaluate(()=>window.opener),null);await popup.close();
  await save();let saved=(await api('/api/content')).items.find(x=>x.title==='Caméra affiliée');assert.equal(saved.original_url,original);assert.equal(saved.url,destination);assert.equal(saved.partner_id,reolink.id);
  const alias=await api('/api/content/'+saved.id+'/story-link',{source:'youtube'});await metric(saved.id);assert.equal(await head(alias.url),destination);
  await api('/api/affiliate-partners/'+reolink.id,{...reolink,code:'UPDATED'},'PUT');
  await page.locator(`[data-id="${saved.id}"] [data-action=edit]`).click();await preview(destination);assert.equal(await fields.locator('[name=url]').inputValue(),original);
  await fields.locator('[name=description]').fill('Description modifiée, destination conservée');await save();assert.equal(await head(alias.url),destination);assert.equal(confirmations.length,0);
  await page.locator(`[data-id="${saved.id}"] [data-action=edit]`).click();await page.locator('#campaign-recalculate').click();const updated='https://shop.reolink.com/p?x=a%2Bb&aff=UPDATED#details';await preview(updated);
  approve=false;await fields.locator('button[value=default]').click();await page.waitForFunction(()=>document.getElementById('campaign-final-link').getAttribute('href')?.includes('UPDATED'));assert(await page.locator('#block-dialog').isVisible());assert.equal(await head(alias.url),destination);
  approve=true;await save();assert.equal(await head(alias.url),updated);assert.deepEqual(await api('/api/content/'+saved.id+'/story-link',{source:'youtube'}),alias);
  await page.locator(`[data-id="${saved.id}"] [data-action=edit]`).click();await page.selectOption('#campaign-partner','');await preview(original);await save();
  saved=(await api('/api/content')).items.find(x=>x.id===saved.id);assert.equal(saved.url,original);assert.equal(saved.partner_id,'');assert.equal(saved.clicks,1);
  await page.locator(`[data-id="${legacy.id}"] [data-action=edit]`).click();await preview(legacyUrl);assert.equal(await page.locator('#campaign-partner').inputValue(),'');assert.equal(await fields.locator('[name=type]').inputValue(),'featured');
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});for(const theme of ['light','dark']){await page.selectOption('#theme-select',theme);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert(await page.locator('#block-dialog').evaluate(n=>n.scrollWidth<=n.clientWidth))}}
  await page.setViewportSize({width:1440,height:1100});await fields.locator('[name=description]').fill('Conserver l’ancien lien');await save();assert.equal(await head(legacyAlias.url),legacyUrl);
  const retained=(await api('/api/content')).items.find(x=>x.id===legacy.id);assert.equal(retained.internal_name,'Repère historique conservé');assert.equal(retained.clicks,1);
  const reusable=await api('/api/content',{type:'promo',title:'Campagne à réutiliser',url:'https://shop.reolink.com/dupcampaign?aff=UPDATED'});await metric(reusable.id);
  const reusableAlias=await api('/api/content/'+reusable.id+'/story-link',{source:'youtube'}),beforeCount=(await api('/api/content')).items.length;
  await page.locator('[data-action=new-campaign]').click();await fields.locator('[name=title]').fill('Doublon évité');await fields.locator('[name=url]').fill('https://shop.reolink.com/dupcampaign');await preview('https://shop.reolink.com/dupcampaign?aff=UPDATED');
  await page.locator(`[data-reuse-campaign="${reusable.id}"]`).click();await page.waitForFunction(id=>document.querySelector('#block-form [name=id]').value===id,reusable.id);assert.equal(await fields.locator('[name=id]').inputValue(),reusable.id);await fields.locator('[name=title]').fill('Campagne réutilisée');await save();
  assert.equal((await api('/api/content')).items.length,beforeCount);assert.equal((await api('/api/content')).items.find(x=>x.id===reusable.id).clicks,1);assert.deepEqual(await api('/api/content/'+reusable.id+'/story-link',{source:'youtube'}),reusableAlias);
  await page.locator('[data-action=new-campaign]').click();await fields.locator('[name=url]').fill(duplicateTracked.url);await page.selectOption('#campaign-partner','');await preview(duplicateTracked.url);
  const beforeTracked=(await api('/api/tracked-links')).items;
  await page.locator(`[data-reuse-tracked="${duplicateTracked.id}"]`).click();await page.locator('#tracked-reuse-dialog[open]').waitFor();await page.selectOption('#tracked-reuse-source',source.id);await page.locator('#tracked-reuse-copy').click();
  await page.waitForFunction(expected=>document.getElementById('tracked-reuse-url').getAttribute('href')===expected,trackedAlias.url);
  assert.equal((await api('/api/tracked-links')).items.length,beforeTracked.length);assert.equal((await api('/api/tracked-links')).items.find(x=>x.id===duplicateTracked.id).clicks,beforeTracked.find(x=>x.id===duplicateTracked.id).clicks);
  assert.deepEqual(errors,[]);
  console.log('PASS campaign affiliation: detection/manual/None, final URL popup, preserved legacy and rule changes, explicit replacement/cancel, stable counters/aliases, campaign and tracked-link reuse, responsive themes');
 }finally{if(browser)await browser.close();backend.kill();await new Promise(r=>backend.exitCode!==null?r():backend.once('exit',r));rmSync(temp,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exitCode=1});
