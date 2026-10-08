// Polite Lamudi scraper: listing pages of "Tanah dijual di Semarang" (Kota + Kab, filtered later).
import { chromium } from 'playwright-core';
import fs from 'fs';
import zlib from 'zlib';
const base = process.argv[2] || 'https://www.lamudi.co.id/jual/jawa-tengah/semarang/tanah/';
const tag = process.argv[3] || 'semarang';
const maxPages = Number(process.argv[4] || 80);
const outDir = `raw/lamudi/${tag}`; fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', headless: false, args: ['--no-sandbox'] });
const ctx = await browser.newContext({ locale: 'id-ID', viewport: { width: 1366, height: 900 } });
const page = await ctx.newPage();
let total = null;
for (let n = 1; n <= maxPages; n++) {
  const f = `${outDir}/page-${String(n).padStart(3, '0')}.html.gz`;
  if (fs.existsSync(f)) continue;
  const url = n === 1 ? base : `${base}?page=${n}`;
  let ok = false;
  for (let attempt = 0; attempt < 3 && !ok; attempt++) {
    try {
      const r = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForTimeout(2500);
      const html = await page.content();
      const m = html.match(/Halaman\s+(\d+)\s+dari\s+(\d+)/);
      if (m) total = Number(m[2]);
      const cnt = (html.match(/data-idanuncio=/g) || []).length;
      console.log(new Date().toISOString(), tag, n, r?.status(), 'cards', cnt, 'of pages', total);
      if (r?.status() === 200 && cnt > 0) { fs.writeFileSync(f, zlib.gzipSync(html)); ok = true; }
      else { const t = await page.title(); console.log('no cards; title=', t); if (/verification|moment|Tunggu/i.test(t)) { await browser.close(); process.exit(3); } if (/tidak ditemukan|no results/i.test(html) && total && n > total) { ok = true; n = 1e9; } else await page.waitForTimeout(60000 * (attempt + 1)); }
    } catch (e) { console.log('ERR', n, e.message.slice(0, 120)); await page.waitForTimeout(10000); }
  }
  if (total && n >= total) break;
  await page.waitForTimeout(3000 + Math.random() * 3000);
}
await browser.close();
