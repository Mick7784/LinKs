// Real browser regression for non-destructive bulk title generation.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {mkdtempSync,rmSync,mkdirSync}=require('node:fs');
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
   ['Nom manuel conservé','https://example.com/no-title'],
   ['Home Assistant Green','https://example.com/already-correct'],
   ['Paye-moi un café','https://ko-fi.com/mickael'],
   ['Paye moi un cafe','https://ko-fi.com/editorial'],
   ['Instagram','https://instagram.com/domotik_studio']
  ];
  for(const [name,url] of initial)await api('/api/tracked-links',{name,url});
  const before=(await api('/api/tracked-links')).items;
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
  const context=await browser.newContext({viewport:{width:1440,height:900}});
  let inspections=0;
  await context.route('**/api/tracked-links/title-preview',async route=>{
   inspections++;
   const {url,current_title}=route.request().postDataJSON();
   assert.equal(current_title,initial.find(row=>row[1]===url)[0],'Existing title sent for comparison');
   const editorial=url.endsWith('/editorial');
   const platform=url.includes('instagram.com'),slug=url.endsWith('product-two');
   const title=editorial?'Paye-moi un café':url.endsWith('product-one')?'UGREEN DXP4800 Pro':
    url.endsWith('product-two')?'Reolink OMVI X16 PoE':'';
   const status=editorial?'ok':platform||url.endsWith('already-correct')?'unchanged':url.includes('ko-fi.com')?'retained':title?'ok':'unavailable';
   await route.fulfill({status:200,contentType:'application/json',
    body:JSON.stringify({status,title:title||current_title,source:platform?'current_title':editorial?'editorial':slug?'url_slug':title?'open_graph':'',confidence:platform||slug?'medium':title?'high':'low',
     reason:platform?'platform_label_relevant':slug?'url_fallback':editorial?'editorial_correction':status==='unavailable'?'http_403':status==='retained'?'no_proven_gain':'already_informative',
     engine:{id:'bounded-metadata-v2',fingerprint:'123456abcdef'},
     diagnostics:{destination_decision:editorial?{reason:'http_403',status:'unavailable'}:undefined,fetch:{http_status:editorial||status==='unavailable'?403:200,code:editorial||status==='unavailable'?'http_403':'body_limit',redirects:0,truncated:!editorial&&status!=='unavailable'},extraction:{candidates:title&&!editorial?3:0}}})});
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
  assert.equal(inspections,7);
  assert.equal(await page.locator('.tracked-bulk-title-row').count(),7);
  const options=page.locator('.tracked-bulk-title-row input[type="checkbox"]');
  assert.equal(await options.count(),7);
  assert.equal(await page.locator('.tracked-bulk-title-row input[type="checkbox"]:checked').count(),0);
  assert.match(await page.locator('#tracked-titles-progress').textContent(),/3 améliorations.*3 titres conservés.*1 analyse sans résultat fiable/);
  assert.equal(await page.locator('.tracked-bulk-title-row.has-proposal').count(),3);
  assert.equal(await page.locator('.tracked-bulk-title-row.is-selected').count(),0);
  assert.match(await dialog.textContent(),/Titre déjà pertinent, conservé/);
  assert.match(await dialog.textContent(),/Aucun gain certain/);
  assert.match(await dialog.textContent(),/Analyse sans résultat fiable/);
  assert.match(await dialog.textContent(),/Proposition issue de l’URL descriptive/);
  const neutral=page.locator('.tracked-bulk-title-row').filter({hasText:'https://instagram.com/'});
  assert.match(await neutral.textContent(),/Titre déjà pertinent pour cette plateforme/);
  assert.doesNotMatch(await neutral.getAttribute('class'),/has-proposal|is-selected/);
  assert.match(await dialog.textContent(),/Réponse HTTP 403/);
  assert.match(await dialog.textContent(),/Fiabilité élevée/);
  assert.equal(await page.locator('#tracked-titles-save').isDisabled(),true);
  assert.deepEqual((await api('/api/tracked-links')).items,before,'Analysis never writes to database');

  const editorialRow=page.locator('.tracked-bulk-title-row').filter({hasText:'Paye moi un cafe'});
  assert.match(await editorialRow.textContent(),/Correction rédactionnelle du titre existant/);
  assert.equal(await editorialRow.locator('input[type="text"]').inputValue(),'Paye-moi un café');
  assert.equal(await editorialRow.locator('input[type="checkbox"]').isChecked(),false);
  await editorialRow.locator('summary').click();
  assert.match(await editorialRow.locator('.tracked-bulk-title-diagnostic').textContent(),/Réponse HTTP 403/);
  assert.match(await dialog.textContent(),/Amélioration proposée depuis la destination/);
  const all=page.locator('#tracked-titles-select-all');
  await all.click();
  assert.equal(await page.locator('.tracked-bulk-title-row input[type="checkbox"]:checked').count(),3,'Select all only selects modifiable titles');
  assert.match(await page.locator('#tracked-titles-count').textContent(),/3 titres sélectionnés sur 7/);
  assert.equal(await page.locator('.tracked-bulk-title-row.is-selected').count(),3);
  await all.click();
  assert.equal(await page.locator('.tracked-bulk-title-row input[type="checkbox"]:checked').count(),0);
  assert.equal(await page.locator('.tracked-bulk-title-row.is-selected').count(),0);
  const manual=page.locator('.tracked-bulk-title-row').filter({hasText:'Nom manuel conservé'});
  assert.doesNotMatch(await manual.textContent(),/Titre déjà pertinent/);
  await manual.locator('summary').click();
  assert.match(await manual.locator('.tracked-bulk-title-diagnostic').textContent(),/HTTP 403.*Moteur bounded-metadata-v2.*123456abcdef/);
  await manual.locator('input[type="text"]').fill('Nom choisi manuellement');
  assert.match(await manual.getAttribute('class'),/has-proposal/);
  assert.equal(await manual.locator('input[type="checkbox"]').isChecked(),false);
  await manual.locator('input[type="checkbox"]').check();
  await manual.locator('input[type="text"]').fill('');
  assert.equal(await manual.locator('input[type="checkbox"]').isChecked(),false);
  assert.equal(await manual.locator('input[type="checkbox"]').isDisabled(),true);
  assert.doesNotMatch(await manual.getAttribute('class'),/has-proposal|is-selected/);
  await manual.locator('input[type="text"]').fill('Nom manuel conservé');
  const row=page.locator('.tracked-bulk-title-row').filter({hasText:'Nom très long ancien 1'});
  await row.locator('input[type="checkbox"]').check();
  await row.locator('input[type="text"]').fill('UGREEN NASync DXP4800 Pro');
  assert.equal(await page.locator('.tracked-bulk-title-row input[type="checkbox"]:checked').count(),1);

  await editorialRow.locator('input[type="text"]').fill('Paye moi un cafe');
  assert.equal(await editorialRow.locator('input[type="checkbox"]').isDisabled(),true);
  assert.doesNotMatch(await editorialRow.getAttribute('class'),/has-proposal|is-selected/);
  await editorialRow.locator('input[type="text"]').fill('Paye-moi un café');
  assert.equal(await editorialRow.locator('input[type="checkbox"]').isChecked(),false);
  await editorialRow.locator('input[type="checkbox"]').check();

  for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:850});
   for(const theme of ['light','dark']){
    await page.selectOption('#theme-select',theme);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow at '+width+' '+theme);
    assert(await dialog.evaluate(node=>node.scrollWidth<=node.clientWidth),'Dialog overflow at '+width+' '+theme);
    const proposal=page.locator('.tracked-bulk-title-row.has-proposal:not(.is-selected)').first();
    const selectedStyle=await row.evaluate(node=>({background:getComputedStyle(node).backgroundColor,border:getComputedStyle(node).borderColor}));
    const proposalStyle=await proposal.evaluate(node=>({background:getComputedStyle(node).backgroundColor,border:getComputedStyle(node).borderColor}));
    const neutralStyle=await neutral.evaluate(node=>({background:getComputedStyle(node).backgroundColor,border:getComputedStyle(node).borderColor}));
    assert.notEqual(proposalStyle.background,neutralStyle.background);assert.notEqual(proposalStyle.border,neutralStyle.border);
    assert.notEqual(selectedStyle.background,proposalStyle.background);assert.notEqual(selectedStyle.border,proposalStyle.border);
    assert.equal(await row.locator('.tracked-bulk-title-marker').textContent(),'Sélectionnée');
    assert.equal(await proposal.locator('.tracked-bulk-title-marker').textContent(),'Proposition disponible');
    if(process.env.TITLE_REVIEW_SCREENSHOTS){
     mkdirSync(process.env.TITLE_REVIEW_SCREENSHOTS,{recursive:true});
     await proposal.scrollIntoViewIfNeeded();
     await page.screenshot({path:join(process.env.TITLE_REVIEW_SCREENSHOTS,`titles-${width}-${theme}.png`),fullPage:true});
    }
   }
  }
  await page.locator('#tracked-titles-save').click();
  await dialog.waitFor({state:'hidden'});
  await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('2 titres mis à jour'));
  const after=(await api('/api/tracked-links')).items;
  const previous=Object.fromEntries(before.map(row=>[row.id,row]));
  const changed=after.filter(row=>row.name!==previous[row.id].name);
  assert.equal(changed.length,2);
  assert.deepEqual(changed.map(row=>row.name).sort(),['Paye-moi un café','UGREEN NASync DXP4800 Pro'].sort());
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
