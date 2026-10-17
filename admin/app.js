"use strict";
const $=id=>document.getElementById(id),fmt=new Intl.NumberFormat("fr-FR");
const names={"direct-inconnu":"Direct / inconnu","autre-site":"Autre site","autre-campagne":"Autre campagne",youtube:"YouTube",instagram:"Instagram","instagram-story":"Ancien lien partagé (source incertaine)","shared-unknown":"Lien partagé (source inconnue)",facebook:"Facebook",google:"Google",discord:"Discord",newsletter:"Newsletter",tiktok:"TikTok",site:"Site",mail:"E-mail",qr:"QR"};
let csrf="",adminTimezone="UTC";
const state={content:[],buttons:[],archives:[],settings:{},chart:[]};
const api=async(path,options={})=>{const response=await fetch(path,{cache:"no-store",...options,headers:{"Content-Type":"application/json","X-Links-Request":"1","X-Links-CSRF":csrf,...(options.headers||{})}});if(response.status===401){location.href="/login";throw new Error("Connexion requise.")}if(!response.ok){let message="Une erreur est survenue.";try{message=(await response.json()).error||message}catch{}throw new Error(message)}return response.status===204?null:response.json()};
const say=(message,error=false)=>{const dialog=[...document.querySelectorAll("dialog[open]")].at(-1);if(dialog){let feedback=dialog.querySelector("[data-dialog-feedback]");if(!feedback){feedback=document.createElement("p");feedback.dataset.dialogFeedback="";feedback.className="editor-feedback";feedback.setAttribute("role","alert");(dialog.querySelector("form")||dialog).prepend(feedback)}feedback.hidden=false;feedback.textContent=message;feedback.classList.toggle("notice-error",error)}const node=$("notice");node.textContent=message;node.classList.toggle("notice-error",error);clearTimeout(say.timer);say.timer=setTimeout(()=>node.textContent="",4000)};
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const typeName={classic:"Lien",featured:"Mise en avant",promo:"Campagne"};
const statusClass=value=>({Actif:"active",Programmé:"scheduled",Expiré:"expired",Brouillon:"draft"}[value]||"");
function activate(id){document.querySelectorAll(".view").forEach(x=>x.classList.toggle("active",x.id===id));document.querySelectorAll(".tabs button").forEach(x=>x.classList.toggle("active",x.dataset.tab===id));syncNavigation();$("topbar-current").textContent=document.querySelector(".tabs button.active")?.textContent.trim()||"Links";if(id==="dashboard"){loadStats()}if(id==="content")loadContent();if(id==="buttons")loadButtons();if(id==="archives")loadArchives();if(id==="appearance")window.LinksAppearance?.load();else window.LinksAppearance?.cancelUploads();if(id!=="settings")profileUploads.forEach(g=>g.invalidate());if(id==="settings"){loadSettings().then(()=>window.LinksSettings?.open())}}
const navigation=$("navigation"),menuToggle=$("menu-toggle"),mobileNavigation=matchMedia("(max-width:760px)");
function closeMenu(restoreFocus=false){navigation.classList.remove("open");menuToggle.setAttribute("aria-expanded","false");if(restoreFocus)menuToggle.focus()}
function syncNavigation(){document.querySelectorAll(".tabs button").forEach(button=>{const active=button.classList.contains("active");if(active){button.setAttribute("aria-current","page");$("menu-current").textContent=button.textContent.trim()}else button.removeAttribute("aria-current")})}
menuToggle.addEventListener("click",()=>{const open=navigation.classList.toggle("open");menuToggle.setAttribute("aria-expanded",String(open))});
navigation.addEventListener("keydown",event=>{if(event.key==="Escape"&&navigation.classList.contains("open")){event.preventDefault();closeMenu(true)}});
document.addEventListener("click",event=>{if(!navigation.contains(event.target))closeMenu()});
navigation.addEventListener("focusout",event=>{if(!navigation.contains(event.relatedTarget))closeMenu()});
mobileNavigation.addEventListener("change",()=>{const active=document.activeElement;const hiddenFocus=mobileNavigation.matches?active?.matches(".tabs button"):active===menuToggle;closeMenu();if(hiddenFocus)(mobileNavigation.matches?menuToggle:document.querySelector(".tabs button.active")).focus()});
document.querySelector(".tabs").addEventListener("click",event=>{const button=event.target.closest("[data-tab]");if(button){activate(button.dataset.tab);closeMenu(mobileNavigation.matches)}});
syncNavigation();

