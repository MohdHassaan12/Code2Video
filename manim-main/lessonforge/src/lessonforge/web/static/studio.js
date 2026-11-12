/* Studio — scene-first editor over the storyboard IR.
 *
 * Everything on screen is a view of the storyboard JSON; edits mutate the IR
 * only, and the deterministic transpiler keeps owning code.
 *
 * Long LLM stages (storyboard, codegen) run as SERVER-SIDE TASKS that this page
 * polls — never as a single long-held fetch. That matters: a codegen chain that
 * falls through several models takes minutes, and a held-open fetch dies with
 * "NetworkError when attempting to fetch resource" long before the server is
 * done (observed 2026-08-01). Polling also gives us live per-model progress.
 */
"use strict";
(() => {

// ───────────────────────── constants ─────────────────────────

// Mirrors transpiler._ENTRANCE_ANIMS / _EXIT_ANIMS.
const ENTRANCES = ["FadeIn", "Write", "Create", "GrowFromCenter", "DrawBorderThenFill",
  "GrowArrow", "SpinInFromNothing", "FadeInFromPoint", "AddTextLetterByLetter", "ShowCreation"];
const EXITS = ["FadeOut", "Uncreate", "ShrinkToCenter", "FadeOutAndShift", "Unwrite"];
const EL_TYPES = ["text", "math", "shape", "svg_icon", "chemical_molecule",
  "coordinate_system", "graph", "math_evolution"];
const EVENT_ACTIONS = ["show", "hide", "transform", "highlight", "move_to", "focus"];
const ZONES = ["TOP_CENTER", "BOTTOM_CENTER", "TOP_LEFT", "TOP_RIGHT", "LEFT_CENTER", "RIGHT_CENTER"];
const DIRECTIONS = ["RIGHT", "LEFT", "UP", "DOWN", "UP+RIGHT", "UP+LEFT", "DOWN+RIGHT", "DOWN+LEFT"];
const TEMPLATES = ["", "TitleStageCaption", "SplitScreen", "FullCanvas"];
const STYLES = [
  ["3blue1brown/minimalist/neon", "3Blue1Brown Neon"],
  ["chalkboard/chalk/pastel", "Chalkboard Pastel"],
  ["cyberpunk/retrowave/orange", "Cyberpunk Retrowave"],
  ["minimalist/dark/mono", "Minimalist Mono"],
  ["powerpoint/clean", "PowerPoint Clean"],
];
const BACKGROUNDS = [
  ["default", "Default Dark Canvas"],
  ["white_canvas", "Default White Canvas"],
  ["chalkboard.jpg", "Chalkboard Texture"],
  ["space.jpg", "Starry Space"],
  ["notebook_paper.jpg", "Notebook Paper"],
  ["blueprint.jpg", "Blueprint Grid"],
];
const MANIM_COLORS = {
  BLUE: "#58C4DD", RED: "#FC6255", GREEN: "#83C167", YELLOW: "#F4D345",
  ORANGE: "#FF862F", PURPLE: "#9A72AC", PINK: "#D147BD", WHITE: "#ECECEC",
  TEAL: "#5CD0B3", GOLD: "#F0AC5F", MAROON: "#C55F73", GRAY: "#8B8B8B", GREY: "#8B8B8B",
};
const FALLBACK_VOICES = {
  languages: [{ code: "hi-IN", label: "Hindi (hi-IN)" }, { code: "en-IN", label: "English (en-IN)" }],
  sarvam_speakers_by_lang: { "hi-IN": ["shubh", "ashutosh", "priya", "suhani"], "en-IN": ["ratan", "ishita"] },
  gemini_voices: ["Puck", "Charon", "Kore", "Fenrir", "Aoede", "Zephyr", "Lyra", "Orion", "Callisto", "Nova"],
  edge_voices_by_lang: {
    "hi-IN": ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"],
    "en-IN": ["en-IN-NeerjaNeural", "en-IN-PrabhatNeural"],
    "bn-IN": ["bn-IN-TanishaaNeural", "bn-IN-BashkarNeural"],
    "ta-IN": ["ta-IN-PallaviNeural", "ta-IN-ValluvarNeural"],
    "te-IN": ["te-IN-ShrutiNeural", "te-IN-MohanNeural"],
  },
  local_voices_by_lang: {
    "hi-IN": ["hf_alpha", "hm_omega", "hf_beta", "hm_psi"],
    "en-IN": ["af_heart", "am_michael", "bf_emma", "bm_george"],
  },
  defaults: { language: "hi-IN", tts_provider: "sarvam", speaker: "shubh" },
  providers_configured: { sarvam: false, gemini: true, edge: true, local: true },
};

const LLM_MODELS_BY_PROVIDER = {
  auto: [
    { value: "auto", label: "Auto (provider defaults)" },
  ],
  anthropic: [
    { value: "auto", label: "Auto (Task-routed: Haiku for small/vision, Sonnet for code, Opus for storyboard)" },
    { value: "claude-opus-5-5", label: "Claude Opus 5.5 (Costliest · best plans · $4 / $20 per MTok)" },
    { value: "claude-sonnet-5-5", label: "Claude Sonnet 5.5 (Code & repairs · $2 / $10)" },
    { value: "claude-haiku-5-5", label: "Claude Haiku 5.5 (Cheapest · small calls & vision · $0.10 / $0.50)" },
    { value: "claude-fable-5-1", label: "Claude Fable 5.1 (Most capable · $10 / $50 · manual only)" },
  ],
  openrouter: [
    { value: "auto", label: "Auto (Gemini 2.5 Flash / GPT-4.1 / Haiku)" },
    { value: "anthropic/claude-haiku-5.5", label: "Claude Haiku 5.5 (via OpenRouter)" },
    { value: "google/gemini-2.5-flash", label: "Google Gemini 2.5 Flash" },
    { value: "openai/gpt-4.1", label: "OpenAI GPT-4.1" },
    { value: "deepseek/deepseek-v3.2", label: "DeepSeek V3.2" },
  ],
  gemini: [
    { value: "auto", label: "Auto (Gemini 2.5 Flash / Pro)" },
    { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
    { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
    { value: "gemini-2.5-flash-lite", label: "Gemini 2.5 Flash Lite" },
  ],
  groq: [
    { value: "auto", label: "Auto (Llama 3.3 70B)" },
    { value: "llama-3.3-70b-versatile", label: "Llama 3.3 70B Versatile" },
    { value: "llama-3.1-8b-instant", label: "Llama 3.1 8B Instant" },
  ],
};

// ───────────────────────── DOM helpers ─────────────────────────

const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === undefined || v === null) continue;
    if (k === "class") n.className = v;
    else if (k === "dataset") Object.assign(n.dataset, v);
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (k === "value") n.value = v;
    else if (k === "checked" || k === "disabled" || k === "selected" || k === "draggable") n[k] = v;
    else n.setAttribute(k, v);
  }
  for (const c of kids.flat(9)) {
    if (c === null || c === undefined || c === false) continue;
    n.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return n;
}

function sel(options, value, onchange, props = {}) {
  const s = el("select", { ...props, onchange: (e) => onchange(e.target.value) });
  for (const o of options) {
    const [v, label] = Array.isArray(o) ? o : [o, o];
    s.append(el("option", { value: v, selected: v === value }, label));
  }
  return s;
}

const escXml = (s) => String(s ?? "").replace(/[<>&"']/g,
  (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&#39;" }[c]));

function toast(msg, kind = "") {
  const t = el("div", { class: `toast ${kind}` }, msg);
  $("#toasts").append(t);
  setTimeout(() => { t.style.opacity = "0"; setTimeout(() => t.remove(), 250); }, 4600);
}

const fmtSecs = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
function fmtAgo(ts) {
  const d = (Date.now() - ts) / 1000;
  if (d < 90) return "just now";
  if (d < 3600) return `${Math.round(d / 60)}m ago`;
  if (d < 86400) return `${Math.round(d / 3600)}h ago`;
  return `${Math.round(d / 86400)}d ago`;
}

// ───────────────────────── API ─────────────────────────

async function api(path, body, method) {
  const opts = { headers: { "Content-Type": "application/json" } };
  const key = localStorage.getItem("gemini_api_key");
  if (key) opts.headers["X-Gemini-API-Key"] = key;
  if (body !== undefined) { opts.method = method || "POST"; opts.body = JSON.stringify(body); }
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const d = await r.json();
      const detail = d.detail ?? d.error;
      if (detail) msg = typeof detail === "string" ? detail : JSON.stringify(detail);
    } catch (_) { /* non-JSON error body */ }
    const err = new Error(msg);
    err.status = r.status;
    throw err;
  }
  return r.json();
}

/* Start a server-side task and poll it to completion.
 * Poll failures are tolerated (a few consecutive misses) — a dropped poll is a
 * blip, not a dead task, and the work continues server-side regardless. */
async function runTask(startPath, body, onTick, opts = {}) {
  const started = await api(startPath, body);
  const taskId = started.task_id;
  if (opts.onStart) opts.onStart(taskId);
  let misses = 0;
  while (true) {
    await sleep(1500);
    let t;
    try {
      t = await api(`/api/tasks/${taskId}`);
      misses = 0;
    } catch (e) {
      if (e.status === 404) throw new Error("The server restarted and lost this task. Please try again.");
      if (++misses >= 8) throw new Error(`Lost contact with the server while working (${e.message}).`);
      continue;
    }
    if (onTick) onTick(t);
    if (t.state === "done") return t.result;
    if (t.state === "error") throw new Error(t.error || "Task failed");
  }
}

// ───────────────────────── project store ─────────────────────────

const STORE_KEY = "studio.projects.v1";
const store = {
  all() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY) || "[]"); }
    catch (_) { return []; }
  },
  save(p) {
    p.updatedAt = Date.now();
    let list = this.all().filter((x) => x.id !== p.id);
    list.unshift(p);
    list = list.slice(0, 20);
    try { localStorage.setItem(STORE_KEY, JSON.stringify(list)); }
    catch (e) { toast("Could not save the project locally (browser storage full).", "warn"); }
  },
  remove(id) {
    localStorage.setItem(STORE_KEY, JSON.stringify(this.all().filter((x) => x.id !== id)));
  },
};

// ───────────────────────── state ─────────────────────────

let VOICES = FALLBACK_VOICES;
/* The RESOLVED theme for the project's style+background, from GET /api/theme — the
 * same table the transpiler uses. The blueprint used to hard-code a dark canvas and
 * its own colours, so the preview could not match the render even in principle
 * (2026-08-14: "the style profile and the background are not matching"). Mirroring
 * theme.py in JS would drift by construction, so it is served. */
