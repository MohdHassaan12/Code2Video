// A simple pendulum released from the side: the bob swings, the period depends on the length and not on the mass. NCERT Class 9 Sound/Motion (oscillation, time period) and Class 11 oscillations, inspired by the textbook activity.
type Pt = [number, number];
type Params = { length_cm: number; mass_g: number; amplitude_deg: number };
type State = { time_s?: number };

export const meta = {
  id: "simple_pendulum",
  title: "Simple pendulum: swing, period and length",
  subject: "physics",
  ncert: ["Class 9, Ch 11 Sound (oscillation, time period and frequency)", "Class 7, Ch 13 Motion and Time (the simple pendulum)", "Class 11 Physics: Oscillations (simple pendulum)"],
  size: [400, 300] as Pt,
  params: {
    length_cm: { type: "number", min: 40, max: 100, default: 64, say: "length of the string from the support to the centre of the bob, in cm" },
    mass_g: { type: "number", min: 20, max: 100, default: 50, say: "mass of the bob in grams (it does not change the period)" },
    amplitude_deg: { type: "number", min: 5, max: 30, default: 20, say: "the angle the bob is pulled aside before release, in degrees" },
  },
  states: {
    time_s: { type: "number", min: 0, max: 6, default: 0, say: "seconds since the bob was released from the side, any value; the bob follows the swing exactly" },
  },
  situations: {
    one_swing: {
      title: "One full to-and-fro swing",
      ncert: ["Class 7 Motion and Time (oscillation, time period)", "Class 9 Sound (oscillation)"],
      params: { length_cm: 64, mass_g: 50, amplitude_deg: 20 },
      steps: [
        { state: { time_s: 0 }, say: "The bob is pulled to one side and let go: it starts from rest." },
        { state: { time_s: 0.4 }, say: "A quarter of a swing later it passes the lowest point, moving fastest." },
        { state: { time_s: 0.8 }, say: "Half a swing: it reaches the other side and stops for a moment." },
        { state: { time_s: 1.2 }, say: "It passes the lowest point again, now moving back." },
        { state: { time_s: 1.6 }, say: "Back where it began after 1.6 seconds: one oscillation. This time is the time period." },
      ],
    },
    longer_string: {
      title: "A longer string gives a longer period",
      ncert: ["Class 7 Motion and Time (the simple pendulum)"],
      params: { length_cm: 40, mass_g: 50, amplitude_deg: 20 },
      steps: [
        { state: { time_s: 0 }, say: "A 40 cm pendulum has a period of about 1.3 seconds." },
        { params: { length_cm: 64 }, say: "Lengthen it to 64 cm: the period grows to about 1.6 seconds." },
        { params: { length_cm: 100 }, say: "At 100 cm the period is about 2.0 seconds. Four times the length would double the period." },
      ],
    },
    heavier_bob: {
      title: "The mass of the bob does not matter",
      ncert: ["Class 7 Motion and Time (the simple pendulum)"],
      params: { length_cm: 64, mass_g: 20, amplitude_deg: 20 },
      steps: [
        { state: { time_s: 0 }, say: "A light 20 g bob on a 64 cm string: period 1.6 seconds." },
        { params: { mass_g: 100 }, say: "Change to a heavy 100 g bob on the same string: the period is still 1.6 seconds." },
      ],
    },
  },
  parts: ["support", "swing_path", "rest_line", "ends", "string", "bob", "angle", "speed_arrow"],
  anchors: ["pivot", "bob_centre", "rest_point"],
  example: { length_cm: 64, mass_g: 50, amplitude_deg: 20 },
};

const INK = "#1B2033", ORANGE = "#E8590C", MAGENTA = "#B4236B", GREY = "#6B7189", STEEL = "#8E93A6";
const G = 9.8, PX = 2.2, PIV: Pt = [250, 36]; // g in m/s^2, pixels per cm, pivot
const f1 = (v: number) => v.toFixed(1);
const t2 = (v: number) => String(Number(v.toFixed(2)));
const t1 = (v: number) => String(Number(v.toFixed(1)));

export function validate(p: Params): string[] {
  const out: string[] = [];
  if (!(p.length_cm >= 40 && p.length_cm <= 100)) out.push("length_cm must be between 40 and 100 cm");
  if (!(p.mass_g >= 20 && p.mass_g <= 100)) out.push("mass_g must be between 20 and 100 g");
  if (!(p.amplitude_deg >= 5 && p.amplitude_deg <= 30)) out.push("amplitude_deg must be between 5 and 30 degrees (small swings)");
  return out;
}

