"""Interactive portrait-strip page (tenchi/output/strips.html): pick one 48x8 strip per row and a colour 3,
see the face and which generals use the same strips. All graphics come from the ROM and are embedded."""
import json
import os

from rom import PORTRAIT_COLOR, PORTRAIT_FIXED, GameRom, nes_rgb


def page_data(r: GameRom) -> dict:
    strips = {}
    for v in range(256):
        tiles = r.portrait_tiles([v])
        strips[v] = "".join(str(tiles[i // 8 % 6][(i // 48) * 8 + i % 8]) for i in range(384))
    gens, rows = [], [set() for _ in range(6)]
    for g in r.generals():
        if not g["color"]:
            continue
        for k, v in enumerate(g["portrait"]):
            rows[k].add(v)
        kanji = []
        for code, bank in g["kanji"]:
            bits = "".join(map(str, r.kanji_glyph(code, bank)))
            kanji.append(f"{int(bits, 2):064x}")
        gens.append({"id": g["id"], "name": g["name"], "p": g["portrait"], "c": g["color"], "k": kanji})
    def hexrgb(c: int) -> str:
        return "#" + "".join(f"{x:02x}" for x in nes_rgb(c))
    return {"fixed": [hexrgb(c) for c in PORTRAIT_FIXED], "colors": [hexrgb(c) for c in PORTRAIT_COLOR],
            "strips": [strips[v] for v in range(256)], "rows": [sorted(s) for s in rows], "generals": gens}


def write(r: GameRom, out: str) -> str:
    path = os.path.join(out, "strips.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(TEMPLATE.replace("/*DATA*/null", json.dumps(page_data(r), ensure_ascii=False, separators=(",", ":"))))
    return path


TEMPLATE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>天地を喰らう頭像拼貼</title>
<style>
:root { --bg: #f6f5f2; --fg: #222; --muted: #666; --card: #fff; --line: #ddd; --accent: #c0392b; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #1d1d1f; --fg: #eee; --muted: #9a9a9a; --card: #2a2a2d; --line: #3a3a3e; --accent: #ff7a6b; }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 16px; background: var(--bg); color: var(--fg);
  font: 14px/1.5 -apple-system, "Hiragino Sans", "Noto Sans CJK TC", sans-serif; }
h1 { font-size: 20px; margin: 0 0 4px; }
p.note { color: var(--muted); margin: 0 0 16px; max-width: 60em; }
.top { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
.face { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 12px; }
canvas { image-rendering: pixelated; display: block; }
#face { width: 288px; height: 288px; background: #000; }
#kanji { height: 32px; margin-top: 8px; background: #000; }
.controls { flex: 1; min-width: 260px; display: flex; flex-direction: column; gap: 10px; }
select, button { font: inherit; padding: 4px 8px; border-radius: 6px; border: 1px solid var(--line);
  background: var(--card); color: var(--fg); }
.swatches { display: flex; gap: 6px; flex-wrap: wrap; }
.sw { width: 28px; height: 28px; border-radius: 6px; border: 2px solid var(--line); cursor: pointer; }
.sw.on { border-color: var(--accent); }
#match { color: var(--muted); }
#match b { color: var(--fg); }
.row { margin-top: 14px; }
.row h2 { font-size: 14px; margin: 0 0 6px; }
.row h2 span { color: var(--muted); font-weight: normal; }
.picks { display: flex; flex-wrap: wrap; gap: 4px; padding-bottom: 6px; }
.pick { flex: none; border: 2px solid transparent; border-radius: 4px; cursor: pointer; padding: 1px; }
.pick.on { border-color: var(--accent); }
.pick canvas { width: 96px; height: 16px; }
.users { color: var(--muted); font-size: 12px; min-height: 1.5em; }
label { color: var(--muted); }
</style>
</head>
<body>
<h1>天地を喰らう 頭像拼貼</h1>
<p class="note">每張頭像是 6 條 48×8 的橫條，加上第 4 色的配色（9 種）。每列從遊戲在該位置用過的橫條中挑一條；
勾選「不限位置」可改從全部 256 條挑。資料與圖形都直接取自 ROM。</p>
<div class="top">
  <div class="face"><canvas id="face" width="48" height="48"></canvas><canvas id="kanji" width="48" height="16"></canvas></div>
  <div class="controls">
    <div><label>載入武將　</label><select id="gen"></select></div>
    <div class="swatches" id="colors"></div>
    <div><button id="rand">隨機拼一張</button>　<label><input type="checkbox" id="all"> 不限位置</label></div>
    <div id="match"></div>
  </div>
</div>
<div id="rows"></div>
<script>
const D = /*DATA*/null;
const cur = { p: D.generals[0].p.slice(), c: D.generals[0].c, g: D.generals[0].id };
const pal = c => [...D.fixed, D.colors[c]];
const rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));

function drawStrip(ctx, v, c, y) {
  const img = ctx.createImageData(48, 8), P = pal(c).map(rgb), s = D.strips[v];
  for (let i = 0; i < 384; i++) { const q = P[+s[i]]; img.data.set([q[0], q[1], q[2], 255], i * 4); }
  ctx.putImageData(img, 0, y);
}
function users(k, v) { return D.generals.filter(g => g.p[k] === v); }
function names(gs) {
  const by = new Map();
  for (const g of gs) { if (!by.has(g.name)) by.set(g.name, []); by.get(g.name).push(g.id); }
  return [...by].map(([n, ids]) => `${n}(${ids.join(",")})`).join("、");
}
function drawKanji(g) {
  const cv = document.getElementById("kanji"), n = g ? g.k.length : 0;
  cv.width = Math.max(16, n * 16); cv.style.width = cv.width * 2 + "px"; cv.style.height = "32px";
  const ctx = cv.getContext("2d"); ctx.fillStyle = "#000"; ctx.fillRect(0, 0, cv.width, 16);
  ctx.fillStyle = "#fff";
  if (g) g.k.forEach((h, j) => {
    const bits = BigInt("0x" + h).toString(2).padStart(256, "0");
    for (let i = 0; i < 256; i++) if (bits[i] === "1") ctx.fillRect(j * 16 + i % 16, i >> 4, 1, 1);
  });
}
function render() {
  const ctx = document.getElementById("face").getContext("2d");
  cur.p.forEach((v, k) => drawStrip(ctx, v, cur.c, k * 8));
  const same = D.generals.filter(g => g.p.every((v, k) => v === cur.p[k]));
  const exact = same.filter(g => g.c === cur.c);
  drawKanji(exact.find(g => g.id === cur.g) || exact[0] || null);
  document.getElementById("match").innerHTML =
    (exact.length ? `完全相同：<b>${names(exact)}</b>` : "沒有武將用這個組合＋配色")
    + (same.length > exact.length ? `<br>同樣橫條、不同配色：${names(same.filter(g => g.c !== cur.c))}` : "")
    + `<br>橫條：${cur.p.map(v => v.toString(16).toUpperCase().padStart(2, "0")).join(" ")}　配色 ${cur.c}`;
  document.querySelectorAll(".sw").forEach((e, i) => e.classList.toggle("on", i + 1 === cur.c));
  document.querySelectorAll(".row").forEach((row, k) => {
    row.querySelectorAll(".pick").forEach(e => e.classList.toggle("on", +e.dataset.v === cur.p[k]));
    row.querySelector(".users").textContent = "用這條的：" + (names(users(k, cur.p[k])) || "（無）");
    row.querySelectorAll(".pick canvas").forEach(cv => drawStrip(cv.getContext("2d"), +cv.parentNode.dataset.v, cur.c, 0));
  });
}
function buildRows() {
  const all = document.getElementById("all").checked, box = document.getElementById("rows");
  box.innerHTML = "";
  for (let k = 0; k < 6; k++) {
    const list = all ? [...Array(256).keys()] : D.rows[k];
    const row = document.createElement("div"); row.className = "row";
    row.innerHTML = `<h2>第 ${k + 1} 條 <span>（y ${k * 8}–${k * 8 + 7}，${list.length} 種）</span></h2>`
      + `<div class="picks"></div><div class="users"></div>`;
    const picks = row.querySelector(".picks");
    for (const v of list) {
      const b = document.createElement("div"); b.className = "pick"; b.dataset.v = v;
      b.title = v.toString(16).toUpperCase().padStart(2, "0") + "：" + (names(users(k, v)) || "此位置沒人用");
      const cv = document.createElement("canvas"); cv.width = 48; cv.height = 8; b.appendChild(cv);
      b.onclick = () => { cur.p[k] = v; render(); };
      picks.appendChild(b);
    }
    box.appendChild(row);
  }
  render();
}
const sel = document.getElementById("gen");
for (const g of D.generals) sel.add(new Option(`${g.id} ${g.name}`, g.id));
sel.onchange = () => { const g = D.generals.find(g => g.id === +sel.value); cur.p = g.p.slice(); cur.c = g.c; cur.g = g.id; render(); };
D.colors.forEach((h, i) => {
  if (!i) return;
  const e = document.createElement("div"); e.className = "sw"; e.style.background = h; e.title = "配色 " + i;
  e.onclick = () => { cur.c = i; render(); };
  document.getElementById("colors").appendChild(e);
});
document.getElementById("rand").onclick = () => {
  const all = document.getElementById("all").checked;
  cur.p = cur.p.map((_, k) => { const l = all ? [...Array(256).keys()] : D.rows[k]; return l[Math.random() * l.length | 0]; });
  cur.c = 1 + (Math.random() * 9 | 0); render();
};
document.getElementById("all").onchange = buildRows;
buildRows();
</script>
</body>
</html>
"""