let THEME = { canvas: "#060a0f", text: "#ECEFF4", accent: "#FFD24A",
              palette: ["#58C4DD", "#FFD24A", "#83C167", "#FC6255", "#CF89E8", "#FF9F40"],
              is_light: false, min_contrast: 3 };
let project = null;
let selScene = 0;
let selCue = -1;
let selTab = "content";
let expandedEl = -1;
let render = { active: false, jobId: null, ws: null, timer: null, pollT: null, startedAt: 0, lastJob: null, codegen: null };
let saveT = null;

const scenes = () => (project && project.storyboard && project.storyboard.visual_storyboard) || [];
const scene = () => scenes()[selScene];

function settingsSig() {
  const s = project.settings;
  return [s.style, s.background, s.persona, s.language, s.speaker, s.tts_provider, s.quality, s.aspect_ratio].join("|");
}
const sceneSig = (sc) => JSON.stringify(sc) + "‖" + settingsSig();
const isDirty = (i) => !project.renderedSigs || project.renderedSigs[i] !== sceneSig(scenes()[i]);
const dirtyCount = () => scenes().reduce((n, _, i) => n + (isDirty(i) ? 1 : 0), 0);

function save() {
  if (!project) return;
  clearTimeout(saveT);
  saveT = setTimeout(() => store.save(project), 350);
}

function onEdit(opts = {}) {
  save();
  refreshTopbar();
  if (opts.canvas) { renderCanvas(); renderRail(); }
  else refreshRailDots();
}

// ───────────────────────── blueprint SVG ─────────────────────────

const ZONE_XY = {
  TOP_CENTER: [0.5, 0.1], BOTTOM_CENTER: [0.5, 0.9], TOP_LEFT: [0.15, 0.1],
  TOP_RIGHT: [0.85, 0.1], LEFT_CENTER: [0.15, 0.5], RIGHT_CENTER: [0.85, 0.5],
  BOTTOM_LEFT: [0.15, 0.9], BOTTOM_RIGHT: [0.85, 0.9],
};
const DIR_XY = {
  UP: [0, -1], DOWN: [0, 1], LEFT: [-1, 0], RIGHT: [1, 0],
  UP_RIGHT: [1, -1], UP_LEFT: [-1, -1], DOWN_RIGHT: [1, 1], DOWN_LEFT: [-1, 1],
};

function hexOf(c) {
  const v = (c || "").trim();
  if (!v) return null;
  if (v.startsWith("#")) {
    const h = v.slice(1);
    if (h.length === 3) return "#" + h.split("").map((x) => x + x).join("").toUpperCase();
    return h.length === 6 ? "#" + h.toUpperCase() : null;
  }
  return MANIM_COLORS[v.toUpperCase().replace(/_[A-E]$/, "")] || null;
}

