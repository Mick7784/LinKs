// Disposable fixtures and presentation checks only; never contacts production.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');const {mkdtempSync,rmSync,mkdirSync,readFileSync}=require('node:fs');const {tmpdir}=require('node:os');const {join,resolve}=require('node:path');
const masters=['brand.svg','brand-light.svg','mark.svg'].map(name=>readFileSync(resolve(__dirname,'../admin',name),'utf8').match(/href="(data:image\/png;base64,[^"]+)"/)[1]);assert(masters.every(value=>value===masters[0]),'Official raster K must be identical in every variant');
(async()=>{const temp=mkdtempSync(join(tmpdir(),'links-ui-'));let browser;const origin='http://127.0.0.1:8081';
execFileSync(process.env.PYTHON_PATH||'python3',[resolve(__dirname,'fixtures.py'),join(temp,'stats.db')]);
const server=spawn(process.env.PYTHON_PATH||'python3',[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:'ignore'});
const api=async(path,data)=>{const r=await fetch(origin+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(r.ok,await r.clone().text());return r.json()};
try{for(let i=0;i<100;i++){try{if((await fetch(origin+'/healthz')).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
const promo=await api('/api/content',{type:'promo',title:'Reolink — Offre partenaire',internal_name:'Reolink — Offre partenaire',url:'https://example.com/reolink',image:'/assets/link-shopping.webp',promo_code:'DOMOTIK5',start_at:'2026-10-01T00:00:00Z',end_at:'2026-12-31T23:00:00Z'});
await api('/api/content',{type:'classic',title:'La communauté domotique',internal_name:'La communauté domotique',url:'https://example.com/discord',icon:'discord'});
const guide=await api('/api/content',{type:'classic',title:'Le guide Home Assistant',internal_name:'Le guide Home Assistant',url:'https://example.com/home-assistant'});
const studio=await api('/api/content',{type:'classic',title:'Les coulisses sur Instagram',internal_name:'Les coulisses sur Instagram',url:'https://example.com/instagram'});
const story=await api(`/api/content/${promo.id}/story-link`,{});
execFileSync(process.env.PYTHON_PATH||'python3',['-c',`import sqlite3,sys,json;from datetime import datetime,timedelta;from zoneinfo import ZoneInfo
db=sqlite3.connect(sys.argv[1]);day=datetime.now(ZoneInfo('Europe/Paris')).date();db.execute("UPDATE settings SET value='DomotiK Studio' WHERE key='profile.name'")
rows=[((day-timedelta(days=i)).isoformat(),source,kind,link,total) for i in range(30) for source in ['direct-inconnu','instagram','youtube'] for kind,link,total in [('view','',25+(i*17)%80),('click','block:'+sys.argv[2],8+(i*7)%21),('impression','block:'+sys.argv[2],14+(i*11)%53)]]
rows += [((day-timedelta(days=i)).isoformat(),'instagram','click','block:'+sys.argv[4],4+i%5) for i in range(30)];rows += [((day-timedelta(days=i)).isoformat(),'youtube','click','block:'+sys.argv[5],2+i%3) for i in range(30)];rows.append((day.isoformat(),'instagram-story','story','story:'+sys.argv[3]+':10',42));rows.append((day.isoformat(),'instagram','promo_code_copy',json.dumps({'id':sys.argv[2],'name':'Reolink — Offre partenaire','code':'DOMOTIK5','timestamp':day.isoformat()+'T10:00:00+00:00'}),12));db.executemany('INSERT INTO counts VALUES(?,?,?,?,?)',rows);db.commit()`,join(temp,'stats.db'),promo.id,story.url.split('/go/')[1],guide.id,studio.id]);
browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1600,height:1080}});let errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(origin);await page.waitForSelector('#chart svg');
const installedVersion=(await api('/api/settings')).app_version;assert.match(installedVersion,/^V\d+\.\d+$/);await page.waitForFunction(version=>document.getElementById('admin-version')?.textContent===`LinKs · ${version}`,installedVersion);assert(await page.locator('#admin-version').isVisible());
assert.equal(await page.locator('.chart-bucket').count(),14);
assert.equal(await page.locator('.brand').getAttribute('href'),'https://github.com/Mick7784/links');assert.equal(await page.locator('.brand').getAttribute('target'),'_blank');assert.equal(await page.locator('.brand').getAttribute('rel'),'noopener noreferrer');
assert.equal(await page.locator('.product-brand').getAttribute('alt'),'LinKs by DomotiK Studio');
assert.equal(await page.locator('.studio-eyebrow,.instance-context').count(),0,'Only the product logo remains in the sidebar header');
assert(await page.locator('.product-brand').isVisible());
assert.equal(await page.locator('.topbar .breadcrumb-brand').count(),1);
assert(await page.locator('.sidebar').evaluate(e=>getComputedStyle(e,'::before').backgroundImage.includes('linear-gradient')),'sidebar color signature absent');
assert(await page.locator('.tabs button.active').evaluate(e=>getComputedStyle(e).boxShadow.includes('inset')),'selected navigation identity absent');
assert.equal(await page.locator('#dashboard .analytics-kpis article').first().evaluate(e=>getComputedStyle(e,'::before').height),'2px');

await page.locator('[data-tab=statistics]').click();await page.locator('#statistics.active').waitFor();await page.selectOption('#analysis-scope','public');await page.locator('#statistics #chart svg').waitFor();assert.equal(await page.locator('#sources .donut-segment').count(),4);assert.equal(await page.locator('#sources .source-row').count(),4);
assert.equal(await page.locator('#story-total').textContent(),'42');assert.equal(await page.locator('#promo-copy-total').textContent(),'12');assert.equal(await page.locator('#story-list .engagement-row,#promo-copy-list .engagement-row').count(),2);
await page.locator('.chart-bucket').last().hover();assert(await page.locator('.chart-tooltip').isVisible());assert.match(await page.locator('.chart-tooltip').textContent(),/Visites.*Clics/);
assert.equal(await page.locator('#sources .source-detail').count(),0);assert.equal(await page.locator('#sources svg').getAttribute('role'),'img');
const geometry=await page.locator('.chart-bucket').evaluateAll(groups=>groups.map(g=>[...g.querySelectorAll('.animated-bar')].map(r=>({x:r.getAttribute('x'),width:r.getAttribute('width'),height:Number(r.getAttribute('height'))}))));assert(geometry.every(([a,b])=>a.x!==b.x&&a.width===b.width),'visits and clicks must be side by side');
assert.equal(await page.locator('.chart-grid').count(),5);assert.equal(await page.locator('.visits-bar').first().evaluate(e=>getComputedStyle(e).fill),'rgb(34, 211, 238)');assert.equal(await page.locator('.clicks-bar').first().evaluate(e=>getComputedStyle(e).fill),'rgb(139, 92, 246)');await page.evaluate(()=>{document.activeElement.blur();scrollTo(0,0)});
const publicBefore=await fetch('http://127.0.0.1:3003/api/public-config').then(r=>r.json());
const overflow=async()=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'horizontal overflow');
const nav=async id=>{if(await page.locator('#menu-toggle').isVisible())await page.locator('#menu-toggle').click();await page.locator(`[data-tab="${id}"]`).click();await page.locator(`#${id}.active`).waitFor()};
await nav('content');await page.locator('[data-section]').first().waitFor();assert.deepEqual(await page.locator('[data-section]').evaluateAll(nodes=>nodes.map(n=>n.dataset.section)),['classic','video','highlight']);
await page.locator('[data-section="classic"] [data-section-move="1"]').click();await page.waitForFunction(()=>document.querySelector('[data-section]').dataset.section==='video');await page.reload();await nav('content');await page.locator('[data-section]').first().waitFor();assert.equal(await page.locator('[data-section]').first().getAttribute('data-section'),'video');
await page.locator('[data-section="video"] [data-section-move="1"]').click();await page.waitForFunction(()=>document.querySelector('[data-section]').dataset.section==='classic');
const beforeOrder=await api('/api/content');const classicIds=beforeOrder.items.filter(x=>x.type==='classic').map(x=>x.id);await page.locator('[data-section="classic"] .list-item').first().locator('[data-action="down"]').click();await page.waitForTimeout(150);const afterOrder=await api('/api/content');assert.deepEqual(afterOrder.items.filter(x=>x.type==='classic').map(x=>x.id),[classicIds[1],classicIds[0],...classicIds.slice(2)]);
await page.locator('[data-section="classic"] .list-item').first().locator('[data-action="down"]').click();await page.waitForTimeout(150);
const videoBefore=(await api('/api/settings')).video_enabled;await page.locator('#section-video-enabled').setChecked(!videoBefore);await page.waitForFunction(expected=>document.querySelector('#section-video-enabled').disabled===false&&document.querySelector('#section-video-enabled').checked===expected,!videoBefore);assert.equal((await api('/api/settings')).video_enabled,!videoBefore);await page.reload();await nav('content');await page.locator('[data-section]').first().waitFor();assert.equal(await page.locator('#section-video-enabled').isChecked(),!videoBefore);await page.locator('#section-video-enabled').setChecked(videoBefore);await page.waitForTimeout(150);
await page.locator('[data-video-settings]').click();await page.locator('#settings.active').waitFor();assert.equal(await page.evaluate(()=>document.activeElement.name),'video_channel_id');await nav('content');await page.locator('.agenda-event').first().waitFor();assert.equal(await page.locator('#content #promo-planning').count(),1);
const month=await page.locator('#timeline-month').textContent();await page.locator('#timeline-next').click();assert.notEqual(await page.locator('#timeline-month').textContent(),month);await page.locator('#timeline-prev').click();assert.equal(await page.locator('#timeline-month').textContent(),month);
await page.evaluate(()=>renderTimeline([]));assert.match(await page.locator('#promo-planning').textContent(),/Aucune promotion/);await nav('dashboard');
if(process.env.UI_SCREENSHOTS)mkdirSync(process.env.UI_SCREENSHOTS,{recursive:true});
await page.selectOption('#period','30');await page.evaluate(()=>loadStats());await page.waitForFunction(()=>document.querySelectorAll('.chart-bucket').length===30);
for(const theme of ['dark','light']){await page.selectOption('#theme-select',theme);assert.equal(await page.locator('html').getAttribute('data-theme'),theme);await overflow();assert(await page.locator('.product-brand').evaluate(i=>i.complete&&i.naturalWidth>0));assert.equal(await page.locator('.analytics-kpis article').count(),5);assert.equal(await page.locator('.campaign-metrics>span').count(),2);
const layout=await page.locator('.analytics-kpis article').evaluateAll(items=>items.map(i=>i.getBoundingClientRect().top));assert(layout.every(y=>y===layout[0]));
if(process.env.UI_SCREENSHOTS){await page.waitForTimeout(650);await page.evaluate(()=>{document.activeElement.blur();scrollTo(0,0);document.getElementById('notice').textContent=''});await page.screenshot({path:join(process.env.UI_SCREENSHOTS,`links-desktop-${theme}.png`),fullPage:true,animations:'disabled'});await nav('content');await page.locator('[data-section]').first().waitFor();await page.evaluate(()=>{document.activeElement.blur();scrollTo(0,0)});await page.screenshot({path:join(process.env.UI_SCREENSHOTS,`links-blocks-${theme}.png`),fullPage:true});await nav('dashboard');}}
await page.selectOption('#theme-select','system');await page.emulateMedia({colorScheme:'dark'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark');await page.emulateMedia({colorScheme:'light'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');await page.reload();assert.equal(await page.locator('#theme-select').inputValue(),'system');await page.locator('#chart svg').waitFor();
for(const period of ['14','30','90','7']){await page.selectOption('#period',period);await page.evaluate(()=>loadStats());await page.locator('#chart svg').waitFor();}
await page.selectOption('#source','instagram');await page.evaluate(()=>loadStats());assert.equal(await page.locator('#promo-copies').textContent(),'12');await page.selectOption('#source','');
for(const width of [768,390,320]){await page.setViewportSize({width,height:844});assert.equal(await page.locator('#admin-version').isVisible(),width>760,'sidebar footer follows existing mobile visibility rules');for(const id of ['dashboard','content','buttons','archives','settings']){await nav(id);await overflow();}await nav('dashboard');}
await page.setViewportSize({width:390,height:844});await page.selectOption('#theme-select','dark');await page.locator('#chart svg').waitFor();if(process.env.UI_SCREENSHOTS)await page.waitForTimeout(650);if(process.env.UI_SCREENSHOTS)await page.screenshot({path:join(process.env.UI_SCREENSHOTS,'links-mobile.png'),fullPage:true,animations:'disabled'});
// Presentation-only API fixtures cover missing optional data and zero chronology.
const today=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Paris'});
let fixture={rows:[],stories:[],promo_code_copies:[],campaign_metrics:[]};
await page.route('**/api/stats?*',route=>route.fulfill({json:fixture}));
const refresh=async()=>{await page.selectOption('#period','14');await page.evaluate(()=>loadStats(true));await page.waitForFunction(()=>document.querySelectorAll('.chart-bucket').length===14);};
await refresh();assert.equal(await page.locator('.chart-bucket').count(),14);assert.equal(await page.locator('.animated-bar[height="0"]').count(),28);assert.equal(await page.locator('#sources .donut-segment').count(),0);assert.equal(await page.locator('#story-list .engagement-row,#promo-copy-list .engagement-row').count(),0);
fixture={rows:[{day:today,source:'direct-inconnu',kind:'view',link:'',total:1}],stories:[{promotion_id:'one',label:'Une Story',total:1,source:'instagram-story',day:today}],promo_code_copies:[{id:'one',name:'Une offre',code:'CODE',source:'direct-inconnu',total:1,day:today}],campaign_metrics:[]};
await page.selectOption('#period','7');await page.evaluate(()=>loadStats(true));await page.waitForFunction(()=>document.querySelector('#story-total').textContent==='1');assert.equal(await page.locator('#story-list .engagement-row,#promo-copy-list .engagement-row').count(),2);await nav('statistics');await page.selectOption('#analysis-scope','copies');assert((await page.locator('#promo-copy-list .engagement-copy strong').textContent()).includes('CODE'));assert.equal(await page.locator('#promo-copy-list details').count(),0);await nav('dashboard');
fixture.rows.push({day:today,source:'direct-inconnu',kind:'click',link:'one',total:2});
await refresh();assert.equal(await page.locator('.chart-bucket').last().locator('.animated-bar').count(),2,'both series remain on chart');
await page.locator('.chart-bucket').last().click();assert(await page.locator('.chart-tooltip').isVisible());

fixture.rows=Array.from({length:12},(_,i)=>({day:today,source:'source-'+i,kind:'view',link:'',total:i+1}));fixture.stories.push({promotion_id:'two',label:'Autre Story',total:2,source:'instagram-story',day:today});fixture.promo_code_copies.push({id:'two',name:'Autre offre',code:'AUTRE',source:'source-1',total:2,day:today});
await refresh();await nav('statistics');await page.selectOption('#analysis-scope','sources');assert.equal(await page.locator('#sources .source-row').count(),13);assert.equal(await page.locator('#source-details').count(),0);await nav('dashboard');assert.equal(await page.locator('#story-list .engagement-row,#promo-copy-list .engagement-row').count(),4);await overflow();
await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator('.animated-bar').first().evaluate(e=>getComputedStyle(e).animationName),'none');
if(process.env.UI_SCREENSHOTS){await nav('content');await page.locator('[data-section]').first().waitFor();await page.screenshot({path:join(process.env.UI_SCREENSHOTS,'links-blocks-mobile.png'),fullPage:true});}assert.deepEqual(await fetch('http://127.0.0.1:3003/api/public-config').then(r=>r.json()),publicBefore,'UI changed public configuration');// Private tracked links live only in admin, with expandable source donuts.
await nav('content');
await page.locator('[data-action="new-tracked"]').click();
await page.locator('#tracked-form [name="name"]').fill('Produit temporaire suivi');
await page.locator('#tracked-form [name="url"]').fill('https://example.com/tracked-product');
await page.locator('#tracked-form button[type="submit"]').click();
await page.locator('.tracked-item').filter({hasText:'Produit temporaire suivi'}).waitFor();
const trackedRow=page.locator('.tracked-item').filter({hasText:'Produit temporaire suivi'});
await trackedRow.locator('[data-open-statistics="shared"]').click();await page.locator("#statistics.active").waitFor();assert.equal(await page.locator("#analysis-search").inputValue(),"Produit temporaire suivi");await nav("content");
await page.locator('#tracked-manage-sources').click();
await page.locator('#tracked-source-form [name="name"]').fill('Canal navigateur');
await page.locator('#tracked-source-form button[type="submit"]').click();
await page.locator('#tracked-source-list input[value="Canal navigateur"]').waitFor();
await page.locator('[data-close-sources]').first().click();
assert(await trackedRow.locator('select option').filter({hasText:'Canal navigateur'}).count());
await overflow();
assert.deepEqual(errors,[]);console.log('PASS UI: desktop dark/light, system/persistence, five KPI, campaign metrics, periods/source filters, navigation at 768/390/320, public config unchanged');
}finally{if(browser)await browser.close();server.kill();await new Promise(r=>server.once('exit',r));rmSync(temp,{recursive:true,force:true})}})().catch(e=>{console.error(e);process.exitCode=1});
