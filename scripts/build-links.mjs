import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const root = process.cwd();
const errors = [];
const platforms = new Set(["youtube", "instagram", "tiktok", "discord", "x", "twitch", "github", "linkedin", "email", "website"]);
const allowed = {
  root: new Set(["$schema", "siteUrl", "profile", "latestVideo", "socials", "links"]),
  profile: new Set(["name", "tagline", "description", "avatar", "logo"]),
  latestVideo: new Set(["channelId"]),
  social: new Set(["platform", "url", "label"]),
  link: new Set(["title", "description", "url", "image", "icon", "featured", "affiliate", "expiresAt"]),
};

let raw;
try { raw = JSON.parse(readFileSync(resolve(root, "links.json"), "utf8")); }
catch (error) { fail([`links.json est invalide : ${error.message}`]); }
if (!record(raw)) fail(["La racine de links.json doit être un objet."]);

checkKeys(raw, "", allowed.root);
const profile = parseProfile(raw.profile);
const latestVideo = raw.latestVideo === undefined ? undefined : await parseLatestVideo(raw.latestVideo);
const socials = raw.socials === undefined ? [] : parseSocials(raw.socials);
const links = parseLinks(raw.links);
const siteUrl = raw.siteUrl === undefined ? undefined : requiredUrl(raw.siteUrl, "siteUrl", ["http:", "https:"]);
if (errors.length) fail(errors);

const output = {
  ...(siteUrl && { siteUrl: siteUrl.replace(/\/+$/, "") }),
  profile,
  ...(latestVideo && { latestVideo }),
  socials,
  links: links.filter((link) => link.expiresAt === null || link.expiresAt > Date.now()),
};
writeFileSync(resolve(root, "site/config.js"), `/* Généré depuis links.json — ne pas modifier directement. */\nwindow.LINKS_CONFIG = ${JSON.stringify(output, null, 2)};\n`);
console.log(`[links] ${output.links.length} lien(s) généré(s).`);

function parseProfile(value) {
  if (!record(value)) { errors.push("profile : objet obligatoire."); return {}; }
  checkKeys(value, "profile", allowed.profile);
  const name = requiredString(value.name, "profile.name");
  const avatar = image(value.avatar, "profile.avatar");
  const tagline = optionalString(value.tagline, "profile.tagline");
  const description = optionalString(value.description, "profile.description");
  const logo = value.logo === undefined ? undefined : image(value.logo, "profile.logo");
  return { name, avatar, ...(tagline && { tagline }), ...(description && { description }), ...(logo && { logo }) };
}

