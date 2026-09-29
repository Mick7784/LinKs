import { createServer } from "node:http";

// Only these public fields may leave the server. Never forward the export itself.
export function publicVideo(data) {
  const v = data?.lastVideo;
  if (v === null) return null;
  if (!v || typeof v.title !== "string" || !v.title.trim()) throw new Error("Invalid video");
  const url = new URL(v.url);
  if (url.protocol !== "https:" || !["youtu.be", "www.youtube.com", "youtube.com"].includes(url.hostname)) throw new Error("Invalid URL");
  const published = new Date(v.publishedAt);
  if (!Number.isFinite(published.getTime())) throw new Error("Invalid date");
  let thumbnail;
  if (typeof v.thumbnail === "string") {
    const image = new URL(v.thumbnail);
    if (image.protocol === "https:" && image.hostname === "i.ytimg.com") thumbnail = image.href;
  }
  return { title: v.title, url: url.href, ...(thumbnail && { thumbnail }), published: published.toISOString() };
}

export function createVideoServer({ url = process.env.CREATOR_STUDIO_URL, key = process.env.CREATOR_STUDIO_API_KEY, fetcher = fetch } = {}) {
  return createServer(async (req, res) => {
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.setHeader("Cache-Control", "no-store");
    if (req.url !== "/latest-video.json") { res.writeHead(404).end("{}"); return; }
    if (req.method !== "GET") { res.setHeader("Allow", "GET"); res.writeHead(405).end("{}"); return; }
    if (!url || !key) { res.writeHead(503).end('{"error":"Video unavailable"}'); return; }
    try {
      const response = await fetcher(url, {
        headers: { Authorization: "Bearer " + key, Accept: "application/json" },
        redirect: "error",
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) throw new Error("Upstream unavailable");
      const video = publicVideo(await response.json());
      res.end(JSON.stringify(video));
    } catch {
      // Do not expose upstream bodies, credentials or private statistics.
      res.writeHead(502).end('{"error":"Video unavailable"}');
    }
  });
}
