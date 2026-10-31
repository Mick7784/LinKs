// Original adapter for the observed Domadoo customer portal. No stealth plugin,
// internal API, credential replay or inferred refused/pending commission status.
export const PORTAL = 'https://www.domadoo.fr/fr/affiliation';
export class PortalError extends Error {}
export function allowedPortalRequest(address,{human=false,method='GET',mainNavigation=false}={}) {
  let url;try{url=new URL(address)}catch{return false}
  const portal=['www.domadoo.fr','domadoo.fr'].includes(url.hostname);
  const verification=['www.google.com','www.gstatic.com','www.recaptcha.net','challenges.cloudflare.com'].includes(url.hostname);
  if(url.protocol!=='https:'||(url.port&&url.port!=='443')||url.username||url.password||!(portal||verification))return false;
  if(mainNavigation&&(!portal||!/^\/fr\/(affiliation|authentification)(\/|$)/.test(url.pathname)))return false;
  if(['GET','HEAD'].includes(method))return true;
  // Only the person at the login window may submit authentication or the site's
  // own verification requests. Collection remains GET/HEAD only, even here.
  return human&&method==='POST'&&(verification||(portal&&(
    /^\/fr\/authentification(\/|$)/.test(url.pathname)||url.pathname.startsWith('/cdn-cgi/challenge-platform/'))));
}
export async function securityChallenge(page) {
  return page.locator('body').evaluate(body=>{
    const visible=node=>node.getBoundingClientRect().width>0&&node.getBoundingClientRect().height>0;
    return [...body.querySelectorAll('#challenge-running,#challenge-stage,#challenge-form,iframe[src*="challenges.cloudflare.com"]')].some(visible)||
      [...body.querySelectorAll('h1,h2')].some(node=>visible(node)&&/performing security verification|verifying you are human|checking your browser|vérification de sécurité/i.test(node.textContent));
  });
}
export function cents(text) {
  const value = String(text).replace(/[\s\u00a0\u202f]/g,'').replace('−','-');
  if (!/^-?\d+(?:,\d{2})?€$/.test(value)) throw new PortalError('Montant Domadoo non reconnu.');
  const [whole,fraction='00']=value.slice(0,-1).replace('-','').split(',');
  const result=(Number(whole)*100+Number(fraction))*(value.startsWith('-')?-1:1);
  if(!Number.isSafeInteger(result))throw new PortalError('Montant hors limites.');
  return result;
}
export function count(text) {
  const value=String(text).replace(/[\s\u00a0\u202f]/g,'');
  if(!/^\d+$/.test(value)||!Number.isSafeInteger(Number(value)))throw new PortalError('Compteur Domadoo non reconnu.');
  return Number(value);
}
export function approval(text) {
  if(text==='check')return true;
  if(text==='close')return false;
  throw new PortalError('Statut Domadoo inconnu.');
}
const normalized=value=>value.trim().replace(/\s+/g,' ').toLowerCase();
export function summaryValues(entries) {
  const mapping={
    'clics':['clicks_30d','clicks_total'], 'clics uniques':['unique_clicks_30d','unique_clicks_total'],
    'ventes en attente':['pending_sales_30d'], 'ventes approuvées':['approved_sales_30d','approved_sales_total'],
    'gains':['earnings_30d'],'total des gains':['earnings_total'],'total des paiements':['payments_total'],
    'paiements en attente':['payments_pending'],'solde':['balance']
  };
  const result={};
  for(const [label,keys] of Object.entries(mapping)){
    const matches=entries.filter(e=>normalized(e.label)===label);
    if(matches.length!==keys.length)throw new PortalError('Libellés du résumé Domadoo modifiés.');
    matches.forEach((entry,index)=>{result[keys[index]]=keys[index].includes('clicks')||keys[index].includes('sales')?count(entry.value):cents(entry.value)});
  }
  return result;
}
export async function isConnected(page) {
  if(await securityChallenge(page))return false;
  const challenge=await page.locator('iframe[src*="captcha"],iframe[src*="challenge"],input[autocomplete="one-time-code"]').evaluateAll(nodes=>nodes.some(n=>n.getBoundingClientRect().width>0));
  return !challenge && new URL(page.url()).origin===new URL(PORTAL).origin && new URL(page.url()).pathname==='/fr/affiliation' &&
    await page.locator('#myaffiliateaccount-summary .list-group-hover').count()>0;
}
export async function assertPortal(page) {
  if(!await isConnected(page))
    throw new PortalError('Reconnexion requise : connexion, double vérification ou protection du portail. Intervention humaine requise.');
}
export async function readSummary(page) {
  const info=await page.locator('#myaffiliateaccount-summary').evaluate(root=>({
    headings:root.textContent,
    entries:[...root.querySelectorAll('.list-group-hover span.pull-xs-right')].map(span=>{
      const parent=span.parentElement.cloneNode(true);
      parent.querySelectorAll('span.pull-xs-right,.progress,script,style').forEach(n=>n.remove());
      return {label:parent.textContent.trim(),value:span.textContent.trim()};
    })
  }));
  if(!info.headings.includes('Last 30 days')||!info.headings.includes('Total'))throw new PortalError('Périodes du résumé non reconnues.');
  return summaryValues(info.entries);
}
export async function readTable(page,kind='sales') {
  const root=kind==='sales'?'#myaffiliateaccount-sales-commissions':'#myaffiliateaccount-myvouchers';
  return page.locator(root).evaluate((section,kind)=>{
    const table=section.querySelector('table');
    if(!table)throw new Error('Missing table');
    return {headers:[...table.querySelectorAll('thead th')].map(n=>n.textContent.trim()),
      rows:[...table.querySelectorAll('tbody tr')].map(row=>{
        const cells=[...row.querySelectorAll('td')];
        if(cells.length!==5)return {empty:cells.length===1 && /aucun|no .*found|no .*available/i.test(row.textContent)};
        const icon=i=>(cells[i].querySelector('.material-icons')?.textContent||cells[i].textContent).trim();
        // Voucher code (cell 1) is deliberately never read.
        return kind==='sales'?{id:cells[0].textContent.trim(),date:cells[1].textContent.trim(),order:cells[2].textContent.trim(),commission:cells[3].textContent.trim(),approved:icon(4)}:
          {date:cells[0].textContent.trim(),amount:cells[2].textContent.trim(),approved:icon(3),used:icon(4)};
      }),links:[...section.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')).filter(href=>href.includes('p='))};
  },kind);
}
export function parseTable(raw,kind='sales') {
  const headers=kind==='sales'?['ID','Date','Total de la commande','Votre commission','Approuvé']:['Créé à','Code','Montant','Approuvé','Utilisé'];
  if(raw.headers.map(normalized).join('|')!==headers.map(normalized).join('|'))throw new PortalError('Colonnes Domadoo modifiées.');
  return raw.rows.filter(row=>!row.empty).map(row=>{
    if(kind==='sales'){
      if(!/^#?\d+$/.test(row.id)||!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(row.date))throw new PortalError('Vente Domadoo illisible.');
      return {provider_id:row.id.replace('#',''),occurred_at:row.date,order_cents:cents(row.order),commission_cents:cents(row.commission),currency:'EUR',status:approval(row.approved)?'approved':'not_approved'};
    }
    let date=row.date;
    if(!/^\d{4}-\d{2}-\d{2}$/.test(date)){
      const match=/^([A-Za-z]{3}) (\d{1,2}), (\d{4})$/.exec(date);
      const month=match?['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].indexOf(match[1])+1:0;
      if(!month)throw new PortalError('Date du bon de paiement non reconnue.');
      date=`${match[3]}-${String(month).padStart(2,'0')}-${match[2].padStart(2,'0')}`;
    }
    return {issued_on:date,amount_cents:cents(row.amount),approved:approval(row.approved),used:approval(row.used)};
  });
}
function pagination(raw,base){
  const links=new Map();
  for(const href of raw.links){
    const url=new URL(href,base),number=Number(url.searchParams.get('p'));
    if(url.origin!==new URL(PORTAL).origin||url.pathname!=='/fr/affiliation'||!Number.isInteger(number)||number<1)throw new PortalError('Lien de pagination inattendu.');
    links.set(number,url.href);
  }
  return links;
}
async function traverse(page,kind,deadline,pause){
  let current=1,last=1,first=null;const rows=[],ids=new Set();
  while(true){
    if(Date.now()>deadline)throw new PortalError('Délai de collecte dépassé : relevé incomplet, ancien relevé conservé.');
    await assertPortal(page);
    const raw=await readTable(page,kind),batch=parseTable(raw,kind),links=pagination(raw,page.url());
    const detected=Math.max(current,...links.keys());
    if(current===1){last=detected;first=JSON.stringify(batch)}
    if(detected!==last && current<last)throw new PortalError('Pagination modifiée pendant la lecture. Réessayer.');
    if(!batch.length&&last>1)throw new PortalError('Page vide dans un historique paginé.');
    for(const row of batch){
      if(kind==='sales'){
        if(ids.has(row.provider_id))throw new PortalError('Vente en double entre deux pages : relevé incomplet.');
        ids.add(row.provider_id);
      }
      rows.push(row);
    }
    if(current===last)break;
    const next=links.get(current+1);
    if(!next)throw new PortalError('Page suivante manquante : relevé incomplet.');
    await pause();await page.goto(next,{waitUntil:'domcontentloaded'});
    if(Number(new URL(page.url()).searchParams.get('p'))!==current+1)throw new PortalError('La pagination a redirigé vers une autre page.');
    current++;
  }
  return {rows,pages:last,first};
}
export async function collect(page,{pause=()=>new Promise(r=>setTimeout(r,1000)),budgetMs=30*60*1000}={}){
  const deadline=Date.now()+budgetMs;
  await page.goto(PORTAL,{waitUntil:'domcontentloaded'});await assertPortal(page);
  const summary=await readSummary(page);
  const sales=await traverse(page,'sales',deadline,pause);
  await pause();await page.goto(PORTAL,{waitUntil:'domcontentloaded'});await assertPortal(page);
  const vouchers=await traverse(page,'vouchers',deadline,pause);
  await pause();await page.goto(PORTAL,{waitUntil:'domcontentloaded'});await assertPortal(page);
  const check=await readTable(page),last=Math.max(1,...pagination(check,page.url()).keys());
  if(JSON.stringify(parseTable(check))!==sales.first||last!==sales.pages||JSON.stringify(await readSummary(page))!==JSON.stringify(summary))
    throw new PortalError('Le portail a changé pendant la collecte. Dernier relevé conservé ; relancer la synchronisation.');
  return {complete:true,currency:'EUR',summary,transactions:sales.rows,vouchers:vouchers.rows,pages:sales.pages};
}