async function parseLatestVideo(value) {
  if (!record(value)) { errors.push("latestVideo : objet attendu."); return undefined; }
  checkKeys(value, "latestVideo", allowed.latestVideo);
  const channelId = requiredString(value.channelId, "latestVideo.channelId");
  if (!/^UC[\w-]{22}$/.test(channelId)) {
    errors.push("latestVideo.channelId : identifiant YouTube invalide (doit commencer par UC).");
    return undefined;
  }
  try {
    const response = await fetch(`https://www.youtube.com/feeds/videos.xml?channel_id=${encodeURIComponent(channelId)}`, {
      headers: { "user-agent": "DomotiK-Studio-Linktree/1.0" },
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) throw new Error(`réponse HTTP ${response.status}`);
    const feed = await response.text();
    const entry = /<entry>([\s\S]*?)<\/entry>/.exec(feed)?.[1];
    const videoId = xmlValue(entry, "yt:videoId");
    const title = xmlValue(entry, "title");
    const published = xmlValue(entry, "published");
    if (!videoId || !title) throw new Error("aucune vidéo trouvée dans le flux");
    return { title, url: `https://youtu.be/${videoId}`, ...(published && { published }) };
  } catch (error) {
    errors.push(`latestVideo : impossible de récupérer la dernière vidéo YouTube (${error.message}).`);
    return undefined;
  }
}

function xmlValue(xml, tag) {
  if (!xml) return undefined;
  const escaped = tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const raw = new RegExp(`<${escaped}[^>]*>([\\s\\S]*?)<\\/${escaped}>`).exec(xml)?.[1];
  return raw ? decodeXml(raw.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1").trim()) : undefined;
}
function decodeXml(value) { return value.replace(/&(amp|lt|gt|quot|apos|#39);/g, (_, entity) => ({ amp: "&", lt: "<", gt: ">", quot: "\\\"", apos: "'", "#39": "'" })[entity]); }

function parseSocials(value) {
  if (!Array.isArray(value)) { errors.push("socials : tableau attendu."); return []; }
  return value.map((item, index) => {
    const path = `socials[${index}]`;
    if (!record(item)) { errors.push(`${path} : objet attendu.`); return {}; }
    checkKeys(item, path, allowed.social);
    if (!platforms.has(item.platform)) errors.push(`${path}.platform : plateforme inconnue.`);
    const url = requiredUrl(item.url, `${path}.url`);
    const label = optionalString(item.label, `${path}.label`);
    return { platform: item.platform, url, ...(label && { label }) };
  });
}

function parseLinks(value) {
  if (!Array.isArray(value)) { errors.push("links : tableau obligatoire."); return []; }
  return value.map((item, index) => {
    const path = `links[${index}]`;
    if (!record(item)) { errors.push(`${path} : objet attendu.`); return {}; }
    checkKeys(item, path, allowed.link);
    const title = requiredString(item.title, `${path}.title`);
    const url = requiredUrl(item.url, `${path}.url`);
    const description = optionalString(item.description, `${path}.description`);
    const imageValue = item.image === undefined ? undefined : image(item.image, `${path}.image`);
    const icon = item.icon === undefined ? undefined : linkIcon(item.icon, `${path}.icon`);
    const featured = bool(item.featured, `${path}.featured`, false);
    const affiliate = bool(item.affiliate, `${path}.affiliate`, false);
    const expiresAt = parseExpiry(item.expiresAt, `${path}.expiresAt`);
    return { id: `link-${index}`, title, url, featured, affiliate, expiresAt, ...(description && { description }), ...(imageValue && { image: imageValue }), ...(icon && { icon }) };
  });
}

function checkKeys(value, path, keys) { for (const key of Object.keys(value)) if (!keys.has(key)) errors.push(`${path ? `${path}.` : ""}${key} : champ inconnu.`); }
function requiredString(value, path) { if (typeof value === "string" && value.trim()) return value.trim(); errors.push(`${path} : texte non vide obligatoire.`); return ""; }
function optionalString(value, path) { if (value === undefined) return undefined; if (typeof value === "string") return value.trim() || undefined; errors.push(`${path} : texte attendu.`); return undefined; }
function requiredUrl(value, path, protocols = ["http:", "https:", "mailto:", "tel:"]) { if (typeof value === "string") try { if (protocols.includes(new URL(value).protocol)) return value; } catch {} errors.push(`${path} : URL complète attendue.`); return ""; }
function image(value, path) { if (typeof value === "string" && value.startsWith("/") && !value.startsWith("//")) { if (!existsSync(resolve(root, "site", decodeURI(value).slice(1)))) errors.push(`${path} : fichier introuvable (${value}).`); return value; } return requiredUrl(value, path, ["http:", "https:"]); }
function bool(value, path, fallback) { if (value === undefined) return fallback; if (typeof value === "boolean") return value; errors.push(`${path} : true ou false attendu.`); return fallback; }
function linkIcon(value, path) { const icons = new Set(["youtube", "instagram", "tiktok", "discord", "mail", "website", "cart", "home"]); if (icons.has(value)) return value; errors.push(`${path} : icône inconnue.`); return undefined; }

function parseExpiry(value, path) {
  if (value === undefined || value === null) return null;
  if (typeof value !== "string") { errors.push(`${path} : date attendue.`); return null; }
  const input = value.trim();
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/.test(input)) { const instant = Date.parse(input); if (!Number.isNaN(instant)) return instant; }
  const date = /^(\d{4})-(\d{2})-(\d{2})$/.exec(input);
  const local = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})$/.exec(input);
  const parts = date ? [...date.slice(1), "00", "00"] : local?.slice(1);
  if (parts) {
    const [year, month, day, hour, minute] = parts.map(Number);
    const real = new Date(Date.UTC(year, month - 1, day, hour, minute));
    if (real.getUTCFullYear() === year && real.getUTCMonth() === month - 1 && real.getUTCDate() === day && real.getUTCHours() === hour && real.getUTCMinutes() === minute) {
      const next = date ? new Date(Date.UTC(year, month - 1, day + 1)) : null;
      return parisInstant(...(next ? [next.getUTCFullYear(), next.getUTCMonth() + 1, next.getUTCDate(), 0, 0] : [year, month, day, hour, minute]));
    }
  }
  errors.push(`${path} : date illisible. Utilise 2026-10-31 ou 2026-10-31T18:00.`); return null;
}
const formatter = new Intl.DateTimeFormat("en-US", { timeZone: "Europe/Paris", hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
function parisInstant(year, month, day, hour, minute) { const asUtc = Date.UTC(year, month - 1, day, hour, minute); const offset = (instant) => { const parts = Object.fromEntries(formatter.formatToParts(new Date(instant)).map((part) => [part.type, Number(part.value)])); return Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second) - Math.floor(instant / 1000) * 1000; }; return asUtc - offset(asUtc - offset(asUtc)); }
function record(value) { return typeof value === "object" && value !== null && !Array.isArray(value); }
function fail(messages) { console.error(`\n[links] ${messages.length} erreur(s) :\n${messages.map((message) => `  • ${message}`).join("\n")}\n`); process.exit(1); }
