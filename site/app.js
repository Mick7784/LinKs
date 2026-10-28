"use strict";

// Footer content is supplied by the public configuration.
function renderFooter(profile={}){
 const quote=document.getElementById("footer-quote"),value=typeof profile.footer_quote==="string"?profile.footer_quote.trim():"";
 quote.textContent=value;quote.hidden=!value;
 const version=document.getElementById("footer-version");
 version.textContent=profile.app_version||"";version.hidden=!profile.app_version;
}
renderFooter();
function sectionTitle(id,label,iconName){const heading=text("h2","section-heading",label);heading.id=id;heading.prepend(icon(iconName));return heading}
function decorateSectionTitle(id,iconName){const heading=document.getElementById(id);if(heading&&!heading.querySelector("svg"))heading.prepend(icon(iconName))}

async function getConfig(){
 if(window.LINKS_PREVIEW_CONFIG)return window.LINKS_PREVIEW_CONFIG;
 try{const response=await fetch("/api/public-config",{cache:"no-store"});if(!response.ok)throw new Error();return await response.json()}
 catch{let fallback;try{const r=await fetch("/public-fallback.json",{cache:"no-store"});if(!r.ok)throw new Error();fallback=await r.json()}catch{fallback=window.LINKS_CONFIG||{profile:{},socials:[],links:[]}}
 const now=Date.now();return {...fallback,links:(fallback.links||[]).filter(item=>(!item.expiresAt||new Date(item.expiresAt).getTime()>now)&&(!item.start_at||new Date(item.start_at).getTime()<=now)&&(!item.end_at||new Date(item.end_at).getTime()>now)).map(item=>({...item,type:item.type||(item.featured?"featured":"classic")}))}}
}

