/* Real local HTTP/SQLite integration, disposable data only. */
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process'),{mkdtempSync,mkdirSync,rmSync,writeFileSync}=require('node:fs'),{tmpdir}=require('node:os'),{join,resolve}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-workspace-')),python=process.env.PYTHON_PATH||'python3',screenshots=process.env.STATISTICS_SCREENSHOTS;
 const server=spawn(python,[resolve(__dirname,'statistics_workspace_fixture.py'),temp],{stdio:['ignore','pipe','pipe'],env:process.env});
 let browser,stderr='';server.stderr.on('data',data=>stderr+=data);
 try{
  const origin=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture timeout: '+stderr)),20000);server.stdout.once('data',data=>{clearTimeout(timer);resolve(data.toString().trim())});server.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+': '+stderr))});});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1920,height:1080},reducedMotion:'reduce'}),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(new URL(r.url()).pathname));
  await page.goto(origin);await page.locator('.sw-overview').waitFor();await page.selectOption('#theme-select','dark');
  const shoot=async name=>{if(screenshots){mkdirSync(screenshots,{recursive:true});await page.screenshot({path:join(screenshots,name+'.png'),fullPage:true,animations:'disabled'});}};
  const noOverflow=async(vertical=false)=>{const sizes=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight}));assert(sizes.scrollWidth<=sizes.width,'horizontal overflow '+JSON.stringify(sizes));if(vertical)assert(sizes.scrollHeight<=sizes.height,'vertical overflow '+JSON.stringify(sizes));return sizes;};
  assert.equal(await page.locator('.sw-metric').textContent(),'17');assert.equal(await page.locator('.sw-campaign').count(),3);
  const fullHD=await noOverflow(true);await shoot('statistiques-vue-ensemble');
  assert.equal(await page.locator('#navigation-tabs [data-tab=dashboard]').count(),0);
  assert.equal(await page.locator('#navigation-tabs [data-tab=statistics]').count(),1);
  const chartPath=await page.locator('.sw-series').getAttribute('d');await page.click('[data-sw-metric=visits]');assert.notEqual(await page.locator('.sw-series').getAttribute('d'),chartPath);assert.equal(await page.locator('.sw-series').count(),1);
  await page.selectOption('#sw-period','month');await page.locator('.sw-overview').waitFor();await page.selectOption('#sw-period','30');await page.locator('.sw-overview').waitFor();
  await page.click('#sw-tab-links');assert.equal(await page.locator('.sw-row').count(),3);
  const row=page.locator('.sw-row').first(),before=await row.boundingBox();await row.click();
  assert.equal(await row.getAttribute('aria-pressed'),'true');assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),'20');
  assert.equal((await row.boundingBox()).height,before.height);assert.equal(await page.locator('.sw-result details').count(),0);
  assert.equal(await page.locator('#sw-context .sw-source').count(),3);await shoot('statistiques-lien-selectionne');
  await page.locator('.sw-row').nth(1).click();assert.equal(await page.locator('.sw-row[aria-pressed=true]').count(),1);assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),'5');
  await page.locator('.sw-row').nth(1).click();assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),'28');
  await page.selectOption('#sw-source','p:youtube');assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),'15');
  await page.locator('#sw-search').fill('multi');assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),'10');
  await page.locator('#sw-search').fill('absent');assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),'0');assert.equal(await page.locator('#sw-context .sw-source').count(),0);
  await page.click('[data-sw-reset]');await page.locator('#sw-search').fill('Même titre');assert.equal(await page.locator('.sw-row').count(),2);
  await page.click('[data-sw-mode=public]');assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),'2');assert((await page.locator('#sw-context').textContent()).includes('Non identifiée'));
  await page.click('[data-sw-mode=tracked]');await page.locator('.sw-row').first().click();
  assert.equal(await page.locator('.sw-reveal').evaluate(el=>getComputedStyle(el).animationName),'none');
  await page.emulateMedia({reducedMotion:'no-preference'});await page.locator('.sw-row').first().click();
  assert.equal(await page.locator('.sw-reveal').evaluate(el=>getComputedStyle(el).animationDuration),'0.76s');
  const today=await page.locator('#sw-date').inputValue();await page.locator('#sw-date').fill('2001-01-01');await page.locator('.sw-empty').waitFor();assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),'0');
  await page.locator('#sw-date').fill(today);await page.locator('.sw-row').first().waitFor();
  await page.click('#sw-tab-visits');assert((await page.locator('.sw-detail-toolbar').textContent()).includes('Visites de la page'));
  await page.click('#sw-tab-campaigns');assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),'6');await shoot('statistiques-campagnes');
  await page.locator('#sw-tab-campaigns').focus();await page.keyboard.press('Home');assert.equal(await page.locator('#sw-tab-overview').getAttribute('aria-selected'),'true');
  for(const [width,height] of [[1366,768],[1440,900],[390,844],[320,700]]){await page.setViewportSize({width,height});await noOverflow();await page.click('#sw-tab-links');await noOverflow();await page.click('#sw-tab-overview');}
  await page.setViewportSize({width:1920,height:1080});await page.selectOption('#theme-select','light');await noOverflow(true);await shoot('statistiques-theme-clair');
  await page.click('#sw-tab-links');await page.locator('#statistics-legacy > summary').click();await page.locator('#chart svg').waitFor();assert.equal(await page.locator('#statistics-codes').count(),1);
  await page.locator('#statistics-legacy > summary').click();await page.click('#sw-tab-overview');await noOverflow(true);
  const merchantRequests=requests.filter(path=>/amazon|domadoo|affiliation\//.test(path));assert.deepEqual(merchantRequests,[]);
  // Force an HTTP error, then a slower stale response: navigation remains usable.
  await page.route('**/api/stats/workspace?**',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Test indisponibilité'})}));
  await page.click('#navigation-tabs [data-tab=statistics]');await page.locator('[data-sw-retry]').waitFor();await page.click('#sw-tab-links');assert.equal(await page.locator('.sw-row').count(),0);
  await page.unroute('**/api/stats/workspace?**');await page.click('[data-sw-retry]');await page.locator('.sw-row').first().waitFor();
  await page.route('**/api/stats/workspace?**',async route=>{if(new URL(route.request().url()).searchParams.get('date')==='2001-01-01')await new Promise(r=>setTimeout(r,350));await route.continue();});
  await page.locator('#sw-date').fill('2001-01-01');await page.click('#sw-tab-campaigns');await page.locator('.sw-empty').waitFor();assert.equal(await page.locator('#sw-tab-campaigns').getAttribute('aria-selected'),'true');await page.unroute('**/api/stats/workspace?**');
  // Add a large history only to this disposable SQLite file; verify bounded DOM.
  execFileSync(python,['-c',"import sqlite3,sys;db=sqlite3.connect(sys.argv[1]);db.executemany('INSERT INTO counts VALUES(?,?,?,?,?)',[(sys.argv[2],'youtube','tracked','tracked:tk_'+str(i).zfill(16)+':12',1) for i in range(10000)]);db.commit()",join(temp,'stats.db'),today]);
  await page.locator('#sw-date').fill(today);await page.locator('.sw-row').first().waitFor();await page.click('#sw-tab-links');
  const started=performance.now();assert((await page.locator('#sw-result-count').textContent()).includes('10'));assert(await page.locator('.sw-row').count()<30);
  await page.locator('#sw-results').focus();await page.keyboard.press('End');assert.equal(await page.locator('.sw-row:focus').getAttribute('data-sw-index'),'10002');
  await page.locator('#sw-search').fill('9999');assert.equal(await page.locator('.sw-row').count(),1);const largeMs=Math.round(performance.now()-started);
  await page.click('#navigation-tabs [data-tab=tracked-links]');await page.locator('#tracked-links.active').waitFor();
  await page.evaluate(()=>location.hash='dashboard');await page.locator('#statistics.active').waitFor();await page.locator('#sw-panel[aria-busy=false]').waitFor();
  assert.deepEqual(errors,[]);
  const report={fullHD,largeHistoryRows:10003,largeHistoryInteractionMs:largeMs,javascriptErrors:errors,merchantRequests,checks:'navigation, units, sources, homonyms, filters, selection, animation, reduced motion, keyboard, 5 viewport sizes, both themes, legacy reports, error/retry, delayed response, large history, old hash'};
  if(screenshots)writeFileSync(join(screenshots,'validation-navigateur.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser?.close();server.kill();await new Promise(r=>server.exitCode!==null?r():server.once('exit',r));rmSync(temp,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
