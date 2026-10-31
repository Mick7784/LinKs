// Explicit merchant preparation with simulated responses and blocked external traffic.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process'),{mkdtempSync,rmSync,readFileSync,mkdirSync}=require('node:fs'),{tmpdir}=require('node:os'),{join}=require('node:path');
const pause=ms=>new Promise(r=>setTimeout(r,ms));async function poll(fn){const end=Date.now()+15000;while(Date.now()<end){if(await fn())return;await pause(60)}throw Error('Analysis state timeout')}
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-analysis-'));let server,browser;
 try{
  server=spawn(process.env.PYTHON_PATH||'python3',['-u','-B','-c',`import os
from fixtures import prepare,populate
prepare(os.environ['ANALYTICS_DB'])
import analytics as a
a.init();populate(a)
s=a.serve(0,True,'127.0.0.1')
a.ORIGIN='http://127.0.0.1:'+str(s.server_port)
with a.connection() as db:
 a.instance.put(db,'site.url',a.ORIGIN);a.instance.put(db,'video.enabled','false')
 for name,url in [('SMLIGHT SMHub Nano MG24','https://www.domadoo.fr/fr/produits-de-domotique/8664-smlight-smhub-nano-mg24-hub-sous-linux-zigbee2mqtt-node-red-et-matterbridge.html?domid=117'),('SMLIGHT SMHub Nano MG24','https://amzn.to/extra'),('SMLIGHT SMHub Nano MG21','https://www.domadoo.fr/fr/8665-hub-mg21.html'),('Antenne SMLIGHT SMHub Nano MG24','https://shop.example/antenna')]:
  item=a.affiliate_partners.save_tracked(db,{'name':name,'url':url},a.story_url_valid,a.now_iso())
  for source in ['YouTube Description','YouTube Post']:
   source_id=db.execute('SELECT id FROM tracking_sources WHERE name=?',(source,)).fetchone()[0]
   a.tracked_links.token_link(db,item['id'],source_id,a.ORIGIN,a.now_iso())
print(a.ORIGIN,flush=True)
s.serve_forever()`],{cwd:__dirname,env:{...process.env,PYTHONIOENCODING:'utf-8',ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:['ignore','pipe','pipe']});
  let logs='';server.stderr.on('data',b=>logs+=b);
  const origin=await new Promise((resolve,reject)=>{let data='';const timer=setTimeout(()=>reject(Error(logs||'Server timeout')),20000);server.stdout.on('data',b=>{data+=b;const m=data.match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0])}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Server exit '+code+': '+logs))})});
  const api=async(path,data)=>{const r=await fetch(origin+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(r.ok,await r.clone().text());return r.json()};
  const template=(await api('/api/descriptions/templates')).items[0],draft=await api('/api/descriptions/drafts',{title:'Recherche SMLIGHT',template_id:template.id,template_revision:template.revision});
  let doc=(await api('/api/descriptions/drafts/'+draft.id)).document;
  const reference=readFileSync(join(__dirname,'fixtures/descriptions/smlight.txt'),'utf8').replace(/^\uFEFF/,'').replace(/\r\n/g,'\n');
  const sections=doc.sections.map(a=>({...a,status:'ambiguous',start:null,end:null,candidates:[]}));
  doc=await api('/api/descriptions/drafts/'+draft.id+'/save',{title:doc.title,text:reference,sections,expected_revision:doc.revision,mutation_id:'browser-import'});
  const before=await api('/api/backup'),get=async()=>(await api('/api/descriptions/drafts/'+draft.id)).document;
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const context=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'reduce'}),errors=[],external=[];let page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));await context.route('**/*',r=>{if(!r.request().url().startsWith(origin)){external.push(r.request().url());return r.abort()}return r.continue()});
  async function open(){await page.goto(origin);await page.locator('[data-tab=descriptions]').click();await page.locator('#descriptions').getByRole('button',{name:'Descriptions',exact:true}).click();await page.locator('.description-draft-list article').filter({hasText:'Recherche SMLIGHT'}).getByRole('button',{name:'Ouvrir',exact:true}).click()}
  const requests=[];context.on('request',r=>{if(r.url().endsWith('/search'))requests.push(r.postDataJSON())});
  await open();let root=page.locator('#descriptions');const area=()=>page.getByLabel('Texte de la description',{exact:true});
  const ready=()=>root.locator('.description-analysis-status').filter({hasText:'à jour'}).waitFor(),saved=()=>root.locator('.description-editor-status').filter({hasText:'Enregistré'}).waitFor();await ready();
  assert.equal(requests.length,0);await area().fill('😀 Test marchand.\n'+reference);await ready();await saved();assert.equal(requests.length,0);
  const count=await root.locator('.description-product').count();await root.getByRole('button',{name:'Rechercher tous les produits',exact:true}).click();
  await root.getByRole('button',{name:'Rechercher tous les produits',exact:true}).waitFor();await saved();assert.equal(requests.length,count);
  // Locate by the product's own heading, independently of candidate labels.
  const hub=root.locator('.description-product').filter({has:page.getByText('SMLIGHT SMHub Nano',{exact:true})}).first(),id=await hub.getAttribute('data-product-id');
  const product=()=>root.locator('[data-product-id="'+id+'"]'),merchant=m=>product().locator('[data-merchant="'+m+'"]');
  await merchant('domadoo').locator('summary').click();assert.equal(await merchant('domadoo').locator('.description-merchant-result').count(),2);
  await merchant('domadoo').locator('.description-merchant-result').filter({hasText:'MG24'}).getByRole('button',{name:'Choisir cette référence',exact:true}).click();
  await merchant('domadoo').getByLabel('Source YouTube',{exact:true}).waitFor();await merchant('domadoo').getByLabel('Source YouTube',{exact:true}).selectOption({label:'YouTube Post · publication existante'});
  assert(!await merchant('domadoo').getByRole('checkbox').isChecked());await merchant('domadoo').getByLabel('Intitulé marchand',{exact:true}).fill('Mon hub Domadoo 😀');await merchant('domadoo').getByRole('checkbox').check();await saved();
  await merchant('amazon').locator('summary').click();await merchant('amazon').getByRole('button',{name:'J’ai déjà un lien affilié',exact:true}).click();
  const amazon='https://link.amazon/Exact_ABC?tag=domotik-21&value=A%2Bb&repeat=1&repeat=2#exact';
  await merchant('amazon').getByLabel('Lien affilié Amazon',{exact:true}).fill(amazon);await merchant('amazon').getByRole('button',{name:'Préparer ce lien',exact:true}).click();
  await merchant('amazon').getByLabel('Intitulé marchand',{exact:true}).waitFor();assert(!await merchant('amazon').getByRole('checkbox').isChecked());await merchant('amazon').getByRole('checkbox').check();await merchant('amazon').getByLabel('Intitulé marchand',{exact:true}).fill('Mon hub Amazon');await saved();
  await product().getByRole('button',{name:'Descendre SMLIGHT SMHub Nano',exact:true}).click();await saved();
  const chosen=await get(),state=chosen.selections.merchant_search.products[id];assert.equal(state.merchants.amazon.prepared.url,amazon);assert.equal(state.merchants.amazon.prepared.mode,'direct');assert.equal(state.merchants.domadoo.prepared.url.match(/domid=/g).length,1);assert.equal(await area().inputValue(),'😀 Test marchand.\n'+reference);
  const others=structuredClone(chosen.selections.merchant_search.products);delete others[id];const previousRequests=requests.length;
  await product().getByLabel('Mots-clés',{exact:true}).fill('SMLIGHT SMHub Nano MG21');await product().getByRole('button',{name:'Rechercher à nouveau',exact:true}).click();
  await poll(async()=>requests.length===previousRequests+1&&(await get()).selections.merchant_search.products[id].merchants.domadoo.query==='SMLIGHT SMHub Nano MG21');await saved();
  let next=(await get()).selections.merchant_search.products[id];assert.equal(next.merchants.amazon.prepared.url,amazon);assert.equal(next.merchants.domadoo.label,'Mon hub Domadoo 😀');assert(next.merchants.domadoo.selected);assert(next.merchants.amazon.selected);
  const otherAfter=structuredClone((await get()).selections.merchant_search.products);delete otherAfter[id];assert.deepEqual(otherAfter,others);assert.deepEqual((await get()).manual_order,chosen.manual_order);
  // Simulate a merchant error; another merchant and all confirmed choices survive.
  await page.route('**/drafts/'+draft.id+'/search',async route=>{const response=await route.fetch(),body=await response.json();body.merchants.domadoo={status:'error',results:[],query:body.query,message:'Erreur Domadoo simulée'};await route.fulfill({json:body})},{times:1});
  await product().getByRole('button',{name:'Rechercher à nouveau',exact:true}).click();await merchant('domadoo').getByText('Erreur Domadoo simulée',{exact:true}).waitFor();await saved();assert(await merchant('domadoo').getByRole('checkbox').isChecked());
  assert.equal((await get()).selections.merchant_search.products[id].merchants.amazon.prepared.url,amazon);
  // A new tab is human-operated; the test substitutes its content, no merchant IO.
  await context.unroute('**/*');await context.route('**/*',route=>route.request().url().startsWith(origin)?route.continue():route.fulfill({contentType:'text/html',body:'<title>Marchand simulé</title>'}));
  const popupPromise=context.waitForEvent('page');await merchant('amazon').getByRole('link',{name:'Ouvrir sur Amazon',exact:true}).click();const popup=await popupPromise;await popup.waitForLoadState();assert(popup.url().startsWith('https://www.amazon.fr/s?'));await popup.close();assert.equal(await merchant('amazon').getByLabel('Lien affilié Amazon',{exact:true}).inputValue(),amazon);
  // Interrupted input is recovered with search results, choices and manual order.
  await context.setOffline(true);await merchant('amazon').getByLabel('Intitulé marchand',{exact:true}).fill('Titre marchand hors ligne 😀');await root.locator('.description-editor-status').filter({hasText:'Hors ligne'}).waitFor();await page.close({runBeforeUnload:false});await context.setOffline(false);
  page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await open();root=page.locator('#descriptions');page.once('dialog',d=>d.accept());await root.getByRole('button',{name:'Reprendre cette copie',exact:true}).click();
  await poll(async()=>(await get()).selections.merchant_search.products[id].merchants.amazon.label==='Titre marchand hors ligne 😀');await ready();
  const recovered=await get();assert.equal(recovered.selections.merchant_search.products[id].merchants.amazon.prepared.url,amazon);assert(recovered.selections.merchant_search.products[id].merchants.domadoo.selected);assert.deepEqual(recovered.manual_order,chosen.manual_order);assert.equal(recovered.text,'😀 Test marchand.\n'+reference);
  await product().locator('[data-search-product]>summary').click();await merchant('amazon').locator('summary').click();
  for(const theme of ['light','dark']){await page.selectOption('#theme-select',theme);await poll(()=>page.locator('#theme-select').isEnabled());assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));if(process.env.DESCRIPTION_SCREENSHOTS){mkdirSync(process.env.DESCRIPTION_SCREENSHOTS,{recursive:true});await page.screenshot({path:join(process.env.DESCRIPTION_SCREENSHOTS,'search-1920-'+theme+'.png')})}}
  const after=await api('/api/backup');for(const key of ['tracked_links','tracked_tokens','tracking_sources','tracking_source_keys','short_aliases','counts','affiliate_partners'])assert.deepEqual(after.tables[key],before.tables[key],key);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);console.log('Description merchant browser: explicit global/individual search, multiple matches, errors, sources, affiliate URLs, manual choices/order, popup and interrupted recovery OK');
 }finally{if(browser)await browser.close();if(server){server.kill();if(server.exitCode===null)await new Promise(r=>server.once('exit',r))}rmSync(temp,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
