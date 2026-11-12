// Force & friction block on a surface with computed force arrows and microscopic contact zoom. NCERT Class 8 Ch 11-12, Class 9 Ch 8.
type Pt = [number, number];
type Params = {
  surface: string;
  applied_force: number;
  opposing_force: number;
  mass_kg: number;
  show_micro: boolean;
  label: string;
};
type State = { motion?: "rest" | "sliding_right" | "sliding_left" | "impending" };

export const meta = {
  id: "force_block",
  title: "Force and friction block on surface",
  subject: "physics",
  ncert: [
    "Class 8, Ch 11 Force and Pressure",
    "Class 8, Ch 12 Friction",
    "Class 9, Ch 8 Force and Laws of Motion",
  ],
  size: [360, 240] as Pt,
  params: {
    surface: {
      type: "enum",
      options: ["smooth ice", "wood", "rough sandpaper", "rollers"],
      default: "wood",
      say: "type of surface under the block",
    },
    applied_force: {
      type: "number",
      min: 0,
      max: 50,
      default: 30,
      say: "forward push or pull force in newtons",
    },
    opposing_force: {
      type: "number",
      min: 0,
      max: 50,
      default: 15,
      say: "opposing friction or counter force in newtons",
    },
    mass_kg: {
      type: "number",
      min: 1,
      max: 20,
      default: 5,
      say: "mass of the block in kilograms",
    },
    show_micro: {
      type: "boolean",
      default: true,
      say: "whether to show microscopic surface irregularities zoom",
    },
    label: {
      type: "string",
      default: "wooden block",
      say: "name of the block",
    },
  },
  parts: ["surface_ground", "block", "force_arrows", "net_force_arrow", "micro_zoom"],
  states: {
    motion: ["rest", "sliding_right", "sliding_left", "impending"],
  },
  anchors: ["left_hook", "right_hook", "top_center", "bottom_contact"],
  layer: "actor",
  ground: 145,
  situations: {
    balanced: { title: "A push that does not move the box", ncert: "Class 8 Ch 11; Class 9 Ch 8", params: { show_micro: false }, steps: [
      { state: { motion: "rest" }, show: ["surface_ground", "block"], say: "A heavy wooden box rests on the floor." },
      { state: { motion: "rest" }, show: ["surface_ground", "block", "force_arrows"], say: "We push it with 30 newtons, and friction pushes back just as hard." },
      { state: { motion: "rest" }, show: ["surface_ground", "block", "force_arrows", "net_force_arrow"], say: "The forces are balanced, so the box does not move." },
    ] },
    unbalanced: { title: "An unbalanced force moves the box", ncert: "Class 9 Ch 8", params: { show_micro: false }, steps: [
      { state: { motion: "rest" }, show: ["surface_ground", "block"], say: "Now the box is on a smoother floor." },
      { state: { motion: "sliding_right" }, show: ["surface_ground", "block", "force_arrows"], say: "We push with 30 newtons; friction is only 15." },
      { state: { motion: "sliding_right" }, show: ["surface_ground", "block", "force_arrows", "net_force_arrow"], say: "An unbalanced force of 15 newtons makes the box move." },
    ] },
    why_friction: { title: "Why there is friction", ncert: "Class 8 Ch 12", params: { surface: "rough sandpaper" }, steps: [
      { state: { motion: "impending" }, show: ["surface_ground", "block", "force_arrows"], say: "Friction always acts against the push." },
      { show: ["surface_ground", "block", "force_arrows", "micro_zoom"], say: "Up close, the bumps on the two surfaces lock into each other." },
    ] },
    push_harder: { title: "A bigger push gives a bigger net force", ncert: "Class 9 Ch 8 (F = ma)", params: { show_micro: false, applied_force: 20, opposing_force: 15 }, steps: [
      { state: { motion: "sliding_right" }, show: ["surface_ground", "block", "force_arrows", "net_force_arrow"], say: "A push of 20 newtons against 15 newtons of friction leaves a net force of 5 newtons." },
      { params: { applied_force: 35 }, say: "Push with 35 newtons: the net force grows to 20 newtons, so the box speeds up faster." },
      { params: { applied_force: 50 }, say: "At 50 newtons the net force is 35 newtons. The bigger the net force, the bigger the acceleration." },
    ] },
  },
  example: {
    surface: "wood",
    applied_force: 30,
    opposing_force: 15,
    mass_kg: 5,
    show_micro: true,
    label: "wooden block",
  },
};

const INK = "#1B2033";
const BLUE = "#2260E9";
const ORANGE = "#E8590C";
const TEAL = "#0E8C8C";
const GREY = "#6B7189";

const SURF_FILL: Record<string, string> = {
  "smooth ice": "#D9EEF9",
  wood: "#DFC39D",
  "rough sandpaper": "#B8A99A",
  rollers: "#E4E2DA",
};

