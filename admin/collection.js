/* Small DOM collection primitive. No application, API or metric knowledge. */
"use strict";
(function(root){
 function select(rows,{query="",sort="total",page=0,pageSize=20}={}){
  const needle=query.trim().toLocaleLowerCase("fr");
  const matching=rows.filter(row=>!needle||[row.name,...(row.details||[])].join(" ").toLocaleLowerCase("fr").includes(needle));
  if(sort!=="input")matching.sort(sort==="name"?(a,b)=>a.name.localeCompare(b.name,"fr"):(a,b)=>b.total-a.total||a.name.localeCompare(b.name,"fr"));
  const pages=Math.max(1,Math.ceil(matching.length/pageSize)),index=Math.max(0,Math.min(page,pages-1));
  return {rows:matching.slice(index*pageSize,(index+1)*pageSize),total:matching.length,pages,page:index};
 }
 function collection(node,{renderRow,pageSize=20,empty="Aucune donnée sur cette période."}){
  let rows=[],options={pageSize,query:"",sort:"total",preview:false},page=0;
  function draw(){
   const result=select(rows,{...options,page});page=result.page;
   const body=document.createElement("div");body.className="collection-rows";
   const max=rows.reduce((peak,row)=>Math.max(peak,row.total),1);
   const seriesMax=rows.reduce((peak,row)=>Math.max(peak,...(row.series||[]).map(x=>x.value)),1);
   if(result.total)body.append(...result.rows.map(row=>renderRow(row,{max,seriesMax,preview:options.preview})));else{const p=document.createElement("p");p.className="empty";p.textContent=empty;body.append(p)}
   if(result.pages===1||options.preview){node.replaceChildren(body);return}
   const nav=document.createElement("nav");nav.className="collection-pagination";nav.setAttribute("aria-label","Pagination · "+(node.getAttribute("aria-label")||"résultats"));
   const status=document.createElement("span");status.setAttribute("role","status");status.textContent=`${result.total} résultats · ${page+1} / ${result.pages}`;
   for(const [label,delta,disabled] of [["Précédent",-1,page===0],["Suivant",1,page===result.pages-1]]){
    const button=document.createElement("button");button.type="button";button.textContent=label;button.disabled=disabled;button.onclick=()=>{page+=delta;draw();node.querySelector('.collection-pagination button:not(:disabled)')?.focus()};nav.append(button);
   }
   nav.prepend(status);node.replaceChildren(body,nav);
  }
  return {setRows(value,settings={}){rows=value;options={...options,...settings};page=0;draw()},filter(value){if(Object.entries(value).every(([key,v])=>options[key]===v))return;options={...options,...value};page=0;draw()}};
 }
 root.StudioCollection={select,create:collection};
})(typeof window==="undefined"?globalThis:window);
