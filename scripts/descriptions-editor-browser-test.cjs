// Temporary database, random local port and blocked external traffic.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process'),{mkdtempSync,rmSync,mkdirSync,readFileSync}=require('node:fs'),{tmpdir}=require('node:os'),{join}=require('node:path');
const S=require('../admin/description-sections.js');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function poll(fn){const end=Date.now()+15000;while(Date.now()<end){if(await fn())return;await pause(80)}throw Error('Timed out waiting for editor state')}
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-editor-'));let server,browser;
 try{
  server=spawn(process.env.PYTHON_PATH||'python3',['-u','-B','-c',`import os
from fixtures import prepare,populate
prepare(os.environ['ANALYTICS_DB'])
import analytics as a
a.init();populate(a)
s=a.serve(0,True,'127.0.0.1')
a.ORIGIN='http://127.0.0.1:'+str(s.server_port)
with a.connection() as db:
 a.instance.put(db,'site.url',a.ORIGIN)
 a.instance.put(db,'video.enabled','false')
print(a.ORIGIN,flush=True)
s.serve_forever()`],{cwd:__dirname,env:{...process.env,PYTHONIOENCODING:'utf-8',ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:['ignore','pipe','pipe']});
  let logs='';server.stderr.on('data',b=>logs+=b);
  const origin=await new Promise((resolve,reject)=>{let value='';const timer=setTimeout(()=>reject(Error(logs||'Server timeout')),20000);server.stdout.on('data',b=>{value+=b;const m=value.match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0])}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Server exit '+code+': '+logs))})});
  const api=async(path,data)=>{const r=await fetch(origin+'/api/descriptions/'+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(r.ok,await r.clone().text());return r.json()};
  const get=async id=>(await api('drafts/'+id)).document;
  let template=(await api('templates')).items[0];template.sections[0].text='Résumé initial 😀\nDu texte é et 👩🏽‍💻.';
  template=await api('templates/'+template.id+'/save',{...template,expected_revision:template.revision});
  const create=title=>api('drafts',{title,template_id:template.id,template_revision:template.revision});
  const original=await create('Rédaction principale'),second=await create('Autre brouillon');
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const context=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],external=[];
  await context.route('**/*',route=>{if(!route.request().url().startsWith(origin)){external.push(route.request().url());return route.abort()}return route.continue()});
  context.on('page',p=>p.on('pageerror',e=>errors.push(e.message)));page.on('pageerror',e=>errors.push(e.message));
  async function open(p,title){await p.goto(origin);await p.locator('[data-tab=descriptions]').click();await p.locator('#descriptions').getByRole('button',{name:'Descriptions',exact:true}).click();await p.locator('.description-draft-list article').filter({has:p.getByText(title,{exact:true})}).getByRole('button',{name:'Ouvrir',exact:true}).click();await p.getByLabel('Texte de la description',{exact:true}).waitFor()}
  await open(page,original.title);
  const root=page.locator('#descriptions'),area=page.getByLabel('Texte de la description',{exact:true}),status=root.locator('.description-editor-status');
  const saved=()=>status.filter({hasText:/^(Enregistré|Copie enregistrée)$/}).waitFor();
  assert.equal(await area.inputValue(),original.text);
  const sizes=await page.locator('.description-editor-layout').evaluate(el=>[el.children[0].getBoundingClientRect().width,el.children[2].getBoundingClientRect().width]);
  assert(Math.abs(sizes[0]/(sizes[0]+sizes[1])-.65)<.02,sizes);
  // The server commits the old request; its response arrives after newer typing.
  let release,received;const gate=new Promise(r=>release=r),sent=new Promise(r=>received=r);
  await page.route('**/drafts/'+original.id+'/save',async route=>{const response=await route.fetch();received();await gate;await route.fulfill({response})},{times:1});
  const first=original.text+'\nPremière saisie 😀',latest=first+'\nSaisie récente https://amzn.to/exact?tag=keep-21&x=a%2Bb#frag';
  await area.fill(first);await sent;await area.fill(latest);
  await area.evaluate(el=>{el.setSelectionRange(4,9);el.dispatchEvent(new Event('select'))});release();
  await poll(async()=>(await get(original.id)).text===latest);await saved();
  assert.equal(await area.inputValue(),latest);assert.deepEqual(await area.evaluate(el=>[el.selectionStart,el.selectionEnd]),[4,9]);
  await root.getByRole('button',{name:'Annuler',exact:true}).click();await poll(async()=>(await get(original.id)).text===first);await saved();
  await root.getByRole('button',{name:'Rétablir',exact:true}).click();await poll(async()=>(await get(original.id)).text===latest);await saved();
  // Renaming and restoring affect the draft only, using its original frozen copy.
  const support=original.template_snapshot.sections.find(s=>s.id==='support');
  const renamed=latest.replace(support.heading,'😀 Mon soutien personnalisé');await area.fill(renamed);await saved();
  let doc=await get(original.id),supportAnchor=doc.sections.find(s=>s.id==='support');assert.equal(supportAnchor.status,'confirmed');assert(supportAnchor.quote.startsWith('😀 Mon soutien'));
  template.sections.find(s=>s.id==='support').text='Nouveau modèle indépendant';template=await api('templates/'+template.id+'/save',{...template,expected_revision:template.revision});
  page.once('dialog',d=>d.accept());await root.locator('[data-anchor-id=support]').getByRole('button',{name:'Restaurer le contenu initial',exact:true}).click();await saved();
  doc=await get(original.id);assert.equal(doc.sections.find(s=>s.id==='support').quote,original.initial_sections.support);
  assert.equal((await api('templates')).items[0].sections.find(s=>s.id==='support').text,'Nouveau modèle indépendant');
  // Move an intact section through plain text, without regenerating its neighbours.
  supportAnchor=doc.sections.find(s=>s.id==='support');const moved=S.slice(doc.text,0,supportAnchor.start)+S.slice(doc.text,supportAnchor.end)+'\n\n'+supportAnchor.quote;
  await area.fill(moved);await saved();doc=await get(original.id);assert.equal(doc.sections.find(s=>s.id==='support').status,'confirmed');assert.equal(doc.sections.find(s=>s.id==='support').end,S.points(moved).length);
  // The supplied complete reference is pasted, not treated as executable instructions.
  const reference=readFileSync(join(__dirname,'fixtures/descriptions/smlight.txt'),'utf8').replace(/^\uFEFF/,'').replace(/\r\n/g,'\n');
  await root.getByRole('button',{name:'Importer par collage',exact:true}).click();await page.getByLabel('Description à importer',{exact:true}).fill(reference);await page.getByRole('button',{name:'Importer et remplacer le texte',exact:true}).click();await poll(async()=>await area.inputValue()===reference);await saved();
  doc=await get(original.id);assert.equal(doc.text,reference);assert(doc.sections.every(s=>s.status==='ambiguous'));assert(doc.text.includes('https://amzn.to/4yj9H0L'));
  const summary=root.locator('[data-anchor-id=summary]');await summary.getByRole('button',{name:'Voir la proposition 1',exact:true}).click();
  page.once('dialog',d=>d.accept());await summary.getByRole('button',{name:'Associer à la sélection',exact:true}).click();await saved();
  doc=await get(original.id);const summaryAnchor=doc.sections.find(s=>s.id==='summary');assert.equal(summaryAnchor.status,'confirmed');assert.equal(S.slice(reference,summaryAnchor.start,summaryAnchor.end),summaryAnchor.quote);
  for(const theme of ['light','dark']){await page.selectOption('#theme-select',theme);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));if(process.env.DESCRIPTION_SCREENSHOTS){mkdirSync(process.env.DESCRIPTION_SCREENSHOTS,{recursive:true});await page.screenshot({path:join(process.env.DESCRIPTION_SCREENSHOTS,'editor-1920-'+theme+'.png')})}}
  // Another tab wins; the losing text stays visible and can become a separate draft.
  const other=await context.newPage();await open(other,original.title);const otherArea=other.getByLabel('Texte de la description',{exact:true});
  const winner=reference+'\nGagnant serveur',loser=reference+'\nSaisie de l’autre onglet 😀';
  await area.fill(winner);await saved();await otherArea.fill(loser);await other.locator('.description-editor-status').filter({hasText:'Conflit de révision'}).waitFor();
  assert.equal(await otherArea.inputValue(),loser);assert.equal((await get(original.id)).text,winner);
  await other.getByRole('button',{name:'Voir la version serveur',exact:true}).click();assert.equal(await other.getByLabel('Version serveur — lecture seule',{exact:true}).inputValue(),winner);await other.getByRole('button',{name:'Fermer',exact:true}).click();
  other.once('dialog',d=>d.accept());await other.getByRole('button',{name:'Enregistrer ma copie',exact:true}).click();await other.locator('.description-editor-status').filter({hasText:'Copie enregistrée'}).waitFor();
  const copies=(await api('drafts')).items.filter(x=>x.title.endsWith(' — copie'));assert.equal(copies.length,1);assert.equal(copies[0].text,loser);assert.equal((await get(original.id)).text,winner);await other.close();
  // Offline interruption: navigation reload reads only the server until explicit recovery.
  const offline=winner+'\nTravail hors ligne 👩🏽‍💻';await context.setOffline(true);await area.fill(offline);await status.filter({hasText:'Hors ligne'}).waitFor();
  const localCount=await page.evaluate(()=>Object.keys(localStorage).filter(k=>k.startsWith('links:description-editor:')).length);assert(localCount>0);
  await page.close({runBeforeUnload:false});await context.setOffline(false);const recovered=await context.newPage();await open(recovered,original.title);
  const recoveredArea=recovered.getByLabel('Texte de la description',{exact:true});assert.equal(await recoveredArea.inputValue(),winner);
  recovered.once('dialog',d=>d.accept());await recovered.getByRole('button',{name:'Reprendre cette copie',exact:true}).click();await poll(async()=>(await get(original.id)).text===offline);await recovered.locator('.description-editor-status').filter({hasText:'Enregistré'}).waitFor();assert.equal(await recoveredArea.inputValue(),offline);
  // A committed request with a lost acknowledgement retries idempotently after restart.
  let lost,abort;const committed=new Promise(r=>lost=r),abortGate=new Promise(r=>abort=r);const beforeLost=await get(original.id);
  await recovered.route('**/drafts/'+original.id+'/save',async route=>{await route.fetch();lost();await abortGate;await route.abort()},{times:1});
  const committedText=offline+'\nAccusé perdu',unacknowledged=committedText+'\nSaisie encore plus récente 😀';await recoveredArea.fill(committedText);await committed;await recoveredArea.fill(unacknowledged);abort();await recovered.locator('.description-editor-status').filter({hasText:'interrompu'}).waitFor();
  await recovered.close({runBeforeUnload:false});const restarted=await context.newPage();await open(restarted,original.title);
  assert.equal(await restarted.getByLabel('Texte de la description',{exact:true}).inputValue(),committedText);
  const recoveryKey=await restarted.evaluate(id=>Object.keys(localStorage).find(k=>k.startsWith('links:description-editor:')&&JSON.parse(localStorage.getItem(k)).id===id),original.id);assert(recoveryKey);
  let resumeAck,resumeSent;const resumeGate=new Promise(r=>resumeAck=r),resumeReceived=new Promise(r=>resumeSent=r);
  await restarted.route('**/drafts/'+original.id+'/save',async route=>{const response=await route.fetch();resumeSent();await resumeGate;await route.fulfill({response})},{times:1});
  restarted.once('dialog',d=>d.accept());await restarted.getByRole('button',{name:'Reprendre cette copie',exact:true}).click();await resumeReceived;
  // Simulate the originating tab writing a newer local recovery while ours saves.
  await restarted.evaluate(key=>{const copy=JSON.parse(localStorage.getItem(key));copy.fields.text+='\nAutre saisie à conserver';copy.savedAt=new Date().toISOString();localStorage.setItem(key,JSON.stringify(copy))},recoveryKey);
  resumeAck();await restarted.locator('.description-editor-status').filter({hasText:'Enregistré'}).waitFor();
  assert(await restarted.evaluate(key=>JSON.parse(localStorage.getItem(key)).fields.text.endsWith('Autre saisie à conserver'),recoveryKey));
  assert.equal((await get(original.id)).text,unacknowledged);assert.equal((await get(original.id)).revision,beforeLost.revision+2);
  // A pending response from the previous document cannot repaint the newly opened one.
  let finish,waiting;const finishGate=new Promise(r=>finish=r),waitingGate=new Promise(r=>waiting=r);
  await restarted.route('**/drafts/'+original.id+'/save',async route=>{const response=await route.fetch();waiting();await finishGate;await route.fulfill({response})},{times:1});
  await restarted.getByLabel('Texte de la description',{exact:true}).fill(unacknowledged+'\nNavigation');await waitingGate;
  await restarted.locator('#descriptions').getByRole('button',{name:'Descriptions',exact:true}).click();await restarted.locator('.description-draft-list article').filter({hasText:second.title}).getByRole('button',{name:'Ouvrir',exact:true}).click();
  await restarted.getByLabel('Titre interne',{exact:true}).waitFor();finish();await pause(200);assert.equal(await restarted.getByLabel('Texte de la description',{exact:true}).inputValue(),second.text);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  console.log('Description editor browser: 65/35, Unicode, stale responses, undo, restoration, moves, full reference import, confirmed associations, conflicts, offline recovery, lost acknowledgements and navigation OK');
 }finally{if(browser)await browser.close();if(server){server.kill();if(server.exitCode===null)await new Promise(r=>server.once('exit',r))}rmSync(temp,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exitCode=1});
