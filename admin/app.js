"use strict";
const $=id=>document.getElementById(id),fmt=new Intl.NumberFormat("fr-FR");
const names={"direct-inconnu":"Direct / inconnu","autre-site":"Autre site","autre-campagne":"Autre campagne",youtube:"YouTube",instagram:"Instagram","instagram-story":"Instagram Story",facebook:"Facebook",google:"Google",discord:"Discord",newsletter:"Newsletter",tiktok:"TikTok",site:"Site",mail:"E-mail",qr:"QR"};
let csrf="",adminTimezone="UTC";
const state={content:[],buttons:[],archives:[],settings:{},chart:[]};
const api=async(path,options={})=>{const response=await fetch(path,{cache:"no-store",...options,headers:{"Content-Type":"application/json","X-Links-Request":"1","X-Links-CSRF":csrf,...(options.headers||{})}});if(response.status===401){location.href="/login";throw new Error("Connexion requise.")}if(!response.ok){let message="Une erreur est survenue.";try{message=(await response.json()).error||message}catch{}throw new Error(message)}return response.status===204?null:response.json()};
const say=(message,error=false)=>{const dialog=[...document.querySelectorAll("dialog[open]")].at(-1);if(dialog){let feedback=dialog.querySelector("[data-dialog-feedback]");if(!feedback){feedback=document.createElement("p");feedback.dataset.dialogFeedback="";feedback.className="editor-feedback";feedback.setAttribute("role","alert");(dialog.querySelector("form")||dialog).prepend(feedback)}feedback.hidden=false;feedback.textContent=message;feedback.classList.toggle("notice-error",error)}const node=$("notice");node.textContent=message;node.classList.toggle("notice-error",error);clearTimeout(say.timer);say.timer=setTimeout(()=>node.textContent="",4000)};
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const typeName={classic:"Lien",featured:"Mise en avant",promo:"Campagne"};
const statusClass=value=>({Actif:"active",Programmé:"scheduled",Expiré:"expired",Brouillon:"draft"}[value]||"");
function activate(id){document.querySelectorAll(".view").forEach(x=>x.classList.toggle("active",x.id===id));document.querySelectorAll(".tabs button").forEach(x=>x.classList.toggle("active",x.dataset.tab===id));syncNavigation();$("topbar-current").textContent=document.querySelector(".tabs button.active")?.textContent.trim()||"Links";if(id==="dashboard"){loadStats()}if(id==="content")loadContent();if(id==="buttons")loadButtons();if(id==="archives")loadArchives();if(id==="settings"){loadSettings();loadQuotes()}}
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
function chartBuckets(days){
 const size=days.length>30?7:1,result=[];
 for(let i=0;i<days.length;i+=size){const slice=days.slice(i,i+size);result.push({start:slice[0][0],end:slice.at(-1)[0],views:slice.reduce((n,d)=>n+d[1],0),clicks:slice.reduce((n,d)=>n+d[2],0)})}
 return result;
}
let chartRenderedWidth=0;
function chart(days){
 state.chart=days;const root=$("chart"),buckets=chartBuckets(days),width=Math.max(200,root.clientWidth),left=38,right=width-8,bottom=190,height=155,slot=(right-left)/Math.max(1,buckets.length),barWidth=Math.min(32,slot*.72),max=Math.max(1,...buckets.flatMap(x=>[x.views,x.clicks]));
 chartRenderedWidth=root.clientWidth;
 const short=d=>d.slice(8,10)+"/"+d.slice(5,7),description=b=>`${short(b.start)}${b.start!==b.end?" – "+short(b.end):""} : ${fmt.format(b.views)} visites · ${fmt.format(b.clicks)} clics`;
 const stride=Math.max(1,Math.ceil(buckets.length/Math.max(2,Math.floor((right-left)/55))));
 const groups=buckets.map((b,i)=>{const center=left+slot*(i+.5),series=[{value:b.views,cls:"visits-bar"},{value:b.clicks,cls:"clicks-bar"}].sort((a,b)=>b.value-a.value);
 const bars=series.map((s,j)=>{const w=barWidth,h=s.value*height/max;return `<rect class="${s.cls}" x="${center-w/2}" y="${bottom-h}" width="${w}" height="${h}" rx="${Math.min(5,w/3)}"/>`}).join("");
 const active=b.views>0||b.clicks>0,close=Math.abs(b.views-b.clicks)*height/max<16;
 const markers=active?series.map((s,j)=>{const y=bottom-s.value*height/max,labelY=close?bottom-series[0].value*height/max-20+j*14:y-7;return `<g class="chart-value ${s.cls}-value"><line x1="${center-barWidth/2}" x2="${center+barWidth/2}" y1="${y}" y2="${y}"/><text text-anchor="middle" x="${center}" y="${labelY}">${fmt.format(s.value)}</text></g>`}).join(""):"";
 const label=i%stride===0?`<text text-anchor="middle" x="${center}" y="213">${short(b.start)}</text>`:"";
 return `<g class="chart-bucket" role="button" tabindex="0" data-bucket="${i}" aria-label="${esc(description(b))}"><title>${esc(description(b))}</title><rect class="chart-hit" x="${left+i*slot}" y="25" width="${slot}" height="170"/>${bars}<g class="chart-values${slot>=34||buckets.filter(x=>x.views||x.clicks).length===1?" always":""}">${markers}</g>${label}</g>`}).join("");
 root.innerHTML=`<svg viewBox="0 0 ${width} 225" role="group" aria-label="Visites et clics ${days.length>30?"par semaine":"par jour"}"><defs><linearGradient id="visits-fill" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" class="visits-stop-start"/><stop offset="100%" class="visits-stop-end"/></linearGradient><linearGradient id="clicks-fill" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" class="clicks-stop-start"/><stop offset="100%" class="clicks-stop-end"/></linearGradient><filter id="bar-shadow" x="-50%" y="-30%" width="200%" height="170%"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000" flood-opacity=".28"/></filter></defs><line class="chart-grid" x1="${left}" x2="${right}" y1="35" y2="35"/><line class="chart-grid" x1="${left}" x2="${right}" y1="${bottom}" y2="${bottom}"/><text x="2" y="39">${fmt.format(max)}</text><text x="2" y="194">0</text>${groups}</svg>`;
 const show=index=>{const b=buckets[index];if(!b)return;$("chart-detail").textContent=description(b);root.querySelectorAll("[data-bucket]").forEach(g=>g.classList.toggle("selected",Number(g.dataset.bucket)===index))};
 root.onclick=event=>{const g=event.target.closest("[data-bucket]");if(g)show(Number(g.dataset.bucket))};
 if(root.chartFocusHandler)root.removeEventListener("focusin",root.chartFocusHandler);
 root.chartFocusHandler=event=>{const g=event.target.closest("[data-bucket]");if(g)show(Number(g.dataset.bucket))};
 root.addEventListener("focusin",root.chartFocusHandler);
 root.onkeydown=event=>{const g=event.target.closest("[data-bucket]");if(!g)return;if(event.key==="Enter"||event.key===" "){event.preventDefault();show(Number(g.dataset.bucket))}else if(event.key==="ArrowRight"||event.key==="ArrowLeft"){event.preventDefault();const index=Math.max(0,Math.min(buckets.length-1,Number(g.dataset.bucket)+(event.key==="ArrowRight"?1:-1)));root.querySelector(`[data-bucket="${index}"]`).focus()}};
 $("chart-detail").textContent=buckets.length?"Touchez une barre pour afficher les chiffres." : "Aucune donnée sur cette période.";
}

