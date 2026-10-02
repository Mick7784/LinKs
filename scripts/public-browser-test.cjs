// Isolated integration fixtures only: no production content or database is modified.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {createServer}=require('node:http');
const {spawn}=require('node:child_process');
const {readFileSync,mkdtempSync,rmSync,mkdirSync}=require('node:fs');
const {resolve,join}=require('node:path');
const {tmpdir}=require('node:os');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-public-')),origin='http://127.0.0.1:18080',admin='http://127.0.0.1:8081';
 const backend=spawn(process.env.PYTHON_PATH||'python3',[resolve(__dirname,'analytics.py')],{env:{...process.env,ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads'),ANALYTICS_ORIGIN:origin},stdio:'inherit'});
 // Recorded real video metadata. Network-independent image responses reuse a real repo asset in tests only.
 const video={title:'Levoit Eleva 300X : enfin un purificateur vraiment autonome ?',url:'https://www.youtube.com/watch?v=B-v11zKyr8U',thumbnail:'https://i.ytimg.com/vi/B-v11zKyr8U/mqdefault.jpg',published:'2026-09-23T16:37:02.000Z'};
 const asset=readFileSync(resolve(__dirname,'../site/assets/portrait.webp'));
 let browser,videoAvailable=true;
 const request=async(path,data,method='POST')=>{const r=await fetch(admin+path,{method,headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});if(!r.ok)throw Error(path+': '+await r.text());return r.status===204?null:r.json()};
 const partner=createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end('<title>Partner test destination</title>')});
 const site=createServer(async(req,res)=>{try{
  const url=new URL(req.url,origin);res.setHeader('Content-Security-Policy',"default-src 'self';script-src 'self';style-src 'self';img-src 'self' https://i.ytimg.com;object-src 'none';base-uri 'self';frame-ancestors 'none'");
  if(url.pathname==='/latest-video.json'){res.writeHead(videoAvailable?200:502,{'Content-Type':'application/json'});return res.end(JSON.stringify(videoAvailable?video:{error:'unavailable'}))}
  if(url.pathname==='/api/public-config'||url.pathname==='/metrics'||url.pathname.startsWith('/go/')||url.pathname.startsWith('/uploads/')){
   const chunks=[];for await(const c of req)chunks.push(c);const body=Buffer.concat(chunks);
   const r=await fetch('http://127.0.0.1:3003'+req.url,{method:req.method,headers:{'Content-Type':req.headers['content-type']||'application/json',Origin:req.headers.origin||origin,'User-Agent':req.headers['user-agent']||'Mozilla/5.0'},body:body.length?body:undefined,redirect:'manual'});
   res.statusCode=r.status;for(const name of ['content-type','location'])if(r.headers.has(name))res.setHeader(name,r.headers.get(name));return res.end(Buffer.from(await r.arrayBuffer()))
  }
  const files={'/':['index.html','text/html'],'/style.css':['style.css','text/css'],'/icons.css':['icons.css','text/css'],'/app.js':['app.js','application/javascript'],'/config.js':['config.js','application/javascript'],'/metrics.js':['metrics.js','application/javascript'],'/assets/studio-links.webp':['assets/studio-links.webp','image/webp'],'/assets/logo.webp':['assets/logo.webp','image/webp'],'/assets/portrait.webp':['assets/portrait.webp','image/webp']};for(const name of ['community','instagram','shopping','smarthome','collaboration'])files['/assets/link-'+name+'.webp']=['assets/link-'+name+'.webp','image/webp'];const file=files[url.pathname];if(!file){res.writeHead(404);return res.end()}
  res.setHeader('Content-Type',file[1]);res.end(readFileSync(resolve(__dirname,'../site',file[0])));
 }catch(e){res.writeHead(500);res.end(e.message)}});
 try{
  for(let i=0;i<100;i++){try{if((await fetch(admin+'/healthz')).ok)break}catch{}await new Promise(r=>setTimeout(r,100));if(i===99)throw Error('Backend did not start')}
  await new Promise(r=>site.listen(18080,'127.0.0.1',r));await new Promise(r=>partner.listen(18082,r));
  const uploaded=await request('/api/upload',{type:'image/webp',data:'data:image/webp;base64,'+asset.toString('base64')});
  const block=(name,extra={})=>({type:'promo',internal_name:name,title:name,description:'Fixture de vérification : cette description longue vérifie la lecture complète sur un petit écran.',url:'https://partner.example/'+encodeURIComponent(name),image:uploaded.url,badge:'Partenaire',cta:'Consulter cette offre de vérification',...extra});
  const first=await request('/api/content',block('Campagne test A',{promo_code:'DOMOTIK10'}));
  const second=await request('/api/content',block('Campagne test B'));
  const future=await request('/api/content',block('Campagne programmée',{start_at:new Date(Date.now()+86400000).toISOString(),end_at:new Date(Date.now()+172800000).toISOString()}));
  const expired=await request('/api/content',block('Campagne expirée',{start_at:new Date(Date.now()-172800000).toISOString(),end_at:new Date(Date.now()-86400000).toISOString()}));
  const draft=await request('/api/content',block('Brouillon',{draft:true}));
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox']}: {})});
  const context=await browser.newContext({userAgent:'Mozilla/5.0 Links integration test',reducedMotion:'reduce'});
  await context.route('https://i.ytimg.com/**',r=>r.fulfill({contentType:'image/webp',body:asset}));
  await context.route('https://partner.example/**',r=>r.fulfill({contentType:'text/html',body:'<title>Partner test destination</title>'}));
  await context.route('https://discord.gg/**',r=>r.fulfill({contentType:'text/html',body:'<title>Discord destination fixture</title>'}));
  await context.route('https://www.youtube.com/**',r=>r.fulfill({contentType:'text/html',body:'<title>YouTube destination</title>'}));
  const page=await context.newPage(),errors=[],consoleErrors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')consoleErrors.push(m.text())});
  const load=async(source='instagram')=>{await page.goto(origin+'/?utm_source='+source);await page.waitForSelector('.video-title');await page.waitForSelector('.carousel-slide .card');};
  await load();
  const config=await request('/api/public-config',undefined,'GET');
  assert.equal(await page.locator('#profile-name').textContent(),config.profile.name);
  assert.equal(await page.locator('#profile-tagline').textContent(),config.profile.tagline);
  assert.equal(await page.locator('#profile-description').textContent(),config.profile.description);
  for(const selector of ['#profile-avatar','#profile-logo','#footer-logo','.video-visual img','.offer-visual img'])assert(await page.locator(selector).first().evaluate(i=>i.complete&&i.naturalWidth>0),'Image missing: '+selector);
  assert.equal(await page.locator('.social').count(),config.socials.length);
  assert.deepEqual(await page.locator('#links a').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href'))),config.links.filter(x=>x.type==='classic').map(x=>x.url));
  assert.equal(await page.locator('.video-title').textContent(),video.title);
  assert.equal(await page.locator('.video-card').getAttribute('href'),video.url);
  assert.equal(await page.locator('.carousel-slide').count(),2);
  assert(!await page.locator('#offers').textContent().then(t=>['Campagne programmée','Campagne expirée','Brouillon'].some(x=>t.includes(x))));

  assert.equal(await page.locator('.offer-cta').count(),0);assert.equal(await page.locator('.offer-link').count(),2);
  assert.equal(await page.locator('.offer-code').count(),1);
  await context.grantPermissions(['clipboard-read','clipboard-write'],{origin});
  let offerPopups=0;page.on('popup',()=>offerPopups++);
  await page.locator('.offer-code').click();
  assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),'DOMOTIK10');
  assert((await page.locator('.offer-code').textContent()).includes('Copié !'));assert.equal(offerPopups,0);

  const active=()=>page.locator('.carousel-dots button[aria-current="true"]');
  await page.locator('.carousel-dots button').nth(1).click();assert.equal(await active().getAttribute('aria-label'),'Afficher l’offre 2 sur 2');
  await page.locator('.carousel-dots button').nth(0).click();assert.equal(await active().getAttribute('aria-label'),'Afficher l’offre 1 sur 2');
  await page.locator('.carousel-dots button').nth(1).click();await page.keyboard.press('ArrowLeft');assert.equal(await active().getAttribute('aria-label'),'Afficher l’offre 1 sur 2');
  const inactive=page.locator('.carousel-slide[aria-hidden="true"] a');assert.equal(await inactive.getAttribute('tabindex'),'-1');
  // Same passive touch handlers: swipe changes the existing transform-based carousel.
  await page.locator('#offers-track').dispatchEvent('touchstart',{touches:[{identifier:0,clientX:240}]});await page.locator('#offers-track').dispatchEvent('touchend',{changedTouches:[{identifier:0,clientX:120}]});assert.equal(await active().getAttribute('aria-label'),'Afficher l’offre 2 sur 2');
  for(const width of [320,360,390,768,1440]){
   await page.setViewportSize({width,height:900});await page.locator('#offers').scrollIntoViewIfNeeded();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Overflow at '+width);
   const composition=await page.evaluate(()=>{
    const box=s=>document.querySelector(s).getBoundingClientRect();
    const image=box('.offer-visual'),copy=box('.offer-copy'),header=box('.profile');
    const video=box('.video-visual'),details=box('.video-details');
    return {imageRight:image.right,imageBottom:image.bottom,imageWidth:image.width,copyLeft:copy.left,copyTop:copy.top,slideWidth:box(".carousel-slide .card").width,headerHeight:header.height,videoRight:video.right,detailsLeft:details.left};
   });
   const creative=await page.locator('.carousel-slide .offer-visual').first().evaluate(n=>{const r=n.getBoundingClientRect();return {ratio:r.width/r.height,fit:getComputedStyle(n.querySelector('img')).objectFit}});
   assert.equal(creative.fit,'cover');
   assert.equal(await page.locator('#offers-prev,#offers-next').count(),0);
   assert(composition.imageWidth<=composition.slideWidth,'Creative fits offer at '+width);
   assert(composition.slideWidth<=680,'Contained vertical column at '+width);
   const videoOverlay=await page.evaluate(()=>{const a=document.querySelector('.video-visual').getBoundingClientRect(),b=document.querySelector('.video-details').getBoundingClientRect();return b.top>=a.top&&b.bottom<=a.bottom+1});
   assert(videoOverlay,'Video text stays inside image at '+width);
   for(const selector of ['.social','.carousel-dots button','.offer-link']){const box=await page.locator(selector).first().boundingBox();assert(box.width>=44&&box.height>=44,'Touch size '+selector)}
   const rects=await page.locator('.card-title,.card-description,.video-title').evaluateAll(nodes=>nodes.filter(n=>!n.closest('.carousel-slide .card.visual .promo-copy')).map(n=>({scroll:n.scrollWidth,width:n.clientWidth})));assert(rects.every(x=>x.scroll<=x.width),'Truncated text '+width);
  }
  const art=await page.locator('#links .card').evaluateAll(nodes=>nodes.map(n=>getComputedStyle(n,'::before').backgroundImage));assert.equal(new Set(art).size,art.length,'Distinct thematic backgrounds');
  const dates=await page.evaluate(()=>{const holder=document.createElement('span');appendCampaignDates(holder,{start_at:'2026-10-01T12:00:00Z',end_at:'2026-10-31T12:00:00Z'});return [...holder.querySelectorAll('time')].map(n=>({text:n.textContent,date:n.dateTime}))});assert.equal(dates.length,2);assert(dates[0].text.startsWith('À partir du '));assert(dates[1].text.startsWith('Jusqu’au '));assert.equal(dates[1].date,'2026-10-31T12:00:00.000Z');
  assert(await page.locator('.carousel-slide[aria-hidden="false"] .offer-title').isVisible());assert(await page.locator('.carousel-slide[aria-hidden="false"] .offer-kicker').isVisible());
  const before=await request('/api/stats',undefined,'GET');
  assert.equal(offerPopups,0);
  const popupPromise=page.waitForEvent('popup');await page.locator('.carousel-slide[aria-hidden="false"] a').click();const popup=await popupPromise;await popup.waitForLoadState();assert.equal(popup.url(),block('Campagne test B').url);await popup.close();
  const videoPopupPromise=page.waitForEvent('popup');await page.locator('.video-card').click();const videoPopup=await videoPopupPromise;await videoPopup.waitForLoadState();assert.equal(videoPopup.url(),video.url);await videoPopup.close();
  const linkPopupPromise=page.waitForEvent('popup');await page.locator('#links a').first().click();const linkPopup=await linkPopupPromise;await linkPopup.waitForLoadState();assert.equal(linkPopup.url(),config.links.find(x=>x.type==='classic').url);await linkPopup.close();
  const socialPopupPromise=page.waitForEvent('popup');await page.locator('.social').first().click();const socialPopup=await socialPopupPromise;await socialPopup.waitForLoadState();assert.equal(socialPopup.url(),config.socials[0].url);await socialPopup.close();
  const clickTotal=data=>data.rows.filter(x=>x.kind==='click').reduce((n,x)=>n+x.total,0);
  let stats;for(let i=0;i<30;i++){stats=await request('/api/stats',undefined,'GET');if(clickTotal(stats)>=clickTotal(before)+4)break;await new Promise(r=>setTimeout(r,50))}
  assert(stats.rows.some(x=>x.kind==='view'&&x.source==='instagram'));assert(stats.rows.some(x=>x.kind==='click'&&x.link==='block:'+second.id&&x.source==='instagram'));assert(stats.rows.some(x=>x.kind==='click'&&x.link==='latest-video'));assert(stats.rows.some(x=>x.kind==='impression')===false); // report rows intentionally exclude impressions
  const blocks=await request('/api/content',undefined,'GET');assert(blocks.items.find(x=>x.id===second.id).impressions>0,'Campaign impressions missing');
  await request('/api/content/'+first.id,block('Campagne test A',{url:'http://localhost:18082/offer'}),'PUT');
  const story=await request('/api/content/'+first.id+'/story-link',{});const token=story.url.split('/').at(-1);await page.goto(origin+'/go/'+token);assert.equal(page.url(),'http://localhost:18082/offer');
  stats=await request('/api/stats',undefined,'GET');assert(stats.stories.some(x=>x.promotion_id===first.id&&x.label==='Campagne test A'&&x.total>=1));
  await request('/api/content/'+first.id,block('Campagne renommée',{url:'http://localhost:18082/changed'}),'PUT');await page.goto(origin+'/go/'+token);assert.equal(page.url(),'http://localhost:18082/changed');await request('/api/content/'+first.id,block('Campagne renommée'),'PUT');
  await load('youtube');assert((await page.locator('#offers').textContent()).includes('Campagne renommée'));
  await request('/api/settings',{name:config.profile.name,tagline:'Accroche de vérification temporaire',description:config.profile.description});await load();assert.equal(await page.locator('#profile-tagline').textContent(),'Accroche de vérification temporaire');
  await request('/api/content/'+future.id,block('Campagne désormais active'),'PUT');await load();assert.equal(await page.locator('.carousel-slide').count(),3);
  // Theme preferences on the admin origin have no effect on public dark colors.
  await page.evaluate(()=>{localStorage.setItem('links-admin-theme','light');document.documentElement.dataset.theme='light'});assert.equal(await page.locator('body').evaluate(n=>getComputedStyle(n).backgroundColor),'rgb(10, 17, 30)');
  await request('/api/content/'+second.id+'/archive',{});await request('/api/content/'+future.id+'/archive',{});await load();assert.equal(await page.locator('.carousel-slide').count(),1);assert(await page.locator('#offers-controls').isHidden());
  await request('/api/content/'+first.id+'/archive',{});await page.goto(origin);await page.waitForSelector('#links .card');assert(await page.locator('#offers').isHidden());
  assert.deepEqual(consoleErrors,[],'Console errors during successful public flows');
  // Existing fetch fallback and failure paths remain operational.
  await page.route('**/api/public-config',r=>r.fulfill({status:503,body:'{}'}));await page.goto(origin);await page.waitForSelector('#links .card');assert.equal(await page.locator('#links .card').count(),config.links.filter(x=>x.type==='classic').length);await page.unroute('**/api/public-config');
  videoAvailable=false;await page.goto(origin);await page.waitForSelector('#links .card');await page.waitForFunction(()=>document.getElementById('latest-video').hidden);videoAvailable=true;
  // Check automatic rotation, then disable motion again before visual captures.
  await request('/api/content/'+first.id+'/restore',{});await request('/api/content/'+second.id+'/restore',{});await page.emulateMedia({reducedMotion:'no-preference'});await load();await page.mouse.move(0,0);await page.locator('#profile-name').click();await page.waitForFunction(()=>document.querySelector('.carousel-dots button.active')?.getAttribute('aria-label')==='Afficher l’offre 2 sur 2',{},{timeout:8000});await page.emulateMedia({reducedMotion:'reduce'});
  const luminance=hex=>{const c=hex.replace('#','').match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722};
  const contrast=(a,b)=>{const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
  for(const [fg,bg] of [['#f1f4fa','#131e2e'],['#b0bdd0','#131e2e'],['#9aabc2','#0a111e'],['#7acfe5','#0a111e'],['#b8e6f1','#213547']])assert(contrast(fg,bg)>=4.5,'Text contrast '+fg);
  assert.deepEqual(errors,[]);
  // Resolution selection only: actual browser load/error events, including HTTP-200 placeholders.
  const thumbnail=page.locator('.video-visual img');
  assert((await thumbnail.getAttribute('src')).endsWith('/maxresdefault.jpg'));
  const imageStyle=await thumbnail.evaluate(n=>({fit:getComputedStyle(n).objectFit,filter:getComputedStyle(n).filter,transform:getComputedStyle(n).transform}));
  assert.deepEqual(imageStyle,{fit:'cover',filter:'none',transform:'none'});
  await page.route('https://i.ytimg.com/**',r=>r.request().url().endsWith('/maxresdefault.jpg')?r.abort():r.fulfill({contentType:'image/webp',body:asset}));
  await load();await page.waitForFunction(()=>document.querySelector('.video-visual img')?.src.endsWith('/sddefault.jpg')&&document.querySelector('.video-visual img').complete);
  await page.unroute('https://i.ytimg.com/**');
  await page.route('https://i.ytimg.com/**',r=>{const url=r.request().url();if(url.endsWith('/maxresdefault.jpg'))return r.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="90"></svg>'});if(url.endsWith('/sddefault.jpg'))return r.abort();return r.fulfill({contentType:'image/webp',body:asset})});
  await load();await page.waitForFunction(()=>document.querySelector('.video-visual img')?.src.endsWith('/hqdefault.jpg')&&document.querySelector('.video-visual img').complete);
  await page.unroute('https://i.ytimg.com/**');
  if(process.env.PUBLIC_SCREENSHOTS){mkdirSync(process.env.PUBLIC_SCREENSHOTS,{recursive:true});for(const width of [390,1440]){await page.setViewportSize({width,height:900});await page.goto(origin);await page.waitForSelector('.video-title');await page.screenshot({path:join(process.env.PUBLIC_SCREENSHOTS,'public-'+width+'.png'),fullPage:true,animations:'disabled'})}}
  console.log('Public config/profile/assets/socials/video, dates/statuses, 0/1/2/3 campaigns, controls/touch/keyboard/rotation, sources/clicks/impressions, Story redirects/stats, admin edits, fallback, five widths: OK');
 }finally{if(browser)await browser.close();await new Promise(r=>site.listening?site.close(r):r());await new Promise(r=>partner.listening?partner.close(r):r());backend.kill();await new Promise(r=>backend.exitCode!==null?r():backend.once('exit',r));rmSync(temp,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