const _rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
function luminance(hex) {
  const [r, g, b] = _rgb(hex).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contrast(a, b) {
  const l = [luminance(a), luminance(b)].sort((x, y) => x - y);
  return (l[1] + 0.05) / (l[0] + 0.05);
}
function hue(hex) {
  const [r, g, b] = _rgb(hex);
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
  if (mx - mn < 1e-6) return -1;
  let h;
  if (mx === r) h = 60 * (((g - b) / (mx - mn)) % 6);
  else if (mx === g) h = 60 * ((b - r) / (mx - mn) + 2);
  else h = 60 * ((r - g) / (mx - mn) + 4);
  return (h + 360) % 360;
}
const isRawPrimary = (hex) => {
  const h = hex.slice(1);
  return [0, 2, 4].every((i) => ["00", "FF"].includes(h.slice(i, i + 2)))
    && h !== "FFFFFF" && h !== "000000";
};
function nearestPalette(hex) {
  const pal = THEME.palette || [];
  if (!pal.length) return hex;
  const h = hue(hex);
  if (h < 0) return pal[0];
  return pal.reduce((best, p) => {
    const d = Math.min(Math.abs(hue(p) - h), 360 - Math.abs(hue(p) - h));
    const bd = Math.min(Math.abs(hue(best) - h), 360 - Math.abs(hue(best) - h));
    return d < bd ? p : best;
  }, pal[0]);
}

/* Mirrors theme.harmonize server-side: a model colour survives when it is legible
 * on THIS canvas and looks picked; a raw primary or an unreadable one snaps to the
 * nearest palette colour by hue. Keeping the two in step is what makes the
 * blueprint an honest preview. */
function elColor(e, fallback, kind) {
  const hex = hexOf(e.color);
  if (!hex) return fallback;
  const canvas = THEME.canvas || "#060a0f";
  const min = THEME.min_contrast || 3;
  const ratio = contrast(hex, canvas);
  if (kind === "text" || kind === "math" || kind === "math_evolution") {
    return ratio < min ? THEME.text : hex;
  }
  if (isRawPrimary(hex) || ratio < min) {
    const cand = nearestPalette(hex);
    if (contrast(cand, canvas) >= min) return cand;
    return ratio < min ? THEME.text : hex;
  }
  return hex;
}

async function refreshTheme() {
  if (!project) return;
  try {
    const q = new URLSearchParams({ style: project.settings.style,
                                    background: project.settings.background });
    THEME = await api(`/api/theme?${q}`);
  } catch (_) { /* keep the built-in default */ }
}

/* Schematic of a scene drawn from the IR alone — zones, anchors and element
 * types, not real Manim geometry. Labeled "Blueprint" in the UI and replaced
 * by the actual clip after a render. */
function blueprintSVG(sc, aspect, opts = {}) {
  const W = aspect === "vertical" ? 540 : 960;
  const H = aspect === "vertical" ? 960 : 540;
  const p = [];
  p.push(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" role="img" preserveAspectRatio="xMidYMid meet">`);
  // The canvas the RENDER will use, not a hard-coded dark one — otherwise the
  // preview lies about every light-canvas project.
  p.push(`<rect width="${W}" height="${H}" fill="${THEME.canvas || "#060a0f"}"/>`);

  if (!opts.tiny) {
    // Faint coordinate plane, echoing Manim's NumberPlane.
    p.push(`<g stroke="${THEME.is_light ? "#E3E8EE" : "#12202c"}" stroke-width="1">`);
    for (let x = 60; x < W; x += 60) p.push(`<line x1="${x}" y1="0" x2="${x}" y2="${H}"/>`);
    for (let y = 60; y < H; y += 60) p.push(`<line x1="0" y1="${y}" x2="${W}" y2="${y}"/>`);
    p.push(`</g>`);
  }

  const tpl = sc.layout_template;
  if (tpl === "SplitScreen") {
    p.push(`<line x1="${W / 2}" y1="18" x2="${W / 2}" y2="${H - 18}" stroke="#2a3f52" stroke-dasharray="7 8" stroke-width="2"/>`);
  } else if (tpl === "TitleStageCaption") {
    p.push(`<line x1="18" y1="${H * 0.18}" x2="${W - 18}" y2="${H * 0.18}" stroke="#22323f" stroke-dasharray="5 9"/>`);
    p.push(`<line x1="18" y1="${H * 0.84}" x2="${W - 18}" y2="${H * 0.84}" stroke="#22323f" stroke-dasharray="5 9"/>`);
  }

  const els = sc.elements || [];
  const pos = {};
  let floatN = 0;

  const place = (e) => {
    if (Array.isArray(e.absolute_position) && e.absolute_position.length >= 2) {
      const [ax, ay] = e.absolute_position;
      return [((ax + 7.1) / 14.2) * W, ((4 - ay) / 8) * H];
    }
    if (e.safe_zone_alignment && ZONE_XY[e.safe_zone_alignment]) {
      const [fx, fy] = ZONE_XY[e.safe_zone_alignment];
      return [fx * W, fy * H];
    }
    if (e.relative_positioning && pos[e.relative_positioning.relative_to]) {
      const t = pos[e.relative_positioning.relative_to];
      const d = DIR_XY[e.relative_positioning.direction] || [0, -1];
      const step = 0.085 * Math.min(W, H) * (1 + (e.relative_positioning.buffer || 0.5));
      return [t[0] + d[0] * step, t[1] + d[1] * step];
    }
    floatN += 1;
    return [W * 0.5 + ((floatN % 3) - 1) * W * 0.17, H * 0.46 + Math.floor(floatN / 3) * H * 0.13];
  };

  els.forEach((e) => { if (!e.relative_positioning) pos[e.id] = place(e); });
  els.forEach((e) => { if (!(e.id in pos)) pos[e.id] = place(e); });

  for (const e of els) {
    let [x, y] = pos[e.id];
    x = Math.max(28, Math.min(W - 28, x));
    y = Math.max(22, Math.min(H - 22, y));
    const s = e.scale || 0.7;
    const raw = String(e.content || e.id || "");
    const label = raw.slice(0, 26) + (raw.length > 26 ? "…" : "");
    const type = e.type || "text";
    const showLabel = !opts.tiny;

    if (type === "coordinate_system" || type === "graph") {
      const w = W * 0.4 * Math.min(s / 0.7, 1.6), h = H * 0.45 * Math.min(s / 0.7, 1.6);
      const c = elColor(e, THEME.text || "#8fa6b8", type);
      p.push(`<g stroke="${c}" stroke-width="2" opacity=".9" fill="none">`);
      p.push(`<line x1="${x - w / 2}" y1="${y + h / 2}" x2="${x + w / 2}" y2="${y + h / 2}"/>`);
      p.push(`<line x1="${x - w / 2 + 14}" y1="${y - h / 2}" x2="${x - w / 2 + 14}" y2="${y + h / 2 + 6}"/>`);
      for (let i = 1; i <= 4; i++) p.push(`<line x1="${x - w / 2 + i * (w / 5)}" y1="${y + h / 2 - 4}" x2="${x - w / 2 + i * (w / 5)}" y2="${y + h / 2 + 4}"/>`);
      if (type === "graph") p.push(`<path d="M ${x - w / 2 + 14} ${y + h / 2 - 8} Q ${x} ${y - h / 2} ${x + w / 2 - 6} ${y - h / 2 + 14}" stroke="#58c4dd" stroke-width="2.5"/>`);
      p.push(`</g>`);
      if (showLabel) p.push(`<text x="${x + w / 2 - 4}" y="${y + h / 2 + 19}" fill="#5f7386" font-size="12" text-anchor="end" font-family="JetBrains Mono, monospace">${escXml(label)}</text>`);
    } else if (type === "shape") {
      const kw = raw.toLowerCase();
      const c = elColor(e, (THEME.palette || [])[0] || "#58c4dd", type);
      const r = 26 * s / 0.7;
      if (kw.includes("point") || kw.includes("dot")) p.push(`<circle cx="${x}" cy="${y}" r="5.5" fill="${c}"/>`);
      else if (kw.includes("arrow")) p.push(`<g stroke="${c}" stroke-width="3" fill="${c}"><line x1="${x - r}" y1="${y + r * 0.5}" x2="${x + r * 0.7}" y2="${y - r * 0.5}"/><path d="M ${x + r * 0.7} ${y - r * 0.5} l -12 2 l 6 9 z"/></g>`);
      else if (kw.includes("line")) p.push(`<line x1="${x - r * 1.4}" y1="${y + r * 0.4}" x2="${x + r * 1.4}" y2="${y - r * 0.4}" stroke="${c}" stroke-width="3"/>`);
      else if (kw.includes("triangle")) p.push(`<polygon points="${x - r},${y + r * 0.8} ${x + r},${y + r * 0.8} ${x + r * 0.6},${y - r * 0.8}" fill="none" stroke="${c}" stroke-width="3"/>`);
      else if (kw.includes("square") || kw.includes("rect") || kw.includes("box")) p.push(`<rect x="${x - r}" y="${y - r * 0.75}" width="${r * 2}" height="${r * 1.5}" fill="none" stroke="${c}" stroke-width="3" rx="3"/>`);
      else p.push(`<circle cx="${x}" cy="${y}" r="${r * 0.8}" fill="none" stroke="${c}" stroke-width="3"/>`);
      if (showLabel) p.push(`<text x="${x}" y="${y + r + 17}" fill="#5f7386" font-size="11" text-anchor="middle" font-family="JetBrains Mono, monospace">${escXml(label)}</text>`);
    } else if (type === "svg_icon" || type === "chemical_molecule") {
      const c = elColor(e, (THEME.palette || [])[4] || "#9a72ac", type);
      const r = 22 * s / 0.7;
      if (type === "svg_icon") p.push(`<rect x="${x - r}" y="${y - r}" width="${r * 2}" height="${r * 2}" transform="rotate(45 ${x} ${y})" fill="none" stroke="${c}" stroke-width="2.5" rx="4"/>`);
      else {
        const hex = Array.from({ length: 6 }, (_, i) => { const a = Math.PI / 3 * i - Math.PI / 6; return `${x + r * Math.cos(a)},${y + r * Math.sin(a)}`; }).join(" ");
        p.push(`<polygon points="${hex}" fill="none" stroke="${c}" stroke-width="2.5"/>`);
      }
      if (showLabel) p.push(`<text x="${x}" y="${y + r + 17}" fill="#5f7386" font-size="11" text-anchor="middle" font-family="JetBrains Mono, monospace">${escXml(label)}</text>`);
    } else {
      const isMath = type.startsWith("math");
      const fs = (isMath ? 19 : 16) * (s / 0.7);
      const c = elColor(e, THEME.text || (isMath ? "#e8eff5" : "#c8dde8"), type);

      if (isMath && typeof window !== "undefined" && window.katex && !opts.tiny) {
        // KaTeX in a foreignObject. The box starts wide and _applyKatexToBlueprint() shrinks the pill to the
        // formula it measured (a character count clipped \frac and \sqrt formulas). Plain div/span: the SVG is set
        // through innerHTML, where an "xhtml:" prefix is not honoured.
        const foW = W * 0.9;
        const foH = fs * 2.6;
        p.push(`<rect class="bp-math-bg" x="${x - foW / 2}" y="${y - foH / 2 - 4}" width="${foW}" height="${foH + 8}" rx="6" fill="${THEME.is_light ? "#F5F7FA" : "#0d1620"}" stroke="${THEME.is_light ? "#D5DCE5" : "#22323f"}"/>`);
        p.push(`<foreignObject x="${x - foW / 2}" y="${y - foH / 2}" width="${foW}" height="${foH}" data-cx="${x}" data-fs="${fs * 0.9}" data-katex="${escXml(previewLatex(raw, type))}">`);
        p.push(`<div style="display:flex;align-items:center;justify-content:center;height:100%;color:${c};font-size:${fs * 0.9}px;white-space:nowrap;"><span class="bp-katex-placeholder">${escXml(raw)}</span></div></foreignObject>`);
      } else {
        const wBox = Math.min(label.length * fs * 0.56 + 24, W * 0.46);
        p.push(`<rect x="${x - wBox / 2}" y="${y - fs * 0.98}" width="${wBox}" height="${fs * 1.96}" rx="5" fill="${THEME.is_light ? "#F5F7FA" : "#0d1620"}" stroke="${THEME.is_light ? "#D5DCE5" : "#22323f"}"/>`);
        p.push(`<text x="${x}" y="${y + fs * 0.36}" fill="${c}" font-size="${fs}" text-anchor="middle" ${isMath ? 'font-style="italic" font-family="Georgia, serif"' : 'font-family="Archivo, system-ui, sans-serif"'}>${escXml(type === "math_evolution" ? label.replace("→", " → ") : label)}</text>`);
      }
    }
  }

  if (!els.length && !opts.tiny) {
    p.push(`<text x="${W / 2}" y="${H / 2}" fill="#5f7386" font-size="15" text-anchor="middle" font-family="Archivo, system-ui, sans-serif">Empty scene — add elements in the Content tab</text>`);
  }
  p.push("</svg>");
  return p.join("");
}

/** What KaTeX is given for a math element: the part of the render's clean-up (lessonforge/mathfix.py
 *  sanitize_math) that decides whether KaTeX can read it at all. The render also uppercases nothing and
 *  upright-sets units; this is the preview, not the proof. */
function previewLatex(raw, type) {
  let s = String(raw || "").replace(/\$/g, " ").replace(/\\[()[\]]/g, " ");
  s = s.replace(/\btext\(([^()]*)\)/g, "\\text{$1}");
  if (type === "math_evolution") s = s.replace("→", " \\to ");
  return s.trim();
}

/** After setting innerHTML to blueprintSVG output, render KaTeX inside the foreignObjects, then fit each pill to
 *  the formula it holds. A formula KaTeX cannot parse is shown as red source text with a "will fail" outline, so
 *  the preview no longer looks fine for a line the render would reject. */
function _applyKatexToBlueprint(container) {
  if (!window.katex) return;
  const svg = container.querySelector("svg");
  const vbW = svg && svg.viewBox && svg.viewBox.baseVal ? svg.viewBox.baseVal.width : 0;
  const k = svg && vbW ? svg.getBoundingClientRect().width / vbW : 0;   // CSS px per SVG unit; 0 when hidden
  container.querySelectorAll("foreignObject[data-katex]").forEach((fo) => {
    const latex = fo.getAttribute("data-katex");
    const span = fo.querySelector(".bp-katex-placeholder");
    const bg = fo.previousElementSibling;
    if (!span) return;
    try {
      katex.render(latex, span, { throwOnError: true, displayMode: false, output: "html" });
    } catch (err) {
      span.textContent = latex;
      span.style.color = "#ff6b6b";
      span.title = "LaTeX error: " + (err && err.message ? err.message : err);
      if (bg) bg.setAttribute("stroke", "#ff6b6b");
    }
    if (!k) return;
    const cx = parseFloat(fo.getAttribute("data-cx"));
    const maxW = vbW * 0.9;
    let w = span.getBoundingClientRect().width / k + 28;
    if (w > maxW) {                      // too wide: shrink the type instead of clipping the formula
      const fs = parseFloat(fo.getAttribute("data-fs")) * (maxW / w);
      span.style.fontSize = fs + "px";
      w = Math.min(maxW, span.getBoundingClientRect().width / k + 28);
    }
    fo.setAttribute("x", cx - w / 2);
    fo.setAttribute("width", w);
    if (bg) { bg.setAttribute("x", cx - w / 2 - 4); bg.setAttribute("width", w + 8); }
  });
}

// ───────────────────────── progress UI ─────────────────────────

function makeProgress(ids) {
  const panel = $(ids.panel), phase = $(ids.phase), text = $(ids.text),
        logBox = $(ids.log), errBox = $(ids.err), elapsed = $(ids.elapsed);
  let timer = null, startedAt = 0;

  return {
    start(label, msg) {
      panel.classList.remove("hidden", "is-done", "is-failed");
      phase.textContent = label;
      text.textContent = msg || "";
      logBox.textContent = ""; logBox.classList.add("hidden");
      errBox.textContent = ""; errBox.classList.add("hidden");
      startedAt = Date.now();
      clearInterval(timer);
      elapsed.textContent = "0:00";
      timer = setInterval(() => { elapsed.textContent = fmtSecs((Date.now() - startedAt) / 1000); }, 1000);
    },
    phase(label, msg) { phase.textContent = label; if (msg !== undefined) text.textContent = msg; },
    say(msg) { text.textContent = msg; },
    lines(lines) {
      if (!lines || !lines.length) return;
      logBox.classList.remove("hidden");
      logBox.textContent = "";
      for (const l of lines.slice(-14)) {
        logBox.append(el("div", { class: l.level === "WARNING" ? "w" : "" }, l.text));
      }
      logBox.scrollTop = logBox.scrollHeight;
    },
    done(msg) {
      clearInterval(timer);
      panel.classList.add("is-done");
      phase.textContent = "Done";
      text.textContent = msg || "";
    },
    fail(msg) {
      clearInterval(timer);
      panel.classList.add("is-failed");
      phase.textContent = "Failed";
      errBox.textContent = msg;
      errBox.classList.remove("hidden");
    },
    hide() { clearInterval(timer); panel.classList.add("hidden"); },
    stop() { clearInterval(timer); },
    elapsedSecs() { return (Date.now() - startedAt) / 1000; },
  };
}

let briefProg = null, studioProg = null;

// ───────────────────────── home view ─────────────────────────

function styleToBackground(style) {
  if (style.includes("chalkboard")) return "chalkboard.jpg";
  if (style.includes("cyberpunk")) return "space.jpg";
  if (style.includes("powerpoint")) return "white_canvas";
  return "default";
}

function getVoicesFor(provider, lang) {
  if (provider === "gemini") {
    return VOICES.gemini_voices || [];
  }
  if (provider === "edge") {
    const edgeMap = VOICES.edge_voices_by_lang || {};
    return edgeMap[lang] || edgeMap["hi-IN"] || ["hi-IN-SwaraNeural"];
  }
  if (provider === "local" || provider === "kokoro") {
    const localMap = VOICES.local_voices_by_lang || {};
    return localMap[lang] || (lang && lang.startsWith("en") ? localMap["en-IN"] : localMap["hi-IN"]) || ["af_heart"];
  }
  return (VOICES.sarvam_speakers_by_lang || {})[lang] || ["shubh"];
}

function refreshBriefVoices() {
  const spk = $("#brief-speaker");
  const prev = spk.value;
  const provider = $("#brief-provider").value;
  const lang = $("#brief-language").value;
  const list = getVoicesFor(provider, lang);
  spk.innerHTML = "";
  list.forEach((v) => spk.append(el("option", { value: v }, v)));
  if (list.includes(prev)) spk.value = prev;

  const note = $("#tts-note");
  const conf = VOICES.providers_configured || {};
  if (provider === "sarvam" && conf.sarvam === false) {
    note.className = "note warn";
    note.textContent = "This server has no Sarvam key — narration falls back to Gemini TTS automatically.";
    note.classList.remove("hidden");
  } else if (provider === "local" && conf.local === false) {
    note.className = "note warn";
    note.textContent = "Kokoro model/voices not found locally on server.";
    note.classList.remove("hidden");
  } else if (provider === "edge" && conf.edge === false) {
    note.className = "note warn";
    note.textContent = "Edge TTS package is not installed on server.";
    note.classList.remove("hidden");
  } else {
    note.classList.add("hidden");
  }
}

function initBrief() {
  const langSel = $("#brief-language");
  langSel.innerHTML = "";
  VOICES.languages.forEach((l) => langSel.append(el("option", { value: l.code }, l.label)));
  langSel.value = VOICES.defaults.language || "hi-IN";
  refreshBriefVoices();
  langSel.addEventListener("change", refreshBriefVoices);
  $("#brief-provider").addEventListener("change", refreshBriefVoices);
  $("#brief-topic").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("#brief-generate").click();
  });

  const auditionBtn = $("#brief-audition");
  if (auditionBtn) {
    auditionBtn.addEventListener("click", async () => {
      const orig = auditionBtn.textContent;
      auditionBtn.textContent = "…";
      auditionBtn.disabled = true;
      try {
        const lang = $("#brief-language").value;
        const provider = $("#brief-provider").value;
        const speaker = $("#brief-speaker").value;
        const sampleText = lang && lang.startsWith("hi")
          ? "नमस्ते! हम इस पाठ में गति और बल के नियमों को विस्तार से समझेंगे।"
          : "Hello! Welcome to this lesson where we explore physics step by step.";
        const r = await api("/api/tts/preview", {
          text: sampleText, language: lang, tts_provider: provider, speaker: speaker,
        });
        const audio = $("#preview-audio");
        audio.src = r.url;
        audio.play();
        if (r.note) toast(r.note, "warn");
      } catch (e) {
        toast(e.message || "Audition failed", "warn");
      } finally {
        auditionBtn.textContent = orig;
        auditionBtn.disabled = false;
      }
    });
  }

  const llmProvSel = $("#brief-llm-provider");
  const llmModelSel = $("#brief-llm-model");
  const llmNote = $("#brief-llm-note");

  function refreshLLMModels() {
    if (!llmProvSel || !llmModelSel) return;
    const prov = llmProvSel.value;
    const list = LLM_MODELS_BY_PROVIDER[prov] || LLM_MODELS_BY_PROVIDER.auto;
    llmModelSel.innerHTML = "";
    list.forEach((m) => llmModelSel.append(el("option", { value: m.value }, m.label)));

    if (llmNote) {
      if (prov === "anthropic") {
        llmNote.className = "note";
        llmNote.textContent = "Anthropic API (needs ANTHROPIC_API_KEY on the server): Auto routes by cost — Haiku 5.5 for vision checks and small calls, Sonnet 5.5 for scene code, Opus 5.5 for the storyboard. Pick a model by hand to use it for this step only (vision checks stay on Haiku).";
        llmNote.classList.remove("hidden");
      } else if (prov === "openrouter") {
        llmNote.className = "note";
        llmNote.textContent = "OpenRouter: Multi-model gateway with metered balance, supports Claude, Gemini, GPT-4, and DeepSeek.";
        llmNote.classList.remove("hidden");
      } else {
        llmNote.classList.add("hidden");
      }
    }
  }

  if (llmProvSel) {
    llmProvSel.addEventListener("change", refreshLLMModels);
    refreshLLMModels();
  }

  // Source material: one entry per line. The server classifies each line (YouTube
  // link / web page / pasted text), so the box takes whatever the user actually has.
  function briefSources() {
    const box = $("#brief-sources");
    if (!box) return [];
    return box.value.split("\n").map((s) => s.trim()).filter(Boolean);
  }

  // Grounding is inspectable BEFORE it is paid for: a transcript that turns out to be
  // disabled is worth knowing about now, not after watching the video.
  const checkBtn = $("#brief-check-sources");
  if (checkBtn) checkBtn.addEventListener("click", async () => {
    const out = $("#brief-sources-out");
    const srcs = briefSources();
    if (!srcs.length) { out.textContent = "Nothing to check — add a link or paste some notes."; return; }
    checkBtn.disabled = true;
    out.textContent = "Fetching…";
    try {
      const r = await fetch("/api/research", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: $("#brief-topic").value.trim(), sources: srcs }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || r.statusText);
      const rows = (d.sources || []).map((s) =>
        `${s.error ? "✗" : "✓"} ${s.kind}: ${(s.title || s.url || "note").slice(0, 60)}` +
        (s.error ? ` — ${s.error.slice(0, 70)}` : ` — ${s.chunks} chunk(s), ${s.chars} chars`));
      out.innerHTML = rows.length ? rows.join("<br>") : "No usable source material.";
    } catch (e) {
      out.textContent = "Could not check sources: " + e.message;
    } finally {
      checkBtn.disabled = false;
    }
  });

  $("#brief-generate").addEventListener("click", async () => {
    const topic = $("#brief-topic").value.trim();
    if (!topic) { toast("Enter a topic first", "error"); $("#brief-topic").focus(); return; }
    const btn = $("#brief-generate");
    btn.disabled = true;
    briefProg.start("Writing the storyboard", "Planning scenes and narration — this is one LLM call and usually takes 30–120 seconds.");
    try {
      const style = $("#brief-style").value;
      const body = {
        topic, style,
        persona: $("#brief-persona").value,
        tech_terms: $("#brief-tech").value,
        language: $("#brief-language").value,
        speaker: $("#brief-speaker").value,
        tts_provider: $("#brief-provider").value,
        llm_provider: $("#brief-llm-provider") ? $("#brief-llm-provider").value : "auto",
        llm_model: $("#brief-llm-model") ? $("#brief-llm-model").value : "auto",
      };
      const yt = $("#brief-yt").value.trim();
      if (yt) body.context = { youtube_url: yt };
      const srcs = briefSources();
      if (srcs.length) body.sources = srcs;

      const sb = await runTask("/api/tasks/storyboard", body, (t) => {
        if (t.progress) briefProg.say(t.progress);
        briefProg.lines(t.progress_lines);
      });

      project = {
        id: "p_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
        topic, createdAt: Date.now(), updatedAt: Date.now(),
        settings: {
          style, background: styleToBackground(style),
          persona: body.persona, tech_terms: body.tech_terms, language: body.language,
          speaker: body.speaker, tts_provider: body.tts_provider,
          llm_provider: body.llm_provider, llm_model: body.llm_model,
          quality: $("#brief-quality").value, aspect_ratio: $("#brief-aspect").value,
        },
        storyboard: sb, renderedSigs: [], lastRender: null, activeJob: null, lastCode: null,
      };
      store.save(project);
      briefProg.hide();
      enterStudio(project);
      toast(`Storyboard ready — ${scenes().length} scenes. Review and edit before rendering.`);
    } catch (e) {
      briefProg.fail(e.message);
    } finally { btn.disabled = false; }
  });
}

