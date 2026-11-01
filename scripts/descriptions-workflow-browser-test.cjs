// Catalogue-only analysis against a temporary database; no external traffic.
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
import descriptions as d
with a.connection() as db:
 template=d.get(db,d.TABLES[0],d.DEFAULT_ID)
 for section in template['sections']:
  for owner in [section,*section['merchants']]:
   for binding in owner['links']:
    item=a.affiliate_partners.save_tracked(db,{'name':binding['id'],'url':binding['reference_url']},a.story_url_valid,a.now_iso())
    source=db.execute("SELECT id FROM tracking_sources WHERE name='YouTube Description'").fetchone()[0]
    a.tracked_links.token_link(db,item['id'],source,a.ORIGIN,a.now_iso());binding.update(link_id=item['id'],source_id=source)
 d.write(db,'templates/'+template['id']+'/save',{**template,'expected_revision':template['revision']},a.ORIGIN)
original_token_link=a.tracked_links.token_link
failed=[False]
def fail_once(db,ident,source,origin,now):
 row=db.execute('SELECT name FROM tracked_links WHERE id=?',(ident,)).fetchone()
 if row and 'Injecteur' in row[0] and not failed[0]:
  failed[0]=True;raise OSError('Échec simulé de publication')
 return original_token_link(db,ident,source,origin,now)
