import { test } from "node:test";
import assert from "node:assert/strict";
import { createVideoServer } from "./video-api.mjs";

test("runtime projection, fresh data, authentication and failure isolation", async () => {
  let title = "First";
  let fail = false;
  const server = createVideoServer({
    url: "http://creator-studio-api:3001/api/export/youtube", key: "private-key",
    fetcher: async (url, options) => {
      assert.equal(options.headers.Authorization, "Bearer private-key");
      assert.equal(options.redirect, "error");
      if (fail) throw new Error("private-key income=9000");
      return { ok: true, json: async () => ({
        thisMonth: { estimatedRevenue: 9000 },
        lastVideo: { title, url: "https://youtu.be/KzfhhIf_x_Q", thumbnail: "https://i.ytimg.com/vi/KzfhhIf_x_Q/hqdefault.jpg", publishedAt: "2026-09-24T12:00:00Z", stats: { private: true } }
      }) };
    }
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const endpoint = "http://127.0.0.1:" + server.address().port + "/latest-video.json";
  try {
    const first = await fetch(endpoint);
    assert.equal(first.headers.get("cache-control"), "no-store");
    const data = await first.json();
    assert.deepEqual(Object.keys(data).sort(), ["published", "thumbnail", "title", "url"]);
    assert.equal(data.title, "First");
    title = "Second";
    assert.equal((await (await fetch(endpoint)).json()).title, "Second");
    fail = true;
    const failure = await fetch(endpoint);
    assert.equal(failure.status, 502);
    assert.equal(await failure.text(), '{"error":"Video unavailable"}');
    assert.equal((await fetch(endpoint, { method: "POST" })).status, 405);
  } finally { await new Promise(resolve => server.close(resolve)); }
});

test("missing credentials never contacts upstream", async () => {
  const server = createVideoServer({ url: "http://example.invalid", key: "", fetcher: () => assert.fail() });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  try { assert.equal((await fetch("http://127.0.0.1:" + server.address().port + "/latest-video.json")).status, 503); }
  finally { await new Promise(resolve => server.close(resolve)); }
});
