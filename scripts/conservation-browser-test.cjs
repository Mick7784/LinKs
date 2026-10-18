// V1.310 cross-surface regressions; disposable fixture database, no deployed data.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process'),{createServer}=require('node:http');
const {readFileSync,mkdtempSync,rmSync,mkdirSync}=require('node:fs'),{join,resolve,extname}=require('node:path'),{tmpdir}=require('node:os');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-conservation-')),root=resolve(__dirname,'..'),python=process.env.PYTHON_PATH||'python3';
 const admin='http://127.0.0.1:8081',origin='http://127.0.0.1:18080';
 execFileSync(python,[join(__dirname,'fixtures.py'),join(temp,'analytics.db'),origin]);
 const backend=spawn(python,[join(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:join(temp,'analytics.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:'inherit'});
 const site=createServer(async(req,res)=>{try{
  res.setHeader('Content-Security-Policy',"default-src 'self';script-src 'self';style-src 'self';img-src 'self' https://i.ytimg.com;object-src 'none';base-uri 'self';frame-ancestors 'none'");
  const path=new URL(req.url,origin).pathname;
  if(path.startsWith('/api/')||path.startsWith('/assets/')||path.startsWith('/uploads/')||path==='/metrics'){
   const chunks=[];for await(const chunk of req)chunks.push(chunk);const body=Buffer.concat(chunks);
   const r=await fetch('http://127.0.0.1:3003'+req.url,{method:req.method,headers:{Origin:req.headers.origin||origin,'Content-Type':'application/json','User-Agent':req.headers['user-agent']||''},body:body.length?body:undefined});
   res.statusCode=r.status;res.setHeader('Content-Type',r.headers.get('content-type')||'application/json');res.end(Buffer.from(await r.arrayBuffer()));return;
  }
  const file=path==='/'?'index.html':path.slice(1);if(!/^[a-z0-9.-]+$/.test(file)){res.writeHead(404).end();return}
  const types={'.html':'text/html','.js':'application/javascript','.css':'text/css','.json':'application/json'};
  res.setHeader('Content-Type',types[extname(file)]||'application/octet-stream');res.end(readFileSync(join(root,'site',file)));
 }catch{res.writeHead(404).end()}});
 let browser;
 const api=async(path,data,method='POST')=>{const r=await fetch(admin+path,{method,headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data===undefined?undefined:JSON.stringify(data)});assert(r.ok,path+': '+await r.clone().text());return r.status===204?null:r.json()};
 try{
  for(let i=0;i<100;i++){try{if((await fetch(admin+'/healthz')).ok)break}catch{}await new Promise(r=>setTimeout(r,100));if(i===99)throw Error('Backend unavailable')}
  await new Promise(r=>site.listen(18080,'127.0.0.1',r));await api('/api/settings',{video_enabled:false});
  const first=await api('/api/content',{type:'promo',internal_name:'Campagne bibliothèque',title:'Votre maison connectée',url:'https://example.org/one',image:'system:smarthome',promo_code:'FIRST'});
  await api('/api/content',{type:'promo',internal_name:'Deuxième campagne',title:'Autre offre',url:'https://example.org/two',image:'system:shopping',promo_code:'SECOND'});
  const tracked=await api('/api/tracked-links',{name:'Privé permanent',url:'https://example.org/private'});
  const sources=(await api('/api/tracking-sources',undefined,'GET')).items;
  const token=await api('/api/tracked-links/'+tracked.id+'/token',{source_id:sources[0].id});
  await fetch('http://127.0.0.1:3003/'+token.code,{redirect:'manual',headers:{'User-Agent':'Mozilla/5.0'}});
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox']}: {})});
  const context=await browser.newContext({userAgent:'Mozilla/5.0 Links V1.310 test'}),page=await context.newPage(),errors=[],csp=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&/Content Security Policy|violates.*directive/.test(m.text()))csp.push(m.text())});
  await page.goto(admin);await page.waitForSelector('.campaign-card img');await page.locator('.campaign-card img').first().evaluate(img=>img.complete?null:new Promise(r=>{img.onload=r;img.onerror=r}));
  assert(await page.locator('.campaign-card img').first().evaluate(img=>img.naturalWidth>0),'Library image must resolve in dashboard');
  assert.equal(await page.locator('.studio-eyebrow,.instance-context').count(),0);
  for(const width of [1440,768,390,320]){await page.setViewportSize({width,height:1000});for(const theme of ['light','dark','system']){
   await page.selectOption('#theme-select',theme);await page.waitForTimeout(180);
   assert.equal(await page.locator('.theme-control').evaluate(n=>getComputedStyle(n).display),'flex');
   assert(await page.locator('#theme-icon svg').isVisible());
   const surfaces=await page.locator('.analytics-kpis article').evaluateAll(nodes=>nodes.map(n=>({background:getComputedStyle(n).backgroundImage,color:getComputedStyle(n).backgroundColor,border:getComputedStyle(n).borderBottomWidth})));
   assert(surfaces.every(x=>x.background==='none'&&x.color===surfaces[0].color&&x.border===surfaces[0].border),'KPI rest surfaces must match');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Admin overflow '+width);
   if(process.env.V1310_SCREENSHOTS&&[1440,390].includes(width)&&theme!=='system'){mkdirSync(process.env.V1310_SCREENSHOTS,{recursive:true});await page.screenshot({path:join(process.env.V1310_SCREENSHOTS,'admin-'+theme+'-'+width+'.png'),fullPage:true})}
  }}
  await page.setViewportSize({width:1440,height:1000});await page.locator('[data-tab=content]').click();await page.locator('.tracked-item').waitFor();
  await page.locator('[data-open-statistics=shared]').first().click();await page.locator('#statistics.active').waitFor();assert.equal(await page.locator('#analysis-scope').inputValue(),'shared');await page.selectOption('#period','7');await page.locator('#story-list').waitFor();

  await page.locator('[data-tab=appearance]').click();await page.getByRole('button',{name:'Créer un thème',exact:true}).click();
  // Enum controls must update without referencing the image upload guard.
  const enumLabel=await page.evaluate(async()=>{const {schema}=await LinksTheme.ready;return Object.values(schema).find(x=>x.type==='enum').label});
  const select=page.getByRole('combobox',{name:enumLabel,exact:true,includeHidden:true});await select.evaluate(n=>{n.closest('details').open=true});await select.selectOption({index:1});
  await page.goto(origin);await page.waitForSelector('.carousel-slide:nth-child(2)');
  for(const width of [1440,390]){await page.setViewportSize({width,height:1000});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));if(process.env.V1310_SCREENSHOTS)await page.screenshot({path:join(process.env.V1310_SCREENSHOTS,'public-'+width+'.png'),fullPage:true})}
  await page.clock.install();await page.goto(origin);await page.waitForSelector('.carousel-slide:nth-child(2)');await page.locator('.offer-code').first().focus();
  await page.clock.runFor(20000);assert.equal(await page.locator('.carousel-slide').first().getAttribute('aria-hidden'),'false','Focus must keep the offer visible');
  await page.locator('.carousel-pause').click();await page.locator('#profile-name').evaluate(n=>{n.tabIndex=-1;n.focus()});await page.mouse.move(0,0);await page.clock.runFor(20000);
  assert.equal(await page.locator('.carousel-slide').first().getAttribute('aria-hidden'),'false','Explicit pause must persist');
  assert.deepEqual(csp,[],'No blocked application scripts/styles');assert.deepEqual(errors,[]);
  console.log('PASS V1.310: library images, stable KPI, theme icons/layout, private periods, enum controls, CSP, responsive public and focus/pause carousel');
 }finally{await browser?.close();await new Promise(r=>site.close(r));backend.kill();await new Promise(r=>backend.once('exit',r));rmSync(temp,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exit(1)});