function arrow(x1: number, y1: number, x2: number, y2: number, color: string, w = 3): string {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy);
  if (len < 6) return "";
  const ux = dx / len;
  const uy = dy / len;
  const hx = x2 - ux * 10;
  const hy = y2 - uy * 10;
  const px = -uy * 5;
  const py = ux * 5;
  return (
    `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="${color}" stroke-width="${w}" stroke-linecap="round"/>` +
    `<polygon points="${x2.toFixed(1)},${y2.toFixed(1)} ${(hx + px).toFixed(1)},${(hy + py).toFixed(1)} ${(hx - px).toFixed(1)},${(hy - py).toFixed(1)}" fill="${color}"/>`
  );
}

export function validate(p: Params): string[] {
  const out: string[] = [];
  if (!(p.applied_force >= 0 && p.applied_force <= 50)) out.push("applied_force must be between 0 and 50 N");
  if (!(p.opposing_force >= 0 && p.opposing_force <= 50)) out.push("opposing_force must be between 0 and 50 N");
  if (!(p.mass_kg >= 1 && p.mass_kg <= 20)) out.push("mass_kg must be between 1 and 20 kg");
  if (!(p.surface in SURF_FILL)) out.push(`unknown surface "${p.surface}"`);
  return out;
}

export function draw(p: Params, state: State = {}) {
  const motion = state.motion ?? (p.applied_force > p.opposing_force ? "sliding_right" : p.applied_force < p.opposing_force ? "sliding_left" : "rest");
  const shiftX = motion === "sliding_right" ? 14 : motion === "sliding_left" ? -14 : motion === "impending" ? 4 : 0;

  const gy = 145;
  const rollerR = 7;
  const blockY = p.surface === "rollers" ? gy - rollerR * 2 : gy;
  const bw = 96 + Math.min(24, p.mass_kg * 1.2);
  const bh = 54 + Math.min(16, p.mass_kg * 0.8);
  const bx = Math.round(180 - bw / 2 + shiftX);
  const by = Math.round(blockY - bh);
  const cx = Math.round(bx + bw / 2);
  const cy = Math.round(by + bh / 2);

  // 1. surface_ground
  let surface_ground = `<rect x="25" y="${gy}" width="310" height="16" fill="${SURF_FILL[p.surface]}" stroke="none"/>`;
  surface_ground += `<line x1="25" y1="${gy}" x2="335" y2="${gy}" stroke="${INK}" stroke-width="3"/>`;
  for (let x = 35; x <= 325; x += 18) {
    surface_ground += `<line x1="${x}" y1="${gy}" x2="${x - 8}" y2="${gy + 12}" stroke="${INK}" stroke-width="1.5"/>`;
  }
  if (p.surface === "rough sandpaper") {
    let teeth = `M25 ${gy}`;
    for (let x = 25; x <= 331; x += 6) teeth += ` L${x + 3} ${gy - 4} L${x + 6} ${gy}`;
    surface_ground += `<path d="${teeth}" fill="none" stroke="${INK}" stroke-width="1.5"/>`;
  } else if (p.surface === "rollers") {
    for (let i = 0; i < 4; i++) {
      const rx = bx + 16 + i * ((bw - 32) / 3);
      surface_ground += `<circle cx="${rx.toFixed(1)}" cy="${gy - rollerR}" r="${rollerR}" fill="#D0D4DF" stroke="${INK}" stroke-width="2"/>`;
    }
  }

  // 2. block
  let block = `<rect x="${bx}" y="${by}" width="${bw}" height="${bh}" rx="3" fill="#E8C99B" stroke="${INK}" stroke-width="3"/>`;
  block += `<line x1="${bx + 10}" y1="${by + 16}" x2="${bx + bw - 10}" y2="${by + 16}" stroke="${GREY}" stroke-width="1.5"/>`;
  block += `<line x1="${bx + 18}" y1="${by + 34}" x2="${bx + bw - 18}" y2="${by + 34}" stroke="${GREY}" stroke-width="1.5"/>`;
  block += `<circle cx="${bx + bw + 5}" cy="${cy}" r="4.5" fill="none" stroke="${INK}" stroke-width="2"/>`;
  block += `<circle cx="${bx - 5}" cy="${cy}" r="4.5" fill="none" stroke="${INK}" stroke-width="2"/>`;
  if (motion === "sliding_right" || motion === "sliding_left") {
    const dir = motion === "sliding_right" ? -1 : 1;
    const sx = dir === -1 ? bx - 12 : bx + bw + 12;
    block += `<line x1="${sx}" y1="${by + 12}" x2="${sx + dir * 16}" y2="${by + 12}" stroke="${ORANGE}" stroke-width="2" stroke-linecap="round"/>`;
    block += `<line x1="${sx}" y1="${by + 26}" x2="${sx + dir * 22}" y2="${by + 26}" stroke="${ORANGE}" stroke-width="2" stroke-linecap="round"/>`;
  }

  // forces the state shows: at rest (or about to slide) static friction balances the push, so the net force is 0;
  // sliding uses the friction given; sliding left mirrors every arrow
  const dir = motion === "sliding_left" ? -1 : 1;
  const push = p.applied_force;
  const friction = motion === "rest" || motion === "impending" ? push : p.opposing_force;
  const net = push - friction;

  // 3. force_arrows (applied force in blue on the pushed side, friction in orange against the motion)
  const appLen = push > 0 ? 22 + push * 1.3 : 0;
  const oppLen = friction > 0 ? 22 + friction * 1.3 : 0;
  const front = dir === 1 ? bx + bw + 9 : bx - 9, back = dir === 1 ? bx : bx + bw;
  const fy = blockY - 8;
  let force_arrows = "";
  if (appLen > 0) force_arrows += arrow(front, cy, front + dir * appLen, cy, BLUE, 3);
  if (oppLen > 0) force_arrows += arrow(back, fy, back - dir * oppLen, fy, ORANGE, 3);

  // 4. net_force_arrow (teal, in the direction of motion; a green dot when balanced)
  const netLen = Math.abs(net) > 0 ? 20 + Math.abs(net) * 1.3 : 0;
  const netY = by - 36;
  let net_force_arrow = "";
  if (netLen > 0) {
    const sgn = net > 0 ? dir : -dir;
    net_force_arrow = arrow(cx - sgn * netLen / 2, netY, cx + sgn * netLen / 2, netY, TEAL, 3);
  } else {
    net_force_arrow = `<circle cx="${cx}" cy="${netY}" r="5" fill="#1F9D55" stroke="${INK}" stroke-width="1.5"/>`;
  }

  // 5. micro_zoom (NCERT Class 8 Fig 12.4 interlocking irregularities)
  let micro_zoom = "";
  if (p.show_micro) {
    const zx = 215, zy = 172, zw = 115, zh = 54;
    micro_zoom += `<line x1="${cx + 10}" y1="${blockY}" x2="${zx}" y2="${zy}" stroke="${GREY}" stroke-width="1.5" stroke-dasharray="4 3"/>`;
    micro_zoom += `<rect x="${zx}" y="${zy}" width="${zw}" height="${zh}" rx="4" fill="#FBF8F1" stroke="${INK}" stroke-width="2"/>`;
    const midY = zy + 27;
    const amp = p.surface === "smooth ice" ? 2 : p.surface === "rough sandpaper" ? 7 : 5;
    let topWave = `M${zx + 6} ${midY - 3}`;
    let botWave = `M${zx + 6} ${midY + 3}`;
    for (let x = zx + 6; x <= zx + zw - 14; x += 12) {
      topWave += ` L${x + 6} ${midY - 3 + amp} L${x + 12} ${midY - 3}`;
      botWave += ` L${x + 6} ${midY + 3 - amp} L${x + 12} ${midY + 3}`;
    }
    micro_zoom += `<path d="${topWave}" fill="none" stroke="${INK}" stroke-width="2"/>`;
    micro_zoom += `<path d="${botWave}" fill="none" stroke="${ORANGE}" stroke-width="2"/>`;
  }

  const labels: { part: string; text: string; at: Pt; side: "left" | "right" | "above" | "below" }[] = [
    { part: "surface_ground", text: p.surface, at: [30, gy + 24], side: "right" },
    { part: "block", text: `${p.label} (${p.mass_kg} kg)`, at: [cx, by - 12], side: "above" },
  ];
  if (appLen > 0) {
    labels.push({ part: "force_arrows", text: `push ${push} N`, at: [front + dir * appLen, cy - 12], side: dir === 1 ? "right" : "left" });
  }
  if (oppLen > 0) {
    labels.push({ part: "force_arrows", text: motion === "impending" ? `max friction ${friction} N` : `friction ${friction} N`, at: [back - dir * oppLen, fy - 14], side: dir === 1 ? "left" : "right" });
  }
  labels.push({
    part: "net_force_arrow",
    text: net === 0 ? (motion === "impending" ? "net 0: about to slide" : "net force 0 (balanced)") : `net force ${Math.abs(net)} N`,
    at: [cx, netY - 14],
    side: "above",
  });
  if (p.show_micro) {
    labels.push({
      part: "micro_zoom",
      text: "interlocking irregularities",
      at: [210, 200],
      side: "left",
    });
  }

  return {
    parts: { surface_ground, block, force_arrows, net_force_arrow, micro_zoom },
    anchors: {
      left_hook: [bx - 5, cy] as Pt,
      right_hook: [bx + bw + 5, cy] as Pt,
      top_center: [cx, by] as Pt,
      bottom_contact: [cx, blockY] as Pt,
    },
    labels,
  };
}
