// Salin index.html ke tiap rute + 404.html agar tautan langsung (deep link) jalan di hosting statis (GitHub Pages).
import fs from "node:fs";
import path from "node:path";
const dist = path.resolve(import.meta.dirname, "../dist");
const html = fs.readFileSync(path.join(dist, "index.html"));
for (const r of ["metodologi", "tentang", "data-zona", "data-editor"]) {
  fs.mkdirSync(path.join(dist, r), { recursive: true });
  fs.writeFileSync(path.join(dist, r, "index.html"), html);
}
fs.writeFileSync(path.join(dist, "404.html"), html);
fs.writeFileSync(path.join(dist, ".nojekyll"), "");
console.log("postbuild: rute statis + 404.html + .nojekyll");
