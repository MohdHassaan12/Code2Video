// Code-drawn figure kinds. Each takes the lesson's figure JSON and returns the node plus its named parts,
// so a step's "focus" can light up the part the voice is talking about.
import {Circle, Line, Node, Rect, Txt} from '@revideo/2d';
import {all, sequence, ThreadGenerator, Vector2} from '@revideo/core';
import {parseMathFunction, tickStep} from './figure_math';

export const C = {
  ink: '#e2e8f0', dim: '#64748b', a: '#38bdf8', b: '#f472b6', c: '#facc15', fill: '#1e293b', accent: '#facc15',
};
export const ROLES: Record<string, string> = {
  given: C.a,
  unknown: C.accent,
  result: '#56faaa',
  wrong: '#e57a9e',
};
export const GRAPH_COLOURS = [C.a, C.accent, '#c9a0f0', '#56faaa'];
const FONT = 'Inter, Helvetica, Arial, sans-serif';

export interface Drawn {
  node: Node;
  parts: Record<string, Node[]>;
  /** Extra moves some kinds make on a step (e.g. the circle's slices becoming a rectangle). */
  onStep?: (i: number, last: boolean) => ThreadGenerator | null;
  /** A kind's own move when a step focuses one of its parts (e.g. counting the grid's squares). */
  onFocus?: (key: string) => ThreadGenerator | null;
}

type P = [number, number];
const label = (text: string, at: P, color = C.ink, size = 30) =>
  <Txt text={text} position={at} fill={color} fontSize={size} fontFamily={FONT} fontWeight={600} /> as Txt;

/** Fit points (y up, in figure units) into a box; returns a mapper to screen coordinates (y down). */
function fitter(points: P[], box: [number, number]) {
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const s = Math.min(box[0] / (x1 - x0 || 1), box[1] / (y1 - y0 || 1));
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  return {s, map: (p: P): P => [(p[0] - cx) * s, -(p[1] - cy) * s]};
}

