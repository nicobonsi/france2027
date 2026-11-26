// France 2027 — the map. Plain ES module, no build step: reads the JSON produced by pipeline/build.py.
import { rampColor, RAMPS, MISSING_FILL, textOn } from "./color.js";
import { fmt } from "./format.js";

const $ = (s) => document.querySelector(s);
const SVG = "http://www.w3.org/2000/svg";
const el = (tag, attrs = {}, parent) => {
  const n = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

async function load(name) {
  const r = await fetch(`data/${name}.json`);
  if (!r.ok) throw new Error(`data/${name}.json : HTTP ${r.status}`);
  return r.json();
}

const state = { lens: null, selected: null, hover: null };
let geo, data, lenses, sources, nation, lensById, shapes = new Map(), tileEls = new Map(); // shapes: code → [elements]
const addShape = (code, n) => { if (!shapes.has(code)) shapes.set(code, []); shapes.get(code).push(n); };

// ------------------------------------------------------------------------------------------------
// Colour scales
// ------------------------------------------------------------------------------------------------
function domainFor(lens) {
  const vals = Object.values(data.territories).map((t) => t.values[lens.id]).filter((v) => v != null && Number.isFinite(v));
  vals.sort((a, b) => a - b);
  if (!vals.length) return null;
  // Trim the extreme 2% so one outlier (Paris density, Guyane unemployment) doesn't flatten the map.
  const q = (p) => vals[Math.min(vals.length - 1, Math.max(0, Math.round(p * (vals.length - 1))))];
  let lo = q(0.02), hi = q(0.98);
  if (lens.scale === "diverging") { const m = Math.max(Math.abs(lo), Math.abs(hi)); lo = -m; hi = m; }
  if (lens.scale === "log") { lo = Math.max(lo, 0.01); }
  return { lo, hi, min: vals[0], max: vals[vals.length - 1] };
}

function colourFor(lens, dom, v) {
  if (lens.scale === "categorical") return v == null ? MISSING_FILL : lens.colors[v] || "#8a8f98";
  if (v == null || !dom) return MISSING_FILL;
  let t;
  if (lens.scale === "log") t = (Math.log(Math.max(v, dom.lo)) - Math.log(dom.lo)) / (Math.log(dom.hi) - Math.log(dom.lo));
  else t = (v - dom.lo) / (dom.hi - dom.lo || 1);
  return rampColor(RAMPS[lens.ramp] || RAMPS.teal, Math.max(0, Math.min(1, t)));
}

// ------------------------------------------------------------------------------------------------
// Map drawing
// ------------------------------------------------------------------------------------------------
const svg = $("#map");
let view; // current viewBox [x, y, w, h]

function drawMap() {
  const [x0, y0, W, H] = geo.viewBox;
  const defs = el("defs", {}, svg);
  const pat = el("pattern", { id: "hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
  el("rect", { width: 6, height: 6, fill: "#2b3542" }, pat);
  el("rect", { width: 2, height: 6, fill: "#46546a" }, pat);

  const gInsets = el("g", { class: "insets" }, svg);
  for (const b of geo.insets) {
    const [bx, by, bw, bh] = b.box;
    el("rect", { class: "inset-box", x: bx, y: by, width: bw, height: bh, rx: 8 }, gInsets);
    el("text", { class: "inset-cap", x: bx + 10, y: by + 20 }, gInsets).textContent = b.name;
    const sx = bx + bw - 12 - b.scale_len, sy = by + bh - 12;
    el("path", { class: "scale", d: `M${sx} ${sy - 3}V${sy}H${sx + b.scale_len}V${sy - 3}`, fill: "none" }, gInsets);
    el("text", { class: "scale-txt", x: sx + b.scale_len, y: sy - 5, "text-anchor": "end" }, gInsets).textContent = `${b.scale_km} km`;
  }
  const ms = geo.metro_scale;
  el("path", { class: "scale", d: `M${ms.at[0]} ${ms.at[1] - 4}V${ms.at[1]}H${ms.at[0] + ms.len}V${ms.at[1] - 4}`, fill: "none" }, svg);
  el("text", { class: "scale-txt", x: ms.at[0] + ms.len, y: ms.at[1] - 6, "text-anchor": "end" }, svg).textContent = `${ms.km} km`;
  el("text", { class: "note-txt", x: 20, y: H - 4 }, svg).textContent = "Outre-mer : échelles différentes de la métropole. Collectivités sans contour IGN représentées par des tuiles.";

  const gTerr = el("g", { class: "territories" }, svg);
  for (const f of geo.features) {
    const p = el("path", { class: "terr", d: f.path, "data-code": f.code, fill: MISSING_FILL }, gTerr);
    if (f.inset) p.dataset.inset = f.inset;
    addShape(f.code, p);
  }
  const gReg = el("g", {}, svg);
  for (const r of geo.regions) el("path", { class: "region", d: r.path }, gReg);

  const gCap = el("g", { class: "capitals" }, svg);
  for (const f of geo.features) {
    if (!f.capital_xy || f.inset) continue;
    el("circle", { class: "capital", cx: f.capital_xy[0], cy: f.capital_xy[1], r: 1.8 }, gCap);
  }

  const gTiles = el("g", { class: "tiles" }, svg);
  for (const t of geo.tiles) {
    const [x, y, w, h] = t.box;
    const g = el("g", { class: "tile" }, gTiles);
    const r = el("rect", { class: "terr", x, y, width: w, height: h, rx: 8, "data-code": t.code, fill: MISSING_FILL }, g);
    const name = el("text", { class: "tile-name", x: x + 10, y: y + 20 }, g);
    name.textContent = t.name.replace("Saint-Martin / Saint-Barthélemy", "St-Martin / St-Barth").replace("Français établis hors de France", "Français de l'étranger");
    const val = el("text", { class: "tile-val", x: x + 10, y: y + h - 14 }, g);
    addShape(t.code, r);
    tileEls.set(t.code, { g, val });
  }

  view = [x0, y0, W, H];
  fitHome();
}

function setView(v) {
  view = v;
  svg.setAttribute("viewBox", v.map((n) => n.toFixed(2)).join(" "));
  const k = geo.viewBox[2] / v[2];
  svg.querySelector(".capitals").style.display = k > 2.2 ? "" : "none";
}

// Fit the whole drawing into the part of the screen not covered by the sidebar (desktop) or the bottom sheet (mobile).
function fitHome() {
  const [x0, y0, W, H] = geo.viewBox;
  const r = svg.getBoundingClientRect();
  const sb = $("#sidebar").getBoundingClientRect();
  const mobile = innerWidth <= 760;
  const area = mobile
    ? { l: 6, t: 6, w: r.width - 12, h: sb.top - r.top - 12 }
    : { l: sb.right - r.left + 8, t: 8, w: r.width - (sb.right - r.left) - 64, h: r.height - 16 };
  const s = Math.min(area.w / W, area.h / H);
  const vw = r.width / s, vh = r.height / s;
  setView([x0 - area.l / s - (area.w / s - W) / 2, y0 - area.t / s - (area.h / s - H) / 2, vw, vh]);
}

function zoomAt(factor, cx, cy) {
  const [x, y, w, h] = view;
  const nw = Math.min(geo.viewBox[2] * 2, Math.max(geo.viewBox[2] / 40, w / factor));
  const f = nw / w;
  const nh = h * f;
  setView([cx - (cx - x) * f, cy - (cy - y) * f, nw, nh]);
}

function clientToSvg(ex, ey) {
  const r = svg.getBoundingClientRect();
  return [view[0] + ((ex - r.left) / r.width) * view[2], view[1] + ((ey - r.top) / r.height) * view[3]];
}

function bindPanZoom() {
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const [cx, cy] = clientToSvg(e.clientX, e.clientY);
    zoomAt(Math.exp(-e.deltaY * (e.deltaMode ? 0.05 : 0.0016)), cx, cy);
  }, { passive: false });

  const pts = new Map();
  let drag = null, pinch = null, moved = false, downCode = null;
  svg.addEventListener("pointerdown", (e) => {
    downCode = e.target?.dataset?.code || null; // read before capture retargets later events to the <svg>
    svg.setPointerCapture(e.pointerId);
    pts.set(e.pointerId, [e.clientX, e.clientY]);
    moved = false;
    if (pts.size === 1) drag = { x: e.clientX, y: e.clientY, v: [...view] };
    if (pts.size === 2) {
      const [a, b] = [...pts.values()];
      pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), v: [...view], c: clientToSvg((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) };
      drag = null;
    }
  });
  svg.addEventListener("pointermove", (e) => {
    if (!pts.has(e.pointerId)) return onHover(e);
    pts.set(e.pointerId, [e.clientX, e.clientY]);
    const r = svg.getBoundingClientRect();
    if (drag) {
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) { moved = true; svg.classList.add("dragging"); hideTooltip(); }
      if (moved) setView([drag.v[0] - (dx / r.width) * drag.v[2], drag.v[1] - (dy / r.height) * drag.v[3], drag.v[2], drag.v[3]]);
    } else if (pinch && pts.size === 2) {
      moved = true;
      const [a, b] = [...pts.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      view = [...pinch.v];
      zoomAt(d / pinch.d, pinch.c[0], pinch.c[1]);
    }
  });
  const end = (e) => {
    pts.delete(e.pointerId);
    svg.classList.remove("dragging");
    if (pts.size < 2) pinch = null;
    if (pts.size === 0) {
      if (!moved && e.type === "pointerup") select(downCode);
      drag = null;
    }
  };
  svg.addEventListener("pointerup", end);
  svg.addEventListener("pointercancel", end);
  svg.addEventListener("pointerleave", hideTooltip);
  svg.addEventListener("dblclick", (e) => { const [cx, cy] = clientToSvg(e.clientX, e.clientY); zoomAt(2, cx, cy); });

  $("#zoom").addEventListener("click", (e) => {
    const z = e.target.closest("button")?.dataset.zoom;
    const cx = view[0] + view[2] / 2, cy = view[1] + view[3] / 2;
    if (z === "in") zoomAt(1.6, cx, cy);
    if (z === "out") zoomAt(1 / 1.6, cx, cy);
    if (z === "reset") fitHome();
  });
  addEventListener("resize", () => fitHome());
}