async function loadStats(){try{
 const range=dates(),data=await api("/api/stats?"+new URLSearchParams(range)),stories=data.stories||[],previous=$("source").value;
 const sources=[...new Set([...data.rows.map(x=>x.source),...stories.map(x=>x.source),...(data.promo_code_copies||[]).map(x=>x.source),...(data.campaign_metrics||[]).map(x=>x.source),...(stories.length?["instagram"]:[])])].sort();
 $("source").replaceChildren(new Option("Toutes les sources",""),...sources.map(x=>new Option(names[x]||x,x)));if(sources.includes(previous))$("source").value=previous;
 const source=$("source").value,rows=data.rows.filter(x=>!source||x.source===source),storyRows=stories.filter(x=>!source||source==="instagram"||source===x.source),days=new Map(),bySource=new Map(),byLink=new Map(),labels=new Map(),byStory=new Map();
 for(let d=new Date(range.start+"T12:00Z");d<=new Date(range.end+"T12:00Z");d.setUTCDate(d.getUTCDate()+1))days.set(d.toISOString().slice(0,10),[0,0]);
 let views=0,clicks=0,storyClicks=0;
 for(const row of rows){labels.set(row.link,row.label||row.link);const pair=days.get(row.day);if(!pair)continue;if(row.kind==="view"){views+=row.total;pair[0]+=row.total;bySource.set(row.source,(bySource.get(row.source)||0)+row.total)}else if(row.kind==="click"){clicks+=row.total;pair[1]+=row.total;byLink.set(row.link,(byLink.get(row.link)||0)+row.total)}}
 for(const row of storyRows){storyClicks+=row.total;const item=byStory.get(row.promotion_id)||{label:row.label,total:0};item.total+=row.total;byStory.set(row.promotion_id,item);bySource.set("instagram",(bySource.get("instagram")||0)+row.total)}
 $("views").textContent=fmt.format(views);$("clicks").textContent=fmt.format(clicks);$("ratio").textContent=views?(clicks*100/views).toLocaleString("fr-FR",{maximumFractionDigits:1})+" %":"—";
 $("story-clicks").textContent=fmt.format(storyClicks);$("story-promos").textContent=fmt.format(byStory.size);
 $("story-list").innerHTML=byStory.size?[...byStory.values()].sort((a,b)=>b.total-a.total).map(x=>`<div class="story-row"><span>${esc(x.label)}</span><strong>${fmt.format(x.total)}</strong></div>`).join(""):'<p class="story-empty">Aucun clic Story sur cette période</p>';
 const campaignStats=new Map(),copyStats=new Map();
 for(const row of (data.campaign_metrics||[]).filter(x=>!source||x.source===source)){const value=campaignStats.get(row.id)||{clicks:0,impressions:0,copies:0};value[row.kind==="click"?"clicks":"impressions"]+=row.total;campaignStats.set(row.id,value)}
 let copyTotal=0;
 for(const row of (data.promo_code_copies||[]).filter(x=>!source||x.source===source)){copyTotal+=row.total;const metric=campaignStats.get(row.id)||{clicks:0,impressions:0,copies:0};metric.copies+=row.total;campaignStats.set(row.id,metric);const key=JSON.stringify([row.id,row.code]);const value=copyStats.get(key)||{id:row.id,name:row.name,code:row.code,total:0};value.total+=row.total;copyStats.set(key,value)}
 $("promo-copies").textContent=fmt.format(copyTotal);
 $("promo-copy-list").innerHTML=copyStats.size?[...copyStats.values()].sort((a,b)=>b.total-a.total).map(value=>{const impressions=campaignStats.get(value.id)?.impressions||0;return `<div class="promo-copy-row"><span>${esc(value.name)}</span><code>${esc(value.code)}</code><strong>${fmt.format(value.total)}</strong><small>Taux de copie : ${impressions?(value.total*100/impressions).toLocaleString("fr-FR",{maximumFractionDigits:1})+" %":"—"}</small></div>`}).join(""):'<p class="empty">Aucun code copié sur cette période.</p>';
 await loadCampaigns(campaignStats);
 chart([...days].map(([day,value])=>[day,...value]));const sorted=map=>[...map].sort((a,b)=>b[1]-a[1]);bars("top-links",sorted(byLink).slice(0,5).map(([key,value])=>[labels.get(key)||key,value]));bars("sources",sorted(bySource).map(([key,value])=>[names[key]||key,value]));
 }catch(error){say(error.message,true)}}

