/* Read-only daily index of the existing report. Campaign metrics duplicate public
   click rows and must never be added again. No visitor or inferred identity. */
"use strict";
(function(root){
 function index(report){
  const days=new Map();
  const add=(row,category,key)=>{
   if(!(row.total>0))return;
   let day=days.get(row.day);if(!day){day={public:[],tracked:[],campaigns:[]};days.set(row.day,day)}
   day[category].push({key,label:row.label,total:row.total,source:row.source,source_name:row.source_name});
  };
  for(const row of report.rows||[])if(row.kind==="click")add(row,"public",row.link);
  for(const row of report.tracked||[])add(row,"tracked",row.link_id);
  for(const row of report.stories||[])add(row,"campaigns",row.promotion_id);
  return days;
 }
 function select(index,day,source="",sourceName=()=>"Source inconnue"){
  const buckets=index.get(day)||{public:[],tracked:[],campaigns:[]},result={};
  for(const category of ["public","tracked","campaigns"]){
   const links=new Map();
   for(const row of buckets[category]){
    if(source&&row.source!==source)continue;
    // A missing identity stays anonymous; it is never matched by title/domain.
    const key=row.key??null,item=links.get(key)||{key,name:row.label||"Lien historique non identifiable",total:0,sources:new Map()};
    item.total+=row.total;const origin=item.sources.get(row.source)||{key:row.source,label:row.source_name||sourceName(row.source),total:0};origin.total+=row.total;item.sources.set(row.source,origin);links.set(key,item);
   }
   const rows=[...links.values()].map(item=>({...item,sourceBreakdown:[...item.sources.values()].sort((a,b)=>b.total-a.total)}));
   result[category]={rows,total:rows.reduce((sum,row)=>sum+row.total,0)};
  }
  return result;
 }
 root.StudioDailyReport={index,select};
})(typeof window==="undefined"?globalThis:window);
