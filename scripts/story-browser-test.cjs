// Full Story journey through the back-office, at desktop and mobile widths.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { spawn, execFileSync } = require('node:child_process');
const { mkdtempSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join, resolve } = require('node:path');

(async () => {
  const temp = mkdtempSync(join(tmpdir(), 'links-story-'));
  const database = join(temp, 'stats.db');
  const admin = 'http://127.0.0.1:8081';
  const publicOrigin = 'http://127.0.0.1:3003';
  execFileSync('python3',[resolve(__dirname,'fixtures.py'),database,publicOrigin]);
  const server = spawn('python3', [resolve(__dirname, 'analytics.py')], {
    env: { ...process.env, ANALYTICS_DB: database, UPLOAD_DIR: join(temp, 'uploads'), ANALYTICS_ORIGIN: publicOrigin },
    stdio: 'inherit'
  });
  const partner = require('node:http').createServer((request, response) => {response.writeHead(200, {'Content-Type':'text/html'});response.end('<h1>Partner destination</h1>')});
  await new Promise(r => partner.listen(18082, r));
  let browser;
  const api = async (path, data, method = 'POST') => {
    const response = await fetch(admin + path, { method, headers: { 'Content-Type': 'application/json','X-Links-Request':'1' }, body: data === undefined ? undefined : JSON.stringify(data) });
    assert(response.ok, `${path}: ${response.status} ${await (response.ok ? Promise.resolve('') : response.text())}`);
    return response.status === 204 ? null : response.json();
  };
  try {
    for (let i = 0; i < 100; i++) {
      try { if ((await fetch(admin + '/healthz')).ok) break; } catch {}
      await new Promise(r => setTimeout(r, 100));
      if (i === 99) throw Error('Backend did not start');
    }
    const promo = { type: 'promo', internal_name: 'Domadoo – Une promotion avec un nom très long pour vérifier le mobile', title: 'Offre publique', url: 'http://localhost:18082/offer?aff=117' };
    const { id } = await api('/api/content', promo);
    browser = await chromium.launch({ headless: true, ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox'] } : {}) });
    const context = await browser.newContext({ permissions: ['clipboard-read', 'clipboard-write'], userAgent: 'Mozilla/5.0 Links functional test' });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(admin);
    await page.locator('[data-tab="content"]').click();
    const copy = page.locator(`[data-id="${id}"] [data-action="copy-story"]`);
    await copy.click();
    await page.waitForFunction(() => document.getElementById('notice').textContent.startsWith('Lien partagé copié'));
    const link = await page.evaluate(() => navigator.clipboard.readText());
    assert.match(link, /\/go\/st_[A-Za-z0-9_-]{16}\?utm_source=instagram$/);
    await copy.click();
    await page.waitForFunction(() => !document.querySelector('[data-action="copy-story"]').disabled);
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), link);
    await page.goto(link);
    assert.equal(page.url(), promo.url);
    const token = new URL(link).pathname.split('/').at(-1);
    execFileSync('python3', ['-c', "import sqlite3,sys;from datetime import datetime,timedelta;from zoneinfo import ZoneInfo;db=sqlite3.connect(sys.argv[1]);day=(datetime.now(ZoneInfo('Europe/Paris'))-timedelta(days=20)).date().isoformat();db.execute('INSERT INTO counts VALUES(?,?,?,?,1)',(day,'instagram-story','story','story:'+sys.argv[2]+':09'));db.commit()", database, token]);
    execFileSync('python3', ['-c', "import sqlite3,sys;from datetime import datetime;from zoneinfo import ZoneInfo;db=sqlite3.connect(sys.argv[1]);day=datetime.now(ZoneInfo('Europe/Paris')).date().isoformat();db.executemany('INSERT INTO counts VALUES(?,?,?,?,?)',[(day,'youtube','view','',2),(day,'youtube','click','Amazon',1)]);db.commit()", database]);
    const stats = async expected => {
      await page.goto(admin);
      await page.waitForFunction(n => document.getElementById('story-clicks').textContent === String(n), expected);
      assert.equal(await page.locator('#views').textContent(), '2');
      assert.equal(await page.locator('#clicks').textContent(), '1');
      assert.equal(await page.locator('#ratio').textContent(), '50 %');
      assert.equal(await page.locator('#story-promos').textContent(), '1');
      assert((await page.locator('#story-list').textContent()).includes(promo.internal_name));
    };
    await stats(1);
    await page.selectOption('#period', '30');
    await page.waitForFunction(() => document.getElementById('story-clicks').textContent === '2');
    await page.selectOption('#source', 'youtube');
    await page.waitForFunction(() => document.getElementById('story-clicks').textContent === '0');
    await page.selectOption('#source', 'instagram');
    await page.waitForFunction(() => document.getElementById('story-clicks').textContent === '1');
    await page.selectOption('#source', 'instagram-story');
    await page.waitForFunction(() => document.getElementById('story-clicks').textContent === '1');
    for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      const boxes = await page.locator('.analytics-kpis article').evaluateAll(nodes => nodes.map(n => ({ x: n.getBoundingClientRect().x, y: n.getBoundingClientRect().y })));
      if (viewport.width > 760) assert(Math.abs(boxes[0].y - boxes[1].y) < 2);
      else assert(boxes[2].y > boxes[0].y);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Horizontal overflow');
    }
    promo.url = 'http://localhost:18082/new-offer?aff=117';
    promo.internal_name = 'Promotion renommée';
    await api('/api/content/' + id, promo, 'PUT');
    await page.goto(link);
    assert.equal(page.url(), promo.url);
    await stats(2);
    await api('/api/content/' + id + '/archive', {});
    await page.goto(link);
    assert.equal(page.url(), promo.url);
    await stats(3);
    await api('/api/content/' + id, undefined, 'DELETE');
    assert.equal((await fetch(link, { redirect: 'manual' })).status, 410);
    await stats(3);
    const second = await api('/api/content', { ...promo, internal_name: 'Deuxième campagne', url: 'http://localhost:18082/second' });
    const secondLink = await api('/api/content/' + second.id + '/story-link', {});
    await page.goto(secondLink.url);
    await page.goto(admin);
    await page.waitForFunction(() => document.getElementById('story-clicks').textContent === '4');
    assert.equal(await page.locator('#story-promos').textContent(), '2');
    const labels = await page.locator('#story-list .engagement-copy strong').allTextContents();
    assert.deepEqual(labels, ['Promotion renommée', 'Deuxième campagne']);
    assert.equal(errors.length, 0, errors.join('\n'));
    console.log('Story browser journey, clipboard, period/source filters, desktop/mobile, dynamic URL, archive and deletion: OK');
  } finally {
    if (browser) await browser.close();
    server.kill();
    await new Promise(r => server.exitCode !== null ? r() : server.once('exit', r));
    await new Promise(r => partner.close(r));
    rmSync(temp, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