export function draw(p: Params, state: State = {}) {
  const TS = meta.states.time_s;
  const t = Math.min(TS.max, Math.max(TS.min, typeof state.time_s === "number" ? state.time_s : TS.default));
  const L = p.length_cm / 100, Lpx = p.length_cm * PX, A = (p.amplitude_deg * Math.PI) / 180;
  const T = 2 * Math.PI * Math.sqrt(L / G), w = (2 * Math.PI) / T; // T = 2 pi sqrt(L / g)
  const th = A * Math.cos(w * t); // released from rest at the side
  const dir = -Math.sign(Math.sin(w * t) || 0); // +1 when the angle is growing (moving right)
  const v = Math.sqrt(Math.max(0, 2 * G * L * (Math.cos(th) - Math.cos(A)))); // energy: v^2 = 2 g L (cos th - cos A)
  const vmax = Math.sqrt(2 * G * L * (1 - Math.cos(A)));
  const r = 7 + (7 * (p.mass_g - 20)) / 80;
  const at = (a: number, d = Lpx): Pt => [PIV[0] + d * Math.sin(a), PIV[1] + d * Math.cos(a)];
  const B = at(th);

  // 1. support: a beam clamped at the top with the string tied to it
  const support = `<rect x="195" y="22" width="110" height="10" rx="2" fill="#BFC4D1" stroke="${INK}" stroke-width="3"/><line x1="250" y1="32" x2="250" y2="${PIV[1]}" stroke="${INK}" stroke-width="3"/>`;
  // 2. swing_path: the arc the bob can travel, dashed
  const e1 = at(-A), e2 = at(A);
  const swing_path = `<path d="M${f1(e1[0])} ${f1(e1[1])} A${f1(Lpx)} ${f1(Lpx)} 0 0 0 ${f1(e2[0])} ${f1(e2[1])}" fill="none" stroke="${GREY}" stroke-width="1.5" stroke-dasharray="5 4"/>`;
  // 3. rest_line: the vertical through the pivot (mean position)
  const rest_line = `<line x1="250" y1="${PIV[1] + 6}" x2="250" y2="${f1(PIV[1] + Lpx + r + 8)}" stroke="${GREY}" stroke-width="1.5" stroke-dasharray="3 4"/>`;
  // 4. ends: outline circles where the bob stops for a moment
  const ends = [e1, e2].map((e) => `<circle cx="${f1(e[0])}" cy="${f1(e[1])}" r="${f1(r)}" fill="none" stroke="${GREY}" stroke-width="1.5" stroke-dasharray="3 3"/>`).join("");
  // 5. string and 6. bob
  const string = `<line x1="${PIV[0]}" y1="${PIV[1]}" x2="${f1(B[0])}" y2="${f1(B[1])}" stroke="${INK}" stroke-width="2"/>`;
  const bob = `<circle cx="${f1(B[0])}" cy="${f1(B[1])}" r="${f1(r)}" fill="${STEEL}" stroke="${INK}" stroke-width="3"/>`;
  // 7. angle: the string's angle from the vertical
  const deg = (Math.abs(th) * 180) / Math.PI;
  const a1 = at(0, 34), a2 = at(th, 34);
  const angle = deg > 2 ? `<path d="M${f1(a1[0])} ${f1(a1[1])} A34 34 0 0 ${th > 0 ? 0 : 1} ${f1(a2[0])} ${f1(a2[1])}" fill="none" stroke="${MAGENTA}" stroke-width="2"/>` : "";
  // 8. speed_arrow: along the path, as long as the speed (45 px per m/s)
  const tx = Math.cos(th) * dir, ty = -Math.sin(th) * dir, len = v * 45;
  let speed_arrow = "";
  if (len >= 8) {
    const s: Pt = [B[0] + tx * (r + 3), B[1] + ty * (r + 3)], e: Pt = [s[0] + tx * len, s[1] + ty * len];
    const hx = e[0] - tx * 9, hy = e[1] - ty * 9;
    speed_arrow = `<line x1="${f1(s[0])}" y1="${f1(s[1])}" x2="${f1(hx)}" y2="${f1(hy)}" stroke="${ORANGE}" stroke-width="3" stroke-linecap="round"/><polygon points="${f1(e[0])},${f1(e[1])} ${f1(hx - ty * 5)},${f1(hy + tx * 5)} ${f1(hx + ty * 5)},${f1(hy - tx * 5)}" fill="${ORANGE}"/>`;
  }

  const phase = t === 0 ? "released: speed zero" : v < 0.03 * vmax ? "at the end: speed zero" : v > 0.95 * vmax ? "lowest point: fastest" : "swinging";
  const labels: { part: string; text: string; at: Pt; side: "left" | "right" | "above" | "below" }[] = [
    { part: "string", text: `length ${t1(p.length_cm)} cm`, at: [10, 30], side: "right" },
    { part: "bob", text: `mass ${t1(p.mass_g)} g`, at: [10, 52], side: "right" },
    { part: "swing_path", text: `period ${t2(T)} s`, at: [10, 74], side: "right" },
    { part: "swing_path", text: `time ${t2(t)} s`, at: [10, 96], side: "right" },
    { part: "angle", text: `angle ${t1(deg)} deg`, at: [10, 118], side: "right" },
    { part: "speed_arrow", text: `speed ${t2(v)} m/s`, at: [10, 140], side: "right" },
    { part: "support", text: "support", at: [311, 24], side: "right" },
    { part: "bob", text: phase, at: [200, 290], side: "above" },
  ];

  return {
    parts: { support, swing_path, rest_line, ends, string, bob, angle, speed_arrow },
    anchors: { pivot: PIV, bob_centre: B, rest_point: at(0) },
    labels,
  };
}
