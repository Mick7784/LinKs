// One targeted import journey, disposable database, no Amazon/network access.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process'),{mkdtempSync,rmSync}=require('node:fs'),{join}=require('node:path'),{tmpdir}=require('node:os');
(async()=>{
 const temp=mkdtempSync(join(tmpdir(),'links-amazon-'));let browser,server;
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
  await page.getByRole('button',{name:'Importer un rapport CSV',exact:true}).first().click();
  const csv='Date;Tag;Produit;Expédiés;Commission\n01/11/2026;site-21;Écran 😀;2;12,34\n';
  await page.locator('#amz-file').setInputFiles({name:'earnings.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});
  await page.locator('#amz-start').fill('2026-11-01');await page.locator('#amz-end').fill('2026-11-01');
  await page.locator('#amz-inspect').click();await page.locator('[data-amazon-column=date]').selectOption('Date');
  for(const [key,value] of [['tracking_id','Tag'],['title','Produit'],['shipped_items','Expédiés'],['commission_cents','Commission']])await page.locator(`[data-amazon-column=${key}]`).selectOption(value);
  await page.locator('#amz-preview').click();await page.locator('#amz-submit').waitFor({state:'visible'});await page.waitForFunction(()=>!document.getElementById('amz-submit').disabled);
  assert.match(await page.locator('#amz-review').innerText(),/12,34/);await page.locator('#amz-confirm').check();await page.locator('#amz-submit').click();await page.locator('#aff-dialog').waitFor({state:'hidden'});
  await page.locator('#affiliation').getByRole('button',{name:'Vue d’ensemble',exact:true}).click();await page.locator('#aff-period').selectOption('all');await page.locator('[data-aff=range]').click();
  await page.getByText('site-21',{exact:false}).first().waitFor();
  const report=await api('overview?account='+account.id);
  assert.equal(report.amazon[0].totals.commission_cents,1234);assert.equal(report.amazon[0].totals.shipped_items,2);assert.equal(report.amazon[0].totals.orders,null);assert.deepEqual(report.losses,[]);
  await page.getByRole('button',{name:'Tous les partenaires',exact:true}).click();await page.locator('.aff-card').filter({hasText:/^Commissions Amazon/}).waitFor();
  assert.match(await page.locator('.aff-card').filter({hasText:'Commissions observées'}).innerText(),/12,34/);
  assert.deepEqual(errors,[]);console.log('PASS Amazon CSV: mapping, confirmation, private API, detailed/global totals, Tracking IDs, unknown orders and no inferred losses.');
 }finally{if(browser)await browser.close();if(server){server.kill();if(server.exitCode===null)await new Promise(r=>server.once('exit',r))}rmSync(temp,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exitCode=1});
