// Test tube: glass, liquid, solid pieces, bubbles, gas leaving the mouth. NCERT Class 10 Ch 1 (zinc + dilute acid).
type Pt = [number, number];
type Params = { liquid: string; level: number; solid: string; label: string };
type State = { bubbles?: "none" | "some" | "many"; liquid?: string; bubble_rate?: number };

export const meta = {
  id: "test_tube",
  title: "Test tube",
  subject: "chemistry",
  ncert: ["Class 10, Ch 1 Chemical Reactions and Equations", "Class 7, Ch 5 Acids, Bases and Salts"],
  size: [120, 260] as Pt,
  params: {
    liquid: { type: "enum", options: ["none", "water", "dilute acid", "copper sulphate", "lime water", "milky lime water"], default: "dilute acid", say: "what is in the tube" },
    level: { type: "number", min: 0, max: 0.9, default: 0.45, say: "how full, 0 to 0.9 of the tube" },
    solid: { type: "enum", options: ["none", "granules", "nail", "powder"], default: "granules", say: "a solid lying in it" },
    label: { type: "string", default: "test tube", say: "the learner's word for it" },
  },
  parts: ["glass", "liquid", "solid", "bubbles", "gas"],
  states: {
    bubbles: ["none", "some", "many"], liquid: ["water", "dilute acid", "copper sulphate", "lime water", "milky lime water"],
    bubble_rate: { type: "number", min: 0, max: 1, default: 0, say: "how fast gas is given off: 0 none, 1 fizzing hard" },
  },
  anchors: ["mouth", "bottom", "side"],
  layer: "prop",
  ground: 232,
  situations: {
    zinc_and_acid: { title: "Zinc and dilute acid give hydrogen", ncert: "Class 10 Ch 1, Activity 1.3", params: { liquid: "dilute acid", solid: "granules", level: 0.45 }, steps: [
      { show: ["glass"], say: "This is a test tube." },
      { show: ["glass", "liquid"], say: "We pour in some dilute sulphuric acid." },
      { show: ["glass", "liquid", "solid"], say: "Then we drop in a few zinc granules." },
      { state: { bubbles: "some" }, show: ["glass", "liquid", "solid", "bubbles"], say: "Bubbles start rising from the zinc." },
      { state: { bubbles: "many" }, say: "Hydrogen gas bubbles out of the mouth of the tube." },
    ] },
    lime_water: { title: "Carbon dioxide turns lime water milky", ncert: "Class 10 Ch 2; Class 7 Ch 5", params: { liquid: "lime water", solid: "none", level: 0.5 }, steps: [
      { show: ["glass", "liquid"], say: "Fresh lime water is clear." },
      { state: { bubbles: "some" }, show: ["glass", "liquid", "bubbles"], say: "We bubble carbon dioxide through it." },
      { state: { bubbles: "some", liquid: "milky lime water" }, show: ["glass", "liquid", "bubbles"], say: "The lime water turns milky." },
    ] },
    reaction_speeds_up: { title: "The reaction speeds up, then slows down", ncert: "Class 10 Ch 1", params: { solid: "granules", liquid: "dilute acid" }, steps: [
      { state: { bubble_rate: 0.2 }, show: ["glass", "liquid", "solid", "bubbles"], say: "At first a few bubbles of hydrogen rise from the zinc." },
      { state: { bubble_rate: 1 }, say: "Soon it fizzes hard." },
      { state: { bubble_rate: 0.4 }, say: "As the acid is used up, the bubbling slows." },
    ] },
  },
  example: { liquid: "dilute acid", level: 0.45, solid: "granules", label: "test tube" },
};

const INK = "#1B2033";
const LIQUID: Record<string, string> = { water: "#CFE6F7", "dilute acid": "#E3F1D4", "copper sulphate": "#4F9BE0", "lime water": "#F1F4F6", "milky lime water": "#E4E2DA" };

export function validate(p: Params): string[] {
  const out: string[] = [];
  if (!(p.level >= 0 && p.level <= 0.9)) out.push("level must be between 0 and 0.9");
  if (!(p.liquid in LIQUID) && p.liquid !== "none") out.push(`unknown liquid "${p.liquid}"`);
  if (!["none", "granules", "nail", "powder"].includes(p.solid)) out.push(`unknown solid "${p.solid}"`);
  if (p.liquid === "none" && p.level > 0) out.push("an empty tube has level 0");
  return out;
}