// ------------------------------------------------------------------------------------------------
// Lenses
// ------------------------------------------------------------------------------------------------
function applyLens(id) {
  const lens = lensById.get(id) || lenses[0];
  state.lens = lens;
  const dom = domainFor(lens);
  for (const [code, nodes] of shapes) {
    const v = data.territories[code]?.values[lens.id];
    const c = colourFor(lens, dom, v);
    for (const node of nodes) node.setAttribute("fill", v == null ? "url(#hatch)" : c);
    const tile = tileEls.get(code);
    if (tile) {
      tile.val.textContent = v == null ? "non publié"
        : lens.scale === "categorical" ? String(v).split(" ").slice(1).join(" ") : formatValue(lens, v, true);
      tile.g.classList.toggle("dark", v != null && textOn(c) === "#f4efe2");
      if (v == null) tile.g.classList.add("dark");
    }
  }
  for (const b of document.querySelectorAll(".lens-btn")) b.setAttribute("aria-pressed", String(b.dataset.lens === lens.id));
  for (const c of document.querySelectorAll(".chip")) c.classList.toggle("on", c.dataset.lens === lens.id);
  drawLegend(lens, dom);
  if (state.selected) openPanel(state.selected);
  writeHash();
}

function formatValue(lens, v, short = false) {
  if (v == null) return "non publié";
  if (lens.scale === "categorical") return String(v);
  const s = fmt(v, lens.fmt);
  const unitInFormat = /^(pct|pts|eur)/.test(lens.fmt || ""); // fmt() already prints %, pts or €
  return short || !lens.unit || unitInFormat ? s : `${s} ${lens.unit}`;
}

