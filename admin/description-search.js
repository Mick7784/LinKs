/* Merchant actions are explicit. Only draft state is persisted; no link is created. */
window.LinksDescriptionSearch=(()=>{'use strict';
 const merchants=['domadoo','amazon'],names={domadoo:'Domadoo',amazon:'Amazon'};
 const labels={existing:'Lien existant',found:'Produit trouvé',search_required:'Recherche nécessaire',amazon_link_required:'Lien Amazon à fournir',no_match:'Aucune correspondance',error:'Erreur de recherche',searching:'Recherche en cours…'};
 const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el};
 const button=(label,fn)=>{const b=node('button',label);b.type='button';b.addEventListener('click',fn);return b};
 const stored=doc=>doc.selections?.merchant_search?.products||{};
 const resolved=value=>!!value?.prepared||['existing','found','no_match'].includes(value?.status);
 const merge=(previous,incoming)=>({...previous,...incoming,...(incoming.status==='error'?{results:previous.results||[]}:{} )});
 const searchURL=(merchant,query)=>merchant==='domadoo'?'https://www.domadoo.fr/fr/recherche?s='+encodeURIComponent(query):'https://www.amazon.fr/s?k='+encodeURIComponent(query);
 const safeURL=raw=>{try{const url=new URL(/^https?:\/\//i.test(raw)?raw:'https://'+raw);return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password?url.href:null}catch{return null}};
 class Panel{
  constructor(analysis){this.analysis=analysis;this.editor=analysis.editor;this.requests=new Map();this.versions=new Map();this.open=new Map();this.batch=false;this.running=new Set();}
  product(id){return this.analysis.result?.products.find(p=>p.id===id)}
  state(product){return stored(this.editor.doc)[product.id]||{query:product.name,merchants:{}}}
  change(product,fn){const d=this.editor.doc;d.analysis_version=1;d.selections.merchant_search={version:1,products:{...stored(d),[product.id]:fn(structuredClone(this.state(product)))}};this.editor.changed()}
  merchantChange(product,merchant,patch){this.change(product,state=>({...state,merchants:{...state.merchants,[merchant]:{...state.merchants[merchant],...patch}}}))}
  next(key){const version=(this.versions.get(key)||0)+1;this.versions.set(key,version);return version}
  async call(path,body,key){const controller=new AbortController();this.requests.get(key)?.abort();this.requests.set(key,controller);const timer=setTimeout(()=>controller.abort(),15000);try{return await this.analysis.request('drafts/'+this.editor.doc.id+'/'+path,body,controller.signal)}finally{clearTimeout(timer);if(this.requests.get(key)===controller)this.requests.delete(key)}}
  async search(product,force=false){
   const initial=this.state(product),targets=force?merchants:merchants.filter(m=>!resolved(initial.merchants[m]));if(!targets.length)return;
   const key=product.id,version=this.next(key),query=initial.query.trim()||product.name,docId=this.editor.doc.id;
   this.open.set(key,true);this.running.add(key);
   this.change(product,state=>({...state,query,merchants:{...state.merchants,...Object.fromEntries(targets.map(m=>[m,{...state.merchants[m],status:'searching',query}]))}}));
   try{
    const response=await this.call('search',{document:this.analysis.input(),product_id:key,query,merchants:targets},key);
    if(this.versions.get(key)!==version||this.editor.doc.id!==docId||!this.product(key)||this.state(product).query!==query)return;
    this.change(product,state=>({...state,merchants:{...state.merchants,...Object.fromEntries(targets.map(m=>[m,merge(state.merchants[m]||{},response.merchants[m])]))}}));
   }catch(error){if(this.versions.get(key)===version&&this.editor.doc.id===docId&&this.product(key))this.change(product,state=>({...state,merchants:{...state.merchants,...Object.fromEntries(targets.map(m=>[m,{...state.merchants[m],status:'error',message:error.message||'Recherche interrompue. Réessayez.'}]))}}))}
   finally{if(this.versions.get(key)===version)this.running.delete(key);this.editor.paint()}
  }
  async all(){if(this.batch||!this.analysis.result)return;this.batch=true;this.editor.paint();const products=[...this.analysis.result.products];try{for(const product of products){if(this.product(product.id))await this.search(product)}}finally{this.batch=false;this.editor.paint()}}
  async prepare(product,merchant,url,linkId=''){
   const key=product.id+':'+merchant,version=this.next(key),docId=this.editor.doc.id;
   this.merchantChange(product,merchant,{url_input:url,message:'Vérification de la destination…'});
   try{
    const before=this.state(product).merchants[merchant];
    const prepared=await this.call('prepare',{document:this.analysis.input(),product_id:product.id,merchant,url,link_id:linkId,label:before.label||''},key);
    const current=this.state(product).merchants[merchant];
    if(this.versions.get(key)!==version||this.editor.doc.id!==docId||!this.product(product.id)||current.url_input!==url)return;
    const place=prepared.placements.length===1?prepared.placements[0]:{};
    this.merchantChange(product,merchant,{prepared,status:prepared.link_id?'existing':'found',message:'Préparation enregistrée dans le brouillon. Aucun lien créé.',
     label:current.label??prepared.label,selected:current.selected??false,link_id:prepared.link_id,source_id:merchant==='amazon'?'':prepared.sources.some(s=>s.id===current.source_id)?current.source_id:prepared.sources.length===1?prepared.sources[0].id:'',
     section_id:current.section_id||place.section_id||'',merchant_id:current.merchant_id||place.merchant_id||''});
   }catch(error){if(this.versions.get(key)===version&&this.editor.doc.id===docId&&this.product(product.id))this.merchantChange(product,merchant,{message:error.message||'Destination non vérifiée. Réessayez.',status:'error'})}
   finally{this.editor.paint()}
  }
  controls(host){const b=button(this.batch?'Recherches en cours…':'Rechercher tous les produits',()=>this.all());b.disabled=this.batch||!this.analysis.result?.products.length;host.append(b)}
  link(label,url){const a=node('a',label,'description-merchant-open');a.href=safeURL(url)||'#';a.target='_blank';a.rel='noopener noreferrer';a.addEventListener('click',()=>{this.editor.persist();this.editor.save()});return a}
  render(product,host){
   const state=this.state(product),details=node('details',undefined,'description-merchant-search');details.dataset.searchProduct=product.id;details.open=!!this.open.get(product.id);
   details.addEventListener('toggle',()=>{if(details.isConnected)this.open.set(product.id,details.open)});details.append(node('summary','Recherche marchande · Domadoo et Amazon'));
   const queryLabel=node('label','Mots-clés'),query=node('input');query.value=state.query;query.maxLength=160;query.dataset.analysisFocus=product.id+'-query';query.setAttribute('aria-label','Mots-clés');
   query.addEventListener('input',()=>{this.next(product.id);this.running.delete(product.id);this.requests.get(product.id)?.abort();this.change(product,s=>({...s,query:query.value}))});queryLabel.append(query);details.append(queryLabel,button('Rechercher à nouveau',()=>this.search(product,true)));
   for(const merchant of merchants){
    const value=state.merchants[merchant]||{},prepared=value.prepared,box=node('details',undefined,'description-merchant');box.dataset.merchant=merchant;const openKey=product.id+':'+merchant;box.open=!!this.open.get(openKey);
    box.addEventListener('toggle',()=>{if(box.isConnected)this.open.set(openKey,box.open)});
    const status=value.status==='searching'&&!this.running.has(product.id)?'Recherche interrompue — relancez':labels[['error','searching','no_match'].includes(value.status)?value.status:prepared?(prepared.link_id?'existing':'found'):value.status||'search_required'];
    box.append(node('summary',names[merchant]+' · '+status));
    box.append(this.link('Ouvrir sur '+names[merchant],searchURL(merchant,state.query||product.name)));
    if(merchant==='domadoo')box.append(node('p','Recherche assistée : choisissez la fiche sur Domadoo puis collez son URL.','muted'));
    else box.append(node('p','Générez officiellement votre lien affilié sur Amazon. Insertion directe, sans statistiques de clics LinKs.','description-analysis-note'));
    if(value.message)box.append(node('p',value.message,value.status==='error'?'description-problems':'muted'));
    if(value.query&&value.query!==state.query)box.append(node('p','Mots-clés modifiés : relancez pour actualiser les correspondances.','muted'));
    for(const candidate of value.results||[]){
     const row=node('div',undefined,'description-merchant-result');row.append(node('strong',candidate.title),node('small','Référence : '+candidate.reference+(candidate.link_id?' · catalogue LinKs':' · à confirmer')),node('code',candidate.url));
     row.append(this.link('Ouvrir la fiche sur '+names[merchant],candidate.url),button('Choisir cette référence',()=>this.prepare(product,merchant,candidate.url,candidate.link_id)));box.append(row);
    }
    const urlLabel=node('label',merchant==='amazon'?'Lien affilié Amazon':'URL de la fiche Domadoo'),url=node('input');url.type='text';url.value=value.url_input||'';url.maxLength=2000;url.dataset.analysisFocus=openKey+'-url';url.setAttribute('aria-label',merchant==='amazon'?'Lien affilié Amazon':'URL de la fiche Domadoo');
    url.addEventListener('input',()=>{this.next(openKey);this.merchantChange(product,merchant,{url_input:url.value})});urlLabel.append(url);
    if(merchant==='amazon')box.append(button('J’ai déjà un lien affilié',()=>{url.focus()}));
    box.append(urlLabel,button('Préparer ce lien',()=>this.prepare(product,merchant,this.state(product).merchants[merchant]?.url_input||'')));
    box.append(button('Aucune correspondance trouvée',()=>this.merchantChange(product,merchant,{status:'no_match',message:'Aucune correspondance signalée manuellement. Les choix précédents restent conservés.'})));
    if(prepared){
     const pending=prepared.original_url!==value.url_input,invalid=pending||!prepared.placements.some(p=>p.section_id===value.section_id&&p.merchant_id===value.merchant_id)||(merchant!=='amazon'&&(!prepared.sources.some(s=>s.id===value.source_id)||(prepared.duplicates.length>0&&!value.link_id)));
     box.append(node('strong','Destination préparée'),node('code',prepared.url));
     if(pending)box.append(node('p','L’URL collée a changé : préparez-la pour remplacer la destination précédente.','description-problems'));
     const check=node('label',undefined,'description-check'),input=node('input');input.type='checkbox';input.checked=!!value.selected&&!invalid;input.disabled=invalid;input.addEventListener('change',()=>this.merchantChange(product,merchant,{selected:input.checked}));check.append(input,node('span','Préparer cette proposition marchande'));box.append(check);
     const titleLabel=node('label','Intitulé marchand'),title=node('input');title.value=value.label??prepared.label;title.maxLength=160;title.dataset.analysisFocus=openKey+'-label';title.addEventListener('input',()=>this.merchantChange(product,merchant,{label:title.value}));titleLabel.append(title);box.append(titleLabel);
     if(prepared.duplicates.length){const label=node('label','Fiche LinKs à réutiliser'),select=node('select');select.setAttribute('aria-label','Fiche LinKs à réutiliser');select.add(new Option('Choisir le lien existant',''));for(const dup of prepared.duplicates){const option=new Option(dup.name+(dup.archived||!dup.enabled?' · indisponible':''),dup.id);option.disabled=!!dup.archived||!dup.enabled;select.add(option)}select.value=value.link_id||'';select.addEventListener('change',()=>{const item=prepared.duplicates.find(d=>d.id===select.value);if(item)this.prepare(product,merchant,item.url,item.id)});label.append(select);box.append(label)}
     if(merchant!=='amazon'){const label=node('label','Source YouTube'),select=node('select');select.setAttribute('aria-label','Source YouTube');select.add(new Option('Choisir une source existante',''));for(const source of prepared.sources)select.add(new Option(source.name+(source.url?' · publication existante':' · publication à préparer'),source.id));select.value=value.source_id||'';select.addEventListener('change',()=>this.merchantChange(product,merchant,{source_id:select.value}));label.append(select);box.append(label);if(!prepared.sources.length)box.append(node('p','Aucune source YouTube disponible. Aucun jeton n’est créé ici.','muted'))}
     const placeLabel=node('label','Sous-section marchande'),place=node('select');place.setAttribute('aria-label','Sous-section marchande');place.add(new Option('Choisir un emplacement',''));for(const p of prepared.placements)place.add(new Option(p.name,p.section_id+'/'+p.merchant_id));place.value=(value.section_id||'')+'/'+(value.merchant_id||'');place.addEventListener('change',()=>{const [section_id='',merchant_id='']=place.value.split('/');this.merchantChange(product,merchant,{section_id,merchant_id})});placeLabel.append(place);box.append(placeLabel);
     if(!prepared.placements.length)box.append(node('p','Aucune sous-section correspondante dans la copie du modèle. Emplacement à résoudre avant application.','muted'));
    }
    details.append(box);
   }
   host.append(details);
  }
 }
 return {Panel,stored,resolved,merge,searchURL};
})();
