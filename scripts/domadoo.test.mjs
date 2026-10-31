import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {cents,approval,parseTable,collect,PORTAL} from './domadoo.mjs';
const require=createRequire(import.meta.url);
test('strict signed EUR and unknown status',()=>{
  assert.equal(cents('1\u202f234,56 €'),123456);assert.equal(cents('−12,34 €'),-1234);assert.equal(cents('0 €'),0);
  for(const v of ['','invalid','1,234.56 €','12,3 €','€12.34','10 USD'])assert.throws(()=>cents(v));
  assert.equal(approval('close'),false);assert.throws(()=>approval('cancel'));
});
const summary=()=>`<section id="myaffiliateaccount-summary"><h3>Last 30 days</h3><div class="list-group-hover">${[['Clics','8'],['Clics uniques','12'],['Ventes en attente','2'],['Ventes approuvées','3'],['Gains','12,34 €']].map(([label,value])=>`<div>${label}<span class="pull-xs-right">${value}</span></div>`).join('')}</div><h3>Total</h3><div class="list-group-hover">${[['Clics','80'],['Clics uniques','120'],['Ventes approuvées','30'],['Total des gains','123,45 €'],['Total des paiements','100,00 €'],['Paiements en attente','0,00 €'],['Solde','23,45 €']].map(([label,value])=>`<div>${label}<span class="pull-xs-right">${value}</span></div>`).join('')}</div></section>`;
function fixture(page,last,{duplicate=false,broken=false,changed=false}={}){
 const id=duplicate&&page===2?1:page;
 const links=page<last?`<a href="/fr/affiliation?t=sales&p=${page+1}">Suivante</a>`:'';
 return `<!doctype html><html><body>${summary()}<section id="myaffiliateaccount-sales-commissions"><table><thead><tr>${['ID','Date','Total de la commande','Votre commission',broken?'État':'Approuvé'].map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody><tr><td>#${changed?id+1000:id}</td><td>2026-10-21 12:00:00</td><td>100,00 €</td><td>${page===3?'-4,00':'4,00'} €</td><td><i class="material-icons">${page%2?'check':'close'}</i></td></tr></tbody></table>${links}<a href="/fr/affiliation?t=sales&p=${last}">»</a></section><section id="myaffiliateaccount-myvouchers"><table><thead><tr>${['Créé à','Code','Montant','Approuvé','Utilisé'].map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody><tr><td>Dec 11, 2025</td><td>DO-NOT-COLLECT-THIS-CODE</td><td>12,00 €</td><td><i class="material-icons">check</i></td><td><i class="material-icons">close</i></td></tr></tbody></table></section></body></html>`;
}
test('105 pages, duplicates, altered markup, mid-crawl movement and challenges',{timeout:120000},async()=>{
 const {chromium}=require('playwright-core');
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH});
 try{
   let scenario={},last=105,visits=0;
   const context=await browser.newContext();await context.route('**/*',route=>{
     const url=new URL(route.request().url()),p=Number(url.searchParams.get('p')||1);if(p===1)visits++;
     return route.fulfill({contentType:'text/html; charset=utf-8',body:scenario.challenge?'<html><input autocomplete="one-time-code"></html>':fixture(p,last,{...scenario,changed:scenario.moving&&visits>2})});
   });
   const page=await context.newPage();
   const result=await collect(page,{pause:async()=>{}});assert.equal(result.transactions.length,105);assert.equal(result.pages,105);
   assert.equal(result.transactions[2].commission_cents,-400);assert.equal(result.transactions[1].status,'not_approved');
   assert.equal(result.summary.unique_clicks_30d,12);assert.equal(result.summary.clicks_30d,8);
   assert.equal(JSON.stringify(result).includes('DO-NOT-COLLECT'),false);assert.equal(result.vouchers[0].issued_on,'2025-12-11');
   last=3;
   for(const next of [{duplicate:true},{broken:true},{moving:true},{challenge:true}]){
     scenario=next;visits=0;await assert.rejects(()=>collect(page,{pause:async()=>{}}));
   }
   scenario={};await assert.rejects(()=>collect(page,{budgetMs:-1,pause:async()=>{}}));
 }finally{await browser.close()}
});
test('session is authenticated ciphertext, outside SQLite and portable backups',async()=>{
 const directory=await mkdtemp(join(tmpdir(),'links-aff-session-'));process.env.AFFILIATION_DATA_DIR=directory;
 const {saveSession,loadSession}=await import('./affiliation-worker.mjs');
 try{
   const data={cookies:[{name:'example',value:'SYNTHETIC-SECRET'}],origins:[]};await saveSession('domadoo',data);
   const stored=await readFile(join(directory,'domadoo.session'));assert.equal(stored.includes('SYNTHETIC-SECRET'),false);assert.deepEqual(await loadSession('domadoo'),data);
   const {writeFile}=await import('node:fs/promises');stored[stored.length-1]^=1;await writeFile(join(directory,'domadoo.session'),stored);await assert.rejects(()=>loadSession('domadoo'));
 }finally{await rm(directory,{recursive:true,force:true})}
});