function drawLegend(lens, dom) {
  const src = sources.find((s) => s.id === lens.source);
  let body = "";
  if (lens.scale === "categorical") {
    const seen = new Set(Object.values(data.territories).map((t) => t.values[lens.id]).filter(Boolean));
    body = `<div class="cats">${[...seen].map((k) => `<div><span class="sw" style="background:${lens.colors[k] || "#8a8f98"}"></span>${esc(k)}</div>`).join("")}</div>`;
  } else if (dom) {
    const ramp = RAMPS[lens.ramp] || RAMPS.teal;
    const stops = ramp.map((c, i) => `${c} ${(i / (ramp.length - 1)) * 100}%`).join(",");
    const mid = lens.scale === "log" ? Math.sqrt(dom.lo * dom.hi) : (dom.lo + dom.hi) / 2;
    body = `<div class="bar" style="background:linear-gradient(90deg,${stops})"></div>
      <div class="ticks"><span>${lens.scale === "diverging" ? "" : "≤ "}${fmt(dom.lo, lens.fmt)}</span><span>${fmt(mid, lens.fmt)}</span><span>${lens.scale === "diverging" ? "" : "≥ "}${fmt(dom.hi, lens.fmt)}</span></div>`;
  }
  const missing = Object.values(data.territories).filter((t) => t.values[lens.id] == null).map((t) => t.name);
  $("#legend").innerHTML = `
    <h3>${esc(lens.label)}${lens.unit ? ` <small style="color:var(--ink-3);font-weight:400">(${esc(lens.unit)})</small>` : ""}</h3>
    <div class="meta">${esc(lens.year)} · ${esc(src?.publisher || "")}${lens.higher_is ? ` · plus haut = ${lens.higher_is === "good" ? "mieux" : "moins bien"}` : ""}</div>
    ${body}
    ${missing.length ? `<div class="miss"><span class="sw"></span>Non publié (${missing.length}) : ${esc(missing.slice(0, 7).join(", "))}${missing.length > 7 ? "…" : ""}</div>` : ""}`;
}

