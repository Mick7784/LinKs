"use strict";
const $=id=>document.getElementById(id),fmt=new Intl.NumberFormat("fr-FR");
const names={"direct-inconnu":"Direct / inconnu","autre-site":"Autre site","autre-campagne":"Autre campagne",youtube:"YouTube",instagram:"Instagram","instagram-story":"Ancien lien partagé (source incertaine)","shared-unknown":"Lien partagé (source inconnue)",facebook:"Facebook",google:"Google",discord:"Discord",newsletter:"Newsletter",tiktok:"TikTok",site:"Site",mail:"E-mail",qr:"QR"};
let csrf="",adminTimezone="UTC";
const state={content:[],buttons:[],archives:[],settings:{},chart:[]};
const reportCache=new Map();
async function reportApi(path){const entry=reportCache.get(path);if(entry&&Date.now()-entry.at<15000)return entry.promise;const value={at:Date.now(),promise:api(path)};if(!reportCache.has(path)&&reportCache.size>=6)reportCache.delete(reportCache.keys().next().value);reportCache.set(path,value);try{return await value.promise}catch(error){if(reportCache.get(path)===value)reportCache.delete(path);throw error}}
const api=async(path,options={})=>{const response=await fetch(path,{cache:"no-store",...options,headers:{"Content-Type":"application/json","X-Links-Request":"1","X-Links-CSRF":csrf,...(options.headers||{})}});if(response.status===401){location.href="/login";throw new Error("Connexion requise.")}if(!response.ok){let message="Une erreur est survenue.";try{message=(await response.json()).error||message}catch{}throw new Error(message)}if(options.method&&options.method!=="GET")reportCache.clear();return response.status===204?null:response.json()};
const say=(message,error=false)=>{const dialog=[...document.querySelectorAll("dialog[open]")].at(-1);if(dialog){let feedback=dialog.querySelector("[data-dialog-feedback]");if(!feedback){feedback=document.createElement("p");feedback.dataset.dialogFeedback="";feedback.className="editor-feedback";feedback.setAttribute("role","alert");(dialog.querySelector("form")||dialog).prepend(feedback)}feedback.hidden=false;feedback.textContent=message;feedback.classList.toggle("notice-error",error)}const node=$("notice");node.textContent=message;node.classList.toggle("notice-error",error);clearTimeout(say.timer);say.timer=setTimeout(()=>node.textContent="",4000)};
const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const typeName={classic:"Lien",featured:"Mise en avant",promo:"Campagne"};
const statusClass=value=>({Actif:"active",Programmé:"scheduled",Expiré:"expired",Brouillon:"draft"}[value]||"");
function activate(id){StudioNavigation.activate(id,document.querySelectorAll(".view"),document.querySelectorAll(".tabs button"));syncNavigation();$("topbar-current").textContent=document.querySelector(".tabs button.active")?.textContent.trim()||"Links";if(id==="dashboard"||id==="statistics"){$(id+"-filters").append($("analytics-filters"));filterAnalysis();loadStats()}if(id==="content"){loadContent();window.LinksTracking?.load().then(()=>{if(state.content.length)renderContent()})}if(id==="tracked-links"){window.LinksTracking?.load();window.LinksTracking?.loadPartners()}if(id==="buttons")loadButtons();if(id==="archives")loadArchives();if(id==="appearance")window.LinksAppearance?.load();else window.LinksAppearance?.cancelUploads();if(id!=="settings")profileUploads.forEach(g=>g.invalidate());if(id==="settings"){loadSettings().then(()=>window.LinksSettings?.open())}}
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