function dates(){const days=Number($("period").value),end=new Intl.DateTimeFormat("en-CA",{timeZone:adminTimezone,year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date()),start=new Date(end+"T12:00:00Z");start.setUTCDate(start.getUTCDate()-days+1);return {start:start.toISOString().slice(0,10),end}}

function bars(id,items){const root=$(id);if(!items.length){root.innerHTML='<p class="empty">Aucune donnée sur cette période.</p>';return}const max=Math.max(...items.map(x=>x[1]),1);root.className="bar-list";root.innerHTML=items.map(([label,value])=>`<div class="bar-row"><span title="${esc(label)}">${esc(label)}</span><span class="bar"><i></i></span><strong>${fmt.format(value)}</strong></div>`).join("");root.querySelectorAll(".bar i").forEach((bar,index)=>{bar.style.width=`${items[index][1]/max*100}%`})}
// Daily chronology includes zero days; only axis labels are thinned.
function chartBuckets(days){return days.map(([day,views,clicks])=>({start:day,end:day,views,clicks}))}
function metricRows(id,items,empty){
 $(id).innerHTML=items.length?items.map(item=>`<div class="engagement-row"><div class="engagement-copy"><strong>${esc(item.name)}</strong>${item.details.length?`<small>${item.details.map(esc).join(" · ")}</small>`:""}</div><div class="engagement-value"><strong>${fmt.format(item.total)}</strong><small>${esc(item.unit)}</small></div></div>`).join(""):`<p class="empty">${esc(empty)}</p>`;
}
function sourceDonut(items){
 const root=$("sources"),total=items.reduce((sum,item)=>sum+item[1],0),colors=["#22D3EE","#8B5CF6","#3B82F6","#0891B2","#6D28D9","#64748B"],radius=66,circumference=2*Math.PI*radius;
 if(!total){root.innerHTML='<p class="empty">Aucune donnée sur cette période.</p>';return}
 let offset=0;
 const segments=items.map(([name,value],i)=>{const length=value/total*circumference,color=colors[i%colors.length],result=`<circle class="donut-segment" role="button" tabindex="0" data-source-index="${i}" aria-label="${esc(name)} : ${fmt.format(value)} (${(value/total*100).toLocaleString("fr-FR",{maximumFractionDigits:1})} %)" cx="90" cy="90" r="${radius}" fill="none" stroke="${color}" stroke-width="24" stroke-dasharray="${length} ${circumference-length}" stroke-dashoffset="${-offset}" transform="rotate(-90 90 90)"><title>${esc(name)} : ${fmt.format(value)}</title></circle>`;offset+=length;return result}).join("");
 root.innerHTML=`<div class="sources-layout"><div class="donut-wrap"><svg viewBox="0 0 180 180" role="group" aria-label="Répartition des sources">${segments}<text class="donut-total" x="90" y="87" text-anchor="middle">${fmt.format(total)}</text><text class="donut-caption" x="90" y="107" text-anchor="middle">Total</text></svg></div><div class="source-list">${items.map(([name,value],i)=>`<button type="button" class="source-row" data-source-index="${i}"><span class="source-dot"></span><span class="source-name">${esc(name)}</span><strong>${fmt.format(value)}</strong><small>${(value/total*100).toLocaleString("fr-FR",{maximumFractionDigits:1})} %</small></button>`).join("")}</div></div><p class="source-detail" role="status" aria-live="polite"></p>`;
 root.querySelectorAll('.source-dot').forEach((dot,i)=>dot.style.backgroundColor=colors[i%colors.length]);
 const show=event=>{const target=event.target.closest('[data-source-index]');if(!target)return;const index=Number(target.dataset.sourceIndex),[name,value]=items[index];root.querySelectorAll('[data-source-index]').forEach(node=>node.classList.toggle('selected',Number(node.dataset.sourceIndex)===index));root.querySelector('.source-detail').textContent=`${name} : ${fmt.format(value)} · ${(value/total*100).toLocaleString("fr-FR",{maximumFractionDigits:1})} %`};
 root.onclick=show;root.onpointerover=show;if(root.sourceFocusHandler)root.removeEventListener("focusin",root.sourceFocusHandler);root.sourceFocusHandler=show;root.addEventListener("focusin",show);root.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();show(event)}};
}
let chartRenderedWidth=0;
function chart(days){
 state.chart=days;const root=$("chart"),buckets=chartBuckets(days),width=Math.max(200,root.clientWidth),left=44,right=width-8,height=width>600?250:180,bottom=height+44,slot=(right-left)/Math.max(1,buckets.length),barWidth=Math.max(1,slot-3),peak=Math.max(1,...buckets.flatMap(x=>[x.views,x.clicks]));
 const magnitude=10**Math.floor(Math.log10(peak/4)),step=Math.max(1,Math.ceil(peak/4/magnitude)*magnitude),max=step*4;
 chartRenderedWidth=root.clientWidth;
 const short=d=>d.slice(8,10)+"/"+d.slice(5,7),description=b=>`${short(b.start)} : ${fmt.format(b.views)} visites · ${fmt.format(b.clicks)} clics`,stride=Math.max(1,Math.ceil(buckets.length/Math.max(2,Math.floor((right-left)/58))));
 const groups=buckets.map((b,i)=>{const center=left+slot*(i+.5),halfWidth=Math.max(2,(barWidth-4)/2),offset=halfWidth/2+2;
 const series=[{value:b.views,cls:"visits-bar",x:center-offset},{value:b.clicks,cls:"clicks-bar",x:center+offset}];
 const bars=series.map(s=>{const h=s.value*height/max;return `<rect class="${s.cls} animated-bar" style="animation-delay:${Math.min(i*8,120)}ms" x="${s.x-halfWidth/2}" y="${bottom-h}" width="${halfWidth}" height="${h}" rx="${Math.min(4,halfWidth/3)}"/>`}).join("");
 const marker=(value,y,cls,x)=>`<g class="chart-value ${cls}"><rect x="${x-Math.max(12,String(value).length*3.6+5)}" y="${y-12}" width="${Math.max(24,String(value).length*7.2+10)}" height="17" rx="3"/><text text-anchor="middle" x="${x}" y="${y}">${fmt.format(value)}</text></g>`;
 const markers=slot>=58?series.filter(x=>x.value).map(x=>marker(x.value,bottom-x.value*height/max-9,x.cls+"-value",x.x)).join(""):"";
 const label=i%stride===0?`<text text-anchor="middle" x="${center}" y="${bottom+23}">${short(b.start)}</text>`:"";
 return `<g class="chart-bucket" role="button" tabindex="0" data-bucket="${i}" aria-label="${esc(description(b))}"><title>${esc(description(b))}</title><rect class="chart-hit" x="${left+i*slot}" y="0" width="${slot}" height="${bottom}"/>${bars}<g class="chart-values${slot>=Math.max(36,String(peak).length*8+12)?" always":""}">${markers}</g>${label}</g>`}).join("");
 const grid=Array.from({length:5},(_,i)=>{const y=bottom-i*height/4;return `<line class="chart-grid" x1="${left}" x2="${right}" y1="${y}" y2="${y}"/><text x="2" y="${y+4}">${fmt.format(i*step)}</text>`}).join("");
 root.innerHTML=`<svg viewBox="0 0 ${width} ${bottom+35}" role="group" aria-label="Visites et clics par jour">${grid}${groups}</svg><div class="chart-tooltip" role="tooltip" hidden></div>`;
 const show=index=>{const b=buckets[index];if(!b)return;$("chart-detail").textContent=description(b);root.querySelectorAll("[data-bucket]").forEach(g=>g.classList.toggle("selected",Number(g.dataset.bucket)===index));const tooltip=root.querySelector('.chart-tooltip');tooltip.hidden=false;tooltip.innerHTML=`<strong>${esc(b.start.split('-').reverse().join('/'))}</strong><span>Visites : ${fmt.format(b.views)}</span><span>Clics : ${fmt.format(b.clicks)}</span>`;tooltip.style.left=`${Math.max(0,Math.min(root.clientWidth-155,(left+slot*(index+.5))/width*root.clientWidth-75))}px`};
 const select=event=>{const g=event.target.closest("[data-bucket]");if(g)show(Number(g.dataset.bucket))};root.onclick=select;root.onpointerover=select;if(root.chartFocusHandler)root.removeEventListener("focusin",root.chartFocusHandler);root.chartFocusHandler=select;root.addEventListener("focusin",select);root.onpointerleave=()=>{root.querySelector('.chart-tooltip').hidden=true};
 root.onkeydown=event=>{const g=event.target.closest("[data-bucket]");if(!g)return;if(event.key==="Enter"||event.key===" "){event.preventDefault();show(Number(g.dataset.bucket))}else if(event.key==="Escape"){root.querySelector('.chart-tooltip').hidden=true}else if(event.key==="ArrowRight"||event.key==="ArrowLeft"){event.preventDefault();const index=Math.max(0,Math.min(buckets.length-1,Number(g.dataset.bucket)+(event.key==="ArrowRight"?1:-1)));root.querySelector(`[data-bucket="${index}"]`).focus()}};
 $("chart-detail").textContent=buckets.length?(matchMedia('(pointer:coarse)').matches?"Touchez une barre pour afficher les chiffres.":""):"Aucune donnée sur cette période.";
}

async function loadStats(){try{
 const range=dates(),data=await api("/api/stats?"+new URLSearchParams(range)),stories=data.stories||[],previous=$("source").value;
 const sources=[...new Set([...data.rows.map(x=>x.source),...stories.map(x=>x.source),...(data.promo_code_copies||[]).map(x=>x.source),...(data.campaign_metrics||[]).map(x=>x.source)])].sort();
 $("source").replaceChildren(new Option("Toutes les sources",""),...sources.map(x=>new Option(names[x]||x,x)));if(sources.includes(previous))$("source").value=previous;
 const source=$("source").value,rows=data.rows.filter(x=>!source||x.source===source),storyRows=stories.filter(x=>!source||x.source===source),days=new Map(),bySource=new Map(),byLink=new Map(),labels=new Map(),byStory=new Map();
 for(let d=new Date(range.start+"T12:00Z");d<=new Date(range.end+"T12:00Z");d.setUTCDate(d.getUTCDate()+1))days.set(d.toISOString().slice(0,10),[0,0]);
 let views=0,clicks=0,storyClicks=0;
 for(const row of rows){labels.set(row.link,row.label||row.link);const pair=days.get(row.day);if(!pair)continue;if(row.kind==="view"){views+=row.total;pair[0]+=row.total;bySource.set(row.source,(bySource.get(row.source)||0)+row.total)}else if(row.kind==="click"){clicks+=row.total;pair[1]+=row.total;byLink.set(row.link,(byLink.get(row.link)||0)+row.total)}}
 for(const row of storyRows){storyClicks+=row.total;const item=byStory.get(row.promotion_id)||{label:row.label,total:0,sources:new Map()};item.total+=row.total;item.sources.set(row.source,(item.sources.get(row.source)||0)+row.total);byStory.set(row.promotion_id,item);bySource.set(row.source,(bySource.get(row.source)||0)+row.total)}
 $("views").textContent=fmt.format(views);$("clicks").textContent=fmt.format(clicks);$("ratio").textContent=views?(clicks*100/views).toLocaleString("fr-FR",{maximumFractionDigits:1})+" %":"—";
 $("story-clicks").textContent=fmt.format(storyClicks);$("story-promos").textContent=fmt.format(byStory.size);$("story-total").textContent=fmt.format(storyClicks);$("story-total").parentElement.title=fmt.format(byStory.size)+" campagne(s)";
 metricRows("story-list",[...byStory.values()].sort((a,b)=>b.total-a.total).map(item=>({name:item.label,total:item.total,unit:"ouvertures",details:[...item.sources].sort((a,b)=>b[1]-a[1]).map(([key,count])=>(names[key]||key)+" : "+fmt.format(count))})),"Aucun lien partagé ouvert sur cette période.");
 const campaignStats=new Map(),copyStats=new Map();
 const getCampaign=id=>campaignStats.get(id)||{clicks:0,impressions:0,shared:0,copies:0};
 for(const row of (data.campaign_metrics||[]).filter(x=>!source||x.source===source)){const value=getCampaign(row.id);value[row.kind==="click"?"clicks":"impressions"]+=row.total;campaignStats.set(row.id,value)}
 for(const row of storyRows){const value=getCampaign(row.promotion_id);value.shared+=row.total;campaignStats.set(row.promotion_id,value)}
 let copyTotal=0;
 for(const row of (data.promo_code_copies||[]).filter(x=>!source||x.source===source)){copyTotal+=row.total;const metric=getCampaign(row.id);metric.copies+=row.total;campaignStats.set(row.id,metric);const key=JSON.stringify([row.id,row.code]);const value=copyStats.get(key)||{id:row.id,name:row.name,code:row.code,total:0};value.total+=row.total;copyStats.set(key,value)}
 $("promo-copies").textContent=fmt.format(copyTotal);$("promo-copy-total").textContent=fmt.format(copyTotal);
 metricRows("promo-copy-list",[...copyStats.values()].sort((a,b)=>b.total-a.total).map(value=>{const impressions=campaignStats.get(value.id)?.impressions||0;return {name:value.name,total:value.total,unit:"copies",details:[value.code,...(impressions?["Taux de copie : "+(value.total*100/impressions).toLocaleString("fr-FR",{maximumFractionDigits:1})+" %"]:[])]}}),"Aucun code copié sur cette période.");
 await loadCampaigns(campaignStats);
 chart([...days].map(([day,value])=>[day,...value]));const sorted=map=>[...map].sort((a,b)=>b[1]-a[1]);bars("top-links",sorted(byLink).slice(0,5).map(([key,value])=>[labels.get(key)||key,value]));sourceDonut(sorted(bySource).map(([key,value])=>[names[key]||key,value]));
 }catch(error){say(error.message,true)}}