function rightTriangle(f: Record<string, any>, box: [number, number]): Drawn {
  const a = Number(f.a ?? 4), b = Number(f.b ?? 3);
  const L = f.labels ?? {};
  // Right angle at the origin; leg a along the ground (to the left), leg b up the wall.
  const R: P = [0, 0], A: P = [-a, 0], B: P = [0, b];
  const sq = (p: P, q: P, away: P): P[] => {
    const d: P = [q[0] - p[0], q[1] - p[1]];
    let n: P = [-d[1], d[0]];
    const mid: P = [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
    // Outward: the normal must point away from the triangle's centre.
    if (n[0] * (mid[0] - away[0]) + n[1] * (mid[1] - away[1]) < 0) n = [-n[0], -n[1]];
    return [p, q, [q[0] + n[0], q[1] + n[1]], [p[0] + n[0], p[1] + n[1]]];
  };
  const centroid: P = [-a / 3, b / 3];
  const squares = f.squares ? {a: sq(A, R, centroid), b: sq(R, B, centroid), c: sq(B, A, centroid)} : null;
  const all_pts: P[] = [R, A, B, ...(squares ? [...squares.a, ...squares.b, ...squares.c] : [])];
  const {map} = fitter(all_pts, box);
  const node = <Node /> as Node;
  const parts: Record<string, Node[]> = {};
  const colors: Record<string, string> = {a: C.a, b: C.b, c: C.c};
  if (squares) {
    for (const k of ['a', 'b', 'c'] as const) {
      const pts = squares[k].map(map);
      const sqNode = <Line points={pts} closed fill={colors[k] + '22'} stroke={colors[k]} lineWidth={3} /> as Line;
      const side = Number(k === 'a' ? a : k === 'b' ? b : Math.hypot(a, b));
      const ctr: P = [pts.reduce((t, p) => t + p[0], 0) / 4, pts.reduce((t, p) => t + p[1], 0) / 4];
      const sideText = k === 'c' && !Number.isInteger(+side.toFixed(2)) ? 'c' : `${+side.toFixed(2)}`;
      const area = label(`${sideText}² = ${+(side * side).toFixed(2)}`, ctr, colors[k], 30);
      node.add(sqNode); node.add(area);
      parts[`square_${k}`] = [sqNode, area];
    }
  }
  const tri = <Line points={[A, R, B].map(map)} closed fill={C.fill} stroke={C.dim} lineWidth={2} /> as Line;
  node.add(tri);
  const sides: Record<string, [P, P]> = {a: [A, R], b: [R, B], c: [B, A]};
  for (const k of ['a', 'b', 'c'] as const) {
    const [p, q] = sides[k];
    const line = <Line points={[map(p), map(q)]} stroke={colors[k]} lineWidth={7} lineCap="round" /> as Line;
    const mid = map([(p[0] + q[0]) / 2, (p[1] + q[1]) / 2]);
    // Side labels sit outside the triangle, or just inside it when squares fill the outside.
    const cs = map(centroid);
    const dx = mid[0] - cs[0], dy = mid[1] - cs[1], len = Math.hypot(dx, dy) || 1;
    const gap = squares ? -30 : 34;
    const out = [(dx / len) * gap, (dy / len) * gap];
    const unknown = f.unknown === k;
    const text = String(L[k] ?? (k === 'c' ? '' : k === 'a' ? a : b));
    const lab = label(text, [mid[0] + out[0], mid[1] + out[1]], unknown ? C.accent : colors[k], unknown ? 40 : 30);
    if (squares) lab.opacity(0); // the squares carry the numbers
    node.add(line); node.add(lab);
    parts[k] = [line, lab];
  }
  const m = 0.45 * Math.min(a, b) / 3;
  node.add(<Line points={[[-m, 0], [-m, m], [0, m]].map(p => map(p as P))} stroke={C.ink} lineWidth={2} />);
  return {node, parts};
}

function circle(f: Record<string, any>, box: [number, number]): Drawn {
  const L = f.labels ?? {};
  const n = Number(f.sectors ?? 0);
  const rearranged = !!f.rearranged;
  const R = Math.min(box[0] / (rearranged ? Math.PI + 0.6 : 2.2), box[1] / 2.4);
  const node = <Node /> as Node;
  const parts: Record<string, Node[]> = {};
  if (!n) {
    const ring = <Circle size={2 * R} stroke={C.a} lineWidth={6} fill={C.fill} /> as Circle;
    const radius = <Line points={[[0, 0], [R, 0]]} stroke={C.b} lineWidth={6} lineCap="round" /> as Line;
    const dot = <Circle size={12} fill={C.ink} /> as Circle;
    const rl = label(String(L.radius ?? 'r'), [R / 2, -26], C.b);
    const cl = label(String(L.circumference ?? ''), [0, -R - 34], C.a);
    node.add([ring, radius, dot, rl, cl]);
    parts.radius = [radius, rl];
    parts.circumference = [ring, cl];
    if (f.unknown === 'area') node.add(label('Area = ?', [0, R + 44], C.accent, 32));
    return {node, parts};
  }
  // Sectors: wedge i points up from its apex; rotated i*theta it is part of the circle.
  const th = 360 / n, arc = (2 * Math.PI * R) / n;
  const wedges = Array.from({length: n}, (_, i) =>
    <Circle size={2 * R} startAngle={-90 - th / 2} endAngle={-90 + th / 2} closed
      fill={i % 2 ? C.a + 'cc' : C.b + 'cc'} stroke={C.fill} lineWidth={2} rotation={i * th} /> as Circle);
  node.add(wedges);
  parts.sectors = wedges;
  const x0 = -(n / 2) * (arc / 2) + arc / 4;
  const base = label(String(L.base ?? ''), [0, R / 2 + 40], C.b);
  const height = label(String(L.height ?? ''), [x0 - arc / 2 - 40, 0], C.a);
  base.opacity(0); height.opacity(0);
  node.add([base, height]);
  const onStep = (_i: number, last: boolean) => {
    if (!rearranged || !last) return null;
    return all(
      sequence(0.02, ...wedges.map((w, i) => all(
        w.rotation(i % 2 ? 180 : 0, 0.8),
        w.position(new Vector2(x0 + (i * arc) / 2, i % 2 ? -R / 2 : R / 2), 0.8)))),
      base.opacity(1, 0.6), height.opacity(1, 0.6));
  };
  return {node, parts, onStep};
}

function rectangle(f: Record<string, any>, box: [number, number]): Drawn {
  const w = Number(f.w ?? 6), h = Number(f.h ?? 4);
  const L = f.labels ?? {};
  const s = Math.min(box[0] / (w + 1.2), box[1] / (h + 1.2));
  const node = <Node /> as Node;
  const cells: Rect[] = [];
  if (f.grid) {
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++)
      cells.push(<Rect width={s} height={s} x={(i - w / 2 + 0.5) * s} y={(j - h / 2 + 0.5) * s}
        stroke={C.dim} lineWidth={1.5} fill={C.fill} /> as Rect);
    node.add(cells);
  }
  const outline = <Rect width={w * s} height={h * s} stroke={C.ink} lineWidth={4} /> as Rect;
  const bottom = <Line points={[[-w * s / 2, h * s / 2], [w * s / 2, h * s / 2]]} stroke={C.a} lineWidth={7} /> as Line;
  const left = <Line points={[[-w * s / 2, -h * s / 2], [-w * s / 2, h * s / 2]]} stroke={C.b} lineWidth={7} /> as Line;
  const wl = label(String(L.w ?? w), [0, h * s / 2 + 34], C.a);
  const hl = label(String(L.h ?? h), [-w * s / 2 - 48, 0], C.b);
  const al = label(String(L.area ?? ''), [0, 0], C.accent, 56);
  if (f.result === 'area') al.opacity(0);
  node.add([outline, bottom, left, wl, hl, al]);
  const parts: Record<string, Node[]> = {length: [bottom, wl], width: [left, hl], height: [left, hl], area: [al]};
  const onFocus = (key: string) => key === 'area' && cells.length
    ? all(sequence(0.04, ...cells.map(c => c.fill(C.accent + '55', 0.2))), al.opacity(1, 0.5))
    : null;
  return {node, parts, onFocus};
}