$("period").addEventListener("change",loadStats);$("source").addEventListener("change",loadStats);new ResizeObserver(()=>{const width=$("chart").clientWidth;if(width>0&&width!==chartRenderedWidth&&state.chart.length)chart(state.chart)}).observe($("chart"));

function canStory(item){try{const url=new URL(item.url);return ["http:","https:"].includes(url.protocol)&&!url.username&&!url.password&&url.hostname!==new URL(publicSiteUrl||location.origin).hostname}catch{return false}}
function storyButton(item){return item.type==="classic"?"":`<button data-action="copy-story" class="story-link-button" title="${canStory(item)?"Copier le lien Story tracké":"URL requise"}" aria-label="${canStory(item)?"Copier le lien Story tracké":"URL requise"}"${canStory(item)?"":" disabled"}>🔗</button>`}
async function copyStory(action,id){if(action.disabled)return;action.disabled=true;try{const {url}=await api(`/api/content/${id}/story-link`,{method:"POST",body:"{}"});let copied=false;try{await navigator.clipboard.writeText(url);copied=true}catch{let input=action.parentNode.querySelector(".story-copy");if(!input){input=document.createElement("input");input.className="story-copy";input.readOnly=true;input.setAttribute("aria-label","Lien Story tracké");action.parentNode.append(input)}input.value=url;input.focus();input.select();try{copied=document.execCommand("copy")}catch{}if(copied)input.remove()}say(copied?"Lien Story copié":"Lien sélectionné : copie-le avec le menu de ton appareil.")}catch(error){say(error.message,true)}finally{action.disabled=false}}
function itemHtml(item,archived=false){const performance=item.type==="classic"?`${fmt.format(item.clicks||0)} clics`:`${fmt.format(item.impressions||0)} impressions · ${fmt.format(item.clicks||0)} clics · CTR ${item.ctr===null?"—":item.ctr+" %"}`;return`<article class="list-item" draggable="${!archived}" data-id="${esc(item.id)}" data-group="${item.type==="classic"?"classic":"highlight"}"><span class="drag-handle">${archived?"◦":"⋮⋮"}</span><span class="type-mark">${item.type==="promo"?"▣":item.type==="featured"?"★":"↗"}</span><div class="item-copy"><strong>${esc(item.internal_name)}</strong><small>${esc(item.title)} · ${typeName[item.type]||item.type} · ${performance}</small><span class="status ${statusClass(item.status)}">${esc(item.status)}</span></div><div class="item-actions">${storyButton(item)}${archived?`<button data-action="restore">Restaurer</button>`:`<span class="move"><button data-action="up" aria-label="Monter">↑</button><button data-action="down" aria-label="Descendre">↓</button></span><button data-action="edit">Modifier</button><details class="row-menu"><summary aria-label="Autres actions pour ${esc(item.internal_name)}" title="Autres actions">···</summary><div class="row-menu-content"><button data-action="duplicate">Dupliquer</button><button data-action="archive">Archiver</button>`}<button data-action="delete" class="trash" title="Supprimer définitivement" aria-label="Supprimer définitivement">Supprimer</button>${archived?"":"</div></details>"}</div></article>`}
function renderContent(){const root=$("content-list"),high=state.content.filter(x=>x.type!=="classic"),classic=state.content.filter(x=>x.type==="classic"),active=high.filter(x=>x.status==="Actif").length,programmed=high.filter(x=>x.status==="Programmé").length;$("promo-count").textContent=`Promotions actives : ${active} / 3`;$("promo-scheduled").textContent=programmed?`• ${programmed} programmée${programmed>1?"s":""}`:"";const ordered=[...high].filter(x=>["Actif","Programmé"].includes(x.status)).sort((a,b)=>new Date(a.start_at||a.created_at)-new Date(b.start_at||b.created_at));$("promo-planning").innerHTML=ordered.length?ordered.map(x=>`<div class="planning-row"><span>${esc(periodText(x.start_at||x.created_at))} — ${esc(periodText(x.end_at))}</span><strong>${esc(x.internal_name)}</strong><small>${esc(x.status)}</small></div>`).join(""):'<p class="empty">Aucune promotion active ou programmée.</p>';root.innerHTML=(high.length?'<h3>Mises en avant et promos</h3>'+high.map(x=>itemHtml(x)).join(""):"")+(classic.length?'<h3>Liens permanents</h3>'+classic.map(x=>itemHtml(x)).join(""):"")||'<p class="empty">Aucun bloc. Ajoute ton premier lien.</p>';setupDrag(root)}
async function loadContent(){try{state.content=(await api("/api/content")).items;renderContent()}catch(error){say(error.message,true)}}
async function loadArchives(){try{state.archives=(await api("/api/content?archived=1")).items;$("archive-list").innerHTML=state.archives.length?state.archives.map(x=>itemHtml(x,true)).join(""):'<p class="empty">Aucune archive.</p>'}catch(error){say(error.message,true)}}
function buttonHtml(item){return`<article class="list-item" draggable="true" data-id="${esc(item.id)}"><span class="drag-handle">⋮⋮</span><span class="type-mark">${esc(item.icon.slice(0,1).toUpperCase())}</span><div class="item-copy"><strong>${esc(item.label)}</strong><small>${esc(item.url)} · ${fmt.format(item.clicks||0)} clics</small><span class="status ${item.active?"active":""}">${item.active?"Actif":"Désactivé"}</span></div><div class="item-actions"><span class="move"><button data-action="up">↑</button><button data-action="down">↓</button></span><button data-action="edit-button">Modifier</button><button data-action="delete-button" class="danger">Supprimer</button></div></article>`}
async function loadButtons(){try{state.buttons=(await api("/api/buttons")).items;$("button-list").innerHTML=state.buttons.length?state.buttons.map(buttonHtml).join(""):'<p class="empty">Aucun bouton.</p>';setupDrag($("button-list"),true)}catch(error){say(error.message,true)}}
function setupDrag(root,buttons=false){let dragged;root.ondragstart=event=>{dragged=event.target.closest(".list-item");dragged?.classList.add("dragging")};root.ondragend=()=>{dragged?.classList.remove("dragging");dragged=null};root.ondragover=event=>{event.preventDefault();const target=event.target.closest(".list-item");if(!dragged||!target||target===dragged||(!buttons&&target.dataset.group!==dragged.dataset.group))return;const box=target.getBoundingClientRect();target.parentNode.insertBefore(dragged,event.clientY<box.top+box.height/2?target:target.nextSibling)};root.ondrop=async event=>{event.preventDefault();await saveOrder(root,buttons)}}
async function saveOrder(root,buttons=false){try{const ids=[...root.querySelectorAll(".list-item")].map(x=>x.dataset.id);await api(buttons?"/api/buttons/reorder":"/api/content/reorder",{method:"POST",body:JSON.stringify({ids})});buttons?loadButtons():loadContent();say("Nouvel ordre enregistré.")}catch(error){say(error.message,true)}}
async function move(root,item,direction,buttons=false){const siblings=[...root.querySelectorAll(`.list-item${buttons?"":'[data-group="'+item.dataset.group+'"]'}`)],index=siblings.indexOf(item),other=siblings[index+direction];if(!other)return;item.parentNode.insertBefore(direction<0?item:other,direction<0?other:item);await saveOrder(root,buttons)}

