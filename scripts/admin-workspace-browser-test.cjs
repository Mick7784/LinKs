// Real UI on a random local port and disposable data. No deployed instance is used.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process'),{mkdtempSync,mkdirSync,rmSync}=require('node:fs');
const {tmpdir}=require('node:os'),{join}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-admin-workspace-'));let browser,server;
 try{
  server=spawn(process.env.PYTHON_PATH||'python3',['-u','-B',join(__dirname,'statistics_workspace_fixture.py'),temp],{stdio:['ignore','pipe','pipe']});
  let stderr='';server.stderr.on('data',data=>stderr+=data);
  const origin=await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('Fixture timeout: '+stderr)),20000);
   server.stdout.once('data',data=>{clearTimeout(timer);resolve(data.toString().trim())});
   server.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+': '+stderr))});
  });
  const read=async path=>{const response=await fetch(origin+path);assert(response.ok,path);return response.json()};
  const paths=['/api/public-config','/api/content','/api/tracked-links','/api/stats/workspace?period=30','/api/appearance','/api/descriptions/templates','/api/descriptions/drafts'];
  const before=await Promise.all(paths.map(read));
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
  const context=await browser.newContext(),page=await context.newPage(),errors=[],writes=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{
   // These endpoints accept drafts via POST but only compute previews/availability.
   const readOnlyPosts=['/api/descriptions/preview','/api/promotions/check'];
   if(request.url().startsWith(origin+'/api/')&&!['GET','HEAD'].includes(request.method())&&!readOnlyPosts.includes(new URL(request.url()).pathname))writes.push(request.url());
  });
  // Public previews can contain external resources; the check never contacts merchants.
  await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  await page.goto(origin);await page.locator('.sw-overview').waitFor();
  const navigate=async id=>{
   if(await page.locator('#menu-toggle').isVisible())await page.locator('#menu-toggle').click();
   await page.locator(`[data-tab="${id}"]`).click();await page.locator(`#${id}.active`).waitFor();
  };
  const fits=async label=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),label);
  const keyboard=async (selector,lastId,firstId)=>{
   const bar=page.locator(selector);await bar.locator('button').first().focus();
   await page.keyboard.press('End');assert.equal(await page.evaluate(()=>document.activeElement.id),lastId);
   await page.keyboard.press('Home');assert.equal(await page.evaluate(()=>document.activeElement.id),firstId);
  };
  const screenshots=process.env.ADMIN_WORKSPACE_SCREENSHOTS;if(screenshots)mkdirSync(screenshots,{recursive:true});
  for(const width of [1440,1024,768,390,320])for(const theme of ['light','dark']){
   await page.setViewportSize({width,height:1000});await page.selectOption('#theme-select',theme);
   for(const view of ['settings','appearance','descriptions','affiliation']){
    await navigate(view);await page.locator(`#${view} .workspace-tabs`).first().waitFor({state:view==='settings'&&width<=760?'attached':'visible'});
    if(view==='settings'){
     if(width>760)assert(await page.locator('#settings-nav').evaluate(nav=>{
      const buttons=[...nav.children];return buttons[0].getBoundingClientRect().top===buttons[1].getBoundingClientRect().top;
     }),'settings sections share a horizontal bar');
     for(const section of ['overview','general','integrations','statistics','security','quotes','sharing','storage','maintenance']){
      if(width<=760)await page.selectOption('.settings-mobile-nav',section);else await page.locator(`[data-settings-section="${section}"]`).click();
      const selected=page.locator('#settings-nav [aria-current="page"]');assert.equal(await selected.getAttribute('data-settings-section'),section);
      await fits(`${view}/${section} ${width} ${theme}`);
     }
     if(width>760)await keyboard('#settings-nav','settings-section-maintenance','settings-section-overview');
     await page.evaluate(()=>LinksSettings.show('overview'));await page.locator('.settings-card').first().waitFor();
     await page.locator('.settings-card').first().focus();await page.keyboard.press('Enter');
     assert.equal(await page.evaluate(()=>document.activeElement.id),width<=760?'':'settings-section-general');
     if(width<=760)assert(await page.locator('.settings-mobile-nav').evaluate(select=>select===document.activeElement));
     await page.evaluate(()=>LinksSettings.show('overview'));await page.locator('.settings-card').first().waitFor();
    }else if(view==='appearance'){
     for(const section of ['library','transfer','editor','campaigns','themes']){
      await page.locator('#appearance-section-'+section).focus();await page.keyboard.press('Enter');
      await page.locator('#appearance-panel').waitFor();
      assert.equal(await page.evaluate(()=>document.activeElement.id),'appearance-section-'+section,'appearance keeps focus after replacement');
      assert.equal(await page.locator('.appearance-tabs [aria-current="page"]').getAttribute('id'),'appearance-section-'+section);
      await fits(`${view}/${section} ${width} ${theme}`);
     }
     await keyboard('.appearance-tabs','appearance-section-transfer','appearance-section-themes');
    }else if(view==='descriptions'){
     for(const section of ['drafts','templates']){
      await page.locator('#description-section-'+section).focus();await page.keyboard.press('Enter');
      await page.waitForFunction(id=>document.activeElement.id===id,'description-section-'+section);
      assert.equal(await page.locator('#descriptions .workspace-tabs [aria-current="page"]').getAttribute('id'),'description-section-'+section);
      await fits(`${view}/${section} ${width} ${theme}`);
     }
     await keyboard('#descriptions .workspace-tabs','description-section-templates','description-section-drafts');
    }else{
     const partner=page.locator('.aff-partner-tabs [data-aff="partner"]').first();
     if(await partner.count()){
      await partner.focus();const id=await partner.getAttribute('id');await page.keyboard.press('Enter');
      await page.locator('#'+id+'[aria-current="page"]').waitFor();
      await page.waitForFunction(id=>document.activeElement.id===id,id);
      for(const button of await page.locator('.aff-tabs:not(.aff-partner-tabs) [data-aff-tab]').all()){
       const id=await button.getAttribute('id');await page.locator('#'+id).focus();await page.keyboard.press('Enter');
       await page.locator('#'+id+'[aria-current="page"]').waitFor();
       await page.waitForFunction(id=>document.activeElement.id===id,id);await fits(`${view}/${id} ${width} ${theme}`);
      }
      await page.locator('.aff-partner-tabs [data-aff="global"]').click();
      await page.locator('.aff-partner-tabs [data-aff="global"][aria-current="page"]').waitFor();
     }
    }
    await fits(`${view} ${width} ${theme}`);
    const style=await page.locator(`#${view} .workspace-tabs button`).first().evaluate(button=>({radius:getComputedStyle(button).borderRadius,size:getComputedStyle(button).fontSize}));
    assert.equal(style.radius,'9px');assert.equal(style.size,width<=650?'12px':'14px');
    if(screenshots&&[1440,390].includes(width)){await page.mouse.move(0,0);await page.screenshot({path:join(screenshots,`${view}-${width}-${theme}.png`),fullPage:true,animations:'disabled'})}
   }
   for(const view of ['campaigns','permanent-links','content','buttons','archives','tracked-links']){
    await navigate(view);await fits(`${view} ${width} ${theme}`);
    const card=page.locator(`#${view} .panel, #${view} .content-section`).first();await card.waitFor();
    assert.equal(await card.evaluate(node=>getComputedStyle(node).borderRadius),'15px',view+' shares card surfaces');
    for(const [action,dialog] of view==='campaigns'?[['[data-action="new-campaign"]','#block-dialog']]:view==='buttons'?[['[data-action="new-button"]','#button-dialog']]:view==='tracked-links'?[['[data-action="new-tracked"]','#tracked-dialog']]:[]){
     await page.locator(action).click();await page.locator(dialog+'[open]').waitFor();await fits(`${dialog} ${width} ${theme}`);
     assert(await page.locator(dialog).evaluate(node=>node.contains(document.activeElement)),'dialog receives focus');
     await page.keyboard.press('Escape');await page.locator(dialog).waitFor({state:'hidden'});
    }
    if(screenshots&&[1440,390].includes(width)){await page.mouse.move(0,0);await page.screenshot({path:join(screenshots,`${view}-${width}-${theme}.png`),fullPage:true,animations:'disabled'})}
   }
  }
  await page.emulateMedia({reducedMotion:'reduce'});
  for(const view of ['settings','appearance','descriptions','affiliation']){
   await navigate(view);
   // Opening Appearance fetches data and replaces its bar. Read the current
   // connected button atomically, rather than a handle that can be detached.
   await page.waitForFunction(view=>{
    const button=document.querySelector(`#${view}.active .workspace-tabs button`);
    if(!button)return false;
    const style=getComputedStyle(button);
    return style.transitionDuration==='0s'&&style.animationName==='none';
   },view);
  }
  await navigate('appearance');
  await page.locator('#appearance-section-library').focus();await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'appearance-section-library');
  assert.deepEqual(await Promise.all(paths.map(read)),before,'navigation preserves public themes, published links, tracked tokens and statistics');
  const touch=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true}),touchPage=await touch.newPage();
  await touch.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  await touchPage.goto(origin);await touchPage.locator('.sw-overview').waitFor();await touchPage.locator('#menu-toggle').click();await touchPage.locator('[data-tab="appearance"]').click();
  await touchPage.locator('.appearance-tabs').waitFor();
  assert(await touchPage.locator('.appearance-tabs button').evaluateAll(buttons=>buttons.every(button=>button.getBoundingClientRect().height>=44)),'touch controls are at least 44px');
  await touch.close();
  assert.deepEqual(writes,[],'browsing does not write application data');assert.deepEqual(errors,[]);
  console.log('PASS admin workspace: 10 modules, detailed sections and dialogs, 5 widths × 2 themes, keyboard/focus, touch, reduced motion, no data writes, public themes/links/history preserved');
 }finally{
  if(browser)await browser.close();
  if(server){server.kill();if(server.exitCode===null)await new Promise(resolve=>server.once('exit',resolve))}
  rmSync(temp,{recursive:true,force:true});
 }
})().catch(error=>{console.error(error);process.exitCode=1});
