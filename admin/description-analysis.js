/* Read-only catalogue analysis; all decisions belong to the draft, never the catalogue. */
window.LinksDescriptionAnalysis=(()=>{'use strict';
 const clone=value=>structuredClone(value),node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el};
 const button=(label,fn)=>{const b=node('button',label);b.type='button';b.addEventListener('click',fn);return b};
 const choices=doc=>doc.selections?.description_analysis||{};
 const ordered=(result,doc)=>[...result.products].sort((a,b)=>{const order=doc.manual_order||[],ia=order.indexOf(a.id),ib=order.indexOf(b.id);return (ia<0?Infinity:ia)-(ib<0?Infinity:ib)||a.position-b.position||a.id.localeCompare(b.id)});
 function effective(proposal,result,doc){
  const stored=choices(doc)[proposal.id]||{},value={...proposal,...stored},errors=[];
  if(proposal.kind==='move'&&Object.hasOwn(choices(doc)[proposal.url_id]||{},'product_id'))value.product_id=choices(doc)[proposal.url_id].product_id;
  if(value.amazon)value.source_id='';
  if(proposal.blocked_reason)errors.push(proposal.blocked_reason);
  const item=result.catalogue.find(i=>i.id===value.link_id);
  if(value.link_id&&(!item||!proposal.matches.some(m=>m.link_id===value.link_id)))errors.push('La correspondance choisie n’est plus disponible pour cette proposition.');
  if(item&&(item.archived||!item.enabled))errors.push('Fiche archivée ou suspendue.');
  if(value.source_id&&(!item||!item.publications.some(p=>p.source_id===value.source_id&&p.active)))errors.push('La source choisie n’est plus disponible.');
  if(value.product_id&&!result.products.some(p=>p.id===value.product_id))errors.push('Le produit associé n’est plus présent.');
  if((result.urls.find(u=>u.id===value.url_id)?.known||{}).revoked)errors.push('Alias LinKs révoqué.');
  return {...value,item,errors,selected:!!value.selected&&!errors.length};
 }
 class Panel{
  constructor(editor,request){this.editor=editor;this.request=request;this.result=null;this.key='';this.sequence=0;this.message='Analyse locale en attente';this.search=new window.LinksDescriptionSearch.Panel(this);}
  input(){const d=this.editor.doc;return {text:d.text,sections:d.sections,...(d.analysis_version===1?{analysis_version:1,products:d.products,selections:d.selections,manual_order:d.manual_order}:{})}}
  signature(){const d=this.editor.doc;return JSON.stringify([d.id,d.text,d.sections,d.products])}
  schedule(force=false){
   const key=this.signature();if(!force&&key===this.key)return;
   this.key=key;this.sequence++;this.controller?.abort();clearTimeout(this.timer);this.result=null;this.message='Analyse locale…';
   this.timer=setTimeout(()=>this.analyze(this.sequence,key),400);
  }
  async analyze(sequence,key){
   const controller=new AbortController();this.controller=controller;const timer=setTimeout(()=>controller.abort(),15000);
   try{const result=await this.request('drafts/'+this.editor.doc.id+'/analyze',this.input(),controller.signal);if(sequence!==this.sequence||key!==this.signature())return;this.result=result;this.message='Analyse locale à jour'}
   catch(error){if(sequence!==this.sequence)return;this.message='Analyse indisponible. Votre texte et vos choix sont conservés.'}
   finally{clearTimeout(timer);if(sequence===this.sequence)this.editor.paint()}
  }
  change(id,patch){const d=this.editor.doc;d.analysis_version=1;d.selections.description_analysis={...choices(d),[id]:{...choices(d)[id],...patch}};this.editor.changed()}
  move(id,destination){
   const ids=ordered(this.result,this.editor.doc).map(p=>p.id),index=ids.indexOf(id);if(index<0||destination<0||destination>=ids.length)return;
   ids.splice(destination,0,ids.splice(index,1)[0]);const d=this.editor.doc;d.analysis_version=1;d.manual_order=[...ids,...d.manual_order.filter(x=>!ids.includes(x))];this.editor.changed();
  }
  render(host){
   const active=document.activeElement,focus=host.contains(active)?{key:active.dataset.analysisFocus,start:active.selectionStart,end:active.selectionEnd}:null;
   for(const key of ['urls','loose']){const existing=host.querySelector('[data-analysis-panel="'+key+'"]');if(existing)this[key+'Open']=existing.open}
   host.replaceChildren();host.append(node('p',this.message,'description-analysis-status'),node('p','Le texte reste inchangé. Les recherches marchandes sont déclenchées uniquement par vos actions.','muted'));
   const controls=node('div',undefined,'description-anchor-actions');
   controls.append(button('Actualiser le catalogue',()=>{this.schedule(true);this.editor.paint()}),button('Ajouter une référence',()=>{const query=prompt('Référence explicitement mentionnée à rechercher');if(!query?.trim()||query.length>160)return;this.editor.doc.analysis_version=1;this.editor.doc.products.push({id:'manual-'+window.LinksUUID(),kind:'manual-reference',query});this.editor.changed()}));this.search.controls(controls);host.append(controls);
   for(const ref of this.editor.doc.products.filter(p=>p.kind==='manual-reference')){
    const row=node('div',undefined,'description-manual-reference'),label=node('label','Référence manuelle'),input=node('input');input.value=ref.query;input.maxLength=160;input.dataset.analysisFocus=ref.id;
    input.addEventListener('input',()=>{ref.query=input.value;this.editor.changed()});label.append(input);row.append(label,button('Retirer cette référence',()=>{this.editor.doc.products=this.editor.doc.products.filter(p=>p.id!==ref.id);this.editor.changed()}));host.append(row);
   }
   if(this.result){
    const result=this.result;for(const warning of result.warnings)host.append(node('p',warning,'muted'));
    const urls=node('details');urls.dataset.analysisPanel='urls';urls.open=!!this.urlsOpen;urls.append(node('summary',result.urls.length+' URL détectée(s) · '+result.urls.filter(u=>u.matches.length||u.known).length+' connue(s)'));
    for(const url of result.urls){const row=node('article',undefined,'description-detected-url');row.dataset.urlId=url.id;row.append(node('strong',url.kind==='links'?'Lien LinKs enregistré':url.kind==='other'?'Autre destination':url.kind),node('code',url.url),node('small',url.occurrences.length+' occurrence(s) · '+(url.matches.length?'Lien connu dans LinKs':url.known?.campaign_id?'Campagne existante':'Destination non retrouvée dans le catalogue')));urls.append(row)}host.append(urls);
    const rows=result.proposals.map(p=>effective(p,result,this.editor.doc)),products=ordered(result,this.editor.doc);
    const loose=rows.filter(p=>!products.some(product=>product.id===p.product_id));
    if(loose.length){const box=node('details');box.dataset.analysisPanel='loose';box.open=!!this.looseOpen;box.append(node('summary','Liens sans produit associé ('+loose.length+')'));for(const row of loose)box.append(this.proposal(row));host.append(box)}
    host.append(node('h3',products.length+' référence(s) explicite(s)'));
    products.forEach((product,index)=>{
     const card=node('article',undefined,'description-product');card.dataset.productId=product.id;card.append(node('strong',product.name));
     const exact=product.matches.filter(m=>m.confidence==='exact');card.append(node('small',exact.length===1?'Nom retrouvé dans LinKs':product.matches.length?'Correspondances possibles — choix manuel':'Référence à préciser / à rechercher ultérieurement'));
     const order=node('div',undefined,'description-anchor-actions'),grip=button('⠿',()=>{});grip.draggable=true;grip.setAttribute('aria-label','Déplacer '+product.name);
     grip.addEventListener('dragstart',e=>e.dataTransfer.setData('text/plain',product.id));card.addEventListener('dragover',e=>e.preventDefault());card.addEventListener('drop',e=>{e.preventDefault();this.move(e.dataTransfer.getData('text/plain'),index)});
     grip.addEventListener('keydown',e=>{if(['ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();this.move(product.id,index+(e.key==='ArrowUp'?-1:1))}});
     const up=button('↑',()=>this.move(product.id,index-1)),down=button('↓',()=>this.move(product.id,index+1));up.disabled=index===0;down.disabled=index===products.length-1;up.setAttribute('aria-label','Monter '+product.name);down.setAttribute('aria-label','Descendre '+product.name);order.append(grip,up,down);card.append(order);
     if(product.evidence.length)card.append(button('Voir la mention',()=>{this.editor.selection=clone(product.evidence[0]);this.editor.writeArea()}));
     this.search.render(product,card);
     for(const row of rows.filter(p=>p.product_id===product.id))card.append(this.proposal(row));
     const candidates=node('details');candidates.append(node('summary','Correspondances dans le catalogue ('+product.matches.length+')'));
     for(const match of product.matches){const item=result.catalogue.find(i=>i.id===match.link_id);candidates.append(node('p',item.name+' · '+this.merchant(item.merchant)+' · '+(match.confidence==='exact'?'nom identique':'incertain')))}card.append(candidates);host.append(card);
    });
    const inactive=Object.keys(choices(this.editor.doc)).filter(id=>!result.proposals.some(p=>p.id===id));if(inactive.length)host.append(node('p',inactive.length+' choix devenu(s) obsolète(s), conservé(s) en mémoire sans proposition active.','muted'));
   }
   if(focus?.key){const input=[...host.querySelectorAll('[data-analysis-focus]')].find(el=>el.dataset.analysisFocus===focus.key);if(input){input.focus();if(typeof focus.start==='number')input.setSelectionRange(focus.start,focus.end)}}
  }
  merchant(key){return this.result.partners.find(p=>p.id===key)?.name||({amazon:'Amazon',domadoo:'Domadoo',youtube:'YouTube'}[key])||key||'Destination'}
  proposal(value){
   const row=node('fieldset',undefined,'description-proposal');row.dataset.proposalId=value.id;row.dataset.operation=value.kind;
   row.append(node('legend',value.kind==='move'?'Déplacement proposé séparément':value.kind==='add'?'Ajout · '+this.merchant(value.merchant):'Lien présent · réutilisation / remplacement'));
   const check=node('label',undefined,'description-check'),input=node('input');input.type='checkbox';input.checked=value.selected;input.disabled=!!value.errors.length;input.addEventListener('change',()=>this.change(value.id,{selected:input.checked}));check.append(input,node('span',value.kind==='move'?value.label:'Préparer cette proposition'));row.append(check);
   if(value.kind==='move'){row.append(node('p','Décoché par défaut. Aucune ligne n’est déplacée.','muted'));return row}
   const url=this.result.urls.find(u=>u.id===value.url_id);row.append(node('code',url?.url||value.item?.url||''));
   const label=node('label','Intitulé dans cette description'),title=node('input');title.value=value.label||'';title.maxLength=160;title.dataset.analysisFocus=value.id+'-label';title.addEventListener('input',()=>this.change(value.id,{label:title.value}));label.append(title);row.append(label);
   const choose=node('label','Fiche existante'),select=node('select');select.setAttribute('aria-label','Fiche existante');select.add(new Option('Choisir une correspondance',''));for(const match of value.matches){const item=this.result.catalogue.find(i=>i.id===match.link_id);select.add(new Option(item.name+' · '+this.merchant(item.merchant)+(match.confidence==='possible'?' · incertain':''),item.id))}select.value=value.link_id;select.addEventListener('change',()=>this.change(value.id,{link_id:select.value,source_id:''}));choose.append(select);row.append(choose);
   if(value.amazon)row.append(node('p','Amazon : URL fournie conservée exactement, insertion directe uniquement, sans statistiques de clics LinKs.','description-analysis-note'));
   else if(value.item){
    const source=node('label','Source de publication existante'),options=node('select');options.setAttribute('aria-label','Source de publication existante');options.add(new Option('Choisir une source déjà enregistrée',''));
    for(const p of value.item.publications){const option=new Option(p.source_name+(p.youtube?' · YouTube':' · autre source')+(p.active?'':' · indisponible'),p.source_id);option.disabled=!p.active;options.add(option)}options.value=value.source_id;options.addEventListener('change',()=>this.change(value.id,{source_id:options.value}));source.append(options);row.append(source);
    const selected=value.item.publications.find(p=>p.source_id===value.source_id&&p.active);if(selected)row.append(node('code',selected.url));else row.append(node('p','Aucun lien de publication choisi. Aucun jeton ne sera créé pendant cette analyse.','muted'));
   }
   if(value.kind==='reuse'){
    const group=node('label','Associer au produit'),options=node('select');options.setAttribute('aria-label','Associer au produit');options.add(new Option('Sans association',''));for(const product of this.result.products)options.add(new Option(product.name,product.id));options.value=value.product_id||'';options.addEventListener('change',()=>this.change(value.id,{product_id:options.value}));group.append(options);row.append(group);
   }
   for(const error of value.errors)row.append(node('p',error,'description-problems'));
   if(value.matches.length>1&&!value.link_id)row.append(node('p','Plusieurs fiches correspondent. Choisissez explicitement la fiche à conserver.','muted'));
   return row;
  }
 }
 return {Panel,effective,ordered};
})();