function numberLine(f: Record<string, any>, box: [number, number]): Drawn {
  let lo = Number(f.min ?? -5);
  let hi = Number(f.max ?? 5);
  if (isNaN(lo)) lo = -5;
  if (isNaN(hi)) hi = 5;
  if (hi <= lo) { lo = -5; hi = 5; }
  const [step, places] = tickStep(lo, hi);
  lo = +(Math.floor(lo / step + 1e-9) * step).toFixed(places);
  hi = +(Math.ceil(hi / step - 1e-9) * step).toFixed(places);

  const node = <Node /> as Node;
  const parts: Record<string, Node[]> = {};
  const lineLen = Math.min(box[0] * 0.85, 520);
  const toScreenX = (x: number) => ((x - (lo + hi) / 2) / (hi - lo || 1)) * lineLen;
  const lineY = 0;

  const axisLine = <Line points={[[toScreenX(lo) - 15, lineY], [toScreenX(hi) + 15, lineY]]}
    stroke={C.dim} lineWidth={4} lineCap="round" /> as Line;
  node.add(axisLine);

  const tickNodes: Node[] = [];
  for (let v = lo; v <= hi + step * 0.5; v += step) {
    const sx = toScreenX(v);
    const tick = <Line points={[[sx, lineY - 8], [sx, lineY + 8]]} stroke={C.dim} lineWidth={2} /> as Line;
    const numStr = `${+v.toFixed(places)}`;
    const num = label(numStr, [sx, lineY + 28], C.dim, 20);
    tickNodes.push(tick, num);
    node.add([tick, num]);
  }
  parts.line = [axisLine, ...tickNodes];

  const points = Array.isArray(f.points) ? f.points : [];
  points.forEach((pt: any, i: number) => {
    if (!pt || typeof pt !== 'object') return;
    const x = Math.min(hi, Math.max(lo, Number(pt.x ?? 0)));
    const sx = toScreenX(x);
    const role = String(pt.role ?? 'given');
    const color = ROLES[role] ?? C.a;
    const dot = <Circle size={16} x={sx} y={lineY} fill={color} /> as Circle;
    const labText = String(pt.label ?? `${x}`);
    const lab = label(labText, [sx, lineY - 30], color, 24);
    node.add([dot, lab]);
    parts[`point${i}`] = [dot];
    parts[`point${i}_label`] = [lab];
  });

  if (f.arrow && typeof f.arrow === 'object') {
    const x0 = Number(f.arrow.from ?? 0);
    const x1 = Number(f.arrow.to ?? 0);
    const sx0 = toScreenX(x0);
    const sx1 = toScreenX(x1);
    const role = String(f.arrow.role ?? 'unknown');
    const color = ROLES[role] ?? C.accent;
    const arrowY = lineY + 68;
    const shaft = <Line points={[[sx0, arrowY], [sx1, arrowY]]} stroke={color} lineWidth={4} /> as Line;
    const dir = sx1 >= sx0 ? 1 : -1;
    const head = <Line points={[[sx1 - dir * 12, arrowY - 8], [sx1, arrowY], [sx1 - dir * 12, arrowY + 8]]}
      stroke={color} lineWidth={4} lineCap="round" lineJoin="round" /> as Line;
    node.add([shaft, head]);
    parts.arrow = [shaft, head];
    if (f.arrow.label) {
      const alab = label(String(f.arrow.label), [(sx0 + sx1) / 2, arrowY + 28], color, 22);
      node.add(alab);
      parts.arrow_label = [alab];
    }
  }

  return {node, parts};
}