const blockDialog=$("block-dialog"),blockForm=$("block-form");
function localDate(value){return LinksDates.local(value,adminTimezone)}
function openBlock(item={}){blockForm.reset();$("block-feedback").hidden=true;$("block-advanced").open=false;const clean={id:"",type:"classic",internal_name:"",title:"",description:"",url:"",icon:"website",image:"",badge:"",cta:"",promo_code:"",priority:"normal",start_at:"",end_at:""};for(const [key,value] of Object.entries(clean))blockForm.elements[key].value=value;$("block-image-file").value="";blockForm.elements.active.checked=true;blockForm.elements.draft.checked=false;if(item.id){for(const key of ["id","type","internal_name","title","description","url","icon","image","badge","cta","promo_code","priority"])blockForm.elements[key].value=item[key]??clean[key];$("block-advanced").open=!!(item.badge||item.cta||item.internal_name!==item.title||(item.type==="classic"&&(item.start_at||item.end_at)));blockForm.elements.active.checked=item.active!==false;blockForm.elements.draft.checked=!!item.draft;blockForm.elements.start_at.value=localDate(item.start_at);blockForm.elements.end_at.value=localDate(item.end_at)}$("promo-availability").hidden=true;$("block-title").textContent=item.id?"Modifier le bloc":"Nouveau bloc";preview();blockDialog.showModal();checkPromotion()}
function updatePromoEditor(){const promo=["promo","featured"].includes(blockForm.elements.type.value);blockForm.querySelectorAll("[data-promo-editorial]").forEach(label=>label.hidden=promo);blockForm.elements.title.required=!promo;const schedule=blockForm.querySelector("[data-campaign-schedule]");const target=promo?blockForm.querySelector(".editor-essential"):$("classic-schedule-slot");if(schedule.parentNode!==target)target.append(schedule);$("block-type-help").textContent=promo?"Offre illustrée dans le carrousel, avec dates et code promo facultatifs.":"Lien permanent avec titre, description et icône ou image.";blockForm.querySelector("[data-promo-code]").hidden=!promo;}
function formBlock(){const data=Object.fromEntries(new FormData(blockForm));data.active=blockForm.elements.active.checked;data.draft=blockForm.elements.draft.checked;if(!data.internal_name.trim())data.internal_name=data.title.trim();if(["promo","featured"].includes(data.type)&&!data.title.trim())data.title=data.internal_name;for(const key of ["start_at","end_at"])data[key]=data[key]?LinksDates.instant(data[key],adminTimezone):null;return data}
let promotionTimer,pendingConflict,lastPromotionCheck;
const periodText=value=>value?new Intl.DateTimeFormat("fr-FR",{dateStyle:"medium",timeStyle:"short",timeZone:adminTimezone}).format(new Date(value)):"sans limite";
async function checkPromotion(){
 clearTimeout(promotionTimer);promotionTimer=setTimeout(async()=>{const node=$("promo-availability"),data=formBlock();if(!["promo","featured"].includes(data.type)||!data.active||data.draft){node.hidden=true;lastPromotionCheck={allowed:true};return}try{const payload={...data,internal_name:data.internal_name||"Nouvelle promotion",title:data.title||"Promotion",url:data.url||"https://example.invalid"};lastPromotionCheck=await api("/api/promotions/check",{method:"POST",body:JSON.stringify(payload)});node.hidden=false;node.className="wide availability "+(lastPromotionCheck.allowed?(lastPromotionCheck.maximum===3?"warning":"success"):"error");node.innerHTML=lastPromotionCheck.allowed?(lastPromotionCheck.maximum===3?`⚠️ Période chargée — ${lastPromotionCheck.maximum}/3 promotions`:`✅ Période disponible — ${lastPromotionCheck.maximum}/3 promotions`):`❌ Limite dépassée — ${lastPromotionCheck.maximum} promotions seraient actives simultanément`;if(lastPromotionCheck.overlaps.length){const first=lastPromotionCheck.overlaps[0];node.innerHTML+=`<small>Une promotion est déjà prévue : ${esc(first.internal_name)}, de ${esc(periodText(first.start_at))} à ${esc(periodText(first.end_at))}.</small>`}}catch(error){node.hidden=false;node.className="wide availability error";node.textContent=error.message;lastPromotionCheck={allowed:false}}},180)
}
async function saveBlock(data){const id=data.id;delete data.id;await api(id?"/api/content/"+id:"/api/content",{method:id?"PUT":"POST",body:JSON.stringify(data)});blockDialog.close();await loadContent();say("Bloc enregistré.")}
function showConflict(data,check){pendingConflict={data,check};const segment=check.segments[0];$("conflict-period").textContent=segment?`Du ${periodText(segment.start_at)} au ${periodText(segment.end_at)}, ${segment.count} promotions seraient actives simultanément.`:"La période contient un chevauchement.";const items=check.overlaps;$("conflict-items").innerHTML=items.map(item=>`<article><strong>${esc(item.internal_name)}</strong><small>${esc(item.status)} · ${esc(periodText(item.start_at))} → ${esc(periodText(item.end_at))}${item.active_days!==null?` · active depuis ${item.active_days} jour(s)`:""}</small></article>`).join("");$("replacement-promo").replaceChildren(...items.map(item=>new Option(item.internal_name+(item.active_days!==null?` — ${item.active_days} j`:""),item.id)));$("conflict-dialog").showModal()}

