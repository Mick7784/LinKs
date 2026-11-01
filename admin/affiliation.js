"use strict";
(()=>{
 const host=$('affiliation');let model=null,account='',tab='overview',page=1,search='',status='',timer=null,loginTimer=null,mfaTimer=null,loginAccount='',renderVersion=0,initialRange=true;
 // Editing the controls never changes the range used by requests.
 let selectedRange={period:'30',start:'',end:''},appliedRange=null;
 const euro=v=>v===null||v===undefined?'—':new Intl.NumberFormat('fr-FR',{style:'currency',currency:'EUR'}).format(v/100);
 const number=v=>v===null||v===undefined?'—':fmt.format(v);
 const at=v=>v?new Intl.DateTimeFormat('fr-FR',{dateStyle:'short',timeStyle:'short',timeZone:adminTimezone}).format(new Date(v)):'Jamais';
 const request=(action,data)=>api('/api/affiliation/'+action,data?{method:'POST',body:JSON.stringify(data)}:{});
 let loginQueue=Promise.resolve(),loginGeneration=0,loadVersion=0,runsVersion=0,salesVersion=0,paymentsVersion=0,syncStarting=false,pollError=false;
 const queueLogin=(action,data)=>{loginQueue=loginQueue.catch(()=>{}).then(()=>request(action,data));return loginQueue};
 const selected=()=>model?.accounts.find(a=>a.id===account);
 const sum=(rows,kind)=>rows.filter(r=>!kind||r.status===kind).reduce((n,r)=>n+r.cents,0);
 const badgeText=a=>a.mode==='csv'?'Import CSV disponible':!a.available?'Connecteur à venir':a.running?'Synchronisation…':({connected:'Session enregistrée',reconnect:'À reconnecter',disconnected:'À connecter'}[a.session_state]||'À connecter');
 const badge=a=>`<span data-aff-account="${esc(a.id)}" class="aff-badge ${a.available&&a.session_state==='connected'?'aff-good':''}">${badgeText(a)}</span>`;
 const kpi=(label,value,help,tone='cyan')=>`<article class="aff-card aff-${tone}"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(help)}</small></article>`;
 function range(){return new URLSearchParams({account,start:appliedRange.start,end:appliedRange.end})}
 function selectPeriod(period){
   const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
   if(period==='all')selectedRange={period,start:'',end:''};
   else if(period==='month')selectedRange={period,start:today.slice(0,7)+'-01',end:today};
   else if(period==='30'){
     // Subtract calendar days from the Paris date, independently of DST and the device zone.
     const first=new Date(today+'T00:00:00Z');first.setUTCDate(first.getUTCDate()-29);
     selectedRange={period,start:first.toISOString().slice(0,10),end:today};
   }else selectedRange={...selectedRange,period:'custom'};
 }
 function chart(rows){
   if(!rows.length)return '<p class="aff-empty">Aucune vente observée pour cette période.</p>';
   const monthly=new Set(rows.map(r=>r.day)).size>60,groups=new Map();
   for(const row of rows){const key=monthly?row.day.slice(0,7):row.day;const values=groups.get(key)||{approved:0,not_approved:0};values[row.status]+=row.cents;groups.set(key,values)}
   const items=[...groups],values=items.flatMap(([,v])=>[v.approved,v.not_approved]),max=Math.max(1,...values),min=Math.min(0,...values),y=v=>160-(v-min)/(max-min)*140,zero=y(0),width=600/Math.max(1,items.length);
   return `<svg viewBox="0 0 700 205" role="img" aria-label="Commissions ${monthly?'mensuelles':'quotidiennes'}, par date de vente"><line x1="65" x2="680" y1="${zero}" y2="${zero}" stroke="currentColor" opacity=".3"/><text x="0" y="20">${esc(euro(max))}</text><text x="0" y="160">${esc(euro(min))}</text>${items.map(([day,v],i)=>['approved','not_approved'].map((key,j)=>`<rect class="aff-bar-${key}" x="${70+i*width+j*width*.4}" y="${Math.min(zero,y(v[key]))}" width="${Math.max(1,width*.36)}" height="${Math.max(0,Math.abs(y(v[key])-zero))}"><title>${esc(day)} · ${key==='approved'?'Approuvées':'Non approuvées'} : ${esc(euro(v[key]))}</title></rect>`).join('')+(i===0||i===items.length-1||i%Math.max(1,Math.ceil(items.length/6))===0?`<text x="${70+i*width}" y="188" text-anchor="start">${esc(day.slice(monthly?0:5))}</text>`:'')).join('')}</svg><p class="aff-legend"><span>● Approuvées</span><span>● Non approuvées</span></p>`;
 }
 async function load({poll=false}={}){
   const version=++loadVersion;clearTimeout(timer);
   if(initialRange){selectPeriod('30');appliedRange={...selectedRange};initialRange=false;}
   try{
     const next=await request('overview?'+range());if(version!==loadVersion)return;
     const snapshots=m=>JSON.stringify(m?.accounts.map(a=>[a.id,a.snapshot?.id]));
     const changed=snapshots(model)!==snapshots(next);model=next;pollError=false;
     if(!poll)render();
     else{
       refreshSyncState();
       if(tab==='settings')loadRuns();
       else if(changed&&tab==='sales')loadSales();
       else if(changed)renderContent();
     }
   }catch(e){
     if(version!==loadVersion)return;
     if(!poll||!pollError)say(e.message,true);pollError=true;
     if(!model)host.innerHTML='<h1>Affiliation</h1><p role="alert">Chargement indisponible.</p><button data-aff="reload">Réessayer</button>';
   }finally{
     if(version===loadVersion&&model?.accounts.some(a=>a.running))timer=setTimeout(()=>{if(host.classList.contains('active'))load({poll:true})},3000);
   }
 }
 function syncNotice(){
   const current=selected(),snap=current?.snapshot;
   if(current?.platform_id==='amazon')return `<p class="aff-freshness">Dernier import : ${esc(at(current.last_success))} · rapports Amazon France, couverture limitée aux fichiers importés. Aucune surveillance des pertes par transaction.</p>`;
   return current?`<p class="aff-freshness">Dernier relevé complet : <strong>${esc(at(current.last_success))}</strong>${snap?' · '+number(snap.row_count)+' ventes · '+number(snap.pages)+' pages · '+(snap.source==='portal'?'Portail Domadoo':'Import manuel'):''}</p>${current.last_error?`<p class="aff-alert" role="status">${esc(current.last_error)} Le dernier relevé valide reste affiché.</p>`:''}`:`<p class="aff-freshness">${model.coverage.ready} / ${model.coverage.total} comptes disposent d’un relevé. Les totaux portent uniquement sur ces comptes.</p>`;
 }
 function refreshSyncState(){
   if(!model)return;
   const current=selected(),running=syncStarting||model.accounts.some(a=>a.running);
   host.querySelectorAll('[data-aff-account]').forEach(node=>{const a=model.accounts.find(a=>a.id===node.dataset.affAccount);if(a){const label=badgeText(a);if(node.textContent!==label)node.textContent=label;node.classList.toggle('aff-good',Boolean(a.available&&a.session_state==='connected'))}});
   host.querySelectorAll('[data-aff="sync"]').forEach(button=>{button.disabled=running||Boolean(current&&!current.available)});
   const notice=$('aff-sync-notice'),html=syncNotice();if(notice&&notice.innerHTML!==html)notice.innerHTML=html;
   if(current)host.querySelectorAll('[data-aff-fact]').forEach(node=>{const key=node.dataset.affFact,label=key==='next_due'&&!current.enabled?'Désactivé':at(current[key]);if(node.textContent!==label)node.textContent=label});
 }
 function render(){
   clearInterval(mfaTimer);mfaTimer=null;
   renderVersion++;
   const current=selected(),label=current?current.partner:'Affiliation';
   const tabs=[['overview','Vue d’ensemble'],...(current?[['sales',current.platform_id==='amazon'?'Rapports Amazon':'Ventes et commissions'],['payments','Paiements'],...(current.platform_id==='amazon'?[['connection','Connexion']]:[]),['settings',current.platform_id==='amazon'?'Import et accès API':'Connexion et synchronisation']]:[['partners','Mes partenaires']])];
   if(!tabs.some(t=>t[0]===tab))tab='overview';
   host.innerHTML=`<div class="section-head"><div><p class="aff-eyebrow">ANALYSER · AFFILIATION</p><h1>${esc(label)} ${current?badge(current):''}</h1><p>${current?esc(current.label)+' · '+esc(current.platform):'Vos revenus et l’état de vos partenaires.'}</p></div><div class="aff-actions">${current?'<button data-aff="global">Tous les partenaires</button>':'<button data-aff="partners">Gérer les partenaires</button>'}${current?.platform_id==='amazon'?'<button class="primary" data-aff="amazon-import">Importer un rapport CSV</button>':`<button class="primary" data-aff="sync" ${current&&!current.available?'disabled':''}>${current?'Synchroniser':'Synchroniser les comptes connectés'}</button>`}</div></div>
    <nav class="aff-tabs" aria-label="Rubriques affiliation">${tabs.map(([id,title])=>`<button data-aff-tab="${id}" ${tab===id?'aria-current="page" class="active"':''}>${title}</button>`).join('')}</nav>
    <div class="aff-filters" ${!['overview','sales',...(current?.platform_id==='amazon'?['payments']:[])].includes(tab)?'hidden':''}><label>Période<select id="aff-period"><option value="custom">Dates sélectionnées</option><option value="month">Ce mois</option><option value="30">30 derniers jours</option><option value="all">Tout l’historique observé</option></select></label><label>Du<input id="aff-start" type="date" value="${esc(selectedRange.start)}"></label><label>Au<input id="aff-end" type="date" value="${esc(selectedRange.end)}"></label><button data-aff="range">Appliquer</button><small>${current?.platform_id==='amazon'?'Dates fournies par le rapport Amazon':'Ventes : date du portail · pertes : première disparition (Europe/Paris)'}</small></div>
    <div id="aff-sync-notice">${syncNotice()}</div>
    <div id="aff-content"></div><dialog id="aff-dialog" aria-labelledby="aff-dialog-title"></dialog>`;
   $('aff-period').value=selectedRange.period;
   renderContent();refreshSyncState();
 }
 function renderContent(){
   const current=selected(),rows=model.aggregate,has=model.has_data,summary=current?.snapshot?.summary;
   if(current?.platform_id==='amazon'){renderAmazon(current);return}
   const amazonReports=model.amazon||[],amazonCents=amazonReports.reduce((n,r)=>n+(r.totals.commission_cents||0),0);
   const candidates=(current?[current]:model.accounts).filter(a=>a.platform_id!=='amazon');
   const domadooData=candidates.some(a=>a.snapshot),financialData=domadooData||amazonReports.some(r=>r.totals.commission_cents!==null);
   const payments=candidates.filter(a=>a.snapshot).reduce((n,a)=>n+a.snapshot.summary.payments_total,0);
   const content=$('aff-content'),losses=model.losses||[],lostCount=losses.reduce((n,r)=>n+r.sales,0),lostCents=losses.reduce((n,r)=>n+r.cents,0);
   if(tab==='overview'){
     content.innerHTML=`${!has?'<div class="aff-empty"><h2>Vos revenus apparaîtront après la première synchronisation.</h2><p>Connectez Domadoo dans « Connexion et synchronisation ». Les autres plateformes pourront être préparées dans Mes partenaires.</p><button data-aff="open" data-id="domadoo">Configurer Domadoo</button></div>':''}
      <div class="aff-kpis">${kpi('Commissions observées',financialData?euro(sum(rows)+amazonCents):'—','Domadoo + commissions Amazon importées · période')}${kpi('Commissions approuvées',domadooData?euro(sum(rows,'approved')):'—','Statut actuel · date de vente','blue')}${kpi('Non approuvées',domadooData?euro(sum(rows,'not_approved')):'—','Attente / refus non distingués par Domadoo','purple')}${kpi('Paiements Domadoo',domadooData?euro(payments):'—','Cumul du portail · indépendant de la période','green')}${!current&&amazonReports.length?kpi('Commissions Amazon',amazonReports.some(r=>r.totals.commission_cents!==null)?euro(amazonCents):'—','Rapports importés · statut fournisseur non présumé','blue'):''}${kpi('Ventes perdues',domadooData?number(lostCount):'—','IDs actuellement absents · première disparition dans la période','lost')}${kpi('Commissions perdues',domadooData?euro(lostCents):'—','Derniers montants connus · disparition, pas refus officiel','lost')}</div>
      <section class="panel aff-chart"><div class="panel-title"><h2>Évolution des commissions</h2><small>Domadoo · montants actuellement observés, corrections incluses</small></div>${chart(model.daily)}</section>
      <div class="aff-grid">${current?`<section class="panel"><h2>Résumé du portail · Last 30 days</h2><dl class="aff-facts">${[['Gains',summary?euro(summary.earnings_30d):'—'],['Ventes approuvées',number(summary?.approved_sales_30d)],['Ventes en attente',number(summary?.pending_sales_30d)],['Clics',number(summary?.clicks_30d)],['Clics uniques',number(summary?.unique_clicks_30d)]].map(([k,v])=>`<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl><small>Fenêtre native de 30 jours au dernier relevé, indépendante du filtre. Les clics ne sont pas des statistiques LinKs.</small></section><section class="panel"><h2>Solde et gains cumulés</h2><dl class="aff-facts">${[['Total des gains',euro(summary?.earnings_total)],['Paiements en attente',euro(summary?.payments_pending)],['Solde',euro(summary?.balance)]].map(([k,v])=>`<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl><p>Les commissions refusées et la date de validation ne sont pas fournies séparément.</p><button data-aff="settings">Connexion et synchronisation</button></section>`:`<section class="panel"><h2>Répartition par partenaire</h2>${partnerDistribution()}</section><section class="panel"><h2>Mes partenaires</h2>${partnerList()}</section>`}</div>`;
   }else if(tab==='partners'){
     content.innerHTML=`<section class="panel"><div class="panel-title"><h2>Mes partenaires d’affiliation</h2><button class="primary" data-aff="add">Ajouter un partenaire</button></div><p>Un partenaire commercial peut avoir plusieurs comptes. Chaque compte utilise une plateforme de reporting.</p>${partnerList()}<p class="field-help">Amazon : import CSV disponible, accès API à vérifier pour votre compte. Affiliatly (Reolink), GoAffPro (Sanyipace), Awin et Impact : connecteurs à venir.</p></section>`;
   }else if(tab==='sales'){
     content.innerHTML=`<section class="panel"><div class="panel-title"><h2>Ventes et commissions</h2><button data-aff="export">Exporter cette sélection</button></div><form id="aff-search-form" class="aff-filters"><label>Rechercher un ID<input id="aff-search" value="${esc(search)}" maxlength="80" placeholder="Numéro de vente"></label><label>Statut<select id="aff-status"><option value="">Tous les statuts</option><option value="approved">Approuvée</option><option value="not_approved">Non approuvée</option><option value="lost">Perdu</option></select></label><button>Rechercher</button></form><p>Perdu : vente disparue d’un relevé complet, sans refus officiel de commission. Les pertes sont filtrées par première disparition (Europe/Paris) et conservent le dernier montant connu.</p><div id="aff-sales-table" aria-live="polite">Chargement…</div></section>`;
     $('aff-status').value=status;$('aff-search-form').onsubmit=e=>{e.preventDefault();search=$('aff-search').value;status=$('aff-status').value;page=1;loadSales()};loadSales();
   }else if(tab==='payments'){
     content.innerHTML=`<div class="aff-kpis">${kpi('Total des paiements',euro(summary?.payments_total),'Cumul indiqué par Domadoo','green')}${kpi('Paiements en attente',euro(summary?.payments_pending),'Libellé du portail','purple')}${kpi('Solde',euro(summary?.balance),'Au dernier relevé')}</div><section class="panel"><h2>Mes bons de paiement</h2><p>Ce tableau décrit les bons visibles dans le portail. Il ne constitue pas un historique des virements bancaires. Les codes utilisables ne sont jamais collectés.</p><div id="aff-payments">Chargement…</div></section>`;loadPayments();
   }else if(tab==='settings'){
     content.innerHTML=`<div class="aff-grid"><section class="panel"><h2>Connexion et session</h2>${badge(current)}<p>Si la connexion automatique est configurée sur votre serveur, cliquez sur Synchroniser. La fenêtre sécurisée reste disponible pour une connexion personnelle ou une vérification supplémentaire.</p><div class="aff-actions"><button class="primary" data-aff="login" ${!current.available?'disabled':''}>Ouvrir la connexion Domadoo</button><button data-aff="disconnect" ${!current.available?'disabled':''}>Déconnecter</button></div><dl class="aff-facts"><div><dt>Dernière tentative</dt><dd data-aff-fact="last_attempt">${esc(at(current.last_attempt))}</dd></div><div><dt>Dernier relevé valide</dt><dd data-aff-fact="last_success">${esc(at(current.last_success))}</dd></div><div><dt>Prochain passage</dt><dd data-aff-fact="next_due">${current.enabled?esc(at(current.next_due)):'Désactivé'}</dd></div></dl><p class="field-help">Une session enregistrée peut expirer. Le résultat de la collecte confirme l’accès aux données.</p></section>
      <section class="panel"><h2>Synchronisation quotidienne</h2><form id="aff-settings-form"><label class="aff-checkbox"><input type="checkbox" id="aff-enabled" ${current.enabled?'checked':''} ${!current.available?'disabled':''}>Activer la collecte quotidienne</label><p class="field-help">À activer après vérification des conditions d’utilisation du portail. CAPTCHA et double vérification demandent votre intervention.</p><div class="aff-filters"><label>Heure locale<select id="aff-hour">${Array.from({length:24},(_,h)=>`<option value="${h}" ${h===current.hour?'selected':''}>${String(h).padStart(2,'0')}:00</option>`).join('')}</select></label><label>Fuseau horaire<input id="aff-zone" value="${esc(current.zone)}" required maxlength="60"></label></div><button class="primary">Enregistrer</button></form><p>Lecture complète de l’historique, une seule collecte à la fois. Le dernier relevé valide est conservé en cas d’échec.</p></section></div><section class="panel"><h2>Historique des synchronisations</h2><div id="aff-runs">Chargement…</div></section>`;
     $('aff-settings-form').onsubmit=async e=>{e.preventDefault();try{await request('settings',{id:account,enabled:$('aff-enabled').checked,hour:Number($('aff-hour').value),zone:$('aff-zone').value});say('Synchronisation enregistrée.');await load()}catch(error){say(error.message,true)}};loadRuns();
   }
 }
 function setupAmazonMfa(id){
   const version=renderVersion,form=$('aff-mfa-form'),state=$('aff-mfa-state'),box=$('aff-mfa-code-box'),manage=$('aff-mfa-manage');
   const live=()=>version===renderVersion&&account===id&&tab==='connection'&&state.isConnected;
   const call=(action,data={})=>request('amazon/mfa/'+action,{account:id,...data});
   let expires=0,refreshing=false,pendingVersion=null;
   const setCode=result=>{
     if(!live())return;
     if(pendingVersion!==result.version){$('aff-mfa-confirm-check').checked=false;$('aff-mfa-confirm').disabled=true}
     pendingVersion=result.version;
     $('aff-mfa-code').textContent=result.code;
     expires=Date.now()+result.remainingMs;
     box.hidden=false;form.hidden=true;manage.hidden=true;
     clearInterval(mfaTimer);
     mfaTimer=setInterval(async()=>{
       if(!live()){clearInterval(mfaTimer);return}
       const left=Math.max(0,Math.ceil((expires-Date.now())/1000));
       $('aff-mfa-countdown').textContent='Nouveau code dans '+left+' s';
       if(left===0&&!refreshing){
         refreshing=true;
         try{setCode(await call('code',{version:pendingVersion}))}catch(error){if(live()){box.hidden=true;state.textContent=error.message}}
         finally{refreshing=false}
       }
     },250);
   };
   const loadState=async()=>{
     const result=await call('status');if(!live())return;
     if(result.environment){box.hidden=true;form.hidden=true;manage.hidden=true;state.textContent=result.conflict?'Conflit MFA : les clés environnement et LinKs diffèrent. Utilisation bloquée. Retirez AMAZON_MFA_SECRET du serveur pour utiliser la clé LinKs.':'MFA géré par AMAZON_MFA_SECRET dans l’environnement. Retirez cette variable pour gérer le MFA dans LinKs.';return}
     if(result.pending){state.textContent='Clé en attente de validation sur Amazon.';setCode(await call('code'));return}
     state.textContent=result.active?(result.environment?'Clé MFA configurée sur le serveur. Retirez AMAZON_MFA_SECRET du serveur pour la supprimer ici.':'Clé MFA activée et conservée chiffrée sur le serveur.'):'Aucune clé MFA enregistrée.';
     box.hidden=true;form.hidden=result.active;manage.hidden=!result.active;
     $('aff-mfa-remove').hidden=result.environment;
   };
   form.onsubmit=async event=>{
     event.preventDefault();const input=$('aff-mfa-secret'),secret=input.value;input.value='';
     const button=form.querySelector('button');button.disabled=true;
     try{setCode(await call('preview',{secret}));if(live())state.textContent='Saisissez ce code sur Amazon, puis confirmez ici.'}
     catch(error){if(live())state.textContent=error.message}
     finally{button.disabled=false}
   };
   $('aff-mfa-copy').onclick=async()=>{try{await navigator.clipboard.writeText($('aff-mfa-code').textContent);say('Code copié.')}catch{say('Copie impossible ; saisissez le code affiché.',true)}};
   $('aff-mfa-confirm-check').onchange=event=>{$('aff-mfa-confirm').disabled=!event.target.checked};
   $('aff-mfa-confirm').onclick=async()=>{try{await call('confirm',{confirmed:true,version:pendingVersion});if(live()){clearInterval(mfaTimer);$('aff-mfa-code').textContent='';await loadState();say('Activation MFA confirmée dans LinKs.')}}catch(error){if(live())state.textContent=error.message}};
   $('aff-mfa-cancel').onclick=async()=>{try{await call('cancel',{version:pendingVersion});if(live()){clearInterval(mfaTimer);$('aff-mfa-code').textContent='';await loadState()}}catch(error){if(live())state.textContent=error.message}};
   $('aff-mfa-replace').onclick=()=>{form.hidden=false;manage.hidden=true;state.textContent='La clé actuelle reste active jusqu’à la confirmation de sa remplaçante.'};
   $('aff-mfa-remove').onclick=async()=>{if(!confirm('Supprimer la clé MFA enregistrée dans LinKs ?'))return;try{await call('remove');if(live()){clearInterval(mfaTimer);$('aff-mfa-code').textContent='';await loadState();say('Clé MFA supprimée de LinKs.')}}catch(error){if(live())state.textContent=error.message}};
   loadState().catch(error=>{if(live())state.textContent=error.message});
 }
 function renderAmazon(current){
   const data=(model.amazon||[]).find(r=>r.account_id===current.id),totals=data?.totals||{},content=$('aff-content');
   const labels={orders:'Commandes distinctes',ordered_items:'Articles commandés',shipped_items:'Articles expédiés',commission_cents:'Commissions déclarées',payment_cents:'Paiements déclarés'};
   const kinds={orders:'Commandes',earnings:'Rémunérations',payments:'Paiements'};
   content.innerHTML=`<p class="aff-alert">${esc(data?.limitation||'Aucune perte par transaction calculée.')} Les Tracking IDs Amazon sont conservés séparément des sources de partage LinKs. Un montant absent reste inconnu.</p>`;
   if(tab==='connection'){
     content.innerHTML+='<section class="panel aff-mfa"><h2>Connexion Amazon Partenaires</h2><p>Configurez AMAZON_LOGIN et AMAZON_PASSWORD sur le serveur. Pour activer la double vérification, saisissez ici la clé TOTP de 52 caractères fournie par Amazon. Saisissez le code affiché sur le site Amazon, puis confirmez ici que l’activation est terminée.</p><p class="field-help">LinKs ne valide pas la clé auprès d’Amazon. La récupération automatique des rapports du portail reste désactivée tant que son accès autorisé n’est pas établi.</p><p id="aff-mfa-state" role="status">Chargement de la configuration MFA…</p><form id="aff-mfa-form" hidden><label>Clé secrète TOTP Amazon<input id="aff-mfa-secret" type="password" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="80" required placeholder="52 caractères Base32"></label><button class="primary">Afficher le code</button></form><div id="aff-mfa-code-box" hidden><p>Code à saisir chez Amazon :</p><div class="aff-mfa-code-row"><strong id="aff-mfa-code" aria-live="polite"></strong><button id="aff-mfa-copy" type="button">Copier</button></div><p id="aff-mfa-countdown" role="status"></p><label class="aff-checkbox"><input id="aff-mfa-confirm-check" type="checkbox">J’ai activé cette clé sur le site Amazon</label><div class="aff-actions"><button id="aff-mfa-confirm" class="primary" disabled>Confirmer l’activation</button><button id="aff-mfa-cancel">Annuler cette clé</button></div></div><div id="aff-mfa-manage" class="aff-actions" hidden><button id="aff-mfa-replace">Remplacer la clé</button><button id="aff-mfa-remove">Supprimer la clé</button></div></section>';
     const portal=document.createElement('section');portal.className='panel';
     portal.innerHTML=`<h2>Synchronisation du portail</h2><p role="status"><strong>Accès Amazon non vérifié</strong></p><p>La collecte automatique n’est pas disponible : les modalités d’accès autorisées et la récupération d’un rapport réel restent à valider. Aucun contrôle Amazon n’a été contourné.</p><dl class="aff-facts"><div><dt>Dernière synchronisation du portail réussie</dt><dd>Aucune</dd></div><div><dt>Dernier import de rapport</dt><dd>${esc(at(current.last_success))}</dd></div></dl><button disabled title="Accès autorisé et collecte réelle à valider">Synchroniser</button><button data-aff="amazon-import">Importer un rapport CSV</button><h3>Horaire souhaité</h3><p>Enregistrez l’horaire pour une future collecte. La synchronisation quotidienne reste désactivée.</p><form class="aff-filters"><label>Heure locale<select name="hour">${Array.from({length:24},(_,h)=>`<option value="${h}" ${h===current.hour?'selected':''}>${String(h).padStart(2,'0')}:00</option>`).join('')}</select></label><label>Fuseau horaire<input name="zone" required maxlength="60" value="${esc(current.zone)}"></label><button>Enregistrer l’horaire</button></form><p class="field-help" role="status" data-portal-message></p>`;
     content.append(portal);
     portal.querySelector('form').onsubmit=async event=>{
       event.preventDefault();const form=event.currentTarget,button=form.querySelector('button'),message=portal.querySelector('[data-portal-message]');button.disabled=true;
       try{await request('settings',{id:current.id,enabled:false,hour:Number(form.elements.hour.value),zone:form.elements.zone.value});current.hour=Number(form.elements.hour.value);current.zone=form.elements.zone.value;message.textContent='Horaire enregistré. La collecte quotidienne reste désactivée.'}
       catch(error){message.textContent=error.message}finally{button.disabled=false}
     };
     setupAmazonMfa(current.id);return;
   }
   if(tab==='settings'){
     content.innerHTML+='<section class="panel"><h2>Amazon Partenaires France</h2><p>Importez un CSV UTF-8 exporté du portail Partenaires. Vérifiez les colonnes, la période et les Tracking IDs avant validation. Les réimports du même périmètre sont historisés ; les chevauchements sont refusés.</p><button data-aff="amazon-import">Importer un rapport CSV</button><h3>Creators API</h3><p>Les identifiants sont configurés exclusivement côté serveur. Ce diagnostic vérifie les rapports réellement accessibles ; il ne garantit pas l’accès aux commissions France. La collecte automatique reste désactivée tant que le format et la couverture de votre compte ne sont pas validés.</p><button id="aff-amazon-probe">Vérifier les rapports disponibles</button><div id="aff-amazon-files" role="status"></div></section>';
     const id=current.id;
     $('aff-amazon-probe').onclick=async event=>{
       const button=event.currentTarget,box=$('aff-amazon-files');button.disabled=true;box.textContent='Vérification…';
       try{const result=await request('amazon/list-reports',{account:id});if(!box.isConnected)return;box.replaceChildren();
         if(!result.reports.length)box.textContent='Aucun rapport disponible pour ces identifiants.';
         for(const report of result.reports){const line=document.createElement('p'),get=document.createElement('button');line.textContent=report.filename+' · '+(report.reportType||'Programme non précisé')+' ';get.textContent='Préparer l’import';get.onclick=async()=>{get.disabled=true;try{const result=await request('amazon/get-report',{account:id,filename:report.filename,reportType:report.reportType});if(account===id)amazonImport(id,result.csv)}catch(error){say(error.message,true)}finally{get.disabled=false}};line.append(get);box.append(line)}
       }catch(error){box.textContent=error.message}finally{button.disabled=false}
     };return;
   }
   content.innerHTML+=`<div class="aff-kpis">${Object.entries(labels).map(([key,label])=>kpi(label,key.endsWith('_cents')?euro(totals[key]):number(totals[key]),'Période appliquée · rapports importés',key==='payment_cents'?'green':'blue')).join('')}</div>`;
   const rows=(data?.rows||[]).filter(r=>tab!=='payments'||r.kind==='payments');
   content.innerHTML+=`<section class="panel"><h2>${tab==='payments'?'Paiements importés':'Lignes de rapports Amazon'}</h2><p>Les lignes peuvent être agrégées : elles ne représentent pas nécessairement des commandes ou transactions individuelles. Les commissions ne sont pas des paiements.</p><div class="aff-table-wrap"><table><thead><tr><th>Date</th><th>Rapport / Tracking ID</th><th>ASIN / produit</th>${Object.values(labels).map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.slice(0,500).map(r=>`<tr><td>${esc(r.date)}</td><td>${kinds[r.kind]}<br>${esc(r.tracking_id||'Non fourni')}</td><td>${esc(r.asin)}<br>${esc(r.title)}${r.provider_status?'<br>Statut fourni : '+esc(r.provider_status):''}${r.transaction_id?'<br>ID fourni : '+esc(r.transaction_id):''}</td>${Object.keys(labels).map(k=>`<td>${k.endsWith('_cents')?euro(r[k]):number(r[k])}</td>`).join('')}</tr>`).join('')||'<tr><td colspan="8">Aucune donnée importée pour cette période.</td></tr>'}</tbody></table></div>${rows.length>500?'<p>Affichage limité aux 500 premières lignes ; les totaux comprennent toutes les lignes filtrées.</p>':''}</section>`;
   content.innerHTML+=`<section class="panel"><h2>Couverture des rapports actifs</h2>${(data?.reports||[]).map(r=>`<p>${kinds[r.kind]} · ${esc(r.start)} → ${esc(r.end)} · ${esc(r.scope==='all'?'Tous les Tracking IDs':r.scope)} · import ${esc(at(r.observed_at))}</p>`).join('')||'<p>Aucun rapport.</p>'}</section>`;
 }
 function amazonImport(id,initial=''){
   const labels={date:'Date de la ligne',tracking_id:'Tracking ID Amazon',asin:'ASIN',title:'Produit',provider_status:'Statut fourni par Amazon',transaction_id:'Identifiant fourni (sans garantie de stabilité)',orders:'Nombre de commandes distinctes',ordered_items:'Articles commandés',shipped_items:'Articles expédiés',commission_cents:'Commission en EUR',payment_cents:'Paiement en EUR'};
   const allowed={orders:['orders','ordered_items'],earnings:['shipped_items','commission_cents'],payments:['payment_cents']};
   let text=initial,prepared=null,edit=0;
   const d=dialog('Importer un rapport Amazon France',`<p>CSV UTF-8, 1 Mo maximum. Aucun identifiant de connexion n’est demandé. Utilisez uniquement des lignes détaillées, sans totaux ni sous-totaux.</p><form id="aff-amazon-import"><label>Fichier CSV<input id="amz-file" type="file" accept=".csv,.txt"></label><label>Ligne de l’en-tête<input id="amz-header" type="number" min="1" max="101" value="1"></label><button type="button" id="amz-inspect">Lire les colonnes</button><label>Type de rapport<select id="amz-kind"><option value="earnings">Rémunérations</option><option value="orders">Commandes</option><option value="payments">Paiements</option></select></label><label>Début du rapport<input id="amz-start" type="date" required value="${esc(appliedRange.start)}"></label><label>Fin du rapport<input id="amz-end" type="date" required value="${esc(appliedRange.end)}"></label><label>Périmètre : all ou Tracking ID exact<input id="amz-scope" value="all" required></label><label>Séparateur décimal<select id="amz-decimal"><option value="comma">Virgule (12,34)</option><option value="dot">Point (12.34)</option></select></label><div id="amz-mapping"></div><button type="button" id="amz-preview">Vérifier l’import</button><div id="amz-review" role="status"></div><label class="aff-checkbox"><input id="amz-confirm" type="checkbox" required>Je confirme le périmètre, les colonnes et l’absence de totaux.</label><button id="amz-submit" disabled>Importer ce rapport</button></form>`);
   const form=$('aff-amazon-import');
   const invalidate=()=>{edit++;prepared=null;$('amz-submit').disabled=true;$('amz-review').textContent='';$('amz-confirm').checked=false};
   form.addEventListener('input',event=>{if(event.target.id!=='amz-confirm')invalidate()});
   $('amz-file').onchange=async event=>{invalidate();$('amz-mapping').replaceChildren();const f=event.target.files[0];text='';if(f){if(f.size>1024*1024){say('Fichier supérieur à 1 Mo.',true);return}const version=edit,value=await f.text();if(version===edit)text=value}};
   $('amz-kind').onchange=()=>{invalidate();$('amz-mapping').replaceChildren()};
   $('amz-header').onchange=()=>{$('amz-mapping').replaceChildren()};
   $('amz-inspect').onclick=async()=>{try{const version=edit,result=await request('amazon/inspect',{account:id,csv:text,header_row:Number($('amz-header').value)});if(!d.isConnected||version!==edit)return;const box=$('amz-mapping');box.replaceChildren();for(const key of ['date','tracking_id','asin','title','provider_status','transaction_id',...allowed[$('amz-kind').value]]){const label=document.createElement('label'),select=document.createElement('select');label.textContent=labels[key];select.dataset.amazonColumn=key;select.add(new Option('Non fourni',''));for(const h of result.headers)select.add(new Option(h,h));label.append(select);box.append(label)}const sample=document.createElement('pre');sample.style.whiteSpace='pre-wrap';sample.textContent=result.rows+' lignes\n'+result.sample.map(r=>r.join(' | ')).join('\n');box.append(sample)}catch(error){say(error.message,true)}};
   $('amz-preview').onclick=async()=>{invalidate();try{const payload={account:id,csv:text,header_row:Number($('amz-header').value),kind:$('amz-kind').value,start:$('amz-start').value,end:$('amz-end').value,scope:$('amz-scope').value,decimal:$('amz-decimal').value,mapping:Object.fromEntries([...form.querySelectorAll('[data-amazon-column]')].map(el=>[el.dataset.amazonColumn,el.value]))};const version=edit,result=await request('amazon/preview',payload);if(!d.isConnected||version!==edit)return;prepared=payload;$('amz-review').textContent=result.rows.length+' lignes · '+result.start+' → '+result.end+' · '+result.scope+' · '+allowed[result.kind].map(k=>{const values=result.rows.filter(r=>r[k]!==null);return labels[k]+': '+(values.length?(k.endsWith('_cents')?euro(values.reduce((n,r)=>n+r[k],0)):number(values.reduce((n,r)=>n+r[k],0))):'Non fourni')}).join(' · ');$('amz-submit').disabled=false}catch(error){say(error.message,true)}};
   form.onsubmit=async event=>{event.preventDefault();if(!prepared||!$('amz-confirm').checked)return;const button=$('amz-submit');button.disabled=true;try{const result=await request('amazon/import',{...prepared,confirmed:true});d.close();say(result.duplicate?'Rapport déjà importé : aucun doublon.':'Rapport Amazon importé.');await load()}catch(error){say(error.message,true);button.disabled=false}};
 }
 function partnerList(){return model.accounts.map(a=>`<article class="aff-partner"><div class="aff-avatar" aria-hidden="true">${esc(a.partner.slice(0,1))}</div><div><strong>${esc(a.partner)}</strong><small>${esc(a.label)} · ${esc(a.platform)}</small><small>Relevé : ${esc(at(a.last_success))}</small></div>${badge(a)}<button data-aff="open" data-id="${esc(a.id)}">Voir les détails</button></article>`).join('')}
 function partnerDistribution(){
   const groups=new Map();for(const a of model.accounts){const total=a.platform_id==='amazon'?(model.amazon||[]).find(r=>r.account_id===a.id)?.totals.commission_cents||0:sum(model.aggregate.filter(r=>r.account_id===a.id),'approved');const existing=groups.get(a.partner_id)||{name:a.partner,cents:0,known:false};existing.cents+=total;existing.known ||=Boolean(a.snapshot);groups.set(a.partner_id,existing)}
   const values=[...groups.values()],positive=values.reduce((n,v)=>n+Math.max(0,v.cents),0);let offset=0;
   const ring=positive?`<svg class="aff-donut" viewBox="0 0 120 120" role="img" aria-label="Répartition des commissions approuvées positives">${values.map((v,i)=>{const portion=Math.max(0,v.cents)/positive*100,part=`<circle class="aff-slice aff-slice-${i%4}" cx="60" cy="60" r="45" pathLength="100" stroke-dasharray="${portion} ${100-portion}" stroke-dashoffset="${-offset}"/>`;offset+=portion;return part}).join('')}</svg>`:'';
   return `<div class="aff-distribution">${ring}<dl class="aff-facts">${values.map(v=>`<div><dt>${esc(v.name)}</dt><dd>${v.known?euro(v.cents):'—'}</dd></div>`).join('')}</dl></div><small>Commissions approuvées Domadoo et déclarées Amazon importées, sur la période. Le cercle représente les montants positifs ; les corrections négatives restent dans les totaux.</small>`;
 }
 function salesQuery(){const query=range();query.set('page',String(page));query.set('search',search);query.set('status',status);return query}
 async function loadSales(){const ticket=++salesVersion,v=renderVersion,id=account;try{const result=await request('transactions?'+salesQuery());if(ticket!==salesVersion||! $('aff-sales-table')||account!==id||v!==renderVersion)return;page=result.page;
   $('aff-sales-table').innerHTML=`<div class="aff-table-wrap"><table><thead><tr><th>ID</th><th>Date du portail</th><th>Commande</th><th>Commission</th><th>Statut</th><th>Historique</th></tr></thead><tbody>${result.items.map(r=>`<tr><td>#${esc(r.provider_id)}</td><td>${esc(r.occurred_at)}</td><td>${euro(r.order_cents)}</td><td>${euro(r.commission_cents)}</td><td><span class="aff-badge ${!r.present?'aff-lost':r.status==='approved'?'aff-good':''}">${!r.present?'Perdu':r.status==='approved'?'Approuvée':'Non approuvée'}</span>${!r.present?`<small>Précédent : ${r.status==='approved'?'Approuvée':'Non approuvée'} · première disparition : ${esc(r.first_missing_at?new Intl.DateTimeFormat('fr-FR',{dateStyle:'short',timeStyle:'short',timeZone:'Europe/Paris'}).format(new Date(r.first_missing_at)):'Date inconnue')}</small>`:''}</td><td><button data-aff="history" data-id="${esc(r.provider_id)}">Voir</button></td></tr>`).join('')||'<tr><td colspan="6">Aucune vente pour cette sélection.</td></tr>'}</tbody></table></div><div class="aff-pagination"><span>${number(result.total)} ventes · page ${result.page} / ${result.pages}</span><button data-aff="previous" ${page===1?'disabled':''}>Précédente</button><button data-aff="next" ${page===result.pages?'disabled':''}>Suivante</button></div>`;
   }catch(e){say(e.message,true)}
 }
 async function loadPayments(){const v=++paymentsVersion,id=account;try{const result=await request('payments?account='+encodeURIComponent(id));if(v!==paymentsVersion||!$('aff-payments')||id!==account)return;$('aff-payments').innerHTML=`<div class="aff-table-wrap"><table><thead><tr><th>Créé à</th><th>Montant</th><th>Approuvé</th><th>Utilisé</th></tr></thead><tbody>${result.items.map(r=>`<tr><td>${esc(r.issued_on)}</td><td>${euro(r.amount_cents)}</td><td>${r.approved?'Oui':'Non'}</td><td>${r.used?'Oui':'Non'}</td></tr>`).join('')||'<tr><td colspan="4">Aucun bon dans le dernier relevé disponible.</td></tr>'}</tbody></table></div>`}catch(e){say(e.message,true)}}
 async function loadRuns(){const v=++runsVersion,id=account;try{const result=await request('runs?account='+encodeURIComponent(id));if(v!==runsVersion||!$('aff-runs')||id!==account)return;const html=result.items.length?`<ul class="aff-run-list">${result.items.map(r=>`<li><strong>${esc(at(r.started_at))}</strong><span>${({running:'En cours',success:'Complet',failed:'Échec'}[r.status])}</span><small>${r.status==='success'?number(r.rows)+' ventes · '+number(r.pages)+' pages':esc(r.message||'Connexion ou lecture du portail…')}</small></li>`).join('')}</ul>`:'<p>Aucune synchronisation effectuée.</p>';if($('aff-runs').innerHTML!==html)$('aff-runs').innerHTML=html}catch(e){say(e.message,true)}}
 function dialog(title,body){const d=$('aff-dialog');d.innerHTML=`<div class="panel-title"><h2 id="aff-dialog-title">${esc(title)}</h2><button data-aff="close" aria-label="Fermer">Fermer</button></div>${body}`;d.showModal();return d}
 async function closeDialog(){clearTimeout(loginTimer);loginGeneration++;const d=$('aff-dialog');if(loginAccount){const id=loginAccount;loginAccount='';await queueLogin('login/close',{account:id}).catch(()=>{})}d?.close()}
 async function showLogin(result){
   if(result.connected){loginAccount='';clearTimeout(loginTimer);$('aff-dialog').close();say('Session Domadoo enregistrée. Lancez une synchronisation pour vérifier les données.');await load();return}
   if(!result.active){await closeDialog();say('Fenêtre de connexion fermée ou expirée.');return}
   if(!$('aff-login-image'))return;
   $('aff-login-image').src='data:image/jpeg;base64,'+result.image;$('aff-login-location').textContent=result.location;
   $('aff-login-challenge').hidden=!result.challenge;
   $('aff-login-verify').disabled=Boolean(result.challenge);
   const d=result.diagnostic;
   const stages={security_check:'Vérification de sécurité du portail',verification:'Double vérification demandée',login_form:'Formulaire de connexion prêt',form_error:'Le formulaire signale une erreur — consultez la page',http_error:'Le portail refuse la requête HTTP',navigation_error:'Navigation interrompue',loading:'Chargement en cours',unknown:'Page non reconnue',browser_closed:'Navigateur fermé'};
   const sessions={restored:'Session précédente reprise',new:'Nouvelle session',browser_changed:'Navigateur changé : une première connexion humaine est nécessaire',unreadable:'Session illisible : une nouvelle connexion est nécessaire'};
   $('aff-login-status').textContent=d?`${stages[d.stage]||'Connexion en cours'} · ${sessions[d.session]||''}`:'';
   $('aff-login-diagnostic').textContent=d?JSON.stringify(d,null,2):'Diagnostic indisponible.';
   clearTimeout(loginTimer);loginTimer=setTimeout(()=>{if(loginAccount)loginAction('login/state')},2500);
 }
 async function loginAction(action,data={}){
   clearTimeout(loginTimer);const generation=loginGeneration,id=loginAccount;if(!id)return;
   try{const result=await queueLogin(action,{account:id,...data});if(generation===loginGeneration&&loginAccount===id)await showLogin(result)}
   catch(e){if(generation===loginGeneration){say(e.message,true);loginTimer=setTimeout(()=>{if(loginAccount)loginAction('login/state')},2500)}}
 }
 async function loginInput(data){await loginAction('login/input',data)}
 host.addEventListener('cancel',e=>{if(e.target.id==='aff-dialog'){e.preventDefault();closeDialog()}},true);
 function editDates(e){
   if(!['aff-start','aff-end'].includes(e.target.id))return;
   selectedRange={period:'custom',start:$('aff-start').value,end:$('aff-end').value};
   $('aff-period').value='custom';
 }
 host.addEventListener('input',editDates);
 host.addEventListener('change',e=>{
   if(e.target.id!=='aff-period'){editDates(e);return}
   selectPeriod(e.target.value);$('aff-start').value=selectedRange.start;$('aff-end').value=selectedRange.end;
 });
 host.addEventListener('click',async e=>{
   const button=e.target.closest('button');if(!button)return;
   if(button.dataset.affTab){tab=button.dataset.affTab;render();return}
   const action=button.dataset.aff;if(!action)return;
   try{
     if(action==='amazon-import')amazonImport(account);
     if(action==='reload')await load();
     if(action==='global'){account='';tab='overview';await load()}
     if(action==='partners'){account='';tab='partners';await load()}
     if(action==='open'){account=button.dataset.id;tab=selected()?.snapshot?'overview':'settings';page=1;await load()}
     if(action==='settings'){tab='settings';render()}
     if(action==='range'){
       const from=$('aff-start'),to=$('aff-end');
       if(!from.reportValidity()||!to.reportValidity())return;
       if(from.value&&to.value&&from.value>to.value)throw new Error('La date « Du » doit précéder ou être égale à la date « Au ».');
       selectedRange={period:$('aff-period').value,start:from.value,end:to.value};
       appliedRange={...selectedRange};page=1;salesVersion++;await load();
     }
     if(action==='previous'||action==='next'){page+=action==='next'?1:-1;await loadSales()}
     if(action==='sync'){
       if(syncStarting||model.accounts.some(a=>a.running))return;
       const ids=account?[account]:model.accounts.filter(a=>a.platform_id==='domadoo'&&a.available&&a.session_state==='connected').map(a=>a.id);
       if(!ids.length)throw new Error('Connectez d’abord un compte dans ses paramètres.');
       syncStarting=true;refreshSyncState();
       try{await request('sync',{account:ids[0],accounts:ids});say('Synchronisation lancée.');await load({poll:true})}
       finally{syncStarting=false;refreshSyncState()}
     }
     if(action==='disconnect'){await request('disconnect',{account});say('Session supprimée et collecte quotidienne désactivée.');await load()}
     if(action==='close')await closeDialog();
     if(action==='history'){
       const history=await request('history?'+new URLSearchParams({account,id:button.dataset.id}));
       dialog('Historique de la vente #'+button.dataset.id,`<p>Dates d’observation dans LinKs ; aucune date de validation fournisseur n’est supposée.</p><ul class="aff-run-list">${history.items.map(r=>{const before=r.before_json?JSON.parse(r.before_json):null,after=JSON.parse(r.after_json);return `<li><strong>${esc(at(r.observed_at))}</strong><span>${before?euro(before.commission_cents)+' → ':''}${euro(after.commission_cents)}</span><small>${!after.present?'Perdu — disparu du relevé complet':after.status==='approved'?'Approuvée':'Non approuvée'}${before?' · correction observée':' · première observation'}</small></li>`}).join('')}</ul>`);
     }
     if(action==='export'){
       button.disabled=true;const saved=page,rows=[],ids=new Set();try{let n=1,totalPages=1,version;do{const q=salesQuery();q.set('page',n);const result=await request('transactions?'+q);if(n===1)version=result.snapshot_id;if(result.snapshot_id!==version)throw new Error('Le relevé a changé pendant l’export. Relancez l’export.');for(const row of result.items){if(ids.has(row.provider_id))throw new Error('Export incohérent : relancez après la synchronisation.');ids.add(row.provider_id)}totalPages=result.pages;rows.push(...result.items);n++}while(n<=totalPages)}finally{page=saved;button.disabled=false}
       const csv=[['ID','Date du portail','Commande EUR','Commission EUR','Statut','Statut précédent ou réel','Première disparition','Présente au dernier relevé'],...rows.map(r=>[r.provider_id,r.occurred_at,(r.order_cents/100).toFixed(2),(r.commission_cents/100).toFixed(2),r.present?r.status:'Perdu',r.status,r.first_missing_at||'',r.present?'Oui':'Non'])].map(r=>r.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(';')).join('\r\n');
       const url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='links-affiliation.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
     }
     if(action==='add'){
       dialog('Ajouter un partenaire',`<form id="aff-add-form"><label>Partenaire commercial<input name="partner" required maxlength="80" placeholder="Ex. Reolink"></label><label>Nom du compte<input name="label" required maxlength="80" placeholder="Mon compte affilié"></label><label>Plateforme<select name="platform">${model.platforms.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}${p.available?'':' · connecteur à venir'}</option>`).join('')}</select></label><p>Domadoo utilise exclusivement son portail officiel. Aucun changement n’est apporté aux liens affiliés existants.</p><button class="primary">Ajouter</button></form>`);
       $('aff-add-form').onsubmit=async event=>{event.preventDefault();try{await request('accounts',Object.fromEntries(new FormData(event.target)));await closeDialog();await load()}catch(error){say(error.message,true)}};
     }
     if(action==='login'){
       button.disabled=true;loginGeneration++;const result=await queueLogin('login/start',{account});loginAccount=account;
       const d=dialog('Connexion personnelle Domadoo',`<p>Les saisies sont transmises au navigateur du serveur, sans enregistrement du mot de passe. Cliquez dans le champ de la page puis utilisez la saisie ci-dessous. Réalisez vous-même toute double vérification ou protection.</p><p id="aff-login-challenge" role="status" hidden><strong>Vérification de sécurité Domadoo en cours.</strong> Suivez uniquement les instructions affichées par le portail. Si cette page reste bloquée, fermez la fenêtre et contactez Domadoo : le navigateur du serveur peut être refusé. Une connexion réussie sur votre ordinateur ne connecte pas LinKs. Aucun relevé ne sera récupéré avant validation de cet accès.</p><p id="aff-login-location"></p><img id="aff-login-image" class="aff-login-image" alt="Fenêtre de connexion Domadoo interactive" tabindex="0"><form id="aff-type-form" class="aff-filters"><label>Saisie dans le champ sélectionné<input id="aff-login-text" type="password" autocomplete="off" maxlength="500"></label><button>Transmettre la saisie</button></form><div class="aff-actions"><button data-login-key="Tab">Champ suivant</button><button data-login-key="ControlOrMeta+A">Tout sélectionner</button><button data-login-key="Backspace">Effacer</button><button data-login-key="Enter">Entrée</button><button data-login-scroll="-500">Monter</button><button data-login-scroll="500">Descendre</button><button id="aff-login-verify">Vérifier mon accès affilié</button></div>`);
       const diagnostic=document.createElement('div');diagnostic.className='aff-connection-diagnostic';
       diagnostic.innerHTML='<p id="aff-login-status" role="status"></p><details><summary>Diagnostic de connexion (sans identifiants)</summary><p>À transmettre si la connexion reste bloquée. Aucun mot de passe, cookie ni jeton n’est inclus.</p><pre id="aff-login-diagnostic"></pre><button type="button" id="aff-copy-diagnostic">Copier le diagnostic</button></details>';
       $('aff-login-location').before(diagnostic);
       $('aff-copy-diagnostic').onclick=async()=>{try{await navigator.clipboard.writeText($('aff-login-diagnostic').textContent);say('Diagnostic copié.')}catch{say('Sélectionnez le diagnostic pour le copier manuellement.',true)}};
       $('aff-login-image').onclick=event=>{const rect=event.target.getBoundingClientRect();loginInput({kind:'click',x:(event.clientX-rect.left)/rect.width*1100,y:(event.clientY-rect.top)/rect.height*760})};
       $('aff-type-form').onsubmit=event=>{event.preventDefault();const input=$('aff-login-text'),text=input.value;input.value='';loginInput({kind:'text',text})};
       d.querySelectorAll('[data-login-key]').forEach(b=>b.onclick=()=>loginInput({kind:'key',key:b.dataset.loginKey}));d.querySelectorAll('[data-login-scroll]').forEach(b=>b.onclick=()=>loginInput({kind:'scroll',delta:Number(b.dataset.loginScroll)}));
       $('aff-login-verify').onclick=()=>loginAction('login/verify');
       await showLogin(result);button.disabled=false;
     }
   }catch(error){say(error.message,true);button.disabled=false}
 });
 window.LinksAffiliation={load};
})();
