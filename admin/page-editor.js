"use strict";
window.LinksPageEditor=(()=>{
 const frame=document.getElementById('page-editor-frame'),host=document.getElementById('page-editor-preview'),status=document.getElementById('page-editor-status'),save=document.getElementById('page-editor-save'),cancel=document.getElementById('page-editor-cancel');
 const sections={classic:['links-section','Liens permanents'],highlight:['offers','Campagnes'],video:['latest-video','Dernière vidéo YouTube']};
 let baseline,draft,dirty=false,busy=false,generation=0,observer,resize;
 const clone=value=>JSON.parse(JSON.stringify(value));
 function update(){
  dirty=!!baseline&&JSON.stringify([draft.section_order,draft.link_ids])!==JSON.stringify([baseline.section_order,baseline.link_ids]);
  save.disabled=busy||!dirty;cancel.disabled=busy||!baseline;
  status.textContent=busy?'Chargement…':dirty?'Modifications non enregistrées':'Organisation enregistrée';
  frame.style.pointerEvents=busy?'none':'';
 }
 function controls(doc,label,kind){
  const bar=doc.createElement('div');bar.className='layout-controls';
  const title=doc.createElement('span');title.textContent=label;bar.append(title);
  for(const [action,text,description] of [['drag','⠿','Déplacer'],['up','↑','Monter'],['down','↓','Descendre']]){
   const button=doc.createElement('button');button.type='button';button.textContent=text;button.dataset.layoutAction=action;button.setAttribute('aria-label',`${description} ${kind} ${label}`);button.title=action==='drag'?'Glisser ou utiliser les touches ↑ et ↓':`${description} ${label}`;bar.append(button);
  }
  return bar;
 }
 function nodes(kind){return [...frame.contentDocument.querySelectorAll(kind==='section'?'[data-layout-section]':'[data-layout-link]')]}
 function key(node){return node.dataset.layoutSection||node.dataset.layoutLink}
 function refreshButtons(){
  for(const kind of ['section','link']){const items=nodes(kind);items.forEach((node,index)=>{const bar=node.querySelector(':scope>.layout-controls');bar.querySelector('[data-layout-action=up]').disabled=index===0;bar.querySelector('[data-layout-action=down]').disabled=index===items.length-1})}
 }
 function remember(){
  draft.section_order=nodes('section').map(key);
  // Invisible/disabled links retain their slots; only rendered links move.
  const visible=nodes('link').map(key),ids=new Set(visible);let index=0;
  draft.link_ids=draft.link_ids.map(id=>ids.has(id)?visible[index++]:id);
  update();refreshButtons();
 }
 function arrange(){
  const doc=frame.contentDocument,footer=doc.querySelector('main>footer');
  for(const id of draft.section_order)footer.before(doc.getElementById(sections[id][0]));
  const links=doc.getElementById('links'),items=new Map(nodes('link').map(node=>[key(node),node]));
  for(const id of draft.link_ids)if(items.has(id))links.append(items.get(id));
  refreshButtons();
 }
 function move(node,direction,handle){
  const kind=node.dataset.layoutSection?'section':'link',items=nodes(kind),index=items.indexOf(node),other=items[index+direction];
  if(!other)return;
  if(direction<0)other.before(node);else other.after(node);
  remember();(handle?.disabled?node.querySelector(':scope>.layout-controls [data-layout-action=drag]'):handle)?.focus();
 }
 function decorate(doc){
  for(const [id,[domId,label]] of Object.entries(sections)){
   const node=doc.getElementById(domId);node.dataset.layoutSection=id;
   if(!node.querySelector(':scope>.layout-controls'))node.prepend(controls(doc,label,'la section'));
   const empty=id==='classic'?!doc.querySelector('#links>a,#links>.layout-link'):id==='highlight'?!doc.querySelector('#offers-track .carousel-slide'):!node.querySelector('.video-card');
   node.hidden=false;node.classList.toggle('layout-empty',empty);
   let note=node.querySelector(':scope>.layout-empty-note');
   if(empty&&!note){note=doc.createElement('p');note.className='layout-empty-note';note.textContent='Aucun contenu affiché actuellement. La position de cette section est conservée.';node.append(note)}else if(!empty)note?.remove();
  }
  for(const card of doc.querySelectorAll('#links>a[data-metric]')){
   const id=card.dataset.metric.replace(/^block:/,'');if(!draft.link_ids.includes(id))continue;
   const wrapper=doc.createElement('div');wrapper.className='layout-link';wrapper.dataset.layoutLink=id;card.before(wrapper);wrapper.append(controls(doc,card.querySelector('.card-title')?.textContent||'Lien','le lien'),card);
  }
  arrange();
 }
 function bind(doc){
  const itemFor=handle=>handle.closest('.layout-controls').parentElement;
  doc.addEventListener('click',event=>{
   if(event.target.closest('a'))event.preventDefault();
   const button=event.target.closest('[data-layout-action]');if(!button||busy)return;
   if(button.dataset.layoutAction!=='drag')move(itemFor(button),button.dataset.layoutAction==='up'?-1:1,button);
  });
  doc.addEventListener('keydown',event=>{
   const handle=event.target.closest('[data-layout-action=drag]');
   if(handle&&['ArrowUp','ArrowDown'].includes(event.key)&&!busy){event.preventDefault();move(itemFor(handle),event.key==='ArrowUp'?-1:1,handle)}
  });
  doc.addEventListener('pointerdown',event=>{
   const handle=event.target.closest('[data-layout-action=drag]');if(!handle||event.button!==0||busy)return;
   event.preventDefault();handle.focus();const node=itemFor(handle),kind=node.dataset.layoutSection?'section':'link',before=clone(draft);node.classList.add('layout-dragging');handle.setPointerCapture?.(event.pointerId);
   const moving=e=>{
    if(e.pointerId!==event.pointerId)return;e.preventDefault();
    const target=doc.elementFromPoint(e.clientX,e.clientY)?.closest(kind==='section'?'[data-layout-section]':'[data-layout-link]');
    if(target&&target!==node){const box=target.getBoundingClientRect();if(e.clientY<box.top+box.height/2)target.before(node);else target.after(node)}
    const frameTop=frame.getBoundingClientRect().top,y=frameTop+e.clientY;if(y<100)window.scrollBy(0,-18);else if(y>innerHeight-100)window.scrollBy(0,18);
   };
   const finish=e=>{if(e.pointerId!==event.pointerId)return;cleanup();remember();handle.focus()};
   const abort=()=>{cleanup();draft=before;arrange();update()};
   const cleanup=()=>{node.classList.remove('layout-dragging');doc.removeEventListener('pointermove',moving);doc.removeEventListener('pointerup',finish);doc.removeEventListener('pointercancel',abort)};
   doc.addEventListener('pointermove',moving,{passive:false});doc.addEventListener('pointerup',finish);doc.addEventListener('pointercancel',abort,{once:true});
  });
 }
 function build(html,config,request){
  observer?.disconnect();resize?.disconnect();
  config=clone(config);config.analytics_enabled=false;config.profile.analytics_enabled=false;config.preview=true;
  frame.onload=()=>{
   if(request!==generation)return;
   const doc=frame.contentDocument;doc.documentElement.dataset.editorTheme=document.documentElement.dataset.theme;
   frame.contentWindow.LINKS_PREVIEW_CONFIG=config;
   const css=doc.createElement('link');css.rel='stylesheet';css.href='/page-editor-preview.css';doc.head.append(css);
   frame.contentWindow.addEventListener('links:rendered',()=>{
    if(request!==generation)return;
    decorate(doc);bind(doc);busy=false;update();
    const video=doc.getElementById('latest-video');observer=new MutationObserver(()=>{if(video.hidden)video.hidden=false;if(video.querySelector('.video-card')){video.classList.remove('layout-empty');video.querySelector('.layout-empty-note')?.remove()}});observer.observe(video,{childList:true,attributes:true,attributeFilter:['hidden']});
    resize=new ResizeObserver(()=>{frame.style.height=Math.ceil(doc.querySelector('main').getBoundingClientRect().height+4)+'px'});resize.observe(doc.querySelector('main'));
   },{once:true});
   const script=doc.createElement('script');script.src='/preview/app.js';doc.body.append(script);
  };
  frame.srcdoc=html.replace(/<script src="(?:app|metrics)\.js" defer><\/script>/g,'').replace(/(src|href)="(?!\/|https:)([^"]+)"/g,'$1="/preview/$2"');
 }
 async function load(force=false){
  if(!force&&(busy||dirty))return;
  const request=++generation;busy=true;update();
  try{
   const [layout,config,response]=await Promise.all([api('/api/page-layout'),api('/api/public-config'),fetch('/preview/index.html')]);
   if(!response.ok)throw Error('Aperçu indisponible.');const html=await response.text();if(request!==generation)return;
   baseline=clone(layout);draft=clone(layout);build(html,config,request);
  }catch(error){if(request===generation){busy=false;update();status.textContent=error.message;say(error.message,true)}}
 }
 save.onclick=async()=>{
  if(busy||!dirty)return;busy=true;update();
  try{baseline=await api('/api/page-layout',{method:'POST',body:JSON.stringify(draft)});draft=clone(baseline);say('Organisation de la page publique enregistrée.')}catch(error){say(error.message,true)}finally{busy=false;update()}
 };
 cancel.onclick=()=>load(true);
 document.querySelectorAll('[data-layout-device]').forEach(button=>button.onclick=()=>{host.dataset.device=button.dataset.layoutDevice;document.querySelectorAll('[data-layout-device]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)))});
 new MutationObserver(()=>{if(frame.contentDocument?.documentElement)frame.contentDocument.documentElement.dataset.editorTheme=document.documentElement.dataset.theme}).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
 window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue=''}});
 return {load};
})();
