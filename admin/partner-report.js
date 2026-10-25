/* Read-only attribution of already filtered report events to explicit current
   associations. Domains, URL parameters and lifetime counters are never used. */
"use strict";
(function(root){
 function attribute(rows,links,partners){
  const records=new Map(links.map(link=>[link.id,link])),names=new Map(partners.map(partner=>[partner.id,partner.name]));
  const attributed=new Map(),withoutPartner=new Map(),unidentified=new Map();
  const add=(group,key,row,link,reason)=>{
   const entry=group.get(key)||{id:link?.id||null,name:link?.name||row.label||"Lien historique non identifiable",total:0,reason};
   entry.total+=row.total;group.set(key,entry);
  };
  for(const row of rows){
   const link=records.get(row.link_id),key=row.link_id||row.link||row;
   if(!link){add(unidentified,key,row,null,"missing-link");continue}
   if(link.partner_id===""){add(withoutPartner,key,row,link);continue}
   if(!Object.hasOwn(link,"partner_id")||!link.partner_id){add(unidentified,key,row,link,"missing-association");continue}
   if(!names.has(link.partner_id)){add(unidentified,key,row,link,"missing-partner");continue}
   const partner=attributed.get(link.partner_id)||{id:link.partner_id,name:names.get(link.partner_id),total:0,links:new Map()};
   partner.total+=row.total;add(partner.links,key,row,link);attributed.set(partner.id,partner);
  }
  const attributedRows=[...attributed.values()].map(partner=>({...partner,links:[...partner.links.values()]}));
  const withoutRows=[...withoutPartner.values()],unidentifiedRows=[...unidentified.values()],sum=items=>items.reduce((total,item)=>total+item.total,0);
  return {attributed:attributedRows,withoutPartner:withoutRows,unidentified:unidentifiedRows,
   totals:{attributed:sum(attributedRows),withoutPartner:sum(withoutRows),unidentified:sum(unidentifiedRows)}};
 }
 root.StudioPartnerReport={attribute};
})(typeof window==="undefined"?globalThis:window);
