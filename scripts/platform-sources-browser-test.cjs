// Platform-first selection, preserved historical aliases and real PulSe retrieval.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const {mkdtempSync,rmSync}=require('node:fs'),{tmpdir}=require('node:os'),{join,resolve}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-platforms-')),python=process.env.PYTHON_PATH||'python3',origin='http://127.0.0.1:8081',db=join(temp,'stats.db'),credential='p'.repeat(64);
 execFileSync(python,[resolve(__dirname,'fixtures.py'),db]);
 const server=spawn(python,[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:db,UPLOAD_DIR:join(temp,'uploads'),PULSE_BRIDGE_TOKEN:credential},stdio:'ignore'});
 let browser;
 const api=async(path,data,method=data?'POST':'GET',pulse=false)=>{const response=await fetch(origin+path,{method,headers:{'Content-Type':'application/json','X-Links-Request':'1',...(pulse?{Authorization:'Bearer '+credential}:{})},body:data?JSON.stringify(data):undefined});assert(response.ok,await response.clone().text());return response.json()};
 try{
  for(let i=0;i<100;i++){try{if((await fetch(origin+'/healthz')).ok)break}catch{}await new Promise(r=>setTimeout(r,100));}
  const sources=(await api('/api/tracking-sources')).items,instagram=sources.find(row=>row.platform==='instagram'),youtube=sources.find(row=>row.platform==='youtube'),legacy=sources.find(row=>row.name==='Instagram Story');
  const old=await api('/api/tracked-links',{name:'Lien historique',url:'https://shop.example/old'}),fresh=await api('/api/tracked-links',{name:'Nouveau lien',url:'https://shop.example/new'});
  const oldToken=await api(`/api/tracked-links/${old.id}/token`,{source_id:legacy.id});
  assert.equal((await api('/api/pulse/story-link',{type:'independent',id:old.id},'POST',true)).url,oldToken.url);
  const pulseFresh=await api('/api/pulse/story-link',{type:'independent',id:fresh.id},'POST',true);assert.equal(pulseFresh.source_id,instagram.id);
  assert((await api('/api/pulse/links',undefined,'GET',true)).links.some(row=>row.id===fresh.id));
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));page.on('dialog',dialog=>dialog.accept());
  await page.goto(origin);await page.locator('#chart svg').waitFor();await page.click('[data-tab="tracked-links"]');
  const row=page.locator(`[data-tracked-id="${fresh.id}"]`);await row.waitFor();assert.equal(await row.locator('select').inputValue(),instagram.id);
  assert.equal(await row.locator('optgroup').first().getAttribute('label'),'Plateformes');assert(await row.locator('optgroup[label="Historiques"] option').filter({hasText:'Instagram Story'}).count());
  assert(await row.locator(`optgroup[label="Plateformes"] option[value="${youtube.id}"]`).count());
  await page.click('#tracked-manage-sources');assert.equal(await page.locator('#tracked-source-list [data-source-id]').count(),6);assert.equal(await page.locator(`#tracked-source-list [data-source-id="${legacy.id}"]`).count(),0);
  await page.selectOption('#tracked-source-scope','historical');await page.locator(`#tracked-source-list [data-source-id="${legacy.id}"]`).waitFor();
  await page.fill('#tracked-source-search','Instagram Story');assert.equal(await page.locator('#tracked-source-list [data-source-id]').count(),1);
  const historic=page.locator(`#tracked-source-list [data-source-id="${legacy.id}"]`);await historic.locator('input').fill('Stories historiques');await historic.locator('[data-source-action="rename"]').click();await page.fill('#tracked-source-search','');await page.selectOption('#tracked-source-scope','current');
  const preferred=page.locator(`#tracked-source-list [data-source-id="${instagram.id}"]`);await preferred.locator('input').fill('Instagram principal');await preferred.locator('[data-source-action="rename"]').click();await page.locator('#tracked-source-list input[value="Instagram principal"]').waitFor();
  await preferred.locator('[data-source-action="remove"]').click();await preferred.locator('[data-source-action="restore"]').waitFor();await preferred.locator('[data-source-action="restore"]').click();await preferred.locator('[data-source-action="remove"]').waitFor();
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:900});for(const theme of ['light','dark']){await page.selectOption('#theme-select',theme);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));if(process.env.UI_SCREENSHOTS&&width===390){await page.waitForTimeout(200);await page.screenshot({path:join(process.env.UI_SCREENSHOTS,`platforms-${theme}.png`),fullPage:true});}}}
  await page.locator('[data-close-sources]').first().click();assert.equal(await row.locator('select').inputValue(),instagram.id);
  assert.equal((await api('/api/pulse/story-link',{type:'independent',id:old.id},'POST',true)).url,oldToken.url);
  assert.equal((await api('/api/pulse/story-link',{type:'independent',id:fresh.id},'POST',true)).url,pulseFresh.url);
  assert.deepEqual(errors,[]);console.log('PASS: grouped platform defaults, history/search/archive/restore, source identity after rename, existing/new PulSe Stories and link retrieval, responsive themes.');
 }finally{await browser?.close();const exited=new Promise(resolve=>server.once('exit',resolve));server.kill();await exited;rmSync(temp,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1});
