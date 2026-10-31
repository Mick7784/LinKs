"use strict";
window.LinksDescriptions=(()=>{
 const root=document.getElementById('descriptions'),clone=value=>structuredClone(value);
 let templates=[],drafts=[],catalogue={items:[],partners:[]},model=null,dirty=false,loaded=false,busy=false,tab='templates',editRevision=0;
 const openItems=new Set(['support']);
 const node=(tag,text,className)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el};
 const request=(path,data)=>api('/api/descriptions/'+path,data===undefined?{}:{method:'POST',body:JSON.stringify(data)});
 function message(text,error=false){const target=root.querySelector('[data-description-status]');if(target){target.textContent=text;target.classList.toggle('error',error)}}
 function button(label,action,className){const el=node('button',label,className);el.type='button';el.addEventListener('click',()=>run(action));return el}
 async function run(action){if(busy)return;try{await action()}catch(error){message(error.message,true)}}
 function changed(){editRevision++;dirty=true;const status=root.querySelector('[data-description-status]');if(status)status.textContent='Modifications du modèle non enregistrées';const save=root.querySelector('[data-save-template]');if(save)save.disabled=false}
 function field(label,object,key,type='text'){
  const wrap=node('label'),title=node('span',label),input=node(type==='textarea'?'textarea':'input');
  if(type!=='textarea')input.type=type;else input.rows=3;
  input.value=object[key]||'';input.addEventListener('input',()=>{object[key]=input.value;changed()});wrap.append(title,input);return wrap;
 }
 function select(label,object,key,options,onChange){
  const wrap=node('label'),input=node('select');wrap.append(node('span',label),input);
  for(const [value,text] of options)input.add(new Option(text,value));
  if(object[key]&&!options.some(x=>x[0]===object[key]))input.add(new Option('Association indisponible',object[key]));
  input.value=object[key]||'';input.addEventListener('change',()=>{object[key]=input.value;changed();onChange?.()});return wrap;
 }
 function check(label,object,key){const wrap=node('label',undefined,'description-check'),input=node('input');input.type='checkbox';input.checked=object[key];input.addEventListener('change',()=>{object[key]=input.checked;changed()});wrap.append(input,node('span',label));return wrap}
 function freshSection(merchant=false){return {id:crypto.randomUUID(),name:merchant?'Nouvelle boutique':'Nouvelle section',heading:'',text:'',after_text:'',hide_if_empty:merchant,links:[],...(merchant?{partner_id:''}:{mode:'manual',merchants:[]})}}
 function move(items,index,destination){if(busy||destination<0||destination>=items.length||index===destination)return;const item=items.splice(index,1)[0];items.splice(destination,0,item);changed();render();root.querySelector(`[data-section-id="${CSS.escape(item.id)}"] > summary button`)?.focus()}
 function sorting(container,items,index,label){
  const actions=node('div',undefined,'description-order'),grip=button('⠿',()=>{});grip.title='Glisser pour déplacer, ou utiliser les flèches';grip.setAttribute('aria-label','Déplacer '+label);grip.style.touchAction='none';
  grip.addEventListener('pointerdown',event=>{
   if(event.button!==0||busy)return;event.preventDefault();grip.focus();grip.setPointerCapture(event.pointerId);let target=index;
   const moving=e=>{if(e.pointerId!==event.pointerId)return;e.preventDefault();let hit=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-section-id]');while(hit&&!items.some(x=>x.id===hit.dataset.sectionId))hit=hit.parentElement?.closest('[data-section-id]');if(hit)target=items.findIndex(x=>x.id===hit.dataset.sectionId);if(e.clientY<80)window.scrollBy(0,-18);else if(e.clientY>innerHeight-80)window.scrollBy(0,18)};
   const cleanup=()=>{grip.removeEventListener('pointermove',moving);grip.removeEventListener('pointerup',finish);grip.removeEventListener('pointercancel',cleanup)};
   const finish=e=>{if(e.pointerId!==event.pointerId)return;moving(e);cleanup();move(items,index,target)};
   grip.addEventListener('pointermove',moving);grip.addEventListener('pointerup',finish);grip.addEventListener('pointercancel',cleanup);
  });
  grip.addEventListener('keydown',event=>{if(['ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();move(items,index,index+(event.key==='ArrowUp'?-1:1))}});
  const up=button('↑',()=>move(items,index,index-1)),down=button('↓',()=>move(items,index,index+1));up.setAttribute('aria-label','Monter '+label);down.setAttribute('aria-label','Descendre '+label);up.disabled=index===0;down.disabled=index===items.length-1;
  const position=node('input');position.type='number';position.min=1;position.max=items.length;position.value=index+1;position.setAttribute('aria-label','Position de '+label);
  position.addEventListener('change',()=>{const n=Number(position.value);if(Number.isInteger(n))move(items,index,n-1)});
  actions.append(grip,up,down,position,button('Supprimer',()=>{if(confirm('Supprimer « '+label+' » de ce modèle ?')){items.splice(index,1);changed();render()}}));return actions;
 }
 function bindings(owner){
  const box=node('div',undefined,'description-bindings');
  owner.links.forEach((binding,index)=>{
   const row=node('fieldset');row.append(node('legend','Lien permanent '+(index+1)),field('Intitulé dans la description',binding,'label'));
   row.append(select('Fiche LinKs existante',binding,'link_id',[['','À associer'],...catalogue.items.map(x=>[x.id,x.name+(x.archived?' · archivé':!x.enabled?' · suspendu':'')])],()=>{binding.source_id='';render()}));
   const link=catalogue.items.find(x=>x.id===binding.link_id),sources=[...new Map((link?.publications||[]).filter(x=>x.active).map(x=>[x.source_id,x])).values()];
   row.append(select('Source YouTube existante (actuelle ou historique)',binding,'source_id',[['','Choisir le lien déjà publié'],...sources.map(x=>[x.source_id,x.source_name])]));
   if(!sources.length)row.append(node('p','Aucun lien de publication disponible pour cette fiche. Gérez ses liens dans « Liens suivis ».','muted'));
   if(binding.reference_url)row.append(node('p','Référence fournie : '+binding.reference_url,'description-reference'));
   row.append(button('Retirer cette association',()=>{owner.links.splice(index,1);changed();render()}));box.append(row);
  });
  box.append(button('Ajouter un lien permanent',()=>{owner.links.push({id:crypto.randomUUID(),label:'',reference_url:'',link_id:'',source_id:''});changed();render()}));return box;
 }
 function sectionEditor(item,items,index,merchant=false){
  const details=node('details',undefined,merchant?'description-merchant':'description-section');details.open=openItems.has(item.id);details.dataset.sectionId=item.id;
  details.addEventListener('toggle',()=>{if(details.isConnected){if(details.open)openItems.add(item.id);else openItems.delete(item.id)}});
  const summary=node('summary');summary.append(node('span',item.name),sorting(details,items,index,item.name));details.append(summary);
  const grid=node('div',undefined,'description-fields');grid.append(field('Nom',item,'name'),field('Titre visible',item,'heading'));
  if(merchant)grid.append(select('Partenaire LinKs',item,'partner_id',[['','Aucun partenaire associé'],...catalogue.partners.map(x=>[x.id,x.name])]));
  else grid.append(select('Comportement',item,'mode',[['manual','Manuel'],['permanent','Permanent'],['smart','Intelligent']]));
  grid.append(check('Masquer si vide',item,'hide_if_empty'));details.append(grid,field('Texte prérempli',item,'text','textarea'),bindings(item),field('Texte après les liens',item,'after_text','textarea'));
  if(!merchant){
   item.merchants.forEach((m,i)=>details.append(sectionEditor(m,item.merchants,i,true)));
   details.append(button('Ajouter une sous-section marchande',()=>{item.merchants.push(freshSection(true));changed();render()}));
  }
  return details;
 }
 async function preview(){
  if(!model)return;
  const snapshot=JSON.stringify(model),result=await request('preview',model);
  if(snapshot!==JSON.stringify(model))return; // Never display a response for an obsolete edit.
  const host=root.querySelector('[data-template-preview]');if(!host)return;host.replaceChildren();
  if(result.problems.length){const list=node('ul',undefined,'description-problems');for(const p of result.problems)list.append(node('li',(p.label||p.id)+' — '+p.message));host.append(list)}
  host.append(node('pre',result.text||'Le modèle ne contient pas encore de texte.','description-text'));
 }
 async function refresh(){[templates,drafts,catalogue]=await Promise.all([request('templates').then(x=>x.items),request('drafts').then(x=>x.items),request('catalogue')])}
 function canDiscard(){return !dirty||confirm('Abandonner les modifications non enregistrées de ce modèle ?')}
 async function save(){
  if(!model)return;busy=true;const revision=editRevision;
  try{const result=await request(model.id?'templates/'+model.id+'/save':'templates',{...model,expected_revision:model.revision});
   Object.assign(model,{id:result.id,revision:result.revision,created_at:result.created_at,updated_at:result.updated_at});await refresh();
   if(revision!==editRevision){message('Modèle enregistré ; vos dernières modifications restent à enregistrer.');return}
   model=result;dirty=false;render();message('Modèle enregistré. Les descriptions existantes restent inchangées.');await preview()}
  finally{busy=false}
 }
 function renderTemplates(){
  const bar=node('div',undefined,'description-toolbar'),chooser=node('select');chooser.setAttribute('aria-label','Modèle de description');chooser.add(new Option('Choisir un modèle',''));for(const t of templates)chooser.add(new Option(t.name,t.id));chooser.value=model?.id||'';
  chooser.addEventListener('change',()=>{if(busy||!canDiscard()){chooser.value=model?.id||'';return}model=clone(templates.find(x=>x.id===chooser.value)||null);dirty=false;render();run(preview)});
  bar.append(chooser,button('Nouveau modèle',()=>{if(!canDiscard())return;model={name:'Nouveau modèle',platform:'youtube',sections:[]};dirty=true;render()}),button('Recharger',async()=>{if(!canDiscard())return;const key=model?.id,revision=editRevision;await refresh();if(revision!==editRevision||key!==model?.id){message('Votre saisie a changé pendant le chargement ; elle est conservée.');return}model=clone(templates.find(x=>x.id===key)||templates[0]||null);dirty=false;render();await preview()}));root.append(bar);
  if(!model){root.append(node('p','Créez un modèle pour préparer vos descriptions.'));return}
  const fields=node('div',undefined,'description-fields');fields.append(field('Nom du modèle',model,'name'),field('Plateforme',model,'platform'));root.append(fields);
  const actions=node('div',undefined,'description-toolbar'),saveButton=button('Enregistrer le modèle',save,'primary');saveButton.dataset.saveTemplate='';saveButton.disabled=!dirty;actions.append(saveButton);
  if(model.id){
   actions.append(button('Dupliquer',async()=>{if(!canDiscard())return;const name=prompt('Nom de la copie',model.name+' — copie');if(!name)return;model=await request('templates/'+model.id+'/duplicate',{name,expected_revision:model.revision});dirty=false;await refresh();render();await preview()}),button('Supprimer le modèle',async()=>{if(!confirm('Supprimer ce modèle ? Les brouillons et versions existants seront conservés.'))return;await request('templates/'+model.id+'/delete',{expected_revision:model.revision});dirty=false;await refresh();model=clone(templates[0]||null);render()}));
  }
  root.append(actions,node('p','Les textes permanents sont préremplis et restent modifiables dans chaque description. Les liens de référence ne sont pas insérés tant que leur association n’est pas résolue.','muted'));
  const layout=node('div',undefined,'description-template-layout'),sections=node('div'),side=node('aside',undefined,'description-template-preview');
  model.sections.forEach((s,i)=>sections.append(sectionEditor(s,model.sections,i)));
  sections.append(button('Ajouter une section',()=>{const item=freshSection();model.sections.push(item);openItems.add(item.id);changed();render()}));
  const output=node('div');output.dataset.templatePreview='';side.append(node('h2','Aperçu du modèle'),button('Actualiser l’aperçu',preview),output);layout.append(sections,side);root.append(layout);
 }
 function renderDrafts(){
  const toolbar=node('div',undefined,'description-toolbar'),selector=node('select');selector.setAttribute('aria-label','Modèle du nouveau brouillon');for(const t of templates)selector.add(new Option(t.name,t.id));
  const create=button('Nouveau brouillon',async()=>{const t=templates.find(x=>x.id===selector.value);if(!t)return;const title=prompt('Titre interne de la description');if(!title)return;const draft=await request('drafts',{title,template_id:t.id,template_revision:t.revision});await refresh();render();showDraft(draft);message('Brouillon enregistré à partir d’une copie du modèle.')} ,'primary');create.disabled=!templates.length;
  toolbar.append(selector,create);root.append(toolbar);
  if(!drafts.length)root.append(node('p','Aucune description enregistrée. Choisissez un modèle pour préparer un brouillon.'));
  const list=node('div',undefined,'description-draft-list');for(const draft of drafts){const row=node('article');row.append(node('strong',draft.title),node('span','Brouillon · '+new Date(draft.updated_at).toLocaleString('fr-FR')),button('Consulter',()=>showDraft(draft)));list.append(row)}root.append(list);
  const host=node('div');host.dataset.draftPreview='';root.append(host);
 }
 function showDraft(draft){const host=root.querySelector('[data-draft-preview]');if(!host)return;host.replaceChildren(node('h2',draft.title),node('p','Contenu enregistré','muted'));for(const p of draft.problems)host.append(node('p',(p.label||p.id)+' — '+p.message,'description-problems'));host.append(node('pre',draft.text,'description-text'))}
 function render(){
  for(const details of root.querySelectorAll('details[data-section-id]')){if(details.open)openItems.add(details.dataset.sectionId);else openItems.delete(details.dataset.sectionId)}
  root.replaceChildren();const head=node('div',undefined,'section-head'),title=node('div');title.append(node('h1','Descriptions'),node('p','Vos descriptions YouTube et leurs modèles.'));head.append(title);root.append(head);
  const nav=node('div',undefined,'description-toolbar');for(const [id,label] of [['drafts','Descriptions'],['templates','Modèles']]){const b=button(label,()=>{tab=id;render();if(id==='templates')return preview()});b.setAttribute('aria-pressed',String(tab===id));nav.append(b)}root.append(nav);
  const status=node('p',dirty?'Modifications du modèle non enregistrées':'', 'description-status');status.dataset.descriptionStatus='';status.setAttribute('role','status');status.setAttribute('aria-live','polite');root.append(status);
  if(tab==='templates')renderTemplates();else renderDrafts();
 }
 async function load(){if(loaded)return;try{await refresh();model=clone(templates[0]||null);loaded=true;render();await preview()}catch(error){root.replaceChildren(node('p',error.message),button('Réessayer',load))}}
 window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue=''}});
 return {load};
})();