function buildDock() {
  const groups = new Map();
  for (const l of lenses) { if (!groups.has(l.group)) groups.set(l.group, []); groups.get(l.group).push(l); }
  $("#lens-dock").innerHTML = [...groups].map(([g, ls]) => `
    <div class="lens-group" role="group" aria-label="${esc(g)}"><span>${esc(g)}</span>
      ${ls.map((l) => `<button class="lens-btn" data-lens="${l.id}" aria-pressed="false" title="${esc(l.description)}">${esc(l.short || l.label)}</button>`).join("")}
    </div>`).join("");
  $("#lens-dock").addEventListener("click", (e) => {
    const b = e.target.closest(".lens-btn");
    if (b) applyLens(b.dataset.lens);
  });
}

function buildHeadline() {
  $("#headline").innerHTML = nation.headline.map((h) => `
    <div class="chip" data-lens="${h.id}" title="${esc(h.note)}" role="button" tabindex="0"><b>${fmt(h.value, h.fmt)}</b><span>${esc(h.label)}</span></div>`).join("");
  $("#headline").addEventListener("click", (e) => { const c = e.target.closest(".chip"); if (c) applyLens(c.dataset.lens); });
}

// ------------------------------------------------------------------------------------------------
// Tooltip & panel
// ------------------------------------------------------------------------------------------------
const tip = $("#tooltip");
function onHover(e) {
  const code = e.target?.dataset?.code;
  if (!code) return hideTooltip();
  const t = data.territories[code];
  const v = t.values[state.lens.id];
  tip.innerHTML = `<b>${esc(t.name)}</b>${/^\d|^2[AB]/.test(code) ? ` <span class="muted">(${esc(code)})</span>` : ""}<br>
    ${esc(state.lens.label)} : ${v == null ? '<span class="muted">non publié</span>' : esc(formatValue(state.lens, v))}`;
  tip.hidden = false;
  const r = tip.getBoundingClientRect();
  let x = e.clientX + 14, y = e.clientY + 14;
  if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
  if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14;
  tip.style.left = `${x}px`; tip.style.top = `${y}px`;
}
function hideTooltip() { tip.hidden = true; }