$("period").addEventListener("change",loadStats);$("source").addEventListener("change",loadStats);new ResizeObserver(()=>{const width=$("chart").clientWidth;if(width>0&&width!==chartRenderedWidth&&state.chart.length)chart(state.chart)}).observe($("chart"));

function canStory(item){try{const url=new URL(item.url);return ["http:","https:"].includes(url.protocol)&&!url.username&&!url.password&&url.hostname!==new URL(publicSiteUrl||location.origin).hostname}catch{return false}}
function storyButton(item){if(item.type==="classic")return "";const disabled=!canStory(item),title=disabled?"URL requise":"Copier le lien tracké pour la plateforme choisie";return `<div class="share-picker"><select aria-label="Plateforme de partage pour ${esc(item.internal_name)}" ${disabled?"disabled":""}><option value="instagram">Instagram Story</option><option value="youtube">YouTube Post</option><option value="facebook">Facebook</option><option value="tiktok">TikTok</option><option value="">Autre / sans source</option></select><button data-action="copy-story" class="story-link-button" title="${title}" aria-label="${title}" ${disabled?"disabled":""}>🔗</button></div>`;}
async function copyStory(action,id){if(action.disabled)return;action.disabled=true;try{const {url}=await api(`/api/content/${id}/story-link`,{method:"POST",body:"{}"});const platform=action.closest(".share-picker")?.querySelector("select")?.value||"";const shareUrl=new URL(url);if(platform)shareUrl.searchParams.set("utm_source",platform);const link=shareUrl.toString();let copied=false;try{await navigator.clipboard.writeText(link);copied=true}catch{let input=action.parentNode.querySelector(".story-copy");if(!input){input=document.createElement("input");input.className="story-copy";input.readOnly=true;input.setAttribute("aria-label","Lien partagé tracké");action.parentNode.append(input)}input.value=link;input.focus();input.select();try{copied=document.execCommand("copy")}catch{}if(copied)input.remove()}say(copied?"Lien partagé copié"+(platform?" · "+(names[platform]||platform):""):"Lien sélectionné : copie-le avec le menu de ton appareil.")}catch(error){say(error.message,true)}finally{action.disabled=false}}
function itemHtml(item,archived=false){const performance=item.type==="classic"?`${fmt.format(item.clicks||0)} clics`:`${fmt.format(item.impressions||0)} impressions · ${fmt.format(item.clicks||0)} clics · CTR ${item.ctr===null?"—":item.ctr+" %"}`;return`<article class="list-item" draggable="${!archived}" data-id="${esc(item.id)}" data-group="${item.type==="classic"?"classic":"highlight"}"><span class="drag-handle">${archived?"◦":"⋮⋮"}</span><span class="type-mark">${item.type==="promo"?"▣":item.type==="featured"?"★":"↗"}</span><div class="item-copy"><strong>${esc(item.internal_name)}</strong><small>${esc(item.title)} · ${typeName[item.type]||item.type} · ${performance}</small><span class="status ${statusClass(item.status)}">${esc(item.status)}</span></div><div class="item-actions">${storyButton(item)}${archived?`<button data-action="restore">Restaurer</button>`:`<span class="move"><button data-action="up" aria-label="Monter">↑</button><button data-action="down" aria-label="Descendre">↓</button></span><button data-action="edit">Modifier</button><details class="row-menu"><summary aria-label="Autres actions pour ${esc(item.internal_name)}" title="Autres actions">···</summary><div class="row-menu-content"><button data-action="duplicate">Dupliquer</button><button data-action="archive">Archiver</button>`}<button data-action="delete" class="trash" title="Supprimer définitivement" aria-label="Supprimer définitivement">Supprimer</button>${archived?"":"</div></details>"}</div></article>`}
const contentSections={classic:"Liens permanents",video:"Dernière vidéo",highlight:"Promotions / mises en avant"};
function renderContent(){
 const root=$("content-list"),order=state.settings.content_order||["classic","video","highlight"];
 root.innerHTML=order.map((key,index)=>{const items=state.content.filter(item=>key==="classic"?item.type==="classic":key==="highlight"?item.type!=="classic":false);
 return `<section class="content-section" data-section="${key}"><header class="content-section-header"><div><h3>${contentSections[key]}</h3>${key!=="video"?`<small>${items.length} élément(s)${key==="highlight"?` · ${items.filter(x=>x.status==="Actif").length} active(s) / 3 · ${items.filter(x=>x.status==="Programmé").length} programmée(s)`:""}</small>`:""}</div><div class="section-moves"><button type="button" data-section-move="-1" aria-label="Monter ${contentSections[key]}"${index===0?" disabled":""}>↑</button><button type="button" data-section-move="1" aria-label="Descendre ${contentSections[key]}"${index===order.length-1?" disabled":""}>↓</button></div></header>${key==="video"?`<div class="video-section"><label class="check"><input type="checkbox" id="section-video-enabled"${state.settings.video_enabled?" checked":""}>Afficher la section vidéo</label><p>La section vidéo est configurée dans Paramètres. Ici, vous gérez uniquement sa visibilité et sa position.</p><button type="button" data-video-settings>Paramètres vidéo →</button></div>`:`<div class="section-items">${items.length?items.map(x=>itemHtml(x)).join(""):'<p class="empty">Aucun élément dans cette section.</p>'}</div>`}</section>`}).join("");setupDrag(root);
 $("section-video-enabled").onchange=async event=>{const input=event.target;input.disabled=true;try{await api("/api/settings",{method:"POST",body:JSON.stringify({video_enabled:input.checked})});state.settings.video_enabled=input.checked;$("youtube-enabled").checked=input.checked;say("Visibilité vidéo enregistrée.")}catch(error){input.checked=!!state.settings.video_enabled;say(error.message,true)}finally{input.disabled=false}};
}
document.addEventListener("click",async event=>{const button=event.target.closest("[data-section-move]");if(button){button.disabled=true;const order=[...(state.settings.content_order||["classic","video","highlight"])],index=order.indexOf(button.closest('[data-section]').dataset.section),next=index+Number(button.dataset.sectionMove);if(next<0||next>=order.length)return;[order[index],order[next]]=[order[next],order[index]];try{await api("/api/settings",{method:"POST",body:JSON.stringify({content_order:order})});state.settings.content_order=order;renderContent();const heading=$("content-list").querySelector(`[data-section="${order[next]}"] h3`);heading.tabIndex=-1;heading.focus();say("Ordre des sections enregistré.")}catch(error){say(error.message,true);button.disabled=false}}
 if(event.target.closest('[data-video-settings]')){activate('settings');window.LinksSettings?.show('integrations');$("youtube-channel").focus()}
});
let timelineCampaigns=[];
function renderTimeline(items=timelineCampaigns){timelineCampaigns=items;LinksCalendar.render(items,{zone:adminTimezone,describe:item=>`${periodText(item.start_at)} → ${periodText(item.end_at)}${LinksCalendar.whole(item,adminTimezone)?" · Journée entière":""}`,edit:item=>openBlock(item),create:(start_at,end_at,calendar_timed)=>openBlock({start_at,end_at,calendar_timed},"promo"),save:saveAgendaPeriod})}
async function saveAgendaPeriod(item,start_at,end_at){
 const data={...editable(item),id:item.id,start_at,end_at};
 try{const check=await api('/api/promotions/check',{method:'POST',body:JSON.stringify(data)});if(!check.allowed){openBlock({...item,start_at,end_at});showConflict(data,check);return}await api('/api/content/'+item.id,{method:'PUT',body:JSON.stringify(data)});await loadStats();say('Période enregistrée.')}catch(error){say(error.message,true);renderTimeline()}
}

