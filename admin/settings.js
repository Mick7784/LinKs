"use strict";
window.LinksSettings=(()=>{
 const nav=document.getElementById('settings-nav'),grid=document.querySelector('.settings-grid');
 const sections=[['overview','Vue d’ensemble','settings-overview'],['general','Général','settings-form'],['integrations','Intégrations','youtube-form'],['statistics','Statistiques','analytics-panel'],['security','Accès & sécurité','access-form'],['quotes','Citations','quotes-panel'],['sharing','Partage','sharing-panel'],['storage','Stockage','storage-panel'],['maintenance','Sauvegarde & maintenance','backup-panel']];
 const technical=grid.querySelector('.technical-settings'),maintenance=document.createElement('div');maintenance.id='settings-maintenance';grid.append(maintenance);maintenance.append(document.getElementById('backup-panel'),technical);sections.at(-1)[2]=maintenance.id;
 let active='overview',sequence=0;
 const mobile=document.createElement('select');mobile.className='settings-mobile-nav';mobile.setAttribute('aria-label','Section des réglages');
 for(const [id,label,panel] of sections){mobile.add(new Option(label,id));const button=document.createElement('button');button.type='button';button.textContent=label;button.dataset.settingsSection=id;button.setAttribute('aria-controls',panel);button.onclick=()=>show(id);nav.append(button);document.getElementById(panel).hidden=true}
 nav.before(mobile);mobile.onchange=()=>show(mobile.value);
 async function overview(run){
  const cards=document.getElementById('settings-cards');cards.textContent='Chargement des statuts…';
  try{const data=await api('/api/settings/overview');if(run!==sequence)return;cards.replaceChildren();
   for(const [id,label,value] of [['general','Identité',data.identity?'Configurée':'À configurer'],['integrations','YouTube',data.youtube?'Configuré':'Non configuré'],['statistics','Statistiques',data.analytics?'Actives':'Inactives'],['storage','Stockage',window.LinksStorage.format(data.storage.bytes)],['storage','Corbeille',`${data.storage.unused} fichier(s) · ${window.LinksStorage.format(data.storage.trash_bytes)}`],['quotes','Citations',String(data.quotes)],['maintenance','Installation',state.settings.app_version||'Version indisponible']]){
    const button=document.createElement('button'),title=document.createElement('span'),status=document.createElement('strong');button.className='settings-card';title.textContent=label;status.textContent=value;button.append(title,status);button.onclick=()=>show(id);cards.append(button)
   }
  }catch(e){if(run===sequence)cards.textContent=e.message}
 }
 async function show(id){
  if(!sections.some(x=>x[0]===id))id='overview';active=id;const run=++sequence;mobile.value=id;
  for(const [key,,panel] of sections)document.getElementById(panel).hidden=key!==id;
  nav.querySelectorAll('button').forEach(b=>{if(b.dataset.settingsSection===id)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});
  try{if(id==='overview')await overview(run);if(id==='integrations')await loadYouTube();if(id==='quotes')await loadQuotes();if(id==='storage')await window.LinksStorage.load()}catch(e){say(e.message,true)}
 }
 // Initialization configures visibility without fetching a hidden Settings view.
 for(const [id,,panel] of sections)document.getElementById(panel).hidden=id!=='overview';nav.firstElementChild.setAttribute('aria-current','page');
 return {open:()=>show(active),show};
})();
