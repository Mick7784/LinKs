"use strict";
window.LinksStorage=(()=>{
 const root=document.getElementById('storage-panel'),status=document.getElementById('storage-status');
 const names={campaigns:'Campagnes',links:'Liens',profile:'Profil',themes:'Thèmes',icons:'Icônes',other:'Autres'};
 const format=n=>new Intl.NumberFormat('fr-FR',{maximumFractionDigits:1}).format(n/(n>=1024*1024?1024*1024:1024))+(n>=1024*1024?' Mo':' Ko');
 const chart=document.createElement('div');chart.className='storage-breakdown';document.getElementById('storage-summary').after(chart);
 const filters=document.createElement('div');filters.className='storage-filters';const category=document.createElement('select'),stateFilter=document.createElement('select');category.setAttribute('aria-label','Catégorie de fichiers');category.add(new Option('Toutes les catégories',''));for(const [id,name] of Object.entries(names))category.add(new Option(name,id));stateFilter.setAttribute('aria-label','Utilisation des fichiers');for(const [id,name] of [['','Tous les fichiers'],['used','Utilisés'],['trash','Corbeille']])stateFilter.add(new Option(name,id));filters.append(category,stateFilter);document.getElementById('storage-files').before(filters);
 let current;
 function files(){const list=document.getElementById('storage-files');list.replaceChildren();for(const item of current.items.filter(x=>(!category.value||x.categories.includes(category.value))&&(!stateFilter.value||Boolean(x.uses.length)===(stateFilter.value==='used')))){
  const row=document.createElement('article');row.className='storage-file';const img=new Image();img.src=item.url;img.alt='';img.loading='lazy';img.onerror=()=>{img.hidden=true};
  const info=document.createElement('div'),name=document.createElement('strong'),meta=document.createElement('small'),usage=document.createElement('p');name.textContent=item.name;meta.textContent=`${item.type} · ${format(item.size)} · ${new Date(item.created_at*1000).toLocaleDateString('fr-FR')} · ${item.categories.map(x=>names[x]).join(', ')}`;usage.textContent=item.uses.length?'Utilisé par : '+item.uses.join(', '):'Corbeille · suppression prévue le '+new Date(item.delete_at*1000).toLocaleDateString('fr-FR');info.append(name,meta,usage);row.append(img,info);list.append(row)
 }if(!list.children.length)list.textContent='Aucun fichier correspondant.'}
 category.onchange=files;stateFilter.onchange=files;
 function render(data){current=data;document.getElementById('storage-summary').textContent=`${format(data.bytes)} utilisés · ${data.used} fichier(s) utilisé(s) · ${data.unused} fichier(s) en corbeille (${format(data.trash_bytes)})`;
  chart.replaceChildren();for(const [id,name] of Object.entries(names)){const row=document.createElement('div'),label=document.createElement('span'),bar=document.createElement('progress');label.textContent=`${name} · ${format(data.categories[id])}`;bar.max=data.bytes||1;bar.value=data.categories[id];bar.setAttribute('aria-label',name+' : part du stockage');row.append(label,bar);chart.append(row)}
  files();root.querySelector('[data-storage="empty"]').disabled=!data.unused;
 }
 async function load(){try{render(await api('/api/storage'));status.textContent=''}catch(e){status.textContent=e.message}}
 for(const button of root.querySelectorAll('[data-storage]'))button.addEventListener('click',async()=>{const action=button.dataset.storage;if(action==='empty'&&!confirm('Supprimer définitivement tous les fichiers de la corbeille ? Les fichiers encore utilisés seront conservés.'))return;const buttons=[...root.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);status.textContent='Vérification des références…';try{const data=await api('/api/storage',{method:'POST',body:JSON.stringify({action})});render(data);status.textContent=action==='empty'?`${data.deleted} fichier(s) supprimé(s).`:`${data.deleted} fichier(s) arrivé(s) à échéance supprimé(s). Les autres fichiers inutilisés restent en corbeille pendant 7 jours.`}catch(e){status.textContent=e.message}finally{buttons.forEach(b=>b.disabled=false);if(current)root.querySelector('[data-storage="empty"]').disabled=!current.unused}});
 return {load,format};
})();
