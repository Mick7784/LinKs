// One targeted import journey, disposable database, no Amazon/network access.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn,spawnSync}=require('node:child_process'),{mkdtempSync,rmSync}=require('node:fs'),{join}=require('node:path'),{tmpdir}=require('node:os');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-amazon-'));let browser,server;
 try{
  server=spawn(process.env.PYTHON_PATH||'python3',['-u','-B','-c',`import os
from fixtures import prepare,populate
prepare(os.environ['ANALYTICS_DB'])
import analytics as a
import affiliation as aff
from unittest.mock import patch
a.init();populate(a)
with a.connection() as db:
 with patch.object(aff,'stamp',return_value='2026-11-02T12:00:00Z'):
  aff.ingest(db,'domadoo',{'complete':True,'currency':'EUR','summary':{k:0 for k in aff.SUMMARY_KEYS},'pages':1,'vouchers':[],'transactions':[{'provider_id':'1','occurred_at':'2026-10-30 12:00:00','order_cents':10000,'commission_cents':992,'currency':'EUR','status':'approved'}]})
s=a.serve(0,True,'127.0.0.1')
a.ORIGIN='http://127.0.0.1:'+str(s.server_port)
with a.connection() as db:
 a.instance.put(db,'site.url',a.ORIGIN)
 a.instance.put(db,'video.enabled','false')
print(a.ORIGIN,flush=True)
s.serve_forever()`],{cwd:__dirname,env:{...process.env,PYTHONIOENCODING:'utf-8',ANALYTICS_DB:join(temp,'db.sqlite'),UPLOAD_DIR:join(temp,'uploads')},stdio:['ignore','pipe','pipe']});
  let logs='';server.stderr.on('data',b=>logs+=b);
  const origin=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error(logs||'Server timeout')),20000);server.on('error',reject);server.stdout.on('data',b=>{output+=b;const m=output.match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);resolve(m[0])}});server.on('exit',()=>{clearTimeout(timer);reject(Error(logs))})});
  const api=async(path,data)=>{const r=await fetch(origin+'/api/affiliation/'+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Links-Request':'1'},body:data?JSON.stringify(data):undefined});assert(r.ok,await r.clone().text());return r.json()};
  const account=await api('accounts',{partner:'Amazon','label':'France test','platform':'amazon'});
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.request().url().startsWith(origin)?r.continue():r.abort());
  await page.goto(origin);await page.locator('[data-tab=affiliation]').click();await page.getByRole('button',{name:'Gérer les partenaires',exact:true}).click();
  await page.locator('.aff-partner').filter({hasText:'France test'}).getByRole('button',{name:'Voir les détails'}).click();
  page.setDefaultTimeout(10000);
  const zip=files=>{const r=spawnSync(process.env.PYTHON_PATH||'python3',['-X','utf8','-B','-c',"import sys,json,io,zipfile; b=io.BytesIO(); z=zipfile.ZipFile(b,'w'); [z.writestr(zipfile.ZipInfo(k,date_time=(2026,1,1,0,0,0)),v) for k,v in json.load(sys.stdin).items()]; z.close(); sys.stdout.buffer.write(b.getvalue())"],{input:JSON.stringify(files)});assert.equal(r.status,0,r.stderr.toString());return r.stdout};
  const category=amount=>`Période: 2026-10-30 → 2026-10-31\nScope: all\nCurrency: EUR\nCatégorie;Clics;Articles commandés;Articles expédiés;Revenus totaux\nMaison;20;4;3;${amount}\n`;
  const upload=async files=>{await page.locator('#amz-zip').setInputFiles({name:'reports.zip',mimeType:'application/zip',buffer:zip(files)});await page.locator('#amz-send').click();};
  const open=()=>page.getByRole('button',{name:'Importer un ZIP Amazon',exact:true}).first().click();
  await open();
  const files={'Category.csv':category('51,87'),'Tracking-Id.csv':category('51,87').replace('Catégorie','Tracking ID').replace('Maison','synthetic-21')};
  await upload(files);await page.waitForFunction(()=>{const n=document.getElementById('amz-zip-result');return n&&!n.textContent.includes('Analyse des rapports')&&!n.textContent.includes('Lecture de l’archive')});assert.match(await page.locator('#amz-zip-result').innerText(),/Import terminé/,JSON.stringify(errors));
  assert.match(await page.locator('#amz-zip-result').innerText(),/2 fichiers traités/);
  assert.match(await page.locator('#amz-zip-result').innerText(),/51,87/);
  assert.match(await page.locator('#amz-zip-result').innerText(),/sans ventilation quotidienne/);
  await page.locator('#aff-dialog [data-aff=close]').click();
  await page.getByRole('button',{name:'Tous les partenaires',exact:true}).click();
  await page.locator('#aff-start').fill('2026-10-30');await page.locator('#aff-end').fill('2026-10-31');await page.locator('[data-aff=range]').click();
  await page.waitForFunction(()=>document.querySelectorAll('[data-overview-date]').length===2&&document.querySelector('[data-overview-total]')?.textContent.includes('61,79'));
  assert.match(await page.locator('[data-overview-undated]').innerText(),/51,87/);
  assert.equal(await page.locator('[data-overview-date]').count(),2);
  const overview=(await api('overview?start=2026-10-30&end=2026-10-31')).overview;
  assert.equal(overview.total_cents,6179);assert.equal(overview.daily.reduce((n,d)=>n+(d.cents||0),0),992);
  assert(await page.locator('[data-overview-compare=previous]').isDisabled());
  assert.match(await page.locator('[data-overview-period]').innerText(),/Déclarées dans les rapports/);
  await page.getByRole('navigation',{name:'Partenaires affiliation'}).getByRole('button',{name:'Amazon',exact:true}).click();
  await open();await upload(files);await page.getByText('Archive déjà importée : aucun doublon, aucune ancienne version réactivée.',{exact:true}).waitFor();
  await upload({'Category.csv':category('52,00'),'Tracking-Id.csv':files['Tracking-Id.csv'].replace('51,87','52,00')});
  await page.getByRole('heading',{name:'Import terminé',exact:true}).waitFor();
  assert.equal((await api('overview?account='+account.id)).amazon[0].totals.commission_cents,5200);
  await upload({'Category.csv':category('99,00').replace('2026-10-30','2026-10-29')});
  await page.getByRole('heading',{name:'Archive conservée à vérifier',exact:true}).waitFor();
  assert.equal((await api('overview?account='+account.id)).amazon[0].totals.commission_cents,5200);
  await upload({'Unknown.csv':'Catégorie;Revenus totaux\nMaison;1,00\n'});
  await page.getByRole('heading',{name:'Archive conservée à vérifier',exact:true}).waitFor();
  assert.equal(await page.locator('#amz-coverage input').count(),0);
  const pendingReport=(await api('overview?account='+account.id)).amazon[0];
  assert.equal(pendingReport.totals.commission_cents,5200);
  assert.equal(pendingReport.pending.length,2);
  const saved=await api('amazon/pending-archive',{account:account.id,id:pendingReport.pending[0].id});
  assert(saved.archive.length>0);
  await page.locator('#aff-dialog [data-aff=close]').click();
  await page.getByRole('button',{name:'Rapports et imports',exact:true}).click();
  await page.getByRole('heading',{name:'Archives nécessitant une attention · 2',exact:true}).waitFor();
  const archiveId=pendingReport.pending[0].id;
  await page.locator('[data-aff=archive-diagnostic][data-id="'+archiveId+'"]').click();
  await page.getByRole('dialog').getByText('Historique des analyses et décisions',{exact:true}).waitFor();
  assert.match(await page.getByRole('dialog').innerText(),/Encodage|UTF|utf/);
  await page.locator('#aff-dialog [data-aff=close]').click();
  const downloaded=page.waitForEvent('download');
  await page.locator('[data-aff=pending-download][data-id="'+archiveId+'"]').click();
  assert.equal((await downloaded).suggestedFilename(),'reports.zip');
  const ignored=page.waitForResponse(r=>r.url().endsWith('/amazon/ignore-archive'));
  await page.locator('[data-aff=archive-ignore][data-id="'+archiveId+'"]').click();await ignored;
  await page.getByRole('heading',{name:'Archives nécessitant une attention · 1',exact:true}).waitFor();
  assert.equal((await api('overview?account='+account.id)).amazon[0].totals.commission_cents,5200);
  await page.locator('[data-aff=archive-reanalyze][data-id="'+archiveId+'"]').click();
  await page.getByRole('heading',{name:'Archives nécessitant une attention · 2',exact:true}).waitFor();
  const batchDone=page.waitForResponse(r=>r.url().endsWith('/amazon/reanalyze-pending'));
  await page.locator('[data-aff=archives-reanalyze]').click();
  const batchResult=await (await batchDone).json();assert.equal(batchResult.results.length,2);
  await page.locator('[data-aff=archives-reanalyze]').waitFor({state:'visible'});
  assert.equal((await api('overview?account='+account.id)).amazon[0].totals.commission_cents,5200);
  await page.setViewportSize({width:390,height:900});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Archive manager fits mobile');
  if(process.env.ARCHIVE_SCREENSHOT)await page.screenshot({path:process.env.ARCHIVE_SCREENSHOT,fullPage:true});
  await page.setViewportSize({width:1280,height:900});
  // A recognized ranking is retained as complementary, with no invented totals.
  const ranking=await api('amazon/import-zip',{account:account.id,archive:zip({'Top-Sellers.csv':'Préambule\nRank;ASIN;Titre du produit\n1;B000000001;Lampe\n'}).toString('base64'),filename:'top-sellers.zip'});
  assert.equal(ranking.state,'complementary');assert.equal(ranking.imported,false);
  await page.evaluate(()=>window.LinksAffiliation.load());
  await page.getByText('Archive complémentaire',{exact:true}).waitFor();
  await open();
  const drop=zip({'Category.csv':category('52,00'),'Tracking-Id.csv':files['Tracking-Id.csv'].replace('51,87','52,00')});
  await page.locator('#amz-drop').evaluate((element,bytes)=>{const transfer=new DataTransfer();transfer.items.add(new File([new Uint8Array(bytes)],'reports.zip',{type:'application/zip'}));element.dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:transfer}))},[...drop]);
  await page.locator('#amz-send').click();
  await page.getByText('Archive déjà importée : aucun doublon, aucune ancienne version réactivée.',{exact:true}).waitFor();
  // A response to a closed import must not mutate a replacement manual dialog.
  let release;const gate=new Promise(resolve=>release=resolve);
  await page.route('**/api/affiliation/amazon/import-zip',async route=>{await gate;await route.continue()});
  const pending=page.waitForRequest('**/api/affiliation/amazon/import-zip');
  await upload(files);await pending;
  await page.locator('#aff-dialog [data-aff=close]').click();await open();
  await page.getByText('Diagnostic et import manuel avancé',{exact:true}).click();await page.locator('#amz-manual').click();
  const refreshed=page.waitForResponse(r=>r.url().includes('/api/affiliation/overview?'));
  release();await refreshed;await page.locator('#amz-file').waitFor();
  await page.setViewportSize({width:390,height:900});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No mobile document overflow');
  assert.deepEqual(errors,[]);console.log('PASS Amazon ZIP: import, live statistics, duplicates, corrections, overlaps, diagnostics, download, ignore/reanalyze, batch, complementary ranking, mobile.');
 }finally{if(browser)await browser.close();if(server){server.kill();if(server.exitCode===null)await new Promise(r=>server.once('exit',r))}rmSync(temp,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exitCode=1});
