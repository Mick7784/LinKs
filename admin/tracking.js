/* Private tracked links and customizable publication sources.
   No public-page content is created by this module. */
(()=>{"use strict";
const get=id=>document.getElementById(id),safe=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=new Intl.NumberFormat("fr-FR");
const state={sources:[],items:[],editing:"",partners:[],editingPartner:"",reusing:""};
const close=which=>get(which)?.close();
const library=StudioCollection.create(get("tracked-list"),{empty:"Aucun lien suivi à afficher. Créez un lien ou ajustez les filtres.",renderRow(row){const template=document.createElement("template");template.innerHTML=rowHTML(row);return template.content.firstElementChild}});
function sourceOptions(prefix="",published=null){
 const available=state.sources.filter(source=>source.active);
 return [["Plateformes",source=>source.platform],["Autres sources",source=>!source.platform&&!source.historical],["Historiques",source=>source.historical]].map(([label,include])=>{
  const rows=available.filter(include);if(!rows.length)return "";
  return `<optgroup label="${label}">${rows.map(source=>`<option value="${prefix+safe(source.id)}">${safe(source.name)}${published?(published.some(row=>row.id===source.id)?" · lien existant":" · à ajouter"):""}</option>`).join("")}</optgroup>`;
 }).join("");
}
function rowHTML(item){
 const value=item.clicks;
 const usable=!item.archived&&item.enabled;
 const options=sourceOptions();
 const title=item.archived?"Archivé":!item.enabled?"Désactivé":"Actif";
 return `<article class="tracked-item${item.archived?" archived":""}" data-tracked-id="${safe(item.id)}">
 <div class="tracked-item-top"><button type="button" class="tracked-expand" data-open-statistics="shared" data-analysis-query="${safe(item.name)}" title="Voir les statistiques de ce lien"><span class="tracked-item-icon" aria-hidden="true">↗</span><span class="tracked-item-label"><strong>${safe(item.name)}</strong><small>Lien suivi · ${fmt.format(value)} clic(s) · ${title}</small></span><span class="tracked-expander" aria-hidden="true">→</span></button>
 <div class="tracked-item-actions"><label class="sr-only" for="source-${safe(item.id)}">Source de publication</label><select id="source-${safe(item.id)}" aria-label="Source pour ${safe(item.name)}" ${!usable||!options?"disabled":""}>${options||'<option>Aucune source</option>'}</select>
 <button type="button" data-tracked-action="copy" ${!usable||!options?"disabled":""} aria-label="Copier un lien permanent pour ${safe(item.name)}" title="Copier le lien permanent de cette source">⧉</button>
 <button type="button" data-tracked-action="open" title="Ouvrir la destination de ${safe(item.name)} dans un nouvel onglet">Ouvrir</button>
 <button type="button" data-tracked-action="edit" title="Modifier la destination de ${safe(item.name)}">Modifier</button>
 <button type="button" data-tracked-action="${item.archived?"restore":"archive"}" title="${item.archived?"Restaurer":"Archiver"} ce lien">${item.archived?"Restaurer":"Archiver"}</button>
 <button type="button" data-tracked-action="${item.enabled?"disable":"enable"}" title="${item.enabled?"Désactiver la redirection":"Réactiver la redirection"}">${item.enabled?"Suspendre":"Activer"}</button></div></div>
</article>`;
}
function render(){
 const status=get("tracked-status").value;
 const items=state.items.filter(row=>status==="all"||status==="current"&&!row.archived||status==="active"&&!row.archived&&row.enabled||status==="disabled"&&!row.archived&&!row.enabled||status==="archived"&&row.archived);
 library.setRows(items.map(row=>({...row,total:row.clicks,details:[row.url,row.original_url,row.notes]})),{query:get("tracked-search").value,sort:"input"});
}
const sourceLibrary=StudioCollection.create(get("tracked-source-list"),{empty:"Aucune source dans cette vue. Ajustez la recherche ou le filtre.",renderRow(row){
 const node=document.createElement("div");node.className="tracked-source-manager-row";node.dataset.sourceId=row.id;
 node.innerHTML=`
 <input value="${safe(row.name)}" aria-label="Nom de source" maxlength="100">
 <span class="tracked-source-counter">${row.platform?"Plateforme · ":row.historical?"Historique · ":""}${fmt.format(row.clicks)} clic(s) · ${row.active?"Active":"Archivée"}</span>
 <button type="button" data-source-action="rename" title="Renommer">Enregistrer</button>
 <button type="button" data-source-action="${row.active?"remove":"restore"}">${row.active?"Retirer":"Restaurer"}</button>`;return node;
}});
function renderSources(){
 const scope=get("tracked-source-scope").value;
 const rows=state.sources.filter(row=>scope==="all"||scope==="historical"&&row.historical||scope==="archived"&&!row.active||scope==="current"&&row.active&&!row.historical);
 sourceLibrary.setRows(rows.map(row=>({...row,total:row.clicks,details:[row.platform||""]})),{sort:"input",query:get("tracked-source-search").value});
}
get("tracked-source-filters").addEventListener("submit",event=>event.preventDefault());
get("tracked-source-search").addEventListener("input",renderSources);
get("tracked-source-scope").addEventListener("change",renderSources);
async function load(){
 if(!get("tracked-list"))return;
 try{
  const [links,sources]=await Promise.all([api("/api/tracked-links"),api("/api/tracking-sources")]);
  state.items=links.items;state.sources=sources.items;
  render();renderSources();if(get("tracked-reuse-dialog").open)renderReuseSources();
 }catch(error){get("tracked-list").textContent=error.message;}
}
let linkPreviewRevision=0,linkPreview=null,manualPartner=false,reapplyPartner=false,savingTracked=false;
let titlePreviewRevision=0,titlePreviewTimer=null,manualTitle=false,automaticTitle="";
function titleSuggestionFeedback(text){
 const node=get("tracked-title-suggestion-status");
 node.textContent=text;node.hidden=!text;
}
function cancelTitleSuggestion(){
 ++titlePreviewRevision;clearTimeout(titlePreviewTimer);titlePreviewTimer=null;
}
function scheduleTitleSuggestion(){
 cancelTitleSuggestion();
 const form=get("tracked-form"),input=form.elements.name,url=form.elements.url.value.trim();
 if(state.editing||manualTitle||!url){titleSuggestionFeedback("");return}
 let parsed;
 try{parsed=new URL(url)}catch{titleSuggestionFeedback("");return}
 if(!["http:","https:"].includes(parsed.protocol)||!parsed.hostname||parsed.username||parsed.password){
  titleSuggestionFeedback("");return;
 }
 // Never overwrite an independently entered title.
 if(input.value.trim()&&input.value!==automaticTitle){titleSuggestionFeedback("");return}
 const revision=titlePreviewRevision;
 titleSuggestionFeedback("Recherche d’un nom court pour cette destination…");
 titlePreviewTimer=setTimeout(async()=>{
  try{
   const result=await api("/api/tracked-links/title-preview",{method:"POST",body:JSON.stringify({url})});
   if(revision!==titlePreviewRevision||state.editing||manualTitle||!get("tracked-dialog").open
      ||form.elements.url.value.trim()!==url||input.value.trim()&&input.value!==automaticTitle)return;
   if(result.status==="ok"&&result.title){
    input.value=result.title.slice(0,input.maxLength);
    automaticTitle=input.value;
    titleSuggestionFeedback("Nom proposé automatiquement. Vous pouvez le modifier.");
   }else{
    titleSuggestionFeedback("Titre non détecté. Renseignez un nom manuellement.");
   }
  }catch(error){
   if(revision===titlePreviewRevision&&!manualTitle&&get("tracked-dialog").open)
    titleSuggestionFeedback("Titre non détecté. Renseignez un nom manuellement.");
  }
 },450);
}

function renderDuplicates(matches=[]){
 get("tracked-duplicates").hidden=!matches.length;
 get("tracked-duplicate-list").innerHTML=matches.map(row=>`<article class="tracked-item"><div class="tracked-item-label"><strong>${safe(row.name)}</strong><small>${row.archived?"Archivé":!row.enabled?"Suspendu":"Actif"}</small></div><div class="profile-image-actions"><button type="button" data-open-duplicate="${safe(row.id)}">Ouvrir sa fiche</button><button type="button" data-reuse-duplicate="${safe(row.id)}">Réutiliser ses liens courts</button></div></article>`).join("");
}
async function previewTracked(detect=false){
 const revision=++linkPreviewRevision,form=get("tracked-form"),link=get("tracked-final-link"),message=get("tracked-final-message"),button=form.querySelector('[type="submit"]');
 linkPreview=null;link.hidden=true;link.removeAttribute("href");button.disabled=true;renderDuplicates();
 if(!form.elements.url.value.trim()){message.textContent="Renseignez une URL d’origine pour afficher la destination finale.";return null}
 message.textContent="Calcul de la destination finale…";
 try{
  const result=await api("/api/tracked-links/preview",{method:"POST",body:JSON.stringify({url:form.elements.url.value,partner_id:form.elements.partner_id.value,link_id:state.editing,detect,apply_partner:reapplyPartner})});
  if(revision!==linkPreviewRevision||!get("tracked-dialog").open)return null;
  if(detect)form.elements.partner_id.value=result.partner_id;
  linkPreview=result;link.textContent=result.url;link.href=result.url;link.hidden=false;renderDuplicates(result.duplicates);
  message.textContent=state.editing&&!reapplyPartner?"Destination enregistrée conservée. Le recalcul utilise les règles actuelles et demande confirmation avant tout remplacement.":"URL réellement générée. Cliquez dessus pour la tester dans un nouvel onglet.";
  get("tracked-partner-note").textContent=detect?(result.partner_id?"Partenaire détecté automatiquement. Vous pouvez en choisir un autre ou « Aucun ».":"Aucun partenaire détecté. L’URL peut être utilisée directement."):"Vous pouvez choisir un autre partenaire ou « Aucun ».";
  button.disabled=savingTracked;return result;
 }catch(error){if(revision===linkPreviewRevision)message.textContent=error.message;return null}
}
async function openEditor(item){
 try{state.partners=(await api("/api/affiliate-partners")).items}catch(error){say(error.message,true);return}
 state.editing=item?.id||"";
 const form=get("tracked-form");form.reset();
 for(const key of ["name","url","notes"])form.elements[key].value=item?.[key]||"";
 form.elements.url.value=item?.original_url||item?.url||"";
 form.elements.partner_id.replaceChildren(new Option("Aucun",""),...state.partners.map(partner=>new Option(partner.name,partner.id)));
 form.elements.partner_id.value=item?.partner_id||"";
 cancelTitleSuggestion();manualTitle=!!item;automaticTitle="";titleSuggestionFeedback("");
 manualPartner=false;reapplyPartner=false;savingTracked=false;get("tracked-recalculate").hidden=!item;
 get("tracked-dialog-title").textContent=item?"Modifier le lien suivi":"Créer un lien suivi";
 get("tracked-dialog").showModal();previewTracked(!item);form.elements.name.focus();
}
async function copyTracked(row,sourceId){
 const selected=sourceId||document.getElementById("source-"+row.id)?.value;if(!selected){say("Ajoute d’abord une source de publication.",true);return}
 const response=await api("/api/tracked-links/"+row.id+"/token",{method:"POST",body:JSON.stringify({source_id:selected})});
 const link=response.url;
 try{await navigator.clipboard.writeText(link);say("Lien permanent copié · "+(state.sources.find(s=>s.id===selected)?.name||""))}
 catch{
   const input=document.createElement("textarea");input.value=link;input.style.position="fixed";input.style.opacity="0";document.body.append(input);input.select();let ok=false;try{ok=document.execCommand("copy")}catch{}input.remove();
   if(ok)say("Lien permanent copié");
   else window.prompt("Copier ce lien permanent",link);
 }
 return link;
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
 event.preventDefault();if(savingTracked)return;const form=event.currentTarget,button=form.querySelector('[type="submit"]');savingTracked=true;button.disabled=true;
 try{
  const preview=await previewTracked();if(!preview)return;
  if(preview.changed&&!confirm(`Remplacer la destination existante ?\n\nActuelle : ${preview.previous_url}\n\nNouvelle : ${preview.url}\n\nLes URL courtes déjà publiées utiliseront cette nouvelle destination.`))return;
  if(preview.duplicate_confirmation_required&&!confirm(`Créer exceptionnellement un doublon de destination ?\n\nDéjà utilisée par : ${preview.duplicates.map(row=>row.name).join(", ")}\n\n${preview.url}\n\nVous pouvez réutiliser leurs liens courts et sources. Continuer malgré ce doublon ?`))return;
  const fields={...Object.fromEntries(new FormData(form)),apply_partner:reapplyPartner,expected_url:preview.url,previous_url:preview.previous_url,confirm_destination:preview.changed,allow_duplicate:preview.duplicate_confirmation_required,duplicate_ids:preview.duplicates.map(row=>row.id).sort()};
  await api(state.editing?"/api/tracked-links/"+state.editing:"/api/tracked-links",{method:state.editing?"PUT":"POST",body:JSON.stringify(fields)});await load();await loadPartners();close("tracked-dialog");say("Lien suivi enregistré.")
 }catch(error){say(error.message,true);previewTracked()}finally{savingTracked=false;button.disabled=!linkPreview}
});
get("tracked-form").elements.name.addEventListener("input",()=>{
 const input=get("tracked-form").elements.name;
 manualTitle=!!input.value.trim();
 automaticTitle="";
 cancelTitleSuggestion();
 if(manualTitle)titleSuggestionFeedback("");
 else scheduleTitleSuggestion();
});
get("tracked-form").elements.url.addEventListener("input",()=>{
 if(!state.editing){
  const input=get("tracked-form").elements.name;
  if(automaticTitle&&input.value===automaticTitle&&!manualTitle){
   input.value="";automaticTitle="";
  }
  scheduleTitleSuggestion();
 }
 reapplyPartner=true;previewTracked(!manualPartner);
});
get("tracked-partner").addEventListener("change",()=>{manualPartner=true;reapplyPartner=true;previewTracked()});
get("tracked-recalculate").addEventListener("click",()=>{reapplyPartner=true;previewTracked()});
get("tracked-dialog").addEventListener("close",()=>{++linkPreviewRevision;linkPreview=null;cancelTitleSuggestion();titleSuggestionFeedback("")});
async function openDuplicate(id){
 await load();const row=state.items.find(item=>item.id===id);if(!row){say("Lien introuvable.",true);return}
 get("tracked-status").value="all";get("tracked-search").value=row.name;render();
 close("tracked-reuse-dialog");close("tracked-dialog");openEditor(row);
}
function renderReuseSources(){
 const row=state.items.find(item=>item.id===state.reusing);if(!row)return;
 const select=get("tracked-reuse-source"),selected=select.value;
 const active=state.sources.filter(source=>source.active);
 select.innerHTML=sourceOptions("",row.sources);
 if(active.some(source=>source.id===selected))select.value=selected;
 if(!active.length)select.append(new Option("Aucune source active",""));
 const usable=!row.archived&&row.enabled&&active.length>0;
 select.disabled=!usable;get("tracked-reuse-copy").disabled=!usable;
 get("tracked-reuse-copy").textContent=row.sources.some(source=>source.id===select.value)?"Copier le lien court existant":"Ajouter cette source et copier";
 get("tracked-reuse-status").textContent=row.archived?"Lien archivé : ouvrez sa fiche puis restaurez-le dans la bibliothèque pour un nouveau partage.":!row.enabled?"Lien suspendu : réactivez-le dans la bibliothèque pour un nouveau partage.":!active.length?"Ajoutez une source de publication pour partager ce lien.":"Les sources marquées « à ajouter » seront rattachées à ce même lien.";
}
async function openReuse(id){
 await load();const row=state.items.find(item=>item.id===id);if(!row){say("Lien introuvable.",true);return}
 state.reusing=id;get("tracked-reuse-heading").textContent=row.name;
 const destination=get("tracked-reuse-destination");destination.textContent=row.url;destination.href=row.url;
 get("tracked-reuse-url").hidden=true;get("tracked-reuse-url").removeAttribute("href");
 renderReuseSources();get("tracked-reuse-dialog").showModal();
}
get("tracked-duplicate-list").addEventListener("click",event=>{const open=event.target.closest("[data-open-duplicate]"),reuse=event.target.closest("[data-reuse-duplicate]");if(open)openDuplicate(open.dataset.openDuplicate);if(reuse)openReuse(reuse.dataset.reuseDuplicate)});
get("tracked-reuse-source").addEventListener("change",()=>{get("tracked-reuse-url").hidden=true;renderReuseSources()});
get("tracked-reuse-copy").addEventListener("click",async()=>{
 const button=get("tracked-reuse-copy"),row=state.items.find(item=>item.id===state.reusing);if(!row)return;
 button.disabled=true;
 try{const url=await copyTracked(row,get("tracked-reuse-source").value);if(url){const output=get("tracked-reuse-url");output.textContent=url;output.href=url;output.hidden=false}await load()}
 catch(error){say(error.message,true)}finally{renderReuseSources()}
});
get("tracked-reuse-manage").addEventListener("click",()=>{renderSources();get("tracked-sources-dialog").showModal()});
get("tracked-reuse-edit").addEventListener("click",()=>openDuplicate(state.reusing));
document.querySelectorAll("[data-close-reuse]").forEach(button=>button.addEventListener("click",()=>close("tracked-reuse-dialog")));
get("tracked-source-form").addEventListener("submit",async event=>{
 event.preventDefault();const form=event.currentTarget,button=form.querySelector('[type="submit"]');button.disabled=true;
 try{await api("/api/tracking-sources",{method:"POST",body:JSON.stringify({name:form.elements.name.value})});form.reset();get("tracked-source-scope").value="current";get("tracked-source-search").value="";await load();say("Source ajoutée.")}
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
  if(action==="remove")get("tracked-source-scope").value="all";
  await load();say(action==="rename"?"Source renommée.":action==="remove"?"Source retirée selon son historique.":"Source restaurée.");
 }catch(error){say(error.message,true)}finally{button.disabled=false}
});
get("tracked-filters").addEventListener("submit",event=>event.preventDefault());
get("tracked-search").addEventListener("input",render);
get("tracked-status").addEventListener("change",render);
document.querySelector('[data-action="new-tracked"]').addEventListener("click",()=>openEditor());
get("tracked-manage-sources").addEventListener("click",()=>{renderSources();get("tracked-sources-dialog").showModal()});
document.querySelectorAll("[data-close-tracked]").forEach(button=>button.addEventListener("click",()=>close("tracked-dialog")));
document.querySelectorAll("[data-close-sources]").forEach(button=>button.addEventListener("click",()=>close("tracked-sources-dialog")));
function campaignOptions(){
 if(!state.sources.length)return null;
 return sourceOptions("src_")+'<option value="">Autre / sans source identifiée</option>';
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
async function openEntity(type,id){
 const result=await api(type==="partner"?"/api/affiliate-partners":"/api/tracked-links"),item=result.items.find(row=>row.id===id);
 if(!item)throw Error("Cette fiche n’est plus disponible.");
 if(type==="partner")openPartner(item);else await openEditor(item);
}
window.LinksTracking={load,campaignOptions,loadPartners,openEntity,reuseEntity:openReuse};
})();
