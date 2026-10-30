// Real browser regression for non-destructive bulk title generation.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {mkdtempSync,rmSync}=require('node:fs');
const {tmpdir}=require('node:os');
const {join,resolve}=require('node:path');

(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-title-bulk-'));
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
  assert(ready,'Test instance did not start');
  const initial=[
   ['Nom très long ancien 1','https://example.com/product-one'],
   ['Ancien nom caméra 2','https://example.com/product-two'],
   ['Nom manuel conservé','https://example.com/no-title']
  ];
  for(const [name,url] of initial)await api('/api/tracked-links',{name,url});
  const before=(await api('/api/tracked-links')).items;
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
  const context=await browser.newContext({viewport:{width:1440,height:900}});
  let inspections=0;
  await context.route('**/api/tracked-links/title-preview',async route=>{
   inspections++;
   const url=route.request().postDataJSON().url;
   const title=url.endsWith('product-one')?'UGREEN DXP4800 Pro':
    url.endsWith('product-two')?'Reolink OMVI X16 PoE':'';
   await route.fulfill({status:200,contentType:'application/json',
    body:JSON.stringify({status:title?'ok':'unavailable',title,source:title?'open_graph':''})});
  });
  const page=await context.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(origin);await page.locator('#chart svg').waitFor();
  if(await page.locator('#menu-toggle').isVisible())await page.locator('#menu-toggle').click();
  await page.locator('[data-tab="tracked-links"]').click();
  await page.locator('#tracked-links.active').waitFor();
  assert.equal(await page.locator('#tracked-manage-sources').count(),1);
  await page.locator('#tracked-generate-titles').click();
  const dialog=page.locator('#tracked-titles-dialog');
  await dialog.waitFor({state:'visible'});
  await page.waitForFunction(()=>document.querySelector('#tracked-titles-progress').textContent.includes('Analyse terminée'));
  assert.equal(inspections,3);
  assert.equal(await page.locator('.tracked-bulk-title-row').count(),3);
  const options=page.locator('.tracked-bulk-title-row input[type="checkbox"]');
  assert.equal(await options.count(),3);
  assert.equal(await page.locator('#tracked-titles-save').isDisabled(),true);
  assert.deepEqual((await api('/api/tracked-links')).items,before,'Analysis never writes to database');

  const all=page.locator('#tracked-titles-select-all');
  await all.click();
  assert.equal(await options.filter({checked:true}).count(),2,'Select all only selects modifiable titles');
  assert.match(await page.locator('#tracked-titles-count').textContent(),/2 titres sélectionnés sur 3/);
  await all.click();
  assert.equal(await options.filter({checked:true}).count(),0);
  const row=page.locator('.tracked-bulk-title-row').filter({hasText:'Nom très long ancien 1'});
  await row.locator('input[type="checkbox"]').check();
  await row.locator('input[type="text"]').fill('UGREEN NASync DXP4800 Pro');
  assert.equal(await options.filter({checked:true}).count(),1);

  for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:850});
   for(const theme of ['light','dark']){
    await page.selectOption('#theme-select',theme);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow at '+width+' '+theme);
    assert(await dialog.evaluate(node=>node.scrollWidth<=node.clientWidth),'Dialog overflow at '+width+' '+theme);
   }
  }
  await page.locator('#tracked-titles-save').click();
  await dialog.waitFor({state:'hidden'});
  await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('1 titre mis à jour'));
  const after=(await api('/api/tracked-links')).items;
  const previous=Object.fromEntries(before.map(row=>[row.id,row]));
  const changed=after.filter(row=>row.name!==previous[row.id].name);
  assert.equal(changed.length,1);
  assert.equal(changed[0].name,'UGREEN NASync DXP4800 Pro');
  for(const link of after){
   const old=previous[link.id];
   for(const key of ['url','original_url','notes','partner_id','archived','enabled','clicks','sources','created_at']){
    assert.deepEqual(link[key],old[key],'Modified '+key);
   }
  }
  assert.deepEqual(errors,[]);
  console.log('PASS: title preview, select all / individual, editable suggestions, atomic apply, no URL changes, mobile dark/light.');
 }finally{
  if(browser)await browser.close();
  const stopped=new Promise(resolve=>server.once('exit',resolve));
  server.kill();await stopped;
  rmSync(temp,{recursive:true,force:true});
 }
})().catch(error=>{console.error(error);process.exitCode=1});
