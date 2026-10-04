"use strict";
// Uses the same SVG paths and public renderer as cards, themes and the live header.
window.LinksShortcuts=(()=>{
 const form=document.getElementById('button-form'),gridForm=form.querySelector('.form-grid');
 const el=(tag,content)=>{const n=document.createElement(tag);if(content)n.textContent=content;return n};
 const btn=(label,run)=>{const b=el('button',label);b.type='button';b.onclick=run;return b};
 const layout=el('div');layout.className='shortcut-editor';gridForm.before(layout);const controls=el('div');controls.append(gridForm);layout.append(controls);
 const select=form.elements.icon;select.closest('label').classList.add('wide');
 const selected=el('div');selected.className='shortcut-selected';select.closest('label').after(selected);
 const search=el('input');search.type='search';search.placeholder='Rechercher une icône';search.setAttribute('aria-label','Rechercher une icône');
 const grid=el('div');grid.className='shortcut-icon-grid';selected.after(search,grid);
 const personal=el('div');personal.className='shortcut-file';const upload=el('input');upload.type='file';upload.accept='image/png,image/jpeg,image/webp,image/gif';upload.setAttribute('aria-label','Importer une icône personnelle');
 personal.append(el('h3','Icône personnalisée'),el('p','Image carrée, fond transparent si possible. PNG, JPEG, WebP ou GIF · 1 Mo maximum.'),upload,btn('Supprimer l’icône personnelle',()=>{guard.invalidate();form.elements.custom_icon.value='';upload.value='';refresh()}));grid.after(personal);
 form.elements.url.placeholder='https://… · mailto:… · tel:… · #section';form.elements.url.closest('label').firstChild.textContent='Destination';
 const preview=el('aside');preview.className='shortcut-preview';preview.dataset.device='desktop';preview.append(el('h3','Aperçu public'));
 const devices=el('div');devices.className='shortcut-device';for(const [id,label] of [['desktop','Desktop'],['mobile','Mobile']])devices.append(btn(label,()=>{preview.dataset.device=id;frame.style.maxWidth=id==='mobile'?'390px':''}));preview.append(devices);
 const frame=el('iframe');frame.title='Aperçu public du raccourci';frame.setAttribute('sandbox','allow-same-origin');preview.append(frame,el('small','Thème public actif · actions désactivées'));layout.append(preview);
 let appearance=null,sequence=0;
 const guard=LinksUploads.create(form,{statusHost:personal,active:()=>document.getElementById('button-dialog').open,purpose:'icon'});
 document.getElementById('button-dialog').addEventListener('close',()=>{sequence++;guard.invalidate()});
 document.getElementById('button-dialog').addEventListener('cancel',()=>{sequence++;guard.invalidate()});

 function item(){return {platform:select.value,custom_icon:form.elements.custom_icon.value,label:form.elements.label.value||LinksIconNames[select.value]||'Raccourci',url:form.elements.url.value||'#preview'}}
 function library(){grid.replaceChildren();for(const [id,label] of Object.entries(LinksIconNames)){if(!label.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()))continue;const b=btn(label,()=>{select.value=id;guard.invalidate();form.elements.custom_icon.value='';refresh()});b.prepend(icon(id));b.setAttribute('aria-label','Icône '+label);b.setAttribute('aria-pressed',String(!form.elements.custom_icon.value&&select.value===id));grid.append(b)}}
 function refresh(){selected.replaceChildren(shortcutIcon(item()),el('span',form.elements.custom_icon.value?'Icône personnelle':LinksIconNames[select.value]));library();const doc=frame.contentDocument;if(!doc?.getElementById('shortcut-preview-row'))return;const a=renderShortcut(item());a.removeAttribute('href');a.removeAttribute('target');a.removeAttribute('data-metric');a.setAttribute('aria-disabled','true');doc.getElementById('shortcut-preview-row').replaceChildren(doc.importNode(a,true));if(appearance)LinksTheme.apply(appearance,doc)}
 search.oninput=library;form.addEventListener('input',refresh);select.addEventListener('change',()=>{guard.invalidate();refresh()});
 upload.onchange=()=>guard.run(upload,url=>{form.elements.custom_icon.value=url;refresh()});
 async function open(){guard.invalidate();const run=++sequence;search.value='';refresh();try{await LinksTheme.ready;const config=await api('/api/public-config');if(run!==sequence)return;appearance=config.appearance;frame.onload=refresh;frame.srcdoc='<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/preview/style.css"><link rel="stylesheet" href="/preview/icons.css"><link rel="stylesheet" href="/preview/theme.css"></head><body><main><header class="profile"><div class="socials" id="shortcut-preview-row"></div></header></main></body></html>'}catch(e){say(e.message,true)}}
 return {open};
})();
