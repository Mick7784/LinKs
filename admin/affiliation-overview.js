"use strict";
// The server owns eligibility, coverage and reconciliation. No financial mapping here.
(()=>{
 const money=n=>n==null?'N/D':new Intl.NumberFormat('fr-FR',{style:'currency',currency:'EUR'}).format(n/100);
 const date=s=>s?s.split('-').reverse().join('/'):'N/D';
 const percent=n=>n==null?'N/D':new Intl.NumberFormat('fr-FR',{maximumFractionDigits:1,signDisplay:'exceptZero'}).format(n)+' %';
 const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const color=id=>{let h=0;for(const c of id)h=(h*31+c.charCodeAt(0))>>>0;return `hsl(${h%360} 66% 58%)`};
 const status=s=>({complete:'Complet',partial:'Partiel',unavailable:'Indisponible'}[s]);
 let selected=null,comparison='none',observer=null;

 function distribution(entries,total){
   const negative=entries.some(p=>p.cents<0),positive=total>0&&!negative;
   let offset=0;
   const slices=positive?entries.filter(p=>p.cents>0).map(p=>{const length=p.cents/total*100;const html=`<circle cx="60" cy="60" r="46" pathLength="100" fill="none" stroke="${color(p.id)}" stroke-width="15" stroke-dasharray="${length} ${100-length}" stroke-dashoffset="${-offset}"/>`;offset+=length;return html}).join(''):'';
   return `<div class="aff-overview-distribution"><div class="aff-overview-ring"><svg viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="46" fill="none" stroke="var(--line)" stroke-width="15"/>${slices}</svg><strong>${safe(money(total))}</strong></div><ul class="aff-overview-breakdown">${entries.map(p=>`<li><span class="aff-overview-dot" style="background:${color(p.id)}"></span><span>${safe(p.name)}<small>${status(p.status)}${p.commission_status?' · '+safe(p.commission_status):''} · ${positive&&p.cents!=null?new Intl.NumberFormat('fr-FR',{maximumFractionDigits:1}).format(p.cents/total*100)+' %':'Part N/D'}</small></span><strong>${safe(money(p.cents))}</strong></li>`).join('')}</ul></div>${negative?'<p class="field-help">Corrections négatives incluses dans le total net. Répartition circulaire et pourcentages masqués pour ne pas déformer ces montants.</p>':total==null?'<p class="aff-empty">Aucun montant admissible connu pour cette sélection.</p>':total===0?'<p class="field-help">Total connu à 0 € ; aucune part à représenter.</p>':''}`;
 }

 function scale(values){
   const low=Math.min(0,...values),high=Math.max(0,...values),rough=Math.max(1,(high-low)/5);
   const magnitude=10**Math.floor(Math.log10(rough));
   const step=[1,2,5,10].map(x=>x*magnitude).find(x=>x>=rough);
   return {min:Math.floor(low/step)*step,max:Math.max(step,Math.ceil(high/step)*step),step};
 }

 function render(host,model){
   observer?.disconnect();
   if(!model){host.innerHTML='<p class="aff-empty">Vue consolidée indisponible. Réessayez le chargement.</p>';return}
   if(!model.daily.some(d=>d.day===selected))selected=[...model.daily].reverse().find(d=>d.cents!=null)?.day||model.end;
   const knownDates=model.accounts.filter(a=>a.eligible&&a.collected_at).map(a=>a.collected_at).sort();
   const excluded=model.accounts.some(a=>!a.eligible);
   const at=v=>new Intl.DateTimeFormat('fr-FR',{dateStyle:'short',timeStyle:'short',timeZone:'Europe/Paris'}).format(new Date(v));
   const trend=(key,label)=>{const c=model.comparisons[key];return `<article class="aff-card"><span>${label}</span><strong>${safe(percent(c.percent))}</strong><small>${c.reason?'Comparaison indisponible : '+safe(c.reason):`${date(c.start)} → ${date(c.end)} · mêmes partenaires éligibles`}</small></article>`};
   host.innerHTML=`<div class="aff-overview-coverage"><p>${model.included_partners} / ${model.total_partners} partenaires pris en compte${model.partial?' · Total partiel':''} · ${knownDates.length?'Collecte de référence la plus ancienne : '+at(knownDates[0]):'Aucune collecte admissible'}${model.accounts.some(a=>a.stale)?' · Collecte à actualiser':''}</p><details><summary>Couverture et exclusions</summary><ul>${model.accounts.map(a=>`<li><strong>${safe(a.name)} · ${safe(a.label)}</strong> — ${a.eligible?status(a.status):'Exclu'}${a.commission_status?' · '+safe(a.commission_status):''}${a.collected_at?' · '+at(a.collected_at):''}${a.stale?' · relevé ancien':''}${a.reason?' · '+safe(a.reason):''}</li>`).join('')}</ul><p>Les jours avant la première vente connue ou après la collecte restent inconnus. La journée en cours est provisoire. Les tendances exigent des fenêtres complètes pour tous les comptes éligibles.</p></details></div>
    ${model.total_cents==null?'<p class="aff-empty">Aucun montant admissible sur cette période. Consultez la couverture, choisissez une autre période ou <button data-aff="partners">configurez vos partenaires</button>.</p>':''}
    <div class="aff-kpis aff-overview-kpis"><article class="aff-card"><span>${safe(model.label)}${model.partial?' · partiel':''}</span><strong data-overview-total>${safe(money(model.total_cents))}</strong><small>${safe(model.description)}</small></article>${trend('previous','Vs période précédente')}${trend('year','Vs même période N-1')}</div>
    ${model.undated_cents!=null?`<p class="field-help" data-overview-undated>Dont ${safe(money(model.undated_cents))} sans ventilation quotidienne : inclus dans le total de période, absent des barres journalières.</p>`:''}<section class="panel aff-overview-chart"><div class="panel-title"><div><h2>Évolution journalière</h2><small>Une barre = somme du jour · cliquez ou utilisez Entrée / Espace pour détailler</small></div><div class="aff-overview-comparison" role="group" aria-label="Comparaison graphique">${[['none','Sans comparaison'],['previous','Période précédente'],['year','Année N-1']].map(([key,label])=>`<button data-overview-compare="${key}" aria-pressed="${comparison===key}" ${key!=='none'&&!model.comparisons[key].available?'disabled title="Aucun historique journalier comparable"':''}>${label}</button>`).join('')}</div></div><div data-overview-chart></div><p class="aff-overview-tooltip" data-overview-tooltip role="status" aria-live="polite"></p><p class="field-help" data-overview-compare-note></p><p class="field-help">Montants en EUR · zéro toujours visible · pointillés : comparaison · repère vide : journée inconnue · barre hachurée : journée partielle.</p></section>
    <div class="aff-grid aff-overview-split"><section class="panel" data-overview-day aria-live="polite"></section><section class="panel" data-overview-period><h2>Répartition sur la période</h2><p class="field-help">Du ${date(model.start)} au ${date(model.end)}${model.partial?' · Total partiel':''}</p>${distribution(model.partners,model.total_cents)}</section></div>`;
   const chart=host.querySelector('[data-overview-chart]'),tooltip=host.querySelector('[data-overview-tooltip]');
   function dayDetail(){
     const d=model.daily.find(d=>d.day===selected);
     const entries=model.partners.map(p=>{const parts=d.parts.filter(r=>r.partner_id===p.id),known=parts.filter(r=>r.cents!=null);return {...p,cents:known.length?known.reduce((n,p)=>n+p.cents,0):null,status:parts.length&&parts.every(p=>p.status==='complete')?'complete':known.length?'partial':'unavailable'}});
     host.querySelector('[data-overview-day]').innerHTML=`<h2>Détail du ${date(selected)}</h2><p class="field-help">${status(d.status)}${excluded?' sur le périmètre inclus · partenaires exclus':''}${d.provisional?' · Journée en cours, provisoire':''} · cette journée uniquement</p>${distribution(entries,d.cents)}`;
   }
   function describe(d){tooltip.textContent=`${date(d.day)} · ${money(d.cents)} · ${status(d.status)}${d.provisional?' · Journée provisoire':''}`}
   function select(day){
     selected=day;
     chart.querySelectorAll('[data-overview-date]').forEach(n=>{const active=n.dataset.overviewDate===selected;n.classList.toggle('is-selected',active);n.setAttribute('aria-pressed',String(active))});
     dayDetail();describe(model.daily.find(d=>d.day===selected));
   }
   function graph(){
     const comp=comparison==='none'?null:model.comparisons[comparison];
     const values=[...model.daily.map(d=>d.cents),...(comp?.daily.map(d=>d.cents)||[])].filter(v=>v!=null);
     const {min,max,step}=scale(values),W=Math.max(300,Math.round(chart.clientWidth)),H=300,L=85,R=18,T=18,B=42,pw=W-L-R,ph=H-T-B;
     const y=v=>T+(max-v)/(max-min)*ph,zero=y(0),span=pw/model.daily.length,labelStep=Math.max(1,Math.ceil(model.daily.length/(pw/68)));
     let markup='<defs><pattern id="aff-partial-hatch" width="5" height="5" patternUnits="userSpaceOnUse"><path d="M0 5L5 0" stroke="currentColor" stroke-opacity=".65"/></pattern></defs>';
     for(let v=min;v<=max;v+=step)markup+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" class="${v===0?'aff-zero':'aff-gridline'}"/><text x="${L-10}" y="${y(v)+4}" text-anchor="end">${safe(money(v))}</text>`;
     let path='',overlay='';const paths=[];
     comp?.daily.forEach((d,i)=>{if(d.cents==null){if(path)paths.push(path);path='';return}const x=L+(i+.5)*span;path+=(path?' L':'M')+`${x} ${y(d.cents)}`;overlay+=`<circle cx="${x}" cy="${y(d.cents)}" r="2" class="aff-comparison-dot"/>`});if(path)paths.push(path);
     for(const d of paths)overlay+=`<path d="${d}" class="aff-comparison-line"/>`;
     markup+=model.daily.map((d,i)=>{
       const x=L+(i+.5)*span,bw=Math.max(.3,Math.min(30,span*.7)),h=d.cents==null?0:Math.abs(y(d.cents)-zero),top=d.cents==null?zero:Math.min(zero,y(d.cents));
       return `<g data-overview-date="${d.day}" role="button" tabindex="0" aria-pressed="${d.day===selected}" aria-label="${date(d.day)} : ${safe(money(d.cents))}, ${status(d.status)}${d.provisional?', provisoire':''}, afficher le détail" class="aff-day ${d.day===selected?'is-selected':''}"><title>${date(d.day)} · ${safe(money(d.cents))} · ${status(d.status)}</title><rect class="aff-hit" x="${x-span/2}" y="${T}" width="${span}" height="${ph}"/><line class="aff-selection-line" x1="${x}" x2="${x}" y1="${T}" y2="${T+ph}"/>${d.cents==null?`<circle class="aff-unknown" cx="${x}" cy="${zero}" r="${Math.min(3,span*.35)}"/>`:`<rect class="aff-daily-bar" x="${x-bw/2}" y="${d.cents===0?zero-1:top}" width="${bw}" height="${d.cents===0?2:h}"/>${d.status==='partial'?`<rect x="${x-bw/2}" y="${top}" width="${bw}" height="${h}" fill="url(#aff-partial-hatch)"/>`:''}`}</g>${i%labelStep===0||i===model.daily.length-1&&i%labelStep>labelStep*.65?`<text x="${x}" y="${H-14}" text-anchor="middle">${date(d.day).slice(0,5)}</text>`:''}`;
     }).join('');
     chart.innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Commissions journalières en euros">${markup}${overlay}</svg>`;
     chart.querySelectorAll('[data-overview-date]').forEach((node,i)=>{
       node.onclick=()=>select(node.dataset.overviewDate);
       node.onfocus=node.onmouseenter=()=>describe(model.daily[i]);
       node.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();select(node.dataset.overviewDate)}else if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const n=e.key==='Home'?0:e.key==='End'?model.daily.length-1:Math.max(0,Math.min(model.daily.length-1,i+(e.key==='ArrowRight'?1:-1)));chart.querySelectorAll('[data-overview-date]')[n].focus()}};
     });
     host.querySelector('[data-overview-compare-note]').textContent=comp?(comp.available?(comp.partial?'Comparaison partielle : les journées non comparables restent des trous.':'Historique comparable · même échelle en euros.'):'Comparaison indisponible : '+comp.reason):'Comparaison masquée.';
   }
   host.querySelectorAll('[data-overview-compare]').forEach(button=>button.onclick=()=>{
     comparison=button.dataset.overviewCompare;
     host.querySelectorAll('[data-overview-compare]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));graph();
   });
   dayDetail();graph();describe(model.daily.find(d=>d.day===selected));
   let width=chart.clientWidth;
   observer=new ResizeObserver(()=>{if(Math.abs(chart.clientWidth-width)>1){width=chart.clientWidth;graph()}});observer.observe(chart);
 }
 window.LinksAffiliationOverview={render};
})();