function metaBadge(meta) {
  if (!meta) return el("span", { class: "chip dim" }, "Raw");
  if ((meta.violations_remaining || 0) > 0) return el("span", { class: "chip bad" }, `${meta.violations_remaining} overlaps`);
  if ((meta.repair_rounds || 0) > 0) return el("span", { class: "chip warn" }, `Repaired ×${meta.repair_rounds}`);
  return el("span", { class: "chip ok" }, "Clean");
}

function renderProjectList() {
  const box = $("#proj-list");
  box.innerHTML = "";
  const list = store.all();
  $("#proj-count").textContent = list.length ? `${list.length}` : "";
  if (!list.length) {
    box.append(el("div", { class: "empty-state", style: "grid-column:1/-1" },
      "No projects yet. Create a storyboard on the left and it lands here — editable, scene by scene."));
    return;
  }
  for (const p of list) {
    const sc0 = (p.storyboard && p.storyboard.visual_storyboard && p.storyboard.visual_storyboard[0]) || { elements: [] };
    const open = () => { project = p; enterStudio(p); };
    const thumb = el("div", { class: "proj-thumb" });
    thumb.innerHTML = blueprintSVG(sc0, p.settings.aspect_ratio, { tiny: true });
    const nScenes = (p.storyboard.visual_storyboard || []).length;
    box.append(el("div", { class: "card proj-card", onclick: open },
      thumb,
      el("div", { class: "card-info" },
        el("div", { class: "card-name" },
          el("span", {}, p.topic),
          el("button", {
            class: "icon-btn", title: "Delete project",
            onclick: (ev) => {
              ev.stopPropagation();
              if (confirm(`Delete the project "${p.topic}"?\n\nRendered videos stay on the server.`)) {
                store.remove(p.id); renderProjectList();
              }
            },
          }, "✕")),
        el("div", { class: "card-meta" },
          p.lastRender ? el("span", { class: "chip ok" }, "rendered") : el("span", { class: "chip dim" }, "storyboard"),
          el("span", { class: "chip dim plain" }, `${nScenes} scenes`),
          el("span", { class: "card-age" }, fmtAgo(p.updatedAt))))));
  }
}

async function renderHistoryList() {
  const box = $("#history-list");
  try {
    const data = await api("/api/video_history");
    box.innerHTML = "";
    const vids = (data.videos || []).slice(0, 8);
    $("#hist-count").textContent = (data.videos || []).length ? `${(data.videos || []).length}` : "";
    if (!vids.length) {
      box.append(el("div", { class: "empty-state", style: "grid-column:1/-1" }, "No rendered videos on the server yet."));
      return;
    }
    for (const v of vids) {
      box.append(el("div", { class: "card" },
        el("video", { src: v.url, controls: "", preload: "metadata" }),
        el("div", { class: "card-info" },
          el("div", { class: "card-name" }, el("span", {}, v.name.replace(/\.mp4$/, ""))),
          el("div", { class: "card-meta" },
            metaBadge(v.render_meta),
            el("span", { class: "chip dim plain" }, v.source === "merged_final" ? "merged" : "lab"),
            el("span", { class: "card-age" }, `${v.size_mb} MB`)))));
    }
  } catch (e) {
    box.innerHTML = "";
    box.append(el("div", { class: "empty-state", style: "grid-column:1/-1" }, `Could not load render history: ${e.message}`));
  }
}