function dates(){
 if($("period").value==="custom"){
  const start=$("stats-start").value,end=$("stats-end").value;
  if(!start||!end||start>end||(Date.parse(end)-Date.parse(start))/86400000>399)throw Error("Choisir une période valide de 400 jours maximum.");
  return {start,end};
 }
 const days=Number($("period").value),end=new Intl.DateTimeFormat("en-CA",{timeZone:adminTimezone,year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date()),start=new Date(end+"T12:00:00Z");start.setUTCDate(start.getUTCDate()-days+1);return {start:start.toISOString().slice(0,10),end}}

const analyticCollections=new Map(),analyticRows=new Map();
let latestTrackedRows=[],partnerReportRows=null,partnerPending=false,partnerUnavailable=false;
let dailyReportData=null,dailyIndex=new Map(),dailySourceName=()=>"Source inconnue",dailyDay="",dailyRange=null;
let statisticsEntities=new Map();
let sourceMetadata=null;
let campaignRows=[],sourceRows=[],analysisDays={},renderedData=null,renderedSource="";
const analysisScope=()=>$("analysis-scope").value;
function readableSourceName({key,label}){
 if(key==="instagram-story"||label==="Ancien lien partagé (source incertaine)")return "Ancien lien partagé";
 if(key==="shared-unknown"||label==="Lien partagé (source inconnue)")return "Source inconnue";
 return label;
}
function renderRawSourceBreakdown(sources,total,{filterable=false}={}){
 if(sources.length>20){const host=document.createElement("div");host.className="platform-member-list";host.setAttribute("aria-label","Sources de publication");StudioCollection.create(host,{pageSize:20,renderRow:source=>{const item=renderRawSourceBreakdown([source],total,{filterable}).firstElementChild;item.removeAttribute("role");return item}}).setRows(sources.map(source=>({...source,name:source.label})),{sort:"input"});return host}
 const list=document.createElement("div");list.className="engagement-source-list";list.setAttribute("role","list");
 for(const source of sources){
  const item=document.createElement("div");item.className="engagement-source-item";item.setAttribute("role","listitem");
  if(source.key==="instagram-story")item.classList.add("is-uncertain");
  if(source.key==="shared-unknown")item.classList.add("is-unknown");
  const label=document.createElement("span");label.className="engagement-source-name";label.textContent=readableSourceName(source);
  const numbers=document.createElement("span");numbers.className="engagement-source-figures";
  const count=document.createElement("strong");count.textContent=fmt.format(source.total);
  const percent=document.createElement("small");percent.textContent=(total>0?source.total/total*100:0).toLocaleString("fr-FR",{maximumFractionDigits:1})+" %";
  numbers.append(count,percent);item.append(label,numbers);if(filterable){if(!["instagram-story","shared-unknown"].includes(source.key)){const origin=document.createElement("small");origin.className="source-origin-note";origin.textContent=source.key.startsWith("tracked:")?"Source de publication":"Source générale";item.append(origin)}const button=document.createElement("button");button.type="button";button.className="source-filter-shortcut";button.dataset.filterSource=source.key;button.textContent="Filtrer cette source";button.setAttribute("aria-label","Filtrer cette source · "+readableSourceName(source));button.onclick=()=>{if(![...$("source").options].some(option=>option.value===source.key))return;$("source").value=source.key;loadStats()};item.append(button)}if(source.key==="instagram-story"){const note=document.createElement("small");note.className="source-provenance-note";note.textContent="Provenance historique incertaine";item.append(note)}list.append(item);
 }
 return list;
}
function platformBreakdownRow(group,total,{filterable=false,open=false}={}){
 const details=document.createElement("details");details.className="platform-source-group";details.dataset.platformKey=group.key;details.open=open;
 const summary=document.createElement("summary"),label=document.createElement("strong"),figures=document.createElement("span");label.className="platform-breakdown-name";label.textContent=group.label;figures.className="engagement-source-figures";
 const count=document.createElement("strong"),share=document.createElement("small");count.textContent=fmt.format(group.total);share.textContent=(total>0?group.total/total*100:0).toLocaleString("fr-FR",{maximumFractionDigits:1})+" %";figures.append(count,share);summary.append(label,figures);details.append(summary);
 details.addEventListener("toggle",()=>{if(!details.open||details.dataset.loaded)return;details.dataset.loaded="true";const note=document.createElement("p");note.className="panel-helper";note.textContent="Parts des sources au sein de cette plateforme.";details.append(note);if(!filterable){details.append(renderRawSourceBreakdown(group.sources,group.total));return}const members=document.createElement("div");members.className="platform-member-list";members.setAttribute("aria-label","Sources de "+group.label);details.append(members);StudioCollection.create(members,{pageSize:20,renderRow:source=>{const item=renderRawSourceBreakdown([source],group.total,{filterable:true}).firstElementChild;item.removeAttribute("role");return item}}).setRows(group.sources.map(source=>({...source,name:source.label,details:[]})),{sort:"total"})});return details;
}
function renderSourceBreakdown(sources,total){
 if($("source-level").value==="sources")return renderRawSourceBreakdown(sources,total);
 const list=document.createElement("div");list.className="platform-source-breakdown";for(const group of StudioSourcePlatforms.group(sources,sourceMetadata||[]))list.append(platformBreakdownRow(group,total));return list;
}
function collectionOptions(){const preview=!$("statistics").classList.contains("active");return {preview,pageSize:preview?5:20,query:preview?"":$("analysis-search").value,sort:preview?"total":$("analysis-sort").value}}
function metricRows(id,items,empty){
 analyticRows.set(id,items);
 if(!analyticCollections.has(id)){
  const node=$(id);node.setAttribute("aria-label",node.closest("section").querySelector("h3,h4").textContent);
  analyticCollections.set(id,StudioCollection.create(node,{empty,renderRow:(item,context)=>{
   const row=document.createElement("div");row.className="engagement-row";
   row.innerHTML=`<div class="engagement-copy"><strong>${esc(item.name)}</strong></div><div class="engagement-value"><strong>${fmt.format(item.total)}</strong><small>${esc(item.unit)}</small></div>`;
   if(item.entity&&!context.preview){const button=document.createElement("button");button.type="button";button.className="statistics-entity-shortcut";button.dataset.statisticsEntity=item.entity.type;button.dataset.entityId=item.entity.id;const label=item.entity.type==="partner"?"Fiche partenaire":["tracked","button"].includes(item.entity.type)?"Fiche du lien":statisticsEntities.get(item.entity.id)?.type==="classic"?"Fiche du lien":"Fiche campagne";button.textContent="Fiche ↗";button.setAttribute("aria-label",label+" · "+item.name);button.title=label;row.append(button)}
   if(item.secondary){const extra=document.createElement("small");extra.className="engagement-secondary";extra.textContent=item.secondary;row.querySelector(".engagement-copy").append(extra)}
   const visual=item.series||([{label:item.unit,value:item.total,key:id==="top-links"?"public-clicks":undefined,tone:item.tone||(id==="top-links"||id==="daily-public-list"?"public":id==="tracked-stat-list"||id==="daily-tracked-list"||id.startsWith("partner-")?"tracked":"campaigns")}]);
   if(id!=="promo-copy-list")row.append(StudioCharts.ranking(visual,item.series?context.seriesMax:context.max,{comparison:Boolean(item.series)}));
   if(!context.preview&&item.details.length){
     const details=document.createElement("details"),summary=document.createElement("summary");summary.textContent=item.detailLabel||(item.sourceBreakdown?"Provenance":"Détails");details.append(summary);
     const renderDetails=()=>{
      if(!details.open||details.dataset.loaded)return;
      details.dataset.loaded="true";
      if(item.sourceBreakdown)details.append(renderSourceBreakdown(item.sourceBreakdown,item.total));
      else{const text=document.createElement("small");text.textContent=item.details.join(" · ");details.append(text)}
     };details.addEventListener("toggle",renderDetails);details.addEventListener("source-level-change",()=>{delete details.dataset.loaded;while(details.children.length>1)details.lastElementChild.remove();renderDetails()});
     details.className="engagement-details"+(item.sourceBreakdown?" engagement-source-details":"");row.append(details);
    }
   return row;
  }}));
 }
 const options=collectionOptions();if(id.startsWith("daily-"))options.pageSize=10;analyticCollections.get(id).setRows(options.preview?items.filter(item=>item.total>0||item.series?.some(entry=>entry.value>0)):items,options);
}
function drawCampaignRanking(){
 const metric=$("campaign-metric").value,units={clicks:"clics publics",shared:"ouvertures partagées",impressions:"impressions",copies:"copies de codes"};
 const rows=campaignRows.map(row=>({...row,total:row.metrics[metric]||0,unit:units[metric],tone:metric==="clicks"?"public":"campaigns",secondary:[metric!=="shared"?fmt.format(row.metrics.shared)+" ouvertures partagées":"",metric!=="clicks"?fmt.format(row.metrics.clicks)+" clics publics":""].filter(Boolean).join(" · ")}));
 const active=rows.filter(row=>Object.values(row.metrics).some(value=>value>0)),inactive=rows.filter(row=>!Object.values(row.metrics).some(value=>value>0));
 metricRows("campaign-details",active,"Aucune campagne avec activité pour cette période et cette source.");
 const details=$("campaign-inactive");details.hidden=!inactive.length;$("campaign-inactive-count").textContent=fmt.format(inactive.length);
 analyticRows.set("campaign-inactive-list",inactive);
 if(details.open)metricRows("campaign-inactive-list",inactive,"Aucune campagne sans activité.");
 else $("campaign-inactive-list").replaceChildren();
}
$("campaign-inactive").addEventListener("toggle",()=>{if($("campaign-inactive").open)drawCampaignRanking()});
function selectDailyDay(day){
 if(!dailyRange||!/^\d{4}-\d{2}-\d{2}$/.test(day))return;
 dailyDay=day<dailyRange.start?dailyRange.start:day>dailyRange.end?dailyRange.end:day;
 drawDailyDetail();StudioCharts.selectDay($("chart"),dailyDay);StudioCharts.selectDay($("public-daily-chart"),dailyDay);
}
function moveDailyDay(delta){const date=new Date(dailyDay+"T12:00:00Z");date.setUTCDate(date.getUTCDate()+delta);selectDailyDay(date.toISOString().slice(0,10))}
function dailyEntity(category,key){
 if(!key)return null;
 if(category==="tracked")return {type:"tracked",id:key};
 if(category==="public"&&key.startsWith("button:"))return {type:"button",id:key.slice(7)};
 const id=category==="public"&&key.startsWith("block:")?key.slice(6):category==="campaigns"?key:null;
 return statisticsEntities.has(id)?{type:"content",id}:null;
}
function dailyProvenance(sources){
 const labels=sources.slice(0,2).map(readableSourceName);
 if(sources.length>2)labels.push("+"+fmt.format(sources.length-2)+" autres sources");
 return labels.join(" · ");
}
function drawDailyDetail(){
 if(!dailyRange||!$("statistics").classList.contains("active"))return;
 const input=$("daily-date");input.min=dailyRange.start;input.max=dailyRange.end;input.value=dailyDay;
 $("daily-previous").disabled=dailyDay<=dailyRange.start;$("daily-next").disabled=dailyDay>=dailyRange.end;
 $("daily-filter-context").textContent=new Intl.DateTimeFormat("fr-FR",{dateStyle:"full",timeZone:"UTC"}).format(new Date(dailyDay+"T12:00:00Z"))+" · "+($("source").selectedOptions[0]?.textContent||"Toutes les sources");
 const result=StudioDailyReport.select(dailyIndex,dailyDay,$("source").value,dailySourceName);
 for(const category of ["public","tracked","campaigns"]){
  const data=result[category];$("daily-"+category+"-total").textContent=fmt.format(data.total);
  metricRows("daily-"+category+"-list",data.rows.map(row=>({name:row.name,total:row.total,unit:category==="public"?"clics publics":"ouvertures",tone:category==="public"?"public":category==="tracked"?"tracked":"campaigns",entity:dailyEntity(category,row.key),sourceBreakdown:row.sourceBreakdown,secondary:dailyProvenance(row.sourceBreakdown),details:row.sourceBreakdown.map(source=>source.label)})),category==="public"?"Aucun clic public enregistré ce jour pour cette source.":category==="tracked"?"Aucune ouverture de lien suivi enregistrée ce jour pour cette source.":"Aucune ouverture de campagne partagée enregistrée ce jour pour cette source.");
 }
}
$("daily-date").onchange=()=>{if($("daily-date").validity.valid&&$("daily-date").value)selectDailyDay($("daily-date").value)};
$("daily-previous").onclick=()=>moveDailyDay(-1);$("daily-next").onclick=()=>moveDailyDay(1);
function drawSources(){
 const options=collectionOptions(),raw=sourceRows.map(([label,total,key])=>({key,label,total})),total=raw.reduce((sum,source)=>sum+source.total,0),platforms=$("source-level").value==="platforms";
 if(options.preview){$("platform-source-details").hidden=true;StudioCharts.donut($("sources"),sourceRows,{preview:true});return}
 const groups=StudioSourcePlatforms.group(raw,sourceMetadata||[]),items=platforms?groups.map(group=>[group.label,group.total,group.key,group.sources.map(source=>source.label)]):sourceRows;
 const details=$("platform-source-details"),open=new Set([...details.querySelectorAll('.platform-source-group[open]')].map(node=>node.dataset.platformKey));details.hidden=!platforms||!groups.length;
 const matching=StudioCollection.select(groups.map(group=>({...group,name:group.label,details:group.sources.map(source=>source.label)})),{query:options.query,sort:options.sort,pageSize:Math.max(1,groups.length)}).rows;
 $("platform-source-list").replaceChildren(...matching.map(group=>platformBreakdownRow(group,total,{filterable:true,open:open.has(group.key)})));
 if(!matching.length){const empty=document.createElement("p");empty.className="empty";empty.textContent="Aucune plateforme ne correspond à cette recherche.";$("platform-source-list").append(empty)}
 $("platform-group-note").textContent=!platforms?"Sources individuelles : le filtre Source permet d’isoler leur activité.":sourceMetadata?"Regroupement de lecture : les sources et leurs filtres restent distincts.":"Métadonnées des plateformes indisponibles : seuls les libellés explicites et les clés connues sont regroupés.";
 StudioCharts.distribution($("sources"),items,{query:options.query,sort:options.sort,category:platforms?"plateforme":"source",onSelect:({key,activate})=>{if(!platforms||!activate)return;let target=[...details.querySelectorAll('.platform-source-group')].find(node=>node.dataset.platformKey===key);if(!target){const selected=groups.find(group=>group.key===key);if(selected){target=platformBreakdownRow(selected,total,{filterable:true});$("platform-source-list").querySelector(".empty")?.remove();$("platform-source-list").append(target)}}if(target){details.open=true;target.open=true}}});
}
$("source-level").onchange=()=>{drawSources();document.querySelectorAll("#statistics .engagement-source-details").forEach(node=>node.dispatchEvent(new Event("source-level-change")))};

function statisticsSeries(scope){
 if(scope==="tracked")return [{key:"tracked-openings",label:"Ouvertures de liens suivis",index:2,tone:"tracked"}];
 if(scope==="shared")return [{key:"tracked-openings",label:"Ouvertures de liens suivis",index:1,tone:"tracked"},{key:"campaign-openings",label:"Ouvertures de campagnes partagées",index:2,tone:"campaigns",dashed:true}];
 if(scope==="campaigns")return [{key:"campaign-clicks",label:"Clics publics des campagnes",index:1,tone:"public",dashed:true},{key:"campaign-openings",label:"Ouvertures de campagnes partagées",index:2,tone:"campaigns",dashed:true}];
 if(scope==="copies")return [{key:"copies",label:"Copies de codes promo",index:2,tone:"campaigns"}];
 return [{key:"visits",label:"Visites de la page",index:1,tone:"public"},{key:"public-clicks",label:"Clics publics",index:2,tone:"public",dashed:true}];
}
function renderPartnerReport(report){
 const note=$("partner-stat-note"),summary=$("partner-attribution-summary");
 note.textContent="Ouvertures de la période et de la source sélectionnées, selon les associations actuelles des liens. L’association au jour du clic n’est pas conservée dans les événements historiques.";
 summary.hidden=false;summary.querySelectorAll('[data-partner-count]').forEach(node=>node.textContent=fmt.format(report.totals[node.dataset.partnerCount]));
 metricRows("partner-stat-list",report.attributed.map(partner=>({name:partner.name,total:partner.total,unit:"ouvertures",entity:{type:"partner",id:partner.id},detailLabel:"Liens suivis concernés",details:partner.links.map(link=>link.name+" : "+fmt.format(link.total)+" ouverture(s)")})),"Aucune ouverture attribuée à un partenaire pour cette période et cette source.");
 const reasons={"missing-link":"Lien absent des métadonnées actuelles.","missing-association":"Information d’association indisponible.","missing-partner":"Partenaire référencé introuvable."};
 for(const [kind,id] of [["withoutPartner","without"],["unidentified","unidentified"]]){
  $("partner-"+id+"-section").hidden=!report[kind].length;
  metricRows("partner-"+id+"-list",report[kind].map(link=>({name:link.name,total:link.total,unit:"ouvertures",details:link.reason?[reasons[link.reason]]:[],entity:link.id?{type:"tracked",id:link.id}:null})),"Aucune ouverture dans cette catégorie.");
 }
 $("partner-unattributed").hidden=!(report.totals.withoutPartner||report.totals.unidentified);
}
async function loadPartnerRanking(){
 const rows=latestTrackedRows;if(partnerReportRows===rows)return;partnerReportRows=rows;partnerUnavailable=false;
 const note=$("partner-stat-note");
 $("partner-attribution-summary").hidden=true;$("partner-unattributed").hidden=true;
 if(!rows.length){partnerPending=false;renderPartnerReport(StudioPartnerReport.attribute([],[],[]));return}
 partnerPending=true;analyticRows.set("partner-stat-list",[]);const loading=document.createElement("p");loading.className="empty";loading.textContent="Chargement des associations partenaires…";$("partner-stat-list").replaceChildren(loading);note.textContent="Vérification des associations explicites des liens suivis…";
 try{
  const [links,partners]=await Promise.all([reportApi("/api/tracked-links"),reportApi("/api/affiliate-partners")]);
  if(rows!==latestTrackedRows)return;if(!$("statistics").classList.contains("active")){partnerReportRows=null;partnerPending=false;return}
  const report=StudioPartnerReport.attribute(rows,links.items,partners.items);
  partnerPending=false;renderPartnerReport(report);
 }catch{if(rows!==latestTrackedRows)return;partnerPending=false;partnerUnavailable=true;$("partner-attribution-summary").hidden=true;$("partner-unattributed").hidden=true;note.textContent="Associations partenaires indisponibles. Les ouvertures des liens restent visibles ci-dessus ; aucune attribution ne peut être vérifiée actuellement.";analyticRows.set("partner-stat-list",[]);const error=document.createElement("p");error.className="empty";error.textContent="Classement temporairement indisponible. Actualisez les statistiques pour réessayer.";$("partner-stat-list").replaceChildren(error)}
}

function syncAnalysis(){
 const statistics=$("statistics").classList.contains("active"),scope=analysisScope();if(statistics)queueStatisticsLocation();
 $("analysis-empty").hidden=sourceRows.some(row=>row[1]>0)||[...analyticRows].filter(([id])=>!id.startsWith("partner-")&&!id.startsWith("daily-")).some(([,rows])=>rows.some(row=>row.total>0||Object.values(row.metrics||{}).some(value=>value>0)));
 $("analysis-history").hidden=false;
 (statistics?$("statistics-chart"):$("dashboard-chart")).append($("traffic-chart"));
 if(!statistics)$("public-daily-chart").replaceChildren();
 if(analysisDays.public){
  const series=statisticsSeries(scope),days=scope==="shared"?analysisDays.sharedSplit:analysisDays[scope];
  chart(statistics?(days||analysisDays.public):analysisDays.public,statistics?series.map(row=>row.label):undefined);
  if(statistics){StudioCharts.timeSeries($("public-daily-chart"),null,analysisDays.public,statisticsSeries("public"),{mode:"bars",active:()=>$("statistics").classList.contains("active"),onSelectDay:selectDailyDay,selectedDay:dailyDay});drawDailyDetail();loadPartnerRanking()}
 }

}
function filterAnalysis(){
 for(const [id,collection] of analyticCollections){if(!["campaign-details","campaign-inactive-list"].includes(id)&&!(id.startsWith("partner-")&&(partnerPending||partnerUnavailable))){const options=collectionOptions(),rows=analyticRows.get(id)||[];if(id.startsWith("daily-"))options.pageSize=10;collection.setRows(options.preview?rows.filter(row=>row.total>0):rows,options)}}
 drawCampaignRanking();drawSources();syncAnalysis();
}
$("analysis-controls").onsubmit=event=>event.preventDefault();
$("analysis-search").oninput=filterAnalysis;$("analysis-sort").onchange=filterAnalysis;
$("analysis-scope").onchange=syncAnalysis;
$("campaign-metric").onchange=()=>{drawCampaignRanking();syncAnalysis()};
function statisticsNavigationHeight(){return getComputedStyle(document.querySelector('.statistics-navigation')).position==="sticky"?document.querySelector('.statistics-navigation').getBoundingClientRect().height:0}
function syncStatisticsLocation(){
 if(!$("statistics").classList.contains("active"))return;
 const height=statisticsNavigationHeight();$("statistics").style.setProperty("--statistics-navigation-height",height+"px");
 const sections=[...document.querySelectorAll('#statistics .statistics-section')],threshold=height+32;
 let current=sections[0];for(const section of sections)if(section.getBoundingClientRect().top<=threshold)current=section;
 if(scrollY+innerHeight>=document.documentElement.scrollHeight-4)current=sections.at(-1);
 document.querySelectorAll('.statistics-sections-nav a').forEach(link=>{if(link.hash==="#"+current.id)link.setAttribute("aria-current","location");else link.removeAttribute("aria-current")});
}
let statisticsScrollFrame=0;
function queueStatisticsLocation(){if(!statisticsScrollFrame)statisticsScrollFrame=requestAnimationFrame(()=>{statisticsScrollFrame=0;syncStatisticsLocation()})}
new ResizeObserver(queueStatisticsLocation).observe(document.querySelector('.statistics-navigation'));addEventListener("scroll",queueStatisticsLocation,{passive:true});
function focusStatisticsSection(id){$("statistics").style.setProperty("--statistics-navigation-height",statisticsNavigationHeight()+"px");const section=$(id);section.scrollIntoView({block:"start"});section.querySelector("h2").focus({preventScroll:true});syncStatisticsLocation()}
$("statistics").querySelectorAll('.statistics-sections-nav a').forEach(link=>link.addEventListener("click",event=>{event.preventDefault();focusStatisticsSection(link.hash.slice(1))}));
$("statistics").addEventListener("click",async event=>{
 const button=event.target.closest('[data-statistics-entity]');if(!button)return;
 const {statisticsEntity:type,entityId:id}=button.dataset,origin=button.closest("[id]")?.id;button.disabled=true;
 try{
  if(type==="tracked"||type==="partner")await window.LinksTracking.openEntity(type,id);
  else if(type==="button"){const lists=await Promise.all([api("/api/buttons"),api("/api/buttons?archived=1")]),item=lists.flatMap(list=>list.items).find(item=>item.id===id);if(!item)throw Error("Cette fiche historique n’est plus disponible.");openButton(item)}
  else{const item=statisticsEntities.get(id);if(!item)throw Error("Cette fiche historique n’est plus disponible.");openBlock(item)}
  const dialog=document.querySelector('dialog[open]');if(dialog)dialog.addEventListener("close",async()=>{await loadStats();const replacement=[...(document.getElementById(origin)||$("statistics")).querySelectorAll('[data-statistics-entity]')].find(node=>node.dataset.statisticsEntity===type&&node.dataset.entityId===id);(replacement||$("statistics-tracked-title")).focus({preventScroll:true})},{once:true});
 }catch(error){say(error.message,true)}finally{button.disabled=false}
});
document.addEventListener("click",event=>{const button=event.target.closest("[data-open-statistics]");if(button){
 const scope=button.dataset.openStatistics;$("analysis-scope").value=["public","shared","campaigns","copies"].includes(scope)?scope:"public";
 $("analysis-search").value=button.dataset.analysisQuery||"";activate("statistics");
 focusStatisticsSection(({shared:"statistics-tracked",public:"statistics-public",campaigns:"statistics-campaigns",copies:"statistics-campaigns"})[scope]||"statistics-overview");
}});
let chartRenderedWidth=0;
function chart(days,labels=["Visites","Clics publics"]){const statistics=$("statistics").classList.contains("active"),kind=statistics?"studio:"+analysisScope():"dashboard";$("chart-detail").hidden=statistics;if(state.chart===days&&state.chartKind===kind&&state.chartLabels?.join("|")===labels.join("|")&&chartRenderedWidth===$("chart").clientWidth&&$("chart").children.length)return;state.chart=days;state.chartKind=kind;state.chartLabels=labels;chartRenderedWidth=$("chart").clientWidth;if(statistics)StudioCharts.timeSeries($("chart"),$("chart-detail"),days,statisticsSeries(analysisScope()),{active:()=>$("statistics").classList.contains("active"),onSelectDay:selectDailyDay,selectedDay:dailyDay});else StudioCharts.timeline($("chart"),$("chart-detail"),days,labels)}

let statsRequest=0;
async function loadStats(force=false){if(force===true)reportCache.clear();const request=++statsRequest;let range;
 try{range=dates();$("stats-range-error").textContent=""}catch(error){$("stats-range-error").textContent=error.message;$("analysis-grid").setAttribute("aria-busy","false");return}
 try{
 $("analysis-grid").setAttribute("aria-busy","true");
 const [data,metadata]=await Promise.all([reportApi("/api/stats?"+new URLSearchParams(range)),reportApi("/api/tracking-sources").catch(()=>null)]),stories=data.stories||[],tracked=data.tracked||[],previous=$("source").value,previousLabel=$("source").selectedOptions[0]?.textContent;
 if(request!==statsRequest)return;
 const sameMetadata=sourceMetadata===(metadata?.items||null);sourceMetadata=metadata?.items||null;
 if(renderedData===data&&renderedSource===$("source").value&&sameMetadata){syncAnalysis();return}
 const trackedNames=new Map([...Object.entries(data.source_names||{}),...tracked.map(x=>[x.source,x.source_name])]);
 const sourceName=key=>trackedNames.get(key)||(Object.hasOwn(names,key)?names[key]:key===previous&&previousLabel?previousLabel:"Source inconnue");
 const sharedNames=new Map([...tracked,...stories].filter(x=>x.source_name).map(x=>[x.source,x.source_name]));
 const sources=[...new Set([...(previous?[previous]:[]),...data.rows.map(x=>x.source),...stories.map(x=>x.source),...tracked.map(x=>x.source),...(data.promo_code_copies||[]).map(x=>x.source),...(data.campaign_metrics||[]).map(x=>x.source)])].sort();
 $("source").replaceChildren(new Option("Toutes les sources",""),...sources.map(x=>new Option(sourceName(x),x)));if(sources.includes(previous))$("source").value=previous;
 const sourceLabel=$("source").selectedOptions[0]?.textContent||"Toutes les sources",periodLabel="du "+range.start.split("-").reverse().join("/")+" au "+range.end.split("-").reverse().join("/");
 $("source").title=sourceLabel;$("statistics-filter-context").textContent="Période "+periodLabel+" · "+sourceLabel;
 $("analysis-empty").textContent="Aucune activité mesurée "+periodLabel+(previous?" pour la source « "+sourceLabel+" »":"")+". Les sections restent accessibles ci-dessous.";

 const source=$("source").value,rows=data.rows.filter(x=>!source||x.source===source),storyRows=stories.filter(x=>!source||x.source===source),trackedRows=tracked.filter(x=>!source||x.source===source),days=new Map(),bySource=new Map(),byLink=new Map(),linkSources=new Map(),labels=new Map(),byStory=new Map();
 const sharedDays=new Map(),copyDays=new Map(),campaignDays=new Map(),trackedDays=new Map();
 const addDay=(map,day,total,index=1)=>{const pair=map.get(day)||[0,0];pair[index]+=total;map.set(day,pair)};
 for(let d=new Date(range.start+"T12:00Z");d<=new Date(range.end+"T12:00Z");d.setUTCDate(d.getUTCDate()+1))days.set(d.toISOString().slice(0,10),[0,0]);
 let views=0,clicks=0,storyClicks=0;
 for(const row of rows){labels.set(row.link,row.label||row.link);const pair=days.get(row.day);if(!pair)continue;if(row.kind==="view"){views+=row.total;pair[0]+=row.total;bySource.set(row.source,(bySource.get(row.source)||0)+row.total)}else if(row.kind==="click"){clicks+=row.total;pair[1]+=row.total;byLink.set(row.link,(byLink.get(row.link)||0)+row.total);const sources=linkSources.get(row.link)||new Map();sources.set(row.source,(sources.get(row.source)||0)+row.total);linkSources.set(row.link,sources)}}
 for(const row of trackedRows){addDay(trackedDays,row.day,row.total);addDay(sharedDays,row.day,row.total);storyClicks+=row.total;const key="tracked:"+row.link_id,item=byStory.get(key)||{label:row.label,total:0,sources:new Map()};item.total+=row.total;item.sources.set(row.source,(item.sources.get(row.source)||0)+row.total);byStory.set(key,item);bySource.set(row.source,(bySource.get(row.source)||0)+row.total)}
 for(const row of storyRows){addDay(sharedDays,row.day,row.total);addDay(campaignDays,row.day,row.total);storyClicks+=row.total;const item=byStory.get(row.promotion_id)||{label:row.label,total:0,sources:new Map()};item.total+=row.total;item.sources.set(row.source,(item.sources.get(row.source)||0)+row.total);byStory.set(row.promotion_id,item);bySource.set(row.source,(bySource.get(row.source)||0)+row.total)}
 $("views").textContent=fmt.format(views);$("clicks").textContent=fmt.format(clicks);$("ratio").textContent=views?(clicks*100/views).toLocaleString("fr-FR",{maximumFractionDigits:1})+" %":"—";
 $("story-clicks").textContent=fmt.format(storyClicks);$("story-promos").textContent=fmt.format(byStory.size);
 // Presentation of existing report series: the combined dashboard total stays unchanged.
 for(const [id,value] of [["statistics-views",$("views").textContent],["statistics-clicks",$("clicks").textContent],["statistics-ratio",$("ratio").textContent]])$(id).textContent=value;
 $("statistics-tracked-openings").textContent=fmt.format(trackedRows.reduce((total,row)=>total+row.total,0));
 $("statistics-campaign-openings").textContent=fmt.format(storyRows.reduce((total,row)=>total+row.total,0));
 $("story-total").textContent=$("statistics-campaign-openings").textContent;
 const sharedMetrics=entries=>entries.map(([key,item])=>{
   const sourceBreakdown=[...item.sources].sort((a,b)=>b[1]-a[1]).map(([key,total])=>({key,label:sharedNames.get(key)||sourceName(key),total}));
   return {name:item.label,total:item.total,unit:"ouvertures",entity:key.startsWith("tracked:")?{type:"tracked",id:key.slice(8)}:statisticsEntities.has(key)?{type:"content",id:key}:null,sourceBreakdown,details:sourceBreakdown.map(({label,total})=>label+" : "+fmt.format(total))};
 });
 metricRows("tracked-stat-list",sharedMetrics([...byStory].filter(([key])=>key.startsWith("tracked:"))),"Aucun lien suivi ouvert sur cette période.");
 metricRows("story-list",sharedMetrics([...byStory].filter(([key])=>!key.startsWith("tracked:"))),"Aucune campagne partagée ouverte sur cette période.");
 const campaignStats=new Map(),copyStats=new Map();
 const getCampaign=id=>campaignStats.get(id)||{clicks:0,impressions:0,shared:0,copies:0};
 for(const row of (data.campaign_metrics||[]).filter(x=>!source||x.source===source)){const value=getCampaign(row.id);value.name=row.name||value.name;value[row.kind==="click"?"clicks":"impressions"]+=row.total;campaignStats.set(row.id,value)}
 for(const row of storyRows){const value=getCampaign(row.promotion_id);value.name=row.label;value.shared+=row.total;campaignStats.set(row.promotion_id,value)}
 let copyTotal=0;
 for(const row of (data.promo_code_copies||[]).filter(x=>!source||x.source===source)){copyTotal+=row.total;addDay(copyDays,row.day,row.total);const metric=getCampaign(row.id);metric.name=row.name;metric.copies+=row.total;campaignStats.set(row.id,metric);const key=JSON.stringify([row.id,row.code]);const value=copyStats.get(key)||{id:row.id,name:row.name,code:row.code,total:0};value.total+=row.total;copyStats.set(key,value)}
 $("promo-copies").textContent=fmt.format(copyTotal);$("promo-copy-total").textContent=fmt.format(copyTotal);$("statistics-copies").textContent=$("promo-copies").textContent;
 metricRows("promo-copy-list",[...copyStats.values()].sort((a,b)=>b.total-a.total).map(value=>{const impressions=campaignStats.get(value.id)?.impressions||0;return {name:value.name+" · "+value.code,total:value.total,unit:"copies",details:[...(impressions?["Taux de copie : "+(value.total*100/impressions).toLocaleString("fr-FR",{maximumFractionDigits:1})+" %"]:[])]}}),"Aucun code copié sur cette période.");
 await loadCampaigns(campaignStats,request);if(request!==statsRequest)return;
 const campaignIds=new Set(campaignRows.map(row=>row.id));for(const row of data.campaign_metrics||[])if(row.kind==="click"&&campaignIds.has(row.id)&&(!source||row.source===source))addDay(campaignDays,row.day,row.total,0);
 analysisDays.public=[...days].map(([day,value])=>[day,...value]);for(const [scope,map] of [["shared",sharedDays],["copies",copyDays],["campaigns",campaignDays],["tracked",trackedDays]])analysisDays[scope]=[...days.keys()].map(day=>[day,...(map.get(day)||[0,0])]);analysisDays.sharedSplit=[...days.keys()].map(day=>[day,trackedDays.get(day)?.[1]||0,campaignDays.get(day)?.[1]||0]);const sorted=map=>[...map].sort((a,b)=>b[1]-a[1]);metricRows("top-links",sorted(byLink).map(([key,value])=>{
   const sourceBreakdown=[...linkSources.get(key)].sort((a,b)=>b[1]-a[1]).map(([source,total])=>({key:source,label:sourceName(source),total}));
   return {name:labels.get(key)||key,total:value,unit:"clics publics",entity:key.startsWith("block:")&&statisticsEntities.has(key.slice(6))?{type:"content",id:key.slice(6)}:null,sourceBreakdown,details:sourceBreakdown.map(({label,total})=>label+" : "+fmt.format(total))};
  }),"Aucun clic public sur cette période.");
 sourceRows=sorted(bySource).map(([key,value])=>[sourceName(key),value,key]);latestTrackedRows=trackedRows;
 if(dailyReportData!==data){dailyIndex=StudioDailyReport.index(data);dailyReportData=data}dailySourceName=sourceName;dailyRange=range;dailyDay=dailyDay>=range.start&&dailyDay<=range.end?dailyDay:range.end;
 document.querySelectorAll(".statistics-kpis strong").forEach(node=>node.classList.toggle("is-long-number",node.textContent.length>8));
 drawSources();syncAnalysis();renderedData=data;renderedSource=source;

 }catch(error){$("stats-range-error").textContent="Actualisation impossible. Les derniers résultats affichés correspondent au filtre précédent.";say(error.message,true)}finally{if(request===statsRequest)$("analysis-grid").setAttribute("aria-busy","false")}}
$("filters").onsubmit=event=>event.preventDefault();
$("period").addEventListener("change",()=>{const custom=$("period").value==="custom";document.querySelectorAll("[data-custom-period]").forEach(node=>node.hidden=!custom);if(custom&&!$("stats-start").value){$("period").value="14";const range=dates();$("stats-start").value=range.start;$("stats-end").value=range.end;$("period").value="custom"}loadStats()});
$("stats-start").onchange=loadStats;$("stats-end").onchange=loadStats;$("source").addEventListener("change",loadStats);new ResizeObserver(()=>{const width=$("chart").clientWidth;if(width>0&&width!==chartRenderedWidth&&state.chart.length)chart(state.chart,state.chartLabels)}).observe($("chart"));

function canStory(item){try{const url=new URL(item.url);return ["http:","https:"].includes(url.protocol)&&!url.username&&!url.password&&url.hostname!==new URL(publicSiteUrl||location.origin).hostname}catch{return false}}
function storyButton(item){if(item.type==="classic")return "";const disabled=!canStory(item),title=disabled?"URL requise":"Copier le lien tracké pour la plateforme choisie";return `<div class="share-picker"><select aria-label="Plateforme de partage pour ${esc(item.internal_name)}" ${disabled?"disabled":""}>${window.LinksTracking?.campaignOptions()||'<option value="instagram">Instagram Story</option><option value="youtube">YouTube Post</option><option value="facebook">Facebook</option><option value="tiktok">TikTok</option><option value="">Autre / sans source</option>'}</select><button data-action="copy-story" class="story-link-button" title="${title}" aria-label="${title}" ${disabled?"disabled":""}>🔗</button></div>`;}
async function copyStory(action,id){if(action.disabled)return;action.disabled=true;try{const platform=action.closest(".share-picker")?.querySelector("select")?.value||"";const {url:link}=await api(`/api/content/${id}/story-link`,{method:"POST",body:JSON.stringify({source:platform})});let copied=false;try{await navigator.clipboard.writeText(link);copied=true}catch{let input=action.parentNode.querySelector(".story-copy");if(!input){input=document.createElement("input");input.className="story-copy";input.readOnly=true;input.setAttribute("aria-label","Lien partagé tracké");action.parentNode.append(input)}input.value=link;input.focus();input.select();try{copied=document.execCommand("copy")}catch{}if(copied)input.remove()}say(copied?"Lien partagé copié"+(platform?" · "+(action.closest(".share-picker")?.querySelector("select")?.selectedOptions[0]?.textContent||platform):""):"Lien sélectionné : copie-le avec le menu de ton appareil.")}catch(error){say(error.message,true)}finally{action.disabled=false}}
function itemHtml(item,archived=false){const performance=item.type==="classic"?`${fmt.format(item.clicks||0)} clics`:`${fmt.format(item.impressions||0)} impressions · ${fmt.format(item.clicks||0)} clics · CTR ${item.ctr===null?"—":item.ctr+" %"}`;return`<article class="list-item" draggable="${!archived}" data-id="${esc(item.id)}" data-group="${item.type==="classic"?"classic":"highlight"}"><span class="drag-handle">${archived?"◦":"⋮⋮"}</span><span class="type-mark">${item.type==="promo"?"▣":item.type==="featured"?"★":"↗"}</span><div class="item-copy"><strong>${esc(item.internal_name)}</strong><small>${esc(item.title)} · ${typeName[item.type]||item.type} · ${performance}</small><span class="status ${statusClass(item.status)}">${esc(item.status)}</span></div><div class="item-actions">${storyButton(item)}${archived?`<button data-action="restore">Restaurer</button>`:`<span class="move"><button data-action="up" aria-label="Monter">↑</button><button data-action="down" aria-label="Descendre">↓</button></span><button data-action="edit">Modifier</button><details class="row-menu"><summary aria-label="Autres actions pour ${esc(item.internal_name)}" title="Autres actions">···</summary><div class="row-menu-content"><button data-action="duplicate">Dupliquer</button><button data-action="archive">Archiver</button>`}<button data-action="delete" class="trash" title="Retirer et conserver l’historique" aria-label="Retirer et conserver l’historique">Retirer</button>${archived?"":"</div></details>"}</div></article>`}
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
 try{const check=await api('/api/promotions/check',{method:'POST',body:JSON.stringify(data)});if(!check.allowed){openBlock({...item,start_at,end_at});showConflict(data,check);return}await api('/api/content/'+item.id,{method:'PUT',body:JSON.stringify(data)});await loadContent();say('Période enregistrée.')}catch(error){say(error.message,true);renderTimeline()}
}

