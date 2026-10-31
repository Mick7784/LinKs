/* Free text is authoritative. Server responses only acknowledge revisions, never replace typing. */
window.LinksDescriptionEditor=(()=>{'use strict';
 const S=window.DescriptionSections,states=new Map(),clone=value=>structuredClone(value);
 const node=(tag,text,className)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el};
 const request=(path,data,signal)=>api('/api/descriptions/'+path,data===undefined?{signal}:{method:'POST',signal,body:JSON.stringify(data)});
 const fields=doc=>({title:doc.title,text:doc.text,youtube_url:doc.youtube_url||'',sections:clone(doc.sections),...(doc.analysis_version===1?{analysis_version:1,products:clone(doc.products),selections:clone(doc.selections),manual_order:clone(doc.manual_order)}:{})});
 function action(label,fn){const b=node('button',label);b.type='button';b.addEventListener('click',fn);return b}
 function dialog(title,text,editable=false){
  const modal=node('dialog',undefined,'description-text-dialog'),form=node('form'),area=node('textarea');form.method='dialog';area.value=text;area.readOnly=!editable;area.setAttribute('aria-label',editable?'Description à importer':title);area.rows=18;
  const cancel=action('Fermer',()=>modal.close()),submit=action(editable?'Importer et remplacer le texte':'Continuer',()=>{modal.returnValue='apply';modal.close('apply')});
  form.append(node('h2',title),area,cancel);if(editable)form.append(submit);modal.append(form);document.body.append(modal);modal.showModal();
  return new Promise(resolve=>modal.addEventListener('close',()=>{const result=modal.returnValue==='apply'?area.value:null;modal.remove();resolve(result)},{once:true}));
 }
 class Editor{
  constructor(document,instance){
   this.doc=clone(document);this.instance=instance;this.writer=crypto.randomUUID();this.generation=0;this.ack=0;this.pending=null;this.pendingGeneration=0;this.saving=false;this.blocked=false;this.history=[];this.future=[];this.selection={start:0,end:0};this.recoveryOrigin=null;this.mode='analysis';this.ratio=65;this.message='Enregistré';this.warning='';this.composing=false;
   this.analysis=new window.LinksDescriptionAnalysis.Panel(this,request);
   this.workflow=new window.LinksDescriptionWorkflow.Controller(this,request);
  }
  prefix(){return `links:description-editor:v1:${this.instance}:${this.doc.id}:`}
  key(){return this.prefix()+this.writer}
  dirty(){return this.generation!==this.ack||!!this.pending}
  forgetRecovery(){
   try{if(this.recoveryOrigin&&localStorage.getItem(this.recoveryOrigin)===this.recoveryValue)localStorage.removeItem(this.recoveryOrigin)}catch{}
   this.recoveryOrigin=null;this.recoveryValue=null;
  }
  persist(){
   if(!this.dirty())return;
   try{localStorage.setItem(this.key(),JSON.stringify({version:1,id:this.doc.id,baseRevision:this.doc.revision,fields:fields(this.doc),selection:this.selection,pending:this.pending,pendingGeneration:this.pendingGeneration,copyPending:this.copyPending,generation:this.generation,blocked:this.blocked,savedAt:new Date().toISOString()}));this.warning=''}
   catch{this.warning='La récupération locale est indisponible ou pleine. Gardez cet onglet ouvert jusqu’à l’enregistrement serveur.'}
  }
  recoveries(){
   const rows=[];try{for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(key?.startsWith(this.prefix())&&key!==this.key()){try{const value=JSON.parse(localStorage.getItem(key));if(value?.version===1&&value.id===this.doc.id&&typeof value.fields?.text==='string'&&Array.isArray(value.fields.sections))rows.push({key,value})}catch{}}}}catch{this.warning='Le stockage local est indisponible.'}return rows.sort((a,b)=>String(b.value.savedAt).localeCompare(String(a.value.savedAt)));
  }
  changed(){this.generation++;this.message='En attente d’enregistrement';this.persist();this.paint();clearTimeout(this.timer);if(!this.composing&&!this.blocked)this.timer=setTimeout(()=>this.save(),700)}
  snapshot(){return {text:this.doc.text,sections:clone(this.doc.sections),selection:clone(this.selection)}}
  remember(){this.history.push(this.snapshot());if(this.history.length>100)this.history.shift();this.future=[]}
  apply(content,{imported=false,selection=null,anchors=null,write=true}={}){
   // Browsers may emit input without a text change (spellcheck/automation/IME).
   // Such notifications must not consume undo steps or reschedule autosave.
   if(content===this.doc.text&&!imported&&!anchors){if(selection)this.selection=selection;return}
   this.remember();const before=this.doc.text;this.doc.text=content;
   this.doc.sections=anchors||S.track(before,content,this.doc.sections,this.doc.template_snapshot.sections,{imported});
   this.selection=selection||{start:S.points(content).length,end:S.points(content).length};
   if(write)this.writeArea();this.changed();
  }
  undo(redo=false){
   const source=redo?this.future:this.history,target=redo?this.history:this.future;if(!source.length)return;
   target.push(this.snapshot());const previous=source.pop();Object.assign(this.doc,{text:previous.text,sections:previous.sections});this.selection=previous.selection;this.writeArea();this.changed();
  }
  writeArea(){if(this.area?.isConnected){this.area.value=this.doc.text;this.area.focus();this.area.setSelectionRange(S.toUTF16(this.doc.text,this.selection.start),S.toUTF16(this.doc.text,this.selection.end))}}
  async save(){
   clearTimeout(this.timer);if(this.saving||this.blocked||this.copyPending||this.composing||!this.dirty())return;
   if(!navigator.onLine){this.message='Hors ligne — copie locale conservée';this.persist();this.paint();return}
   if(!this.pending){this.pending={...fields(this.doc),expected_revision:this.doc.revision,mutation_id:crypto.randomUUID()};this.pendingGeneration=this.generation}
   const operation=clone(this.pending),generation=this.pendingGeneration;this.saving=true;this.persist();this.paint();
   const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);
   try{
    const saved=await request('drafts/'+this.doc.id+'/save',operation,controller.signal);
    // Do not assign saved.text, saved.sections, or any editable field here.
    this.doc.revision=saved.revision;this.doc.updated_at=saved.updated_at;this.doc.last_mutation=saved.last_mutation;
    this.ack=generation;this.pending=null;this.message='Enregistré';
    if(!this.dirty()){try{localStorage.removeItem(this.key())}catch{}this.forgetRecovery()}else this.persist();
   }catch(error){
    if(error.status===409){this.blocked=true;this.message='Conflit de révision — votre saisie est conservée'}
    else{this.message=error.status===400?error.message:'Enregistrement interrompu — copie locale conservée. Réessayez.';if(error.status===400)this.pending=null}
    this.persist();
   }finally{clearTimeout(timeout);this.saving=false;this.paint()}
   if(!this.pending&&!this.blocked&&this.generation!==this.ack&&this.message==='Enregistré')this.timer=setTimeout(()=>this.save(),0);
  }
  async fork(){
   if(this.saving)return;
   if(!confirm('Enregistrer votre texte dans un nouveau brouillon, en conservant la version serveur actuelle ?'))return;
   const oldKey=this.key(),oldId=this.doc.id;
   if(!this.copyPending)this.copyPending={operation:{...fields(this.doc),title:S.slice(this.doc.title,0,140)+' — copie',expected_revision:this.doc.revision,mutation_id:crypto.randomUUID()},generation:this.generation,title:this.doc.title};
   const {operation,generation,title}=this.copyPending;
   this.saving=true;this.persist();this.paint();const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);
   try{
    const saved=await request('drafts/'+oldId+'/fork',operation,controller.signal);states.delete(oldId);this.doc.id=saved.id;this.doc.revision=saved.revision;this.doc.updated_at=saved.updated_at;if(this.doc.title===title)this.doc.title=saved.title;this.doc.last_mutation=saved.last_mutation;states.set(saved.id,this);
    this.ack=generation;this.pending=null;this.copyPending=null;this.blocked=false;this.message='Copie enregistrée';this.writer=crypto.randomUUID();
    try{localStorage.removeItem(oldKey)}catch{}this.forgetRecovery();
    this.onFork?.(saved.id);if(this.title?.isConnected)this.title.value=this.doc.title;
    if(this.dirty()){this.persist();this.timer=setTimeout(()=>this.save(),0)}
   }catch(error){this.message='Copie interrompue — réessayez « Enregistrer ma copie ». Votre saisie est conservée.';this.persist()}finally{clearTimeout(timeout);this.saving=false;this.paint()}
  }
  async serverVersion(){try{const response=await request('drafts/'+this.doc.id);await dialog('Version serveur — lecture seule',response.document.text)}catch(error){this.message=error.message;this.paint()}}
  async reload(){
   if(!confirm('Ouvrir la version serveur ? Votre saisie non enregistrée restera disponible dans les récupérations locales.'))return;
   if(this.saving)return;clearTimeout(this.timer);this.persist();const generation=this.generation;this.saving=true;this.paint();
   try{const response=await request('drafts/'+this.doc.id);if(this.generation!==generation){this.message='Votre saisie a changé pendant le chargement ; elle est conservée';return}this.doc=response.document;this.writer=crypto.randomUUID();this.generation=0;this.ack=0;this.pending=null;this.copyPending=null;this.blocked=false;this.history=[];this.future=[];this.recoveryOrigin=null;this.selection={start:0,end:0};this.message='Version serveur chargée';this.mount(this.host,this.onFork)}catch(error){this.message=error.message}finally{this.saving=false;this.paint();if(this.dirty()&&!this.blocked)this.timer=setTimeout(()=>this.save(),700)}
  }
  recover(key,value){
   if(this.saving)return;
   if(!confirm('Reprendre cette copie locale ? Les emplacements ambigus resteront à confirmer.'))return;
   const expectedIds=this.doc.template_snapshot.sections.map(s=>s.id).sort().join('|');
   if(typeof value.fields.title!=='string'||value.fields.sections.map(s=>s.id).sort().join('|')!==expectedIds){this.message='Cette récupération est incompatible ; son texte reste consultable.';this.paint();return}
   // Keep the current unsaved copy as a separate recovery before switching.
   if(this.dirty()){this.persist();this.writer=crypto.randomUUID()}
   this.remember();Object.assign(this.doc,clone(value.fields));this.selection=value.selection||{start:0,end:0};this.recoveryOrigin=key;this.recoveryValue=JSON.stringify(value);
   const acknowledged=value.pending?.mutation_id===this.doc.last_mutation?.id;
   this.blocked=value.baseRevision!==this.doc.revision&&!acknowledged;
   this.generation++;this.pending=!this.blocked&&!acknowledged?clone(value.pending):null;
   // An interrupted in-flight save can be retried exactly. Its ack must not clear
   // edits made after that request was captured in the recovered page.
   this.pendingGeneration=this.pending?(JSON.stringify(fields(value.pending))===JSON.stringify(fields(value.fields))?this.generation:this.generation-1):0;
   this.copyPending=value.copyPending?clone(value.copyPending):null;
   if(this.copyPending){this.copyPending.generation=this.generation-(value.copyPending.generation!==value.generation?1:0);this.blocked=true}
   this.message=this.blocked?'Copie récupérée — conflit avec la version serveur':'Copie locale récupérée';this.writeArea();if(this.title)this.title.value=this.doc.title;this.persist();this.paint();if(!this.blocked)this.timer=setTimeout(()=>this.save(),700);
  }
  bind(anchor,span){
   if(!confirm('Confirmer cet emplacement pour « '+this.definition(anchor.id).name+' » ?'))return;
   try{const anchors=S.bind(this.doc.text,this.doc.sections,anchor.id,span.start,span.end);this.remember();this.doc.sections=anchors;this.changed()}
   catch(error){this.message=error.message;this.paint()}
  }
  definition(id){return this.doc.template_snapshot.sections.find(s=>s.id===id)}
  restore(anchor){
   if(anchor.status!=='confirmed')return;
   const initial=this.doc.initial_sections[anchor.id];
   if(!confirm('Restaurer uniquement « '+this.definition(anchor.id).name+' » depuis sa copie initiale ? Cette opération est annulable.\n\n'+initial))return;
   const content=S.slice(this.doc.text,0,anchor.start)+initial+S.slice(this.doc.text,anchor.end),end=anchor.start+S.points(initial).length;
   let anchors=S.track(this.doc.text,content,this.doc.sections,this.doc.template_snapshot.sections);
   try{anchors=S.bind(content,anchors,anchor.id,anchor.start,end);this.apply(content,{anchors,selection:{start:anchor.start,end}})}catch(error){this.message=error.message;this.paint()}
  }
  paint(){
   this.analysis.schedule();
   this.workflow.schedule();this.workflow.paint();
   if(!this.host?.isConnected||this.host.editorOwner!==this)return;
   this.status.textContent=this.saving?'Enregistrement…':this.message;this.status.dataset.state=this.blocked?'conflict':this.dirty()?'pending':'saved';this.localWarning.textContent=this.warning;
   this.count.textContent=S.points(this.doc.text).length.toLocaleString('fr-FR')+' caractères';this.undoButton.disabled=!this.history.length;this.redoButton.disabled=!this.future.length;
   this.conflict.hidden=!this.blocked;this.saveButton.disabled=this.saving||this.blocked||!this.dirty();
   this.recoveryBox.replaceChildren();for(const {key,value} of this.recoveries()){
    const row=node('div',undefined,'description-recovery');row.append(node('p','Copie locale du '+new Date(value.savedAt).toLocaleString('fr-FR')+' (cet appareil, éventuellement un autre onglet)'),action('Voir le texte',()=>dialog('Copie locale — lecture seule',value.fields.text)),action('Reprendre cette copie',()=>this.recover(key,value)),action('Supprimer cette copie locale',()=>{if(confirm('Supprimer cette récupération locale ?')){try{localStorage.removeItem(key)}catch{}this.paint()}}));this.recoveryBox.append(row);
   }
   if(this.mode==='analysis'){this.analysis.render(this.assistant);return}
   this.assistant.replaceChildren();
   if(this.mode==='preview'){this.workflow.preview(this.assistant);return}
   const order=[...this.doc.sections].sort((a,b)=>(a.start??Infinity)-(b.start??Infinity));
   for(const anchor of order){
    const row=node('article',undefined,'description-anchor');row.dataset.anchorId=anchor.id;
    row.append(node('strong',this.definition(anchor.id).name),node('small',anchor.status==='confirmed'?'Emplacement confirmé':'Emplacement à confirmer'));
    const buttons=node('div',undefined,'description-anchor-actions');
    if(anchor.status==='confirmed'){
     buttons.append(action('Voir',()=>{this.selection={start:anchor.start,end:anchor.end};this.writeArea()}),action('Restaurer le contenu initial',()=>this.restore(anchor)),action('Dissocier l’emplacement',()=>{this.remember();Object.assign(anchor,{status:'ambiguous',start:null,end:null,candidates:[]});this.changed()}));
    }else{
     row.append(node('p','Sélectionnez le passage correspondant dans le texte, puis confirmez son association.','muted'));
     for(const [index,span] of anchor.candidates.entries()){
      const candidate=node('div',undefined,'description-candidate');candidate.append(node('p',S.slice(this.doc.text,span.start,Math.min(span.end,span.start+140))));candidate.append(action('Voir la proposition '+(index+1),()=>{this.selection=clone(span);this.writeArea()}),action('Confirmer la proposition '+(index+1),()=>this.bind(anchor,span)));row.append(candidate);
     }
    }
    buttons.append(action('Associer à la sélection',()=>this.bind(anchor,this.selection)));row.append(buttons);this.assistant.append(row);
   }
   if(this.doc.problems.length){const issues=node('details');issues.append(node('summary','Associations de liens à résoudre'));for(const problem of this.doc.problems)issues.append(node('p',(problem.label||problem.id)+' — '+problem.message));this.assistant.append(issues)}
  }
  mount(host,onFork){
   this.host=host;host.editorOwner=this;this.onFork=onFork;host.replaceChildren();host.classList.add('description-editor');
   const toolbar=node('div',undefined,'description-editor-toolbar'),label=node('label','Titre interne');this.title=node('input');this.title.value=this.doc.title;this.title.maxLength=160;this.title.addEventListener('input',()=>{this.doc.title=this.title.value;this.changed()});label.append(this.title);
   this.undoButton=action('Annuler',()=>this.undo());this.redoButton=action('Rétablir',()=>this.undo(true));this.saveButton=action('Enregistrer maintenant',()=>this.save());
   toolbar.append(label,action('Importer par collage',async()=>{const value=await dialog('Coller une description complète','',true);if(value!==null)this.apply(value,{imported:true})}),this.undoButton,this.redoButton,this.saveButton);
   this.status=node('p',undefined,'description-editor-status');this.status.setAttribute('role','status');this.status.setAttribute('aria-live','polite');this.count=node('span');this.localWarning=node('p',undefined,'description-problems');this.recoveryBox=node('div');
   this.conflict=node('div',undefined,'description-conflict');this.conflict.append(node('p','Votre texte reste ici. La version enregistrée ailleurs n’a pas été remplacée.'),action('Voir la version serveur',()=>this.serverVersion()),action('Enregistrer ma copie',()=>this.fork()),action('Recharger la version serveur',()=>this.reload()));
   const layout=node('div',undefined,'description-editor-layout'),left=node('div'),right=node('aside');this.area=node('textarea',undefined,'description-editor-text');this.area.value=this.doc.text;this.area.setAttribute('aria-label','Texte de la description');this.area.spellcheck=true;
   this.area.setSelectionRange(S.toUTF16(this.doc.text,this.selection.start),S.toUTF16(this.doc.text,this.selection.end));
   const selection=()=>{this.selection={start:S.toPoint(this.area.value,this.area.selectionStart),end:S.toPoint(this.area.value,this.area.selectionEnd,true)}};
   this.area.addEventListener('select',selection);this.area.addEventListener('click',selection);this.area.addEventListener('keyup',selection);
   this.area.addEventListener('beforeinput',event=>{selection();this.pasteAll=event.inputType==='insertFromPaste'&&this.selection.start===0&&this.selection.end===S.points(this.doc.text).length});
   this.area.addEventListener('input',()=>{const next={start:S.toPoint(this.area.value,this.area.selectionStart),end:S.toPoint(this.area.value,this.area.selectionEnd,true)};this.apply(this.area.value,{selection:next,imported:!!this.pasteAll,write:false});this.pasteAll=false});
   this.area.addEventListener('compositionstart',()=>{this.composing=true;clearTimeout(this.timer)});this.area.addEventListener('compositionend',()=>{this.composing=false;this.timer=setTimeout(()=>this.save(),700)});
   this.area.addEventListener('keydown',event=>{if(!event.isComposing&&(event.ctrlKey||event.metaKey)&&['z','y'].includes(event.key.toLowerCase())){event.preventDefault();this.undo(event.shiftKey||event.key.toLowerCase()==='y')}});
   left.append(this.area);const separator=node('div',undefined,'description-editor-separator');separator.tabIndex=0;separator.setAttribute('role','separator');separator.setAttribute('aria-orientation','vertical');separator.setAttribute('aria-label','Largeur de l’éditeur');separator.setAttribute('aria-valuemin','45');separator.setAttribute('aria-valuemax','80');
   const resize=value=>{this.ratio=Math.max(45,Math.min(80,value));layout.style.gridTemplateColumns=`minmax(0,${this.ratio}fr) 8px minmax(280px,${100-this.ratio}fr)`;separator.setAttribute('aria-valuenow',String(Math.round(this.ratio)))};resize(this.ratio);
   separator.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight'].includes(event.key)){event.preventDefault();resize(this.ratio+(event.key==='ArrowLeft'?-2:2))}});
   separator.addEventListener('pointerdown',event=>{event.preventDefault();separator.setPointerCapture(event.pointerId);const move=e=>{const rect=layout.getBoundingClientRect();resize(100*(e.clientX-rect.left)/rect.width)};const done=()=>{separator.removeEventListener('pointermove',move);separator.removeEventListener('pointerup',done);separator.removeEventListener('pointercancel',done)};separator.addEventListener('pointermove',move);separator.addEventListener('pointerup',done);separator.addEventListener('pointercancel',done)});
   const tabs=node('div',undefined,'description-anchor-actions');tabs.append(action('Analyse et catalogue',()=>{this.mode='analysis';this.paint()}),action('Sections',()=>{this.mode='sections';this.paint()}),action('Aperçu du texte',()=>{this.mode='preview';this.paint()}));this.assistant=node('div',undefined,'description-assistant-content');right.append(node('h2','Assistant de rédaction'),node('p','Les URL collées restent intactes. Un lien marchand inséré directement ne fournit pas de statistiques de clics LinKs.','muted'),tabs,this.assistant);
   const workflow=node('div',undefined,'description-workflow-toolbar');
   layout.append(left,separator,right);host.append(toolbar,workflow,this.status,this.count,this.localWarning,this.conflict,this.recoveryBox,layout);this.workflow.mount(workflow);this.paint();
  }
 }
 async function mount(host,id,onFork){
  host.textContent='Chargement du brouillon…';const token=crypto.randomUUID();host.dataset.editorRequest=token;
  try{let state=states.get(id);if(!state){const response=await request('drafts/'+id);state=states.get(id)||new Editor(response.document,response.instance_id);states.set(id,state)}if(host.isConnected&&host.dataset.editorRequest===token)state.mount(host,onFork)}catch(error){if(host.isConnected&&host.dataset.editorRequest===token)host.replaceChildren(node('p',error.message),action('Réessayer',()=>mount(host,id,onFork)))}
 }
 window.addEventListener('beforeunload',event=>{let pending=false;for(const state of states.values()){state.persist();if(state.dirty()||state.saving)pending=true}if(pending){event.preventDefault();event.returnValue=''}});
 window.addEventListener('pagehide',()=>{for(const state of states.values())state.persist()});
 window.addEventListener('online',()=>{for(const state of states.values())state.save()});
 window.addEventListener('storage',()=>{for(const state of states.values())if(state.host?.isConnected)state.paint()});
 return {mount};
})();
