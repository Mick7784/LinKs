"use strict";
// One operation belongs to one editor generation; stale callbacks never touch its successor.
window.LinksUploads=(()=>{
 const groups=new WeakMap();
 function create(scope,{statusHost=scope,active=()=>true,purpose=''}={}){
  let generation=0,pending=false,status;
  let group=groups.get(scope);if(!group){group={guards:[],saved:new Map()};groups.set(scope,group)}
  function sync(){const busy=group.guards.some(g=>g.pending());const targets=[...scope.querySelectorAll('button[type="submit"],button.primary,[data-upload-save]'),...document.querySelectorAll(`button[form="${scope.id}"]`)];
   if(busy){for(const b of targets){if(!group.saved.has(b))group.saved.set(b,b.disabled);b.disabled=true}}
   else{for(const [b,disabled] of group.saved)if(b.isConnected)b.disabled=disabled;group.saved.clear()}
  }
  function show(message,error=false){if(!status?.isConnected){status=document.createElement('p');status.className='upload-status';status.setAttribute('role','status');statusHost.append(status)}status.textContent=message;status.classList.toggle('notice-error',error)}
  const guard={pending:()=>pending,invalidate(){generation++;pending=false;if(status)status.textContent='';sync()},dispose(){guard.invalidate();group.guards=group.guards.filter(g=>g!==guard)},async run(input,apply){const file=input.files?.[0];if(!file)return;const run=++generation;pending=true;sync();show('Import de l’image en cours…');const current=()=>run===generation&&active();
   try{if(!['image/png','image/jpeg','image/webp','image/gif'].includes(file.type))throw Error('PNG, JPEG, WebP ou GIF uniquement.');if(file.size>(purpose==='icon'?1:4)*1024*1024)throw Error(`Image supérieure à ${purpose==='icon'?1:4} Mo.`);
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('Lecture du fichier impossible.'));reader.readAsDataURL(file)});if(!current())return;
    const result=await api('/api/upload',{method:'POST',body:JSON.stringify({type:file.type,data,purpose})});if(!current())return;apply(result.url);show('Image importée. Enregistrez pour l’appliquer.');
   }catch(error){if(current())show(error.message,true)}finally{if(run===generation){pending=false;input.value='';sync()}}
  }};
  group.guards.push(guard);
  scope.addEventListener('submit',event=>{if(pending&&event.submitter?.value!=='cancel'){event.preventDefault();event.stopImmediatePropagation();show('Patientez jusqu’à la fin de l’import.',true)}},true);
  return guard;
 }
 return {create};
})();
