/* LinKs statistics: one authenticated workspace, four independent event families. */
"use strict";
(function (root) {
  const palette = {youtube:'#43bdf6',instagram:'#b895ff',discord:'#34d8ae',facebook:'#659eff',tiktok:'#ed91b5',google:'#efbd5f',linkedin:'#7da6e3',twitter:'#9eaac4',telegram:'#68cce0',newsletter:'#e8bc79',mail:'#f09c73',site:'#8ebd7e',qr:'#df9bd7',other:'#b4a089',unknown:'#8d99ac'};
  const labels = {youtube:'YouTube',instagram:'Instagram',discord:'Discord',facebook:'Facebook',google:'Google','direct-inconnu':'Non identifiée','shared-unknown':'Non identifiée','instagram-story':'Non identifiée · historique incertain',unknown:'Non identifiée','autre-site':'Autre site','autre-campagne':'Autre campagne'};
  const config = {
    visits:{title:'Visites de la page LinKs',subtitle:'Fréquentation de la page publique',unit:'visites',count:'Origines',icon:'eye',color:'var(--accent)'},
    tracked:{title:'Ouvertures de liens suivis',subtitle:'Chaque lien conserve toutes ses provenances',unit:'ouvertures',count:'Liens ouverts',icon:'link',color:'var(--purple)'},
    public:{title:'Clics sur les liens publics',subtitle:'Clics enregistrés sur la page publique',unit:'clics publics',count:'Liens cliqués',icon:'click',color:'var(--accent)'},
    campaigns:{title:'Campagnes partagées',subtitle:'Ouvertures des liens de campagne, archives comprises',unit:'ouvertures',count:'Campagnes ouvertes',icon:'campaign',color:'var(--warning)'}
  };
  const sum = values => Object.values(values || {}).reduce((a,b) => a+b,0);
  const aggregate = items => {const result=Object.create(null);for(const item of items)for(const [key,n] of Object.entries(item.sources))result[key]=(result[key]||0)+n;return result;};
  function filter(items, query='', source='', platform=()=>null) {
    const q=query.trim().toLocaleLowerCase('fr');
    return items.filter(item=>!q||[item.name,item.id].join(' ').toLocaleLowerCase('fr').includes(q)).map(item=>{
      const sources=Object.fromEntries(Object.entries(item.sources).filter(([key])=>!source||(source.startsWith('p:')?platform(key)===source.slice(2):key===source)));
      return {...item,sources,total:sum(sources)};
    }).filter(item=>item.total>0).sort((a,b)=>b.total-a.total||String(a.id).localeCompare(String(b.id),'fr'));
  }
  function percentages(values) {
    const total=sum(values);if(!total)return Object.fromEntries(Object.keys(values).map(key=>[key,0]));
    const entries=Object.entries(values).map(([key,n])=>({key,exact:n*100/total,value:Math.floor(n*100/total)}));
    let rest=100-entries.reduce((n,item)=>n+item.value,0);
    for(const item of [...entries].sort((a,b)=>(b.exact-b.value)-(a.exact-a.value)||a.key.localeCompare(b.key)))if(rest-->0)item.value++;
    return Object.fromEntries(entries.map(item=>[item.key,item.value]));
  }
  const shift=(day,n)=>{const d=new Date(day+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10);};
  root.LinksStatisticsModel={filter,aggregate,percentages,shift,palette};
  if(typeof document==='undefined')return;
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=new Intl.NumberFormat('fr-FR');
  const paths={overview:'<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',link:'<path d="m10 13 4-4M8 15H6a4 4 0 0 1 0-8h4a4 4 0 0 1 4 4M16 9h2a4 4 0 1 1 0 8h-4a4 4 0 0 1-4-4"/>',campaign:'<path d="M3 11v4a2 2 0 0 0 2 2h3l2 4h3l-2.5-5.5L19 19V7l-8.5 3.5H5a2 2 0 0 0-2 2M21 10a4 4 0 0 1 0 6"/>',chart:'<path d="M3 3v18h18m-14-5 4-5 4 3 5-8"/>',pie:'<path d="M21 13a9 9 0 1 1-10-10v10ZM13 3v8h8A9 9 0 0 0 13 3Z"/>',click:'<path d="m5 3 14 10-7 1-3 7Zm7 11 4 7"/>'};
  const icon=name=>`<svg class="sw-icon" viewBox="0 0 24 24" aria-hidden="true">${paths[name]||paths.chart}</svg>`;
  const state={tab:'overview',mode:'tracked',date:'',period:'30',metric:'tracked',query:'',source:'',selected:null,data:null,loading:false,error:'',request:0};
  let host,options,visible=[],all=[],sequence=0,scrollFrame=0,platformCache=new Map();
  const category=()=>state.tab==='links'?state.mode:state.tab;
  const sourceName=key=>labels[key]||state.data?.sources.names[key]||state.data?.sources.metadata.find(row=>'tracked:'+row.id===key||row.id===key)?.name||'Non identifiée';
  function groups(sources) {
    return root.StudioSourcePlatforms.group(Object.entries(sources).map(([key,total])=>({key,total,label:sourceName(key)})),state.data?.sources.metadata||[]).map(group=>({...group,label:group.key==='unknown'?'Non identifiée':group.label}));
  }
  const platform=key=>{if(!platformCache.has(key))platformCache.set(key,groups({[key]:1})[0]?.key);return platformCache.get(key);};
  const dateLabel=day=>new Intl.DateTimeFormat('fr-FR',{dateStyle:'long',timeZone:'UTC'}).format(new Date(day+'T12:00:00Z'));
  const pill=text=>`<span class="sw-pill">${esc(text)}</span>`;
  function donut(sources,unit,size=242) {
    const parts=groups(sources),total=sum(sources),circ=2*Math.PI*51,id='sw-mask-'+(++sequence);let offset=0;
    const rings=parts.map(part=>{const length=part.total/total*circ;const markup=`<circle cx="70" cy="70" r="51" fill="none" stroke="${palette[part.key]||palette.other}" stroke-width="16" stroke-dasharray="${length} ${circ}" stroke-dashoffset="${-offset}" transform="rotate(-90 70 70)"/>`;offset+=length;return markup;}).join('');
    return `<svg class="sw-donut" viewBox="0 0 140 140" width="${size}" height="${size}" role="img" aria-label="${esc(total?parts.map(p=>p.label+' : '+p.total).join(', '):'Aucune donnée')}"><defs><mask id="${id}" maskUnits="userSpaceOnUse" x="0" y="0" width="140" height="140"><rect width="140" height="140" fill="black"/><circle class="sw-reveal" cx="70" cy="70" r="51" stroke="white" stroke-width="20" fill="none" transform="rotate(-90 70 70)"/></mask></defs><circle cx="70" cy="70" r="51" fill="none" stroke="var(--line)" stroke-width="16"/>${total?`<g mask="url(#${id})">${rings}</g>`:''}<g class="sw-fade"><text class="sw-donut-number" x="70" y="67" text-anchor="middle">${fmt.format(total)}</text><text class="sw-donut-unit" x="70" y="84" text-anchor="middle">${esc(unit)}</text></g></svg>`;
  }
  function legend(sources) {
    const parts=groups(sources),shares=percentages(Object.fromEntries(parts.map(p=>[p.key,p.total])));
    return `<div class="sw-legend sw-fade">${parts.map(p=>`<div class="sw-source"><span><svg width="10" height="10" aria-hidden="true"><rect width="10" height="10" rx="3" fill="${palette[p.key]||palette.other}"/></svg>${esc(p.label)}</span><strong>${fmt.format(p.total)}</strong><span>${shares[p.key]} %</span></div>`).join('')||'<p class="sw-muted">Aucune donnée sur cette journée.</p>'}</div>`;
  }
  function chart(metric,series=state.data.series) {
    const cfg=config[metric],w=1320,h=225,l=44,r=12,t=18,b=29,peak=Math.max(1,...series.map(d=>d[metric])),max=Math.ceil(peak/4)*4;
    const coords=series.map((d,i)=>[l+i/Math.max(1,series.length-1)*(w-l-r),t+(h-t-b)*(1-d[metric]/max)]),path=coords.map(([x,y],i)=>`${i?'L':'M'}${x.toFixed(2)} ${y.toFixed(2)}`).join(' '),id='sw-fill-'+(++sequence);
    const grid=[0,1,2,3,4].map(n=>{const y=t+(h-t-b)*n/4;return `<path d="M${l} ${y}H${w-r}" stroke="var(--line)" stroke-dasharray="2 5"/><text x="${l-9}" y="${y+4}" text-anchor="end">${fmt.format(max*(1-n/4))}</text>`;}).join('');
    return `<div class="sw-chart"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(cfg.title+', du '+dateLabel(series[0].day)+' au '+dateLabel(series.at(-1).day))}"><defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1"><stop stop-color="${cfg.color}" stop-opacity=".25"/><stop offset="1" stop-color="${cfg.color}" stop-opacity="0"/></linearGradient></defs>${grid}<path d="${path} L${coords.at(-1)[0]} ${h-b} L${l} ${h-b}Z" fill="url(#${id})"/><path class="sw-series" d="${path}" fill="none" stroke="${cfg.color}" stroke-width="3" stroke-linejoin="round"/>${coords.map(([x,y],i)=>`<circle cx="${x}" cy="${y}" r="3" fill="${cfg.color}"/><circle cx="${x}" cy="${y}" r="11" fill="transparent"><title>${esc(dateLabel(series[i].day))} : ${fmt.format(series[i][metric])} ${cfg.unit}</title></circle>`).join('')}</svg></div><div class="sw-axis"><span>${dateLabel(series[0].day)}</span><span>${dateLabel(series.at(-1).day)}</span></div>`;
  }
  function overview() {
    const d=state.data,o=d.overview,change=d.previous_visits>0?Math.round((o.visits.total-d.previous_visits)*100/d.previous_visits):null;
    return `<div class="sw-overview"><article class="sw-card sw-visits"><div class="sw-card-head"><h2>${icon('eye')}Visites aujourd’hui</h2>${pill('Aujourd’hui')}</div><strong class="sw-metric">${fmt.format(o.visits.total)}</strong><p class="sw-muted">Ouvertures de la page publique LinKs</p><div class="sw-push"><span class="sw-trend ${change===null?'sw-neutral':change<0?'sw-negative':''}">${change===null?'— Comparaison indisponible':(change>=0?'+':'')+change+' % vs veille'}</span><button class="sw-link" data-sw-go="visits">Voir les visites →</button></div></article><article class="sw-card sw-links"><div class="sw-card-head"><h2>${icon('link')}Performance des liens</h2><button class="sw-link" data-sw-go="links">Analyser →</button></div><div class="sw-link-mid">${donut(o.tracked.sources,'ouvertures',146)}${legend(o.tracked.sources)}</div><p class="sw-muted sw-link-note">${fmt.format(o.tracked.total)} ouvertures suivies · ${fmt.format(o.public.total)} clics publics, comptés séparément</p></article><article class="sw-card sw-campaigns"><div class="sw-card-head"><h2>${icon('campaign')}Campagnes actives</h2>${pill(d.active_count+' actives')}</div><div class="sw-campaign-list">${d.active_campaigns.map(c=>`<button class="sw-campaign" data-sw-campaign="${esc(c.id)}" title="${esc(c.name)}"><span class="sw-dot" aria-hidden="true"></span><span><strong>${esc(c.name)}</strong><small>${fmt.format(c.total)} ouvertures aujourd’hui</small></span><span aria-hidden="true">›</span></button>`).join('')||'<p class="sw-muted">Aucune campagne active actuellement.</p>'}</div><button class="sw-link sw-push" data-sw-go="campaigns">Voir les campagnes →</button></article></div><section class="sw-card sw-month"><div class="sw-card-head"><div><h2>${icon('chart')}Performances mensuelles</h2><p class="sw-muted">${d.period==='month'?'Mois civil en cours':'30 derniers jours'} · une mesure à la fois</p></div><div class="sw-chart-tools"><label class="sr-only" for="sw-period">Période du graphique</label><select id="sw-period"><option value="30" ${state.period==='30'?'selected':''}>30 jours glissants</option><option value="month" ${state.period==='month'?'selected':''}>Mois civil</option></select><div class="sw-toggle" role="group" aria-label="Mesure du graphique">${[['visits','Visites'],['tracked','Liens suivis'],['campaigns','Campagnes']].map(([id,label])=>`<button data-sw-metric="${id}" aria-pressed="${state.metric===id}">${label}</button>`).join('')}</div></div></div>${chart(state.metric)}<p class="sw-muted sw-chart-note">${esc(config[state.metric].title)} · ${esc(d.timezone)}</p></section>`;
  }
  function detailShell() {
    const key=category(),cfg=config[key];all=state.data.details[key].items.map(item=>key==='visits'?{...item,name:sourceName(item.id)}:item);
    const allSources=aggregate(all),platforms=groups(allSources);
    return `<div class="sw-detail-toolbar"><div><h2>${esc(cfg.title)}</h2><p class="sw-muted">${cfg.subtitle}</p></div><div class="sw-date"><button data-sw-day="-1" aria-label="Journée précédente">←</button><label class="sr-only" for="sw-date">Journée consultée</label><input id="sw-date" type="date" value="${state.date}" max="${state.data.today}" required><button data-sw-day="1" aria-label="Journée suivante" ${state.date>=state.data.today?'disabled':''}>→</button></div></div><div id="sw-kpis" class="sw-kpis"></div><div class="sw-detail-grid"><section class="sw-card sw-list-panel"><div class="sw-card-head"><h3>${icon(cfg.icon)}Détail du jour</h3>${pill(dateLabel(state.date))}</div><div class="sw-filters">${state.tab==='links'?`<div class="sw-toggle" role="group" aria-label="Type de liens"><button data-sw-mode="tracked" aria-pressed="${state.mode==='tracked'}">Suivis</button><button data-sw-mode="public" aria-pressed="${state.mode==='public'}">Publics</button></div>`:''}<input id="sw-search" type="search" aria-label="Rechercher un élément" placeholder="Rechercher un nom ou un identifiant…" value="${esc(state.query)}"><label class="sr-only" for="sw-source">Origine</label><select id="sw-source"><option value="">Toutes les origines</option><optgroup label="Plateformes">${platforms.map(p=>`<option value="p:${esc(p.key)}">${esc(p.label)}</option>`).join('')}</optgroup><optgroup label="Sources de publication">${Object.keys(allSources).sort((a,b)=>sourceName(a).localeCompare(sourceName(b),'fr')).map(key=>`<option value="${esc(key)}">${esc(sourceName(key))}</option>`).join('')}</optgroup></select><button class="sw-reset" data-sw-reset aria-label="Effacer la recherche et le filtre">Effacer</button></div><div id="sw-results" class="sw-results" role="list" aria-label="${esc(cfg.title)} · flèches haut et bas pour parcourir tous les résultats" tabindex="0"></div><div class="sw-list-foot"><span id="sw-result-count"></span><span>Sélectionnez une ligne pour voir ses origines</span></div></section><aside id="sw-context" class="sw-card sw-context" aria-live="polite" aria-atomic="true"></aside></div><details class="sw-evolution"><summary>${icon('chart')}Évolution de la période — ${cfg.unit}</summary>${chart(key,state.data.detail_series)}<p class="sw-muted">${esc(cfg.title)} · toutes les origines, indépendamment des filtres du jour</p><details class="sw-chart-table"><summary>Consulter les valeurs du graphique</summary><table><thead><tr><th>Jour</th><th>${cfg.unit}</th></tr></thead><tbody>${state.data.detail_series.map(row=>`<tr><td>${dateLabel(row.day)}</td><td>${fmt.format(row[key])}</td></tr>`).join('')}</tbody></table></details></details>`;
  }
  function updateResults(resetScroll=true) {
    visible=filter(all,state.query,state.source,platform);if(!visible.some(item=>item.id===state.selected))state.selected=null;
    const total=sum(aggregate(visible)),cfg=config[category()];
    host.querySelector('#sw-kpis').innerHTML=[[cfg.unit,total,cfg.icon],[cfg.count,visible.length,'link'],['Origines distinctes',groups(aggregate(visible)).length,'pie']].map(([label,n,ico])=>`<div class="sw-mini"><span>${icon(ico)}</span><div><small>${label}${state.source||state.query?' · filtrées':''}</small><strong>${fmt.format(n)}</strong></div></div>`).join('');
    host.querySelector('#sw-result-count').textContent=fmt.format(visible.length)+' résultat(s)';
    const list=host.querySelector('#sw-results');if(resetScroll)list.scrollTop=0;renderRows();renderContext();
  }
  function renderRows(focusIndex=null) {
    const list=host.querySelector('#sw-results');if(!list)return;
    if(!visible.length){list.innerHTML='<p class="sw-empty">Aucun résultat sur cette journée avec ces filtres.</p>';return;}
    const size=64,start=Math.max(0,Math.floor(list.scrollTop/size)-5),end=Math.min(visible.length,start+Math.ceil((list.clientHeight||322)/size)+11);
    const active=focusIndex??(list.contains(document.activeElement)?Number(document.activeElement.dataset.swIndex):null);
    const fragment=document.createDocumentFragment(),before=document.createElement('div');before.style.height=(start*size)+'px';before.setAttribute('role','presentation');fragment.append(before);
    for(let i=start;i<end;i++){
      const item=visible[i],row=document.createElement('div');row.className='sw-result';row.setAttribute('role','listitem');row.setAttribute('aria-posinset',i+1);row.setAttribute('aria-setsize',visible.length);
      row.innerHTML=`<button class="sw-row" data-sw-index="${i}" aria-pressed="${state.selected===item.id}" title="${esc(item.name)}"><span class="sw-row-icon">${icon(config[category()].icon)}</span><span class="sw-row-copy"><strong>${esc(item.name)}</strong><small>${esc(item.status|| (category()==='visits'?'Provenance de la visite':category()==='public'?'Clic depuis la page publique':'Lien suivi'))}</small></span><span class="sw-selected-label" aria-hidden="true">Sélectionné</span><b>${fmt.format(item.total)}</b></button>`;fragment.append(row);
    }
    const after=document.createElement('div');after.style.height=((visible.length-end)*size)+'px';after.setAttribute('role','presentation');fragment.append(after);list.replaceChildren(fragment);
    if(active!==null)list.querySelector(`[data-sw-index="${active}"]`)?.focus({preventScroll:true});
  }
  function renderContext() {
    const item=visible.find(row=>row.id===state.selected),sources=item?.sources||aggregate(visible),node=host.querySelector('#sw-context');
    node.innerHTML=`<div class="sw-card-head"><h3>${icon('pie')}Répartition par origine</h3>${pill(item?'Sélection':state.query||state.source?'Résultats filtrés':'Global')}</div><p class="sw-context-title" title="${esc(item?.name||'Toutes les origines')}">${esc(item?.name||'Toutes les origines')}</p>${donut(sources,config[category()].unit)}${legend(sources)}<p class="sw-context-note">${item?'Cliquez de nouveau sur cette ligne pour revenir à la répartition globale.':'Sélectionnez une ligne pour afficher ses origines.'}</p>`;
    for(const button of host.querySelectorAll('[data-sw-index]'))button.setAttribute('aria-pressed',String(visible[Number(button.dataset.swIndex)]?.id===state.selected));
  }
  function render() {
    const tabs=[['overview','Vue d’ensemble','overview'],['visits','Visites','eye'],['links','Liens','link'],['campaigns','Campagnes','campaign']];
    const activeId=host.contains(document.activeElement)?document.activeElement.id:null;
    host.innerHTML=`<header class="sw-heading"><div><span class="sw-heading-icon">${icon('chart')}</span><div><h1>Statistiques</h1><p class="sw-muted">L’essentiel aujourd’hui, les détails à la demande.</p></div></div><span class="sw-date-label">${state.data?esc(dateLabel(state.data.today)):''}</span><details class="sw-actions"><summary>Actions rapides</summary><div><button data-quick-create="tracked">Créer un lien suivi</button><button data-quick-create="campaign">Créer une campagne</button><button data-open-view="content">Organiser la page</button></div></details></header><nav class="sw-tabs" role="tablist" aria-label="Vues statistiques">${tabs.map(([id,label,ico])=>`<button id="sw-tab-${id}" role="tab" data-sw-tab="${id}" aria-controls="sw-panel" aria-selected="${id===state.tab}" tabindex="${id===state.tab?0:-1}">${icon(ico)}${label}</button>`).join('')}</nav><div id="sw-status" role="status" class="sw-status">${state.error?`<span>${esc(state.error)}</span><button data-sw-retry>Réessayer</button>`:state.loading?'Chargement des statistiques…':state.data?.collection_enabled===false?'Collecte désactivée : seuls les événements déjà enregistrés sont disponibles.':''}</div><div id="sw-panel" role="tabpanel" aria-labelledby="sw-tab-${state.tab}" aria-busy="${state.loading}">${!state.data||state.loading||state.error?'':state.tab==='overview'?overview():detailShell()}</div>`;
    const legacy=document.getElementById('statistics-legacy');legacy.hidden=state.tab==='overview';if(legacy.hidden)legacy.open=false;
    if(state.data&&!state.loading&&!state.error&&state.tab!=='overview'){
      host.querySelector('#sw-source').value=state.source;
      updateResults();host.querySelector('#sw-results').addEventListener('scroll',()=>{cancelAnimationFrame(scrollFrame);scrollFrame=requestAnimationFrame(()=>renderRows());});
    }
    if(activeId)document.getElementById(activeId)?.focus({preventScroll:true});
  }
  async function load() {
    if(!options)return;const request=++state.request;state.loading=true;state.error='';state.selected=null;render();
    try{const data=await options.api('/api/stats/workspace?'+new URLSearchParams({date:state.date,period:state.period}));if(request!==state.request)return;state.data=data;platformCache.clear();state.date=data.date;state.loading=false;render();}
    catch(error){if(request!==state.request)return;state.loading=false;state.error='Statistiques indisponibles. '+error.message;render();}
  }
  function navigate(tab,{query='',mode=state.mode}={}) {
    state.tab=tab;state.mode=mode;state.query=query;state.source='';state.selected=null;render();
  }
  function bind() {
    host.addEventListener('click',event=>{
      const button=event.target.closest('button');if(!button)return;const d=button.dataset;
      if(d.swTab||d.swGo)return navigate(d.swTab||d.swGo);
      if(d.swMetric){state.metric=d.swMetric;render();return;}
      if(d.swMode){state.mode=d.swMode;state.selected=null;state.source='';state.query='';render();return;}
      if(d.swIndex!==undefined){const item=visible[Number(d.swIndex)];state.selected=state.selected===item.id?null:item.id;renderContext();return;}
      if(d.swCampaign){state.date=state.data.today;navigate('campaigns');load();return;}
      if(d.swDay){state.date=shift(state.date,Number(d.swDay));load();return;}
      if('swReset' in d){state.query='';state.source='';state.selected=null;host.querySelector('#sw-search').value='';host.querySelector('#sw-source').value='';updateResults();return;}
      if('swRetry' in d)load();
    });
    host.addEventListener('input',event=>{if(event.target.id==='sw-search'){state.query=event.target.value;state.selected=null;updateResults();}});
    host.addEventListener('change',event=>{
      const el=event.target;if(el.id==='sw-date'&&el.validity.valid&&el.value){state.date=el.value;load();}
      if(el.id==='sw-source'){state.source=el.value;state.selected=null;updateResults();}
      if(el.id==='sw-period'){state.period=el.value;try{localStorage.setItem('links.statistics.period',state.period);}catch{}load();}
    });
    host.addEventListener('keydown',event=>{
      const tab=event.target.closest('[data-sw-tab]');
      if(tab&&['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){
        event.preventDefault();const ids=['overview','visits','links','campaigns'],index=ids.indexOf(state.tab),next=event.key==='Home'?0:event.key==='End'?3:(index+(event.key==='ArrowRight'?1:3))%4;navigate(ids[next]);document.getElementById('sw-tab-'+ids[next]).focus();return;
      }
      const list=event.target.closest('#sw-results');if(!list||!visible.length||!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;
      event.preventDefault();const current=event.target.dataset.swIndex===undefined?-1:Number(event.target.dataset.swIndex),index=event.key==='Home'?0:event.key==='End'?visible.length-1:Math.max(0,Math.min(visible.length-1,current+(event.key==='ArrowDown'?1:-1)));
      if(index*64<list.scrollTop||index*64+64>list.scrollTop+list.clientHeight)list.scrollTop=Math.max(0,index*64-list.clientHeight/2);renderRows(index);
    });
  }
  root.LinksStatistics={
    init(settings){options=settings;host=document.getElementById('statistics-workspace');try{const p=localStorage.getItem('links.statistics.period');if(['30','month'].includes(p))state.period=p;}catch{}bind();return load();},
    load,navigate,
    open(scope,query=''){const tab=scope==='campaigns'?'campaigns':['tracked','shared','public'].includes(scope)?'links':'overview';navigate(tab,{query,mode:scope==='public'?'public':'tracked'});},
  };
})(typeof window==='undefined'?globalThis:window);