function nationalValue(id) { return nation.headline.find((h) => h.id === id)?.value; }

function rank(lensId, code) {
  const arr = Object.entries(data.territories).filter(([, t]) => t.values[lensId] != null && (t.kind === "dep" || t.kind === "drom"));
  arr.sort((a, b) => b[1].values[lensId] - a[1].values[lensId]);
  const i = arr.findIndex(([c]) => c === code);
  return i < 0 ? null : [i + 1, arr.length];
}

function openPanel(code) {
  const t = data.territories[code];
  if (!t) return;
  const kindLabel = { dep: "Département", drom: "Département et région d'outre-mer", com: "Collectivité d'outre-mer", abroad: "Circonscriptions consulaires" }[t.kind];
  const groups = new Map();
  for (const l of lenses) {
    if (l.group === "Présidentielle 2022") continue;
    if (!groups.has(l.group)) groups.set(l.group, []);
    groups.get(l.group).push(l);
  }
  const rows = [...groups].map(([g, ls]) => `<h4>${esc(g)}</h4><table>${ls.map((l) => {
    const v = t.values[l.id];
    const nat = nationalValue(l.id);
    const rk = v != null && l.scale !== "categorical" ? rank(l.id, code) : null;
    return `<tr class="clickable ${state.lens.id === l.id ? "cur" : ""}" data-lens="${l.id}"><td>${esc(l.label)}</td>
      <td class="v">${v == null ? '<span class="na">non publié</span>' : esc(formatValue(l, v))}</td>
      <td class="n">${rk ? `${rk[0]}<sup>e</sup>/${rk[1]}` : ""}${nat != null && v != null ? `<br>France ${fmt(nat, l.fmt)}` : ""}</td></tr>`;
  }).join("")}</table>`).join("");

  const res = t.p22 ? `<h4>Présidentielle 2022 — 1er tour</h4>
    <div class="sub">${fmt(t.p22.inscrits, "int")} inscrits · abstention ${fmt(t.values.p22_abstention, "pct1")}</div>
    <div class="res">${t.p22.results.slice(0, 8).map(([n, p]) => `<span>${esc(n)}</span><div><div class="b" style="width:${(p / t.p22.results[0][1]) * 100}%;background:${lensById.get("p22_winner").colors[n] || "#8a8f98"}"></div></div><span class="p">${fmt(p, "pct1")}</span>`).join("")}</div>` : "";

  const missing = lenses.filter((l) => t.values[l.id] == null).map((l) => l.label);
  $("#panel").innerHTML = `<button class="close" data-close aria-label="Fermer">✕</button>
    <h2>${esc(t.name)}</h2>
    <div class="sub">${esc(kindLabel)}${/^\d|^2[AB]/.test(code) ? ` · ${esc(code)}` : ""}${t.region_name && t.kind === "dep" ? ` · ${esc(t.region_name)}` : ""}${t.capital ? ` · préfecture : ${esc(t.capital)}` : ""}${t.status ? `<br>${esc(t.status)}` : ""}</div>
    ${t.kind === "abroad" || t.kind === "com" ? "" : rows}
    ${res}
    ${t.kind === "com" ? `<div class="note">Aucun indicateur Insee : les collectivités d'outre-mer ont leurs propres instituts statistiques (ISEE en Nouvelle-Calédonie, ISPF en Polynésie, etc.) et souvent leur propre fiscalité. Seuls les résultats électoraux nationaux sont disponibles ici pour l'instant.</div>` : ""}
    ${missing.length && (t.kind === "dep" || t.kind === "drom") ? `<div class="note"><b>Non publié pour ce territoire :</b> ${esc(missing.join(", "))}.
      Voir l'Almanach pour la couverture de chaque source.</div>` : ""}`;
  $("#panel").hidden = false;
}