async function loadContent(){try{state.content=(await api("/api/content")).items;renderContent();renderTimeline(state.content)}catch(error){say(error.message,true)}}
async function loadArchives(){try{const retired=(await api("/api/buttons?archived=1")).items;$("archive-buttons").innerHTML=retired.length?retired.map(item=>`<article class="list-item" data-id="${esc(item.id)}"><div class="item-copy"><strong>${esc(item.label)}</strong><small>${fmt.format(item.clicks||0)} clics historiques</small></div><button data-action="restore-button">Restaurer</button></article>`).join(""):"<p class=empty>Aucun raccourci retiré.</p>";state.archives=(await api("/api/content?archived=1")).items;$("archive-list").innerHTML=state.archives.length?state.archives.map(x=>itemHtml(x,true)).join(""):'<p class="empty">Aucune archive.</p>'}catch(error){say(error.message,true)}}
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

document.addEventListener("click",async event=>{const action=event.target.closest("[data-action]");if(!action)return;const item=action.closest(".list-item"),id=item?.dataset.id;try{switch(action.dataset.action){case"restore-button":await api(`/api/buttons/${id}/restore`,{method:"POST",body:"{}"});await loadArchives();return say("Raccourci restauré avec son historique.");case"copy-story":return copyStory(action,id);case"new-block":return openBlock();case"new-campaign":return openBlock({},"promo");case"new-button":return openButton();case"edit":return openBlock(state.content.find(x=>x.id===id));case"edit-button":return openButton(state.buttons.find(x=>x.id===id));case"duplicate":await api(`/api/content/${id}/duplicate`,{method:"POST",body:"{}"});await loadContent();return say("Bloc dupliqué en brouillon.");case"archive":await api(`/api/content/${id}/archive`,{method:"POST",body:"{}"});await loadContent();return say("Bloc archivé.");case"restore":await api(`/api/content/${id}/restore`,{method:"POST",body:"{}"});await loadArchives();return say("Bloc restauré.");case"delete":if(confirm("Retirer ce contenu de la page ? Son historique, ses images et tous les liens publiés seront conservés dans les archives.")){const fromArchives=!!item.closest("#archive-list");await api("/api/content/"+id,{method:"DELETE"});fromArchives?await loadArchives():await loadContent();say("Contenu retiré. Historique et redirections conservés.")}return;case"delete-button":if(confirm("Retirer ce raccourci ? Son identité, ses images et ses statistiques seront conservées dans les archives.")){await api("/api/buttons/"+id,{method:"DELETE"});await loadButtons()}return;case"up":return move(item.parentNode,item,-1,item.parentNode.id==="button-list");case"down":return move(item.parentNode,item,1,item.parentNode.id==="button-list")}}catch(error){say(error.message,true)}});
const editable=item=>Object.fromEntries(["type","internal_name","title","description","url","icon","image","badge","cta","promo_code","priority","active","draft","start_at","end_at","calendar_timed"].map(key=>[key,item[key]]));
$("conflict-dialog").addEventListener("click",async event=>{const action=event.target.closest("[data-conflict]")?.dataset.conflict;if(!action||!pendingConflict)return;try{if(action==="dates"){$("conflict-dialog").close();return}if(action==="next"){const next=pendingConflict.check.next_start;if(!next){say("Aucun créneau automatique trouvé : modifie les dates.",true);$("conflict-dialog").close();return}const oldStart=pendingConflict.data.start_at?new Date(pendingConflict.data.start_at):new Date(),oldEnd=pendingConflict.data.end_at?new Date(pendingConflict.data.end_at):null,newStart=new Date(next);const fields=LinksCalendar.inputFields({start_at:next,end_at:oldEnd?new Date(newStart.getTime()+Math.max(60000,oldEnd-oldStart)).toISOString():null},adminTimezone);for(const [key,value] of Object.entries(fields))blockForm.elements[key].value=value;$("conflict-dialog").close();preview();checkPromotion();say("Premier créneau disponible proposé. La date reste modifiable.");return}if(action==="replace"){const id=$("replacement-promo").value,target=state.content.find(item=>item.id===id);if(!target||!confirm(`Désactiver « ${target.internal_name} » et enregistrer cette promotion ?`))return;await api("/api/promotions/replace",{method:"POST",body:JSON.stringify({replace_id:id,content:pendingConflict.data})});$("conflict-dialog").close();blockDialog.close();await loadContent();say("Promotion remplacée et désactivée.")}}catch(error){say(error.message,true)}});