async function loadContent(){try{state.content=(await api("/api/content")).items;renderContent()}catch(error){say(error.message,true)}}
async function loadArchives(){try{state.archives=(await api("/api/content?archived=1")).items;$("archive-list").innerHTML=state.archives.length?state.archives.map(x=>itemHtml(x,true)).join(""):'<p class="empty">Aucune archive.</p>'}catch(error){say(error.message,true)}}
function buttonHtml(item){return`<article class="list-item" draggable="true" data-id="${esc(item.id)}"><span class="drag-handle">⋮⋮</span><span class="type-mark">${shortcutIcon({...item,platform:item.icon}).outerHTML}</span><div class="item-copy"><strong>${esc(item.label)}</strong><small>${esc(item.url)} · ${fmt.format(item.clicks||0)} clics</small><span class="status ${item.active?"active":""}">${item.active?"Actif":"Désactivé"}</span></div><div class="item-actions"><span class="move"><button data-action="up">↑</button><button data-action="down">↓</button></span><button data-action="edit-button">Modifier</button><button data-action="delete-button" class="danger">Supprimer</button></div></article>`}
async function loadButtons(){try{state.buttons=(await api("/api/buttons")).items;$("button-list").innerHTML=state.buttons.length?state.buttons.map(buttonHtml).join(""):'<p class="empty">Aucun bouton.</p>';setupDrag($("button-list"),true)}catch(error){say(error.message,true)}}
function setupDrag(root,buttons=false){let dragged;root.ondragstart=event=>{dragged=event.target.closest(".list-item");dragged?.classList.add("dragging")};root.ondragend=()=>{dragged?.classList.remove("dragging");dragged=null};root.ondragover=event=>{event.preventDefault();const target=event.target.closest(".list-item");if(!dragged||!target||target===dragged||(!buttons&&target.dataset.group!==dragged.dataset.group))return;const box=target.getBoundingClientRect();target.parentNode.insertBefore(dragged,event.clientY<box.top+box.height/2?target:target.nextSibling)};root.ondrop=async event=>{event.preventDefault();await saveOrder(root,buttons)}}
async function saveOrder(root,buttons=false){try{const ids=[...(buttons?root:$("content-list")).querySelectorAll(".list-item")].map(x=>x.dataset.id);await api(buttons?"/api/buttons/reorder":"/api/content/reorder",{method:"POST",body:JSON.stringify({ids})});buttons?loadButtons():loadContent();say("Nouvel ordre enregistré.")}catch(error){say(error.message,true)}}
async function move(root,item,direction,buttons=false){const siblings=[...root.querySelectorAll(`.list-item${buttons?"":'[data-group="'+item.dataset.group+'"]'}`)],index=siblings.indexOf(item),other=siblings[index+direction];if(!other)return;item.parentNode.insertBefore(direction<0?item:other,direction<0?other:item);await saveOrder(root,buttons)}

const blockDialog=$("block-dialog"),blockForm=$("block-form");
const blockUpload=LinksUploads.create(blockForm,{statusHost:blockForm.querySelector(".image-editor"),active:()=>blockDialog.open});
blockDialog.addEventListener("close",()=>blockUpload.invalidate());
blockDialog.addEventListener("cancel",()=>blockUpload.invalidate());
function localDate(value){return LinksDates.local(value,adminTimezone)}
function openBlock(item={},type="classic"){blockUpload.invalidate();blockForm.reset();$("block-feedback").hidden=true;$("block-advanced").open=false;const clean={id:"",type,internal_name:"",title:"",description:"",url:"",icon:"website",image:"",badge:"",cta:"",promo_code:"",priority:"normal",start_at:"",end_at:""};for(const [key,value] of Object.entries(clean))blockForm.elements[key].value=value;$("block-image-file").value="";blockForm.elements.active.checked=true;blockForm.elements.draft.checked=false;if(item.id){for(const key of ["id","type","internal_name","title","description","url","icon","image","badge","cta","promo_code","priority"])blockForm.elements[key].value=item[key]??clean[key];$("block-advanced").open=!!(item.badge||item.cta||item.internal_name!==item.title||(item.type==="classic"&&(item.start_at||item.end_at)));blockForm.elements.active.checked=item.active!==false;blockForm.elements.draft.checked=!!item.draft;}const fields=LinksCalendar.inputFields(item,adminTimezone);for(const [key,value] of Object.entries(fields))blockForm.elements[key].value=value;blockForm.scheduleOriginal={fields,calendar_timed:!!item.calendar_timed,start_at:item.start_at||null,end_at:item.end_at||null};$("promo-availability").hidden=true;$("block-title").textContent=item.id?"Modifier le bloc":"Nouveau bloc";preview();blockDialog.showModal();checkPromotion()}
function updatePromoEditor(){const promo=["promo","featured"].includes(blockForm.elements.type.value);blockForm.querySelectorAll("[data-promo-editorial]").forEach(label=>label.hidden=promo);blockForm.elements.title.required=!promo;const legacySchedule=!!(blockForm.scheduleOriginal?.start_at||blockForm.scheduleOriginal?.end_at);blockForm.querySelector("[data-campaign-schedule]").hidden=!promo&&!legacySchedule;$("block-advanced").hidden=true;const name=blockForm.querySelector("[data-campaign-name]");name.hidden=!promo;const target=blockForm.querySelector(".editor-essential");if(name.parentNode!==target)target.prepend(name);$("block-type-help").textContent=promo?"Campagne avec image, dates et code promo facultatifs.":"Lien avec titre, description, icône et image de fond.";blockForm.querySelector("[data-promo-code]").hidden=!promo;$("image-guidance").textContent=promo?"Campagne : 1200 × 1200 px recommandé (1:1). Recadrage centré selon l’écran ; garder le sujet au centre. Aucun minimum imposé.":"Fond de lien : 1600 × 400 px recommandé (4:1). Recadrage centré pour remplir la carte ; garder le sujet au centre. Aucun minimum imposé.";blockForm.elements.priority.closest("label").hidden=!promo;for(const field of ["badge","cta"])blockForm.elements[field].closest("label").hidden=true;}
function formBlock(){const data=Object.fromEntries(new FormData(blockForm));data.active=blockForm.elements.active.checked;data.draft=blockForm.elements.draft.checked;if(!data.internal_name.trim())data.internal_name=data.title.trim();if(["promo","featured"].includes(data.type)&&!data.title.trim())data.title=data.internal_name;const original=blockForm.scheduleOriginal,unchanged=original&&Object.entries(original.fields).every(([key,value])=>blockForm.elements[key].value===value);const range=unchanged?{start_at:original.start_at,end_at:original.end_at}:LinksCalendar.inputRange(data.start_at,data.start_time,data.end_at,data.end_time,adminTimezone);Object.assign(data,range);data.calendar_timed=unchanged?original.calendar_timed:!!(data.start_time||data.end_time);delete data.start_time;delete data.end_time;return data}
let promotionTimer,pendingConflict,lastPromotionCheck;
const periodText=value=>value?new Intl.DateTimeFormat("fr-FR",{dateStyle:"medium",timeStyle:"short",timeZone:adminTimezone}).format(new Date(value)):"sans limite";
async function checkPromotion(){
 clearTimeout(promotionTimer);promotionTimer=setTimeout(async()=>{const node=$("promo-availability");let data;try{data=formBlock()}catch(error){node.hidden=false;node.textContent=error.message;return}if(!["promo","featured"].includes(data.type)||!data.active||data.draft){node.hidden=true;lastPromotionCheck={allowed:true};return}try{const payload={...data,internal_name:data.internal_name||"Nouvelle promotion",title:data.title||"Promotion",url:data.url||"https://example.invalid"};lastPromotionCheck=await api("/api/promotions/check",{method:"POST",body:JSON.stringify(payload)});node.hidden=false;node.className="wide availability "+(lastPromotionCheck.allowed?(lastPromotionCheck.maximum===3?"warning":"success"):"error");node.innerHTML=lastPromotionCheck.allowed?(lastPromotionCheck.maximum===3?`⚠️ Période chargée — ${lastPromotionCheck.maximum}/3 promotions`:`✅ Période disponible — ${lastPromotionCheck.maximum}/3 promotions`):`❌ Limite dépassée — ${lastPromotionCheck.maximum} promotions seraient actives simultanément`;if(lastPromotionCheck.overlaps.length){const first=lastPromotionCheck.overlaps[0];node.innerHTML+=`<small>Une promotion est déjà prévue : ${esc(first.internal_name)}, de ${esc(periodText(first.start_at))} à ${esc(periodText(first.end_at))}.</small>`}}catch(error){node.hidden=false;node.className="wide availability error";node.textContent=error.message;lastPromotionCheck={allowed:false}}},180)
}
async function saveBlock(data){if(blockUpload.pending())throw Error("Attendre la fin de l’import.");const id=data.id;delete data.id;await api(id?"/api/content/"+id:"/api/content",{method:id?"PUT":"POST",body:JSON.stringify(data)});blockDialog.close();await loadContent();await loadStats();say("Bloc enregistré.")}
function showConflict(data,check){pendingConflict={data,check};const segment=check.segments[0];$("conflict-period").textContent=segment?`Du ${periodText(segment.start_at)} au ${periodText(segment.end_at)}, ${segment.count} promotions seraient actives simultanément.`:"La période contient un chevauchement.";const items=check.overlaps;$("conflict-items").innerHTML=items.map(item=>`<article><strong>${esc(item.internal_name)}</strong><small>${esc(item.status)} · ${esc(periodText(item.start_at))} → ${esc(periodText(item.end_at))}${item.active_days!==null?` · active depuis ${item.active_days} jour(s)`:""}</small></article>`).join("");$("replacement-promo").replaceChildren(...items.map(item=>new Option(item.internal_name+(item.active_days!==null?` — ${item.active_days} j`:""),item.id)));$("conflict-dialog").showModal()}

