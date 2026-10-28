// Real public document, disposable database, and no production connections.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process'),{mkdtempSync,rmSync,mkdirSync}=require('node:fs'),{tmpdir}=require('node:os'),{join,resolve}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-layout-')),origin='http://127.0.0.1:8081',python=process.env.PYTHON_PATH||'python3';let browser,server;
 execFileSync(python,[resolve(__dirname,'fixtures.py'),join(temp,'stats.db'),origin]);
 const start=async()=>{server=spawn(python,[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:'ignore'});for(let i=0;i<100;i++){try{if((await fetch(origin+'/healthz')).ok)return}catch{}await new Promise(r=>setTimeout(r,100))}throw Error('Backend did not start')};
 const stop=async()=>{server.kill();await new Promise(r=>server.exitCode!==null?r():server.once('exit',r))};
 const api=async(path,data)=>{const r=await fetch(origin+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(r.ok,await r.clone().text());return r.json()};
 try{
  await start();await api('/api/content',{type:'promo',title:'Les essentiels de la maison connectée',url:'https://partner.example/offer',promo_code:'MAISON10'});
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],metrics=[];
  const mockVideo=async target=>target.route('**/latest-video.json',route=>route.fulfill({json:{title:'Une maison connectée qui vous ressemble',url:'https://www.youtube.com/watch?v=abcdefghijk',thumbnail:origin+'/preview/assets/link-community.webp',published:'2026-10-27T10:00:00Z'}}));
  await mockVideo(context);page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(new URL(r.url()).pathname==='/metrics')metrics.push(r.url())});
  const nav=async id=>{if(await page.locator('#menu-toggle').isVisible())await page.locator('#menu-toggle').click();await page.locator(`[data-tab="${id}"]`).click()};
  const ready=async()=>{await page.locator('#page-editor-status').filter({hasText:'Organisation enregistrée'}).waitFor();await page.frameLocator('#page-editor-frame').locator('.video-card').waitFor()};
  const frame=page.frameLocator('#page-editor-frame'),sectionOrder=()=>frame.locator('[data-layout-section]').evaluateAll(nodes=>nodes.map(n=>n.dataset.layoutSection)),linkOrder=()=>frame.locator('[data-layout-link]').evaluateAll(nodes=>nodes.map(n=>n.dataset.layoutLink));
  await page.goto(origin);await page.locator('#chart svg').waitFor();await nav('content');await ready();
  const before=await api('/api/public-config'),layout=await api('/api/page-layout'),records=(await api('/api/content')).items;
  assert.deepEqual(await sectionOrder(),before.section_order);assert.deepEqual(await linkOrder(),layout.link_ids);
  assert.equal(await frame.locator('main>.profile').count(),1);assert.equal(await frame.locator('main>footer').count(),1);
  assert.equal(await frame.locator('.profile [data-layout-action],footer [data-layout-action]').count(),0);
  assert.equal(await frame.locator('.offer-title').textContent(),'Les essentiels de la maison connectée');
  // The editor uses the same app, cards, styles and active appearance as the public page.
  const publicPage=await context.newPage();await publicPage.goto(origin+'/preview/index.html');await publicPage.locator('#links .card').first().waitFor();
  assert.deepEqual(await frame.locator('#links .card').evaluateAll(nodes=>nodes.map(n=>n.outerHTML)),await publicPage.locator('#links .card').evaluateAll(nodes=>nodes.map(n=>n.outerHTML)));
  assert.deepEqual(await frame.locator('.offer-card').evaluateAll(nodes=>nodes.map(n=>n.outerHTML)),await publicPage.locator('.offer-card').evaluateAll(nodes=>nodes.map(n=>n.outerHTML)));
  await frame.locator('[data-layout-section=classic]> .layout-controls [data-layout-action=up]').click();
  await frame.locator('[data-layout-link]').first().locator('[data-layout-action=drag]').focus();await page.keyboard.press('ArrowDown');
  assert.deepEqual(await api('/api/page-layout'),layout);assert.deepEqual(await api('/api/public-config'),before,'Draft cannot publish');
  assert.equal(await page.locator('#page-editor-save').isEnabled(),true);
  await nav('campaigns');await nav('content');assert.notDeepEqual(await linkOrder(),layout.link_ids,'Draft survives navigation');
  await page.locator('#page-editor-cancel').click();await ready();assert.deepEqual(await sectionOrder(),layout.section_order);assert.deepEqual(await linkOrder(),layout.link_ids);assert(await page.locator('#page-editor-save').isDisabled());
  // Keyboard, arrow buttons and mouse dragging all update only the local draft.
  await frame.locator('[data-layout-section=classic]>.layout-controls [data-layout-action=drag]').press('ArrowUp');
  await frame.locator('[data-layout-section=classic]>.layout-controls [data-layout-action=up]').click();
  assert.equal((await sectionOrder())[0],'classic');
  const grip=frame.locator('[data-layout-link]').first().locator('[data-layout-action=drag]'),target=frame.locator('[data-layout-link]').nth(1);
  await target.scrollIntoViewIfNeeded();const from=await grip.boundingBox(),to=await target.boundingBox();
  await page.mouse.move(from.x+from.width/2,from.y+from.height/2);await page.mouse.down();await page.mouse.move(to.x+to.width/2,to.y+to.height-3,{steps:12});await page.mouse.up();
  assert.equal((await linkOrder())[0],layout.link_ids[1]);
  const expectedSections=await sectionOrder(),expectedLinks=await linkOrder();await page.locator('#page-editor-save').click();await ready();
  const saved=await api('/api/page-layout');assert.deepEqual(saved.section_order,expectedSections);assert.deepEqual(saved.link_ids,expectedLinks);
  assert.deepEqual((await api('/api/content')).items.filter(x=>x.type!=='classic'),records.filter(x=>x.type!=='classic'),'Campaign records unchanged');
  await publicPage.reload();await publicPage.locator('#links .card').first().waitFor();
  assert.deepEqual(await publicPage.locator('main>section').evaluateAll(nodes=>nodes.map(n=>n.id)),expectedSections.map(x=>({classic:'links-section',highlight:'offers',video:'latest-video'})[x]));
  assert.deepEqual(await publicPage.locator('#links .card').evaluateAll(nodes=>nodes.map(n=>n.dataset.metric.slice(6))),expectedLinks);
  await stop();await start();assert.deepEqual(await api('/api/page-layout'),saved,'Restart preserves both orders');
  await page.reload();await nav('content');await ready();assert.deepEqual(await sectionOrder(),expectedSections);assert.deepEqual(await linkOrder(),expectedLinks);
  for(const width of [1440,390,320])for(const theme of ['light','dark']){
   await page.setViewportSize({width,height:1000});await page.selectOption('#theme-select',theme);
   await page.locator(`[data-layout-device="${width>760?'desktop':'mobile'}"]`).click();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Admin overflow');assert(await frame.locator('body').evaluate(n=>n.scrollWidth<=innerWidth),'Preview overflow');
   if(process.env.LAYOUT_SCREENSHOTS&&width!==320){mkdirSync(process.env.LAYOUT_SCREENSHOTS,{recursive:true});await page.evaluate(()=>{document.activeElement.blur();scrollTo(0,0);document.getElementById('notice').textContent=''});await page.screenshot({path:join(process.env.LAYOUT_SCREENSHOTS,`page-editor-${width>760?'desktop':'mobile'}-${theme}.png`),fullPage:true,animations:'disabled'})}
  }
  // A touch gesture moves an entire section, and can still be cancelled.
  const touch=await browser.newContext({hasTouch:true,isMobile:true,viewport:{width:390,height:1000},reducedMotion:'reduce'});await mockVideo(touch);
  const mobile=await touch.newPage();await mobile.goto(origin);await mobile.locator('#menu-toggle').click();await mobile.locator('[data-tab=content]').click();await mobile.locator('#page-editor-status').filter({hasText:'Organisation enregistrée'}).waitFor();
  const mobileFrame=mobile.frameLocator('#page-editor-frame'),source=mobileFrame.locator('[data-layout-section]').nth(1).locator(':scope>.layout-controls [data-layout-action=drag]'),destination=mobileFrame.locator('[data-layout-section]').first().locator(':scope>.layout-controls');
  await source.scrollIntoViewIfNeeded();const a=await source.boundingBox(),b=await destination.boundingBox(),cdp=await touch.newCDPSession(mobile),x=a.x+a.width/2,y=a.y+a.height/2;
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});for(let i=1;i<=12;i++)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x,y:y+(b.y+2-y)*i/12}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  assert(await mobile.locator('#page-editor-save').isEnabled(),'Touch move creates draft');assert.deepEqual(await api('/api/page-layout'),saved);await mobile.locator('#page-editor-cancel').click();await mobile.locator('#page-editor-status').filter({hasText:'Organisation enregistrée'}).waitFor();await touch.close();
  const unavailable=await browser.newContext();await unavailable.route('**/latest-video.json',route=>route.fulfill({status:503,json:{error:'No video'}}));const emptyPage=await unavailable.newPage();await emptyPage.goto(origin);await emptyPage.locator('[data-tab=content]').click();await emptyPage.locator('#page-editor-status').filter({hasText:'Organisation enregistrée'}).waitFor();const emptyFrame=emptyPage.frameLocator('#page-editor-frame');await emptyFrame.locator('#latest-video.layout-empty .layout-empty-note').waitFor();assert(await emptyFrame.locator('#latest-video').isVisible(),'Unavailable video remains movable');assert.equal(await emptyFrame.locator('[data-layout-section]').count(),3);await unavailable.close();
  assert.deepEqual(metrics,[],'Editor sends no analytics');assert.deepEqual(errors,[]);
  console.log('PASS page editor: real rendering, private draft/cancel, atomic save/restart, link order, mouse/touch/keyboard, responsive light/dark, no metrics');
 }finally{await browser?.close();if(server?.exitCode===null)await stop();rmSync(temp,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exitCode=1});
