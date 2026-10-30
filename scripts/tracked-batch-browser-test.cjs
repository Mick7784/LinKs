// E2E: batch creation, duplicate avoidance, partner changes, manual titles, mobile.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {mkdtempSync,rmSync}=require('node:fs');
const {tmpdir}=require('node:os');
const {join,resolve}=require('node:path');

(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-create-batch-'));
 const origin='http://127.0.0.1:8081',publicOrigin='http://127.0.0.1:3003';
 const python=process.env.PYTHON_PATH||'python3';
 execFileSync(python,[resolve(__dirname,'fixtures.py'),join(temp,'stats.db'),publicOrigin]);
 const server=spawn(python,[resolve(__dirname,'analytics.py')],{
  env:{...process.env,ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:'ignore'
 });
 let browser;
 const api=async(path,data)=>{
  const response=await fetch(origin+path,{
   method:data?'POST':'GET',
   headers:{'Content-Type':'application/json','X-Links-Request':'1'},
   body:data?JSON.stringify(data):undefined
  });
  assert(response.ok,await response.clone().text());
  return response.json();
 };
 try{
  let ready=false;
  for(let n=0;n<100;n++){
   try{if((await fetch(origin+'/healthz')).ok){ready=true;break}}catch{}
   await new Promise(done=>setTimeout(done,100));
  }
  assert(ready,'Disposable test server did not start');
  await api('/api/tracked-links',{name:'Existant à réutiliser',url:'https://example.com/existing'});
  const firstSnapshot=(await api('/api/tracked-links')).items;
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
  const context=await browser.newContext({viewport:{width:1440,height:900}});
  const page=await context.newPage(),errors=[];
  let metadataCalls=0,createCalls=0;
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{
   if(request.method()==='POST'&&new URL(request.url()).pathname==='/api/tracked-links/batch/create')createCalls++;
  });
  await context.route('**/api/tracked-links/title-preview',async route=>{
   metadataCalls++;
   const url=route.request().postDataJSON().url;
   let title='';
   if(url.includes('omvi-x16'))title='Reolink OMVI X16 PoE';
   if(url.includes('zigbee-module'))title='Module Zigbee Sonoff';
   await route.fulfill({status:200,contentType:'application/json',
    body:JSON.stringify({status:title?'ok':'unavailable',title,source:title?'open_graph':''})});
  });
  await page.goto(origin);await page.locator('#chart svg').waitFor();
  if(await page.locator('#menu-toggle').isVisible())await page.locator('#menu-toggle').click();
  await page.locator('[data-tab="tracked-links"]').click();
  await page.locator('#tracked-links.active').waitFor();
  await page.locator('#tracked-open-batch').click();
  const dialog=page.locator('#tracked-batch-dialog');
  await dialog.waitFor({state:'visible'});
  assert.equal(await dialog.getByText('Plateforme de partage').count(),0);
  const urls=['https://example.com/existing',
    'https://shop.reolink.com/products/omvi-x16',
    'https://www.domadoo.fr/products/zigbee-module',
    'https://shop.reolink.com/products/omvi-x16'];
  await page.locator('#tracked-batch-urls').fill(urls.join('\n'));
  await page.locator('#tracked-batch-analyze').click();
  await page.waitForFunction(()=>{
   const root=document.querySelector('#tracked-batch-dialog');
   return root&&root.querySelectorAll('.tracked-batch-row').length===4&&
    root.querySelector('#tracked-batch-analyze').disabled===false&&
    root.querySelector('#tracked-batch-progress').textContent.includes('prêts à créer');
  });
  assert.equal(await page.locator('.tracked-batch-row').count(),4);
  assert.equal(metadataCalls,2,'Only new unique destinations should be fetched for titles');
  assert.equal(createCalls,0,'Preview does not create tracked links');
  assert.deepEqual((await api('/api/tracked-links')).items,firstSnapshot);
  const existing=page.locator('.tracked-batch-row[data-index="0"]');
  const reolink=page.locator('.tracked-batch-row[data-index="1"]');
  const domadoo=page.locator('.tracked-batch-row[data-index="2"]');
  const repeated=page.locator('.tracked-batch-row[data-index="3"]');
  assert.match(await existing.locator('.tracked-batch-row-status').textContent(),/Déjà suivi/);
  assert.match(await repeated.locator('.tracked-batch-row-status').textContent(),/Doublon de la ligne 2/);
  assert(await existing.locator('input[type="checkbox"]').isDisabled());
  assert(await repeated.locator('input[type="checkbox"]').isDisabled());
  assert.match(await reolink.locator('.tracked-batch-destination').textContent(),/aff=1404/);
  assert.match(await domadoo.locator('.tracked-batch-destination').textContent(),/domid=117/);

  // Change one partner to "Aucun"; preview is recomputed without a duplicate engine.
  await domadoo.locator('select').selectOption('');
  await page.waitForFunction(()=>!document.querySelector('#tracked-batch-analyze').disabled);
  assert.equal(await domadoo.locator('.tracked-batch-destination').textContent(),urls[2]);
  assert.equal(await domadoo.locator('input[type="text"]').inputValue(),'Module Zigbee Sonoff');

  const all=page.locator('#tracked-batch-select-all');
  await all.click();
  assert.equal(await page.locator('.tracked-batch-row input[type="checkbox"]:checked').count(),0);
  await reolink.locator('input[type="checkbox"]').check();
  assert.match(await page.locator('#tracked-batch-count').textContent(),/1 lien sélectionné/);
  await all.click();
  assert.equal(await page.locator('.tracked-batch-row input[type="checkbox"]:checked').count(),2);
  await domadoo.locator('input[type="text"]').fill('Sonoff ZBMINIR2');

  for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:850});
   for(const theme of ['light','dark']){
    await page.selectOption('#theme-select',theme);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),
      'Horizontal overflow at '+width+' '+theme);
    assert(await dialog.evaluate(node=>node.scrollWidth<=node.clientWidth),
      'Dialog overflow at '+width+' '+theme);
   }
  }
  await page.locator('#tracked-batch-create').click();
  await dialog.waitFor({state:'hidden'});
  await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('2 liens suivis créés'));
  const after=(await api('/api/tracked-links')).items;
  assert.equal(after.length,3);
  assert.equal(after.find(item=>item.name==='Existant à réutiliser').url,firstSnapshot[0].url);
  assert.equal(after.find(item=>item.name==='Sonoff ZBMINIR2').url,urls[2]);
  assert.equal(after.find(item=>item.name==='Reolink OMVI X16 PoE').url,urls[1]+'?aff=1404');
  assert(!after.some(item=>Object.hasOwn(item,'category')));
  assert.deepEqual(errors,[]);
  assert.equal(createCalls,1);
  // Missing metadata remains editable; stale/failed previews cannot be submitted.
  await page.locator('#tracked-open-batch').click();
  await page.locator('#tracked-batch-urls').fill('https://example.com/no-title');
  await page.locator('#tracked-batch-analyze').click();
  await page.waitForFunction(()=>!document.querySelector('#tracked-batch-analyze').disabled);
  const manual=page.locator('.tracked-batch-row').first();
  assert.match(await manual.locator('.tracked-batch-row-status').textContent(),/Titre indisponible/);
  await manual.locator('input[type="text"]').fill('Titre manuel');
  assert.match(await manual.locator('.tracked-batch-row-status').textContent(),/Prêt à créer/);
  await manual.locator('input[type="checkbox"]').check();
  assert(await page.locator('#tracked-batch-create').isEnabled());
  await context.route('**/api/tracked-links/batch/preview',route=>route.fulfill({
   status:503,contentType:'application/json',body:JSON.stringify({error:'Indisponible'})
  }));
  await manual.locator('select').selectOption('');
  await page.waitForFunction(()=>!document.querySelector('#tracked-batch-analyze').disabled);
  assert(await page.locator('#tracked-batch-create').isDisabled());
  assert.match(await page.locator('#tracked-batch-progress').textContent(),/Analyse impossible/);
  await context.unroute('**/api/tracked-links/batch/preview');
  await page.locator('#tracked-batch-analyze').click();
  await page.waitForFunction(()=>!document.querySelector('#tracked-batch-analyze').disabled);
  assert(await page.locator('#tracked-batch-create').isEnabled());
  await page.locator('#tracked-batch-urls').fill('https://example.com/changed');
  assert(await page.locator('#tracked-batch-create').isDisabled());
  assert.equal(createCalls,1);
  assert.deepEqual((await api('/api/tracked-links')).items,after);
  await page.locator('[data-close-batch]').first().click();
  // Multiple matching partners require a manual choice, even on an error row.
  const chosenPartner=await api('/api/affiliate-partners',{
   name:'Choix A',domains:['ambiguous.example'],code:'A',template:'{url}?ref={code}'
  });
  await api('/api/affiliate-partners',{
   name:'Choix B',domains:['ambiguous.example'],code:'B',template:'{url}?ref={code}'
  });
  const invalidPartner=await api('/api/affiliate-partners',{
   name:'Destination LinKs interdite',domains:[],code:'X',template:'http://127.0.0.1:3003/{code}'
  });
  await page.locator('#tracked-open-batch').click();
  const recoverUrl='https://ambiguous.example/omvi-x16';
  await page.locator('#tracked-batch-urls').fill(recoverUrl);
  await page.locator('#tracked-batch-analyze').click();
  await page.waitForFunction(()=>!document.querySelector('#tracked-batch-analyze').disabled);
  assert.match(await manual.locator('.tracked-batch-row-status').textContent(),/Erreur/);
  assert(await manual.locator('select').isEnabled());
  await manual.locator('select').selectOption(chosenPartner.id);
  await page.waitForFunction(()=>!document.querySelector('#tracked-batch-analyze').disabled);
  assert.equal(await manual.locator('.tracked-batch-destination').textContent(),recoverUrl+'?ref=A');
  assert.equal(await manual.locator('input[type="text"]').inputValue(),'Reolink OMVI X16 PoE');
  await manual.locator('input[type="text"]').fill('Nom conservé');
  await manual.locator('select').selectOption(invalidPartner.id);
  await page.waitForFunction(()=>!document.querySelector('#tracked-batch-analyze').disabled);
  assert.match(await manual.locator('.tracked-batch-row-status').textContent(),/Erreur/);
  assert(await page.locator('#tracked-batch-create').isDisabled());
  assert(await manual.locator('select').isEnabled());
  await manual.locator('select').selectOption('');
  await page.waitForFunction(()=>!document.querySelector('#tracked-batch-analyze').disabled);
  assert.equal(await manual.locator('.tracked-batch-destination').textContent(),recoverUrl);
  assert.equal(await manual.locator('input[type="text"]').inputValue(),'Nom conservé');
  assert(await page.locator('#tracked-batch-create').isEnabled());
  assert.equal(createCalls,1);
  assert.deepEqual((await api('/api/tracked-links')).items,after);
  assert.deepEqual(errors,[]);
  console.log('PASS: bulk preview and creation, auto partner, override, duplicates, select all, manual title, responsive.');
 }finally{
  if(browser)await browser.close();
  const stopped=new Promise(resolve=>server.once('exit',resolve));server.kill();await stopped;
  rmSync(temp,{recursive:true,force:true});
 }
})().catch(error=>{console.error(error);process.exitCode=1});
