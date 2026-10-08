// Server statis kecil untuk hasil build (dist/) dengan fallback SPA dan kompresi gzip.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const ROOT = path.resolve(import.meta.dirname, "dist");
const PORT = Number(process.env.PORT || 4173);
const HOST = process.env.HOST || "0.0.0.0";
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".geojson": "application/geo+json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".ico": "image/x-icon",
  ".csv": "text/csv; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".webmanifest": "application/manifest+json",
};
const COMPRESSIBLE = new Set([".html", ".js", ".css", ".json", ".geojson", ".svg", ".csv", ".txt"]);

function send(req, res, file, status = 200) {
  const ext = path.extname(file).toLowerCase();
  const headers = { "Content-Type": TYPES[ext] || "application/octet-stream", "X-Content-Type-Options": "nosniff" };
  headers["Cache-Control"] = file.includes(`${path.sep}assets${path.sep}`) ? "public, max-age=31536000, immutable" : ext === ".html" ? "no-cache" : "public, max-age=3600";
  const gz = COMPRESSIBLE.has(ext) && /\bgzip\b/.test(req.headers["accept-encoding"] || "");
  if (gz) {
    headers["Content-Encoding"] = "gzip";
    headers["Vary"] = "Accept-Encoding";
  }
  res.writeHead(status, headers);
  if (req.method === "HEAD") return res.end();
  const stream = fs.createReadStream(file);
  (gz ? stream.pipe(zlib.createGzip({ level: 6 })) : stream).pipe(res);
}

http
  .createServer((req, res) => {
    try {
      const url = new URL(req.url || "/", "http://x");
      const rel = decodeURIComponent(url.pathname);
      const file = path.normalize(path.join(ROOT, rel));
      if (!file.startsWith(ROOT)) {
        res.writeHead(403).end();
        return;
      }
      if (fs.existsSync(file) && fs.statSync(file).isFile()) return send(req, res, file);
      // berkas data/aset yang tidak ada → 404 sungguhan (mis. ubin jalan di luar cakupan)
      if (rel.startsWith("/data/") || rel.startsWith("/assets/") || path.extname(rel)) {
        res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" }).end("404");
        return;
      }
      return send(req, res, path.join(ROOT, "index.html"));
    } catch (e) {
      res.writeHead(500).end(String(e));
    }
  })
  .listen(PORT, HOST, () => console.log(`Peta Semarang: http://${HOST}:${PORT}`));