// ───────────────────────── studio shell ─────────────────────────

async function enterStudio(p) {
  project = p;
  await refreshTheme();
  selScene = 0; selCue = -1; selTab = "content"; expandedEl = -1;
  $("#view-home").classList.add("hidden");
  $("#view-studio").classList.remove("hidden");
  document.title = `${p.topic} — Studio`;
  $$(".insp-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === selTab));
  studioProg.hide();
  renderAll();
  if (p.lastRender && p.lastRender.video_url) showVideoTab(false);
  else showBlueprintTab();
  if (p.activeJob) { studioProg.start("Rendering", "Reattaching to a render started earlier…"); attachToJob(p.activeJob); }
}

function leaveStudio() {
  detachRenderUI();
  studioProg.hide();
  project = null;
  $("#view-studio").classList.add("hidden");
  $("#view-home").classList.remove("hidden");
  document.title = "Studio — STEM Animation Lab";
  renderProjectList(); renderHistoryList();
}

function renderAll() {
  refreshTopbar(); renderRail(); renderCanvas(); renderCueStrip(); renderInspector();
}

function refreshTopbar() {
  $("#studio-title").textContent = project.topic;
  const chips = $("#studio-chips");
  chips.innerHTML = "";
  chips.append(el("span", { class: "chip dim plain" }, `${scenes().length} scenes`));
  const lr = project.lastRender;
  if (lr) {
    chips.append(metaBadge(lr));
    if ((lr.voice_degraded || 0) > 0) chips.append(el("span", { class: "chip warn" }, `voice ×${lr.voice_degraded}`));
  } else chips.append(el("span", { class: "chip dim" }, "not rendered"));
  const d = dirtyCount();
  if (d > 0 && lr) chips.append(el("span", { class: "chip edited" }, `${d} edited`));

  const label = $("#render-label"), btn = $("#btn-render");
  if (render.active) { label.textContent = "Rendering…"; btn.disabled = true; }
  else {
    btn.disabled = false;
    label.textContent = lr ? (d > 0 ? `Re-render (${d} changed)` : "Re-render") : "Render video";
  }
}

// ───────────────────────── scene rail ─────────────────────────

let dragFrom = -1;

function renderRail() {
  const rail = $("#scene-rail");
  rail.innerHTML = "";
  scenes().forEach((sc, i) => {
    const pic = el("div", { class: "thumb-pic" });
    pic.innerHTML = blueprintSVG(sc, project.settings.aspect_ratio, { tiny: true });
    const th = el("div", {
      class: `thumb${i === selScene ? " on" : ""}`, draggable: true,
      onclick: () => { selScene = i; selCue = -1; expandedEl = -1; renderAll(); },
      ondragstart: (e) => { dragFrom = i; th.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; },
      ondragend: () => { dragFrom = -1; $$(".thumb").forEach((t) => t.classList.remove("dragging", "dragover")); },
      ondragover: (e) => { e.preventDefault(); th.classList.add("dragover"); },
      ondragleave: () => th.classList.remove("dragover"),
      ondrop: (e) => { e.preventDefault(); th.classList.remove("dragover"); if (dragFrom >= 0 && dragFrom !== i) moveScene(dragFrom, i); },
    },
      pic,
      el("button", { class: "thumb-menu", title: "Scene actions", onclick: (ev) => { ev.stopPropagation(); sceneMenu(ev, i); } }, "⋮"),
      el("div", { class: "thumb-title" },
        el("span", { class: "thumb-n" }, String(i + 1).padStart(2, "0")),
        el("span", { class: "thumb-name" }, sc.description || "Untitled scene")),
      el("div", { class: "thumb-sub" },
        el("span", { class: `dot ${railDot(i)}` }),
        railStatusText(i)),
    );
    rail.append(th);
  });
  rail.append(el("div", { class: "thumb add", title: "Add a scene", onclick: addScene }, "+"));
}

const railDot = (i) => !project.lastRender ? "off" : (isDirty(i) ? "warn" : "ok");
const railStatusText = (i) => !project.lastRender ? "not rendered" : (isDirty(i) ? "edited" : "rendered");

function refreshRailDots() {
  $$("#scene-rail .thumb:not(.add)").forEach((th, i) => {
    const dot = th.querySelector(".dot"), sub = th.querySelector(".thumb-sub");
    if (!dot || !sub) return;
    dot.className = `dot ${railDot(i)}`;
    sub.childNodes[1].textContent = railStatusText(i);
    const name = th.querySelector(".thumb-name");
    if (name) name.textContent = scenes()[i].description || "Untitled scene";
  });
}

function renumber() { scenes().forEach((sc, i) => { sc.scene_index = i + 1; }); }

function moveScene(from, to) {
  const arr = scenes();
  const [sc] = arr.splice(from, 1);
  arr.splice(to, 0, sc);
  const sigs = project.renderedSigs || [];
  const [sg] = sigs.splice(from, 1);
  sigs.splice(to, 0, sg);
  renumber();
  selScene = to;
  save(); renderAll();
}

function newSceneTemplate(idx) {
  return {
    scene_index: idx + 1, description: "New scene", elements: [],
    narration_cues: [{ cue: "", event: "", animation_events: [] }],
    wait_time: 1, composition: null, layout_template: null,
  };
}

function addScene() {
  scenes().push(newSceneTemplate(scenes().length));
  (project.renderedSigs = project.renderedSigs || []).push(null);
  selScene = scenes().length - 1; selCue = -1;
  save(); renderAll();
  $("#scene-rail").scrollLeft = $("#scene-rail").scrollWidth;
}

function sceneMenu(ev, i) {
  $$(".ctx").forEach((m) => m.remove());
  const m = el("div", { class: "ctx" },
    el("button", { onclick: () => { m.remove(); duplicateScene(i); } }, "Duplicate scene"),
    el("button", { class: "danger", onclick: () => { m.remove(); deleteScene(i); } }, "Delete scene"),
  );
  document.body.append(m);
  const r = ev.target.getBoundingClientRect();
  m.style.left = `${Math.min(r.left, window.innerWidth - 170)}px`;
  m.style.top = `${Math.max(8, r.top - m.offsetHeight - 6)}px`;
  setTimeout(() => document.addEventListener("click", () => m.remove(), { once: true }), 0);
}

function duplicateScene(i) {
  scenes().splice(i + 1, 0, structuredClone(scenes()[i]));
  (project.renderedSigs = project.renderedSigs || []).splice(i + 1, 0, null);
  renumber();
  selScene = i + 1;
  save(); renderAll();
}

function deleteScene(i) {
  if (scenes().length <= 1) { toast("A video needs at least one scene", "warn"); return; }
  if (!confirm(`Delete scene ${i + 1} — “${scenes()[i].description || "untitled"}”?`)) return;
  scenes().splice(i, 1);
  (project.renderedSigs || []).splice(i, 1);
  renumber();
  selScene = Math.min(selScene, scenes().length - 1);
  save(); renderAll();
}

// ───────────────────────── canvas + cue strip ─────────────────────────

function showBlueprintTab() {
  $("#cv-tab-bp").classList.add("on"); $("#cv-tab-vid").classList.remove("on");
  $("#canvas-blueprint").classList.remove("hidden"); $("#canvas-video").classList.add("hidden");
}

function showVideoTab(autoplay) {
  const lr = project.lastRender;
  if (!lr || !lr.video_url) return;
  $("#cv-tab-vid").disabled = false;
  $("#cv-tab-vid").classList.add("on"); $("#cv-tab-bp").classList.remove("on");
  $("#canvas-video").classList.remove("hidden"); $("#canvas-blueprint").classList.add("hidden");
  const v = $("#studio-video");
  if (v.getAttribute("src") !== lr.video_url) { v.src = lr.video_url; v.load(); }
  if (autoplay) v.play().catch(() => {});
  refreshVideoAudioBar();
}

function refreshVideoAudioBar() {
  if (!project) return;
  const s = project.settings || {};
  const currentProvider = s.tts_provider || "sarvam";
  const currentSpeaker = s.speaker || "shubh";
  const lang = s.language || "hi-IN";

  const label = $("#video-voice-label");
  if (label) {
    label.textContent = `${currentProvider.toUpperCase()} · ${currentSpeaker}`;
  }

  const sel = $("#video-voice-select");
  if (!sel) return;
  sel.innerHTML = "";

  const providers = [
    { id: "sarvam", label: "Sarvam AI" },
    { id: "edge", label: "Edge TTS (Free)" },
    { id: "local", label: "Local Kokoro (Free)" },
    { id: "gemini", label: "Gemini TTS" },
  ];

  providers.forEach((p) => {
    const list = getVoicesFor(p.id, lang);
    if (!list || !list.length) return;
    const optgroup = document.createElement("optgroup");
    optgroup.label = p.label;
    list.forEach((spk) => {
      const opt = el("option", { value: `${p.id}:${spk}` }, `${spk}`);
      if (p.id === currentProvider && spk === currentSpeaker) {
        opt.selected = true;
      }
      optgroup.append(opt);
    });
    sel.append(optgroup);
  });
}

function renderCanvas() {
  const sc = scene();
  if (!sc) return;
  const bpContainer = $("#canvas-blueprint");
  bpContainer.innerHTML = blueprintSVG(sc, project.settings.aspect_ratio);
  _applyKatexToBlueprint(bpContainer);
  $("#cv-tab-vid").disabled = !(project.lastRender && project.lastRender.video_url);
  const cap = $("#scene-caption");
  cap.innerHTML = "";
  cap.append(
    el("b", {}, `Scene ${selScene + 1}`),
    ` · ${(sc.elements || []).length} elements · ${(sc.narration_cues || []).length} cues`,
    sc.composition ? ` — ${sc.composition}` : "");
}

function renderCueStrip() {
  const strip = $("#cue-strip");
  strip.innerHTML = "";
  const cues = (scene() && scene().narration_cues) || [];
  cues.forEach((_, i) => {
    strip.append(el("button", {
      class: `cue-seg${i === selCue ? " on" : ""}`,
      title: `Cue ${i + 1}`,
      onclick: () => {
        selCue = selCue === i ? -1 : i;
        renderCueStrip();
        if (selTab === "audio" || selTab === "motion") {
          renderInspector();
          const card = $(`#cue-${selTab}-${i}`);
          if (card) card.scrollIntoView({ block: "center", behavior: "smooth" });
        }
      },
    }));
  });
  $("#cue-count").textContent = cues.length ? (selCue >= 0 ? `${selCue + 1} / ${cues.length}` : `${cues.length}`) : "none";
}

// ───────────────────────── inspector ─────────────────────────

function renderInspector() {
  const body = $("#insp-body");
  body.innerHTML = "";
  const sc = scene();
  if (!sc) return;
  if (selTab === "content") renderContentTab(body, sc);
  else if (selTab === "motion") renderMotionTab(body, sc);
  else if (selTab === "audio") renderAudioTab(body, sc);
  else renderStyleTab(body, sc);
}

const elementIds = (sc) => (sc.elements || []).map((e) => e.id);

function slugId(sc, content) {
  const base = (content || "element").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 24) || "element";
  let id = base, n = 2;
  while (elementIds(sc).includes(id)) id = `${base}_${n++}`;
  return id;
}