function preview(){
 updatePromoEditor();const data=formBlock();publicTimezone=adminTimezone;
 const promo=["promo","featured"].includes(data.type);data.title=data.title||data.internal_name||"Titre du lien";
 const card=promo?renderOffer(data):renderBlock(data);card.querySelectorAll("a,button").forEach(node=>{node.removeAttribute("href");node.setAttribute("disabled","");node.tabIndex=-1});if(card.tagName==="A")card.removeAttribute("href");
 let frame=$("block-preview").querySelector("iframe");
 if(!frame){frame=document.createElement("iframe");frame.className="promo-preview-frame";frame.title="Aperçu public du contenu";frame.setAttribute("sandbox","allow-same-origin");$("block-preview").replaceChildren(frame);frame.addEventListener("load",()=>{try{const resize=()=>{frame.style.height=frame.contentDocument.documentElement.scrollHeight+"px"};resize();frame.contentDocument.querySelectorAll("img").forEach(img=>img.addEventListener("load",resize))}catch{}})}
 frame.srcdoc=`<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/preview/style.css"><link rel="stylesheet" href="/preview/icons.css"><link rel="stylesheet" href="/preview/preview.css"></head><body><div class="${promo?"carousel":"links"}"><div class="${promo?"carousel-slide":"preview-link"}">${card.outerHTML}</div></div></body></html>`;
 $("clear-block-image").disabled=!data.image;
}
$("clear-block-image").addEventListener("click",()=>{blockForm.elements.image.value="";$("block-image-file").value="";preview()});
blockForm.addEventListener("input",()=>{preview();checkPromotion()});blockForm.addEventListener("submit",async event=>{event.preventDefault();if(event.submitter?.value==="cancel"){blockDialog.close();return}try{const data=formBlock();if(["promo","featured"].includes(data.type)&&data.active&&!data.draft){const payload={...data};lastPromotionCheck=await api("/api/promotions/check",{method:"POST",body:JSON.stringify(payload)});if(!lastPromotionCheck.allowed){showConflict(data,lastPromotionCheck);return}}await saveBlock(data)}catch(error){say(error.message,true)}});
$("block-image-file").addEventListener("change",async event=>{const file=event.target.files[0];if(!file)return;if(file.size>4*1024*1024){say("L’image dépasse 4 Mo.",true);return}try{const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file)}),result=await api("/api/upload",{method:"POST",body:JSON.stringify({type:file.type,data})});blockForm.elements.image.value=result.url;preview();say("Image importée.")}catch(error){say(error.message,true)}});
document.querySelectorAll("[data-preview]").forEach(button=>button.addEventListener("click",()=>{document.querySelectorAll("[data-preview]").forEach(x=>x.classList.toggle("active",x===button));$("block-preview").classList.toggle("mobile",button.dataset.preview==="mobile")}));

