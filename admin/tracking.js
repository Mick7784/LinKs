/* Private tracked links and customizable publication sources.
   No public-page content is created by this module. */
(()=>{"use strict";
const get=id=>document.getElementById(id),safe=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=new Intl.NumberFormat("fr-FR");
const state={sources:[],items:[],editing:"",partners:[],editingPartner:""};
const close=which=>get(which)?.close();
const library=StudioCollection.create(get("tracked-list"),{empty:"Aucun lien suivi à afficher. Créez un lien ou ajustez les filtres.",renderRow(row){const template=document.createElement("template");template.innerHTML=rowHTML(row);return template.content.firstElementChild}});
function rowHTML(item){
 const value=item.clicks;
 const usable=!item.archived&&item.enabled;
 const options=state.sources.filter(s=>s.active).map(s=>`<option value="${safe(s.id)}">${safe(s.name)}</option>`).join("");
 const title=item.archived?"Archivé":!item.enabled?"Désactivé":"Actif";
 return `<article class="tracked-item${item.archived?" archived":""}" data-tracked-id="${safe(item.id)}">
 <div class="tracked-item-top"><button type="button" class="tracked-expand" data-open-statistics="shared" data-analysis-query="${safe(item.name)}" title="Voir les statistiques de ce lien"><span class="tracked-item-icon" aria-hidden="true">↗</span><span class="tracked-item-label"><strong>${safe(item.name)}</strong><small>${safe(item.category||"Lien suivi")} · ${fmt.format(value)} clic(s) · ${title}</small></span><span class="tracked-expander" aria-hidden="true">→</span></button>
 <div class="tracked-item-actions"><label class="sr-only" for="source-${safe(item.id)}">Source de publication</label><select id="source-${safe(item.id)}" aria-label="Source pour ${safe(item.name)}" ${!usable||!options?"disabled":""}>${options||'<option>Aucune source</option>'}</select>
 <button type="button" data-tracked-action="copy" ${!usable||!options?"disabled":""} aria-label="Copier un lien permanent pour ${safe(item.name)}" title="Copier le lien permanent de cette source">⧉</button>
 <button type="button" data-tracked-action="open" title="Ouvrir la destination de ${safe(item.name)} dans un nouvel onglet">Ouvrir</button>
 <button type="button" data-tracked-action="edit" title="Modifier la destination de ${safe(item.name)}">Modifier</button>
 <button type="button" data-tracked-action="${item.archived?"restore":"archive"}" title="${item.archived?"Restaurer":"Archiver"} ce lien">${item.archived?"Restaurer":"Archiver"}</button>
 <button type="button" data-tracked-action="${item.enabled?"disable":"enable"}" title="${item.enabled?"Désactiver la redirection":"Réactiver la redirection"}">${item.enabled?"Suspendre":"Activer"}</button></div></div>
</article>`;
}
function render(){
 const status=get("tracked-status").value,category=get("tracked-category").value;
 const items=state.items.filter(row=>(status==="all"||status==="current"&&!row.archived||status==="active"&&!row.archived&&row.enabled||status==="disabled"&&!row.archived&&!row.enabled||status==="archived"&&row.archived)&&(!category||row.category===category));
 library.setRows(items.map(row=>({...row,total:row.clicks,details:[row.url,row.category,row.notes]})),{query:get("tracked-search").value,sort:"input"});
}
function renderCategories(){
 const select=get("tracked-category"),selected=select.value;
 select.replaceChildren(new Option("Toutes les catégories",""),...[...new Set(state.items.map(row=>row.category).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"fr")).map(value=>new Option(value,value)));
 select.value=[...select.options].some(option=>option.value===selected)?selected:"";
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
  const [links,sources]=await Promise.all([api("/api/tracked-links"),api("/api/tracking-sources")]);
  state.items=links.items;state.sources=sources.items;
  renderCategories();render();renderSources();
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
 if(action==="edit"){openEditor(row);return}
 if(action==="open"){if(["http:","https:"].includes(new URL(row.url).protocol))window.open(row.url,"_blank","noopener,noreferrer");return}
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
 try{await api(state.editing?"/api/tracked-links/"+state.editing:"/api/tracked-links",{method:state.editing?"PUT":"POST",body:JSON.stringify(fields)});await load();close("tracked-dialog");say("Lien suivi enregistré.")}
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
get("tracked-filters").addEventListener("submit",event=>event.preventDefault());
get("tracked-search").addEventListener("input",render);
get("tracked-status").addEventListener("change",render);
get("tracked-category").addEventListener("change",render);
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
const partnerLibrary=StudioCollection.create(get("partner-list"),{empty:"Aucun partenaire configuré. Les liens affiliés directs restent utilisables.",renderRow(row){
 const article=document.createElement("article");article.className="tracked-item";article.dataset.partnerId=row.id;
 article.innerHTML=`<div class="tracked-item-top"><div class="tracked-item-label"><strong>${safe(row.name)}</strong><small>Code : ${safe(row.code||"Non renseigné")} · ${safe(row.domains.join(", ")||"Aucun domaine")}</small><small>${safe(row.template)}</small></div><div class="tracked-item-actions"><button type="button" data-partner-action="edit">Modifier</button><button type="button" data-partner-action="delete" ${row.links?'disabled title="Ce partenaire est associé à des liens"':''}>Supprimer</button></div></div>`;
 return article;
}});
async function loadPartners(){
 try{const result=await api("/api/affiliate-partners");state.partners=result.items;partnerLibrary.setRows(state.partners.map(row=>({...row,total:0})),{sort:"name"})}
 catch(error){get("partner-list").textContent=error.message}
}
let previewRevision=0,previewTimer;
function previewPartner(){
 const revision=++previewRevision;clearTimeout(previewTimer);
 const link=get("partner-preview-link"),output=get("partner-preview"),form=get("partner-form");
 link.hidden=true;link.removeAttribute("href");
 const fields=Object.fromEntries(new FormData(form));
 if(!fields.name.trim()||!fields.template.trim()||!fields.test_url.trim()){output.textContent="Renseignez le nom, le modèle et une URL de test pour afficher l’aperçu.";return}
 output.textContent="Préparation de l’aperçu…";
 previewTimer=setTimeout(async()=>{
  try{const result=await api("/api/affiliate-partners/preview",{method:"POST",body:JSON.stringify(fields)});if(revision!==previewRevision)return;output.textContent=result.url;link.href=result.url;link.hidden=false}
  catch(error){if(revision===previewRevision)output.textContent=error.message}
 },180);
}
function openPartner(partner){
 state.editingPartner=partner?.id||"";const form=get("partner-form");form.reset();
 for(const key of ["name","code","template"])form.elements[key].value=partner?.[key]||(key==="template"?"{url}?ref={code}":"");
 form.elements.domains.value=(partner?.domains||[]).join("\n");
 form.elements.test_url.value=partner?.domains?.length?"https://"+partner.domains[0]+"/":"https://example.com/produit";
 get("partner-dialog-title").textContent=partner?"Modifier le partenaire":"Ajouter un partenaire";
 get("partner-dialog").showModal();previewPartner();form.elements.name.focus();
}
get("partner-add").addEventListener("click",()=>openPartner());
get("partner-form").addEventListener("input",previewPartner);
get("partner-form").addEventListener("submit",async event=>{
 event.preventDefault();const form=event.currentTarget,button=form.querySelector('[type="submit"]');button.disabled=true;
 try{await api("/api/affiliate-partners"+(state.editingPartner?"/"+state.editingPartner:""),{method:state.editingPartner?"PUT":"POST",body:JSON.stringify(Object.fromEntries(new FormData(form)))});await loadPartners();close("partner-dialog");say("Partenaire enregistré.")}
 catch(error){say(error.message,true)}finally{button.disabled=false}
});
get("partner-list").addEventListener("click",async event=>{
 const button=event.target.closest("[data-partner-action]");if(!button)return;
 const row=state.partners.find(partner=>partner.id===button.closest("[data-partner-id]")?.dataset.partnerId);if(!row)return;
 if(button.dataset.partnerAction==="edit"){openPartner(row);return}
 if(!confirm(`Supprimer le partenaire « ${row.name} » ?`))return;
 button.disabled=true;
 try{await api("/api/affiliate-partners/"+row.id,{method:"DELETE"});await loadPartners();say("Partenaire supprimé.")}
 catch(error){say(error.message,true)}finally{button.disabled=false}
});
get("partner-dialog").addEventListener("close",()=>{++previewRevision;clearTimeout(previewTimer)});
document.querySelectorAll("[data-close-partner]").forEach(button=>button.addEventListener("click",()=>close("partner-dialog")));
window.LinksTracking={load,campaignOptions,loadPartners};
})();
