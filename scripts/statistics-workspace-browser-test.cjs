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
  assert.equal(await page.locator('.sw-metric').textContent(),'621');assert.equal(await page.locator('.sw-campaign').count(),3);
  const settled=()=>page.locator('#sw-panel[aria-busy=false]').waitFor();
  assert.equal(await page.locator('#sw-period').inputValue(),'30');
  assert.match(await page.locator('.sw-visits .sw-trend').textContent(),/30 jours précédents/);
  assert.equal(await page.locator('.sw-links .sw-donut-number').textContent(),'35');
  for(const [tab,total,daily,previous] of [['visits','621','17','18'],['links','35','28','7'],['campaigns','10','6','4'],['copies','7','5','2']]){
    await page.click('#sw-tab-'+tab);
    assert.equal(await page.locator('#sw-period').inputValue(),'30');
    assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),total);
    assert.match(await page.locator('#sw-kpis .sw-trend').textContent(),/30 jours précédents/);
    if(tab==='links'){
      assert.match(await page.locator('#sw-partners').textContent(),/Domadoo/);
      assert.equal(await page.locator('#sw-partners tbody tr').count(),1);
      assert.equal(await page.locator('#sw-partners tbody td').last().textContent(),'27');
    }
    if(['campaigns','copies'].includes(tab)){
      assert.equal(await page.locator('.sw-performance-kpis strong').first().textContent(),'140');
      if(tab==='copies'){
        assert.equal(await page.locator('.sw-performance-kpis strong').last().textContent(),'5 %');
        await page.selectOption('#sw-source','p:instagram');
        assert.equal(await page.locator('.sw-performance-kpis strong').first().textContent(),'40');
        assert.equal(await page.locator('.sw-performance-kpis strong').nth(1).textContent(),'2');
        await page.click('[data-sw-reset]');
      }
    }
    assert.equal(await page.locator('#sw-date').count(),0);
    await page.selectOption('#sw-period','day');await settled();
    assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),daily);
    assert.match(await page.locator('#sw-kpis .sw-trend').textContent(),/vs veille/);
    const day=new Date((await page.locator('#sw-date').inputValue())+'T12:00:00Z');
    day.setUTCDate(day.getUTCDate()-1);
    await page.locator('#sw-date').fill(day.toISOString().slice(0,10));await settled();
    assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),previous);
    await page.click('#sw-tab-overview');
    assert.equal(await page.locator('.sw-metric').textContent(),'18');
    await page.selectOption('#sw-period','30');await settled();
  }
  await page.click('#sw-tab-overview');
  const fullHD=await noOverflow(true);await shoot('statistiques-vue-ensemble');
  const campaignCard=await page.locator('.sw-campaigns').boundingBox(),campaignAction=await page.locator('.sw-campaigns [data-sw-go=campaigns]').boundingBox();
  assert(campaignAction.y+campaignAction.height<=campaignCard.y+campaignCard.height,'campaign action clipped');
  const points=page.locator('[data-sw-point]'),selected=page.locator('[data-sw-point][aria-pressed=true]');
  assert.equal(await points.count(),30);
  assert.equal(await selected.count(),0);
  assert.equal(await page.locator('.sw-chart-reveal').evaluate(el=>getComputedStyle(el).animationName),'none');
  const previousDay=await points.nth(28).getAttribute('data-sw-point');
  await points.nth(28).click();await settled();
  assert.equal(await selected.getAttribute('data-sw-point'),previousDay);
  assert.equal(await page.locator('.sw-metric').textContent(),'18');
  assert.equal(await page.locator('.sw-links .sw-donut-number').textContent(),'7');
  assert.match(await page.locator('.sw-links .sw-source').textContent(),/Instagram/);
  assert.match(await page.locator('.sw-campaign-list').textContent(),/4 ouvertures ce jour-là/);
  const guideStyle=await selected.locator('.sw-day-guide').evaluate(el=>{
    const style=getComputedStyle(el);return [style.visibility,style.strokeDasharray,style.stroke];
  });
  assert.equal(guideStyle[0],'visible');assert.notEqual(guideStyle[1],'none');assert.notEqual(guideStyle[2],'none');
  const guide=await selected.locator('line').evaluate(el=>[el.x1.baseVal.value,el.x2.baseVal.value,el.y1.baseVal.value,el.y2.baseVal.value]);
  assert.equal(guide[0],guide[1]);assert(guide[3]>guide[2]);
  await shoot('statistiques-jour-selectionne');
  await selected.press('ArrowLeft');await settled();assert.equal(await page.locator('.sw-metric').textContent(),'19');
  assert.equal(await page.locator('.sw-links .sw-donut-number').textContent(),'0');
  await selected.press('ArrowRight');await settled();await page.click('[data-sw-go=links]');
  assert.equal(await page.locator('#sw-date').inputValue(),previousDay);
  assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),'7');
  await page.emulateMedia({reducedMotion:'no-preference'});await page.click('#sw-tab-overview');
  const reveal=await page.locator('.sw-chart-reveal').elementHandle();
  assert.equal(await reveal.evaluate(el=>getComputedStyle(el).animationName),'sw-draw-chart');
  await selected.press('End');await settled();assert.equal(await page.locator('.sw-metric').textContent(),'17');
  assert.equal(await page.locator('.sw-campaign').count(),3);
  assert.equal(await page.locator('.sw-chart-reveal').count(),0);await reveal.dispose();
  await page.emulateMedia({reducedMotion:'reduce'});
  assert.equal(await page.locator('#navigation-tabs [data-tab=dashboard]').count(),0);
  assert.equal(await page.locator('#navigation-tabs [data-tab=statistics]').count(),1);
  const chartPath=await page.locator('.sw-series').getAttribute('d');await page.click('[data-sw-metric=visits]');assert.notEqual(await page.locator('.sw-series').getAttribute('d'),chartPath);assert.equal(await page.locator('.sw-series').count(),1);
  await page.selectOption('#sw-period','month');await page.locator('.sw-overview').waitFor();await page.selectOption('#sw-period','30');await page.locator('.sw-overview').waitFor();await page.selectOption('#sw-period','day');await settled();
  await page.click('#sw-tab-links');await page.locator('.sw-row').first().waitFor();assert.equal(await page.locator('.sw-row').count(),3);
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
  await page.locator('#sw-date').fill(today);await settled();await page.locator('.sw-row').first().waitFor();
  await page.click('#sw-tab-visits');assert((await page.locator('.sw-detail-toolbar').textContent()).includes('Visites de la page'));
  await page.click('#sw-tab-campaigns');assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),'6');await shoot('statistiques-campagnes');
  await page.locator('#sw-tab-campaigns').focus();await page.keyboard.press('Home');assert.equal(await page.locator('#sw-tab-overview').getAttribute('aria-selected'),'true');
  for(const [width,height] of [[1366,768],[1440,900],[390,844],[320,700]]){
    await page.setViewportSize({width,height});await noOverflow();
    await page.waitForFunction(()=>{const node=document.querySelector('.sw-time-chart');return node.clientWidth===node.querySelector('svg').viewBox.baseVal.width;});
    const ticks=await page.locator('.sw-day-tick').evaluateAll(nodes=>nodes.map(n=>{
      const {left,right}=n.getBoundingClientRect();return {left,right,text:n.textContent};
    }));
    assert(ticks.length>=3);assert(ticks.every(t=>!/\d{4}/.test(t.text)));
    assert(ticks.every((t,i)=>!i||t.left>=ticks[i-1].right),'overlapping ticks at '+width);
    await points.first().click();await settled();assert.equal(await selected.getAttribute('data-sw-point'),await points.first().getAttribute('data-sw-point'));
    await selected.press('End');await settled();await page.click('#sw-tab-links');await noOverflow();await page.click('#sw-tab-overview');
  }
  await page.setViewportSize({width:1920,height:1080});await page.selectOption('#theme-select','light');await noOverflow(true);await shoot('statistiques-theme-clair');
  for(const tab of ['visits','links','campaigns','copies']){
    await page.click('#sw-tab-'+tab);
    await page.locator('.sw-evolution > summary').click();
    await page.locator('.sw-time-chart svg').waitFor();
    assert.equal(await page.locator('.sw-chart-table').count(),0);
    assert.equal(await page.locator('#statistics-legacy').isVisible(),false);
    const path=await page.locator('.sw-series').getAttribute('d');
    const dates=await points.evaluateAll(nodes=>nodes.map(node=>node.dataset.swPoint));
    await points.nth(28).click();await settled();
    await page.waitForFunction(day=>document.querySelector('#sw-date')?.value===day&&document.querySelector('#sw-panel').getAttribute('aria-busy')==='false',dates[28]);
    assert.equal(await selected.getAttribute('data-sw-point'),dates[28]);
    assert.equal(await page.locator('.sw-series').getAttribute('d'),path);
    assert.equal(await page.locator('.sw-evolution').getAttribute('open'),'');
    assert((await page.locator('.sw-chart-value').textContent()).includes(' · '));
    await selected.press('End');await settled();
    await page.waitForFunction(day=>document.querySelector('#sw-date')?.value===day&&document.querySelector('#sw-panel').getAttribute('aria-busy')==='false',dates.at(-1));
    if(tab==='copies'){
      assert.equal(await page.locator('#sw-context .sw-donut-number').textContent(),'5');
      await shoot('statistiques-codes-promos');
      await page.locator('#sw-search').fill('AUTOMNE10');assert.equal(await page.locator('.sw-row').count(),1);
      await page.locator('#sw-search').fill('absent');assert.equal(await page.locator('.sw-row').count(),0);
      await page.click('[data-sw-reset]');
    }
    await page.locator('.sw-evolution > summary').click();
  }
  await page.locator('#sw-tab-copies').focus();await page.keyboard.press('Home');
  assert.equal(await page.locator('#sw-tab-overview').getAttribute('aria-selected'),'true');
  await page.keyboard.press('End');assert.equal(await page.locator('#sw-tab-copies').getAttribute('aria-selected'),'true');
  await page.setViewportSize({width:320,height:700});await noOverflow();
  await page.locator('.sw-evolution > summary').click();await page.locator('.sw-time-chart svg').waitFor();
  await noOverflow();await shoot('statistiques-codes-promos-mobile');
  await page.click('#sw-tab-overview');await page.setViewportSize({width:1920,height:1080});await noOverflow(true);
  const merchantRequests=requests.filter(path=>/amazon|domadoo|affiliation\//.test(path));assert.deepEqual(merchantRequests,[]);
  // Force an HTTP error, then a slower stale response: navigation remains usable.
  await page.route('**/api/stats/workspace?**',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Test indisponibilité'})}));
  await page.click('#navigation-tabs [data-tab=statistics]');await page.locator('[data-sw-retry]').waitFor();await page.click('#sw-tab-links');assert.equal(await page.locator('.sw-row').count(),0);
  await page.unroute('**/api/stats/workspace?**');await page.click('[data-sw-retry]');await page.locator('.sw-row').first().waitFor();
  await page.route('**/api/stats/workspace?**',async route=>{if(new URL(route.request().url()).searchParams.get('date')==='2001-01-01')await new Promise(r=>setTimeout(r,350));await route.continue();});
  await page.locator('#sw-date').fill('2001-01-01');await page.click('#sw-tab-campaigns');await page.locator('.sw-empty').waitFor();assert.equal(await page.locator('#sw-tab-campaigns').getAttribute('aria-selected'),'true');await page.unroute('**/api/stats/workspace?**');
  // Add a large history only to this disposable SQLite file; verify bounded DOM.
  execFileSync(python,['-c',"import sqlite3,sys;db=sqlite3.connect(sys.argv[1]);db.executemany('INSERT INTO counts VALUES(?,?,?,?,?)',[(sys.argv[2],'youtube','tracked','tracked:tk_'+str(i).zfill(16)+':12',1) for i in range(10000)]);db.commit()",join(temp,'stats.db'),today]);
  await page.locator('#sw-date').fill(today);await settled();await page.locator('.sw-row').first().waitFor();await page.click('#sw-tab-links');
  const started=performance.now();assert((await page.locator('#sw-result-count').textContent()).includes('10'));assert(await page.locator('.sw-row').count()<30);
  await page.locator('#sw-results').focus();await page.keyboard.press('End');assert.equal(await page.locator('.sw-row:focus').getAttribute('data-sw-index'),'10002');
  await page.locator('#sw-search').fill('9999');assert.equal(await page.locator('.sw-row').count(),1);const largeMs=Math.round(performance.now()-started);
  await page.click('#navigation-tabs [data-tab=tracked-links]');await page.locator('#tracked-links.active').waitFor();
  await page.evaluate(()=>location.hash='dashboard');await page.locator('#statistics.active').waitFor();await page.locator('#sw-panel[aria-busy=false]').waitFor();
  assert.deepEqual(errors,[]);
  const report={fullHD,largeHistoryRows:10003,largeHistoryInteractionMs:largeMs,javascriptErrors:errors,merchantRequests,checks:'navigation, units, sources, homonyms, filters, selection, animation, reduced motion, keyboard, 5 viewport sizes, both themes, detail charts, promo codes, error/retry, delayed response, large history, old hash'};
  if(screenshots)writeFileSync(join(screenshots,'validation-navigateur.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser?.close();server.kill();await new Promise(r=>server.exitCode!==null?r():server.once('exit',r));rmSync(temp,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
