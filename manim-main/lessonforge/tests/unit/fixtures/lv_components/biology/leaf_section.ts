// Cross-section of a leaf: its layers, a stoma between two guard cells (opening 0 to 1), and which way and how much gas moves as the light changes.
type Pt = [number, number];
type Params = { label: string };
type State = { stoma?: "open" | "closed"; time?: "day" | "night"; opening?: number; light?: number };

export const meta = {
  id: "leaf_section",
  title: "Section through a leaf",
  subject: "biology",
  ncert: ["Class 7, Ch 1 Nutrition in Plants (stomata)", "Class 10, Ch 5 Life Processes (Fig 5.3 open and closed stomatal pore)", "Class 11, Ch 5 Anatomy of Flowering Plants (dorsiventral leaf)"],
  size: [400, 260] as Pt,
  params: {
    label: { type: "string", default: "leaf section", say: "a title for the drawing" },
  },
  parts: ["upper_epidermis", "palisade", "spongy", "vein", "lower_epidermis", "stoma", "light", "gases"],
  states: {
    stoma: ["open", "closed"],
    time: ["day", "night"],
    opening: { type: "number", min: 0, max: 1, default: 1, say: "how wide the stoma is: 0 closed, 1 fully open" },
    light: { type: "number", min: 0, max: 1, default: 1, say: "how bright the light is: 0 night, 1 bright sunlight; at about 0.25 food-making just matches respiration" },
  },
  anchors: ["stoma", "vein", "top"],
  layer: "actor",
  ground: 192,
  situations: {
    leaf_layers: { title: "The layers inside a leaf", ncert: "Class 11 Ch 5; Class 7 Ch 1", params: {}, steps: [
      { state: { stoma: "open", time: "day" }, show: ["upper_epidermis"], say: "This is a thin slice across a leaf. On top is a single layer of cells, the upper epidermis, coated with a waxy cuticle." },
      { show: ["upper_epidermis", "palisade"], say: "Below it are tall palisade cells packed with chloroplasts. Most food is made here." },
      { show: ["upper_epidermis", "palisade", "spongy"], say: "Then loose, rounded spongy cells with air spaces between them." },
      { show: ["upper_epidermis", "palisade", "spongy", "vein"], say: "A vein runs through the middle. Its xylem brings water and its phloem carries food away." },
      { show: ["upper_epidermis", "palisade", "spongy", "vein", "lower_epidermis", "stoma"], say: "The lower epidermis has tiny pores called stomata. Each one sits between two guard cells." },
    ] },
    stoma_open_close: { title: "Guard cells open and close the stoma", ncert: "Class 10 Ch 5, Fig 5.3", params: {}, steps: [
      { state: { stoma: "open", time: "day" }, show: ["upper_epidermis", "palisade", "spongy", "vein", "lower_epidermis", "stoma"], say: "When the guard cells swell with water, the pore between them opens." },
      { state: { stoma: "closed" }, say: "When they lose water, they close the pore, so the leaf loses less water." },
    ] },
    gases_day_night: { title: "Gases go in and out through the stomata", ncert: "Class 7 Ch 1; Class 10 Ch 5", params: {}, steps: [
      { state: { stoma: "open", time: "day" }, show: ["upper_epidermis", "palisade", "spongy", "vein", "lower_epidermis", "stoma", "light"], say: "In sunlight the leaf makes food." },
      { show: ["upper_epidermis", "palisade", "spongy", "vein", "lower_epidermis", "stoma", "light", "gases"], say: "Carbon dioxide goes in through the open stoma, and the oxygen made comes out." },
      { state: { time: "night" }, say: "At night there is no food making, only respiration: oxygen goes in and carbon dioxide comes out." },
      { state: { stoma: "closed" }, say: "When the stoma is closed, hardly any gas passes." },
    ] },
  },
  example: { label: "leaf section" },
};

const INK = "#1B2033";
const WAX = "#E9E2B8";
const SKIN = "#F4F1E6";
const PAL = "#BFE3B4";
const SPONGE = "#D8EFCF";
const CHLORO = "#1F9D55";
const GUARD = "#8ACB88";
const XYLEM = "#9AA1B8";
const PHLOEM = "#E8C9A0";
const SUN = "#F2A51A";
const CO2 = "#6B7189";
const O2 = "#0E8C8C";

export function validate(p: Params): string[] {
  const out: string[] = [];
  if (typeof p.label !== "string" || !p.label.trim()) out.push("label cannot be empty");
  else if (p.label.length > 14) out.push("label must be 14 characters or fewer so it fits beside the sun");
  return out;
}

