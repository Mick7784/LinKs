"use strict";
let publicTimezone = "UTC";
const paths = {
  phone: '<path d="M5 3h4l2 5-3 2c2 4 3 5 6 6l2-3 5 2v4c-1 5-18-5-18-13Z"/>',
  video: '<rect x="3" y="5" width="13" height="14" rx="3"/><path d="m16 9 5-3v12l-5-3"/>',
  podcast: '<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/>',
  blog: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 11h8M8 15h5"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18M7 15h3m4 0h3"/>',
  location: '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
  homeassistant: '<path d="m2 11 10-9 10 9v11H2Z"/><path d="M12 19V8m0 6-5-4m5 7 5-5"/><circle cx="12" cy="7" r="1"/><circle cx="6" cy="9" r="1"/><circle cx="18" cy="11" r="1"/>',
  facebook: '<path d="M15 21v-8h3l1-4h-4V7c0-1 1-2 2-2h2V2h-3c-3 0-5 2-5 5v2H8v4h3v8"/>',
  x: '<path d="m4 3 16 18h-4L4 3h4l12 18M20 3 4 21"/>',
  linkedin: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 10v7m4 0v-7m0 3c0-4 6-4 6 0v4"/><circle cx="7" cy="7" r=".6"/>',
  github: '<path d="M9 21v-4c-4 1-4-2-6-2m12 6v-4c0-1-.5-2-1-2 4-.5 6-2 6-6 0-1-1-2-1-3l-.2-3-3 2a13 13 0 0 0-8 0L5 3l-.2 3c-.6 1-1 2-1 3 0 4 2 5.5 6 6-.7.5-1 1-1 2"/>',
  threads: '<path d="M19 6c-3-5-12-5-14 1-3 9 3 15 9 14 7-1 8-8 4-11-4-3-10-1-10 3 0 4 7 4 8-1 1-6-5-8-7-4"/>',
  twitch: '<path d="M4 3h17v12l-5 5h-5l-4 3v-3H3V6Z"/><path d="M11 7v6m5-6v6"/>',
  telegram: '<path d="m3 10 18-7-4 18-5-6-3 3v-5l9-7-12 6Z"/>',
  whatsapp: '<path d="M4 17 2 22l6-2a9 9 0 1 0-4-3Z"/><path d="M8 7c-2 4 5 10 8 8l1-2-3-1-1 1-3-3 1-1-2-3Z"/>',
  pinterest: '<circle cx="12" cy="11" r="9"/><path d="m8 22 3-14m-.7 4c1 4 7 3 7-2 0-6-10-6-10 0"/>',
  reddit: '<path d="m12 7 2-5 5 1"/><circle cx="20" cy="3" r="1"/><ellipse cx="12" cy="14" rx="9" ry="6"/><path d="M4 10c-4-4-5 4-1 4m17-4c4-4 5 4 1 4M8 16c3 2 5 2 8 0"/><circle cx="8" cy="13" r="1"/><circle cx="16" cy="13" r="1"/>',
  snapchat: '<path d="M7 9C5 1 19 1 17 9l3 1-3 2c0 3 2 4 4 5l-3 1-1 2-3-1-2 2-2-2-3 1-1-2-3-1c2-1 4-2 4-5l-3-2Z"/>',
  network: '<circle cx="12" cy="5" r="3"/><circle cx="5" cy="18" r="3"/><circle cx="19" cy="18" r="3"/><path d="m10 8-4 7m8-7 4 7M8 18h8"/>',
  contact: '<rect x="4" y="2" width="16" height="20" rx="2"/><circle cx="12" cy="9" r="3"/><path d="M7 18c0-5 10-5 10 0M2 6h4M2 12h4M2 18h4"/>',

  youtube:
    '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 5 3-5 3Z"/>',
  instagram:
    '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".7" fill="currentColor"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m3 7 9 6 9-6"/>',
  email:
    '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m3 7 9 6 9-6"/>',
  discord:
    '<path d="M8 5 5 6C3 10 2 14 3 17l4 2 1-2m8-12 3 1c2 4 3 8 2 11l-4 2-1-2M8 6c3-1 5-1 8 0M6 16c4 2 8 2 12 0"/><circle cx="8.5" cy="12" r="1"/><circle cx="15.5" cy="12" r="1"/>',
  tiktok:
    '<path d="M14 4v10.5a4.5 4.5 0 1 1-3-4.24"/><path d="M14 4c1 2.4 2.7 3.8 5 4"/>',
  website:
    '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.3 2.5 3.5 5.5 3.5 9S14.3 18.5 12 21c-2.3-2.5-3.5-5.5-3.5-9S9.7 5.5 12 3"/>',
  amazon:
    '<path d="M14.7 14.8c-1.6 1.5-5.4 1.9-6.4-.4-1.1-2.7 1-4.5 5.1-4.5V8.6c0-1.5-2.8-1.7-3.4.2L7.6 8c.8-3.6 7.9-4.1 8.4.6v5.1l1.2 1.5-2.1 1.6-1.1-1.6Zm-1.3-2.9c-2.7-.1-3.5 1-2.8 2 .8 1.2 2.8.2 2.8-2Z" fill="currentColor" stroke="none"/><path d="M3 18c5.1 3.2 11 3.4 17-.1m-3.1-.7 3.7.3-1.2 3" stroke="#ff9900" stroke-width="1.7"/>',
  cart: '<path d="M3 4h2l2 12h10l2-8H6"/><circle cx="9" cy="20" r="1"/><circle cx="17" cy="20" r="1"/>',
  home: '<path d="m3 11 9-7 9 7v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/><path d="M9 21v-6h6v6"/>',
  tag: '<path d="M20 13 13 20 4 11V4h7Z"/><circle cx="8.5" cy="8.5" r="1"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1"/>',
  play: '<path d="m9 7 8 5-8 5Z" fill="currentColor" stroke="none"/>',
  copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
  forward: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  arrow: '<path d="M6 18 18 6M6 6h12v12"/>',
};
function icon(name, cls = "") {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  node.setAttribute("viewBox", "0 0 24 24");
  node.setAttribute("fill", "none");
  node.setAttribute("stroke", "currentColor");
  node.setAttribute("stroke-width", "1.7");
  node.setAttribute("stroke-linecap", "round");
  node.setAttribute("stroke-linejoin", "round");
  node.setAttribute("aria-hidden", "true");
  if (cls) node.setAttribute("class", cls);
  node.innerHTML = paths[name] || paths.website;
  return node;
}
function validUrl(value) {
  if (!value) return false;
  try {
    return (
      ["https:", "mailto:", "tel:"].includes(new URL(value).protocol) ||
      value.startsWith("#")
    );
  } catch {
    return false;
  }
}
function text(tag, cls, value) {
  const el = document.createElement(tag);
  el.className = cls;
  el.textContent = value;
  return el;
}
function external(a, url, affiliate = false) {
  a.href = url;
  if (url.startsWith("http")) {
    a.target = "_blank";
    a.rel = affiliate ? "noopener noreferrer sponsored" : "noopener noreferrer";
  }
}
function isAmazon(item) {
  if (item.icon === "amazon") return true;
  try {
    const host = new URL(item.url).hostname.toLowerCase();
    return (
      /^(?:[a-z0-9-]+\.)?amazon\.(?:com|fr|de|it|es|nl|pl|se|ca|com\.au|co\.uk|co\.jp|com\.br|com\.mx|in|ae|sa|com\.be|com\.tr|sg)$/.test(
        host,
      ) || ["amzn.to", "amzn.eu"].includes(host)
    );
  } catch {
    return false;
  }
}
async function copyPromoCode(value) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return true;
    }
  } catch {}
  const active = document.activeElement,
    input = document.createElement("textarea");
  input.value = value;
  input.readOnly = true;
  input.className = "clipboard-fallback";
  input.setAttribute("aria-label", "Code promo à copier");
  document.body.append(input);
  input.select();
  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch {
  } finally {
    input.remove();
    active?.focus({ preventScroll: true });
  }
  return copied;
}
function appendCampaignDates(copy, item) {
  const formatter = new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: publicTimezone,
  });
  for (const [value, label] of [
    [item.start_at || item.startAt, "À partir du "],
    [item.end_at || item.endAt || item.expiresAt, "Jusqu’au "],
  ]) {
    if (!value) continue;
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) continue;
    const node = text("time", "promo-dates", label + formatter.format(date));
    node.dateTime = date.toISOString();
    copy.append(node);
  }
}
function renderBlock(item) {
  item={...item,image:window.LinksTheme?LinksTheme.asset(item.image):item.image};
  const amazon = isAmazon(item);
  const iconName = amazon ? "amazon" : item.icon || "website";
  const a = document.createElement("a");
  external(a, item.url);
  a.dataset.metric = item.metricKey || "link:" + item.url;
  a.className =
    "card " + (item.type || "classic") + (item.image ? " visual" : "");
  a.dataset.icon = iconName;
  if (item.type === "promo" || item.type === "featured") {
    const label = text("span", "offer-label", "Offre du moment");
    label.prepend(icon("tag"));
    a.append(label);
  }
  if (item.type === "promo" || item.image) {
    const frame = document.createElement("span");
    frame.className = "promo-visual";
    if (item.image) {
      const image = new Image();
      image.src = item.image;
      image.alt = "";
      image.loading = "lazy";
      image.decoding = "async";
      frame.append(image);
      if (item.type === "promo" || item.type === "featured") {
        const backdrop = image.cloneNode();
        backdrop.className = "promo-backdrop";
        backdrop.setAttribute("aria-hidden", "true");
        a.append(backdrop);
      }
    }
    const copy = document.createElement("span");
    copy.className = "promo-copy";
    const meta = document.createElement("span");
    meta.className = "promo-meta";
    if (item.badge) meta.append(text("span", "content-badge", item.badge));
    meta.append(text("span", "card-title", item.title));
    if (item.description)
      meta.append(text("span", "card-description", item.description));
    copy.append(meta);
    if (item.type === "promo" || item.type === "featured")
      appendCampaignDates(copy, item);
    if (item.cta) copy.append(text("span", "card-cta", item.cta));
    copy.append(externalAction());
    if (item.type === "classic") {
      const badge = document.createElement("span");
      badge.className = "card-icon";
      badge.append(icon(iconName));
      a.append(badge);
    }
    a.append(frame, copy);
    if (item.type === "classic") a.append(externalAction());
    return a;
  }
  const badge = document.createElement("span");
  badge.className = "card-icon";
  badge.append(icon(iconName));
  const copy = document.createElement("span");
  copy.className = "card-copy";
  if (item.badge) copy.append(text("span", "content-badge", item.badge));
  if (item.type === "featured" && !item.badge)
    copy.append(text("span", "eyebrow", "À découvrir"));
  copy.append(text("span", "card-title", item.title));
  if (item.description)
    copy.append(text("span", "card-description", item.description));
  if (item.cta && item.type === "featured")
    copy.append(text("span", "card-cta", item.cta));
  if (item.type === "featured") appendCampaignDates(copy, item);
  a.append(badge, copy, externalAction());
  return a;
}