function select(code) {
  for (const s of shapes.get(state.selected) || []) s.classList.remove("sel");
  state.selected = code && data.territories[code] ? code : null;
  if (state.selected) {
    for (const s of shapes.get(state.selected) || []) {
      s.classList.add("sel");
      if (!s.closest(".tile")) s.parentNode.appendChild(s); // draw the outline above its neighbours
    }
    openPanel(state.selected);
  } else {
    $("#panel").hidden = true;
  }
  writeHash();
}

// Zoom so the territory sits in the middle of the area left free by the sidebar and the side panel.
function zoomTo(code) {
  const s = (shapes.get(code) || []).find((n) => !n.dataset.inset);
  if (!s) return;
  const b = s.getBBox();
  const r = svg.getBoundingClientRect();
  const mobile = innerWidth <= 760;
  const left = mobile ? 0 : $("#sidebar").getBoundingClientRect().right - r.left;
  const panel = $("#panel");
  const right = mobile || panel.hidden ? r.width - 56 : panel.getBoundingClientRect().left - r.left;
  const bottom = mobile ? Math.min($("#sidebar").getBoundingClientRect().top, panel.hidden ? innerHeight : panel.getBoundingClientRect().top) - r.top : r.height;
  const free = { w: Math.max(120, right - left), h: Math.max(120, bottom) };
  // target: the shape fills ~45% of the free area, but never zoom in more than 4x the home view
  const want = Math.max(b.width / 0.45 / free.w, b.height / 0.45 / free.h, geo.viewBox[2] / 4 / r.width);
  const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
  setView([cx - (left + free.w / 2) * want, cy - (free.h / 2) * want, r.width * want, r.height * want]);
}

// ------------------------------------------------------------------------------------------------
// Search
// ------------------------------------------------------------------------------------------------
const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
function bindSearch() {
  const input = $("#search"), out = $("#search-results");
  const items = Object.entries(data.territories).map(([code, t]) => ({ code, t, key: norm(`${t.name} ${code} ${t.capital || ""}`) }));
  let hits = [], cur = 0;
  const render = () => {
    out.innerHTML = hits.map((h, i) => `<button role="option" aria-selected="${i === cur}" data-code="${h.code}">${esc(h.t.name)} <small>${/^\d|^2[AB]/.test(h.code) ? h.code : ""}</small></button>`).join("");
    out.hidden = !hits.length;
  };
  const go = (code) => { select(code); zoomTo(code); input.value = ""; hits = []; render(); input.blur(); };
  input.addEventListener("input", () => {
    const q = norm(input.value.trim());
    hits = q ? items.filter((i) => i.key.includes(q)).sort((a, b) => a.key.indexOf(q) - b.key.indexOf(q)).slice(0, 10) : [];
    cur = 0; render();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { cur = Math.min(cur + 1, hits.length - 1); render(); e.preventDefault(); }
    if (e.key === "ArrowUp") { cur = Math.max(cur - 1, 0); render(); e.preventDefault(); }
    if (e.key === "Enter" && hits[cur]) go(hits[cur].code);
    if (e.key === "Escape") { input.value = ""; hits = []; render(); input.blur(); }
  });
  out.addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) go(b.dataset.code); });
}