const sectionTitle = (text) => el("div", { class: "t-eyebrow" }, text);

// --- Content ---

function renderContentTab(body, sc) {
  const s1 = el("div", { class: "insp-sect" }, sectionTitle("Scene"));
  s1.append(el("div", { class: "field" },
    el("label", {}, "Title / description"),
    el("textarea", {
      value: sc.description || "", rows: 2,
      oninput: (e) => { sc.description = e.target.value; onEdit(); },
      onchange: () => refreshRailDots(),
    })));
  s1.append(el("div", { class: "field" },
    el("label", {}, "Composition"),
    el("textarea", {
      value: sc.composition || "", rows: 2,
      placeholder: "Title banner top, coordinate grid centre, derivation stacked right column",
      oninput: (e) => { sc.composition = e.target.value || null; onEdit(); },
    }),
    el("div", { class: "hint" }, "The layout gestalt. The transpiler reads this before making zone decisions.")));
  body.append(s1);

  const s2 = el("div", { class: "insp-sect" }, sectionTitle(`Elements · ${(sc.elements || []).length}`));
  (sc.elements || []).forEach((e, i) => s2.append(elementCard(sc, e, i)));
  s2.append(el("button", {
    class: "add-row", onclick: () => {
      sc.elements = sc.elements || [];
      sc.elements.push({
        id: slugId(sc, "new_text"), type: "text", content: "New text",
        color: null, entrance_animation: "FadeIn", exit_animation: "FadeOut",
        scale: 0.7, absolute_position: null, relative_positioning: null, safe_zone_alignment: null,
      });
      expandedEl = sc.elements.length - 1;
      onEdit({ canvas: true }); renderInspector();
    },
  }, "+  Add element"));
  body.append(s2);
}

function contentHint(type) {
  if (type === "math" || type === "math_evolution")
    return "LaTeX without surrounding $. For math_evolution use FROM → TO with a literal arrow.";
  if (type === "svg_icon") return "One clean English search keyword, e.g. “telescope”.";
  if (type === "chemical_molecule") return "A valid SMILES string, e.g. “CCO” for ethanol.";
  if (type === "coordinate_system" || type === "graph")
    return "Include axis ranges: “time vs velocity x:0-10, y:0-50”.";
  return "";
}

function elementCard(sc, e, i) {
  const open = expandedEl === i;
  const card = el("div", { class: `el${open ? " open" : ""}` });
  card.append(el("div", {
    class: "el-head",
    onclick: () => { expandedEl = open ? -1 : i; renderInspector(); },
  },
    el("span", { class: "el-tag" }, e.type || "text"),
    el("span", { class: "el-title" }, e.content || e.id),
    el("span", { class: "el-caret" }, "▸")));
  if (!open) return card;

  const b = el("div", { class: "el-body" });
  b.append(el("div", { class: "el-id" }, `id: ${e.id}`));
  b.append(el("div", { class: "row-2" },
    el("div", { class: "field" }, el("label", {}, "Type"),
      sel(EL_TYPES, e.type || "text", (v) => { e.type = v; onEdit({ canvas: true }); renderInspector(); })),
    el("div", { class: "field" }, el("label", {}, "Scale"),
      el("input", {
        type: "number", step: "0.1", min: "0.1", max: "2", value: e.scale ?? 0.7,
        oninput: (ev) => { e.scale = parseFloat(ev.target.value) || 0.7; onEdit({ canvas: true }); },
      }))));
  const hint = contentHint(e.type);
  const isMathType = e.type === "math" || e.type === "math_evolution";
  const mathPreview = isMathType ? el("div", { class: "katex-preview" }) : null;
  if (mathPreview && window.katex && e.content) {
    try { katex.render(e.content, mathPreview, { throwOnError: false, displayMode: true }); }
    catch (_) { mathPreview.textContent = e.content; }
  }
  b.append(el("div", { class: "field" },
    el("label", {}, "Content"),
    el("textarea", {
      value: e.content || "", rows: 2,
      oninput: (ev) => {
        e.content = ev.target.value; onEdit({ canvas: true });
        if (mathPreview && window.katex) {
          mathPreview.textContent = "";
          try { katex.render(e.content, mathPreview, { throwOnError: false, displayMode: true }); }
          catch (_) { mathPreview.textContent = e.content; }
        }
      },
    }),
    hint ? el("div", { class: "hint" }, hint) : null,
    mathPreview));
  b.append(el("div", { class: "row-2" },
    el("div", { class: "field" }, el("label", {}, "Colour"),
      el("input", {
        type: "text", value: e.color || "", placeholder: "auto (theme)",
        oninput: (ev) => { e.color = ev.target.value.trim() || null; onEdit({ canvas: true }); },
      })),
    el("div", { class: "field" }, el("label", {}, "Zone"),
      sel([["", "auto"], ...ZONES.map((z) => [z, z])], e.safe_zone_alignment || "",
        (v) => { e.safe_zone_alignment = v || null; onEdit({ canvas: true }); }))));

  if (e.relative_positioning) {
    b.append(el("div", { class: "field" }, el("div", { class: "anchor-note" },
      el("span", {}, "Anchored to"),
      el("span", { class: "mono" }, e.relative_positioning.relative_to),
      el("span", {}, e.relative_positioning.direction),
      el("button", { class: "btn tiny", style: "margin-left:auto", onclick: () => { e.relative_positioning = null; onEdit({ canvas: true }); renderInspector(); } }, "detach"))));
  }
  if (Array.isArray(e.absolute_position)) {
    b.append(el("div", { class: "field" }, el("div", { class: "anchor-note" },
      el("span", {}, "Fixed at"),
      el("span", { class: "mono" }, `[${e.absolute_position.join(", ")}]`),
      el("button", { class: "btn tiny", style: "margin-left:auto", onclick: () => { e.absolute_position = null; onEdit({ canvas: true }); renderInspector(); } }, "clear"))));
  }
  b.append(el("button", {
    class: "btn tiny danger", onclick: () => {
      const removed = removeElementEvents(sc, e.id);
      sc.elements.splice(i, 1);
      expandedEl = -1;
      onEdit({ canvas: true }); renderInspector();
      toast(removed ? `Element deleted, plus ${removed} event${removed > 1 ? "s" : ""} that referenced it` : "Element deleted");
    },
  }, "Delete element"));
  card.append(b);
  return card;
}

function removeElementEvents(sc, id) {
  let removed = 0;
  for (const cue of sc.narration_cues || []) {
    if (!cue.animation_events) continue;
    const before = cue.animation_events.length;
    cue.animation_events = cue.animation_events.filter((ev) => ev.target !== id && ev.to !== id);
    removed += before - cue.animation_events.length;
  }
  return removed;
}

// --- Motion ---

function renderMotionTab(body, sc) {
  const s1 = el("div", { class: "insp-sect" }, sectionTitle("Entrances & exits"));
  s1.append(el("div", { class: "hint", style: "margin:-4px 0 10px" },
    "“auto” uses the per-type defaults: text fades, math writes, shapes follow their keyword (arrow grows, line draws)."));
  (sc.elements || []).forEach((e) => {
    s1.append(el("div", { class: "mrow" },
      el("span", { class: "el-tag" }, e.type || "text"),
      el("span", { class: "el-title" }, e.content || e.id),
      sel([["", "auto"], ...ENTRANCES.map((a) => [a, a])],
        ENTRANCES.includes(e.entrance_animation) ? e.entrance_animation : "",
        (v) => { e.entrance_animation = v || ""; onEdit(); }, { title: "Entrance animation" }),
      sel([["", "auto"], ...EXITS.map((a) => [a, a])],
        EXITS.includes(e.exit_animation) ? e.exit_animation : "",
        (v) => { e.exit_animation = v || ""; onEdit(); }, { title: "Exit animation" })));
  });
  if (!(sc.elements || []).length) s1.append(el("div", { class: "empty-state" }, "No elements yet — add them in the Content tab."));
  body.append(s1);

  const s2 = el("div", { class: "insp-sect" }, sectionTitle("Events per cue"));
  s2.append(el("div", { class: "hint", style: "margin:-4px 0 10px" },
    "Targets only list this scene's elements — a per-scene render can't reference another scene's objects."));
  (sc.narration_cues || []).forEach((cue, ci) => s2.append(motionCueCard(sc, cue, ci)));
  body.append(s2);
}

function evtLabel(ev) {
  return `${ev.action}(${ev.target || "?"}${ev.to ? ` → ${ev.to}` : ""})`;
}

function motionCueCard(sc, cue, ci) {
  const ids = elementIds(sc);
  const card = el("div", { class: `cue${ci === selCue ? " sel" : ""}`, id: `cue-motion-${ci}` });
  card.append(el("div", { class: "cue-top" },
    el("span", { class: "cue-n" }, `CUE ${ci + 1}`),
    el("span", { class: "cue-preview" }, cue.cue || "(no narration)")));

  const foot = el("div", { class: "cue-foot" });
  (cue.animation_events || []).forEach((ev, ei) => {
    foot.append(el("span", { class: "evt" }, evtLabel(ev),
      el("span", {
        class: "evt-x", title: "Remove",
        onclick: () => { cue.animation_events.splice(ei, 1); onEdit(); renderInspector(); },
      }, "✕")));
  });
  if (cue.event && !(cue.animation_events || []).length) {
    foot.append(el("span", { class: "evt legacy", title: "Legacy free-text event, sanitized at codegen" }, `legacy: ${cue.event.slice(0, 36)}`));
  }
  if (!foot.children.length) foot.append(el("span", { class: "evt muted" }, "no events"));
  card.append(foot);

  const actionS = sel(EVENT_ACTIONS, "show", () => syncExtras(), { style: "flex:0 0 88px" });
  const targetS = sel(ids.length ? ids : [["", "—"]], ids[0] || "", () => {});
  const toS = sel(ids.length ? ids : [["", "—"]], ids[0] || "", () => {}, { title: "Destination element" });
  const colorI = el("input", { type: "text", placeholder: "YELLOW" });
  const dirS = sel(DIRECTIONS, "RIGHT", () => {}, { style: "flex:0 0 96px" });
  const addB = el("button", {
    class: "btn tiny", onclick: () => {
      if (!ids.length) { toast("Add an element first", "warn"); return; }
      const a = actionS.value;
      const ev = { action: a, target: targetS.value };
      if (a === "transform" || a === "move_to") ev.to = toS.value;
      if (a === "highlight" && colorI.value.trim()) ev.color = colorI.value.trim();
      if (a === "move_to") ev.direction = dirS.value;
      cue.animation_events = cue.animation_events || [];
      cue.animation_events.push(ev);
      onEdit(); renderInspector();
    },
  }, "add");
  const syncExtras = () => {
    const a = actionS.value;
    toS.style.display = (a === "transform" || a === "move_to") ? "" : "none";
    colorI.style.display = a === "highlight" ? "" : "none";
    dirS.style.display = a === "move_to" ? "" : "none";
  };
  syncExtras();
  card.append(el("div", { class: "evt-add" }, actionS, targetS, toS, colorI, dirS, addB));
  return card;
}