function renderOffer(item) {
  item={...item,image:window.LinksTheme?LinksTheme.asset(item.image):item.image};
  const card = document.createElement("article");
  card.className = "card offer-card";
  const visual = text("span", "offer-visual", "");
  if (item.image) {
    const image = new Image();
    image.src = item.image;
    image.alt = "";
    image.loading = "lazy";
    image.decoding = "async";
    visual.append(image);
  }
  const copy = text("div", "offer-copy", ""),
    label = text("span", "offer-kicker", "Offre du moment");
  label.prepend(icon("tag"));
  copy.append(label, text("h3", "offer-title", item.title));
  const formatter = new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: publicTimezone,
  });
  const start = new Date(item.start_at || item.startAt || ""),
    end = new Date(item.end_at || item.endAt || item.expiresAt || "");
  if (Number.isFinite(start.getTime()) || Number.isFinite(end.getTime())) {
    const dates = text("p", "offer-dates", "");
    const add = (date) => {
      const t = text("time", "", formatter.format(date));
      t.dateTime = date.toISOString();
      dates.append(t);
    };
    if (Number.isFinite(start.getTime())) {
      dates.append("Du ");
      add(start);
    }
    if (Number.isFinite(end.getTime())) {
      dates.append(Number.isFinite(start.getTime()) ? " au " : "Jusqu’au ");
      add(end);
    }
    copy.append(dates);
  }
  const code =
    typeof item.promo_code === "string" ? item.promo_code.trim() : "";
  if (code) {
    const button = text("button", "offer-code", "");
    button.type = "button";
    button.setAttribute("aria-label", "Copier le code promo " + code);
    const wording = text("span", "offer-code-value", "Code promo : ");
    wording.append(text("strong", "", code));
    const feedback = text("span", "offer-code-feedback", "Cliquer pour copier");
    feedback.setAttribute("aria-live", "polite");
    button.append(icon("tag"), wording, icon("copy"), feedback);
    let reset;
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      event.preventDefault();
      try {
        if (!(await copyPromoCode(code))) throw new Error("Copy failed");
        window.dispatchEvent(
          new CustomEvent("links:promo-code-copy", {
            detail: {
              link: item.metricKey || (item.id ? "block:" + item.id : ""),
              code,
            },
          }),
        );
        feedback.textContent = "Copié !";
        clearTimeout(reset);
        reset = setTimeout(() => {
          feedback.textContent = "Cliquer pour copier";
        }, 2000);
      } catch {
        feedback.textContent = "Copie impossible";
        clearTimeout(reset);
        reset = setTimeout(() => {
          feedback.textContent = "Cliquer pour copier";
        }, 2000);
      }
    });
    copy.append(button);
  }
  const link = text("a", "offer-link", "");
  external(link, item.url);
  link.dataset.metric = item.metricKey || "link:" + item.url;
  link.setAttribute("aria-label", "Ouvrir l’offre " + item.title);
  card.append(visual, link, copy);
  return card;
}

function externalAction() {
  const action = document.createElement("span");
  action.className = "external-action";
  action.setAttribute("aria-hidden", "true");
  action.append(icon("arrow"));
  return action;
}