const buttonDialog=$("button-dialog"),buttonForm=$("button-form");
function openButton(item={}){buttonForm.querySelector("[data-dialog-feedback]")?.remove();buttonForm.reset();buttonForm.elements.id.value=item.id||"";for(const key of ["icon","label","url"])if(item[key]!==undefined)buttonForm.elements[key].value=item[key];buttonForm.elements.active.checked=item.active!==false;$("button-title").textContent=item.id?"Modifier le bouton":"Nouveau bouton";buttonDialog.showModal()}
buttonForm.addEventListener("submit",async event=>{event.preventDefault();if(event.submitter?.value==="cancel"){buttonDialog.close();return}try{const data=Object.fromEntries(new FormData(buttonForm)),id=data.id;delete data.id;data.active=buttonForm.elements.active.checked;await api(id?"/api/buttons/"+id:"/api/buttons",{method:id?"PUT":"POST",body:JSON.stringify(data)});buttonDialog.close();await loadButtons();say("Bouton enregistré.")}catch(error){say(error.message,true)}});

document.addEventListener("click",async event=>{const action=event.target.closest("[data-action]");if(!action)return;const item=action.closest(".list-item"),id=item?.dataset.id;try{switch(action.dataset.action){case"copy-story":return copyStory(action,id);case"new-block":return openBlock();case"new-button":return openButton();case"edit":return openBlock(state.content.find(x=>x.id===id));case"edit-button":return openButton(state.buttons.find(x=>x.id===id));case"duplicate":await api(`/api/content/${id}/duplicate`,{method:"POST",body:"{}"});await loadContent();return say("Bloc dupliqué en brouillon.");case"archive":await api(`/api/content/${id}/archive`,{method:"POST",body:"{}"});await loadContent();return say("Bloc archivé.");case"restore":await api(`/api/content/${id}/restore`,{method:"POST",body:"{}"});await loadArchives();return say("Bloc restauré.");case"delete":if(confirm("Supprimer définitivement ce bloc et ses statistiques de page ? L’historique Story sera conservé. Cette action est irréversible.")){const fromArchives=!!item.closest("#archive-list");await api("/api/content/"+id,{method:"DELETE"});fromArchives?await loadArchives():await loadContent();say("Bloc supprimé. Historique Story conservé.")}return;case"delete-button":if(confirm("Supprimer ce bouton et ses statistiques ?")){await api("/api/buttons/"+id,{method:"DELETE"});await loadButtons()}return;case"up":return move(item.parentNode,item,-1,item.parentNode.id==="button-list");case"down":return move(item.parentNode,item,1,item.parentNode.id==="button-list")}}catch(error){say(error.message,true)}});
const editable=item=>Object.fromEntries(["type","internal_name","title","description","url","icon","image","badge","cta","promo_code","priority","active","draft","start_at","end_at"].map(key=>[key,item[key]]));
$("conflict-dialog").addEventListener("click",async event=>{const action=event.target.closest("[data-conflict]")?.dataset.conflict;if(!action||!pendingConflict)return;try{if(action==="dates"){$("conflict-dialog").close();return}if(action==="next"){const next=pendingConflict.check.next_start;if(!next){say("Aucun créneau automatique trouvé : modifie les dates.",true);$("conflict-dialog").close();return}const oldStart=pendingConflict.data.start_at?new Date(pendingConflict.data.start_at):new Date(),oldEnd=pendingConflict.data.end_at?new Date(pendingConflict.data.end_at):null,newStart=new Date(next);blockForm.elements.start_at.value=localDate(next);if(oldEnd)blockForm.elements.end_at.value=localDate(new Date(newStart.getTime()+Math.max(60000,oldEnd-oldStart)).toISOString());$("conflict-dialog").close();preview();checkPromotion();say("Premier créneau disponible proposé. La date reste modifiable.");return}if(action==="replace"){const id=$("replacement-promo").value,target=state.content.find(item=>item.id===id);if(!target||!confirm(`Désactiver « ${target.internal_name} » et enregistrer cette promotion ?`))return;await api("/api/promotions/replace",{method:"POST",body:JSON.stringify({replace_id:id,content:pendingConflict.data})});$("conflict-dialog").close();blockDialog.close();await loadContent();say("Promotion remplacée et désactivée.")}}catch(error){say(error.message,true)}});