// --- Audio ---

function renderAudioTab(body, sc) {
  const s = project.settings;
  const s1 = el("div", { class: "insp-sect" }, sectionTitle("Voice"));
  const speakerHolder = el("div", { class: "field" });

  const speakerSelect = () => {
    const list = getVoicesFor(s.tts_provider, s.language);
    if (!list.includes(s.speaker)) s.speaker = list[0];
    speakerHolder.innerHTML = "";
    speakerHolder.append(el("label", {}, "Speaker"), sel(list, s.speaker, (v) => { s.speaker = v; onEdit(); }));
  };

  s1.append(el("div", { class: "row-2" },
    el("div", { class: "field" }, el("label", {}, "Persona"),
      sel([["hybrid", "Hinglish"], ["native", "Native"], ["en", "English"]], s.persona, (v) => { s.persona = v; onEdit(); })),
    el("div", { class: "field" }, el("label", {}, "Language"),
      sel(VOICES.languages.map((l) => [l.code, l.label]), s.language, (v) => { s.language = v; speakerSelect(); onEdit(); }))));
  s1.append(el("div", { class: "row-2" },
    el("div", { class: "field" }, el("label", {}, "Provider"),
      sel([
        ["sarvam", "Sarvam AI"],
        ["gemini", "Gemini TTS"],
        ["edge", "Edge TTS (Free)"],
        ["local", "Local (Kokoro)"]
      ], s.tts_provider, (v) => { s.tts_provider = v; speakerSelect(); onEdit(); })),
    speakerHolder));
  speakerSelect();
  const conf = VOICES.providers_configured || {};
  if (s.tts_provider === "sarvam" && conf.sarvam === false) {
    s1.append(el("div", { class: "hint" }, "No Sarvam key on this server — previews and renders fall back to Gemini TTS."));
  } else if (s.tts_provider === "edge") {
    s1.append(el("div", { class: "hint" }, "Edge TTS: Microsoft neural voices (free, requires network)."));
  } else if (s.tts_provider === "local" || s.tts_provider === "kokoro") {
    s1.append(el("div", { class: "hint" }, "Local TTS: Kokoro-82M on-device CPU model (free, runs locally)."));
  }
  s1.append(el("div", { class: "hint" }, "Voice settings apply to the whole video and mark every scene for re-render."));
  body.append(s1);

  const s2 = el("div", { class: "insp-sect" }, sectionTitle(`Narration · ${(sc.narration_cues || []).length} cues`));
  (sc.narration_cues || []).forEach((cue, ci) => s2.append(audioCueCard(sc, cue, ci)));
  s2.append(el("button", {
    class: "add-row", onclick: () => {
      sc.narration_cues = sc.narration_cues || [];
      sc.narration_cues.push({ cue: "", event: "", animation_events: [] });
      onEdit(); renderInspector(); renderCueStrip();
    },
  }, "+  Add cue"));
  body.append(s2);
}

function audioCueCard(sc, cue, ci) {
  const playBtn = el("button", { class: "btn tiny", title: "Audition this cue" }, "▶");
  playBtn.addEventListener("click", async () => {
    const text = (cue.cue || "").trim();
    if (!text) { toast("This cue has no narration yet", "warn"); return; }
    playBtn.disabled = true; playBtn.textContent = "…";
    try {
      const s = project.settings;
      const r = await api("/api/tts/preview", {
        text, language: s.language, tts_provider: s.tts_provider, speaker: s.speaker,
      });
      const audio = $("#preview-audio");
      audio.src = r.url; audio.play();
      if (r.note && !audioCueCard._noted) { toast(r.note, "warn"); audioCueCard._noted = true; }
    } catch (e) { toast(`Preview failed: ${e.message}`, "error"); }
    finally { playBtn.disabled = false; playBtn.textContent = "▶"; }
  });

  const nEvents = (cue.animation_events || []).length;
  return el("div", { class: `cue${ci === selCue ? " sel" : ""}`, id: `cue-audio-${ci}` },
    el("div", { class: "cue-top" },
      el("span", { class: "cue-n" }, `CUE ${ci + 1}`),
      el("span", { class: "spacer" }),
      playBtn,
      el("button", {
        class: "btn tiny", title: "Delete cue", onclick: () => {
          if ((cue.cue || "").trim() && !confirm(`Delete cue ${ci + 1}?`)) return;
          sc.narration_cues.splice(ci, 1);
          if (selCue >= sc.narration_cues.length) selCue = -1;
          onEdit(); renderInspector(); renderCueStrip();
        },
      }, "✕")),
    el("textarea", {
      value: cue.cue || "", rows: 2, placeholder: "What the narrator says on this beat…",
      oninput: (e) => { cue.cue = e.target.value; onEdit(); },
      onfocus: () => { selCue = ci; renderCueStrip(); },
    }),
    el("div", { class: "cue-foot" },
      nEvents
        ? el("span", { class: "evt", title: "Edit in the Motion tab" }, `${nEvents} event${nEvents > 1 ? "s" : ""}`)
        : el("span", { class: "evt muted" }, "no events")));
}

// --- Style ---

function renderStyleTab(body, sc) {
  const s = project.settings;
  const s1 = el("div", { class: "insp-sect" }, sectionTitle("This scene"));
  s1.append(el("div", { class: "row-2" },
    el("div", { class: "field" }, el("label", {}, "Layout template"),
      sel(TEMPLATES.map((t) => [t, t || "auto"]), sc.layout_template || "",
        (v) => { sc.layout_template = v || null; onEdit({ canvas: true }); })),
    el("div", { class: "field" }, el("label", {}, "End pause (s)"),
      el("input", {
        type: "number", step: "0.5", min: "0", max: "10", value: sc.wait_time ?? 1,
        oninput: (e) => { sc.wait_time = parseFloat(e.target.value) || 0; onEdit(); },
      }))));
  body.append(s1);

  const s2 = el("div", { class: "insp-sect" }, sectionTitle("Whole video"));
  s2.append(el("div", { class: "field" }, el("label", {}, "Visual style"),
    sel(STYLES, s.style, (v) => {
      s.style = v;
      refreshTheme().then(() => { renderCanvas(); renderRail(); });
      const bg = styleToBackground(v);
      if (bg !== s.background) { s.background = bg; toast(`Background switched to “${bg}” to match the style`); renderInspector(); }
      onEdit({ canvas: true });
    })));
  s2.append(el("div", { class: "field" }, el("label", {}, "Canvas background"),
    sel(BACKGROUNDS, s.background, (v) => {
      s.background = v;
      refreshTheme().then(() => { renderCanvas(); renderRail(); });
      onEdit();
    })));
  s2.append(el("div", { class: "row-2" },
    el("div", { class: "field" }, el("label", {}, "Quality"),
      sel([["l", "Low — fast"], ["m", "Medium"], ["h", "High — slow"]], s.quality, (v) => { s.quality = v; onEdit(); })),
    el("div", { class: "field" }, el("label", {}, "Aspect"),
      sel([["widescreen", "16:9"], ["vertical", "9:16"]], s.aspect_ratio, (v) => { s.aspect_ratio = v; onEdit({ canvas: true }); }))));
  const llmProvList = [
    ["auto", "Auto (Default priority)"],
    ["anthropic", "Anthropic API"],
    ["openrouter", "OpenRouter"],
    ["gemini", "Google Gemini"],
    ["groq", "Groq"]
  ];
  s2.append(el("div", { class: "row-2" },
    el("div", { class: "field" }, el("label", {}, "AI Provider"),
      sel(llmProvList, s.llm_provider || "auto", (v) => {
        s.llm_provider = v;
        s.llm_model = "auto";
        onEdit();
        renderInspector();
      })),
    el("div", { class: "field" }, el("label", {}, "AI Model"),
      sel((LLM_MODELS_BY_PROVIDER[s.llm_provider || "auto"] || LLM_MODELS_BY_PROVIDER.auto).map((m) => [m.value, m.label]), s.llm_model || "auto", (v) => {
        s.llm_model = v;
        onEdit();
      }))));
  s2.append(el("div", { class: "hint" }, "These apply to every scene, so changing one marks the whole video for re-render."));
  body.append(s2);

  const s3 = el("div", { class: "insp-sect" }, sectionTitle("Scene actions"),
    el("div", { style: "display:flex;gap:8px" },
      el("button", { class: "btn tiny", onclick: () => duplicateScene(selScene) }, "Duplicate"),
      el("button", { class: "btn tiny danger", onclick: () => deleteScene(selScene) }, "Delete")));
  body.append(s3);
}

// ───────────────────────── render flow ─────────────────────────

function detachRenderUI() {
  clearTimeout(render.pollT);
  if (render.ws) { try { render.ws.close(); } catch (_) {} }
  render.active = false; render.ws = null; render.pollT = null;
}

async function startRender() {
  if (render.active || !project) return;
  render.active = true;
  refreshTopbar();
  studioProg.start("Generating code", "Transpiling the storyboard into Manim, then reviewing layout.");
  try {
    const s = project.settings;
    // Codegen as a polled task: the model chain can take minutes, and a
    // held-open fetch dies long before it finishes.
    const codegen = await runTask("/api/tasks/codegen", {
      storyboard: project.storyboard,
      style: s.style, background: s.background, persona: s.persona,
      language: s.language, speaker: s.speaker, tts_provider: s.tts_provider,
      llm_provider: s.llm_provider, llm_model: s.llm_model,
    }, (t) => {
      if (t.progress) studioProg.say(t.progress);
      studioProg.lines(t.progress_lines);
    });

    render.codegen = codegen;
    project.lastCode = codegen.code || null;
    if (codegen.valid === false) {
      toast(`Code still has a syntax issue after auto-repair: ${codegen.validation_error}`, "warn");
    }
    const nScripts = (codegen.scene_scripts || []).length;
    studioProg.phase("Rendering", nScripts > 1
      ? `Rendering ${nScripts} scenes in parallel, then joining them.`
      : "Rendering…");

    const resp = await api("/api/compile_video", {
      code: codegen.code,
      scene_class: codegen.scene_class || "STEMAnimation",
      quality: s.quality, aspect_ratio: s.aspect_ratio, persona: s.persona,
      scene_scripts: nScripts > 1 ? codegen.scene_scripts : null,
    });
    project.activeJob = resp.job_id;
    save();
    attachToJob(resp.job_id);
  } catch (e) {
    render.active = false;
    detachRenderUI();
    studioProg.fail(e.message);
    refreshTopbar();
    toast(`Could not start the render: ${e.message}`, "error");
  }
}

