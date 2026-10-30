/* Batch creation of tracked links. Publication platforms are intentionally absent. */
(()=>{"use strict";
const $=id=>document.getElementById(id);
const dialog=$("tracked-batch-dialog"),input=$("tracked-batch-urls"),list=$("tracked-batch-list");
const analyzeButton=$("tracked-batch-analyze"),selectAll=$("tracked-batch-select-all");
const createButton=$("tracked-batch-create"),counter=$("tracked-batch-count"),progress=$("tracked-batch-progress");
const openButton=$("tracked-open-batch");
if(!dialog||!list||!openButton)return;

let rows=[],partners=[],revision=0,controller=null,busy=false,done=0,expected=0,previewReady=false;
const items=new Map();
const elem=(tag,classname="",value)=>{
 const el=document.createElement(tag);
 if(classname)el.className=classname;
 if(value!==undefined)el.textContent=value;
 return el;
};
const canCreate=row=>!row.error&&!row.duplicates?.length&&row.duplicate_of==null;
const usable=row=>canCreate(row)&&!!row.title.trim()&&row.title_status!=="pending";
const selected=()=>rows.filter(row=>row.selected&&usable(row));
function update(){
 const available=rows.filter(usable),chosen=selected();
 counter.textContent=chosen.length+" lien"+(chosen.length>1?"s":"")+" sélectionné"+(chosen.length>1?"s":"")+" sur "+rows.length;
 const all=available.length>0&&chosen.length===available.length;
 selectAll.textContent=all?"Tout désélectionner":"Sélectionner tout";
 selectAll.disabled=!previewReady||busy||done<expected||!available.length;
 createButton.disabled=!previewReady||busy||done<expected||!chosen.length;
 if(!previewReady)return;
 if(busy)return;
 if(done<expected)progress.textContent="Récupération des titres : "+done+" / "+expected;
 else if(rows.length){
  const ready=rows.filter(usable).length;
  const existing=rows.filter(row=>row.duplicates?.length).length;
  const repeated=rows.filter(row=>row.duplicate_of!=null).length;
  const errors=rows.filter(row=>row.error).length;
  progress.textContent=ready+" prêt"+(ready>1?"s":"")+" à créer"+
   (existing?" · "+existing+" déjà suivi"+(existing>1?"s":""):"")+
   (repeated?" · "+repeated+" répétition"+(repeated>1?"s":"")+" dans le lot":"")+
   (errors?" · "+errors+" erreur"+(errors>1?"s":""):"")+".";
 }else progress.textContent="";
}
function render(){
 list.replaceChildren();items.clear();
 const fragment=document.createDocumentFragment();
 for(const row of rows){
  const box=elem("div","tracked-batch-row");
  box.dataset.index=String(row.index);
  const head=elem("div","tracked-batch-row-head");
  const label=elem("label","tracked-batch-row-check");
  const checkbox=document.createElement("input");
  checkbox.type="checkbox";checkbox.checked=row.selected&&usable(row);
  checkbox.disabled=!usable(row);
  checkbox.setAttribute("aria-label","Créer le lien "+(row.index+1));
  label.append(checkbox,elem("strong","",String(row.index+1)+". "+row.url));
  head.append(label);
  const fields=elem("div","tracked-batch-fields");
  const nameLabel=elem("label","","Nom du lien");
  const name=document.createElement("input");
  name.type="text";name.maxLength=160;name.value=row.title;
  name.placeholder="Nom court et explicite";name.disabled=!!row.error;
  name.setAttribute("aria-label","Titre du lien "+(row.index+1));
  nameLabel.append(name);
  const partnerLabel=elem("label","","Partenaire");
  const partner=document.createElement("select");
  // An ambiguous/invalid affiliate rule must remain correctable in this row.
  const autoName=partners.find(p=>p.id===row.partner_id)?.name||"Aucun";
  partner.append(new Option("Automatique · "+autoName,"__auto__"),new Option("Aucun",""));
  for(const item of partners)partner.append(new Option(item.name,item.id));
  partner.value=row.manual_partner?row.chosen_partner_id:"__auto__";
  partner.setAttribute("aria-label","Partenaire du lien "+(row.index+1));
  partnerLabel.append(partner);
  fields.append(nameLabel,partnerLabel);
  const destination=elem("small","tracked-batch-destination",row.final_url||"");
  const feedback=elem("small","tracked-batch-row-status");
  const foot=elem("div","tracked-batch-row-foot");
  foot.append(destination,feedback);
  box.append(head,fields,foot);
  fragment.append(box);
  items.set(row.index,{box,checkbox,name,partner,destination,feedback});
  checkbox.addEventListener("change",()=>{
   row.selected=checkbox.checked&&usable(row);checkbox.checked=row.selected;update();
  });
  name.addEventListener("input",()=>{
   row.title=name.value;row.manual_title=true;row.title_status="complete";
   if(!name.value.trim())row.selected=false;
   showRow(row);
   update();
  });
  partner.addEventListener("change",()=>{
   row.manual_partner=partner.value!=="__auto__";
   row.chosen_partner_id=partner.value==="__auto__"?"":partner.value;
   inspect(true);
  });
  showRow(row);
 }
 list.append(fragment);update();
}
function showRow(row){
 const node=items.get(row.index);if(!node)return;
 node.name.value=row.title;
 node.checkbox.disabled=!usable(row);
 node.checkbox.checked=row.selected&&usable(row);
 node.destination.textContent=row.final_url||"";
 node.partner.firstChild.textContent="Automatique · "+(partners.find(p=>p.id===row.partner_id)?.name||"Aucun");
 node.feedback.textContent=row.error?"Erreur : "+row.error:
  row.duplicates?.length?"Déjà suivi : "+row.duplicates.map(item=>item.name).join(", ")+" — aucun doublon créé.":
  row.duplicate_of!=null?"Doublon de la ligne "+(row.duplicate_of+1)+" — ignoré.":
  row.title_status==="pending"?"Recherche du titre…":
  !row.title.trim()?"Titre indisponible : renseignez un nom manuellement.":
  "Prêt à créer. La destination affiliée reste modifiable via le partenaire.";
}
async function fetchTitles(myRevision,signal){
 let next=0;
 const pending=rows.filter(row=>canCreate(row)&&row.title_status==="pending");
 expected=pending.length;done=0;update();
 const worker=async()=>{
  while(myRevision===revision&&!signal.aborted){
   const row=pending[next++];
   if(!row)break;
   try{
    const data=await api("/api/tracked-links/title-preview",{
     method:"POST",signal,body:JSON.stringify({url:row.url})
    });
    if(myRevision!==revision||signal.aborted)return;
    if(!row.manual_title&&data.status==="ok"&&typeof data.title==="string")
     row.title=data.title.slice(0,160).trim();
   }catch(error){
    if(myRevision!==revision||signal.aborted)return;
   }
   if(myRevision!==revision||signal.aborted)return;
   row.title_status="complete";
   done++;
   showRow(row);update();
  }
 };
 await Promise.all(Array.from({length:Math.min(3,pending.length)},()=>worker()));
 if(myRevision===revision&&!signal.aborted){busy=false;update();}
}
async function inspect(preserve=false){
 previewReady=false;update();
 const urls=input.value.split(/\r?\n/).map(line=>line.trim()).filter(Boolean);
 if(!urls.length){say("Ajoutez au moins une URL.",true);return}
 if(urls.length>50){say("50 URL maximum par lot.",true);return}
 const previous=preserve?rows.slice():[];
 ++revision;const myRevision=revision;
 if(controller)controller.abort();
 controller=new AbortController();
 busy=true;expected=0;done=0;
 analyzeButton.disabled=true;createButton.disabled=true;selectAll.disabled=true;
 progress.textContent="Analyse des partenaires et des doublons…";
 try{
  const result=await api("/api/tracked-links/batch/preview",{
   method:"POST",signal:controller.signal,
   body:JSON.stringify({items:urls.map((url,index)=>{
    const old=previous[index]?.url===url?previous[index]:null;
    return {url,manual_partner:old?.manual_partner||false,
     partner_id:old?.manual_partner?old.chosen_partner_id:""};
   })})
  });
  if(myRevision!==revision||controller.signal.aborted)return;
  rows=result.items.map((item,index)=>{
   const old=previous[index]?.url===urls[index]?previous[index]:null;
   return {
    ...item,index,url:urls[index],
    manual_partner:old?.manual_partner||false,
    chosen_partner_id:old?.chosen_partner_id||"",
    title:old?.title||"",manual_title:old?.manual_title||false,
    title_status:old?.title_status==="complete"&&(!old.error||old.manual_title)?"complete":item.error?"complete":"pending",
    selected:old?old.selected:true
   };
  });
  previewReady=true;render();
  // The title endpoint is called only for new rows needing a suggestion.
  await fetchTitles(myRevision,controller.signal);
 }catch(error){
  if(myRevision===revision&&!controller.signal.aborted){
   progress.textContent="Analyse impossible : "+error.message;
   say(error.message,true);
   busy=false;update();
  }
 }finally{
  if(myRevision===revision)analyzeButton.disabled=false;
 }
}
async function open(){
 openButton.disabled=true;
 try{
  const result=await api("/api/affiliate-partners");
  partners=result.items;
  rows=[];done=0;expected=0;busy=false;previewReady=false;
  list.replaceChildren();progress.textContent="";
  input.value="";
  dialog.showModal();input.focus();
  update();
 }catch(error){say(error.message,true)}
 finally{openButton.disabled=false}
}
selectAll.addEventListener("click",()=>{
 const available=rows.filter(usable),all=available.every(row=>row.selected);
 for(const row of available){
  row.selected=!all;
  const node=items.get(row.index);if(node)node.checkbox.checked=row.selected;
 }
 update();
});
analyzeButton.addEventListener("click",()=>inspect(true));
input.addEventListener("input",()=>{
 ++revision;if(controller)controller.abort();
 busy=false;previewReady=false;analyzeButton.disabled=false;
 progress.textContent="Analysez les URL modifiées avant de créer les liens.";update();
});
createButton.addEventListener("click",async()=>{
 if(!previewReady||busy||done<expected)return;
 const chosen=selected();
 if(!chosen.length)return;
 busy=true;update();createButton.disabled=true;
 progress.textContent="Création des liens sélectionnés…";
 try{
  const data=await api("/api/tracked-links/batch/create",{
   method:"POST",
   body:JSON.stringify({items:chosen.map(row=>({
    url:row.url,name:row.title.trim(),partner_id:row.partner_id,
    expected_url:row.final_url
   }))})
  });
  dialog.close();
  await window.LinksTracking.load();
  say(data.created+" lien"+(data.created>1?"s":"")+" suivi"+(data.created>1?"s":"")+" créé"+(data.created>1?"s":"")+".");
 }catch(error){
  progress.textContent="Aucun lien du lot sélectionné créé. "+error.message;
  say(error.message,true);
 }finally{busy=false;update();}
});
document.querySelectorAll("[data-close-batch]").forEach(button=>button.addEventListener("click",()=>dialog.close()));
dialog.addEventListener("close",()=>{
 ++revision;if(controller)controller.abort();controller=null;
 rows=[];items.clear();expected=0;done=0;busy=false;
});
openButton.addEventListener("click",open);
})();