let settingsLoading=0;
async function loadSettings(){profileUploads.forEach(g=>g.invalidate());settingsLoading++;const fields=[...$("settings-form").querySelectorAll('[name],button[type="submit"],button.primary'),...document.querySelectorAll('button[form="settings-form"]')];fields.forEach(x=>x.disabled=true);try{
 state.settings=await api("/api/settings");adminTimezone=state.settings.timezone||"UTC";publicSiteUrl=state.settings.site_url||"";
 $("software-version").value=state.settings.app_version||"";
 const sidebarVersion=$("admin-version");sidebarVersion.textContent=state.settings.app_version?"LinKs · "+state.settings.app_version:"";sidebarVersion.hidden=!state.settings.app_version;
 for(const key of ["name","tagline","description","logo","avatar","footer_owner","site_url","timezone"])$("settings-form").elements[key].value=state.settings[key]||"";
 refreshProfileImages();
 for(const key of ["analytics_enabled"])$("settings-form").elements[key].checked=!!state.settings[key];
 $("settings-form").elements.source_rules.value=JSON.stringify(state.settings.source_rules||[],null,2);
 $("admin-owner").textContent=(state.settings.name||"Links")+" · Administration";

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
  const summary=await api("/api/restore/preview",{method:"POST",body:content});
  if(!confirm(`Restaurer ${parsed.tables.content_blocks.length} blocs et ${parsed.tables.top_buttons.length} boutons ? ${summary.retained_content} contenu(s) absent(s) du fichier conservé(s), ${summary.published_redirects} redirection(s) protégée(s), ${summary.counter_total} action(s) historiques après restauration. Les réglages et contenus sauvegardés seront restaurés. Les identifiants, historiques et destinations déjà publiées seront conservés, sans additionner les compteurs communs. Une copie de sécurité locale sera créée avant restauration.`))return;
  input.disabled=true;$('download-backup').disabled=true;$('backup-status').textContent='Vérification et restauration…';
  await api('/api/restore',{method:'POST',body:content});if(state.settings.auth_mode==='local'){location.href='/login';return}await loadSettings();await loadStats();state.content=[];state.buttons=[];state.archives=[];$('backup-status').textContent='Sauvegarde restaurée. Tes données sont disponibles.';
 }catch(error){$('backup-status').textContent='Restauration non effectuée : '+error.message;}finally{input.disabled=false;$('download-backup').disabled=false;input.value='';}
});