let blockPreviewTimer,blockPreviewData;
function preview(){
 updatePromoEditor();blockPreviewData=formBlock();$("clear-block-image").disabled=!blockPreviewData.image;
 clearTimeout(blockPreviewTimer);blockPreviewTimer=setTimeout(renderBlockPreview,80);
}
function renderBlockPreview(){
 const data=blockPreviewData;if(!data)return;publicTimezone=adminTimezone;
 const promo=["promo","featured"].includes(data.type);data.title=data.title||data.internal_name||"Titre du lien";
 const card=promo?renderOffer(data):renderBlock(data);card.querySelectorAll("a,button").forEach(node=>{node.removeAttribute("href");node.setAttribute("disabled","");node.tabIndex=-1});if(card.tagName==="A")card.removeAttribute("href");
 let frame=$("block-preview").querySelector("iframe");
 if(!frame){frame=document.createElement("iframe");frame.className="promo-preview-frame";frame.title="Aperçu public du contenu";frame.setAttribute("sandbox","allow-same-origin");$("block-preview").replaceChildren(frame);frame.addEventListener("load",renderBlockPreview);frame.srcdoc='<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/preview/style.css"><link rel="stylesheet" href="/preview/icons.css"><link rel="stylesheet" href="/preview/preview.css"><link rel="stylesheet" href="/preview/theme.css"></head><body><div id="preview-root"></div></body></html>';return}
 const doc=frame.contentDocument,root=doc?.getElementById('preview-root');if(!root)return;
 root.className=promo?'carousel':'links';const wrapper=doc.createElement('div');wrapper.className=promo?'carousel-slide':'preview-link';wrapper.append(doc.importNode(card,true));root.replaceChildren(wrapper);
 const resize=()=>{frame.style.height=doc.documentElement.scrollHeight+'px'};
 LinksTheme.apply(window.linksActiveAppearance,doc).then(resize);resize();root.querySelectorAll('img').forEach(img=>img.addEventListener('load',resize,{once:true}));
}
$("clear-block-image").addEventListener("click",()=>{blockUpload.invalidate();blockForm.elements.image.value="";$("block-image-file").value="";preview()});
blockForm.addEventListener("input",event=>{if(event.target===blockForm.elements.image)blockUpload.invalidate();try{preview()}catch(error){say(error.message,true)}checkPromotion()});blockForm.addEventListener("submit",async event=>{event.preventDefault();if(event.submitter?.value==="cancel"){blockDialog.close();return}try{const data=formBlock();if(["promo","featured"].includes(data.type)&&data.active&&!data.draft){const payload={...data};lastPromotionCheck=await api("/api/promotions/check",{method:"POST",body:JSON.stringify(payload)});if(!lastPromotionCheck.allowed){showConflict(data,lastPromotionCheck);return}}await saveBlock(data)}catch(error){say(error.message,true)}});
$("block-image-file").addEventListener("change",event=>blockUpload.run(event.target,url=>{blockForm.elements.image.value=url;preview()}));

document.querySelectorAll("[data-preview]").forEach(button=>button.addEventListener("click",()=>{document.querySelectorAll("[data-preview]").forEach(x=>x.classList.toggle("active",x===button));$("block-preview").classList.toggle("mobile",button.dataset.preview==="mobile")}));

const buttonDialog=$("button-dialog"),buttonForm=$("button-form");
function openButton(item={}){buttonForm.querySelector("[data-dialog-feedback]")?.remove();buttonForm.reset();buttonForm.elements.id.value=item.id||"";buttonForm.elements.custom_icon.value=item.custom_icon||"";for(const key of ["icon","label","url"])if(item[key]!==undefined)buttonForm.elements[key].value=key==="icon"&&item[key]==="email"?"mail":item[key];buttonForm.elements.active.checked=item.active!==false;$("button-title").textContent=item.id?"Modifier le bouton":"Nouveau bouton";buttonDialog.showModal();window.LinksShortcuts?.open()}
buttonForm.addEventListener("submit",async event=>{event.preventDefault();if(event.submitter?.value==="cancel"){buttonDialog.close();return}try{const data=Object.fromEntries(new FormData(buttonForm)),id=data.id;delete data.id;data.active=buttonForm.elements.active.checked;await api(id?"/api/buttons/"+id:"/api/buttons",{method:id?"PUT":"POST",body:JSON.stringify(data)});buttonDialog.close();await loadButtons();say("Bouton enregistré.")}catch(error){say(error.message,true)}});

