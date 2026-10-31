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
print(a.ORIGIN,flush=True)
s.serve_forever()`],{cwd:__dirname,env:{...process.env,PYTHONIOENCODING:'utf-8',ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:['ignore','pipe','pipe']});
  let logs='';server.stderr.on('data',b=>logs+=b);
  const origin=await new Promise((resolve,reject)=>{let data='';const timer=setTimeout(()=>reject(Error(logs||'Server timeout')),20000);server.stdout.on('data',b=>{data+=b;const m=data.match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0])}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Server exit '+code+': '+logs))})});
  const api=async(path,data)=>{const r=await fetch(origin+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(r.ok,await r.clone().text());return r.json()};
  const template=(await api('/api/descriptions/templates')).items[0],draft=await api('/api/descriptions/drafts',{title:'Analyse SMLIGHT',template_id:template.id,template_revision:template.revision});
  let doc=(await api('/api/descriptions/drafts/'+draft.id)).document;
  const reference=readFileSync(join(__dirname,'fixtures/descriptions/smlight.txt'),'utf8').replace(/^\uFEFF/,'').replace(/\r\n/g,'\n');
  const sections=doc.sections.map(a=>({...a,status:'ambiguous',start:null,end:null,candidates:[]}));
  doc=await api('/api/descriptions/drafts/'+draft.id+'/save',{title:doc.title,text:reference,sections,expected_revision:doc.revision,mutation_id:'browser-import'});
  const before=await api('/api/backup'),get=async()=>(await api('/api/descriptions/drafts/'+draft.id)).document;
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const context=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'reduce'}),errors=[],external=[];let page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));await context.route('**/*',r=>{if(!r.request().url().startsWith(origin)){external.push(r.request().url());return r.abort()}return r.continue()});
  async function open(){await page.goto(origin);await page.locator('[data-tab=descriptions]').click();await page.locator('#descriptions').getByRole('button',{name:'Descriptions',exact:true}).click();await page.locator('.description-draft-list article').filter({hasText:'Analyse SMLIGHT'}).getByRole('button',{name:'Ouvrir',exact:true}).click()}
  await open();const root=page.locator('#descriptions'),area=page.getByLabel('Texte de la description',{exact:true});
  const ready=()=>root.locator('.description-analysis-status').filter({hasText:'à jour'}).waitFor(),saved=()=>root.locator('.description-editor-status').filter({hasText:'Enregistré'}).waitFor();await ready();
  assert.equal(await area.inputValue(),reference);assert.equal(await root.locator('.description-detected-url').count(),10);
  assert.equal((await get()).revision,doc.revision); // Analysis itself never saves or mutates.
  assert(!(await root.locator('.description-product>strong').allTextContents()).some(n=>/Antenne|MQTT|Home Assistant/.test(n)));
  for(const box of await root.locator('[data-operation=reuse] input[type=checkbox]').all())assert(await box.isChecked());
  for(const box of await root.locator('[data-operation=add] input[type=checkbox]').all())assert(!await box.isChecked());
  for(const box of await root.locator('[data-operation=move] input[type=checkbox]').all())assert(!await box.isChecked());
  for(const theme of ['light','dark']){await page.selectOption('#theme-select',theme);await poll(()=>page.locator('#theme-select').isEnabled());assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));if(process.env.DESCRIPTION_SCREENSHOTS){mkdirSync(process.env.DESCRIPTION_SCREENSHOTS,{recursive:true});await page.screenshot({path:join(process.env.DESCRIPTION_SCREENSHOTS,'analysis-1920-'+theme+'.png')})}}
  const domadoo=root.locator('[data-operation=reuse]').filter({has:page.locator('code').filter({hasText:'8664-smlight-smhub'})});
  const id=await domadoo.getAttribute('data-proposal-id'),row=()=>root.locator(`[data-proposal-id="${id}"]`);
  assert.equal(await row().getByLabel('Source de publication existante',{exact:true}).inputValue(),'');
  await row().getByLabel('Source de publication existante',{exact:true}).selectOption({label:'YouTube Post · YouTube'});
  await row().getByLabel('Intitulé dans cette description',{exact:true}).fill('Mon hub 😀 personnel');await row().getByRole('checkbox').uncheck();await saved();
  await root.getByRole('button',{name:'Déplacer Kit CPL avec Wi-Fi',exact:true}).press('ArrowUp');await saved();
  const initial=await get(),initialOrder=initial.manual_order.slice(),choice=initial.selections.description_analysis[id];assert.equal(choice.selected,false);assert.equal(choice.label,'Mon hub 😀 personnel');assert(choice.source_id);
  await area.fill('😀 Nouvelle introduction.\n'+reference);await ready();await saved();
  assert.equal(await row().getByLabel('Intitulé dans cette description',{exact:true}).inputValue(),choice.label);assert(!await row().getByRole('checkbox').isChecked());assert.equal(await row().getByLabel('Source de publication existante',{exact:true}).inputValue(),choice.source_id);
  assert.deepEqual((await get()).manual_order,initialOrder);
  // A superseded response cannot restore old discoveries or reset current decisions.
  let received,release;const sent=new Promise(r=>received=r),gate=new Promise(r=>release=r);
  await page.route('**/drafts/'+draft.id+'/analyze',async route=>{const response=await route.fetch();received();await gate;try{await route.fulfill({response})}catch{}},{times:1});
  await area.fill('SONOFF ZBDongle-P.\n'+reference);await sent;await area.fill('SONOFF ZBDongle-E.\n'+reference);release();await ready();await saved();
  const names=await root.locator('.description-product>strong').allTextContents();assert(names.includes('SONOFF ZBDongle-E'));assert(!names.includes('SONOFF ZBDongle-P'));assert.equal((await get()).selections.description_analysis[id].label,choice.label);
  // Explicit manual references are draft-owned, editable and persistent.
  page.once('dialog',d=>d.accept('Home Assistant Green'));await root.getByRole('button',{name:'Ajouter une référence',exact:true}).click();await ready();await saved();
  await root.getByLabel('Référence manuelle',{exact:true}).fill('Home Assistant Green personnel');await ready();await saved();
  const withManual=await get();assert.equal(withManual.products.find(p=>p.kind==='manual-reference').query,'Home Assistant Green personnel');
  await open();await ready();assert.equal(await row().getByLabel('Intitulé dans cette description',{exact:true}).inputValue(),choice.label);assert(!await row().getByRole('checkbox').isChecked());assert.equal(await root.getByLabel('Référence manuelle',{exact:true}).inputValue(),'Home Assistant Green personnel');
  assert((await area.inputValue()).includes('https://amzn.to/4yj9H0L'));assert((await root.innerText()).includes('insertion directe uniquement'));
  // Removing one URL makes just its proposal obsolete; saved intent survives undo/reanalysis.
  const text=await area.inputValue(),url=reference.match(/https:\/\/www\.domadoo\.fr\/fr\/produits[^\s]+/)[0];await area.fill(text.replace(url,''));await ready();await saved();assert.equal(await row().count(),0);
  assert.deepEqual((await get()).selections.description_analysis[id],choice);await area.fill(text);await ready();await saved();assert(!await row().getByRole('checkbox').isChecked());
  // The phase-2 recovery now includes analysis choices as well as free text.
  await context.setOffline(true);await row().getByLabel('Intitulé dans cette description',{exact:true}).fill('Choix conservé hors ligne 😀');await root.locator('.description-editor-status').filter({hasText:'Hors ligne'}).waitFor();
  await page.close({runBeforeUnload:false});await context.setOffline(false);page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await open();
  const recoveredRoot=page.locator('#descriptions');page.once('dialog',d=>d.accept());await recoveredRoot.getByRole('button',{name:'Reprendre cette copie',exact:true}).click();
  await poll(async()=>(await get()).selections.description_analysis[id].label==='Choix conservé hors ligne 😀');
  assert.deepEqual((await get()).manual_order,initialOrder);assert.equal((await get()).products.find(p=>p.kind==='manual-reference').query,'Home Assistant Green personnel');
  const after=await api('/api/backup');for(const key of ['tracked_links','tracked_tokens','tracking_sources','tracking_source_keys','short_aliases','counts'])assert.deepEqual(after.tables[key],before.tables[key],key);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);console.log('Description analysis browser: SMLIGHT, local catalogue, source choices, editable titles, stale analysis, manual references/order, recovery, defaults and unchanged tracking OK');
 }finally{if(browser)await browser.close();if(server){server.kill();if(server.exitCode===null)await new Promise(r=>server.once('exit',r))}rmSync(temp,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
