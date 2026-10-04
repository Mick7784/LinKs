"use strict";
window.LinksStorage=(()=>{
 const root=document.getElementById('storage-panel'),status=document.getElementById('storage-status');
 const format=n=>new Intl.NumberFormat('fr-FR',{maximumFractionDigits:1}).format(n/1024/1024)+' Mo';
 function render(data){document.getElementById('storage-summary').textContent=`${format(data.bytes)} utilisés · ${data.used} fichier(s) utilisé(s) · ${data.unused} fichier(s) en corbeille`;
  const list=document.getElementById('storage-files');list.replaceChildren();for(const item of data.items){const row=document.createElement('article');row.className='storage-file';const img=new Image();img.src=item.url;img.alt='';img.loading='lazy';const info=document.createElement('div'),name=document.createElement('strong'),meta=document.createElement('small'),usage=document.createElement('p');name.textContent=item.name;meta.textContent=`${item.type} · ${format(item.size)}`;usage.textContent=item.uses.length?'Utilisé par : '+item.uses.join(', '):'Corbeille · suppression prévue le '+new Date(item.delete_at*1000).toLocaleDateString('fr-FR');info.append(name,meta,usage);row.append(img,info);list.append(row)}
  if(!data.items.length)list.textContent='Aucun fichier personnel uploadé.';root.querySelector('[data-storage="empty"]').disabled=!data.unused;
 }
 async function load(){try{render(await api('/api/storage'));status.textContent=''}catch(e){status.textContent=e.message}}
 for(const button of root.querySelectorAll('[data-storage]'))button.addEventListener('click',async()=>{const action=button.dataset.storage;if(action==='empty'&&!confirm('Supprimer définitivement tous les fichiers de la corbeille ? Les fichiers encore utilisés seront conservés.'))return;const buttons=[...root.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);status.textContent='Vérification des références…';try{const data=await api('/api/storage',{method:'POST',body:JSON.stringify({action})});render(data);status.textContent=action==='empty'?`${data.deleted} fichier(s) supprimé(s).`:`${data.deleted} fichier(s) arrivé(s) à échéance supprimé(s). Les autres fichiers inutilisés restent en corbeille pendant 7 jours.`}catch(e){status.textContent=e.message}finally{buttons.forEach(b=>b.disabled=false);await loadCounts()}});
 async function loadCounts(){try{render(await api('/api/storage'))}catch{}}
 return {load};
})();