function attachToJob(jobId) {
  render.active = true;
  render.jobId = jobId;
  refreshTopbar();

  let finished = false;
  const finish = (job) => { if (!finished) { finished = true; finalizeRender(job); } };

  let misses = 0;
  const poll = async () => {
    if (finished) return;
    try {
      const job = await api(`/api/render_status/${jobId}`);
      misses = 0;
      handleJobTick(job);
      if (job.state === "done" || job.state === "error") { finish(job); return; }
    } catch (e) {
      if (e.status === 404) {
        finish({ state: "error", error: "The server restarted and lost this render job." });
        return;
      }
      if (++misses >= 8) {
        finish({ state: "error", error: `Lost contact with the render job: ${e.message}` });
        return;
      }
    }
    render.pollT = setTimeout(poll, 2000);
  };

  try {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${location.host}/ws/render_status/${jobId}`);
    render.ws = ws;
    ws.onmessage = (e) => {
      try {
        const job = JSON.parse(e.data);
        handleJobTick(job);
        if (job.state === "done" || job.state === "error") finish(job);
      } catch (_) {}
    };
    ws.onerror = () => { if (!finished && !render.pollT) poll(); };
    ws.onclose = () => { if (!finished && !render.pollT) poll(); };
  } catch (_) { poll(); }
}

function handleJobTick(job) {
  render.lastJob = job;
  const bits = [];
  if (job.progress) bits.push(job.progress);
  else bits.push(`state: ${job.state}`);
  if (job.repair_rounds) bits.push(`repair rounds: ${job.repair_rounds}`);
  studioProg.say(bits.join("  ·  "));
}

function finalizeRender(job) {
  detachRenderUI();
  render.lastJob = job;
  project.activeJob = null;

  if (job.state === "done" && job.success && job.video_url) {
    project.lastRender = {
      video_url: job.video_url,
      job_id: job.job_id || render.jobId,
      at: Date.now(),
      repair_rounds: job.repair_rounds || 0,
      violations_remaining: job.violations_remaining ?? null,
      voice_degraded: Array.isArray(job.voice_degraded) ? job.voice_degraded.length : (job.voice_degraded || 0),
      vision_findings: Array.isArray(job.vision_report) ? job.vision_report.length : 0,
      render_seconds: job.render_duration_seconds || null,
      beats: job.animation_beats || null,
    };
    project.renderedSigs = scenes().map((sc) => sceneSig(sc));
    save();
    studioProg.done(`Rendered in ${job.render_duration_seconds ? Math.round(job.render_duration_seconds) + "s" : fmtSecs(studioProg.elapsedSecs())}` +
      (job.repair_rounds ? ` · ${job.repair_rounds} repair round${job.repair_rounds > 1 ? "s" : ""}` : ""));
    setTimeout(() => studioProg.hide(), 6000);
    refreshTopbar(); renderRail(); renderCanvas();
    showVideoTab(true);
    toast("Video rendered.");
  } else {
    save();
    // The server classifies failures (infra / latex / code) into job.error —
    // an infra failure means retry later, not edit the storyboard.
    studioProg.fail(job.error || "Render failed. Open Advanced → Logs for the full output.");
    refreshTopbar();
    toast(project.lastRender
      ? "Render failed — your previous video is untouched."
      : "Render failed — see the error panel.", "error");
  }
}

// ───────────────────────── advanced drawer ─────────────────────────

function openDrawer() {
  $("#drawer").classList.remove("hidden");
  fillDrawer();
}

function fillDrawer() {
  const sb = project ? project.storyboard : null;
  $("#adv-json").textContent = sb ? JSON.stringify(sb, null, 2) : "No storyboard.";
  $("#adv-code").textContent = (render.codegen && render.codegen.code) || (project && project.lastCode) ||
    "No generated code yet — run a render first.";
  $("#adv-logs").textContent = (render.lastJob && render.lastJob.logs) || "No job logs in this session yet.";

  const rep = $("#adv-report");
  rep.innerHTML = "";
  const lr = project && project.lastRender;
  if (lr) {
    const grid = el("div", { class: "report-grid" });
    const cell = (k, v, cls = "", sub = "") => grid.append(el("div", { class: "rcell" },
      el("span", { class: "t-eyebrow" }, k),
      el("div", { class: `rval ${cls}` }, String(v)),
      sub ? el("div", { class: "rsub" }, sub) : null));
    cell("Repair rounds", lr.repair_rounds, lr.repair_rounds ? "warn" : "good", lr.repair_rounds ? "layout was fixed" : "clean first pass");
    cell("Violations left", lr.violations_remaining ?? "—", (lr.violations_remaining || 0) > 0 ? "bad" : "good", "overlap / clipping");
    cell("Voice degraded", lr.voice_degraded, lr.voice_degraded ? "warn" : "good", lr.voice_degraded ? "fallback voice used" : "primary voice");
    cell("Vision findings", lr.vision_findings, lr.vision_findings ? "warn" : "good", "frame review");
    cell("Render time", lr.render_seconds ? `${Math.round(lr.render_seconds)}s` : "—");
    cell("Beats", lr.beats ?? "—", "", "animation steps");
    rep.append(grid);
  } else {
    rep.append(el("div", { class: "empty-state" },
      "No render yet. The verification report — repair rounds, layout violations, voice and vision findings — appears here after the first render."));
  }

  const list = (title, items) => {
    if (!items || !items.length) return;
    rep.append(el("div", { class: "report-h" }, title));
    rep.append(el("div", { class: "report-list" }, items.map((x) => (typeof x === "string" ? x : JSON.stringify(x))).join("\n")));
  };
  const job = render.lastJob || {};
  list("Vision report", job.vision_report);
  list("Layout warnings", job.bbox_warnings);
  list("Voice degradation", Array.isArray(job.voice_degraded) ? job.voice_degraded : null);
  list("Asset warnings", render.codegen && render.codegen.asset_warnings);
  list("Non-Manim items", sb && sb.non_manim_items && sb.non_manim_items.map((x) => (typeof x === "string" ? x : JSON.stringify(x))));
}

// ───────────────────────── wiring ─────────────────────────

function wire() {
  $("#btn-back").addEventListener("click", leaveStudio);
  $("#btn-render").addEventListener("click", startRender);
  $("#btn-advanced").addEventListener("click", openDrawer);
  $("#drawer-close").addEventListener("click", () => $("#drawer").classList.add("hidden"));
  $("#drawer-scrim").addEventListener("click", () => $("#drawer").classList.add("hidden"));
  $("#drawer-copy").addEventListener("click", () => {
    const pane = $(".pane.on");
    navigator.clipboard.writeText(pane.innerText).then(() => toast("Copied to clipboard"));
  });
  $$(".drawer-head [data-dtab]").forEach((b) => b.addEventListener("click", () => {
    $$(".drawer-head [data-dtab]").forEach((x) => x.classList.toggle("on", x === b));
    $$(".pane").forEach((p) => p.classList.remove("on"));
    $(`#adv-${b.dataset.dtab}`).classList.add("on");
  }));
  $$(".insp-tabs button").forEach((b) => b.addEventListener("click", () => {
    selTab = b.dataset.tab;
    $$(".insp-tabs button").forEach((x) => x.classList.toggle("on", x === b));
    renderInspector();
  }));
  $("#cv-tab-bp").addEventListener("click", showBlueprintTab);
  $("#cv-tab-vid").addEventListener("click", () => showVideoTab(false));
  const auditionVideoBtn = $("#btn-video-voice-audition");
  if (auditionVideoBtn) {
    auditionVideoBtn.addEventListener("click", async () => {
      if (!project) return;
      const selVal = $("#video-voice-select").value;
      if (!selVal) return;
      const [provider, speaker] = selVal.split(":");
      const s = project.settings || {};
      const sc = (scenes && scenes()[0]) || {};
      const text = (sc?.narration_cues?.[0]?.cue || "Hello, this is a lesson preview from Adhyay STEM Studio.").trim();
      const orig = auditionVideoBtn.textContent;
      auditionVideoBtn.textContent = "…";
      auditionVideoBtn.disabled = true;
      try {
        const r = await api("/api/tts/preview", {
          text,
          language: s.language || "hi-IN",
          tts_provider: provider,
          speaker: speaker,
        });
        const audio = $("#preview-audio");
        audio.src = r.url;
        audio.play();
        if (r.note) toast(r.note, "warn");
      } catch (e) {
        toast(`Audition failed: ${e.message}`, "error");
      } finally {
        auditionVideoBtn.textContent = orig;
        auditionVideoBtn.disabled = false;
      }
    });
  }

  const revoiceBtn = $("#btn-video-revoice");
  if (revoiceBtn) {
    revoiceBtn.addEventListener("click", () => {
      if (!project) return;
      const selVal = $("#video-voice-select").value;
      if (!selVal) return;
      const [provider, speaker] = selVal.split(":");
      project.settings.tts_provider = provider;
      project.settings.speaker = speaker;
      onEdit();
      refreshVideoAudioBar();
      toast(`Narration voice set to ${speaker} (${provider}). Rendering video…`, "info");
      startRender();
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#drawer").classList.contains("hidden")) $("#drawer").classList.add("hidden");
  });
}

async function init() {
  briefProg = makeProgress({
    panel: "#brief-prog", phase: "#brief-phase", text: "#brief-text",
    log: "#brief-log", err: "#brief-err", elapsed: "#brief-elapsed",
  });
  studioProg = makeProgress({
    panel: "#prog-panel", phase: "#prog-phase", text: "#prog-text",
    log: "#prog-log", err: "#prog-error", elapsed: "#prog-elapsed",
  });
  wire();
  try { VOICES = await api("/api/voices"); } catch (_) { /* built-in tables */ }
  initBrief();
  renderProjectList();
  renderHistoryList();
}

init();

})();

// KaTeX is a deferred CDN script: if the first canvas render ran before it was ready, draw the canvas again.
window.addEventListener("load", () => {
  try { if (window.katex && typeof project !== "undefined" && project && scene()) renderCanvas(); } catch (_) {}
});