function bars(f: Record<string, any>, box: [number, number]): Drawn {
  const items: any[] = Array.isArray(f.parts) ? f.parts.slice(0, 4) : [];
  const node = <Node /> as Node;
  const parts: Record<string, Node[]> = {};
  if (!items.length) return {node, parts};

  const totalW = Math.min(box[0] * 0.9, 520);
  const labelW = 100;
  const barW = totalW - labelW - 20;
  const barH = 46;
  const gap = 24;
  const totalH = items.length * barH + (items.length - 1) * gap;
  const startY = -totalH / 2 + barH / 2;

  items.forEach((item, i) => {
    if (!item || typeof item !== 'object') return;
    const n = Math.max(0, Math.floor(Number(item.n ?? 1)));
    const d = Math.max(1, Math.floor(Number(item.d ?? 2)));
    const role = String(item.role ?? 'given');
    const color = ROLES[role] ?? C.a;
    const y = startY + i * (barH + gap);

    const labX = -totalW / 2 + labelW / 2;
    const labText = String(item.label ?? `${n}/${d}`);
    const lab = label(labText, [labX, y], color, 26);
    node.add(lab);
    parts[`bar${i}_label`] = [lab];

    const cellW = barW / d;
    const barStartX = -totalW / 2 + labelW + 20;
    const frameCells: Rect[] = [];
    const filledCells: Rect[] = [];

    for (let c = 0; c < d; c++) {
      const cx = barStartX + (c + 0.5) * cellW;
      const cell = <Rect width={cellW} height={barH} x={cx} y={y}
        stroke={C.dim} lineWidth={2} fill={C.fill} /> as Rect;
      frameCells.push(cell);
      node.add(cell);
      if (c < Math.min(n, d)) {
        const filled = <Rect width={cellW - 2} height={barH - 2} x={cx} y={y}
          fill={color + 'aa'} stroke={color} lineWidth={1} /> as Rect;
        filledCells.push(filled);
        node.add(filled);
      }
    }
    parts[`frame${i}`] = frameCells;
    parts[`bar${i}`] = [...filledCells, ...frameCells];
  });
  return {node, parts};
}


function graph(f: Record<string, any>, box: [number, number]): Drawn {
  const node = <Node /> as Node;
  const parts: Record<string, Node[]> = {};
  const graphW = Math.min(box[0] * 0.85, 480);
  const graphH = Math.min(box[1] * 0.8, 360);

  const rawX = f.x_range || [-5, 5];
  const a = Number(rawX[0] ?? -5), b = Number(rawX[1] ?? 5);
  const rawY = f.y_range;
  let lo = rawY ? Number(rawY[0]) : -5;
  let hi = rawY ? Number(rawY[1]) : 5;
  if (isNaN(lo) || isNaN(hi) || hi <= lo) { lo = -5; hi = 5; }

  const mapX = (x: number) => ((x - a) / (b - a || 1) - 0.5) * graphW;
  const mapY = (y: number) => -((y - lo) / (hi - lo || 1) - 0.5) * graphH;

  const y0 = Math.max(lo, Math.min(hi, 0));
  const x0 = Math.max(a, Math.min(b, 0));

  const xAxis = <Line points={[[mapX(a), mapY(y0)], [mapX(b), mapY(y0)]]} stroke={C.dim} lineWidth={2} /> as Line;
  const yAxis = <Line points={[[mapX(x0), mapY(lo)], [mapX(x0), mapY(hi)]]} stroke={C.dim} lineWidth={2} /> as Line;
  node.add([xAxis, yAxis]);
  parts.axes = [xAxis, yAxis];

  if (f.x_label) {
    const xlab = label(String(f.x_label), [mapX(b) + 24, mapY(y0)], C.dim, 20);
    node.add(xlab);
    parts.x_label = [xlab];
  }
  if (f.y_label) {
    const ylab = label(String(f.y_label), [mapX(x0), mapY(hi) - 24], C.dim, 20);
    node.add(ylab);
    parts.y_label = [ylab];
  }

  // Curves
  const funcs: string[] = Array.isArray(f.functions) ? f.functions : [];
  const labels = f.labels ?? {};
  funcs.forEach((fnStr, n) => {
    const fn = parseMathFunction(String(fnStr));
    if (!fn) return;
    const color = GRAPH_COLOURS[n % GRAPH_COLOURS.length];
    const steps = 150;
    const dx = (b - a) / steps;
    const segments: P[][] = [];
    let currentSeg: P[] = [];

    for (let i = 0; i <= steps; i++) {
      const x = a + i * dx;
      let y: number;
      try {
        y = fn(x);
      } catch {
        y = NaN;
      }
      if (Number.isFinite(y) && y >= lo - (hi - lo) * 0.1 && y <= hi + (hi - lo) * 0.1) {
        currentSeg.push([mapX(x), mapY(y)]);
      } else {
        if (currentSeg.length >= 2) segments.push(currentSeg);
        currentSeg = [];
      }
    }
    if (currentSeg.length >= 2) segments.push(currentSeg);

    const curveNodes: Node[] = [];
    segments.forEach(pts => {
      const line = <Line points={pts} stroke={color} lineWidth={4} lineCap="round" lineJoin="round" /> as Line;
      node.add(line);
      curveNodes.push(line);
    });
    parts[`curve${n}`] = curveNodes;

    const lblText = labels[`curve${n}`] ?? `y = ${fnStr}`;
    if (segments.length && segments[0].length) {
      const pt = segments[segments.length - 1][segments[segments.length - 1].length - 1];
      const clab = label(String(lblText), [pt[0] + 10, pt[1] - 15], color, 20);
      node.add(clab);
      parts[`curve${n}_label`] = [clab];
    }
  });

  // Points
  const pts = Array.isArray(f.points) ? f.points : [];
  pts.forEach((pt: any, i: number) => {
    if (!pt || typeof pt !== 'object') return;
    const x = Number(pt.x ?? 0);
    const y = Number(pt.y ?? (funcs.length ? (parseMathFunction(funcs[0])?.(x) ?? 0) : 0));
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    const role = String(pt.role ?? 'given');
    const color = ROLES[role] ?? C.a;
    const sx = mapX(x), sy = mapY(y);
    const dot = pt.open
      ? <Circle size={14} x={sx} y={sy} stroke={color} lineWidth={3} fill={C.fill} /> as Circle
      : <Circle size={14} x={sx} y={sy} fill={color} /> as Circle;
    node.add(dot);
    parts[`point${i}`] = [dot];
    if (pt.label) {
      const plab = label(String(pt.label), [sx + 15, sy - 15], color, 20);
      node.add(plab);
      parts[`point${i}_label`] = [plab];
    }
  });

  return {node, parts};
}

