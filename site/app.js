"use strict";

const paths = {
  youtube: '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3Z"/>',
  instagram: '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".7" fill="currentColor"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m3 7 9 6 9-6"/>',
  discord: '<path d="M8 5 5 6C3 10 2 14 3 17l4 2 1-2m8-12 3 1c2 4 3 8 2 11l-4 2-1-2M8 6c3-1 5-1 8 0M6 16c4 2 8 2 12 0"/><circle cx="8.5" cy="12" r="1"/><circle cx="15.5" cy="12" r="1"/>',
  tiktok: '<path d="M14 4v10.5a4.5 4.5 0 1 1-3-4.24"/><path d="M14 4c1 2.4 2.7 3.8 5 4"/>',
  website: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.3 2.5 3.5 5.5 3.5 9S14.3 18.5 12 21c-2.3-2.5-3.5-5.5-3.5-9S9.7 5.5 12 3"/>',
  cart: '<path d="M3 4h2l2 12h10l2-8H6"/><circle cx="9" cy="20" r="1"/><circle cx="17" cy="20" r="1"/>',
  home: '<path d="m3 11 9-7 9 7v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/><path d="M9 21v-6h6v6"/>',
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
  node.innerHTML = paths[name] || paths.website;
  return node;
}

function validUrl(value) {
  if (!value) return false;
  try { return ["https:", "mailto:", "tel:"].includes(new URL(value).protocol); } catch { return false; }
}

function text(tag, cls, value) {
  const el = document.createElement(tag);
  el.className = cls;
  el.textContent = value;
  return el;
}

const config = window.LINKS_CONFIG || { profile: {}, socials: [], links: [] };
const profile = config.profile || {};
function setText(id, value) {
  const el = document.getElementById(id);
  if (el && value) el.textContent = value;
}

setText("profile-name", profile.name);
setText("profile-tagline", profile.tagline);
setText("profile-description", profile.description);
setText("footer-name", profile.name);
if (profile.avatar) document.getElementById("profile-avatar").src = profile.avatar;
if (profile.logo) {
  document.getElementById("profile-logo").src = profile.logo;
  document.getElementById("footer-logo").src = profile.logo;
}

const socialTarget = document.getElementById("socials");
for (const item of config.socials.filter((item) => validUrl(item.url))) {
  const a = document.createElement("a");
  const label = item.label || item.platform;
  a.className = "social";
  a.href = item.url;
  a.setAttribute("aria-label", label);
  a.title = label;
  if (item.url.startsWith("http")) {
    a.target = "_blank";
    a.rel = "noopener noreferrer";
  }
  a.append(icon(item.platform));
  socialTarget.append(a);
}

const latestVideoTarget = document.getElementById("latest-video");
const latestVideo = config.latestVideo;
if (latestVideo && validUrl(latestVideo.url) && latestVideo.title && latestVideo.image) {
  const a = document.createElement("a");
  a.className = "video-card";
  a.href = latestVideo.url;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  const image = document.createElement("img");
  image.src = latestVideo.image;
  image.alt = "Miniature de la dernière vidéo";
  image.loading = "eager";
  const copy = document.createElement("span");
  copy.className = "video-copy";
  copy.append(text("span", "eyebrow", "Dernière vidéo"), text("span", "video-title", latestVideo.title), text("span", "video-action", "Regarder sur YouTube"));
  a.append(image, copy, icon("arrow", "arrow"));
  latestVideoTarget.append(a);
  latestVideoTarget.hidden = false;
}

const linkTarget = document.getElementById("links");
function renderLinks() {
  linkTarget.replaceChildren();
  const now = Date.now();
  const visible = config.links.filter((item) => validUrl(item.url) && (!item.expiresAt || item.expiresAt > now));
  for (const item of visible) {
    const a = document.createElement("a");
    a.href = item.url;
    a.className = "card" + (item.featured ? " featured" : "");
    if (item.url.startsWith("http")) {
      a.target = "_blank";
      a.rel = item.affiliate ? "noopener noreferrer sponsored" : "noopener noreferrer";
    }
    const badge = document.createElement("span");
    badge.className = "card-icon";
    if (item.image) {
      const image = document.createElement("img");
      image.src = item.image;
      image.alt = "";
      badge.append(image);
    } else badge.append(icon(item.icon || "website"));
    const copy = document.createElement("span");
    copy.className = "card-copy";
    if (item.featured) copy.append(text("span", "eyebrow", "À découvrir"));
    copy.append(text("span", "card-title", item.title));
    if (item.description) copy.append(text("span", "card-description", item.description));
    if (item.affiliate) copy.append(text("span", "affiliate", "Lien affilié · vous soutenez la chaîne"));
    a.append(badge, copy, icon("arrow", "arrow"));
    linkTarget.append(a);
  }
  const next = visible.map((item) => item.expiresAt).filter(Boolean).filter((value) => value > now).sort((a, b) => a - b)[0];
  if (next) window.setTimeout(renderLinks, Math.max(0, next - Date.now()));
}

renderLinks();
document.getElementById("year").textContent = new Date().getFullYear();