export function draw(p: Params, state: State = {}) {
  const x0 = 35, x1 = 85, top = 20, bottom = 230, r = (x1 - x0) / 2, cx = (x0 + x1) / 2;
  const liquid = state.liquid ?? p.liquid;
  // the glass: two walls and a round bottom, a lip at the mouth
  const glass = `<path d="M${x0} ${top} V${bottom - r} A${r} ${r} 0 0 0 ${x1} ${bottom - r} V${top}" fill="none" stroke="${INK}" stroke-width="3"/>` +
    `<path d="M${x0 - 5} ${top} H${x0 + 3} M${x1 - 3} ${top} H${x1 + 5}" stroke="${INK}" stroke-width="3" stroke-linecap="round"/>`;
  // the liquid fills from the bottom up to its level (computed, never typed in)
  const inner = bottom - top - 4, surface = bottom - 2 - p.level * inner;
  const liq = liquid === "none" || p.level === 0 ? "" :
    `<path d="M${x0 + 2} ${surface} V${bottom - r} A${r - 2} ${r - 2} 0 0 0 ${x1 - 2} ${bottom - r} V${surface} Z" fill="${LIQUID[liquid]}" stroke="none"/>` +
    `<line x1="${x0 + 2}" y1="${surface}" x2="${x1 - 2}" y2="${surface}" stroke="${INK}" stroke-width="1.5"/>`;
  // a solid lying at the bottom
  const pieces: Pt[] = [[cx - 12, bottom - 14], [cx + 2, bottom - 10], [cx + 13, bottom - 16], [cx - 4, bottom - 22]];
  const solid = p.solid === "granules" ? pieces.map(([x, y]) => `<polygon points="${x - 5},${y} ${x},${y - 6} ${x + 6},${y - 1} ${x + 2},${y + 5}" fill="#9AA0B4" stroke="${INK}" stroke-width="1.5"/>`).join("")
    : p.solid === "nail" ? `<line x1="${cx - 8}" y1="${bottom - 12}" x2="${cx + 6}" y2="${surface + 10}" stroke="#6B7189" stroke-width="5" stroke-linecap="round"/>`
    : p.solid === "powder" ? `<path d="M${x0 + 6} ${bottom - 8} Q${cx} ${bottom - 22} ${x1 - 6} ${bottom - 8} Z" fill="#E8E2D0" stroke="${INK}" stroke-width="1.5"/>` : "";
  // bubbles rise from the solid to the surface; how many is the state
  const n = state.bubble_rate !== undefined ? Math.round(11 * Math.min(1, Math.max(0, state.bubble_rate))) : { none: 0, some: 5, many: 11 }[state.bubbles ?? "none"];
  let bubbles = "";
  for (let i = 0; i < n; i++) {
    const y = bottom - 30 - ((i * 37) % Math.max(10, bottom - 30 - surface - 6));
    const x = cx - 14 + ((i * 19) % 29);
    if (y > surface + 4) bubbles += `<circle cx="${x}" cy="${y}" r="${3 + (i % 3)}" fill="none" stroke="${INK}" stroke-width="1.5"/>`;
  }
  // gas leaving the mouth: three short wavy lines
  const gas = [cx - 14, cx, cx + 14].map((x) => `<path d="M${x} ${top - 2} q-6 -8 0 -14 q6 -6 0 -14" fill="none" stroke="#6B7189" stroke-width="2"/>`).join("");
  return {
    parts: { glass, liquid: liq, solid, bubbles, gas },
    anchors: { mouth: [cx, top] as Pt, bottom: [cx, bottom] as Pt, side: [x1, (top + bottom) / 2] as Pt },
    labels: [
      { part: "glass", text: p.label, at: [x1, top + 40] as Pt, side: "right" },
      { part: "liquid", text: liquid, at: [x1 - 4, (surface + bottom) / 2] as Pt, side: "right" },
      { part: "solid", text: p.solid === "granules" ? "zinc granules" : p.solid, at: [x0 + 4, bottom - 14] as Pt, side: "left" },
      { part: "gas", text: "gas", at: [cx + 16, top - 20] as Pt, side: "right" },
    ],
  };
}
