// Isolated random-port server and disposable database; no merchant or production requests.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process'),{mkdtempSync,rmSync,mkdirSync}=require('node:fs'),{tmpdir}=require('node:os'),{join}=require('node:path');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-descriptions-')),python=process.env.PYTHON_PATH||'python3';let browser,server;
 const setup=`import os
from fixtures import prepare,populate
prepare(os.environ['ANALYTICS_DB'])
import analytics as a
a.init();populate(a)
s=a.serve(0,True,'127.0.0.1')
a.ORIGIN='http://127.0.0.1:'+str(s.server_port)
with a.connection() as db:
 a.instance.put(db,'site.url',a.ORIGIN)
 a.instance.put(db,'video.enabled','false')
 t=a.descriptions.get(db,a.descriptions.TABLES[0],a.descriptions.DEFAULT_ID)
 for section in t['sections']:
  for owner in [section,*section['merchants']]:
   for binding in owner['links']:
    row=a.affiliate_partners.save_tracked(db,{'name':binding['id'],'url':binding['reference_url']},a.story_url_valid,a.now_iso())
    source=db.execute("SELECT id FROM tracking_sources WHERE name='YouTube Description'").fetchone()[0]
    a.tracked_links.token_link(db,row['id'],source,a.ORIGIN,a.now_iso())
print(a.ORIGIN,flush=True)
s.serve_forever()`;
 try{
  server=spawn(python,['-u','-B','-c',setup],{cwd:__dirname,env:{...process.env,PYTHONIOENCODING:'utf-8',ANALYTICS_DB:join(temp,'stats.db'),UPLOAD_DIR:join(temp,'uploads')},stdio:['ignore','pipe','pipe']});
  let logs='';server.stderr.on('data',b=>logs+=b);
  const origin=await new Promise((resolve,reject)=>{let value='';const timer=setTimeout(()=>reject(Error('Server timeout: '+logs)),20000);server.stdout.on('data',b=>{value+=b;const match=value.match(/http:\/\/127\.0\.0\.1:\d+/);if(match){clearTimeout(timer);resolve(match[0])}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Server exited '+code+': '+logs))})});
  const api=async(path,data)=>{const r=await fetch(origin+'/api/descriptions/'+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(r.ok,await r.clone().text());return r.json()};
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const context=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],external=[];
  await context.route('**/*',route=>{if(!route.request().url().startsWith(origin)){external.push(route.request().url());return route.abort()}return route.continue()});
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin);await page.locator('[data-tab=descriptions]').click();
  const root=page.locator('#descriptions'),save=root.getByRole('button',{name:'Enregistrer le modèle',exact:true});
  await root.locator('.description-section').first().waitFor();
  assert.equal(await root.locator('.description-section').count(),7);
  assert.equal(await root.locator('.description-merchant').count(),2);
  assert.equal(await root.locator('.description-problems li').count(),4);
  assert(!await root.locator('[data-template-preview]').innerText().then(x=>x.includes('https://ko-fi.com')));
  // Bind the four exact existing catalogue records and historical source tokens.
  const fields=root.locator('.description-bindings fieldset');
  for(let i=0;i<4;i++){
   for(const key of [i===0?'support':i===1?'affiliate':'community',...(i===1?['domadoo']:[])]){
    const section=root.locator(`[data-section-id="${key}"]`);if(await section.getAttribute('open')===null)await section.locator(':scope > summary > span').click();
   }
   const row=fields.nth(i),options=await row.getByLabel('Fiche LinKs existante').locator('option').evaluateAll(nodes=>nodes.map(n=>({value:n.value,text:n.textContent})));
   const name=['kofi','domadoo-shop','instagram','discord'][i],choice=options.find(x=>x.text===name);assert(choice);
   await row.getByLabel('Fiche LinKs existante').selectOption(choice.value);
   const source=fields.nth(i).getByLabel('Source YouTube existante (actuelle ou historique)');
   await source.selectOption({label:'YouTube Description'});
  }
  await save.click();await root.locator('[data-description-status]').filter({hasText:'Modèle enregistré'}).waitFor();
  assert.equal(await root.locator('.description-problems li').count(),0);
  assert((await root.locator('[data-template-preview]').innerText()).includes('Merci pour votre soutien ❤️'));
  // A delayed save response must never erase text entered while it was in flight.
  let releaseSave;const gate=new Promise(resolve=>releaseSave=resolve);
  await page.route('**/api/descriptions/templates/domotik-youtube/save',async route=>{await gate;await route.continue()},{times:1});
  await root.getByLabel('Nom du modèle',{exact:true}).fill('Version envoyée');
  await Promise.all([page.waitForRequest(r=>r.url().endsWith('/domotik-youtube/save')),save.click()]);
  await root.getByLabel('Nom du modèle',{exact:true}).fill('Saisie pendant enregistrement');releaseSave();
  await root.locator('[data-description-status]').filter({hasText:'dernières modifications restent'}).waitFor();
  assert.equal(await root.getByLabel('Nom du modèle',{exact:true}).inputValue(),'Saisie pendant enregistrement');
  assert.equal((await api('templates')).items.find(x=>x.id==='domotik-youtube').name,'Version envoyée');
  // Preserve local edits on internal navigation and asynchronous reload attempts.
  await root.getByLabel('Nom du modèle',{exact:true}).fill('Mon modèle personnel');
  await page.locator('[data-tab=tracked-links]').click();await page.locator('[data-tab=descriptions]').click();
  assert.equal(await root.getByLabel('Nom du modèle',{exact:true}).inputValue(),'Mon modèle personnel');
  for(const key of (await root.locator('details[open]').evaluateAll(nodes=>nodes.map(n=>n.dataset.sectionId))).reverse())await root.locator(`[data-section-id="${key}"] > summary > span`).click();
  // Keyboard order keeps stable identities and persists after a refresh.
  await root.getByRole('button',{name:'Déplacer Hashtags',exact:true}).press('ArrowUp');
  await save.click();await root.locator('[data-description-status]').filter({hasText:'Modèle enregistré'}).waitFor();
  let template=(await api('templates')).items.find(x=>x.id==='domotik-youtube');assert.equal(template.sections[5].id,'hashtags');
  // Mouse drag also changes the persisted model without changing any section IDs.
  await root.getByRole('button',{name:'Déplacer Hashtags',exact:true}).dragTo(root.locator('.description-section > summary').first());
  await save.click();await root.locator('[data-description-status]').filter({hasText:'Modèle enregistré'}).waitFor();
  template=(await api('templates')).items.find(x=>x.id==='domotik-youtube');assert.equal(template.sections[0].id,'hashtags');
  // Another editor wins: retain our visible text and show the conflict.
  await root.getByLabel('Nom du modèle',{exact:true}).fill('Saisie locale conservée');
  await api('templates/'+template.id+'/save',{...template,name:'Autre onglet',expected_revision:template.revision});
  await save.click();await root.locator('[data-description-status]').filter({hasText:'changé ailleurs'}).waitFor();
  assert.equal(await root.getByLabel('Nom du modèle',{exact:true}).inputValue(),'Saisie locale conservée');
  page.once('dialog',dialog=>dialog.accept());await root.getByRole('button',{name:'Recharger',exact:true}).click();
  await root.getByLabel('Nom du modèle',{exact:true}).filter({visible:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('#descriptions input')?.value==='Autre onglet');
  // Duplicate includes the saved section IDs; editing the copy is independent.
  page.once('dialog',dialog=>dialog.accept('Modèle copié'));await root.getByRole('button',{name:'Dupliquer',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#descriptions input')?.value==='Modèle copié');
  assert.equal((await api('templates')).items.length,2);
  await root.getByRole('button',{name:'Descriptions',exact:true}).click();
  page.once('dialog',dialog=>dialog.accept('Brouillon de référence'));await root.getByRole('button',{name:'Nouveau brouillon',exact:true}).click();
  await root.locator('[data-draft-preview] h2').filter({hasText:'Brouillon de référence'}).waitFor();
  const draft=(await api('drafts')).items[0];assert(draft.text.includes('BOOST'));assert(!draft.text.includes('amzn.to'));
  await root.getByRole('button',{name:'Modèles',exact:true}).click();
  for(const theme of ['light','dark']){
   await page.selectOption('#theme-select',theme);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(process.env.DESCRIPTION_SCREENSHOTS){mkdirSync(process.env.DESCRIPTION_SCREENSHOTS,{recursive:true});await page.screenshot({path:join(process.env.DESCRIPTION_SCREENSHOTS,'descriptions-1920-'+theme+'.png'),fullPage:false})}
  }
  page.once('dialog',dialog=>dialog.accept());await root.getByRole('button',{name:'Supprimer le modèle',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#descriptions input')?.value==='Autre onglet');
  assert.equal((await api('drafts')).items[0].text,draft.text);
  assert.equal((await api('templates')).items.length,1);assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  console.log('Descriptions browser: templates, bindings, order, concurrency, drafts and both desktop themes OK');
 }finally{
  if(browser)await browser.close();
  if(server){server.kill();if(server.exitCode===null)await new Promise(resolve=>server.once('exit',resolve))}
  rmSync(temp,{recursive:true,force:true});
 }
})().catch(error=>{console.error(error);process.exitCode=1});
