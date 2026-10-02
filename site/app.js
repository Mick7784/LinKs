"use strict";
// Optional footer content: populated when a future configuration source supplies it.
function renderFooter(profile={}){
 const quote=document.getElementById("footer-quote"),value=typeof profile.footer_quote==="string"?profile.footer_quote.trim():"";
 quote.textContent=value;quote.hidden=!value;
 const version=document.getElementById("footer-version");
 version.textContent=profile.app_version||"";version.hidden=!profile.app_version;
}
renderFooter();
const paths={
 youtube:'<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3Z"/>',
 instagram:'<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".7" fill="currentColor"/>',
 mail:'<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m3 7 9 6 9-6"/>',
 email:'<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m3 7 9 6 9-6"/>',
 discord:'<path d="M8 5 5 6C3 10 2 14 3 17l4 2 1-2m8-12 3 1c2 4 3 8 2 11l-4 2-1-2M8 6c3-1 5-1 8 0M6 16c4 2 8 2 12 0"/><circle cx="8.5" cy="12" r="1"/><circle cx="15.5" cy="12" r="1"/>',
 tiktok:'<path d="M14 4v10.5a4.5 4.5 0 1 1-3-4.24"/><path d="M14 4c1 2.4 2.7 3.8 5 4"/>',
 website:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.3 2.5 3.5 5.5 3.5 9S14.3 18.5 12 21c-2.3-2.5-3.5-5.5-3.5-9S9.7 5.5 12 3"/>',
 cart:'<path d="M3 4h2l2 12h10l2-8H6"/><circle cx="9" cy="20" r="1"/><circle cx="17" cy="20" r="1"/>',
 home:'<path d="m3 11 9-7 9 7v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/><path d="M9 21v-6h6v6"/>',
 tag:'<path d="M20 13 13 20 4 11V4h7Z"/><circle cx="8.5" cy="8.5" r="1"/>',
 link:'<path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1"/>',
 play:'<path d="m9 7 8 5-8 5Z" fill="currentColor" stroke="none"/>',
 copy:'<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
 forward:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
 arrow:'<path d="M6 18 18 6M6 6h12v12"/>'
};
function icon(name,cls=""){const node=document.createElementNS("http://www.w3.org/2000/svg","svg");node.setAttribute("viewBox","0 0 24 24");node.setAttribute("fill","none");node.setAttribute("stroke","currentColor");node.setAttribute("stroke-width","1.7");node.setAttribute("stroke-linecap","round");node.setAttribute("stroke-linejoin","round");node.setAttribute("aria-hidden","true");if(cls)node.setAttribute("class",cls);node.innerHTML=paths[name]||paths.website;return node}
function validUrl(value){if(!value)return false;try{return["https:","mailto:","tel:"].includes(new URL(value).protocol)||value.startsWith("#")}catch{return false}}
function text(tag,cls,value){const el=document.createElement(tag);el.className=cls;el.textContent=value;return el}
function external(a,url,affiliate=false){a.href=url;if(url.startsWith("http")){a.target="_blank";a.rel=affiliate?"noopener noreferrer sponsored":"noopener noreferrer"}}
function sectionTitle(id,label,iconName){const heading=text("h2","section-heading",label);heading.id=id;heading.prepend(icon(iconName));return heading}
function decorateSectionTitle(id,iconName){const heading=document.getElementById(id);if(heading&&!heading.querySelector("svg"))heading.prepend(icon(iconName))}
function externalAction(){const action=document.createElement("span");action.className="external-action";action.setAttribute("aria-hidden","true");action.append(icon("arrow"));return action}
async function getConfig(){try{const response=await fetch("/api/public-config",{cache:"no-store"});if(!response.ok)throw new Error();return await response.json()}catch{const fallback=window.LINKS_CONFIG||{profile:{},socials:[],links:[]};return {...fallback,links:(fallback.links||[]).filter(item=>!item.expiresAt||new Date(item.expiresAt).getTime()>Date.now()).map(item=>({...item,type:item.type||(item.featured?"featured":"classic")}))}}}
// Try full-resolution artwork first; YouTube may return a tiny placeholder with HTTP 200.
function videoThumbnailSources(video){
 let id;
 try{const image=new URL(video.thumbnail);if(image.hostname==="i.ytimg.com")id=image.pathname.match(/^\/(?:vi|vi_webp)\/([A-Za-z0-9_-]{11})\//)?.[1]}catch{}
 if(!id)try{const url=new URL(video.url);if(url.hostname==="youtu.be")id=url.pathname.slice(1).split("/")[0];else if(["youtube.com","www.youtube.com"].includes(url.hostname))id=url.searchParams.get("v")||url.pathname.match(/^\/(?:shorts|embed)\/([^/]+)/)?.[1]}catch{}
 if(!/^[A-Za-z0-9_-]{11}$/.test(id||""))return video.thumbnail?[video.thumbnail]:[];
 return [...new Set(["maxresdefault","sddefault","hqdefault","mqdefault","default"].map(size=>"https://i.ytimg.com/vi/"+id+"/"+size+".jpg").concat(video.thumbnail||[]))];
}
function loadVideoThumbnail(image,sources){
 let index=0;
 const next=()=>{if(index>=sources.length){image.remove();return}image.src=sources[index++]};
 image.addEventListener("error",next);
 image.addEventListener("load",()=>{if(image.naturalWidth<=120&&index<sources.length)next()});
 next();
}
function renderVideo(target,video){if(!video||!validUrl(video.url)||!video.title)return;const heading=sectionTitle("latest-video-title","Dernière vidéo","youtube");heading.className="video-heading";const a=document.createElement("a");a.className="video-card";a.dataset.metric="latest-video";external(a,video.url);const visual=document.createElement("div");visual.className="video-visual";const sources=videoThumbnailSources(video);if(sources.length){const image=new Image();image.alt="";image.width=1280;image.height=720;image.decoding="async";visual.append(image);loadVideoThumbnail(image,sources)}const play=document.createElement("span");play.className="video-play";play.setAttribute("aria-hidden","true");play.append(icon("play"));a.append(play);const details=document.createElement("div");details.className="video-details";const copy=document.createElement("div");copy.className="card-copy";copy.append(text("h3","video-title",video.title));const published=new Date(video.published);if(Number.isFinite(published.getTime())){const date=text("time","video-date","Publiée le "+new Intl.DateTimeFormat("fr-FR",{day:"numeric",month:"long",year:"numeric",timeZone:"Europe/Paris"}).format(published));date.dateTime=published.toISOString();copy.append(date)}details.append(copy,externalAction());a.append(visual,details);details.querySelector(".card-copy").prepend(heading);target.append(a);target.hidden=false}
function appendCampaignDates(copy,item){
 const formatter=new Intl.DateTimeFormat("fr-FR",{day:"numeric",month:"short",year:"numeric",timeZone:"Europe/Paris"});
 for(const [value,label] of [[item.start_at||item.startAt,"À partir du "],[item.end_at||item.endAt||item.expiresAt,"Jusqu’au "]]){
  if(!value)continue;const date=new Date(value);if(!Number.isFinite(date.getTime()))continue;
  const node=text("time","promo-dates",label+formatter.format(date));node.dateTime=date.toISOString();copy.append(node);
 }
}
function renderBlock(item){const a=document.createElement("a");external(a,item.url);a.dataset.metric=item.metricKey||"link:"+item.url;a.className="card "+(item.type||"classic")+(item.image?" visual":"");a.dataset.icon=item.icon||"website";if(item.type==="promo"||item.type==="featured"){const label=text("span","offer-label","Offre du moment");label.prepend(icon("tag"));a.append(label)}
 if(item.type==="promo"||item.image){const frame=document.createElement("span");frame.className="promo-visual";if(item.image){const image=new Image();image.src=item.image;image.alt="";image.loading="lazy";image.decoding="async";frame.append(image);if(item.type==="promo"||item.type==="featured"){const backdrop=image.cloneNode();backdrop.className="promo-backdrop";backdrop.setAttribute("aria-hidden","true");a.append(backdrop)}}const copy=document.createElement("span");copy.className="promo-copy";const meta=document.createElement("span");meta.className="promo-meta";if(item.badge)meta.append(text("span","content-badge",item.badge));meta.append(text("span","card-title",item.title));if(item.description)meta.append(text("span","card-description",item.description));copy.append(meta);if(item.type==="promo"||item.type==="featured")appendCampaignDates(copy,item);if(item.cta)copy.append(text("span","card-cta",item.cta));copy.append(externalAction());if(item.type==="classic"){const badge=document.createElement("span");badge.className="card-icon";badge.append(icon(item.icon||"website"));a.append(badge)}a.append(frame,copy);if(item.type==="classic")a.append(externalAction());return a}
 const badge=document.createElement("span");badge.className="card-icon";badge.append(icon(item.icon||"website"));const copy=document.createElement("span");copy.className="card-copy";if(item.badge)copy.append(text("span","content-badge",item.badge));if(item.type==="featured"&&!item.badge)copy.append(text("span","eyebrow","À découvrir"));copy.append(text("span","card-title",item.title));if(item.description)copy.append(text("span","card-description",item.description));if(item.cta&&item.type==="featured")copy.append(text("span","card-cta",item.cta));if(item.type==="featured")appendCampaignDates(copy,item);a.append(badge,copy,externalAction());return a}

function renderOffer(item){
 const card=document.createElement("article");card.className="card offer-card";
 const visual=text("span","offer-visual","");if(item.image){const image=new Image();image.src=item.image;image.alt="";image.loading="lazy";image.decoding="async";visual.append(image)}
 const copy=text("div","offer-copy",""),label=text("span","offer-kicker","Offre du moment");label.prepend(icon("tag"));copy.append(label,text("h3","offer-title",item.title));
 const formatter=new Intl.DateTimeFormat("fr-FR",{day:"numeric",month:"long",year:"numeric",timeZone:"Europe/Paris"});
 const start=new Date(item.start_at||item.startAt||""),end=new Date(item.end_at||item.endAt||item.expiresAt||"");
 if(Number.isFinite(start.getTime())||Number.isFinite(end.getTime())){
  const dates=text("p","offer-dates","");const add=(date)=>{const t=text("time","",formatter.format(date));t.dateTime=date.toISOString();dates.append(t)};
  if(Number.isFinite(start.getTime())){dates.append("Du ");add(start)}
  if(Number.isFinite(end.getTime())){dates.append(Number.isFinite(start.getTime())?" au ":"Jusqu’au ");add(end)}copy.append(dates);
 }
 const code=typeof item.promo_code==="string"?item.promo_code.trim():"";
 if(code){
  const button=text("button","offer-code","");button.type="button";button.setAttribute("aria-label","Copier le code promo "+code);
  const wording=text("span","offer-code-value","Code promo : ");wording.append(text("strong","",code));
  const feedback=text("span","offer-code-feedback","Cliquer pour copier");feedback.setAttribute("aria-live","polite");
  button.append(icon("tag"),wording,icon("copy"),feedback);let reset;
  button.addEventListener("click",async event=>{event.stopPropagation();event.preventDefault();try{await navigator.clipboard.writeText(code);window.dispatchEvent(new CustomEvent("links:promo-code-copy",{detail:{link:item.metricKey,code}}));feedback.textContent="Copié !";clearTimeout(reset);reset=setTimeout(()=>{feedback.textContent="Cliquer pour copier"},2000)}catch{feedback.textContent="Copie impossible";clearTimeout(reset);reset=setTimeout(()=>{feedback.textContent="Cliquer pour copier"},2000)}});copy.append(button);
 }
 const link=text("a","offer-link","");external(link,item.url);link.dataset.metric=item.metricKey||"link:"+item.url;link.setAttribute("aria-label","Ouvrir l’offre "+item.title);card.append(visual,link,copy);return card;
}

function renderOffers(items){
 const root=document.getElementById("offers"),track=document.getElementById("offers-track"),controls=document.getElementById("offers-controls"),dots=document.getElementById("offers-dots"),status=document.getElementById("offers-status");if(!items.length)return;
 decorateSectionTitle("offers-title","tag");
 const offers=items.slice(0,3),interactive=offers.length>1;offers.forEach(item=>{const slide=document.createElement("div");slide.className="carousel-slide";slide.append(renderOffer(item));track.append(slide)});root.hidden=false;controls.hidden=!interactive;
 let index=0,timer,pauseTimer,touchX=0,visible=false;const announce=()=>{if(visible)window.dispatchEvent(new CustomEvent("links:impression",{detail:{link:offers[index].metricKey}}))};
 const slides=[...track.children];const reducedMotion=matchMedia("(prefers-reduced-motion: reduce)");
 const show=(next,user=false)=>{index=(next+offers.length)%offers.length;track.style.transform=`translateX(-${index*100}%)`;slides.forEach((slide,i)=>{const active=i===index;slide.setAttribute("aria-hidden",String(!active));slide.inert=!active;slide.querySelectorAll("a,button").forEach(link=>active?link.removeAttribute("tabindex"):link.setAttribute("tabindex","-1"))});[...dots.children].forEach((dot,i)=>{const active=i===index;dot.classList.toggle("active",active);dot.setAttribute("aria-current",active?"true":"false")});if(interactive)status.textContent=`Offre ${index+1} sur ${offers.length}`;announce();if(user)pause()};
 const play=()=>{clearInterval(timer);if(interactive&&!reducedMotion.matches)timer=setInterval(()=>show(index+1),6000)};const pause=()=>{if(!interactive)return;clearInterval(timer);clearTimeout(pauseTimer);pauseTimer=setTimeout(play,10000)};
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible)announce()},{threshold:.5}).observe(root);
 if(interactive){slides.forEach((slide,i)=>{slide.setAttribute("role","group");slide.setAttribute("aria-label",`${i+1} sur ${offers.length}`)});offers.forEach((_,i)=>{const dot=document.createElement("button");dot.type="button";dot.setAttribute("aria-label",`Afficher l’offre ${i+1} sur ${offers.length}`);dot.addEventListener("click",event=>{event.stopPropagation();show(i,true)});dots.append(dot)});track.addEventListener("touchstart",event=>{touchX=event.touches[0].clientX;pause()},{passive:true});track.addEventListener("touchend",event=>{const delta=event.changedTouches[0].clientX-touchX;if(Math.abs(delta)>45)show(index+(delta<0?1:-1),true)},{passive:true});root.addEventListener("keydown",event=>{if(event.key==="ArrowLeft"||event.key==="ArrowRight"){event.preventDefault();show(index+(event.key==="ArrowRight"?1:-1),true)}});root.addEventListener("pointerenter",pause);root.addEventListener("focusin",pause);document.addEventListener("visibilitychange",()=>document.hidden?clearInterval(timer):play());reducedMotion.addEventListener("change",play);play()}
 show(0)
}
async function start(){
 const config=await getConfig(),profile=config.profile||{};const set=(id,value)=>{const el=document.getElementById(id);if(el&&value)el.textContent=value};set("profile-name",profile.name);set("profile-tagline",profile.tagline);set("profile-description",profile.description);set("footer-name",profile.name);renderFooter(profile);
 if(profile.avatar)document.getElementById("profile-avatar").src=profile.avatar;if(profile.logo){document.getElementById("profile-logo").src=profile.logo;document.getElementById("footer-logo").src=profile.logo}
 const socials=document.getElementById("socials");for(const item of (config.socials||[]).filter(x=>validUrl(x.url))){const a=document.createElement("a");a.className="social";a.dataset.metric=item.metricKey||"social:"+item.platform;external(a,item.url);a.setAttribute("aria-label",item.label||item.platform);a.title=item.label||item.platform;a.append(icon(item.platform));socials.append(a)}
 const video=document.getElementById("latest-video");if(config.latestVideo)fetch("/latest-video.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw new Error();return r.json()}).then(data=>renderVideo(video,data)).catch(()=>{video.hidden=true});
 const visible=(config.links||[]).filter(x=>validUrl(x.url)),offers=visible.filter(x=>x.type==="promo"||x.type==="featured"),permanent=visible.filter(x=>x.type==="classic");renderOffers(offers);const links=document.getElementById("links");if(permanent.length){decorateSectionTitle("links-title","link");for(const item of permanent)links.append(renderBlock(item));document.getElementById("links-section").hidden=false}document.getElementById("year").textContent=new Date().getFullYear()
}
start();

