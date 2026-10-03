"use strict";
let publicTimezone="UTC";
const paths={
 youtube:'<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3Z"/>',
 instagram:'<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".7" fill="currentColor"/>',
 mail:'<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m3 7 9 6 9-6"/>',
 email:'<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m3 7 9 6 9-6"/>',
 discord:'<path d="M8 5 5 6C3 10 2 14 3 17l4 2 1-2m8-12 3 1c2 4 3 8 2 11l-4 2-1-2M8 6c3-1 5-1 8 0M6 16c4 2 8 2 12 0"/><circle cx="8.5" cy="12" r="1"/><circle cx="15.5" cy="12" r="1"/>',
 tiktok:'<path d="M14 4v10.5a4.5 4.5 0 1 1-3-4.24"/><path d="M14 4c1 2.4 2.7 3.8 5 4"/>',
 website:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.3 2.5 3.5 5.5 3.5 9S14.3 18.5 12 21c-2.3-2.5-3.5-5.5-3.5-9S9.7 5.5 12 3"/>',
 amazon:'<path d="M14.7 14.8c-1.6 1.5-5.4 1.9-6.4-.4-1.1-2.7 1-4.5 5.1-4.5V8.6c0-1.5-2.8-1.7-3.4.2L7.6 8c.8-3.6 7.9-4.1 8.4.6v5.1l1.2 1.5-2.1 1.6-1.1-1.6Zm-1.3-2.9c-2.7-.1-3.5 1-2.8 2 .8 1.2 2.8.2 2.8-2Z" fill="currentColor" stroke="none"/><path d="M3 18c5.1 3.2 11 3.4 17-.1m-3.1-.7 3.7.3-1.2 3" stroke="#ff9900" stroke-width="1.7"/>',
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
function isAmazon(item){
 if(item.icon==="amazon")return true;
 try{const host=new URL(item.url).hostname.toLowerCase();return /^(?:[a-z0-9-]+\.)?amazon\.(?:com|fr|de|it|es|nl|pl|se|ca|com\.au|co\.uk|co\.jp|com\.br|com\.mx|in|ae|sa|com\.be|com\.tr|sg)$/.test(host)||["amzn.to","amzn.eu"].includes(host)}catch{return false}
}
async function copyPromoCode(value){
 try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(value);return true}}catch{}
 const active=document.activeElement,input=document.createElement("textarea");input.value=value;input.readOnly=true;input.className="clipboard-fallback";input.setAttribute("aria-label","Code promo à copier");document.body.append(input);input.select();
 let copied=false;try{copied=document.execCommand("copy")}catch{}finally{input.remove();active?.focus({preventScroll:true})}return copied;
}
function appendCampaignDates(copy,item){
 const formatter=new Intl.DateTimeFormat("fr-FR",{day:"numeric",month:"short",year:"numeric",timeZone:publicTimezone});
 for(const [value,label] of [[item.start_at||item.startAt,"À partir du "],[item.end_at||item.endAt||item.expiresAt,"Jusqu’au "]]){
  if(!value)continue;const date=new Date(value);if(!Number.isFinite(date.getTime()))continue;
  const node=text("time","promo-dates",label+formatter.format(date));node.dateTime=date.toISOString();copy.append(node);
 }
}
function renderBlock(item){const amazon=isAmazon(item);const iconName=amazon?"amazon":item.icon||"website";const a=document.createElement("a");external(a,item.url);a.dataset.metric=item.metricKey||"link:"+item.url;a.className="card "+(item.type||"classic")+(item.image?" visual":"");a.dataset.icon=iconName;if(item.type==="promo"||item.type==="featured"){const label=text("span","offer-label","Offre du moment");label.prepend(icon("tag"));a.append(label)}
 if(item.type==="promo"||item.image){const frame=document.createElement("span");frame.className="promo-visual";if(item.image){const image=new Image();image.src=item.image;image.alt="";image.loading="lazy";image.decoding="async";frame.append(image);if(item.type==="promo"||item.type==="featured"){const backdrop=image.cloneNode();backdrop.className="promo-backdrop";backdrop.setAttribute("aria-hidden","true");a.append(backdrop)}}const copy=document.createElement("span");copy.className="promo-copy";const meta=document.createElement("span");meta.className="promo-meta";if(item.badge)meta.append(text("span","content-badge",item.badge));meta.append(text("span","card-title",item.title));if(item.description)meta.append(text("span","card-description",item.description));copy.append(meta);if(item.type==="promo"||item.type==="featured")appendCampaignDates(copy,item);if(item.cta)copy.append(text("span","card-cta",item.cta));copy.append(externalAction());if(item.type==="classic"){const badge=document.createElement("span");badge.className="card-icon";badge.append(icon(iconName));a.append(badge)}a.append(frame,copy);if(item.type==="classic")a.append(externalAction());return a}
 const badge=document.createElement("span");badge.className="card-icon";badge.append(icon(iconName));const copy=document.createElement("span");copy.className="card-copy";if(item.badge)copy.append(text("span","content-badge",item.badge));if(item.type==="featured"&&!item.badge)copy.append(text("span","eyebrow","À découvrir"));copy.append(text("span","card-title",item.title));if(item.description)copy.append(text("span","card-description",item.description));if(item.cta&&item.type==="featured")copy.append(text("span","card-cta",item.cta));if(item.type==="featured")appendCampaignDates(copy,item);a.append(badge,copy,externalAction());return a}

function renderOffer(item){
 const card=document.createElement("article");card.className="card offer-card";
 const visual=text("span","offer-visual","");if(item.image){const image=new Image();image.src=item.image;image.alt="";image.loading="lazy";image.decoding="async";visual.append(image)}
 const copy=text("div","offer-copy",""),label=text("span","offer-kicker","Offre du moment");label.prepend(icon("tag"));copy.append(label,text("h3","offer-title",item.title));
 const formatter=new Intl.DateTimeFormat("fr-FR",{day:"numeric",month:"long",year:"numeric",timeZone:publicTimezone});
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
  button.addEventListener("click",async event=>{event.stopPropagation();event.preventDefault();try{if(!await copyPromoCode(code))throw new Error("Copy failed");window.dispatchEvent(new CustomEvent("links:promo-code-copy",{detail:{link:item.metricKey||(item.id?"block:"+item.id:""),code}}));feedback.textContent="Copié !";clearTimeout(reset);reset=setTimeout(()=>{feedback.textContent="Cliquer pour copier"},2000)}catch{feedback.textContent="Copie impossible";clearTimeout(reset);reset=setTimeout(()=>{feedback.textContent="Cliquer pour copier"},2000)}});copy.append(button);
 }
 const link=text("a","offer-link","");external(link,item.url);link.dataset.metric=item.metricKey||"link:"+item.url;link.setAttribute("aria-label","Ouvrir l’offre "+item.title);card.append(visual,link,copy);return card;
}


function externalAction(){const action=document.createElement("span");action.className="external-action";action.setAttribute("aria-hidden","true");action.append(icon("arrow"));return action}