async function loadSettings(){try{
 state.settings=await api("/api/settings");adminTimezone=state.settings.timezone||"UTC";publicSiteUrl=state.settings.site_url||"";
 $("version-form").elements.app_version.value=state.settings.app_version||"";
 for(const key of ["name","tagline","description","logo","avatar","footer_owner","site_url","timezone","video_channel_id"])$("settings-form").elements[key].value=state.settings[key]||"";
 for(const key of ["analytics_enabled","video_enabled"])$("settings-form").elements[key].checked=!!state.settings[key];
 $("settings-form").elements.source_rules.value=JSON.stringify(state.settings.source_rules||[],null,2);
 $("admin-name").textContent=state.settings.name||"Links";$("admin-owner").textContent=(state.settings.name||"Links")+" · Administration";
 $("admin-logo").hidden=!state.settings.logo;if(state.settings.logo)$("admin-logo").src=state.settings.logo;
 document.querySelectorAll(".public-link").forEach(a=>{a.hidden=!publicSiteUrl;a.href=publicSiteUrl||"#"});$("admin-timezone").textContent=adminTimezone;
 for(const r of state.settings.source_rules||[])names[r.key]=r.label;
 const select=$("share-source");select.querySelectorAll("[data-instance-source]").forEach(x=>x.remove());for(const r of state.settings.source_rules||[]){const o=new Option(r.label,r.aliases[0]||r.key);o.dataset.instanceSource="1";select.append(o)}shareUrl();
 $("access-form").elements.mode.value=state.settings.auth_mode;accessFields();$("logout").hidden=state.settings.auth_mode!=="local";
}catch(error){say(error.message,true)}}
$("settings-form").addEventListener("submit",async event=>{event.preventDefault();try{
 const data=Object.fromEntries(new FormData(event.target));data.analytics_enabled=event.target.elements.analytics_enabled.checked;data.video_enabled=event.target.elements.video_enabled.checked;data.source_rules=JSON.parse(data.source_rules||"[]");
 await api("/api/settings",{method:"POST",body:JSON.stringify(data)});await loadSettings();say("Réglages enregistrés.")
}catch(error){say(error.message,true)}});
async function initializeAdmin(){try{const auth=await api("/api/auth/status");csrf=auth.csrf||"";await loadSettings();await loadStats()}catch(error){say(error.message,true)}}

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
 const items=(await api("/api/content")).items.filter(item=>item.type!=="classic"&&item.status==="Actif").map(item=>{const value=metrics.get(item.id)||{clicks:0,impressions:0,copies:0};return {...item,...value,ctr:value.impressions?Math.round(value.clicks*1000/value.impressions)/10:null}});
 $("active-campaigns").innerHTML=items.length?items.map(item=>`<article class="campaign-card">${item.image?`<img src="${esc(item.image)}" alt="" loading="lazy">`:'<span class="type-mark" aria-hidden="true">↗</span>'}<div><strong>${esc(item.internal_name)}</strong><small>${esc(periodText(item.start_at||item.created_at))} → ${esc(periodText(item.end_at))}</small><span class="status active">Actif</span><p>${fmt.format(item.impressions||0)} impressions · ${fmt.format(item.clicks||0)} clics${item.promo_code||item.copies?` · ${fmt.format(item.copies||0)} copies`:""} · CTR ${item.ctr==null?"—":esc(item.ctr)+" %"}</p></div><button type="button" data-open-content aria-label="Gérer ${esc(item.internal_name)}">→</button></article>`).join(""):'<p class="empty">Aucune campagne en cours.</p>';
 }catch(error){$("active-campaigns").textContent=error.message}}