a.tracked_links.token_link=fail_once
print(a.ORIGIN,flush=True)
s.serve_forever()`],{cwd:__dirname,env:{...process.env,PYTHONIOENCODING:'utf-8',ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:['ignore','pipe','pipe']});
  let logs='';server.stderr.on('data',b=>logs+=b);
  const origin=await new Promise((resolve,reject)=>{let data='';const timer=setTimeout(()=>reject(Error(logs||'Server timeout')),20000);server.stdout.on('data',b=>{data+=b;const m=data.match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0])}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Server exit '+code+': '+logs))})});
  const api=async(path,data)=>{const r=await fetch(origin+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(r.ok,await r.clone().text());return r.json()};
  const template=(await api('/api/descriptions/templates')).items[0],draft=await api('/api/descriptions/drafts',{title:'Finalisation SMLIGHT',template_id:template.id,template_revision:template.revision});
  let doc=(await api('/api/descriptions/drafts/'+draft.id)).document;
  const reference=readFileSync(join(__dirname,'fixtures/descriptions/smlight.txt'),'utf8').replace(/^\uFEFF/,'').replace(/\r\n/g,'\n');
  const get=async()=>(await api('/api/descriptions/drafts/'+draft.id)).document;
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const context=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],external=[];
  // Exercise the HTTP/older-browser UUID fallback throughout persistence and recovery.
  await context.addInitScript(()=>Object.defineProperty(crypto,'randomUUID',{value:undefined,configurable:true}));
  page.on('pageerror',e=>errors.push(e.message));await context.route('**/*',r=>{if(!r.request().url().startsWith(origin)){external.push(r.request().url());return r.abort()}return r.continue()});
  // Force the clipboard fallback; copy must still expose the complete exact text.
  await page.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw Error('Denied')}}}));
  async function open(id=draft.id){await page.goto(origin);await page.locator('[data-tab=descriptions]').click();await page.locator('#descriptions').getByRole('button',{name:'Descriptions',exact:true}).click();const item=(await api('/api/descriptions/drafts')).items.find(d=>d.id===id);await page.locator('.description-draft-list article').filter({hasText:item.title}).getByRole('button',{name:'Ouvrir',exact:true}).click()}
  await open();const root=page.locator('#descriptions'),area=page.getByLabel('Texte de la description',{exact:true}),saved=()=>root.locator('.description-editor-status').filter({hasText:'Enregistré'}).waitFor();
  await root.getByRole('button',{name:'Importer par collage',exact:true}).click();await page.getByLabel('Description à importer',{exact:true}).fill(reference);await page.getByRole('button',{name:'Importer et remplacer le texte',exact:true}).click();await saved();
  await root.getByRole('button',{name:'Sections',exact:true}).click();
  for(const id of ['summary','support','affiliate','videos','chapters','community','hashtags']){const anchor=root.locator('[data-anchor-id="'+id+'"]');if(await anchor.getByRole('button',{name:'Confirmer la proposition 1',exact:true}).count()){page.once('dialog',d=>d.accept());await anchor.getByRole('button',{name:'Confirmer la proposition 1',exact:true}).click();await saved()}}
  doc=await get();assert.equal(doc.text,reference);assert(doc.sections.every(a=>a.status==='confirmed'));
  const payload=()=>({text:doc.text,sections:doc.sections,analysis_version:1,products:doc.products,selections:doc.selections,manual_order:doc.manual_order});
  let analyzed=await api('/api/descriptions/drafts/'+draft.id+'/analyze',payload());
  const backup=await api('/api/backup'),source=backup.tables.tracking_sources.find(s=>s.name==='YouTube Description').id;
  doc.selections.merchant_search={version:1,products:{}};
  const amazon='https://link.amazon/FinalExact?tag=official-21&x=A%2Bb&x=+&x=2#😀';
  let failingOperation;
  for(const [name,merchant,url] of [
   ['SMLIGHT SMHub Nano MG24','domadoo',reference.match(/https:\/\/www.domadoo.fr\/fr\/produits[^\s]+/)[0]],
   ['Injecteur PoE SMLIGHT 48 V / 24 W','domadoo',reference.match(/https:\/\/www.domadoo.fr\/fr\/accessoires[^\s]+/)[0]],
   ['Kit CPL avec Wi-Fi','amazon',amazon]]){
   const product=analyzed.products.find(p=>p.name===name);assert(product,name);
   const prepared=await api('/api/descriptions/drafts/'+draft.id+'/prepare',{document:payload(),product_id:product.id,merchant,url,label:name});
   doc.selections.merchant_search.products[product.id]={query:name,merchants:{[merchant]:{prepared,url_input:url,status:'found',selected:true,label:name,link_id:prepared.link_id,source_id:merchant==='amazon'?'':source,section_id:'affiliate',merchant_id:merchant}}};
   const op='merchant-'+product.id+'-'+merchant;if(name.startsWith('Injecteur'))failingOperation=op;
   if(merchant==='amazon')doc.selections.operations={[op]:{target_url_id:analyzed.urls.find(u=>u.url==='https://amzn.to/4yj9H0L').id}};
  }
  doc=await api('/api/descriptions/drafts/'+draft.id+'/save',{...payload(),title:doc.title,expected_revision:doc.revision,mutation_id:'prepared-workflow'});await open();await saved();
  const before=await api('/api/backup');await root.getByRole('button',{name:'Comparer les modifications',exact:true}).click();
  let review=page.getByRole('dialog').filter({has:page.getByRole('heading',{name:'Comparer avant application',exact:true})});await review.waitFor();
  assert((await review.innerText()).includes('Lien suivi à créer'));await review.getByLabel('Afficher uniquement les modifications',{exact:true}).check();
  assert.deepEqual((await api('/api/backup')).tables,before.tables); // Preview allocates nothing.
  for(const theme of ['light','dark']){await page.selectOption('#theme-select',theme,{force:true});if(process.env.DESCRIPTION_SCREENSHOTS){mkdirSync(process.env.DESCRIPTION_SCREENSHOTS,{recursive:true});await page.screenshot({path:join(process.env.DESCRIPTION_SCREENSHOTS,'workflow-1920-'+theme+'.png')})}}
  await review.getByRole('button',{name:'Appliquer les modifications',exact:true}).click();await root.locator('.description-workflow-status').filter({hasText:'Application partielle'}).waitFor();
  let applied=await get();assert.equal(applied.workflow.results[failingOperation].status,'failed');assert(applied.text.includes(amazon));assert(!applied.text.includes('https://amzn.to/4yj9H0L'));assert.equal((await api('/api/backup')).tables.tracked_links.length,before.tables.tracked_links.length);
  // Retry succeeds server-side but its response is lost. The same mutation is replayed.
  await page.route('**/drafts/'+draft.id+'/apply',async route=>{await route.fetch();await route.abort('failed')},{times:1});
  await root.getByRole('button',{name:'Comparer les modifications',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Appliquer les modifications',exact:true}).click();await root.getByRole('button',{name:'Reprendre la validation',exact:true}).waitFor();
  const afterLost=await api('/api/backup');assert.equal(afterLost.tables.tracked_links.length,before.tables.tracked_links.length+1);
  await root.getByRole('button',{name:'Reprendre la validation',exact:true}).click();await root.getByRole('button',{name:'Reprendre la validation',exact:true}).waitFor({state:'detached'});await saved();
  applied=await get();assert.equal(applied.workflow.results[failingOperation].status,'applied');assert.equal(applied.text,await area.inputValue());assert(applied.text.includes(amazon));assert.deepEqual((await api('/api/backup')).tables,afterLost.tables);
  // Text undo/redo never rolls back catalogue records or duplicates them.
  const finalText=applied.text;await root.getByRole('button',{name:'Annuler',exact:true}).click();assert.notEqual(await area.inputValue(),finalText);await root.getByRole('button',{name:'Rétablir',exact:true}).click();await saved();assert.equal(await area.inputValue(),finalText);
  await root.getByRole('button',{name:'Finaliser et copier',exact:true}).click();const finalize=page.getByRole('dialog');await finalize.getByLabel('Texte à finaliser',{exact:true}).waitFor();const ignore=finalize.getByLabel('Ignorer volontairement ces propositions pour cette version',{exact:true});if(await ignore.count())await ignore.check();
  await finalize.getByRole('button',{name:'Enregistrer la version et copier',exact:true}).click();await page.getByText('Copie automatique indisponible. Le texte est sélectionné : utilisez Ctrl+C.',{exact:true}).waitFor().catch(async error=>{console.error('Finalization UI:',await root.locator('.description-workflow-status').allTextContents());console.error('Dialogs:',await page.getByRole('dialog').allTextContents());throw error});assert.equal(await page.getByLabel('Texte final à copier',{exact:true}).inputValue(),finalText);
  const versions=(await api('/api/descriptions/drafts/'+draft.id+'/versions')).items;assert.equal(versions.length,1);assert.equal(versions[0].text,finalText);assert(versions[0].links.some(l=>l.url===amazon&&l.destination===amazon));
  await page.evaluate(()=>{navigator.clipboard.writeText=async text=>{window.copiedDescription=text}});await page.getByRole('button',{name:'Copier le texte intégral',exact:true}).click();assert.equal(await page.evaluate(()=>window.copiedDescription),finalText);
  await page.getByRole('dialog').getByRole('button',{name:'Fermer',exact:true}).click();await area.fill(finalText+'\n#Recette');await saved();
  await root.getByRole('button',{name:'Finaliser et copier',exact:true}).click();await page.getByLabel('Texte à finaliser',{exact:true}).waitFor();const remaining=page.getByLabel('Ignorer volontairement ces propositions pour cette version',{exact:true});if(await remaining.count())await remaining.check();await page.getByRole('button',{name:'Enregistrer la version et copier',exact:true}).click();await page.getByLabel('Texte final à copier',{exact:true}).waitFor();assert.equal(await page.getByLabel('Texte final à copier',{exact:true}).inputValue(),finalText+'\n#Recette');
  const both=(await api('/api/descriptions/drafts/'+draft.id+'/versions')).items;assert.equal(both.length,2);assert.equal(both.find(v=>v.id===versions[0].id).text,finalText);
  await page.getByRole('dialog').getByRole('button',{name:'Fermer',exact:true}).click();await root.getByRole('button',{name:'Historique',exact:true}).click();
  await page.getByLabel('URL YouTube facultative',{exact:true}).fill('https://youtu.be/eRgBHrvzJDw');await saved();assert.equal((await get()).youtube_url,'https://youtu.be/eRgBHrvzJDw');
  await page.getByRole('button',{name:'Comparer ces versions',exact:true}).click();const versionComparison=page.getByRole('dialog').filter({has:page.getByRole('heading',{name:'Comparaison des versions immuables',exact:true})});await versionComparison.getByLabel('Afficher uniquement les modifications',{exact:true}).check();assert((await versionComparison.innerText()).includes('#Recette'));await versionComparison.getByRole('button',{name:'Fermer',exact:true}).click();
  const versionRow=page.getByRole('dialog').locator('[data-version-id="'+versions[0].id+'"]');await versionRow.locator('summary').first().click();
  page.once('dialog',d=>d.accept());await versionRow.getByRole('button',{name:'Restaurer dans un nouveau brouillon',exact:true}).click();await poll(async()=>await root.getByLabel('Titre interne',{exact:true}).inputValue().then(t=>t.includes('restauré')));
  assert.equal(await area.inputValue(),finalText);assert.equal((await api('/api/descriptions/drafts/'+draft.id+'/versions')).items.find(v=>v.id===versions[0].id).text,finalText);
  const after=await api('/api/backup');assert.deepEqual(after.tables.counts,before.tables.counts);assert.deepEqual(after.tables.tracking_sources,before.tables.tracking_sources);assert(after.tables.tracked_tokens.every(t=>t.click_total===0));
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);console.log('Description workflow browser: SMLIGHT import, historical links, partial application, lost response, idempotent retry, exact Amazon, comparison, undo, finalization, clipboard fallback and immutable restoration OK');
 }finally{if(browser)await browser.close();if(server){server.kill();if(server.exitCode===null)await new Promise(r=>server.once('exit',r))}rmSync(temp,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
