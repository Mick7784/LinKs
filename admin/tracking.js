/* Private tracked links and customizable publication sources.
   No public-page content is created by this module. */
(()=>{"use strict";
const get=id=>document.getElementById(id),safe=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=new Intl.NumberFormat("fr-FR");
const colors=["#22d3ee","#8b5cf6","#3b82f6","#14b8a6","#a78bfa","#f59e0b","#64748b","#ec4899"];
const state={sources:[],items:[],expanded:new Set(),period:"14",editing:""};
const close=which=>get(which)?.close();
const periodDates=()=>{
 if(state.period==="all")return "";
 const end=new Intl.DateTimeFormat("en-CA",{timeZone:typeof adminTimezone==="string"?adminTimezone:"Europe/Paris",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
 const start=new Date(end+"T12:00:00Z");start.setUTCDate(start.getUTCDate()-Number(state.period)+1);
 return "?"+new URLSearchParams({start:start.toISOString().slice(0,10),end});
};
function summaryDonut(row){
 const segments=row.sources.filter(s=>(state.period==="all"?s.total:s.period)>0);
 const total=state.period==="all"?row.clicks:row.period_clicks;
 const radius=52,around=2*Math.PI*radius;let offset=0;
 const arcs=segments.map((s,i)=>{const count=state.period==="all"?s.total:s.period,portion=count/total,stroke=colors[i%colors.length],
  arc=`<circle cx="72" cy="72" r="${radius}" fill="none" stroke="${stroke}" stroke-width="19" stroke-dasharray="${(portion*around).toFixed(3)} ${around.toFixed(3)}" stroke-dashoffset="${(-offset).toFixed(3)}" transform="rotate(-90 72 72)"><title>${safe(s.name)} : ${fmt.format(count)} clics (${(portion*100).toFixed(1)} %)</title></circle>`;
  offset+=portion*around;return arc}).join("");
 const donut=`<svg viewBox="0 0 144 144" role="img" aria-label="Répartition des clics par source"><circle cx="72" cy="72" r="52" fill="none" stroke="currentColor" stroke-opacity=".1" stroke-width="19"/>${arcs}<text x="72" y="72" dy="1" fill="currentColor" font-weight="700" font-size="24" text-anchor="middle">${fmt.format(total)}</text><text x="72" y="91" fill="currentColor" fill-opacity=".6" font-size="11" text-anchor="middle">clics</text></svg>`;
 const list=segments.length?segments.map((s,i)=>{const n=state.period==="all"?s.total:s.period;return `<div class="tracked-stat-source"><span class="tracked-source-color" data-color-index="${i%colors.length}"></span><span>${safe(s.name)}</span><strong>${fmt.format(n)}</strong><small>${(n/total*100).toLocaleString("fr-FR",{maximumFractionDigits:1})} %</small></div>`}).join(""):'<p class="empty">Aucun clic sur cette période.</p>';
 return `<div class="tracked-details"><div class="tracked-donut">${donut}</div><div class="tracked-detail-copy"><p>Origine des clics · ${state.period==="all"?"Toutes périodes":state.period+" derniers jours"}</p>${list}<p class="tracked-historic">Total historique conservé : <strong>${fmt.format(row.clicks)}</strong> clic(s).</p><p class="tracked-historic">Le canal correspond à la source choisie au partage, même si le lien a ensuite été repartagé ailleurs.</p></div></div>`;
}
function rowHTML(item){
 const expanded=state.expanded.has(item.id),value=state.period==="all"?item.clicks:item.period_clicks;
 const usable=!item.archived&&item.enabled;
 const options=state.sources.filter(s=>s.active).map(s=>`<option value="${safe(s.id)}">${safe(s.name)}</option>`).join("");
 const title=item.archived?"Archivé":!item.enabled?"Désactivé":"Actif";
 return `<article class="tracked-item${item.archived?" archived":""}" data-tracked-id="${safe(item.id)}">
 <div class="tracked-item-top"><button type="button" class="tracked-expand" data-tracked-action="toggle" aria-expanded="${expanded}" aria-controls="tracked-panel-${safe(item.id)}"><span class="tracked-item-icon" aria-hidden="true">↗</span><span class="tracked-item-label"><strong>${safe(item.name)}</strong><small>${safe(item.category||"Lien suivi")} · ${fmt.format(value)} clic(s) · ${title}</small></span><span class="tracked-expander" aria-hidden="true">${expanded?"⌃":"⌄"}</span></button>
 <div class="tracked-item-actions"><label class="sr-only" for="source-${safe(item.id)}">Source de publication</label><select id="source-${safe(item.id)}" aria-label="Source pour ${safe(item.name)}" ${!usable||!options?"disabled":""}>${options||'<option>Aucune source</option>'}</select>
 <button type="button" data-tracked-action="copy" ${!usable||!options?"disabled":""} aria-label="Copier un lien permanent pour ${safe(item.name)}" title="Copier le lien permanent de cette source">⧉</button>
 <button type="button" data-tracked-action="edit" title="Modifier la destination de ${safe(item.name)}">Modifier</button>
 <button type="button" data-tracked-action="${item.archived?"restore":"archive"}" title="${item.archived?"Restaurer":"Archiver"} ce lien">${item.archived?"Restaurer":"Archiver"}</button>
 <button type="button" data-tracked-action="${item.enabled?"disable":"enable"}" title="${item.enabled?"Désactiver la redirection":"Réactiver la redirection"}">${item.enabled?"Suspendre":"Activer"}</button></div></div>
 <div id="tracked-panel-${safe(item.id)}" class="tracked-panel" ${expanded?"":"hidden"}>${expanded?summaryDonut(item):""}</div></article>`;
}
function render(){
 const archived=get("tracked-show-archived")?.checked;
 const items=state.items.filter(row=>archived||!row.archived);
 get("tracked-list").innerHTML=items.length?items.map(rowHTML).join(""):'<p class="empty">Aucun lien suivi. Créez un lien pour partager un produit sans l’afficher sur votre page publique.</p>';
}
function renderSources(){
 get("tracked-source-list").innerHTML=state.sources.map(row=>`<div class="tracked-source-manager-row" data-source-id="${safe(row.id)}">
 <input value="${safe(row.name)}" aria-label="Nom de source" maxlength="100">
 <span class="tracked-source-counter">${fmt.format(row.clicks)} clic(s) · ${row.active?"Active":"Archivée"}</span>
 <button type="button" data-source-action="rename" title="Renommer">Enregistrer</button>
 <button type="button" data-source-action="${row.active?"remove":"restore"}">${row.active?"Retirer":"Restaurer"}</button></div>`).join("")||'<p class="empty">Aucune source. Ajoutez-en une ci-dessus.</p>';
}
async function load(){
 if(!get("tracked-list"))return;
 try{
  const [links,sources]=await Promise.all([api("/api/tracked-links"+periodDates()),api("/api/tracking-sources")]);
  state.items=links.items;state.sources=sources.items;
  render();renderSources();
 }catch(error){get("tracked-list").textContent=error.message;}
}
function openEditor(item){
 state.editing=item?.id||"";
 const form=get("tracked-form");form.reset();
 for(const key of ["name","url","category","notes"])form.elements[key].value=item?.[key]||"";
 get("tracked-dialog-title").textContent=item?"Modifier le lien suivi":"Créer un lien suivi";
 get("tracked-dialog").showModal();form.elements.name.focus();
}
async function copyTracked(row){
 const select=document.getElementById("source-"+row.id);if(!select?.value){say("Ajoute d’abord une source de publication.",true);return}
 const response=await api("/api/tracked-links/"+row.id+"/token",{method:"POST",body:JSON.stringify({source_id:select.value})});
 const link=response.url;
 try{await navigator.clipboard.writeText(link);say("Lien permanent copié · "+(state.sources.find(s=>s.id===select.value)?.name||""))}
 catch{
   const input=document.createElement("textarea");input.value=link;input.style.position="fixed";input.style.opacity="0";document.body.append(input);input.select();let ok=false;try{ok=document.execCommand("copy")}catch{}input.remove();
   if(ok)say("Lien permanent copié");
   else window.prompt("Copier ce lien permanent",link);
 }
}
get("tracked-list").addEventListener("click",async event=>{
 const button=event.target.closest("button[data-tracked-action]");if(!button)return;
 const article=button.closest("[data-tracked-id]"),row=state.items.find(x=>x.id===article?.dataset.trackedId);if(!row)return;
 const action=button.dataset.trackedAction;
 if(action==="toggle"){state.expanded.has(row.id)?state.expanded.delete(row.id):state.expanded.add(row.id);render();return}
 if(action==="edit"){openEditor(row);return}
 try{
  button.disabled=true;
  if(action==="copy")return await copyTracked(row);
  if(action==="disable"&&!confirm("Suspendre la redirection ? Les liens publiés répondront temporairement comme indisponibles."))return;
  if(action==="archive"&&!confirm("Archiver ce lien ? Les URLs déjà publiées continueront de rediriger et de compter les clics."))return;
  await api("/api/tracked-links/"+row.id+"/"+action,{method:"POST",body:"{}"});
  await load();say(action==="archive"?"Lien archivé. Redirections conservées.":"Lien mis à jour.");
 }catch(error){say(error.message,true)}finally{button.disabled=false}
});
get("tracked-form").addEventListener("submit",async event=>{
 event.preventDefault();const form=event.currentTarget,button=form.querySelector('[type="submit"]');button.disabled=true;
 const fields=Object.fromEntries(new FormData(form));
 try{await api(state.editing?"/api/tracked-links/"+state.editing:"/api/tracked-links",{method:state.editing?"PUT":"POST",body:JSON.stringify(fields)});close("tracked-dialog");await load();say("Lien suivi enregistré.")}
 catch(error){say(error.message,true)}finally{button.disabled=false}
});
get("tracked-source-form").addEventListener("submit",async event=>{
 event.preventDefault();const form=event.currentTarget,button=form.querySelector('[type="submit"]');button.disabled=true;
 try{await api("/api/tracking-sources",{method:"POST",body:JSON.stringify({name:form.elements.name.value})});form.reset();await load();say("Source ajoutée.")}
 catch(error){say(error.message,true)}finally{button.disabled=false}
});
get("tracked-source-list").addEventListener("click",async event=>{
 const button=event.target.closest("button[data-source-action]");if(!button)return;
 const holder=button.closest("[data-source-id]"),row=state.sources.find(s=>s.id===holder?.dataset.sourceId);if(!row)return;
 const action=button.dataset.sourceAction;
 if(action==="remove"){
  const text=row.clicks?"Cette source possède "+row.clicks+" clic(s). Elle sera archivée, ses liens resteront actifs.":"Une source déjà utilisée pour un partage sera archivée, même sans clic. Seule une source jamais publiée peut être supprimée.";
  if(!confirm(text+" Continuer ?"))return;
 }
 try{
  button.disabled=true;
  if(action==="rename"){await api("/api/tracking-sources/"+row.id,{method:"PUT",body:JSON.stringify({name:holder.querySelector("input").value})})}
  else if(action==="remove"){await api("/api/tracking-sources/"+row.id,{method:"DELETE"})}
  else{await api("/api/tracking-sources/"+row.id+"/restore",{method:"POST",body:"{}"})}
  await load();say(action==="rename"?"Source renommée.":action==="remove"?"Source retirée selon son historique.":"Source restaurée.");
 }catch(error){say(error.message,true)}finally{button.disabled=false}
});
get("tracked-show-archived").addEventListener("change",render);
get("tracked-period").addEventListener("change",event=>{state.period=event.target.value;load()});
document.querySelector('[data-action="new-tracked"]').addEventListener("click",()=>openEditor());
get("tracked-manage-sources").addEventListener("click",()=>{renderSources();get("tracked-sources-dialog").showModal()});
document.querySelectorAll("[data-close-tracked]").forEach(button=>button.addEventListener("click",()=>close("tracked-dialog")));
document.querySelectorAll("[data-close-sources]").forEach(button=>button.addEventListener("click",()=>close("tracked-sources-dialog")));
function campaignOptions(){
 if(!state.sources.length)return null;
 const preferred=["Instagram Story","YouTube Post","Facebook","TikTok"];
 const available=state.sources.filter(source=>source.active).sort((a,b)=>{
   const ai=preferred.indexOf(a.name),bi=preferred.indexOf(b.name);
   return (ai===-1?100:ai)-(bi===-1?100:bi)||a.name.localeCompare(b.name,"fr");
 });
 return available.map(source=>`<option value="${"src_"+source.id}">${safe(source.name)}</option>`).join("")+'<option value="">Autre / sans source identifiée</option>';
}
window.LinksTracking={load,campaignOptions};
})();
