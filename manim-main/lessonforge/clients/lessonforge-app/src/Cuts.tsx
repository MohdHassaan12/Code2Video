// Watch modes. One video serves a first-time learner and a student revising: a "cut" is
// the list of time ranges one way of watching keeps, and the player skips the rest.
//
//   useCuts     which cut is selected, and the skipping (fed by the player's time reports)
//   CutPicker   "How do you want to watch?": the chips, the selected cut's hint and
//               "Save this version"
//   CutEnd      over the video once a cut has run out: on into the full lesson from there
//
// A job with no cuts, or only the full one, offers nothing: all three stay out of the way.
import { RefObject, useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Linking, Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { api, Cut, Job, mediaUrl, Range, viewerMode } from './api';
import { clock, say } from './format';
import type { PlayerHandle } from './Player';
import { C } from './theme';

const FULL = 'full';
const NONE: Cut[] = [];
// A seek may land a little before the place asked for; that is still inside the range.
const EDGE_S = 0.3;
// The same skip is not issued twice within this long: a viewer dragging the scrubber
// through a skipped part is moved on once, not fought with on every report.
const AGAIN_MS = 2000;
// A cut that keeps the video's last moments ends when the video does.
const TAIL_S = 1;
// Closer than this, two positions are the same place.
const SAME_S = 0.5;

type Save = { state: 'busy' } | { state: 'ready'; url: string } | { state: 'failed'; message: string };

function within(ranges: Range[], t: number): boolean {
  return ranges.some(([start, end]) => t >= start - EDGE_S && t < end);
}

// The one tag a chapter chip has room for.
export function depthTag(depths: string[] | undefined): string {
  return ['core', 'basics', 'practice', 'extra'].find((depth) => depths?.includes(depth)) ?? '';
}

function openFile(url: string): void {
  if (Platform.OS === 'web' && typeof window !== 'undefined') window.open(url, '_blank', 'noopener');
  else Linking.openURL(url).catch(() => {});
}

export type Cuts = ReturnType<typeof useCuts>;

// `offer`: false where only the full lesson is to be watched (a student's review).
export function useCuts(server: string, job: Job, player: RefObject<PlayerHandle | null>, offer = true) {
  const listed = (offer && job.cuts) || NONE;
  const full = listed.find((cut) => cut.id === FULL);
  const offered = full && listed.length > 1 ? listed : NONE;
  const [selected, setSelected] = useState(FULL);
  const [ended, setEnded] = useState(false);
  const [saves, setSaves] = useState<Record<string, Save>>({});
  // What the player's reports are judged against; they arrive between renders.
  const live = useRef({
    cut: null as Cut | null,
    runsOut: false,
    at: 0,
    ended: false,
    skipped: { to: -1, wall: 0 },
    // Where choosing a cut moved the video from and to, until it is watched from there.
    moved: null as { from: number; to: number } | null,
  });
  const requests = useRef(new Set<AbortController>());
  useEffect(() => {
    const pending = requests.current;
    return () => pending.forEach((request) => request.abort());
  }, []);

  const current = offered.find((cut) => cut.id === selected) ?? full ?? null;
  const total = full ? full.ranges[full.ranges.length - 1][1] : 0;

  // `held`: something else (a question) is holding the video where it is.
  const onTime = useCallback(
    (now: number, held: boolean) => {
      const state = live.current;
      state.at = now;
      if (state.moved && Math.abs(now - state.moved.to) >= SAME_S) state.moved = null;
      const cut = state.cut;
      if (!cut || held) return;
      if (within(cut.ranges, now)) {
        if (state.ended) {
          state.ended = false;
          setEnded(false);
        }
        return;
      }
      const next = cut.ranges.find(([start]) => start > now);
      if (next) {
        const wall = Date.now();
        if (state.skipped.to === next[0] && wall - state.skipped.wall < AGAIN_MS) return;
        state.skipped = { to: next[0], wall };
        state.at = next[0];
        player.current?.moveTo(next[0]);
        return;
      }
      if (state.runsOut) return;
      // Past everything the cut keeps: it is over, though the video is not.
      player.current?.pause();
      if (!state.ended) {
        state.ended = true;
        setEnded(true);
      }
    },
    [player],
  );

  // True when the selected cut keeps this moment (the questions ask only what is watched).
  const keeps = useCallback((t: number) => {
    const cut = live.current.cut;
    return !cut || cut.ranges.some(([start, end]) => t >= start && t <= end);
  }, []);

  const select = (id: string) => {
    const cut = offered.find((one) => one.id === id);
    if (!cut) return;
    const state = live.current;
    state.cut = id === FULL ? null : cut;
    state.runsOut = total - cut.ranges[cut.ranges.length - 1][1] < TAIL_S;
    state.skipped = { to: -1, wall: 0 };
    state.ended = false;
    setEnded(false);
    setSelected(id);
    // Still where the last choice put it: that choice was a look, and this one starts
    // from where the viewer really was.
    const from = state.moved && Math.abs(state.at - state.moved.to) < SAME_S ? state.moved.from : state.at;
    const to = !state.cut || within(cut.ranges, from) ? from : cut.ranges[0][0];
    state.moved = null;
    if (Math.abs(to - state.at) < SAME_S) return;
    state.moved = { from, to };
    state.at = to;
    player.current?.moveTo(to);
  };

  // From the end of a cut: the same video, unabridged, from where the cut stopped.
  const resumeFull = () => {
    select(FULL);
    live.current.moved = null;
    player.current?.play();
  };

  // True when the selected cut keeps nothing of the stretch from `start` to `end`.
  const skips = (start: number, end: number) =>
    !!current && current.id !== FULL && !current.ranges.some(([from, to]) => from < end && to > start);

  const save = (cut: Cut) => {
    if (saves[cut.id]?.state === 'busy') return;
    const request = new AbortController();
    const settle = (result: Save) => {
      requests.current.delete(request);
      if (!request.signal.aborted) setSaves((old) => ({ ...old, [cut.id]: result }));
    };
    requests.current.add(request);
    setSaves((old) => ({ ...old, [cut.id]: { state: 'busy' } }));
    api.saveCut(server, job.job_id, cut.id, request.signal).then(
      (made) =>
        settle(
          typeof made?.video_url === 'string' && made.video_url
            ? { state: 'ready', url: mediaUrl(server, made.video_url) }
            : { state: 'failed', message: 'The server returned no file.' },
        ),
      (error) => settle({ state: 'failed', message: say(error).slice(0, 140) }),
    );
  };

  return {
    offered,
    current,
    total,
    // The ranges playback is held to; null while the whole video plays.
    ranges: current && current.id !== FULL ? current.ranges : null,
    ended,
    saved: current ? saves[current.id] : undefined,
    onTime,
    keeps,
    select,
    showFull: () => select(FULL),
    resumeFull,
    skips,
    save,
  };
}

export function CutPicker({ cuts }: { cuts: Cuts }) {
  const { current, offered, saved } = cuts;
  if (!current || offered.length === 0) return null;
  return (
    <View style={styles.picker}>
      <Text style={styles.heading}>How do you want to watch?</Text>
      <View style={styles.chips} role="radiogroup" aria-label="How do you want to watch?">
        {offered.map((cut) => {
          const on = cut.id === current.id;
          return (
            <Pressable
              key={cut.id}
              role="radio"
              aria-checked={on}
              aria-label={`${cut.label}, ${clock(cut.seconds)}`}
              onPress={() => cuts.select(cut.id)}
              style={({ pressed }) => [styles.chip, on && styles.chipOn, pressed && styles.pressed]}>
              <Text style={[styles.chipText, on && styles.chipTextOn]}>
                {on ? '✓ ' : ''}
                {cut.label} <Text style={styles.time}>{clock(cut.seconds)}</Text>
              </Text>
            </Pressable>
          );
        })}
      </View>
      <View style={styles.under}>
        {current.hint ? <Text style={styles.hint}>{current.hint}</Text> : null}
        {/* Saving a cut writes a new file: the viewer site makes nothing, so it is only offered on the studio. */}
        {current.id === FULL || viewerMode() ? null : saved?.state === 'busy' ? (
          <View style={styles.waiting}>
            <ActivityIndicator color={C.teal} size="small" />
            <Text style={styles.hint}>Preparing…</Text>
          </View>
        ) : saved?.state === 'ready' ? (
          <Pressable accessibilityRole="link" onPress={() => openFile(saved.url)} style={({ pressed }) => [styles.link, pressed && styles.pressed]}>
            <Text style={styles.linkText}>Open the saved video ↗</Text>
          </Pressable>
        ) : (
          <Pressable accessibilityRole="button" onPress={() => cuts.save(current)} style={({ pressed }) => [styles.link, pressed && styles.pressed]}>
            <Text style={styles.linkText}>Save this version</Text>
          </Pressable>
        )}
      </View>
      {current.id !== FULL && !viewerMode() && saved?.state === 'failed' ? (
        <Text style={styles.error} aria-live="polite">
          Could not save this version. {saved.message}
        </Text>
      ) : null}
    </View>
  );
}

// "Quick revision" → "End of quick revision"; an acronym keeps its capitals.
function inSentence(label: string): string {
  return /^[A-Z][a-z]/.test(label) ? label[0].toLowerCase() + label.slice(1) : label;
}

export function CutEnd({ cuts }: { cuts: Cuts }) {
  if (!cuts.ended || !cuts.current) return null;
  return (
    <View style={styles.end}>
      <View style={styles.endCard}>
        <Text style={styles.endText}>End of {inSentence(cuts.current.label)}</Text>
        <Pressable accessibilityRole="button" onPress={cuts.resumeFull} style={({ pressed }) => [styles.endButton, pressed && styles.pressed]}>
          <Text style={styles.endButtonText}>Watch the full lesson</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  picker: { gap: 8 },
  heading: { color: C.muted, fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: 1, borderColor: C.line, backgroundColor: C.panel, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 9 },
  chipOn: { borderColor: C.teal },
  chipText: { color: C.muted, fontSize: 14 },
  chipTextOn: { color: C.teal },
  time: { fontVariant: ['tabular-nums'] },
  pressed: { opacity: 0.7 },
  under: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', columnGap: 14, rowGap: 4 },
  hint: { color: C.muted, fontSize: 13, lineHeight: 19 },
  waiting: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  // Text buttons, with padding that widens the tap target without moving the layout.
  link: { padding: 10, margin: -10 },
  linkText: { color: C.teal, fontSize: 13, lineHeight: 19, fontWeight: '600', textDecorationLine: 'underline' },
  error: { color: C.pink, fontSize: 13, lineHeight: 19 },
  // Along the top of the video, clear of the transport controls at the bottom.
  end: { position: 'absolute', top: 8, left: 8, right: 8, alignItems: 'center', pointerEvents: 'box-none' },
  endCard: {
    maxWidth: '100%',
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'center',
    columnGap: 12,
    rowGap: 6,
    backgroundColor: 'rgba(11, 18, 32, 0.94)',
    borderWidth: 1,
    borderColor: C.line,
    borderRadius: 12,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  endText: { color: C.ink, fontSize: 14, fontWeight: '600' },
  endButton: { backgroundColor: C.teal, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 8 },
  endButtonText: { color: C.bg, fontSize: 14, fontWeight: '600' },
});
