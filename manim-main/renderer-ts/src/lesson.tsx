// One lessonforge chapter, drawn from render_input.json (lesson.json beats + timeline.json times).
import {Latex, Layout, makeScene2D, Node, Rect, Txt} from '@revideo/2d';
import {all, createRef, ThreadGenerator, useScene, waitFor} from '@revideo/core';
import {C, draw, Drawn} from './figures';
import {RenderInput, Step, stepTimes} from './timing';

const FONT = 'Inter, Helvetica, Arial, sans-serif';

function card(step: Step, width: number): Node {
  const text = String(step.show ?? '');
  if (step.kind === 'math') {
    return <Latex tex={`\\color{white}{${text}}`} height={46} /> as Node;
  }
  const key = step.kind === 'key' || step.highlight;
  return (
    <Rect fill={key ? '#facc1522' : '#00000000'} stroke={key ? C.accent : '#00000000'} lineWidth={2} radius={10}
      padding={[10, 16]} layout>
      <Txt text={text} fill={key ? C.accent : C.ink} fontSize={30} fontFamily={FONT} fontWeight={key ? 700 : 500}
        textWrap maxWidth={width} />
    </Rect>) as Node;
}

function* glow(nodes: Node[]): ThreadGenerator {
  yield* all(...nodes.map(n => n.scale(1.12, 0.25).to(1, 0.35)));
}

export default makeScene2D('lesson', function* (view) {
  const input = useScene().variables.get('input', null as unknown as RenderInput)();
  const W = input.width, H = input.height;
  view.fill('#0f172a');
  const u = W / 1280; // layout below is in 1280x720 units
  const root = <Node scale={u} /> as Node;
  view.add(root);
  root.add(<Txt text={input.chapter.title} x={-600} y={-322} offsetX={-1} fill={C.dim} fontSize={24}
    fontFamily={FONT} fontWeight={700} letterSpacing={2} />);
  const caption = createRef<Txt>();
  root.add(<Txt ref={caption} text="" y={310} fill={C.ink} fontSize={26} fontFamily={FONT} textWrap
    textAlign="center" width={1100} />);
  const figBox: [number, number] = [600, 470];
  const figAt = {x: -300, y: 0};
  const board = createRef<Layout>();
  root.add(<Layout ref={board} layout direction="column" gap={22} alignItems="start" x={330} y={-40}
    width={520} height={520} />);

  let now = 0;
  const at = function* (t: number): ThreadGenerator {
    if (t > now) { yield* waitFor(t - now); now = t; }
  };
  const byId = new Map(input.timeline.map(t => [t.id, t]));
  const t0 = input.timeline.length ? input.timeline[0].start : 0;

  let carriedFig: Drawn | null = null;
  let carriedKey: string | null = null;

  for (let bi = 0; bi < input.chapter.beats.length; bi++) {
    const beat = input.chapter.beats[bi];
    const nextBeat = input.chapter.beats[bi + 1];
    const tb = byId.get(beat.id);
    if (!tb) continue;
    const start = tb.start - t0;
    yield* at(start);

    // Picture for this beat: keep the carried figure across beats unless it changes or is turned off.
    const off = (beat as any).picture === 'off';
    const spec = off ? null : (beat.figure ?? (carriedFig ? null : undefined));
    const key = spec ? JSON.stringify(spec) : null;

    let fig: Drawn | null = null;

    if (off) {
      if (carriedFig) {
        yield carriedFig.node.opacity(0, 0.3);
        carriedFig.node.remove();
        carriedFig = null;
        carriedKey = null;
      }
    } else if (key && key !== carriedKey) {
      // A new/different figure replaces the old one.
      if (carriedFig) {
        yield carriedFig.node.opacity(0, 0.3);
        carriedFig.node.remove();
      }
      fig = draw(spec ?? undefined, figBox);
      if (fig) {
        fig.node.position([figAt.x, figAt.y]);
        fig.node.opacity(0);
        root.add(fig.node);
        yield fig.node.opacity(1, 0.4);
      }
      carriedFig = fig;
      carriedKey = key;
    } else if (carriedFig) {
      // Kept from previous beat.
      fig = carriedFig;
    } else if (spec) {
      fig = draw(spec ?? undefined, figBox);
      if (fig) {
        fig.node.position([figAt.x, figAt.y]);
        fig.node.opacity(0);
        root.add(fig.node);
        yield fig.node.opacity(1, 0.4);
      }
      carriedFig = fig;
      carriedKey = key;
    }

    // Events inside the beat, in time order.
    const steps = beat.steps ?? [];
    const times = stepTimes(steps, tb);
    type Ev = {t: number; run: () => ThreadGenerator | void};
    const evs: Ev[] = [];
    for (const s of tb.sentences) evs.push({t: start + s.start, run: () => { caption().text(s.text); }});
    steps.forEach((s, i) => evs.push({t: start + times[i], run: () => {
      const c = card(s, 500);
      c.opacity(0);
      board().add(c);
      const moves: ThreadGenerator[] = [c.opacity(1, 0.35)];
      if (fig && s.focus && fig.parts[s.focus]) moves.push(glow(fig.parts[s.focus]));
      const own = fig?.onFocus?.(s.focus ?? '');
      if (own) moves.push(own);
      const st = fig?.onStep?.(i, i === steps.length - 1);
      if (st) moves.push(st);
      return all(...moves);
    }}));
    evs.sort((x, y) => x.t - y.t);
    for (const e of evs) {
      yield* at(e.t);
      const g = e.run();
      if (g) yield g;
    }

    // End of the beat: clear board and caption; clear picture only if next beat replaces it or turns it off, or at chapter end.
    const nextOff = nextBeat && ((nextBeat as any).picture === 'off');
    const nextSpec = nextBeat ? (nextOff ? null : (nextBeat.figure ?? (carriedFig ? null : undefined))) : null;
    const nextKey = nextSpec ? JSON.stringify(nextSpec) : null;
    const willRetireFig = !nextBeat || nextOff || (nextKey && nextKey !== carriedKey);

    yield* at(Math.max(now, start + tb.duration - 0.35));
    const old = [...board().children()];
    const fadeMoves: ThreadGenerator[] = old.map(n => n.opacity(0, 0.3));
    if (willRetireFig && carriedFig) {
      fadeMoves.push(carriedFig.node.opacity(0, 0.3));
    }
    yield all(...fadeMoves);
    yield* at(start + tb.duration);
    old.forEach(n => n.remove());
    if (willRetireFig && carriedFig) {
      carriedFig.node.remove();
      carriedFig = null;
      carriedKey = null;
    }
    caption().text('');
  }
});