// Interface preferences belong exclusively to the admin origin and use a distinct key.
const themeKey="links-admin-theme",themeMedia=matchMedia("(prefers-color-scheme: dark)");
const themeIcons={light:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2"/></svg>',dark:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M20 15A8 8 0 0 1 9 4 8 8 0 1 0 20 15Z"/></svg>',system:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>'};
function applyAdminTheme(preference){
 const mode=["light","dark","system"].includes(preference)?preference:"system";
 $("theme-select").value=mode;
 document.documentElement.dataset.theme=mode==="system"?(themeMedia.matches?"dark":"light"):mode;
 document.querySelector("#theme-icon").innerHTML=themeIcons[mode];
 document.querySelector(".product-brand").src=document.documentElement.dataset.theme==="light"?"/brand-light.svg":"/brand.svg";
}
let themePreference="dark";try{themePreference=localStorage.getItem(themeKey)||"dark"}catch{}
applyAdminTheme(themePreference);
$("theme-select").addEventListener("change",event=>{applyAdminTheme(event.target.value);try{localStorage.setItem(themeKey,event.target.value)}catch{say("Thème appliqué. La mémorisation est indisponible dans ce navigateur.",true)}});
themeMedia.addEventListener("change",()=>{if($("theme-select").value==="system")applyAdminTheme("system")});

