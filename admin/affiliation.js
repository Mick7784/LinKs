"use strict";
(()=>{
 const host=$('affiliation');let model=null,account='',tab='overview',page=1,search='',status='',start='',end='',timer=null,loginTimer=null,loginAccount='',renderVersion=0,initialRange=true;
 const euro=v=>v===null||v===undefined?'—':new Intl.NumberFormat('fr-FR',{style:'currency',currency:'EUR'}).format(v/100);
 const number=v=>v===null||v===undefined?'—':fmt.format(v);
 const at=v=>v?new Intl.DateTimeFormat('fr-FR',{dateStyle:'short',timeStyle:'short',timeZone:adminTimezone}).format(new Date(v)):'Jamais';
 const request=(action,data)=>api('/api/affiliation/'+action,data?{method:'POST',body:JSON.stringify(data)}:{});
 const selected=()=>model?.accounts.find(a=>a.id===account);
 const sum=(rows,kind)=>rows.filter(r=>!kind||r.status===kind).reduce((n,r)=>n+r.cents,0);
 const badge=a=>a.available?`<span class="aff-badge ${a.session_state==='connected'?'aff-good':''}">${a.running?'Synchronisation…':({connected:'Session enregistrée',reconnect:'À reconnecter',disconnected:'À connecter'}[a.session_state]||'À connecter')}</span>`:'<span class="aff-badge">Connecteur à venir</span>';
 const kpi=(label,value,help,tone='cyan')=>`<article class="aff-card aff-${tone}"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(help)}</small></article>`;
 function range(){return new URLSearchParams({account,start,end})}
 function month(){const d=new Intl.DateTimeFormat('sv-SE',{timeZone:adminTimezone}).format(new Date());start=d.slice(0,7)+'-01';end=d}
 function chart(rows){
   if(!rows.length)return '<p class="aff-empty">Aucune vente observée pour cette période.</p>';
   const monthly=new Set(rows.map(r=>r.day)).size>60,groups=new Map();
   for(const row of rows){const key=monthly?row.day.slice(0,7):row.day;const values=groups.get(key)||{approved:0,not_approved:0};values[row.status]+=row.cents;groups.set(key,values)}
   const items=[...groups],values=items.flatMap(([,v])=>[v.approved,v.not_approved]),max=Math.max(1,...values),min=Math.min(0,...values),y=v=>160-(v-min)/(max-min)*140,zero=y(0),width=600/Math.max(1,items.length);
   return `<svg viewBox="0 0 700 205" role="img" aria-label="Commissions ${monthly?'mensuelles':'quotidiennes'}, par date de vente"><line x1="65" x2="680" y1="${zero}" y2="${zero}" stroke="currentColor" opacity=".3"/><text x="0" y="20">${esc(euro(max))}</text><text x="0" y="160">${esc(euro(min))}</text>${items.map(([day,v],i)=>['approved','not_approved'].map((key,j)=>`<rect class="aff-bar-${key}" x="${70+i*width+j*width*.4}" y="${Math.min(zero,y(v[key]))}" width="${Math.max(1,width*.36)}" height="${Math.max(0,Math.abs(y(v[key])-zero))}"><title>${esc(day)} · ${key==='approved'?'Approuvées':'Non approuvées'} : ${esc(euro(v[key]))}</title></rect>`).join('')+(i===0||i===items.length-1||i%Math.max(1,Math.ceil(items.length/6))===0?`<text x="${70+i*width}" y="188" text-anchor="start">${esc(day.slice(monthly?0:5))}</text>`:'')).join('')}</svg><p class="aff-legend"><span>● Approuvées</span><span>● Non approuvées</span></p>`;
 }
 async function load(){
   if(initialRange){month();initialRange=false;}
   try{
     model=await request('overview?'+range());render();
     clearTimeout(timer);if(model.accounts.some(a=>a.running))timer=setTimeout(()=>{if(host.classList.contains('active'))load()},3000);
   }catch(e){say(e.message,true);if(!model)host.innerHTML='<h1>Affiliation</h1><p role="alert">Chargement indisponible.</p><button data-aff="reload">Réessayer</button>'}
 }
 function render(){
   renderVersion++;
   const current=selected(),label=current?current.partner:'Affiliation',rows=model.aggregate,has=model.has_data,snap=current?.snapshot,summary=snap?.summary;
   const candidates=current?[current]:model.accounts;
   const payments=candidates.filter(a=>a.snapshot).reduce((n,a)=>n+a.snapshot.summary.payments_total,0);
   const tabs=[['overview','Vue d’ensemble'],...(current?[['sales','Ventes et commissions'],['payments','Paiements'],['settings','Connexion et synchronisation']]:[['partners','Mes partenaires']])];
   if(!tabs.some(t=>t[0]===tab))tab='overview';
   host.innerHTML=`<div class="section-head"><div><p class="aff-eyebrow">ANALYSER · AFFILIATION</p><h1>${esc(label)} ${current?badge(current):''}</h1><p>${current?esc(current.label)+' · '+esc(current.platform):'Vos revenus et l’état de vos partenaires.'}</p></div><div class="aff-actions">${current?'<button data-aff="global">Tous les partenaires</button>':'<button data-aff="partners">Gérer les partenaires</button>'}<button class="primary" data-aff="sync" ${current&&!current.available?'disabled':''}>${current?'Synchroniser':'Synchroniser les comptes connectés'}</button></div></div>
    <nav class="aff-tabs" aria-label="Rubriques affiliation">${tabs.map(([id,title])=>`<button data-aff-tab="${id}" ${tab===id?'aria-current="page" class="active"':''}>${title}</button>`).join('')}</nav>
    <div class="aff-filters" ${!['overview','sales'].includes(tab)?'hidden':''}><label>Période<select id="aff-period"><option value="custom">Dates sélectionnées</option><option value="month">Ce mois</option><option value="30">30 derniers jours</option><option value="all">Tout l’historique observé</option></select></label><label>Du<input id="aff-start" type="date" value="${esc(start)}"></label><label>Au<input id="aff-end" type="date" value="${esc(end)}"></label><button data-aff="range">Appliquer</button><small>Dates des ventes · fuseau du portail non documenté</small></div>
    ${current?`<p class="aff-freshness">Dernier relevé complet : <strong>${esc(at(current.last_success))}</strong>${snap?' · '+number(snap.row_count)+' ventes · '+number(snap.pages)+' pages · '+(snap.source==='portal'?'Portail Domadoo':'Import manuel'):''}</p>${current.last_error?`<p class="aff-alert" role="status">${esc(current.last_error)} Le dernier relevé valide reste affiché.</p>`:''}`:`<p class="aff-freshness">${model.coverage.ready} / ${model.coverage.total} comptes disposent d’un relevé. Les totaux portent uniquement sur ces comptes.</p>`}
    <div id="aff-content"></div><dialog id="aff-dialog" aria-labelledby="aff-dialog-title"></dialog>`;
   const content=$('aff-content');
   if(tab==='overview'){
     content.innerHTML=`${!has?'<div class="aff-empty"><h2>Vos revenus apparaîtront après la première synchronisation.</h2><p>Connectez Domadoo dans « Connexion et synchronisation ». Les autres plateformes pourront être préparées dans Mes partenaires.</p><button data-aff="open" data-id="domadoo">Configurer Domadoo</button></div>':''}
      <div class="aff-kpis">${kpi('Commissions observées',has?euro(sum(rows)):'—','Approuvées + non approuvées · période')}${kpi('Commissions approuvées',has?euro(sum(rows,'approved')):'—','Statut actuel · date de vente','blue')}${kpi('Non approuvées',has?euro(sum(rows,'not_approved')):'—','Attente / refus non distingués par Domadoo','purple')}${kpi('Total des paiements',has?euro(payments):'—','Cumul du portail · indépendant de la période','green')}</div>
      <section class="panel aff-chart"><div class="panel-title"><h2>Évolution des commissions</h2><small>Montants actuellement observés, corrections incluses</small></div>${chart(model.daily)}</section>
      <div class="aff-grid">${current?`<section class="panel"><h2>Résumé du portail · Last 30 days</h2><dl class="aff-facts">${[['Gains',summary?euro(summary.earnings_30d):'—'],['Ventes approuvées',number(summary?.approved_sales_30d)],['Ventes en attente',number(summary?.pending_sales_30d)],['Clics',number(summary?.clicks_30d)],['Clics uniques',number(summary?.unique_clicks_30d)]].map(([k,v])=>`<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl><small>Fenêtre native de 30 jours au dernier relevé, indépendante du filtre. Les clics ne sont pas des statistiques LinKs.</small></section><section class="panel"><h2>Solde et gains cumulés</h2><dl class="aff-facts">${[['Total des gains',euro(summary?.earnings_total)],['Paiements en attente',euro(summary?.payments_pending)],['Solde',euro(summary?.balance)]].map(([k,v])=>`<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl><p>Les commissions refusées et la date de validation ne sont pas fournies séparément.</p><button data-aff="settings">Connexion et synchronisation</button></section>`:`<section class="panel"><h2>Répartition par partenaire</h2>${partnerDistribution()}</section><section class="panel"><h2>Mes partenaires</h2>${partnerList()}</section>`}</div>`;
   }else if(tab==='partners'){
     content.innerHTML=`<section class="panel"><div class="panel-title"><h2>Mes partenaires d’affiliation</h2><button class="primary" data-aff="add">Ajouter un partenaire</button></div><p>Un partenaire commercial peut avoir plusieurs comptes. Chaque compte utilise une plateforme de reporting.</p>${partnerList()}<p class="field-help">Amazon, Affiliatly (Reolink), GoAffPro (Sanyipace), Awin et Impact : préparation des comptes disponible, connecteurs à venir.</p></section>`;
   }else if(tab==='sales'){
     content.innerHTML=`<section class="panel"><div class="panel-title"><h2>Ventes et commissions</h2><button data-aff="export">Exporter cette sélection</button></div><form id="aff-search-form" class="aff-filters"><label>Rechercher un ID<input id="aff-search" value="${esc(search)}" maxlength="80" placeholder="Numéro de vente"></label><label>Statut<select id="aff-status"><option value="">Tous les statuts</option><option value="approved">Approuvée</option><option value="not_approved">Non approuvée</option><option value="missing">Absente du dernier relevé</option></select></label><button>Rechercher</button></form><p>Une vente absente reste historisée ; son absence ne signifie pas qu’elle a été annulée.</p><div id="aff-sales-table" aria-live="polite">Chargement…</div></section>`;
     $('aff-status').value=status;$('aff-search-form').onsubmit=e=>{e.preventDefault();search=$('aff-search').value;status=$('aff-status').value;page=1;loadSales()};loadSales();
   }else if(tab==='payments'){
     content.innerHTML=`<div class="aff-kpis">${kpi('Total des paiements',euro(summary?.payments_total),'Cumul indiqué par Domadoo','green')}${kpi('Paiements en attente',euro(summary?.payments_pending),'Libellé du portail','purple')}${kpi('Solde',euro(summary?.balance),'Au dernier relevé')}</div><section class="panel"><h2>Mes bons de paiement</h2><p>Ce tableau décrit les bons visibles dans le portail. Il ne constitue pas un historique des virements bancaires. Les codes utilisables ne sont jamais collectés.</p><div id="aff-payments">Chargement…</div></section>`;loadPayments();
   }else if(tab==='settings'){
     content.innerHTML=`<div class="aff-grid"><section class="panel"><h2>Connexion et session</h2>${badge(current)}<p>Connectez-vous personnellement à Domadoo dans la fenêtre sécurisée. Elle se ferme dès que l’espace affilié est reconnu.</p><div class="aff-actions"><button class="primary" data-aff="login" ${!current.available?'disabled':''}>Ouvrir la connexion Domadoo</button><button data-aff="disconnect" ${!current.available?'disabled':''}>Déconnecter</button></div><dl class="aff-facts"><div><dt>Dernière tentative</dt><dd>${esc(at(current.last_attempt))}</dd></div><div><dt>Dernier relevé valide</dt><dd>${esc(at(current.last_success))}</dd></div><div><dt>Prochain passage</dt><dd>${current.enabled?esc(at(current.next_due)):'Désactivé'}</dd></div></dl><p class="field-help">Une session enregistrée peut expirer. Le résultat de la collecte confirme l’accès aux données.</p></section>
      <section class="panel"><h2>Synchronisation quotidienne</h2><form id="aff-settings-form"><label class="aff-checkbox"><input type="checkbox" id="aff-enabled" ${current.enabled?'checked':''} ${!current.available?'disabled':''}>Activer la collecte quotidienne</label><p class="field-help">À activer après vérification des conditions d’utilisation du portail. CAPTCHA et double vérification demandent votre intervention.</p><div class="aff-filters"><label>Heure locale<select id="aff-hour">${Array.from({length:24},(_,h)=>`<option value="${h}" ${h===current.hour?'selected':''}>${String(h).padStart(2,'0')}:00</option>`).join('')}</select></label><label>Fuseau horaire<input id="aff-zone" value="${esc(current.zone)}" required maxlength="60"></label></div><button class="primary">Enregistrer</button></form><p>Lecture complète de l’historique, une seule collecte à la fois. Le dernier relevé valide est conservé en cas d’échec.</p></section></div><section class="panel"><h2>Historique des synchronisations</h2><div id="aff-runs">Chargement…</div></section>`;
     $('aff-settings-form').onsubmit=async e=>{e.preventDefault();try{await request('settings',{id:account,enabled:$('aff-enabled').checked,hour:Number($('aff-hour').value),zone:$('aff-zone').value});say('Synchronisation enregistrée.');await load()}catch(error){say(error.message,true)}};loadRuns();
   }
 }
 function partnerList(){return model.accounts.map(a=>`<article class="aff-partner"><div class="aff-avatar" aria-hidden="true">${esc(a.partner.slice(0,1))}</div><div><strong>${esc(a.partner)}</strong><small>${esc(a.label)} · ${esc(a.platform)}</small><small>Relevé : ${esc(at(a.last_success))}</small></div>${badge(a)}<button data-aff="open" data-id="${esc(a.id)}">Voir les détails</button></article>`).join('')}
 function partnerDistribution(){
   const groups=new Map();for(const a of model.accounts){const total=sum(model.aggregate.filter(r=>r.account_id===a.id),'approved');const existing=groups.get(a.partner_id)||{name:a.partner,cents:0,known:false};existing.cents+=total;existing.known ||=Boolean(a.snapshot);groups.set(a.partner_id,existing)}
   const values=[...groups.values()],positive=values.reduce((n,v)=>n+Math.max(0,v.cents),0);let offset=0;
   const ring=positive?`<svg class="aff-donut" viewBox="0 0 120 120" role="img" aria-label="Répartition des commissions approuvées positives">${values.map((v,i)=>{const portion=Math.max(0,v.cents)/positive*100,part=`<circle class="aff-slice aff-slice-${i%4}" cx="60" cy="60" r="45" pathLength="100" stroke-dasharray="${portion} ${100-portion}" stroke-dashoffset="${-offset}"/>`;offset+=portion;return part}).join('')}</svg>`:'';
   return `<div class="aff-distribution">${ring}<dl class="aff-facts">${values.map(v=>`<div><dt>${esc(v.name)}</dt><dd>${v.known?euro(v.cents):'—'}</dd></div>`).join('')}</dl></div><small>Commissions approuvées de la période. Le cercle représente les montants positifs ; les corrections négatives restent dans les totaux.</small>`;
 }
 function salesQuery(){return new URLSearchParams({account,start,end,page:String(page),search,status})}
 async function loadSales(){const v=renderVersion,id=account;try{const result=await request('transactions?'+salesQuery());if(! $('aff-sales-table')||account!==id||v!==renderVersion)return;page=result.page;
   $('aff-sales-table').innerHTML=`<div class="aff-table-wrap"><table><thead><tr><th>ID</th><th>Date du portail</th><th>Commande</th><th>Commission</th><th>Statut</th><th>Historique</th></tr></thead><tbody>${result.items.map(r=>`<tr><td>#${esc(r.provider_id)}</td><td>${esc(r.occurred_at)}</td><td>${euro(r.order_cents)}</td><td>${euro(r.commission_cents)}</td><td><span class="aff-badge ${r.present&&r.status==='approved'?'aff-good':''}">${!r.present?'Absente du relevé':r.status==='approved'?'Approuvée':'Non approuvée'}</span></td><td><button data-aff="history" data-id="${esc(r.provider_id)}">Voir</button></td></tr>`).join('')||'<tr><td colspan="6">Aucune vente pour cette sélection.</td></tr>'}</tbody></table></div><div class="aff-pagination"><span>${number(result.total)} ventes · page ${result.page} / ${result.pages}</span><button data-aff="previous" ${page===1?'disabled':''}>Précédente</button><button data-aff="next" ${page===result.pages?'disabled':''}>Suivante</button></div>`;
   }catch(e){say(e.message,true)}
 }
 async function loadPayments(){const id=account;try{const result=await request('payments?account='+encodeURIComponent(id));if(!$('aff-payments')||id!==account)return;$('aff-payments').innerHTML=`<div class="aff-table-wrap"><table><thead><tr><th>Créé à</th><th>Montant</th><th>Approuvé</th><th>Utilisé</th></tr></thead><tbody>${result.items.map(r=>`<tr><td>${esc(r.issued_on)}</td><td>${euro(r.amount_cents)}</td><td>${r.approved?'Oui':'Non'}</td><td>${r.used?'Oui':'Non'}</td></tr>`).join('')||'<tr><td colspan="4">Aucun bon dans le dernier relevé disponible.</td></tr>'}</tbody></table></div>`}catch(e){say(e.message,true)}}
 async function loadRuns(){const id=account;try{const result=await request('runs?account='+encodeURIComponent(id));if(!$('aff-runs')||id!==account)return;$('aff-runs').innerHTML=result.items.length?`<ul class="aff-run-list">${result.items.map(r=>`<li><strong>${esc(at(r.started_at))}</strong><span>${({running:'En cours',success:'Complet',failed:'Échec'}[r.status])}</span><small>${r.status==='success'?number(r.rows)+' ventes · '+number(r.pages)+' pages':esc(r.message||'Lecture du portail…')}</small></li>`).join('')}</ul>`:'<p>Aucune synchronisation effectuée.</p>'}catch(e){say(e.message,true)}}
 function dialog(title,body){const d=$('aff-dialog');d.innerHTML=`<div class="panel-title"><h2 id="aff-dialog-title">${esc(title)}</h2><button data-aff="close" aria-label="Fermer">Fermer</button></div>${body}`;d.showModal();return d}
 async function closeDialog(){clearTimeout(loginTimer);const d=$('aff-dialog');if(loginAccount){const id=loginAccount;loginAccount='';await request('login/close',{account:id}).catch(()=>{})}d?.close()}
 async function showLogin(result){
   if(result.connected){loginAccount='';clearTimeout(loginTimer);$('aff-dialog').close();say('Session Domadoo enregistrée. Lancez une synchronisation pour vérifier les données.');await load();return}
   if(!result.active){await closeDialog();say('Fenêtre de connexion fermée ou expirée.');return}
   if(!$('aff-login-image'))return;
   $('aff-login-image').src='data:image/jpeg;base64,'+result.image;$('aff-login-location').textContent=result.location;
   $('aff-login-challenge').hidden=!result.challenge;
   $('aff-login-verify').disabled=Boolean(result.challenge);
   clearTimeout(loginTimer);loginTimer=setTimeout(async()=>{if(!loginAccount)return;try{await showLogin(await request('login/state',{account:loginAccount}))}catch(e){say(e.message,true);await closeDialog()}},2500);
 }
 async function loginInput(data){clearTimeout(loginTimer);try{await showLogin(await request('login/input',{account:loginAccount,...data}))}catch(e){say(e.message,true)}}
 host.addEventListener('cancel',e=>{if(e.target.id==='aff-dialog'){e.preventDefault();closeDialog()}},true);
 host.addEventListener('change',e=>{if(e.target.id!=='aff-period')return;const v=e.target.value;if(v==='month')month();else if(v==='all'){start='';end=''}else if(v==='30'){const now=new Date();end=new Intl.DateTimeFormat('sv-SE',{timeZone:adminTimezone}).format(now);now.setUTCDate(now.getUTCDate()-29);start=new Intl.DateTimeFormat('sv-SE',{timeZone:adminTimezone}).format(now)}else return;page=1;load()});
 host.addEventListener('click',async e=>{
   const button=e.target.closest('button');if(!button)return;
   if(button.dataset.affTab){tab=button.dataset.affTab;render();return}
   const action=button.dataset.aff;if(!action)return;
   try{
     if(action==='reload')await load();
     if(action==='global'){account='';tab='overview';await load()}
     if(action==='partners'){account='';tab='partners';await load()}
     if(action==='open'){account=button.dataset.id;tab=selected()?.snapshot?'overview':'settings';page=1;await load()}
     if(action==='settings'){tab='settings';render()}
     if(action==='range'){start=$('aff-start').value;end=$('aff-end').value;page=1;await load()}
     if(action==='previous'||action==='next'){page+=action==='next'?1:-1;await loadSales()}
     if(action==='sync'){
       const ids=account?[account]:model.accounts.filter(a=>a.available&&a.session_state==='connected').map(a=>a.id);
       if(!ids.length)throw new Error('Connectez d’abord un compte dans ses paramètres.');
       await request('sync',{account:ids[0],accounts:ids});say('Synchronisation lancée.');await load();
     }
     if(action==='disconnect'){await request('disconnect',{account});say('Session supprimée et collecte quotidienne désactivée.');await load()}
     if(action==='close')await closeDialog();
     if(action==='history'){
       const history=await request('history?'+new URLSearchParams({account,id:button.dataset.id}));
       dialog('Historique de la vente #'+button.dataset.id,`<p>Dates d’observation dans LinKs ; aucune date de validation fournisseur n’est supposée.</p><ul class="aff-run-list">${history.items.map(r=>{const before=r.before_json?JSON.parse(r.before_json):null,after=JSON.parse(r.after_json);return `<li><strong>${esc(at(r.observed_at))}</strong><span>${before?euro(before.commission_cents)+' → ':''}${euro(after.commission_cents)}</span><small>${!after.present?'Absente du relevé':after.status==='approved'?'Approuvée':'Non approuvée'}${before?' · correction observée':' · première observation'}</small></li>`}).join('')}</ul>`);
     }
     if(action==='export'){
       button.disabled=true;const saved=page,rows=[],ids=new Set();try{let n=1,totalPages=1,version;do{const q=salesQuery();q.set('page',n);const result=await request('transactions?'+q);if(n===1)version=result.snapshot_id;if(result.snapshot_id!==version)throw new Error('Le relevé a changé pendant l’export. Relancez l’export.');for(const row of result.items){if(ids.has(row.provider_id))throw new Error('Export incohérent : relancez après la synchronisation.');ids.add(row.provider_id)}totalPages=result.pages;rows.push(...result.items);n++}while(n<=totalPages)}finally{page=saved;button.disabled=false}
       const csv=[['ID','Date du portail','Commande EUR','Commission EUR','Statut','Présente au dernier relevé'],...rows.map(r=>[r.provider_id,r.occurred_at,(r.order_cents/100).toFixed(2),(r.commission_cents/100).toFixed(2),r.status,r.present?'Oui':'Non'])].map(r=>r.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(';')).join('\r\n');
       const url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='links-affiliation.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
     }
     if(action==='add'){
       dialog('Ajouter un partenaire',`<form id="aff-add-form"><label>Partenaire commercial<input name="partner" required maxlength="80" placeholder="Ex. Reolink"></label><label>Nom du compte<input name="label" required maxlength="80" placeholder="Mon compte affilié"></label><label>Plateforme<select name="platform">${model.platforms.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}${p.available?'':' · connecteur à venir'}</option>`).join('')}</select></label><p>Domadoo utilise exclusivement son portail officiel. Aucun changement n’est apporté aux liens affiliés existants.</p><button class="primary">Ajouter</button></form>`);
       $('aff-add-form').onsubmit=async event=>{event.preventDefault();try{await request('accounts',Object.fromEntries(new FormData(event.target)));await closeDialog();await load()}catch(error){say(error.message,true)}};
     }
     if(action==='login'){
       button.disabled=true;const result=await request('login/start',{account});loginAccount=account;
       const d=dialog('Connexion personnelle Domadoo',`<p>Les saisies sont transmises au navigateur du serveur, sans enregistrement du mot de passe. Cliquez dans le champ de la page puis utilisez la saisie ci-dessous. Réalisez vous-même toute double vérification ou protection.</p><p id="aff-login-challenge" role="status" hidden><strong>Vérification de sécurité Domadoo en cours.</strong> Suivez uniquement les instructions affichées par le portail. Si cette page reste bloquée, fermez la fenêtre et contactez Domadoo : le navigateur du serveur peut être refusé. Une connexion réussie sur votre ordinateur ne connecte pas LinKs. Aucun relevé ne sera récupéré avant validation de cet accès.</p><p id="aff-login-location"></p><img id="aff-login-image" class="aff-login-image" alt="Fenêtre de connexion Domadoo interactive" tabindex="0"><form id="aff-type-form" class="aff-filters"><label>Saisie dans le champ sélectionné<input id="aff-login-text" type="password" autocomplete="off" maxlength="500"></label><button>Transmettre la saisie</button></form><div class="aff-actions"><button data-login-key="Tab">Champ suivant</button><button data-login-key="ControlOrMeta+A">Tout sélectionner</button><button data-login-key="Backspace">Effacer</button><button data-login-key="Enter">Entrée</button><button data-login-scroll="-500">Monter</button><button data-login-scroll="500">Descendre</button><button id="aff-login-verify">Vérifier mon accès affilié</button></div>`);
       $('aff-login-image').onclick=event=>{const rect=event.target.getBoundingClientRect();loginInput({kind:'click',x:(event.clientX-rect.left)/rect.width*1100,y:(event.clientY-rect.top)/rect.height*760})};
       $('aff-type-form').onsubmit=event=>{event.preventDefault();const input=$('aff-login-text'),text=input.value;input.value='';loginInput({kind:'text',text})};
       d.querySelectorAll('[data-login-key]').forEach(b=>b.onclick=()=>loginInput({kind:'key',key:b.dataset.loginKey}));d.querySelectorAll('[data-login-scroll]').forEach(b=>b.onclick=()=>loginInput({kind:'scroll',delta:Number(b.dataset.loginScroll)}));
       $('aff-login-verify').onclick=async()=>{clearTimeout(loginTimer);try{await showLogin(await request('login/verify',{account:loginAccount}))}catch(error){say(error.message,true)}};
       await showLogin(result);button.disabled=false;
     }
   }catch(error){say(error.message,true);button.disabled=false}
 });
 window.LinksAffiliation={load};
})();