document.addEventListener("click",event=>{
 if(event.target.closest("[data-open-content]")){activate("content");document.querySelector("#content h2").setAttribute("tabindex","-1");document.querySelector("#content h2").focus()}
 document.querySelectorAll(".row-menu[open]").forEach(menu=>{if(!menu.contains(event.target)||event.target.closest("[data-action]"))menu.open=false});
});
document.addEventListener("keydown",event=>{if(event.key==="Escape")document.querySelectorAll(".row-menu[open]").forEach(menu=>{menu.open=false;menu.querySelector("summary").focus()})});

/* Footer quotations: local controls in Settings. */
let quotes=[],quotesPending=null,quotesAnalysisId=0;
function quoteText(value){const match=value.match(/^(.*?)(\s*\([^()]+\))$/s);return match?esc(match[1])+`<span class="quote-source">${esc(match[2])}</span>`:esc(value)}
function drawQuotes(){
 $("quotes-summary").textContent=quotes.length+" / 300 citations · "+quotes.filter(q=>q.active).length+" actives";
 $("quotes-clear").hidden=!quotes.length;
 $("quotes-limit").hidden=quotes.length<300;
 $("quote-form").querySelector("button").disabled=quotes.length>=300;
 $("quotes-list").innerHTML=quotes.length?quotes.map(q=>`<article class="quote-row" data-quote-id="${esc(q.id)}"><p>${quoteText(q.text)}</p><div class="actions"><button type="button" class="quote-toggle" role="switch" aria-checked="${q.active}" ${q.pending?"disabled":""} aria-label="Activer ou désactiver la citation" data-quote-toggle>${q.active?"● Activé":"○ Désactivé"}</button><button type="button" data-quote-delete ${q.pending?"disabled":""}>Supprimer</button></div></article>`).join(""):"<p>Aucune citation pour le moment.</p>";
}
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

$("version-form").addEventListener("submit",async event=>{event.preventDefault();const button=event.target.querySelector("button");button.disabled=true;try{const data=await api("/api/app-version",{method:"POST",body:JSON.stringify({app_version:event.target.elements.app_version.value})});event.target.elements.app_version.value=data.app_version;say("Version enregistrée.")}catch(error){say(error.message,true)}finally{button.disabled=false}});

$("quotes-clear").addEventListener("click",async event=>{
 if(!quotes.length||!confirm("Supprimer définitivement les "+quotes.length+" citations ? Cette action est irréversible."))return;
 const button=event.target;button.disabled=true;
 try{await api("/api/quotes",{method:"DELETE"});quotes=[];clearQuoteAnalysis();drawQuotes();$("quotes-feedback").textContent="Toutes les citations ont été supprimées."}catch(error){$("quotes-feedback").textContent=error.message}finally{button.disabled=false}
});

function accessFields(){const form=$("access-form"),local=form.elements.mode.value==="local";$("local-account-fields").hidden=!local;$("external-confirm-label").hidden=local;$("current-password-label").hidden=state.settings.auth_mode!=="local";}
$("access-form").elements.mode.addEventListener("change",accessFields);
$("access-form").addEventListener("submit",async event=>{event.preventDefault();try{const data=Object.fromEntries(new FormData(event.target));data.confirm_external=event.target.elements.confirm_external.checked;data.csrf=csrf;await api("/api/auth/access",{method:"POST",body:JSON.stringify(data)});location.reload()}catch(error){say(error.message,true)}});
$("logout").addEventListener("click",async()=>{await api("/api/auth/logout",{method:"POST",body:JSON.stringify({csrf})});location.href="/login"});
for(const input of document.querySelectorAll("[data-profile-upload]"))input.addEventListener("change",async()=>{const file=input.files[0];if(!file)return;try{if(file.size>4*1024*1024)throw Error("Image supérieure à 4 Mo.");const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file)});const result=await api("/api/upload",{method:"POST",body:JSON.stringify({type:file.type,data})});$("settings-form").elements[input.dataset.profileUpload].value=result.url}catch(error){say(error.message,true)}finally{input.value=""}});
for(const button of document.querySelectorAll("[data-clear-profile]"))button.addEventListener("click",()=>$("settings-form").elements[button.dataset.clearProfile].value="");
if(Intl.supportedValuesOf)$("timezones").replaceChildren(...Intl.supportedValuesOf("timeZone").map(x=>new Option(x,x)));
initializeAdmin();
