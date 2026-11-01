/* Confirmed server operations only. Comparison never allocates a link. */
window.LinksDescriptionWorkflow=(()=>{'use strict';
 const clone=v=>structuredClone(v),node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};
 const button=(text,fn)=>{const b=node('button',text);b.type='button';b.addEventListener('click',fn);return b};
 const status={ready:'Prête',applied:'Appliquée',ignored:'Ignorée',obsolete:'Obsolète',failed:'Échouée'};
 const kinds={replace:'Remplacement',add:'Ajout',move:'Déplacement',remove:'Retrait',cleanup:'Sections vides'};
 function compact(rows){const out=[];let i=0;while(i<rows.length){if(rows[i].kind==='same'){out.push(rows[i++]);continue}const left=[],right=[];while(i<rows.length&&rows[i].kind!=='same'){if(rows[i].left!==undefined)left.push(rows[i].left);if(rows[i].right!==undefined)right.push(rows[i].right);i++}for(let j=0;j<Math.max(left.length,right.length);j++)out.push({left:left[j],right:right[j],kind:'change'})}return out}
 function diff(before,after){
  const a=before.split('\n'),b=after.split('\n');
  if(a.length*b.length>500000){let p=0;while(p<a.length&&p<b.length&&a[p]===b[p])p++;return compact([...a.slice(0,p).map(text=>({left:text,right:text,kind:'same'})),...a.slice(p).map(left=>({left,kind:'remove'})),...b.slice(p).map(right=>({right,kind:'add'}))])}
  const rows=Array.from({length:a.length+1},()=>new Uint32Array(b.length+1));
  for(let i=a.length-1;i>=0;i--)for(let j=b.length-1;j>=0;j--)rows[i][j]=a[i]===b[j]?1+rows[i+1][j+1]:Math.max(rows[i+1][j],rows[i][j+1]);
  const out=[];let i=0,j=0;while(i<a.length||j<b.length){if(i<a.length&&j<b.length&&a[i]===b[j])out.push({left:a[i++],right:b[j++],kind:'same'});else if(j<b.length&&(i===a.length||rows[i][j+1]>=rows[i+1][j]))out.push({right:b[j++],kind:'add'});else out.push({left:a[i++],kind:'remove'})}return compact(out);
 }
 function modal(title){const dialog=node('dialog',undefined,'description-review-dialog');dialog.append(node('h2',title));const content=node('div');dialog.append(content,button('Fermer',()=>dialog.close()));document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove(),{once:true});dialog.showModal();return {dialog,content}}
 function comparison(host,before,after){const label=node('label',undefined,'description-check'),only=node('input');only.type='checkbox';label.append(only,node('span','Afficher uniquement les modifications'));const grid=node('div',undefined,'description-comparison');host.append(label,grid);const lines=diff(before,after);const render=()=>{grid.replaceChildren(node('h3','Texte original'),node('h3','Texte proposé'));for(const line of lines){if(only.checked&&line.kind==='same')continue;grid.append(node('div',line.left??' ',line.kind!=='same'&&line.left!==undefined?'description-diff-remove':'description-diff-line'),node('div',line.right??' ',line.kind!=='same'&&line.right!==undefined?'description-diff-add':'description-diff-line'))}};only.addEventListener('change',render);render()}
 class Controller{
  constructor(editor,request){this.editor=editor;this.request=request;this.plan=null;this.key='';this.sequence=0;this.busy=false;this.note='';}
  signature(){const e=this.editor;return JSON.stringify([e.doc.id,e.doc.revision,e.generation])}
  prefix(){return 'links:description-validation:v1:'+this.editor.instance+':'+this.editor.doc.id+':'}
  pending(){const out=[];try{for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(key.startsWith(this.prefix())){try{const value=JSON.parse(localStorage.getItem(key));if(value?.request?.mutation_id&&value.path)out.push({key,value})}catch{}}}}catch{}return out}
  schedule(){const key=this.signature();if(key===this.key)return;this.key=key;this.plan=null;const sequence=++this.sequence;clearTimeout(this.timer);const e=this.editor;if(e.dirty()||e.saving||this.busy||this.pending().length)return;this.timer=setTimeout(async()=>{try{const plan=await this.request('drafts/'+e.doc.id+'/compare',{expected_revision:e.doc.revision});if(sequence===this.sequence&&key===this.signature()){this.plan=plan;e.paint()}}catch(error){if(sequence===this.sequence)this.note=error.message}},300)}
  async flush(){const e=this.editor;if(this.busy||e.saving)throw Error('Attendez la fin de l’enregistrement.');if(this.pending().length)throw Error('Reprenez d’abord la validation interrompue.');await e.save();if(e.dirty()||e.blocked)throw Error('Enregistrez le brouillon et résolvez le conflit avant cette action.')}
  async fresh(){await this.flush();const e=this.editor,signature=this.signature();const plan=await this.request('drafts/'+e.doc.id+'/compare',{expected_revision:e.doc.revision});if(signature!==this.signature())throw Error('Votre saisie a changé. Ouvrez à nouveau la comparaison.');this.plan=plan;return plan}
  run(fn){return Promise.resolve().then(fn).catch(error=>{this.note=error.message;this.paint()})}
  option(id,patch){const e=this.editor;e.doc.analysis_version=1;e.doc.selections.operations={...e.doc.selections.operations,[id]:{...e.doc.selections.operations?.[id],...patch}};e.changed()}
  mount(host){this.host=host;this.paint()}
  paint(){if(!this.host?.isConnected)return;this.host.replaceChildren();const actions=node('div',undefined,'description-toolbar');actions.append(button('Comparer les modifications',()=>this.run(()=>this.review())),button('Finaliser et copier',()=>this.run(()=>this.finish())),button('Historique',()=>this.run(()=>this.history())));this.host.append(actions);if(this.note)this.host.append(node('p',this.note,'description-workflow-status'));for(const {key,value} of this.pending())this.host.append(node('p','Validation interrompue : votre texte reste conservé.'),button('Reprendre la validation',()=>this.run(()=>this.execute(value.path,value.request,key,value))));for(const b of actions.querySelectorAll('button'))b.disabled=this.busy;
   const results=Object.values(this.editor.doc.workflow?.results||{});if(results.length){const details=node('details');details.append(node('summary','Résultat de la dernière application'));for(const r of results)details.append(node('p',(status[r.status]||r.status)+' — '+r.reason));this.host.append(details)}
  }
  preview(host){if(!this.plan){host.append(node('p','Aperçu du texte saisi ; enregistrez pour actualiser les propositions.','muted'),node('pre',this.editor.doc.text,'description-text'));return}for(const warning of this.plan.warnings)host.append(node('p',warning,'description-analysis-note'));if(this.plan.operations.some(o=>o.selected&&o.pending_create))host.append(node('p','Les liens à créer sont représentés par leur destination réelle. Aucune URL courte fictive.','muted'));host.append(button('Comparer en grand',()=>this.run(()=>this.review())),node('pre',this.plan.after,'description-text'))}
  async review(){
   const plan=await this.fresh(),{dialog,content}=modal('Comparer avant application');
   for(const warning of plan.warnings)content.append(node('p',warning,'description-analysis-note'));
   const list=node('div',undefined,'description-operation-list');content.append(list);
   for(const op of plan.operations){
    const row=node('details',undefined,'description-operation');row.dataset.operationId=op.id;row.open=op.status==='obsolete';row.append(node('summary',(kinds[op.kind]||op.kind)+' · '+(status[op.status]||op.status)+' · '+(op.label||op.raw||'')+(op.pending_create?' · Lien suivi à créer':'')));
    row.append(node('p',op.reason));if(op.url)row.append(node('code',op.url));
    const label=node('label',undefined,'description-check'),selected=node('input');selected.type='checkbox';selected.checked=!!op.selected;selected.addEventListener('change',()=>{this.option(op.id,{selected:selected.checked});dialog.close();this.note='Sélection modifiée. Comparez à nouveau.';this.paint()});label.append(selected,node('span',op.selected?'Conserver cette opération':'Sélectionner cette opération'));row.append(label);
    const correction=(patch)=>{this.option(op.id,patch);dialog.close();this.note='Choix conservé. Comparez à nouveau.';this.paint()};
    if(op.kind!=='cleanup'){
     const fields=node('div',undefined,'description-operation-options');
     const select=(caption,options,value,fn)=>{const label=node('label',caption),input=node('select');input.setAttribute('aria-label',caption);input.add(new Option('Choisir',''));for(const [name,id] of options)input.add(new Option(name,id));input.value=value||'';input.addEventListener('change',()=>fn(input.value));label.append(input);fields.append(label)};
     if(!op.amazon&&op.kind!=='remove'&&op.kind!=='move'){select('Fiche LinKs',plan.catalogue.map(i=>[i.name,i.id]),op.link_id,link_id=>correction({link_id,source_id:''}));select('Source de publication',plan.sources.map(s=>[s.name,s.id]),op.source_id,source_id=>correction({source_id}))}
     if(!op.amazon&&op.raw&&!op.link_id&&op.kind==='replace')fields.append(button('Autoriser la création de ce lien',()=>{if(confirm('Autoriser la création de cette destination via LinKs, uniquement lors de la prochaine application confirmée ?'))correction({allow_create:true,selected:true})}));
     if(op.origin==='merchant'){select('Remplacer une URL présente',plan.urls.map(u=>[u.url,u.id]),op.option.target_url_id,target_url_id=>correction({target_url_id}));}
     if(op.raw&&op.kind!=='move')fields.append(button('Retirer uniquement cette URL du texte',()=>correction({action:'remove',selected:true})));
     if(['add','move'].includes(op.kind)){
      const sections=this.editor.doc.template_snapshot.sections;select('Section cible',sections.map(s=>[s.name,s.id]),op.section_id,section_id=>correction({section_id,merchant_id:''}));
      const section=sections.find(s=>s.id===op.section_id);if(section?.merchants.length)select('Sous-section cible',section.merchants.map(s=>[s.name,s.id]),op.merchant_id,merchant_id=>correction({merchant_id}));
      fields.append(button('Autoriser la section au curseur',()=>{if(confirm('Créer cette section à la position actuelle du curseur dans le texte ?'))correction({allow_section:true,section_at:this.editor.selection.start})}));
      if(op.merchant_id)fields.append(button('Autoriser l’ajout de la sous-section',()=>{if(confirm('Ajouter le titre marchand de la copie du modèle dans la section confirmée ?'))correction({allow_subsection:true})}),button('Associer la sous-section à la sélection',()=>{const s=this.editor.selection;if(s.start===s.end){this.note='Sélectionnez le passage dans l’éditeur puis rouvrez la comparaison.';dialog.close();this.paint();return}correction({merchant_span:{...s,quote:window.DescriptionSections.slice(this.editor.doc.text,s.start,s.end)}})}));
     }
     row.append(fields);
    }
    list.append(row);
   }
   comparison(content,plan.before,plan.after);const apply=button('Appliquer les modifications',()=>this.run(async()=>{dialog.close();await this.execute('drafts/'+this.editor.doc.id+'/apply',{expected_revision:plan.expected_revision,text_hash:plan.text_hash,plan_hash:plan.plan_hash,mutation_id:window.LinksUUID()})}));apply.disabled=!plan.operations.some(o=>o.status==='ready');content.append(apply,button('Revenir aux sélections',()=>dialog.close()));
  }
  async execute(path,request,key=null,pending=null){
   const e=this.editor;if(this.busy||e.saving)throw Error('Une opération est déjà en cours.');
   const record=pending||{path,request,baseRevision:e.doc.revision,baseText:e.doc.text,savedAt:new Date().toISOString()};
   key=key||this.prefix()+request.mutation_id;try{localStorage.setItem(key,JSON.stringify(record))}catch{throw Error('Impossible de conserver la validation pour une reprise. Libérez le stockage local avant de continuer.')}
   this.busy=true;e.saving=true;clearTimeout(e.timer);const generation=e.generation,revision=e.doc.revision;this.paint();
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
   try{
    const raw=await this.request(path,request,controller.signal),response=path.startsWith('versions/')?{document:raw,restored:true}:raw;
    localStorage.removeItem(key);
    if(e.generation!==generation||(e.dirty()&&pending)||(!response.restored&&revision!==record.baseRevision&&revision!==response.document.revision)){
     e.blocked=true;this.note='Opération enregistrée sur le serveur. Votre saisie plus récente reste intacte : comparez-la à la version serveur ou enregistrez une copie.';e.persist();
    }else if(response.restored){window.LinksDescriptions.openDraft(response.document)}
    else{
     if(e.doc.text!==response.document.text)e.remember();e.doc=clone(response.document);e.generation++;e.ack=e.generation;e.pending=null;e.blocked=false;e.message='Enregistré';e.writeArea();e.forgetRecovery();try{localStorage.removeItem(e.key())}catch{}
     this.note=response.version?'Version finalisée et conservée dans l’historique.':(response.results||[]).some(r=>r.status==='failed'||r.status==='obsolete')?'Application partielle : les réussites sont conservées. Corrigez les opérations restantes.':'Modifications appliquées. Le texte affiche les véritables URL.';
    }
    this.key='';this.plan=null;if(response.version)await this.copyDialog(response.version);return response;
   }catch(error){if(error.status===409||error.status===400){localStorage.removeItem(key);if(error.status===409)e.blocked=true}else{e.blocked=true;e.persist()}throw error}
   finally{clearTimeout(timer);this.busy=false;e.saving=false;e.paint();this.paint()}
  }
  async finish(){
   const plan=await this.fresh(),e=this.editor,count=Array.from(plan.before).length,{dialog,content}=modal('Finaliser et copier');
   content.append(node('p',count+' / 5 000 caractères'));for(const warning of plan.warnings)content.append(node('p',warning,'description-analysis-note'));
   const remaining=plan.operations.filter(o=>o.selected&&['ready','obsolete'].includes(o.status));let ignore;
   if(remaining.length){content.append(node('p',remaining.length+' opération(s) sélectionnée(s) restent non appliquées. Le texte actuel sera conservé exactement.'));const label=node('label',undefined,'description-check');ignore=node('input');ignore.type='checkbox';label.append(ignore,node('span','Ignorer volontairement ces propositions pour cette version'));content.append(label)}
   const text=node('textarea');text.readOnly=true;text.value=plan.before;text.setAttribute('aria-label','Texte à finaliser');content.append(text);
   const submit=button('Enregistrer la version et copier',()=>this.run(async()=>{if(ignore&&!ignore.checked){this.note='Confirmez l’abandon des propositions restantes ou appliquez-les.';this.paint();return}dialog.close();await this.execute('drafts/'+e.doc.id+'/finalize',{expected_revision:plan.expected_revision,text_hash:plan.text_hash,plan_hash:plan.plan_hash,mutation_id:window.LinksUUID(),ignore_remaining:!!ignore?.checked})}));submit.disabled=count>5000||!plan.before.trim();content.append(submit);
  }
  async copyDialog(version){const {content}=modal('Version finalisée — texte exact'),area=node('textarea'),message=node('p');area.readOnly=true;area.value=version.text;area.setAttribute('aria-label','Texte final à copier');content.append(node('p',new Date(version.finalized_at).toLocaleString('fr-FR')),area,message);const copy=async()=>{try{await navigator.clipboard.writeText(version.text);message.textContent='Texte intégral copié.'}catch{message.textContent='Copie automatique indisponible. Le texte est sélectionné : utilisez Ctrl+C.';area.focus();area.select()}};content.append(button('Copier le texte intégral',copy));await copy()}
  async history(){
   await this.flush();const e=this.editor,{items}=await this.request('drafts/'+e.doc.id+'/versions'),{dialog,content}=modal('Historique des versions');
   const videoLabel=node('label','URL YouTube facultative'),video=node('input');video.value=e.doc.youtube_url||'';video.type='url';video.setAttribute('aria-label','URL YouTube facultative');video.addEventListener('input',()=>{e.doc.youtube_url=video.value;e.changed()});videoLabel.append(video);content.append(videoLabel);
   if(!items.length){content.append(node('p','Aucune version finalisée.'));return}
   items.sort((a,b)=>b.finalized_at.localeCompare(a.finalized_at));const left=node('select'),right=node('select');left.setAttribute('aria-label','Version de gauche');right.setAttribute('aria-label','Version de droite');for(const [i,v] of items.entries()){const label=new Date(v.finalized_at).toLocaleString('fr-FR')+' · '+(items.length-i);left.add(new Option(label,v.id));right.add(new Option(label,v.id))}if(items.length>1)right.selectedIndex=1;
   content.append(left,right,button('Comparer ces versions',()=>{const a=items.find(v=>v.id===left.value),b=items.find(v=>v.id===right.value),view=modal('Comparaison des versions immuables');comparison(view.content,a.text,b.text)}));
   for(const v of items){const row=node('details');row.dataset.versionId=v.id;row.append(node('summary',new Date(v.finalized_at).toLocaleString('fr-FR')+' · '+Array.from(v.text).length+' caractères'));const text=node('textarea');text.readOnly=true;text.value=v.text;text.setAttribute('aria-label','Texte de la version');row.append(text,button('Comparer au brouillon',()=>{const view=modal('Version / brouillon actuel');comparison(view.content,v.text,e.doc.text)}),button('Copier cette version',()=>this.copyDialog(v)),button('Restaurer dans un nouveau brouillon',()=>this.run(async()=>{await this.flush();if(!confirm('Créer un nouveau brouillon avec cette version, sans modifier l’historique ?'))return;dialog.close();await this.execute('versions/'+v.id+'/restore',{mutation_id:window.LinksUUID()})})));
    const links=node('details');links.append(node('summary','Destinations constatées à la finalisation'));for(const l of v.links)links.append(node('code',l.url),node('p',l.destination+' · fiche '+(l.link_id||'directe')+' · source '+(l.source_id||'aucune')));row.append(links);content.append(row);
   }
  }
 }
 return {Controller,diff};
})();
