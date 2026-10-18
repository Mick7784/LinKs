"use strict";
(function(){
const fmt=new Intl.NumberFormat("fr-FR"),esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function ranking(series,max){
 const root=document.createElement("div");root.className="ranking-bars";
 series.forEach((entry,index)=>{const line=document.createElement("div"),track=document.createElement("span"),bar=document.createElement("i");line.className="ranking-series";line.setAttribute("role","img");line.setAttribute("aria-label",entry.label+" : "+fmt.format(entry.value));track.className="ranking-track";bar.style.width=Math.min(100,Math.max(0,entry.value/Math.max(max,1)*100))+"%";bar.className=index?"ranking-secondary":"ranking-primary";track.append(bar);line.append(track);if(series.length>1){const caption=document.createElement("small");caption.textContent=entry.label+" · "+fmt.format(entry.value);line.append(caption)}root.append(line)});
 return root;
}
function donut(root,items,{preview=false,query="",sort="input"}={}){
 const total=items.reduce((sum,item)=>sum+item[1],0),colors=["#22D3EE","#8B5CF6","#3B82F6","#0891B2","#6D28D9","#64748B"],radius=66,circumference=2*Math.PI*radius;
 if(!total){root.innerHTML='<p class="empty">Aucun événement sur cette période.</p>';return}
 const limit=preview?4:5,main=items.slice(0,limit),rest=items.slice(limit).reduce((n,x)=>n+x[1],0),segments=rest?[...main,["Autres sources",rest]]:main;
 let offset=0;
 const circles=segments.map(([name,value],index)=>{const length=value/total*circumference,result=`<circle class="donut-segment" cx="90" cy="90" r="${radius}" fill="none" stroke="${colors[index%colors.length]}" stroke-width="24" stroke-dasharray="${length} ${circumference-length}" stroke-dashoffset="${-offset}" transform="rotate(-90 90 90)"><title>${esc(name)} : ${fmt.format(value)}</title></circle>`;offset+=length;return result}).join("");
 root.innerHTML=`<div class="sources-layout"><div class="donut-wrap"><svg viewBox="0 0 180 180" role="img" aria-label="Répartition des événements ; valeurs dans la légende">${circles}<text class="donut-total" x="90" y="87" text-anchor="middle">${fmt.format(total)}</text><text class="donut-caption" x="90" y="107" text-anchor="middle">Événements</text></svg></div><div class="source-list"></div></div>`;
 const rows=(preview?segments:items).map(([name,value],index)=>({name,total:value,color:colors[Math.min(index,limit)%colors.length],details:[]}));
 StudioCollection.create(root.querySelector('.source-list'),{pageSize:preview?5:20,renderRow:item=>{const row=document.createElement('div');row.className='source-row';row.innerHTML=`<span class="source-dot"></span><span class="source-name">${esc(item.name)}</span><strong>${fmt.format(item.total)}</strong><small>${(item.total/total*100).toLocaleString("fr-FR",{maximumFractionDigits:1})} %</small>`;row.querySelector('.source-dot').style.backgroundColor=item.color;return row}}).setRows(rows,{sort,query,preview});
}
function timeline(root,detail,days,labels){
 const buckets=days.map(([day,views,clicks])=>({start:day,end:day,views,clicks})),width=Math.max(200,root.clientWidth),left=44,right=width-8,height=width>600?250:180,bottom=height+44,slot=(right-left)/Math.max(1,buckets.length),barWidth=Math.max(1,slot-3),peak=Math.max(1,...buckets.flatMap(x=>[x.views,x.clicks]));
 const magnitude=10**Math.floor(Math.log10(peak/4)),step=Math.max(1,Math.ceil(peak/4/magnitude)*magnitude),max=step*4;
 const short=d=>d.slice(8,10)+"/"+d.slice(5,7),description=b=>`${short(b.start)} : ${labels[0]?fmt.format(b.views)+" "+labels[0]+" · ":""}${fmt.format(b.clicks)} ${labels[1]}`,stride=Math.max(1,Math.ceil(buckets.length/Math.max(2,Math.floor((right-left)/58))));
 const groups=buckets.map((b,i)=>{const center=left+slot*(i+.5),halfWidth=Math.max(2,(barWidth-4)/2),offset=halfWidth/2+2;
 const series=[{value:b.views,cls:"visits-bar",x:center-offset},{value:b.clicks,cls:"clicks-bar",x:center+offset}];
 const bars=series.map(s=>{const h=s.value*height/max;return `<rect class="${s.cls} animated-bar" x="${s.x-halfWidth/2}" y="${bottom-h}" width="${halfWidth}" height="${h}" rx="${Math.min(4,halfWidth/3)}"/>`}).join("");
 const marker=(value,y,cls,x)=>`<g class="chart-value ${cls}"><rect x="${x-Math.max(12,String(value).length*3.6+5)}" y="${y-12}" width="${Math.max(24,String(value).length*7.2+10)}" height="17" rx="3"/><text text-anchor="middle" x="${x}" y="${y}">${fmt.format(value)}</text></g>`;
 const markers=slot>=58?series.filter(x=>x.value).map(x=>marker(x.value,bottom-x.value*height/max-9,x.cls+"-value",x.x)).join(""):"";
 const label=i%stride===0?`<text text-anchor="middle" x="${center}" y="${bottom+23}">${short(b.start)}</text>`:"";
 return `<g class="chart-bucket" role="button" tabindex="0" data-bucket="${i}" aria-label="${esc(description(b))}"><title>${esc(description(b))}</title><rect class="chart-hit" x="${left+i*slot}" y="0" width="${slot}" height="${bottom}"/>${bars}<g class="chart-values${slot>=Math.max(36,String(peak).length*8+12)?" always":""}">${markers}</g>${label}</g>`}).join("");
 const grid=Array.from({length:5},(_,i)=>{const y=bottom-i*height/4;return `<line class="chart-grid" x1="${left}" x2="${right}" y1="${y}" y2="${y}"/><text x="2" y="${y+4}">${fmt.format(i*step)}</text>`}).join("");
 root.innerHTML=`<svg viewBox="0 0 ${width} ${bottom+35}" role="group" aria-label="${esc(labels.filter(Boolean).join(" et "))} par jour">${grid}${groups}</svg><div class="chart-tooltip" role="tooltip" hidden></div>`;
 const show=index=>{const b=buckets[index];if(!b)return;detail.textContent=description(b);root.querySelectorAll("[data-bucket]").forEach(g=>g.classList.toggle("selected",Number(g.dataset.bucket)===index));const tooltip=root.querySelector('.chart-tooltip');tooltip.hidden=false;tooltip.innerHTML=`<strong>${esc(b.start.split('-').reverse().join('/'))}</strong>${labels[0]?`<span>${esc(labels[0])} : ${fmt.format(b.views)}</span>`:""}<span>${esc(labels[1])} : ${fmt.format(b.clicks)}</span>`;tooltip.style.left=`${Math.max(0,Math.min(root.clientWidth-155,(left+slot*(index+.5))/width*root.clientWidth-75))}px`};
 const select=event=>{const g=event.target.closest("[data-bucket]");if(g)show(Number(g.dataset.bucket))};root.onclick=select;root.onpointerover=select;if(root.chartFocusHandler)root.removeEventListener("focusin",root.chartFocusHandler);root.chartFocusHandler=select;root.addEventListener("focusin",select);root.onpointerleave=()=>{root.querySelector('.chart-tooltip').hidden=true};
 root.onkeydown=event=>{const g=event.target.closest("[data-bucket]");if(!g)return;if(event.key==="Enter"||event.key===" "){event.preventDefault();show(Number(g.dataset.bucket))}else if(event.key==="Escape"){root.querySelector('.chart-tooltip').hidden=true}else if(event.key==="ArrowRight"||event.key==="ArrowLeft"){event.preventDefault();const index=Math.max(0,Math.min(buckets.length-1,Number(g.dataset.bucket)+(event.key==="ArrowRight"?1:-1)));root.querySelector(`[data-bucket="${index}"]`).focus()}};
 detail.textContent=buckets.length?(matchMedia('(pointer:coarse)').matches?"Touchez une barre pour afficher les chiffres.":""):"Aucune donnée sur cette période.";
}
window.StudioCharts={donut,ranking,timeline};
})();