// Eligibility remains available to PulSe; the page uses the server's selection.
// Static fallback links are already ranked by the server, then filtered by date.
function selectedOffers(config){
 const now=Date.now(),ids=Array.isArray(config.visible_campaign_ids)?new Set(config.visible_campaign_ids):null;
 return (config.links||[]).filter(x=>validUrl(x.url)&&["promo","featured"].includes(x.type)&&(!ids||ids.has(x.id))&&(!x.start_at||Date.parse(x.start_at)<=now)&&(!x.end_at||Date.parse(x.end_at)>now)).slice(0,3);
}

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
function renderVideo(target,video){if(!video||!validUrl(video.url)||!video.title)return;const heading=sectionTitle("latest-video-title","Dernière vidéo","youtube");heading.className="video-heading";const a=document.createElement("a");a.className="video-card";a.dataset.metric="latest-video";external(a,video.url);const visual=document.createElement("div");visual.className="video-visual";const sources=videoThumbnailSources(video);if(sources.length){const image=new Image();image.alt="";image.width=1280;image.height=720;image.decoding="async";visual.append(image);loadVideoThumbnail(image,sources)}const play=document.createElement("span");play.className="video-play";play.setAttribute("aria-hidden","true");play.append(icon("play"));a.append(play);const details=document.createElement("div");details.className="video-details";const copy=document.createElement("div");copy.className="card-copy";copy.append(text("h3","video-title",video.title));const published=new Date(video.published);if(Number.isFinite(published.getTime())){const date=text("time","video-date","Publiée le "+new Intl.DateTimeFormat("fr-FR",{day:"numeric",month:"long",year:"numeric",timeZone:publicTimezone}).format(published));date.dateTime=published.toISOString();copy.append(date)}details.append(copy,externalAction());a.append(visual,details);details.querySelector(".card-copy").prepend(heading);target.append(a);target.hidden=false}
let disposeOffers=()=>{};
function renderOffers(items){
 disposeOffers();
 const root=document.getElementById("offers"),track=document.getElementById("offers-track"),controls=document.getElementById("offers-controls"),dots=document.getElementById("offers-dots"),status=document.getElementById("offers-status");
 const controller=new AbortController(),listen=(target,type,handler,options={})=>target.addEventListener(type,handler,{...options,signal:controller.signal});
 let observer;
 track.replaceChildren();dots.replaceChildren();controls.querySelector('.carousel-pause')?.remove();track.style.transform="";root.hidden=true;controls.hidden=true;status.textContent="";
 disposeOffers=()=>controller.abort();
 if(!items.length)return;
 decorateSectionTitle("offers-title","tag");
 const offers=items.slice(0,3),interactive=offers.length>1;offers.forEach(item=>{const slide=document.createElement("div");slide.className="carousel-slide";slide.append(renderOffer(item));track.append(slide)});root.hidden=false;controls.hidden=!interactive;
 let index=0,timer,pauseTimer,touchX=0,visible=false;const announce=()=>{if(visible)window.dispatchEvent(new CustomEvent("links:impression",{detail:{link:offers[index].metricKey}}))};
 const slides=[...track.children];const reducedMotion=matchMedia("(prefers-reduced-motion: reduce)");let hoverPaused=false,focusPaused=false,userPaused=false;
 const show=(next,user=false)=>{index=(next+offers.length)%offers.length;track.style.transform=`translateX(-${index*100}%)`;slides.forEach((slide,i)=>{const active=i===index;slide.setAttribute("aria-hidden",String(!active));slide.inert=!active;slide.querySelectorAll("a,button").forEach(link=>active?link.removeAttribute("tabindex"):link.setAttribute("tabindex","-1"))});[...dots.children].forEach((dot,i)=>{const active=i===index;dot.classList.toggle("active",active);dot.setAttribute("aria-current",active?"true":"false")});if(interactive)status.textContent=`Offre ${index+1} sur ${offers.length}`;announce();if(user)pause()};
 const play=()=>{clearInterval(timer);if(interactive&&!hoverPaused&&!focusPaused&&!userPaused&&!document.hidden&&!reducedMotion.matches&&document.documentElement.dataset.linksMotion!=="reduce")timer=setInterval(()=>show(index+1),6000)};const pause=()=>{if(!interactive)return;clearInterval(timer);clearTimeout(pauseTimer);pauseTimer=setTimeout(play,10000)};
 observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible)announce()},{threshold:.5});observer.observe(root);
 disposeOffers=()=>{controller.abort();observer.disconnect();clearInterval(timer);clearTimeout(pauseTimer)};
 if(interactive){slides.forEach((slide,i)=>{slide.setAttribute("role","group");slide.setAttribute("aria-label",`${i+1} sur ${offers.length}`)});offers.forEach((_,i)=>{const dot=document.createElement("button");dot.type="button";dot.setAttribute("aria-label",`Afficher l’offre ${i+1} sur ${offers.length}`);dot.addEventListener("click",event=>{event.stopPropagation();show(i,true)});dots.append(dot)});listen(track,"touchstart",event=>{touchX=event.touches[0].clientX;pause()},{passive:true});listen(track,"touchend",event=>{const delta=event.changedTouches[0].clientX-touchX;if(Math.abs(delta)>45)show(index+(delta<0?1:-1),true)},{passive:true});listen(root,"keydown",event=>{if(event.key==="ArrowLeft"||event.key==="ArrowRight"){event.preventDefault();show(index+(event.key==="ArrowRight"?1:-1),true)}});listen(root,"pointerenter",()=>{hoverPaused=true;pause()});listen(root,"pointerleave",()=>{hoverPaused=false;play()});listen(root,"focusin",()=>{focusPaused=true;pause()});listen(root,"focusout",event=>{focusPaused=root.contains(event.relatedTarget);if(!focusPaused)play()});listen(document,"visibilitychange",play);listen(reducedMotion,"change",play);play()}
 show(0)
}
async function start(){
 const config=await getConfig(),profile=config.profile||{};publicTimezone=config.timezone||profile.timezone||"UTC";
 await LinksTheme.apply(config.appearance);window.LINKS_PUBLIC_CONFIG=config;window.dispatchEvent(new CustomEvent("links:config",{detail:config}));
 if(config.setup_completed!==true){document.querySelector("main").replaceChildren(text("p","fallback","Links est en cours de configuration."));return}
 const set=(id,value)=>{const el=document.getElementById(id);if(el){el.textContent=value||"";el.hidden=!value}};
 set("profile-name",profile.name||"Links");set("profile-tagline",profile.tagline);set("profile-description",profile.description);set("footer-name",profile.footer_owner||profile.name);renderFooter(profile);
 document.title=(profile.name||"Links")+" — Tous mes liens";document.querySelector('meta[name="description"]').content=profile.description||"";
 const image=(id,value,alt="")=>{const el=document.getElementById(id);el.hidden=!value;if(value){el.src=value;el.alt=alt}else el.removeAttribute("src")};
 image("profile-avatar",profile.avatar,profile.name||"");image("profile-logo",profile.logo);image("footer-logo",profile.logo);
 document.querySelector(".logo-badge").hidden=!profile.logo;document.querySelector(".portrait-wrap").hidden=!profile.avatar&&!profile.logo;
 if(!profile.avatar&&profile.logo){image("profile-avatar",profile.logo);document.querySelector(".logo-badge").hidden=true}
 const favicon=document.getElementById("site-favicon");if(profile.logo)favicon.href=profile.logo;else favicon.removeAttribute("href");
 const socials=document.getElementById("socials");for(const item of (config.socials||[]).filter(x=>validUrl(x.url))){socials.append(renderShortcut(item))}
 const video=document.getElementById("latest-video");if(config.latestVideo)fetch("/latest-video.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw new Error();return r.json()}).then(data=>renderVideo(video,data)).catch(()=>{video.hidden=true});
 const visible=(config.links||[]).filter(x=>validUrl(x.url)),offers=selectedOffers(config),permanent=visible.filter(x=>x.type==="classic");renderOffers(offers);watchCampaigns(config,offers);const links=document.getElementById("links");if(permanent.length){decorateSectionTitle("links-title","link");for(const item of permanent)links.append(renderBlock(item));document.getElementById("links-section").hidden=false}document.getElementById("year").textContent=new Intl.DateTimeFormat("fr-FR",{year:"numeric",timeZone:publicTimezone}).format(new Date())
}
// Refresh only campaign DOM. Metrics and all page-level listeners start once.
function watchCampaigns(config,initial){
 if(window.LINKS_PREVIEW_CONFIG)return;
 let signature=JSON.stringify(initial),timer,busy=false,current=config;
 const schedule=()=>{clearTimeout(timer);const remaining=Date.parse(current.next_campaign_change)-Date.now();const delay=!document.hidden&&remaining>0?Math.min(30000,Math.max(250,remaining+100)):30000;timer=setTimeout(refresh,delay)};
 async function refresh(){
  if(busy)return;if(document.hidden){schedule();return}busy=true;
  try{const next=await getConfig();const offers=selectedOffers(next);
   const nextSignature=JSON.stringify(offers);if(nextSignature!==signature){renderOffers(offers);signature=nextSignature}current=next;
  }finally{busy=false;schedule()}
 }
 document.addEventListener("visibilitychange",()=>{if(!document.hidden){clearTimeout(timer);refresh()}});schedule();
}
start();

