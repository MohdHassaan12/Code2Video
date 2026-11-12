// A school child for story and classroom scenes: ten named children (same body, own hair, skin and clothes), eight poses.
// Built from a helper-model library of ten near-identical files; one file now draws all of them.
type Pt = [number, number];
type Params = { who: string; facing: string; expression: string; scale: number };
type State = { pose?: "standing" | "walking" | "sitting" | "pointing" | "thinking" | "raising_hand" | "observing" | "talking" };

const KIDS: Record<string, { hair: string; skin: string; outfit: string; top: string; bottom: string }> = {
  Aarav: { hair: "short", skin: "#C9875A", outfit: "shirt", top: "#4F9BE0", bottom: "#263B70" },
  Anaya: { hair: "braids", skin: "#B97850", outfit: "pinafore", top: "#F1F4F6", bottom: "#263B70" },
  Rohan: { hair: "short", skin: "#A86B45", outfit: "kurta", top: "#F2C14E", bottom: "#5C6B3A" },
  Meera: { hair: "plait", skin: "#C9875A", outfit: "salwar", top: "#E4A23C", bottom: "#5C6B3A" },
  Kabir: { hair: "curly", skin: "#8F5A3A", outfit: "shirt", top: "#5BAE73", bottom: "#C9A46A" },
  Tara: { hair: "ponytail", skin: "#B97850", outfit: "frock", top: "#5BAE73", bottom: "#C9A46A" },
  Arjun: { hair: "short", skin: "#9C6644", outfit: "shirt", top: "#8B86D9", bottom: "#2C3550" },
  Isha: { hair: "bob", skin: "#C9875A", outfit: "salwar", top: "#8B86D9", bottom: "#2C3550" },
  Chotu: { hair: "curly", skin: "#A86B45", outfit: "tshirt", top: "#E58A75", bottom: "#4F9BE0" },
  Gudiya: { hair: "pigtails", skin: "#9C6644", outfit: "frock", top: "#E58A75", bottom: "#4F9BE0" },
};

export const meta = {
  id: "child",
  title: "School child",
  subject: "characters",
  ncert: ["Any class 6-10 story, activity or classroom scene"],
  size: [160, 230] as Pt,
  params: {
    who: { type: "enum", options: Object.keys(KIDS), default: "Aarav", say: "which child: each has their own hair, skin and clothes" },
    facing: { type: "enum", options: ["right", "left"], default: "right", say: "which way the child faces (pointing, walking)" },
    expression: { type: "enum", options: ["neutral", "happy", "curious"], default: "happy", say: "face" },
    scale: { type: "number", min: 0.6, max: 1.4, default: 1, say: "size, 1 is a child of about 10" },
  },
  parts: ["body", "hair", "face", "props"],
  states: { pose: ["standing", "walking", "sitting", "pointing", "thinking", "raising_hand", "observing", "talking"] },
  anchors: ["head", "hand_left", "hand_right", "feet", "center"],
  layer: "actor",
  ground: 218,
  situations: {
    asks_question: { title: "A child asks a question in class", ncert: "Any class", params: {}, steps: [
      { state: { pose: "sitting" }, say: "Aarav is listening in class." },
      { state: { pose: "raising_hand" }, say: "He raises his hand." },
      { state: { pose: "talking" }, say: "And asks his question." },
    ] },
    observes: { title: "A child looks closely", ncert: "Class 6-8 activities", params: { who: "Meera" }, steps: [
      { state: { pose: "standing" }, say: "Meera finds something on the ground." },
      { state: { pose: "observing" }, say: "She looks at it through a magnifying glass." },
    ] },
  },
  example: { who: "Aarav", facing: "right", expression: "happy", scale: 1 },
};

const INK = "#1B2033", HAIR = "#29252A", GREY = "#6B7189";

export function validate(p: Params): string[] {
  const out: string[] = [];
  if (!(p.who in KIDS)) out.push(`unknown child "${p.who}"`);
  if (!["right", "left"].includes(p.facing)) out.push(`facing must be right or left, not "${p.facing}"`);
  if (!["neutral", "happy", "curious"].includes(p.expression)) out.push(`unknown expression "${p.expression}"`);
  if (!(p.scale >= 0.6 && p.scale <= 1.4)) out.push("scale must be between 0.6 and 1.4");
  return out;
}