function shape(f: Record<string, any>, box: [number, number]): Drawn {
  const ptsMap: Record<string, [number, number]> = f.points ?? {};
  const allPts: P[] = Object.values(ptsMap);
  const {map} = fitter(allPts.length ? allPts : [[-2, -2], [2, 2]], box);
  const node = <Node /> as Node;
  const parts: Record<string, Node[]> = {};

  if (f.polygon && typeof f.polygon === 'string') {
    const polyPts = f.polygon.split('').map(ch => ptsMap[ch]).filter(Boolean).map(map);
    if (polyPts.length >= 3) {
      const poly = <Line points={polyPts} closed fill={C.fill} stroke={C.dim} lineWidth={3} /> as Line;
      node.add(poly);
      parts.polygon = [poly];
    }
  }

  // Segments
  const segs = Array.isArray(f.segments) ? f.segments : [];
  segs.forEach((seg: any, i: number) => {
    if (!seg || typeof seg !== 'object' || !seg.ends) return;
    const [p0, p1] = seg.ends.split('').map((ch: string) => ptsMap[ch]);
    if (!p0 || !p1) return;
    const line = <Line points={[map(p0), map(p1)]} stroke={seg.dashed ? C.dim : C.ink}
      lineWidth={seg.dashed ? 2 : 3} lineDash={seg.dashed ? [6, 6] : undefined} /> as Line;
    node.add(line);
    parts[`segment${i}`] = [line];
    parts[`segment_${seg.ends}`] = [line];
  });

  // Vertices and labels
  for (const [name, pt] of Object.entries(ptsMap)) {
    const mapped = map(pt);
    const dot = <Circle size={10} x={mapped[0]} y={mapped[1]} fill={C.ink} /> as Circle;
    const vlab = label(name, [mapped[0] + 16, mapped[1] - 16], C.ink, 22);
    node.add([dot, vlab]);
    parts[name] = [dot];
    parts[`${name}_label`] = [vlab];
  }

  return {node, parts};
}

export const KINDS: Record<string, (f: Record<string, any>, box: [number, number]) => Drawn> = {
  right_triangle: rightTriangle,
  circle,
  rectangle,
  number_line: numberLine,
  bars,
  graph,
  shape,
};

export function draw(f: Record<string, any> | undefined, box: [number, number]): Drawn | null {
  const make = f && KINDS[f.kind];
  return make ? make(f!, box) : null;
}
