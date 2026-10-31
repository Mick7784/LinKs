/* Bulk title review for existing tracked links; never changes their destinations. */
(()=>{"use strict";
const $=id=>document.getElementById(id);
const dialog=$("tracked-titles-dialog"),list=$("tracked-titles-list"),progress=$("tracked-titles-progress");
const chooseAll=$("tracked-titles-select-all"),save=$("tracked-titles-save"),count=$("tracked-titles-count");
if(!dialog||!list||!chooseAll||!save)return;
let session=0,controller=null,rows=[],working=false,next=0,done=0;
const nodes=new Map();
function element(tag,className,text){
 const node=document.createElement(tag);
 if(className)node.className=className;
 if(text!==undefined)node.textContent=text;
 return node;
}
function currentChanges(){
 return rows.filter(row=>row.selected&&row.proposed.trim()&&row.proposed.trim()!==row.original);
}
function selectable(){
 return rows.filter(row=>row.status!=="pending"&&row.proposed.trim()&&row.proposed.trim()!==row.original);
}
function updateControls(){
 const eligible=selectable(),selected=currentChanges();
 count.textContent=selected.length+" titre"+(selected.length>1?"s":"")+" sélectionné"+(selected.length>1?"s":"")+" sur "+rows.length;
 chooseAll.disabled=working||!eligible.length||done<rows.length;
 chooseAll.textContent=eligible.length>0&&selected.length===eligible.length?"Tout désélectionner":"Sélectionner tout";
 save.disabled=working||done<rows.length||!selected.length;
 if(working)return;
 if(!rows.length)progress.textContent="Aucun lien non archivé à analyser.";
 else if(done<rows.length)progress.textContent="Analyse des destinations : "+done+" / "+rows.length;
 else {
  const proposed=rows.filter(row=>row.status==="generated"&&row.proposed.trim()!==row.original).length;
  const retained=rows.filter(row=>row.status==="unchanged"||row.status==="retained").length;
  const unavailable=rows.filter(row=>row.status==="unavailable").length;
  progress.textContent="Analyse terminée · "+proposed+" amélioration"+(proposed>1?"s":"")+
    (retained?" · "+retained+" titre"+(retained>1?"s":"")+" conservé"+(retained>1?"s":""):"")+
    (unavailable?" · "+unavailable+" analyse"+(unavailable>1?"s":"")+" incomplète"+(unavailable>1?"s":""):"")+".";
 }
}
function renderRows(){
 nodes.clear();
 list.replaceChildren();
 const fragment=document.createDocumentFragment();
 for(const row of rows){
  const outer=element("div","tracked-bulk-title-row");
  outer.dataset.id=row.id;
  const left=element("div","tracked-bulk-title-original");
  const label=element("label","tracked-bulk-title-choice");
  const check=document.createElement("input");
  check.type="checkbox";check.disabled=true;check.checked=false;
  check.setAttribute("aria-label","Sélectionner "+row.original);
  label.append(check,element("strong","",row.original));
  left.append(label,element("small","tracked-bulk-title-url",row.url));
  const right=element("div","tracked-bulk-title-result");
  const heading=element("label","tracked-bulk-title-new-label","Titre proposé");
  const input=document.createElement("input");
  input.type="text";input.maxLength=160;input.value=row.original;input.disabled=true;
  input.setAttribute("aria-label","Nouveau titre pour "+row.original);
  heading.append(input);
  const status=element("small","tracked-bulk-title-status","Analyse en cours…");
  const diagnostic=element("details","tracked-bulk-title-diagnostic");diagnostic.hidden=true;
  const diagnosticText=element("small","tracked-bulk-title-status");
  diagnostic.append(element("summary","","Diagnostic"),diagnosticText);
  right.append(heading,status,diagnostic);
  outer.append(left,right);fragment.append(outer);
  nodes.set(row.id,{input,check,status,diagnostic,diagnosticText});
  check.addEventListener("change",()=>{
   row.selected=check.checked&&!!row.proposed.trim()&&row.proposed.trim()!==row.original;
   check.checked=row.selected;updateControls();
  });
  input.addEventListener("input",()=>{
   row.proposed=input.value;
   row.status=input.value.trim()===row.original?"unchanged":"manual";
   status.textContent=row.status==="manual"?"Modification manuelle. Sélectionnez ce titre pour le valider.":"Titre actuel conservé.";
   if(!input.value.trim()||input.value.trim()===row.original)row.selected=false;
   check.disabled=!input.value.trim()||input.value.trim()===row.original;
   check.checked=row.selected;
   updateControls();
  });
 }
 list.append(fragment);
 updateControls();
}
function reasonLabel(reason){
 if(/^http_\d{3}$/.test(reason||""))return "Réponse HTTP "+reason.slice(5)+".";
 return ({dns_error:"Résolution DNS impossible.",dns_timeout:"Délai DNS dépassé.",dns_busy:"Résolution DNS occupée.",
  network_timeout:"La destination a dépassé le délai réseau.",network_error:"Connexion à la destination impossible.",
  deadline_exceeded:"Délai global de récupération dépassé.",tls_error:"Connexion sécurisée impossible.",
  blocked_destination:"Destination refusée par les protections réseau.",invalid_url:"URL invalide.",
  redirect_loop:"Boucle de redirection.",redirect_limit:"Trop de redirections.",redirect_missing:"Redirection sans destination.",redirect_invalid:"Redirection invalide.",
  unsupported_encoding:"Compression non prise en charge.",invalid_compression:"Réponse compressée invalide.",
  http_protocol_error:"Réponse HTTP invalide.",unsupported_content:"La réponse n’est pas une page HTML.",
  invalid_html:"HTML inexploitable.",invalid_jsonld:"Données structurées invalides.",
  metadata_missing:"Aucune métadonnée exploitable dans la portion lue.",generic_metadata:"Métadonnées trop génériques.",
  conflicting_metadata:"Informations contradictoires.",blocked_page:"Page de vérification ou de blocage.",
  score_too_low:"Indices insuffisants pour proposer un changement.",url_fallback:"Proposition issue de l’URL descriptive.",
  url_matches_current:"URL cohérente avec le titre ; métadonnées non confirmées.",platform_title_preserved:"Nom de la destination conservé.",
  preview_failed:"La prévisualisation n’a pas abouti."})[reason]||"";
}
function showResult(row){
 const node=nodes.get(row.id);if(!node)return;
 node.input.value=row.proposed;
 node.input.disabled=false;
 node.check.disabled=!row.proposed.trim()||row.proposed.trim()===row.original;
 node.check.checked=false;
 const reliability={high:"élevée",medium:"moyenne",low:"faible"}[row.confidence];
 node.status.textContent=(row.status==="generated"?"Amélioration proposée. Modifiable avant validation.":
  row.status==="unchanged"?"Titre déjà pertinent, conservé.":
  row.status==="retained"?"Aucun gain certain : titre actuel conservé.":
  "Analyse incomplète : titre actuel conservé.")+
  (reasonLabel(row.reason)?" "+reasonLabel(row.reason):"")+
  (reliability&&row.status!=="unavailable"?" Fiabilité "+reliability+".":"");
 if(row.diagnostics){
  const fetch=row.diagnostics.fetch||{},extraction=row.diagnostics.extraction||{};
  const parts=[/^http_/.test(fetch.code||"")?"":reasonLabel(fetch.code),Number.isInteger(fetch.http_status)?"HTTP "+fetch.http_status:"",
   Number.isInteger(fetch.redirects)?fetch.redirects+" redirection(s)":"",
   fetch.truncated?"Lecture limitée à 256 Ko":"",
   Number.isInteger(extraction.candidates)?extraction.candidates+" candidat(s)":"Extraction non effectuée",
   row.engine?.id&&/^[a-z0-9-]+$/.test(row.engine.id)?"Moteur "+row.engine.id:"",
   /^[a-f0-9]{12}$/.test(row.engine?.fingerprint||"")?row.engine.fingerprint:""].filter(Boolean);
  node.diagnosticText.textContent=parts.join(" · ");node.diagnostic.hidden=false;
 }
}
async function inspectAll(mySession){
 let position=0;
 const worker=async()=>{
  while(mySession===session&&controller&&!controller.signal.aborted){
   const index=position++;if(index>=rows.length)break;
   const row=rows[index];
   try{
    const result=await api("/api/tracked-links/title-preview",{
     method:"POST",body:JSON.stringify({url:row.url,current_title:row.original}),signal:controller.signal
    });
    if(mySession!==session||controller.signal.aborted)return;
    const title=result.status==="ok"&&typeof result.title==="string"?result.title.trim():"";
    row.proposed=title||row.original;
    row.status=["unchanged","retained","unavailable"].includes(result.status)?result.status:
      !title?"unavailable":title===row.original?"unchanged":"generated";
    row.confidence=result.confidence;row.reason=result.reason;row.diagnostics=result.diagnostics;row.engine=result.engine;
   }catch(error){
    if(mySession!==session||controller.signal.aborted)return;
    row.proposed=row.original;row.status="unavailable";row.reason="preview_failed";
   }
   done++;showResult(row);updateControls();
  }
 };
 await Promise.all(Array.from({length:Math.min(3,rows.length)},()=>worker()));
 if(mySession===session){controller=null;updateControls();}
}
async function open(){
 const button=$("tracked-generate-titles");
 button.disabled=true;
 try{
  const response=await api("/api/tracked-links");
  rows=response.items.filter(row=>!row.archived).map(row=>({
   id:row.id,original:row.name,url:row.original_url||row.url,
   expectedUpdatedAt:row.updated_at,proposed:row.name,status:"pending",selected:false
  }));
  done=0;next=0;working=false;
  const mySession=++session;
  if(controller)controller.abort();
  controller=new AbortController();
  renderRows();dialog.showModal();
  if(rows.length)await inspectAll(mySession);
 }catch(error){say(error.message,true)}
 finally{button.disabled=false;}
}
chooseAll.addEventListener("click",()=>{
 const eligible=selectable(),allSelected=eligible.every(row=>row.selected);
 for(const row of eligible){
  row.selected=!allSelected;
  const node=nodes.get(row.id);if(node)node.check.checked=row.selected;
 }
 updateControls();
});
save.addEventListener("click",async()=>{
 if(working||done!==rows.length)return;
 const selected=currentChanges();if(!selected.length)return;
 working=true;updateControls();
 try{
  const result=await api("/api/tracked-links/titles/bulk-update",{
   method:"POST",body:JSON.stringify({items:selected.map(row=>({
    id:row.id,name:row.proposed.trim(),expected_name:row.original,
    expected_updated_at:row.expectedUpdatedAt
   }))})
  });
  dialog.close();
  await window.LinksTracking.load();
  say(result.updated+" titre"+(result.updated>1?"s":"")+" mis à jour.");
 }catch(error){
  say(error.message,true);
 }finally{working=false;updateControls();}
});
document.querySelectorAll("[data-close-titles]").forEach(button=>button.addEventListener("click",()=>dialog.close()));
dialog.addEventListener("close",()=>{
 ++session;if(controller)controller.abort();controller=null;nodes.clear();rows=[];
});
$("tracked-generate-titles").addEventListener("click",open);
})();
