// Number line with a frog that hops forward or back in equal jumps: counting on, counting back and skip counting.
type Pt = [number, number];
type Params = { start: number; end: number; from: number; jump: number; jumps: number; direction: "forward" | "back" };
type State = { progress?: "start" | "first hop" | "all hops"; hops_done?: number };

export const meta = {
  id: "number_line",
  title: "Number line with hops",
  subject: "maths",
  ncert: ["Class 1, Joyful Mathematics: Addition and subtraction", "Class 2, Ch 8 Counting in groups", "Class 3, Ch 3 Give and take; skip counting", "Class 6, Ch 2 Whole numbers on the number line"],
  size: [400, 200] as Pt,
  params: {
    start: { type: "number", min: -10, max: 90, default: 0, say: "first number on the line" },
    end: { type: "number", min: -5, max: 100, default: 10, say: "last number on the line (5 to 20 steps after start)" },
    from: { type: "number", min: -10, max: 100, default: 2, say: "where the frog starts" },
    jump: { type: "number", min: 1, max: 10, default: 2, say: "size of each hop" },
    jumps: { type: "number", min: 1, max: 6, default: 3, say: "how many hops" },
    direction: { type: "enum", options: ["forward", "back"], default: "forward", say: "hop forward (add) or back (take away)" },
  },
  parts: ["line", "frog", "hops", "result"],
  states: {
    progress: ["start", "first hop", "all hops"],
    hops_done: { type: "number", min: 0, max: 6, default: 0, say: "how many hops the frog has made; 1.5 = halfway through the second hop, in mid-air (stops at the last hop)" },
  },
  anchors: ["zero", "frog"],
  layer: "overlay",
  ground: 200,
  situations: {
    count_on: { title: "Adding by counting on", ncert: "Class 1 Addition", params: { start: 0, end: 10, from: 3, jump: 1, jumps: 4, direction: "forward" }, steps: [
      { state: { progress: "start" }, show: ["line"], say: "Here is a number line from 0 to 10." },
      { show: ["line", "frog"], say: "The frog sits on 3." },
      { state: { progress: "first hop" }, show: ["line", "frog", "hops"], say: "To add 4, it hops forward one at a time. One hop takes it to 4." },
      { state: { progress: "all hops" }, say: "Four hops: 4, 5, 6, 7." },
      { show: ["line", "frog", "hops", "result"], say: "So 3 plus 4 is 7." },
    ] },
    count_back: { title: "Taking away by counting back", ncert: "Class 1 Subtraction", params: { start: 0, end: 10, from: 9, jump: 1, jumps: 3, direction: "back" }, steps: [
      { state: { progress: "start" }, show: ["line", "frog"], say: "The frog is on 9." },
      { state: { progress: "all hops" }, show: ["line", "frog", "hops"], say: "To take away 3, it hops back three times: 8, 7, 6." },
      { show: ["line", "frog", "hops", "result"], say: "9 take away 3 is 6." },
    ] },
    skip_count: { title: "Skip counting in fives", ncert: "Class 2 Counting in groups", params: { start: 0, end: 20, from: 0, jump: 5, jumps: 4, direction: "forward" }, steps: [
      { state: { progress: "start" }, show: ["line", "frog"], say: "The frog starts at 0 and jumps 5 each time." },
      { state: { progress: "first hop" }, show: ["line", "frog", "hops"], say: "One jump of 5 lands on 5." },
      { state: { progress: "all hops" }, say: "5, 10, 15, 20." },
      { show: ["line", "frog", "hops", "result"], say: "Four jumps of 5 make 20. 4 times 5 is 20." },
    ] },
    hop_by_hop: { title: "Follow the frog hop by hop", ncert: "Class 1-2 Maths (adding on a number line)", params: { start: 0, end: 10, from: 2, jump: 2, jumps: 3, direction: "forward" }, steps: [
      { state: { hops_done: 0 }, show: ["line", "frog", "hops", "result"], say: "The frog sits on 2." },
      { state: { hops_done: 0.5 }, say: "It jumps 2 forward. Halfway, it is in the air." },
      { state: { hops_done: 1 }, say: "It lands on 4." },
      { state: { hops_done: 3 }, say: "Two more jumps of 2: 6, then 8. So 2 + 2 + 2 + 2 = 8." },
    ] },
  },
  example: { start: 0, end: 10, from: 2, jump: 2, jumps: 3, direction: "forward" },
};

