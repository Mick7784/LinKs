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
  const csv='Date,Tag,clics,articles commandés,articles expédiés,revenus totaux\n10-31-2026,test-21,7,3,2,3.75\n';
  const payload={account:account.id,csv,kind:'performance',view:'category',mapping:{date:'Date',clicks:'clics',ordered_items:'articles commandés',shipped_items:'articles expédiés',commission_cents:'revenus totaux'},start:'2026-10-31',end:'2026-10-31',scope:'all',date_format:'mdy',decimal:'dot',confirmed:true};
  await api('amazon/import',payload);
  await api('amazon/import',{...payload,view:'tracking_id',contribution:'detail',mapping:{...payload.mapping,tracking_id:'Tag'}});
  await page.goto(origin);await page.locator('[data-tab=affiliation]').click();await page.getByRole('button',{name:'Gérer les partenaires',exact:true}).click();
  await page.locator('.aff-partner').filter({hasText:'France test'}).getByRole('button',{name:'Voir les détails'}).click();
  await page.locator('.aff-card').filter({hasText:'Clics Amazon'}).waitFor();
  assert.equal(await page.locator('.aff-card').filter({hasText:'Clics Amazon'}).locator('strong').innerText(),'7');
  assert.match(await page.locator('section.panel').filter({has:page.getByRole('heading',{name:'Évolution quotidienne',exact:true})}).innerText(),/2026-10-31/);
  assert.match(await page.locator('section.panel').filter({has:page.getByRole('heading',{name:'Répartition par Tracking ID',exact:true})}).innerText(),/test-21/);
  assert.deepEqual(errors,[]);console.log('PASS statistiques Amazon : clics, évolution datée, répartition distincte.');
 }finally{if(browser)await browser.close();if(server){server.kill();if(server.exitCode===null)await new Promise(r=>server.once('exit',r))}rmSync(temp,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exitCode=1});
