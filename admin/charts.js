"use strict";
(function(){
const fmt=new Intl.NumberFormat("fr-FR"),esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function donut(root,items){
 const total=items.reduce((sum,item)=>sum+item[1],0),colors=["#22D3EE","#8B5CF6","#3B82F6","#0891B2","#6D28D9","#64748B"],radius=66,circumference=2*Math.PI*radius;
 if(!total){root.innerHTML='<p class="empty">Aucune donnée sur cette période.</p>';return}
 let offset=0;
 const segments=items.map(([name,value],i)=>{const length=value/total*circumference,color=colors[i%colors.length],result=`<circle class="donut-segment" role="button" tabindex="0" data-source-index="${i}" aria-label="${esc(name)} : ${fmt.format(value)} (${(value/total*100).toLocaleString("fr-FR",{maximumFractionDigits:1})} %)" cx="90" cy="90" r="${radius}" fill="none" stroke="${color}" stroke-width="24" stroke-dasharray="${length} ${circumference-length}" stroke-dashoffset="${-offset}" transform="rotate(-90 90 90)"><title>${esc(name)} : ${fmt.format(value)}</title></circle>`;offset+=length;return result}).join("");
 root.innerHTML=`<div class="sources-layout"><div class="donut-wrap"><svg viewBox="0 0 180 180" role="group" aria-label="Répartition des sources">${segments}<text class="donut-total" x="90" y="87" text-anchor="middle">${fmt.format(total)}</text><text class="donut-caption" x="90" y="107" text-anchor="middle">Total</text></svg></div><div class="source-list">${items.map(([name,value],i)=>`<button type="button" class="source-row" data-source-index="${i}"><span class="source-dot"></span><span class="source-name">${esc(name)}</span><strong>${fmt.format(value)}</strong><small>${(value/total*100).toLocaleString("fr-FR",{maximumFractionDigits:1})} %</small></button>`).join("")}</div></div><p class="source-detail" role="status" aria-live="polite"></p>`;
 root.querySelectorAll('.source-dot').forEach((dot,i)=>dot.style.backgroundColor=colors[i%colors.length]);
 const show=event=>{const target=event.target.closest('[data-source-index]');if(!target)return;const index=Number(target.dataset.sourceIndex),[name,value]=items[index];root.querySelectorAll('[data-source-index]').forEach(node=>node.classList.toggle('selected',Number(node.dataset.sourceIndex)===index));root.querySelector('.source-detail').textContent=`${name} : ${fmt.format(value)} · ${(value/total*100).toLocaleString("fr-FR",{maximumFractionDigits:1})} %`};
 root.onclick=show;root.onpointerover=show;if(root.sourceFocusHandler)root.removeEventListener("focusin",root.sourceFocusHandler);root.sourceFocusHandler=show;root.addEventListener("focusin",show);root.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();show(event)}};
}
window.StudioCharts={donut};
})();
