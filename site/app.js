"use strict";
const paths = {
  youtube: '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3Z"/>',
  instagram: '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".7" fill="currentColor"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m3 7 9 6 9-6"/>',
  shop: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/><path d="M9 21v-8h6v8"/>',
  discord: '<path d="M8 5 5 6C3 10 2 14 3 17l4 2 1-2m8-12 3 1c2 4 3 8 2 11l-4 2-1-2M8 6c3-1 5-1 8 0M6 16c4 2 8 2 12 0"/><circle cx="8.5" cy="12" r="1"/><circle cx="15.5" cy="12" r="1"/>',
  arrow: '<path d="M6 18 18 6M6 6h12v12"/>'
};
function icon(name, className = "") {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  node.setAttribute("viewBox", "0 0 24 24");
  node.setAttribute("fill", "none");
  node.setAttribute("stroke", "currentColor");
  node.setAttribute("stroke-width", "1.7");
  node.setAttribute("stroke-linecap", "round");
  node.setAttribute("stroke-linejoin", "round");
  node.setAttribute("aria-hidden", "true");
  if (className) node.setAttribute("class", className);
  node.innerHTML = paths[name] || paths.arrow;
  return node;
}
function validUrl(value) {
  if (!value) return false;
  try { return ["https:", "mailto:"].includes(new URL(value).protocol); } catch { return false; }
}
function text(tag, cls, value) {
  const el = document.createElement(tag); el.className = cls; el.textContent = value; return el;
}
const config = window.LINKS_CONFIG || { socials: [], links: [] };
for (const item of config.socials.filter(item => validUrl(item.url))) {
  const a = document.createElement("a");
  a.className = "social"; a.href = item.url; a.setAttribute("aria-label", item.label); a.title = item.label;
  a.append(icon(item.icon)); document.getElementById("socials").append(a);
}
for (const item of config.links.filter(item => validUrl(item.url))) {
  const a = document.createElement("a"); a.href = item.url;
  a.className = "card" + (item.featured ? " featured" : ""); a.dataset.icon = item.icon;
  if (item.affiliate) a.rel = "sponsored";
  const badge = document.createElement("span"); badge.className = "card-icon"; badge.append(icon(item.icon));
  const copy = document.createElement("span"); copy.className = "card-copy";
  if (item.eyebrow) copy.append(text("span", "eyebrow", item.eyebrow));
  copy.append(text("span", "card-title", item.title), text("span", "card-description", item.description));
  if (item.affiliate) copy.append(text("span", "affiliate", "Lien affilié · vous soutenez la chaîne"));
  a.append(badge, copy, icon("arrow", "arrow")); document.getElementById("links").append(a);
}
document.getElementById("year").textContent = new Date().getFullYear();
