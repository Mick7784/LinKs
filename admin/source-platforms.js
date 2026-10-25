/* Analytical view only: every source keeps its original key and contribution. */
"use strict";
(function(root){
 const labels={youtube:"YouTube",instagram:"Instagram",facebook:"Facebook",tiktok:"TikTok",discord:"Discord",google:"Google",linkedin:"LinkedIn",twitter:"X / Twitter",telegram:"Telegram",newsletter:"Newsletter",mail:"E-mail",site:"Site",qr:"QR",other:"Autres",unknown:"Source inconnue"};
 const normal=value=>String(value||"").normalize("NFKC").trim().toLocaleLowerCase("fr").replace(/\s+/g," ");
 const aliases=new Map();
 for(const [key,label] of Object.entries(labels))if(!["unknown","other"].includes(key))aliases.set(normal(label),key);
 for(const [key,names] of Object.entries({youtube:["YouTube Post","YouTube Description"],instagram:["Instagram Story","Instagram Bio"],facebook:["Facebook Post","Facebook Story","Facebook Groupe"],tiktok:["TikTok Bio","TikTok Vidéo"],discord:["Discord Message","Discord Annonce"],twitter:["Twitter","X","Twitter Post","X Post"],linkedin:["LinkedIn Post"],telegram:["Telegram Message"],other:["Autre / Direct","Autres"],mail:["Email","E-mail"]}))for(const name of names)aliases.set(normal(name),key);
 const uncertain=new Set(["instagram-story","shared-unknown","direct-inconnu"]);
 function identify(source,records){
  const key=String(source.key),record=key.startsWith("tracked:")?records.get(key.slice(8)):records.get(key);
  if(uncertain.has(key))return "unknown";
  if(record?.platform)return Object.hasOwn(labels,record.platform)?record.platform:"other";
  if(Object.hasOwn(labels,key))return key;
  if(["autre-site","autre-campagne"].includes(key))return "other";
  const name=record?.name||source.label;
  if(aliases.has(normal(name)))return aliases.get(normal(name));
  if(!name||["source inconnue","lien partagé (source inconnue)","ancien lien partagé (source incertaine)","ancien lien partagé"].includes(normal(name))||String(name)===key&&/^(?:track[.:]|tracked:|src_|[a-f0-9]{32}$)/i.test(key))return "unknown";
  return "other";
 }
 function group(sources,metadata=[]){
  const records=new Map(metadata.map(row=>[row.id,row])),groups=new Map();
  for(const source of sources){
   const key=identify(source,records),entry=groups.get(key)||{key,label:labels[key],total:0,sources:new Map()};
   const member=entry.sources.get(source.key)||{...source,total:0};member.total+=source.total;entry.sources.set(source.key,member);entry.total+=source.total;groups.set(key,entry);
  }
  return [...groups.values()].map(entry=>({...entry,sources:[...entry.sources.values()]})).sort((a,b)=>b.total-a.total||a.label.localeCompare(b.label,"fr"));
 }
 root.StudioSourcePlatforms={group};
})(typeof window==="undefined"?globalThis:window);