// ------------------------------------------------------------------------------------------------
// Almanac
// ------------------------------------------------------------------------------------------------
function buildAlmanac() {
  const src = (id) => sources.find((s) => s.id === id);
  const groups = new Map();
  for (const l of lenses) { if (!groups.has(l.group)) groups.set(l.group, []); groups.get(l.group).push(l); }
  $("#almanac-body").innerHTML = `
    <h2>Almanach</h2>
    <p>Chaque chiffre de la carte vient d'une source publique, citée ci-dessous avec son millésime. Quand une source ne couvre pas un territoire,
    la carte l'affiche <b>hachuré</b> et indique « non publié » : rien n'est estimé ni extrapolé.</p>
    <p class="muted">Carte : départements de métropole en Lambert-93 ; chaque DROM dans son propre encart et sa propre projection (échelles différentes).
    La Nouvelle-Calédonie, la Polynésie française, Wallis-et-Futuna, Saint-Pierre-et-Miquelon, Saint-Martin et Saint-Barthélemy n'ont pas de contours
    dans ADMIN EXPRESS ; elles apparaissent sous forme de tuiles, comme les Français de l'étranger.</p>
    ${[...groups].map(([g, ls]) => `<h3>${esc(g)}</h3><dl>${ls.map((l) => `
      <dt>${esc(l.label)} <span class="muted">— ${esc(l.year)}${l.unit ? `, ${esc(l.unit)}` : ""}</span></dt>
      <dd>${esc(l.description)}<br><span class="muted">Source : <a href="${esc(src(l.source)?.page)}" target="_blank" rel="noopener">${esc(src(l.source)?.title)}</a>
      (${esc(src(l.source)?.publisher)}). Couverture : ${esc(l.coverage)}</span></dd>`).join("")}</dl>`).join("")}
    <h3>Sources</h3>
    <dl>${sources.map((s) => `<dt><a href="${esc(s.page)}" target="_blank" rel="noopener">${esc(s.title)}</a></dt><dd>${esc(s.publisher)} · ${esc(s.licence)}</dd>`).join("")}</dl>
    <p class="muted">Code et chaîne de traitement : <a href="https://github.com/nicobonsi/france2027" target="_blank" rel="noopener">github.com/nicobonsi/france2027</a>.</p>`;
  const modal = $("#almanac");
  $("#btn-almanac").addEventListener("click", () => { modal.hidden = false; modal.querySelector(".close").focus(); });
  modal.addEventListener("click", (e) => { if (e.target === modal || e.target.closest("[data-close]")) modal.hidden = true; });
}

// ------------------------------------------------------------------------------------------------
// URL state & keys
// ------------------------------------------------------------------------------------------------
function writeHash() {
  const p = new URLSearchParams();
  if (state.lens) p.set("indicateur", state.lens.id);
  if (state.selected) p.set("territoire", state.selected);
  history.replaceState(null, "", `#${p}`);
}
function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  return { lens: p.get("indicateur"), sel: p.get("territoire") };
}

function bindKeys() {
  addEventListener("keydown", (e) => {
    if (e.target.matches("input")) return;
    if (e.key === "/") { e.preventDefault(); $("#search").focus(); }
    if (e.key === "Escape") { $("#almanac").hidden = true; select(null); }
    if (e.key === "l" || e.key === "L") {
      const i = lenses.indexOf(state.lens);
      applyLens(lenses[(i + (e.shiftKey ? -1 : 1) + lenses.length) % lenses.length].id);
    }
  });
  $("#panel").addEventListener("click", (e) => {
    if (e.target.closest("[data-close]")) return select(null);
    const row = e.target.closest("tr[data-lens]");
    if (row) applyLens(row.dataset.lens);
  });
}

// ------------------------------------------------------------------------------------------------
async function main() {
  [geo, data, { lenses }, sources, nation] = await Promise.all([load("geo"), load("data"), load("lenses"), load("sources"), load("nation")]);
  lensById = new Map(lenses.map((l) => [l.id, l]));
  drawMap();
  buildDock();
  buildHeadline();
  buildAlmanac();
  bindPanZoom();
  bindSearch();
  bindKeys();
  const h = readHash();
  applyLens(lensById.has(h.lens) ? h.lens : "unemployment");
  if (h.sel && data.territories[h.sel]) select(h.sel);
  fitHome(); // after the legend is filled: on mobile its height sets the visible map area
  $("#loading").remove();
}

main().catch((err) => {
  console.error(err);
  const l = $("#loading");
  l.classList.add("err");
  l.textContent = `Impossible de charger les données : ${err.message}`;
});