const INK = "#1B2033";
const HOP = "#2260E9";
const FROG = "#1F9D55";

export function validate(p: Params): string[] {
  const out: string[] = [];
  for (const k of ["start", "end", "from", "jump", "jumps"] as const) if (!Number.isInteger(p[k])) out.push(`${k} must be a whole number`);
  if (!(p.start >= -10 && p.start <= 90)) out.push("start must be from -10 to 90");
  if (!(p.end >= -5 && p.end <= 100)) out.push("end must be from -5 to 100");
  if (!(p.jump >= 1 && p.jump <= 10)) out.push("jump must be from 1 to 10");
  if (!(p.jumps >= 1 && p.jumps <= 6)) out.push("jumps must be from 1 to 6");
  if (!["forward", "back"].includes(p.direction)) out.push(`unknown direction "${p.direction}"`);
  if (out.length) return out;
  if (!(p.end - p.start >= 5 && p.end - p.start <= 20)) out.push("the line must show 5 to 20 steps (end - start)");
  const last = p.from + (p.direction === "forward" ? 1 : -1) * p.jump * p.jumps;
  if (p.from < p.start || p.from > p.end) out.push("the frog must start on the line");
  if (last < p.start || last > p.end) out.push(`the frog would land on ${last}, off the line`);
  return out;
}