const r1 = (n: number) => Math.round(n * 10) / 10;
const lead = (a: Pt, b: Pt) => `<line x1="${r1(a[0])}" y1="${r1(a[1])}" x2="${r1(b[0])}" y2="${r1(b[1])}" stroke="${INK}" stroke-width="1"/>`;
const arrow = (a: Pt, b: Pt, c: string) => {
  const ang = Math.atan2(b[1] - a[1], b[0] - a[0]), w = (t: number) => `${r1(b[0] - 9 * Math.cos(ang + t))} ${r1(b[1] - 9 * Math.sin(ang + t))}`;
  return `<line x1="${r1(a[0])}" y1="${r1(a[1])}" x2="${r1(b[0])}" y2="${r1(b[1])}" stroke="${c}" stroke-width="3" stroke-linecap="round"/>` +
    `<path d="M${w(0.5)} L${r1(b[0])} ${r1(b[1])} L${w(-0.5)}" fill="none" stroke="${c}" stroke-width="3" stroke-linejoin="round"/>`;
};

export function draw(p: Params, state: State = {}) {
  const cl = (v: number) => Math.min(1, Math.max(0, v));
  const o = cl(state.opening ?? ((state.stoma ?? "open") === "open" ? 1 : 0)), lt = cl(state.light ?? ((state.time ?? "day") === "day" ? 1 : 0));
  // food-making (grows with light) minus respiration (steady); > 0 takes CO2 in, < 0 gives it out
  const net = lt - 0.25, flow = (o * Math.abs(net)) / 0.75;
  const X0 = 150, X1 = 392, LX = 140, sx = 210, vx = 320, vy = 142;
  // Part 1: the waxy cuticle and one row of flat upper epidermis cells
  let upper_epidermis = `<rect x="${X0}" y="38" width="${X1 - X0}" height="4" fill="${WAX}" stroke="${INK}" stroke-width="1.5"/>`;
  for (let x = X0; x < X1; x += 22) upper_epidermis += `<rect x="${x}" y="42" width="${Math.min(22, X1 - x)}" height="16" fill="${SKIN}" stroke="${INK}" stroke-width="1.5"/>`;
  upper_epidermis += lead([LX, 34], [160, 40]) + lead([LX, 56], [158, 52]);
  // Part 2: tall palisade cells, each with chloroplasts
  let palisade = "";
  for (let x = X0 + 2; x + 14 <= X1; x += 16) {
    palisade += `<rect x="${x}" y="60" width="14" height="48" rx="6" fill="${PAL}" stroke="${INK}" stroke-width="1.5"/>` +
      `<circle cx="${x + 7}" cy="72" r="3" fill="${CHLORO}"/><circle cx="${x + 7}" cy="95" r="3" fill="${CHLORO}"/>`;
  }
  palisade += lead([LX, 84], [154, 84]);
  // Part 3: loose spongy cells; the gaps between them are air spaces (one kept open above the stoma)
  let spongy = "";
  [122, 146, 167].forEach((y, row) => {
    for (let i = 0, x = X0 + 12 + (row % 2) * 12; x <= X1 - 10; i++, x += 24) {
      if (Math.hypot(x - vx, y - vy) < 38 || (Math.abs(x - sx) < 22 && y > 140) || (i * 3 + row) % 7 === 0) continue;
      spongy += `<circle cx="${x}" cy="${y}" r="10.5" fill="${SPONGE}" stroke="${INK}" stroke-width="1.5"/><circle cx="${x - 3}" cy="${y - 2}" r="3" fill="${CHLORO}"/>`;
    }
  });
  spongy += lead([LX, 128], [158, 128]);
  // Part 4: a vein: xylem (thick-walled tubes, upper side) over phloem (smaller cells, lower side)
  let vein = `<ellipse cx="${vx}" cy="${vy}" rx="28" ry="24" fill="${SKIN}" stroke="${INK}" stroke-width="2"/>`;
  for (const [dx, dy] of [[-12, -9], [0, -12], [12, -9]]) vein += `<circle cx="${vx + dx}" cy="${vy + dy}" r="5" fill="${XYLEM}" stroke="${INK}" stroke-width="1.5"/>`;
  for (const [dx, dy] of [[-10, 8], [0, 11], [10, 8]]) vein += `<circle cx="${vx + dx}" cy="${vy + dy}" r="4" fill="${PHLOEM}" stroke="${INK}" stroke-width="1.5"/>`;
  vein += lead([LX, 152], [vx - 28, vy + 6]);
  // Part 5: the lower epidermis, broken where the stoma is
  let lower_epidermis = "";
  for (let x = X0; x < X1; x += 22) {
    const a = x, b = Math.min(x + 22, X1);
    if (b <= sx - 17 || a >= sx + 17) lower_epidermis += `<rect x="${a}" y="176" width="${b - a}" height="16" fill="${SKIN}" stroke="${INK}" stroke-width="1.5"/>`;
    else {
      if (a < sx - 17) lower_epidermis += `<rect x="${a}" y="176" width="${sx - 17 - a}" height="16" fill="${SKIN}" stroke="${INK}" stroke-width="1.5"/>`;
      if (b > sx + 17) lower_epidermis += `<rect x="${sx + 17}" y="176" width="${b - sx - 17}" height="16" fill="${SKIN}" stroke="${INK}" stroke-width="1.5"/>`;
    }
  }
  lower_epidermis += lead([LX, 184], [154, 184]);
  // Part 6: two guard cells; swollen and bowed apart (pore open) or slack and touching (pore closed)
  const g = r1(8.5 + 5.5 * o), gr = r1(8.5 + 0.5 * o);
  let stoma = `<ellipse cx="${sx - g}" cy="184" rx="${gr}" ry="9" fill="${GUARD}" stroke="${INK}" stroke-width="2"/><ellipse cx="${sx + g}" cy="184" rx="${gr}" ry="9" fill="${GUARD}" stroke="${INK}" stroke-width="2"/>` +
    `<circle cx="${sx - g - 2}" cy="184" r="3" fill="${CHLORO}"/><circle cx="${sx + g + 2}" cy="184" r="3" fill="${CHLORO}"/>`;
  stoma += lead([LX, 208], [sx - g - 6, 190]) + lead([LX, 232], [sx - 1, 190]);
  // Part 7: sunlight falling on the leaf, or the moon at night
  // brighter light: a bigger sun and longer rays
  const light = lt >= 0.05
    ? `<circle cx="372" cy="16" r="${r1(6 + 4 * lt)}" fill="${SUN}" stroke="${INK}" stroke-width="1.5"/>` + [[360, 26, 336, 36], [366, 30, 356, 36], [352, 20, 316, 36]].map(([a, b, c, d]) => `<line x1="${a}" y1="${b}" x2="${r1(a + (c - a) * (0.3 + 0.7 * lt))}" y2="${r1(b + (d - b) * (0.3 + 0.7 * lt))}" stroke="${SUN}" stroke-width="3" stroke-linecap="round"/>`).join("")
    : `<path d="M374 6 A11 11 0 1 0 380 26 A9 9 0 1 1 374 6 Z" fill="#E8E4D0" stroke="${INK}" stroke-width="1.5"/>`;
  // Part 8: gases through the open pore: in by one arrow, out by the other; none when the pore is closed
  let gases = "";
  const labels: Array<{ part: string; text: string; at: Pt; side: "left" | "right" | "above" | "below" }> = [
    { part: "upper_epidermis", text: "cuticle", at: [LX, 34], side: "left" },
    { part: "upper_epidermis", text: "upper epidermis", at: [LX, 56], side: "left" },
    { part: "palisade", text: "palisade cells", at: [LX, 84], side: "left" },
    { part: "spongy", text: "spongy cells", at: [LX, 128], side: "left" },
    { part: "vein", text: "vein", at: [LX, 152], side: "left" },
    { part: "lower_epidermis", text: "lower epidermis", at: [LX, 184], side: "left" },
    { part: "stoma", text: "guard cell", at: [LX, 208], side: "left" },
    { part: "stoma", text: o >= 0.5 ? "stoma (open)" : o < 0.15 ? "stoma (closed)" : "half-open stoma", at: [LX, 232], side: "left" },
    { part: "light", text: lt >= 0.6 ? "sunlight" : lt >= 0.05 ? "dim light" : "night", at: [352, 16], side: "left" },
    { part: "upper_epidermis", text: p.label, at: [146, 16], side: "right" },
  ];
  if (o < 0.15) labels.push({ part: "gases", text: "little gas passes", at: [sx + 26, 222], side: "right" });
  else if (flow < 0.04) labels.push({ part: "gases", text: "in and out balance", at: [sx + 26, 222], side: "right" });
  else {
    // arrow length grows with how much gas moves
    const len = r1(18 + 30 * flow), inC = net > 0 ? CO2 : O2, outC = net > 0 ? O2 : CO2;
    gases = arrow([sx - 16, 205 + len], [sx - 4, 205], inC) + arrow([sx + 4, 205], [sx + 16, 205 + len], outC);
    labels.push({ part: "gases", text: net > 0 ? "CO₂ in" : "O₂ in", at: [sx - 20, 205 + len], side: "left" });
    labels.push({ part: "gases", text: net > 0 ? "O₂ out" : "CO₂ out", at: [sx + 20, 205 + len], side: "right" });
  }
  return {
    parts: { upper_epidermis, palisade, spongy, vein, lower_epidermis, stoma, light, gases },
    anchors: { stoma: [sx, 184] as Pt, vein: [vx, vy] as Pt, top: [271, 38] as Pt },
    labels,
  };
}