// a limb: a thick skin or cloth stroke with an ink edge
const limb = (d: string, fill: string, w = 12) =>
  `<path d="${d}" fill="none" stroke="${INK}" stroke-width="${w + 4}" stroke-linecap="round" stroke-linejoin="round"/>` +
  `<path d="${d}" fill="none" stroke="${fill}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`;

export function draw(p: Params, state: State = {}) {
  const k = KIDS[p.who] ?? KIDS.Aarav;
  const pose = state.pose ?? "standing";
  const cx = 70, hy = 38, sit = pose === "sitting";
  const hip = sit ? 150 : 128, top = 70, sh = 76;           // shoulders at y 76, hips at 128 (lower when sitting on the bench)
  const dy = sit ? 22 : 0;                                    // sitting lowers the upper body onto the bench

  // legs first, so the clothes sit over them
  const shoe = (x: number, y: number) => `<path d="M${x - 9} ${y} h22 v-6 q-4 -6 -12 -6 h-10 z" fill="${INK}"/>`;
  let legs = "";
  if (sit) legs = limb(`M${cx - 8} ${hip} H${cx + 22} V${hip + 40}`, k.bottom, 13) + limb(`M${cx + 2} ${hip} H${cx + 32} V${hip + 40}`, k.bottom, 13) + shoe(cx + 25, hip + 52) + shoe(cx + 35, hip + 52);
  else if (pose === "walking") legs = limb(`M${cx - 6} ${hip} L${cx - 20} ${hip + 70}`, k.bottom, 13) + limb(`M${cx + 6} ${hip} L${cx + 22} ${hip + 70}`, k.bottom, 13) + shoe(cx - 22, hip + 80) + shoe(cx + 24, hip + 80);
  else legs = limb(`M${cx - 8} ${hip} V${hip + 70}`, k.bottom, 13) + limb(`M${cx + 8} ${hip} V${hip + 70}`, k.bottom, 13) + shoe(cx - 8, hip + 80) + shoe(cx + 10, hip + 80);

  // clothes: the outfit decides the shape of the top
  const y0 = top + dy, s0 = sh + dy, h0 = hip;
  const long = k.outfit === "kurta" || k.outfit === "salwar" || k.outfit === "frock" || k.outfit === "pinafore";
  const hem = long ? h0 + 22 : h0 + 4, flare = k.outfit === "frock" || k.outfit === "pinafore" ? 14 : 6;
  let clothes = `<path d="M${cx - 24} ${y0} Q${cx} ${y0 - 8} ${cx + 24} ${y0} L${cx + 26 + flare} ${hem} Q${cx} ${hem + 8} ${cx - 26 - flare} ${hem} Z" fill="${k.top}" stroke="${INK}" stroke-width="2.5" stroke-linejoin="round"/>`;
  if (k.outfit === "pinafore") clothes += `<path d="M${cx - 14} ${y0 + 2} V${y0 + 30} H${cx + 14} V${y0 + 2}" fill="none" stroke="${k.bottom}" stroke-width="5"/><path d="M${cx - 18} ${y0 + 30} H${cx + 18} L${cx + 26 + flare} ${hem} Q${cx} ${hem + 8} ${cx - 26 - flare} ${hem} Z" fill="${k.bottom}" stroke="${INK}" stroke-width="2"/>`;
  if (k.outfit === "shirt") clothes += `<path d="M${cx - 9} ${y0 - 3} L${cx} ${y0 + 8} L${cx + 9} ${y0 - 3}" fill="none" stroke="${INK}" stroke-width="2"/><line x1="${cx}" y1="${y0 + 8}" x2="${cx}" y2="${hem - 4}" stroke="${INK}" stroke-width="1.5"/>`;
  if (k.outfit === "kurta" || k.outfit === "salwar") clothes += `<line x1="${cx}" y1="${y0 - 3}" x2="${cx}" y2="${y0 + 22}" stroke="${INK}" stroke-width="1.5"/>`;
  if (k.outfit === "salwar") clothes += `<path d="M${cx - 22} ${y0 + 2} Q${cx} ${y0 + 22} ${cx + 22} ${y0 + 2}" fill="none" stroke="${k.bottom}" stroke-width="5" stroke-linecap="round"/>`;

  // arms: the pose decides where the hands go (the front hand is the right-hand one when facing right)
  const L: Pt = [cx - 24, s0], R: Pt = [cx + 24, s0];
  let hl: Pt = [cx - 32, s0 + 50], hr: Pt = [cx + 32, s0 + 50], elbowR = `Q${cx + 40} ${s0 + 26}`, elbowL = `Q${cx - 40} ${s0 + 26}`;
  let props = "";
  if (pose === "walking") { hl = [cx - 14, s0 + 48]; hr = [cx + 40, s0 + 42]; elbowL = `Q${cx - 30} ${s0 + 24}`; elbowR = `Q${cx + 36} ${s0 + 20}`; }
  if (pose === "sitting") { hl = [cx + 10, hip - 4]; hr = [cx + 30, hip - 4]; elbowL = `Q${cx - 26} ${s0 + 34}`; elbowR = `Q${cx + 34} ${s0 + 30}`; }
  if (pose === "pointing") { hr = [cx + 78, s0 + 6]; elbowR = `Q${cx + 50} ${s0 + 8}`; }
  if (pose === "raising_hand") { hr = [cx + 30, 0]; elbowR = `Q${cx + 40} ${s0 - 34}`; }
  if (pose === "thinking") { hr = [cx + 10, hy + 22]; elbowR = `Q${cx + 44} ${s0 + 20}`; }
  if (pose === "talking") { hr = [cx + 52, s0 + 14]; elbowR = `Q${cx + 44} ${s0 + 34}`; hl = [cx - 50, s0 + 14]; elbowL = `Q${cx - 44} ${s0 + 34}`; }
  if (pose === "observing") {
    hr = [cx + 42, hy + 12]; elbowR = `Q${cx + 46} ${s0 + 20}`;
    props += `<line x1="${hr[0]}" y1="${hr[1]}" x2="${hr[0] + 6}" y2="${hr[1] - 14}" stroke="${GREY}" stroke-width="5" stroke-linecap="round"/>` +
      `<circle cx="${hr[0] + 12}" cy="${hr[1] - 26}" r="12" fill="#E8F2F8" stroke="${INK}" stroke-width="3"/>`; // magnifying glass
  }
  const hand = (h: Pt) => `<circle cx="${h[0]}" cy="${h[1]}" r="6.5" fill="${k.skin}" stroke="${INK}" stroke-width="2"/>`;
  const arms = limb(`M${L[0]} ${L[1]} ${elbowL} ${hl[0]} ${hl[1]}`, k.top, 11) + limb(`M${R[0]} ${R[1]} ${elbowR} ${hr[0]} ${hr[1]}`, k.top, 11) + hand(hl) + hand(hr);
  if (pose === "pointing") props += `<line x1="${hr[0] + 6}" y1="${hr[1]}" x2="${hr[0] + 16}" y2="${hr[1]}" stroke="${INK}" stroke-width="4" stroke-linecap="round"/>`;
  let bench = "";
  if (sit) bench += `<rect x="${cx - 30}" y="${hip + 6}" width="78" height="10" rx="2" fill="#B07A4A" stroke="${INK}" stroke-width="2.5"/>` +
    `<line x1="${cx - 22}" y1="${hip + 16}" x2="${cx - 22}" y2="${hip + 54}" stroke="${INK}" stroke-width="4"/><line x1="${cx + 40}" y1="${hip + 16}" x2="${cx + 40}" y2="${hip + 54}" stroke="${INK}" stroke-width="4"/>`;

  // head and neck
  const hY = hy + dy;
  const head = `<rect x="${cx - 6}" y="${hY + 22}" width="12" height="14" fill="${k.skin}" stroke="${INK}" stroke-width="2"/>` +
    `<ellipse cx="${cx}" cy="${hY}" rx="23" ry="26" fill="${k.skin}" stroke="${INK}" stroke-width="2.5"/>`;

  // hair: every style starts with a cap over the top of the head
  const cap = `<path d="M${cx - 24} ${hY + 2} Q${cx - 26} ${hY - 30} ${cx} ${hY - 28} Q${cx + 26} ${hY - 30} ${cx + 24} ${hY + 2} Q${cx + 14} ${hY - 14} ${cx - 4} ${hY - 12} Q${cx - 18} ${hY - 10} ${cx - 24} ${hY + 2} Z" fill="${HAIR}" stroke="${INK}" stroke-width="2"/>`;
  const extra: Record<string, string> = {
    short: "",
    curly: [-18, -6, 6, 18].map((x) => `<circle cx="${cx + x}" cy="${hY - 26}" r="8" fill="${HAIR}" stroke="${INK}" stroke-width="2"/>`).join(""),
    braids: [-1, 1].map((d) => limb(`M${cx + d * 22} ${hY} L${cx + d * 24} ${hY + 44}`, HAIR, 7)).join(""),
    plait: limb(`M${cx - 22} ${hY} Q${cx - 30} ${hY + 30} ${cx - 22} ${hY + 56}`, HAIR, 8),
    ponytail: limb(`M${cx - 22} ${hY - 10} Q${cx - 42} ${hY} ${cx - 36} ${hY + 28}`, HAIR, 9),
    pigtails: [-1, 1].map((d) => `<circle cx="${cx + d * 28}" cy="${hY - 6}" r="9" fill="${HAIR}" stroke="${INK}" stroke-width="2"/>`).join(""),
    bob: `<path d="M${cx - 24} ${hY} V${hY + 20} H${cx - 14} V${hY - 6} Z M${cx + 24} ${hY} V${hY + 20} H${cx + 14} V${hY - 6} Z" fill="${HAIR}" stroke="${INK}" stroke-width="2"/>`,
  };
  const hair = extra[k.hair] + cap;

  // face: two dot eyes looking the way they face; the mouth is the expression
  const look = pose === "thinking" ? -2 : 2;
  let face = `<circle cx="${cx - 8 + look}" cy="${hY + 2}" r="2.6" fill="${INK}"/><circle cx="${cx + 8 + look}" cy="${hY + 2}" r="2.6" fill="${INK}"/>`;
  const open = pose === "talking" || p.expression === "curious";
  face += open ? `<ellipse cx="${cx + look}" cy="${hY + 14}" rx="3.5" ry="3" fill="${INK}"/>`
    : p.expression === "happy" ? `<path d="M${cx - 7} ${hY + 12} Q${cx} ${hY + 19} ${cx + 7} ${hY + 12}" fill="none" stroke="${INK}" stroke-width="2" stroke-linecap="round"/>`
    : `<line x1="${cx - 5}" y1="${hY + 14}" x2="${cx + 5}" y2="${hY + 14}" stroke="${INK}" stroke-width="2" stroke-linecap="round"/>`;

  // facing left mirrors the whole child; scale grows it from the feet
  const s = p.scale, mx = p.facing === "left" ? -1 : 1, footY = 218;
  const T = (pt: Pt): Pt => [Math.round(cx + mx * (pt[0] - cx) * s), Math.round(footY + (pt[1] - footY) * s)];
  const g = (svg: string) => svg ? `<g transform="translate(${cx} ${footY}) scale(${mx * s} ${s}) translate(${-cx} ${-footY})">${svg}</g>` : "";
  return {
    parts: { body: g(bench + legs + clothes + head + arms), hair: g(hair), face: g(face), props: g(props) },
    anchors: { head: T([cx, hY - 28]), hand_left: T(hl), hand_right: T(hr), feet: T([cx, footY]), center: T([cx, 115 + dy]) },
    labels: [{ part: "body", text: p.who, at: T([cx, footY + 6]), side: "below" }],
  };
}