export function draw(p: Params, state: State = {}) {
  const y = 150, X0 = 30, X1 = 370, unit = (X1 - X0) / (p.end - p.start);
  const xOf = (v: number) => +(X0 + (v - p.start) * unit).toFixed(1);
  const sign = p.direction === "forward" ? 1 : -1;
  const hd = state.hops_done !== undefined ? Math.min(p.jumps, Math.max(0, state.hops_done)) : { start: 0, "first hop": 1, "all hops": p.jumps }[state.progress ?? "all hops"];
  // whole hops made, and how far through the next one the frog is (0 = sitting on the line)
  const done = Math.floor(hd + 1e-9), part = Math.round((hd - done) * 100) / 100;
  const h = Math.min(70, 34 + p.jump * unit * 0.25);
  const at = p.from + sign * p.jump * done, last = p.from + sign * p.jump * p.jumps;
  // Part 1: the line with arrow ends, a tick and its number at every whole number
  let line = `<line x1="${X0 - 18}" y1="${y}" x2="${X1 + 18}" y2="${y}" stroke="${INK}" stroke-width="3"/>` +
    `<path d="M${X0 - 12} ${y - 6} L${X0 - 20} ${y} L${X0 - 12} ${y + 6} M${X1 + 12} ${y - 6} L${X1 + 20} ${y} L${X1 + 12} ${y + 6}" fill="none" stroke="${INK}" stroke-width="3" stroke-linejoin="round"/>`;
  for (let v = p.start; v <= p.end; v++) {
    line += `<line x1="${xOf(v)}" y1="${y - 7}" x2="${xOf(v)}" y2="${y + 7}" stroke="${INK}" stroke-width="2"/>` +
      `<text x="${xOf(v)}" y="${y + 26}" font-family="DejaVu Sans" font-size="${p.end - p.start > 12 ? 11 : 14}" fill="${INK}" text-anchor="middle">${v}</text>`;
  }
  // the point a fraction t along a hop that starts at value v0 (a curve from the line, up, and down again)
  const hopAt = (v0: number, t: number): Pt => {
    const a = xOf(v0), b = xOf(v0 + sign * p.jump), mid = (a + b) / 2, top = y - 30 - h * 2;
    return [+((1 - t) ** 2 * a + 2 * t * (1 - t) * mid + t * t * b).toFixed(1), +((1 - t) ** 2 * (y - 4) + 2 * t * (1 - t) * top + t * t * (y - 4)).toFixed(1)];
  };
  // Part 2: the frog on the line where it has got to, or in mid-air partway through a hop
  const air = part > 0 ? hopAt(at, part) : null;
  const fx = air ? air[0] : xOf(at);
  const frogAt = (fx: number, y: number) => `<path d="M${fx - 13} ${y - 2} q-4 -6 2 -8 M${fx + 13} ${y - 2} q4 -6 -2 -8" fill="none" stroke="${INK}" stroke-width="2" stroke-linecap="round"/>` +
    `<ellipse cx="${fx}" cy="${y - 13}" rx="13" ry="10" fill="${FROG}" stroke="${INK}" stroke-width="2"/>` +
    `<circle cx="${fx - 6}" cy="${y - 24}" r="4" fill="#FFFDF6" stroke="${INK}" stroke-width="1.5"/><circle cx="${fx + 6}" cy="${y - 24}" r="4" fill="#FFFDF6" stroke="${INK}" stroke-width="1.5"/>` +
    `<circle cx="${fx - 6}" cy="${y - 24}" r="1.5" fill="${INK}"/><circle cx="${fx + 6}" cy="${y - 24}" r="1.5" fill="${INK}"/>`;
  const frog = frogAt(fx, air ? air[1] + 4 : y);
  // Part 3: one arc per hop made so far, with an arrowhead where it lands
  let hops = "";
  const labels: Array<{ part: string; text: string; at: Pt; side: "left" | "right" | "above" | "below" }> = [];
  for (let k = 0; k < done; k++) {
    const a = xOf(p.from + sign * p.jump * k), b = xOf(p.from + sign * p.jump * (k + 1)), mid = (a + b) / 2;
    // the hop leaves the line and lands on it; the landing end stops at the frog's back when the frog is there
    const land = k === done - 1 ? y - 26 : y - 4;
    hops += `<path d="M${a} ${y - 4} Q${mid} ${y - 30 - h * 2} ${b} ${land}" fill="none" stroke="${HOP}" stroke-width="2.5"/>` +
      `<path d="M${b - sign * 8} ${land - 9} L${b} ${land} L${b + sign * 3} ${land - 11}" fill="none" stroke="${HOP}" stroke-width="2.5" stroke-linejoin="round"/>`;
    labels.push({ part: "hops", text: `${sign > 0 ? "+" : "−"}${p.jump}`, at: [mid, +(y - 34 - h).toFixed(1)], side: "above" });
  }
  if (air) {
    // the path so far through the hop in progress (the first part of the curve, split at the frog)
    const a0: Pt = [xOf(at), y - 4], b0 = hopAt(at, 1), mid = (a0[0] + b0[0]) / 2, c: Pt = [a0[0] + (mid - a0[0]) * part, a0[1] + (y - 30 - h * 2 - a0[1]) * part];
    hops += `<path d="M${a0[0]} ${a0[1]} Q${+c[0].toFixed(1)} ${+c[1].toFixed(1)} ${air[0]} ${air[1] + 8}" fill="none" stroke="${HOP}" stroke-width="2.5" stroke-dasharray="5 4"/>`;
  }
  // Part 4: the sum it shows (nothing drawn; a label)
  const steps = p.jumps <= 4 ? Array(p.jumps).fill(`${sign > 0 ? "+" : "−"} ${p.jump}`).join(" ") : `${sign > 0 ? "+" : "−"} ${p.jumps} × ${p.jump}`;
  labels.push({ part: "result", text: `${p.from} ${steps} = ${last}`, at: [14, 18], side: "right" });
  return { parts: { line, frog, hops, result: "" }, anchors: { zero: [xOf(p.start), y] as Pt, frog: [fx, air ? air[1] + 4 : y] as Pt }, labels };
}