const iconPaths={
 globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a17 17 0 0 1 0 18 17 17 0 0 1 0-18Z"/>',
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
async function loadCampaigns(metrics=new Map(),request=0){try{
 const [current,archived]=await Promise.all([reportApi("/api/content"),reportApi("/api/content?archived=1")]);const campaigns=current.items;if(request&&request!==statsRequest)return;
 statisticsEntities=new Map([...campaigns,...archived.items].map(item=>[item.id,item]));
 const allCampaigns=new Map([...campaigns,...archived.items].filter(x=>x.type!=="classic").map(x=>[x.id,x]));
 const classicIds=new Set([...campaigns,...archived.items].filter(x=>x.type==="classic").map(x=>x.id));
 for(const [id,value] of metrics){if(!classicIds.has(id)&&!allCampaigns.has(id))allCampaigns.set(id,{id,internal_name:value.name||id,status:"Historique"})}
 campaignRows=[...allCampaigns.values()].map(item=>{const value=metrics.get(item.id)||{};return {id:item.id,name:item.internal_name,entity:statisticsEntities.has(item.id)?{type:"content",id:item.id}:null,metrics:{clicks:value.clicks||0,shared:value.shared||0,impressions:value.impressions||0,copies:value.copies||0},details:[item.status,"Impressions : "+fmt.format(value.impressions||0),"Clics publics : "+fmt.format(value.clicks||0),"Ouvertures partagées : "+fmt.format(value.shared||0),"Copies : "+fmt.format(value.copies||0),"CTR page : "+(value.impressions?(value.clicks*100/value.impressions).toLocaleString("fr-FR",{maximumFractionDigits:1})+" %":"—")]}});
 drawCampaignRanking();
 const items=campaigns.filter(item=>item.type!=="classic"&&item.status==="Actif").map(item=>{const value=metrics.get(item.id)||{clicks:0,shared:0,impressions:0,copies:0};return {...item,...value,pageClicks:value.clicks,sharedClicks:value.shared,totalClicks:value.clicks+value.shared,ctr:value.impressions?Math.round(value.clicks*1000/value.impressions)/10:null}});
 $("active-campaigns").innerHTML=items.length?items.map(item=>`<article class="campaign-card">${item.image?`<img src="${esc(LinksTheme.asset(item.image))}" alt="" loading="lazy">`:'<span class="type-mark" aria-hidden="true">↗</span>'}<div><strong>${esc(item.internal_name)}</strong><small>${esc(periodText(item.start_at||item.created_at))} → ${esc(periodText(item.end_at))}</small><span class="status active">Actif</span><div class="campaign-metrics"><span><small>Clics publics</small><b>${fmt.format(item.pageClicks||0)}</b></span><span><small>Ouvertures partagées</small><b>${fmt.format(item.sharedClicks||0)}</b></span></div><button type="button" data-open-statistics="campaigns">Statistiques</button></div><button type="button" data-open-content aria-label="Gérer ${esc(item.internal_name)}">→</button></article>`).join(""):'<p class="empty">Aucune campagne en cours.</p>';
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