document.addEventListener("click",async event=>{const action=event.target.closest("[data-action]");if(!action)return;const item=action.closest(".list-item"),id=item?.dataset.id;try{switch(action.dataset.action){case"copy-story":return copyStory(action,id);case"new-block":return openBlock();case"new-campaign":return openBlock({},"promo");case"new-button":return openButton();case"edit":return openBlock(state.content.find(x=>x.id===id));case"edit-button":return openButton(state.buttons.find(x=>x.id===id));case"duplicate":await api(`/api/content/${id}/duplicate`,{method:"POST",body:"{}"});await loadContent();return say("Bloc dupliqué en brouillon.");case"archive":await api(`/api/content/${id}/archive`,{method:"POST",body:"{}"});await loadContent();return say("Bloc archivé.");case"restore":await api(`/api/content/${id}/restore`,{method:"POST",body:"{}"});await loadArchives();return say("Bloc restauré.");case"delete":if(confirm("Supprimer définitivement ce bloc et ses statistiques de page ? L’historique Story sera conservé. Cette action est irréversible.")){const fromArchives=!!item.closest("#archive-list");await api("/api/content/"+id,{method:"DELETE"});fromArchives?await loadArchives():await loadContent();say("Bloc supprimé. Historique Story conservé.")}return;case"delete-button":if(confirm("Supprimer ce bouton et ses statistiques ?")){await api("/api/buttons/"+id,{method:"DELETE"});await loadButtons()}return;case"up":return move(item.parentNode,item,-1,item.parentNode.id==="button-list");case"down":return move(item.parentNode,item,1,item.parentNode.id==="button-list")}}catch(error){say(error.message,true)}});
const editable=item=>Object.fromEntries(["type","internal_name","title","description","url","icon","image","badge","cta","promo_code","priority","active","draft","start_at","end_at","calendar_timed"].map(key=>[key,item[key]]));
$("conflict-dialog").addEventListener("click",async event=>{const action=event.target.closest("[data-conflict]")?.dataset.conflict;if(!action||!pendingConflict)return;try{if(action==="dates"){$("conflict-dialog").close();return}if(action==="next"){const next=pendingConflict.check.next_start;if(!next){say("Aucun créneau automatique trouvé : modifie les dates.",true);$("conflict-dialog").close();return}const oldStart=pendingConflict.data.start_at?new Date(pendingConflict.data.start_at):new Date(),oldEnd=pendingConflict.data.end_at?new Date(pendingConflict.data.end_at):null,newStart=new Date(next);const fields=LinksCalendar.inputFields({start_at:next,end_at:oldEnd?new Date(newStart.getTime()+Math.max(60000,oldEnd-oldStart)).toISOString():null},adminTimezone);for(const [key,value] of Object.entries(fields))blockForm.elements[key].value=value;$("conflict-dialog").close();preview();checkPromotion();say("Premier créneau disponible proposé. La date reste modifiable.");return}if(action==="replace"){const id=$("replacement-promo").value,target=state.content.find(item=>item.id===id);if(!target||!confirm(`Désactiver « ${target.internal_name} » et enregistrer cette promotion ?`))return;await api("/api/promotions/replace",{method:"POST",body:JSON.stringify({replace_id:id,content:pendingConflict.data})});$("conflict-dialog").close();blockDialog.close();await loadContent();say("Promotion remplacée et désactivée.")}}catch(error){say(error.message,true)}});

let settingsLoading=0;
async function loadSettings(){profileUploads.forEach(g=>g.invalidate());settingsLoading++;const fields=[...$("settings-form").querySelectorAll('[name],button[type="submit"],button.primary'),...document.querySelectorAll('button[form="settings-form"]')];fields.forEach(x=>x.disabled=true);try{
 state.settings=await api("/api/settings");adminTimezone=state.settings.timezone||"UTC";publicSiteUrl=state.settings.site_url||"";
 $("software-version").value=state.settings.app_version||"";
 for(const key of ["name","tagline","description","logo","avatar","footer_owner","site_url","timezone"])$("settings-form").elements[key].value=state.settings[key]||"";
 refreshProfileImages();
 for(const key of ["analytics_enabled"])$("settings-form").elements[key].checked=!!state.settings[key];
 $("settings-form").elements.source_rules.value=JSON.stringify(state.settings.source_rules||[],null,2);
 $("admin-name").textContent=state.settings.name||"Links";$("admin-owner").textContent=(state.settings.name||"Links")+" · Administration";
 $("admin-logo").hidden=!state.settings.logo;if(state.settings.logo)$("admin-logo").src=state.settings.logo;
 document.querySelectorAll(".public-link").forEach(a=>{a.hidden=!publicSiteUrl;a.href=publicSiteUrl||"#"});$("admin-timezone").textContent=adminTimezone;
 for(const r of state.settings.source_rules||[])names[r.key]=r.label;
 const select=$("share-source");select.querySelectorAll("[data-instance-source]").forEach(x=>x.remove());for(const r of state.settings.source_rules||[]){const o=new Option(r.label,r.aliases[0]||r.key);o.dataset.instanceSource="1";select.append(o)}shareUrl();
 $("access-form").elements.mode.value=state.settings.auth_mode;accessFields();$("logout").hidden=state.settings.auth_mode!=="local";
}catch(error){say(error.message,true)}finally{if(--settingsLoading===0)fields.forEach(x=>x.disabled=false)}}
$("settings-form").addEventListener("submit",async event=>{event.preventDefault();try{
 const data=Object.fromEntries(new FormData(event.target));data.analytics_enabled=event.target.elements.analytics_enabled.checked;data.source_rules=JSON.parse(data.source_rules||"[]");
 await api("/api/settings",{method:"POST",body:JSON.stringify(data)});await loadSettings();say("Réglages enregistrés.");$("settings-save-status").textContent="";$("analytics-save-status").textContent="";const feedback=event.submitter?.closest("#analytics-panel")?$("analytics-save-status"):$("settings-save-status");feedback.textContent="Préférences enregistrées."
}catch(error){say(error.message,true)}});
async function initializeAdmin(){try{const auth=await api("/api/auth/status");csrf=auth.csrf||"";await LinksTheme.ready;window.linksActiveAppearance=(await api('/api/public-config')).appearance;await loadSettings();await loadStats()}catch(error){say(error.message,true)}}

