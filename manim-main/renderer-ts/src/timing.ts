// Times inside one chapter, from timeline.json. All seconds, counted from the chapter's first beat.

export interface Sentence {text: string; start: number; duration: number}
export interface BeatTime {id: string; start: number; duration: number; sentences: Sentence[]}
export interface Step {say?: string; show?: string; kind?: string; focus?: string; highlight?: boolean}
export interface Beat {id: string; narration?: string; figure?: Record<string, any>; steps?: Step[]}
export interface RenderInput {
  version: 1;
  title: string;
  chapter: {id: number; title: string; beats: Beat[]};
  timeline: BeatTime[];
  audio?: string;
  width: number;
  height: number;
  fps: number;
}

const words = (s: string) =>
  s.toLowerCase().replace(/[^a-z0-9\s-]/g, ' ').split(/\s+/).filter(Boolean);

/** When the narrator starts saying `phrase` (beat-relative seconds), or null if it is never said. */
export function whenSaid(phrase: string, sentences: Sentence[]): number | null {
  const want = words(phrase);
  if (!want.length) return null;
  for (const s of sentences) {
    const w = words(s.text);
    for (let i = 0; i + want.length <= w.length; i++) {
      if (want.every((x, k) => w[i + k] === x)) return s.start + (s.duration * i) / Math.max(1, w.length);
    }
  }
  return null;
}

/** Beat-relative time for each step: when its words are said, else spread evenly through the speech. */
export function stepTimes(steps: Step[], t: BeatTime): number[] {
  const first = t.sentences[0]?.start ?? 0;
  const last = t.sentences.length ? t.sentences[t.sentences.length - 1] : undefined;
  const end = last ? last.start + last.duration : t.duration;
  let prev = first;
  return steps.map((s, i) => {
    const said = s.say ? whenSaid(s.say, t.sentences) : null;
    const guess = first + ((end - first) * (i + 0.5)) / steps.length;
    prev = Math.max(prev, said ?? guess);
    return prev;
  });
}