// Sharing and backup remain in Settings, without another navigation section.
let publicSiteUrl='';
function shareUrl(){if(!publicSiteUrl){$("share-url").value="";return}const url=new URL(publicSiteUrl);url.searchParams.set('utm_source',$('share-source').value);$('share-url').value=url.href;}
$('share-source').addEventListener('change',shareUrl);shareUrl();
$('copy-share').addEventListener('click',async()=>{
 const input=$('share-url');
 try{if(!navigator.clipboard)throw new Error();await navigator.clipboard.writeText(input.value);$('share-status').textContent='Lien copié.';}
 catch{input.focus();input.select();let copied=false;try{copied=document.execCommand('copy');}catch{}$('share-status').textContent=copied?'Lien copié.':'Le lien est sélectionné : copie-le avec le menu de ton appareil.';}
});
function downloadBlob(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
async function backup(){const response=await fetch('/api/backup',{cache:'no-store'});if(response.status===401){location.href="/login";throw new Error("Connexion requise.")}if(!response.ok){let message='Sauvegarde impossible.';try{message=(await response.json()).error||message;}catch{}throw new Error(message);}return response.blob();}
$('download-backup').addEventListener('click',async()=>{const button=$('download-backup');button.disabled=true;$('backup-status').textContent='Préparation du fichier…';try{downloadBlob(await backup(),'links-sauvegarde-'+new Date().toISOString().slice(0,10)+'.json');$('backup-status').textContent='Téléchargement lancé. Conserve ce fichier.';}catch(error){$('backup-status').textContent=error.message;}finally{button.disabled=false;}});
$('restore-backup').addEventListener('change',async event=>{
 const input=event.target,file=input.files[0];if(!file)return;
 try{
  if(file.size>64*1024*1024)throw new Error('Le fichier dépasse 64 Mo.');
  const content=await file.text();let parsed;try{parsed=JSON.parse(content);}catch{throw new Error('Ce fichier JSON est illisible.');}
  if(!['links-backup','domotik-links-backup'].includes(parsed.format)||![1,2,3].includes(parsed.version)||!Array.isArray(parsed.tables?.content_blocks)||!Array.isArray(parsed.tables?.top_buttons))throw new Error('Ce fichier n’est pas une sauvegarde Links compatible.');
  if(!confirm(`Restaurer ${parsed.tables.content_blocks.length} blocs et ${parsed.tables.top_buttons.length} boutons ? Les contenus, images utilisées, réglages et statistiques actuels seront remplacés. Télécharge d’abord une sauvegarde si tu souhaites pouvoir revenir en arrière.`))return;
  input.disabled=true;$('download-backup').disabled=true;$('backup-status').textContent='Vérification et restauration…';
  await api('/api/restore',{method:'POST',body:content});if(state.settings.auth_mode==='local'){location.href='/login';return}await loadSettings();await loadStats();state.content=[];state.buttons=[];state.archives=[];$('backup-status').textContent='Sauvegarde restaurée. Tes données sont disponibles.';
 }catch(error){$('backup-status').textContent='Restauration non effectuée : '+error.message;}finally{input.disabled=false;$('download-backup').disabled=false;input.value='';}
});


// Interface preferences belong exclusively to the admin origin and use a distinct key.
const themeKey="links-admin-theme",themeMedia=matchMedia("(prefers-color-scheme: dark)");
function applyAdminTheme(preference){
 const mode=["light","dark","system"].includes(preference)?preference:"system";
 $("theme-select").value=mode;
 document.documentElement.dataset.theme=mode==="system"?(themeMedia.matches?"dark":"light"):mode;
 document.querySelector(".product-brand").src=document.documentElement.dataset.theme==="light"?"/brand-light.svg":"/brand.svg";
}
let themePreference="dark";try{themePreference=localStorage.getItem(themeKey)||"dark"}catch{}
applyAdminTheme(themePreference);
$("theme-select").addEventListener("change",event=>{applyAdminTheme(event.target.value);try{localStorage.setItem(themeKey,event.target.value)}catch{say("Thème appliqué. La mémorisation est indisponible dans ce navigateur.",true)}});
themeMedia.addEventListener("change",()=>{if($("theme-select").value==="system")applyAdminTheme("system")});

const iconPaths={
 dashboard:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
 links:'<path d="m10 13 4-4m-6 6-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 3 1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0"/>',
 buttons:'<rect x="3" y="7" width="18" height="10" rx="3"/><path d="M8 12h8"/>',
 archive:'<rect x="3" y="3" width="18" height="4" rx="1"/><path d="M5 7v13h14V7M10 11h4"/>',
 settings:'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/>',
 external:'<path d="M14 3h7v7m0-7L10 14M10 3H4v17h17v-6"/>',
 theme:'<circle cx="12" cy="12" r="8"/><path d="M12 4v16"/>',
 visits:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
 click:'<path d="m5 3 14 9-6 1-3 6-5-16Zm8 11 4 6"/>',
 chart:'<path d="M4 3v17h17M8 16v-4m5 4V8m5 8V5"/>',
 story:'<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M10 18h4m-3-12 4 3-4 3V6Z"/>'
};
document.querySelectorAll("[data-icon]").forEach(node=>{node.innerHTML=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[node.dataset.icon]||""}</svg>`});
async function loadCampaigns(metrics=new Map()){try{
 const campaigns=(await api("/api/content")).items;renderTimeline(campaigns);
 const items=campaigns.filter(item=>item.type!=="classic"&&item.status==="Actif").map(item=>{const value=metrics.get(item.id)||{clicks:0,shared:0,impressions:0,copies:0};return {...item,...value,pageClicks:value.clicks,sharedClicks:value.shared,totalClicks:value.clicks+value.shared,ctr:value.impressions?Math.round(value.clicks*1000/value.impressions)/10:null}});
 $("active-campaigns").innerHTML=items.length?items.map(item=>`<article class="campaign-card">${item.image?`<img src="${esc(item.image)}" alt="" loading="lazy">`:'<span class="type-mark" aria-hidden="true">↗</span>'}<div><strong>${esc(item.internal_name)}</strong><small>${esc(periodText(item.start_at||item.created_at))} → ${esc(periodText(item.end_at))}</small><span class="status active">Actif</span><div class="campaign-metrics"><span><small>Impressions</small><b>${fmt.format(item.impressions||0)}</b></span><span><small>Clics sur page</small><b>${fmt.format(item.pageClicks||0)}</b></span><span class="metric-shared"><small>Liens partagés</small><b>${fmt.format(item.sharedClicks||0)}</b></span><span class="metric-total"><small>Total clics</small><b>${fmt.format(item.totalClicks||0)}</b></span><span><small>CTR page</small><b>${item.ctr==null?"—":esc(item.ctr)+" %"}</b></span></div></div><button type="button" data-open-content aria-label="Gérer ${esc(item.internal_name)}">→</button></article>`).join(""):'<p class="empty">Aucune campagne en cours.</p>';
 }catch(error){$("active-campaigns").textContent=error.message}}

document.addEventListener("click",event=>{
 if(event.target.closest("[data-open-content]")){activate("content");document.querySelector("#content h2").setAttribute("tabindex","-1");document.querySelector("#content h2").focus()}
 document.querySelectorAll(".row-menu[open]").forEach(menu=>{if(!menu.contains(event.target)||event.target.closest("[data-action]"))menu.open=false});
});
document.addEventListener("keydown",event=>{if(event.key==="Escape")document.querySelectorAll(".row-menu[open]").forEach(menu=>{menu.open=false;menu.querySelector("summary").focus()})});

/* Footer quotations: local controls in Settings. */
let quotes=[],quotesPending=null,quotesAnalysisId=0,quotesPage=0;
const QUOTES_PAGE_SIZE=20;
function quoteText(value){const match=value.match(/^(.*?)(\s*\([^()]+\))$/s);return match?esc(match[1])+`<span class="quote-source">${esc(match[2])}</span>`:esc(value)}
function drawQuotes(){
 $("quotes-summary").textContent=quotes.length+" / 300 citations · "+quotes.filter(q=>q.active).length+" actives";
 $("quotes-clear").hidden=!quotes.length;
 $("quotes-limit").hidden=quotes.length<300;
 $("quote-form").querySelector("button").disabled=quotes.length>=300;
 const query=$("quotes-search").value.trim().toLocaleLowerCase('fr'),filter=$("quotes-filter").value;
 const matching=quotes.filter(q=>q.text.toLocaleLowerCase('fr').includes(query)&&(!filter||q.active===(filter==='active')));
 const pages=Math.max(1,Math.ceil(matching.length/QUOTES_PAGE_SIZE));quotesPage=Math.min(quotesPage,pages-1);
 $("quotes-page").textContent=`${matching.length} résultat(s) · page ${quotesPage+1} / ${pages}`;
 $("quotes-prev").disabled=quotesPage===0;$("quotes-next").disabled=quotesPage>=pages-1;
 $("quotes-list").innerHTML=matching.length?matching.slice(quotesPage*QUOTES_PAGE_SIZE,(quotesPage+1)*QUOTES_PAGE_SIZE).map(q=>`<article class="quote-row" data-quote-id="${esc(q.id)}"><p>${quoteText(q.text)}</p><div class="actions"><button type="button" class="quote-toggle" role="switch" aria-checked="${q.active}" ${q.pending?"disabled":""} aria-label="Activer ou désactiver la citation" data-quote-toggle>${q.active?"● Activé":"○ Désactivé"}</button><button type="button" data-quote-delete ${q.pending?"disabled":""}>Supprimer</button></div></article>`).join(""):(quotes.length?"<p>Aucune citation ne correspond aux filtres.</p>":"<p>Aucune citation pour le moment.</p>");
}
for(const id of ['quotes-search','quotes-filter'])$(id).addEventListener('input',()=>{quotesPage=0;drawQuotes()});
$('quotes-prev').onclick=()=>{quotesPage--;drawQuotes()};$('quotes-next').onclick=()=>{quotesPage++;drawQuotes()};
async function loadQuotes(){try{quotes=(await api("/api/quotes")).items;drawQuotes()}catch(error){$("quotes-feedback").textContent=error.message}}
function clearQuoteAnalysis(){quotesAnalysisId++;quotesPending=null;$("quotes-analysis").hidden=true}
$("quotes-batch").addEventListener("input",clearQuoteAnalysis);
async function analyzeQuotes(value,imported=false){
 clearQuoteAnalysis();const analysisId=quotesAnalysisId;
 const result=await api("/api/quotes/analyze",{method:"POST",body:JSON.stringify({text:value})});
 if(analysisId!==quotesAnalysisId)return;
 quotesPending={text:value,imported,allowed:result.allowed};
 $("quotes-analysis-summary").textContent=result.detected+" citations détectées · "+result.new+" nouvelles · "+result.allowed+" peuvent être ajoutées · "+result.excess+" dépassent la limite de 300 · "+result.duplicates+" doublons";
 $("quotes-confirm").textContent=(imported?"Importer ":"Ajouter ")+result.allowed+" citations";
 $("quotes-confirm").disabled=!result.allowed;$("quotes-analysis").hidden=false;
}
$("quote-form").addEventListener("submit",async event=>{
 event.preventDefault();if(quotes.length>=300){$("quotes-feedback").textContent="Limite de 300 citations atteinte.";return}const button=event.target.querySelector("button");button.disabled=true;
 try{const result=await api("/api/quotes",{method:"POST",body:JSON.stringify({text:event.target.elements.text.value,single:true})});event.target.reset();await loadQuotes();$("quotes-feedback").textContent=result.new?"Citation ajoutée.":"Cette citation existe déjà."}catch(error){$("quotes-feedback").textContent=error.message}finally{button.disabled=quotes.length>=300}
});
$("quotes-batch-form").addEventListener("submit",async event=>{
 event.preventDefault();const button=event.target.querySelector('button[type="submit"]');button.disabled=true;
 try{await analyzeQuotes($("quotes-batch").value)}catch(error){$("quotes-feedback").textContent=error.message}finally{button.disabled=false}
});
$("quotes-file").addEventListener("change",async event=>{
 clearQuoteAnalysis();const file=event.target.files[0];if(!file)return;
 try{if(!/\.txt$/i.test(file.name)||file.size>1024*1024)throw Error("Choisis un fichier .txt UTF-8 de 1 Mo maximum.");const value=new TextDecoder("utf-8",{fatal:true}).decode(await file.arrayBuffer());$("quotes-batch").value=value;await analyzeQuotes(value,true)}catch(error){$("quotes-feedback").textContent=error.message}finally{event.target.value=""}
});
$("quotes-confirm").addEventListener("click",async event=>{
 if(!quotesPending)return;const pending=quotesPending;event.target.disabled=true;
 try{const result=await api("/api/quotes",{method:"POST",body:JSON.stringify({text:pending.text,limit:pending.allowed})});clearQuoteAnalysis();$("quotes-batch").value="";await loadQuotes();$("quotes-feedback").textContent=result.added+" citations ajoutées · "+result.duplicates+" doublons ignorés · "+result.excess+" au-delà de la limite."}catch(error){$("quotes-feedback").textContent=error.message;event.target.disabled=false}
});
$("quotes-list").addEventListener("click",async event=>{
 const toggle=event.target.closest("[data-quote-toggle]"),remove=event.target.closest("[data-quote-delete]");
 if(!toggle&&!remove)return;const row=event.target.closest("[data-quote-id]"),q=quotes.find(x=>x.id===row.dataset.quoteId);if(!q||q.pending)return;
 if(remove){if(!confirm("Supprimer définitivement cette citation ?"))return;q.pending=true;remove.disabled=true;row.querySelector("[data-quote-toggle]").disabled=true;try{await api("/api/quotes/"+q.id,{method:"DELETE"});quotes=quotes.filter(x=>x!==q);drawQuotes()}catch(error){q.pending=false;drawQuotes();$("quotes-feedback").textContent=error.message}return}
 const previous=q.active;q.active=!previous;q.pending=true;toggle.disabled=true;toggle.setAttribute("aria-checked",String(q.active));toggle.textContent=q.active?"● Activé":"○ Désactivé";$("quotes-summary").textContent=quotes.length+" / 300 citations · "+quotes.filter(x=>x.active).length+" actives";
 try{await api("/api/quotes/"+q.id,{method:"PUT",body:JSON.stringify({active:q.active})})}catch(error){q.active=previous;$("quotes-feedback").textContent=error.message}finally{q.pending=false;drawQuotes()}
});



$("quotes-clear").addEventListener("click",async event=>{
 if(!quotes.length||!confirm("Supprimer définitivement les "+quotes.length+" citations ? Cette action est irréversible."))return;
 const button=event.target;button.disabled=true;
 try{await api("/api/quotes",{method:"DELETE"});quotes=[];clearQuoteAnalysis();drawQuotes();$("quotes-feedback").textContent="Toutes les citations ont été supprimées."}catch(error){$("quotes-feedback").textContent=error.message}finally{button.disabled=false}
});

function accessFields(){const form=$("access-form"),local=form.elements.mode.value==="local";$("local-account-fields").hidden=!local;$("external-confirm-label").hidden=local;$("current-password-label").hidden=state.settings.auth_mode!=="local";}
$("access-form").elements.mode.addEventListener("change",accessFields);
$("access-form").addEventListener("submit",async event=>{event.preventDefault();try{const data=Object.fromEntries(new FormData(event.target));data.confirm_external=event.target.elements.confirm_external.checked;data.csrf=csrf;await api("/api/auth/access",{method:"POST",body:JSON.stringify(data)});location.reload()}catch(error){say(error.message,true)}});
$("logout").addEventListener("click",async()=>{await api("/api/auth/logout",{method:"POST",body:JSON.stringify({csrf})});location.href="/login"});
const profileUploads=[],profileUploadByKey={};
for(const input of document.querySelectorAll("[data-profile-upload]")){const key=input.dataset.profileUpload,guard=LinksUploads.create($("settings-form"),{statusHost:input.closest('.profile-image-editor'),active:()=>$("settings").classList.contains('active')});profileUploads.push(guard);profileUploadByKey[key]=guard;input.addEventListener('change',()=>guard.run(input,url=>{$("settings-form").elements[key].value=url;refreshProfileImages()}))}

for(const button of document.querySelectorAll("[data-clear-profile]"))button.addEventListener("click",()=>{profileUploadByKey[button.dataset.clearProfile].invalidate();$("settings-form").elements[button.dataset.clearProfile].value="";refreshProfileImages()});
if(Intl.supportedValuesOf)$("timezones").replaceChildren(...Intl.supportedValuesOf("timeZone").map(x=>new Option(x,x)));
initializeAdmin();

function refreshProfileImages(){for(const key of ["logo","avatar"]){const value=$("settings-form").elements[key].value,img=document.querySelector(`[data-profile-image="${key}"]`);img.hidden=!value;if(value)img.src=value;else img.removeAttribute("src");document.querySelector(`[data-profile-placeholder="${key}"]`).hidden=!!value;document.querySelector(`[data-clear-profile="${key}"]`).disabled=!value;}}
for(const button of document.querySelectorAll("[data-replace-profile]"))button.addEventListener("click",()=>$("profile-"+button.dataset.replaceProfile+"-file").click());

async function loadYouTube(){const status=await api('/api/youtube');$('youtube-channel').value=status.channel;$('youtube-enabled').checked=status.enabled;$('youtube-state').textContent=status.configured?'Configuré':'Non configuré';$('youtube-key').value='';$('youtube-key').disabled=status.key_managed;$('youtube-key-info').textContent=status.key_managed?'Clé gérée par le serveur.':status.key_configured?'Clé enregistrée. Laissez vide pour la conserver.':'La clé est conservée sur le serveur et ne sera jamais affichée.';$('youtube-remove-key').hidden=!status.key_configured||status.key_managed;if(status.legacy)$('youtube-feedback').textContent='La source serveur existante est conservée. Vous pouvez la tester sans modifier sa configuration.';}
function youtubePayload(){return {channel:$('youtube-channel').value.trim(),api_key:$('youtube-key').value,enabled:$('youtube-enabled').checked}}
function youtubePreview(result){const node=$('youtube-preview');node.replaceChildren();node.hidden=false;if(result.channel_name){const heading=document.createElement('strong');heading.textContent=result.channel_name;node.append(heading)}if(!result.video){const p=document.createElement('p');p.textContent='Aucune vidéo publique publiée détectée.';node.append(p);return}const link=document.createElement('a');link.href=result.video.url;link.target='_blank';link.rel='noopener noreferrer';if(result.video.thumbnail){const img=document.createElement('img');img.src=result.video.thumbnail;img.alt='Miniature de la dernière vidéo';link.append(img)}const title=document.createElement('strong');title.textContent=result.video.title;link.append(title);const date=document.createElement('small');date.textContent=periodText(result.video.published);link.append(date);node.append(link)}
async function youtubeAction(test){const buttons=$('youtube-form').querySelectorAll('button');buttons.forEach(b=>b.disabled=true);$('youtube-feedback').textContent=test?'Recherche de la dernière vidéo…':'Enregistrement…';try{const result=await api(test?'/api/youtube/test':'/api/youtube',{method:'POST',body:JSON.stringify(youtubePayload())});if(test){youtubePreview(result);$('youtube-feedback').textContent='Connexion réussie.'}else{await loadSettings();await loadYouTube();await loadContent();$('youtube-feedback').textContent='Configuration YouTube enregistrée.'}}catch(error){$('youtube-feedback').textContent=error.message;}finally{buttons.forEach(b=>b.disabled=false)}}
$('youtube-form').addEventListener('submit',event=>{event.preventDefault();youtubeAction(false)});$('youtube-test').addEventListener('click',()=>youtubeAction(true));$('youtube-remove-key').addEventListener('click',async()=>{try{await api('/api/youtube',{method:'POST',body:JSON.stringify({...youtubePayload(),api_key:'',remove_key:true})});await loadSettings();await loadYouTube();$('youtube-feedback').textContent='Clé retirée.'}catch(error){$('youtube-feedback').textContent=error.message}});
