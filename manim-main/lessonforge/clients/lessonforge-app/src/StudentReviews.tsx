// Student reviews, for the lesson's owner: the link to hand to students, how many
// reviews have come back, and what they say — ratings, choices, the parts marked
// confusing (tap a time to watch it), and the written answers. Owner token only: a
// student's review link is refused these calls, and never reaches this card.
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, Share, StyleSheet, Text, View } from 'react-native';

import { api, FeedbackSummary, Job, statusOf } from './api';
import { clock, say } from './format';
import { C } from './theme';

type Link = { state: 'idle' } | { state: 'busy' } | { state: 'ready'; url: string; copied: boolean } | { state: 'failed'; message: string };

const TEXTS_SHOWN = 5;
const TOP_CHAPTERS = 3;
const BAR_HEIGHT = 34;

// The page students open is served by the server itself; in a browser that is this origin.
function linkBase(server: string): string {
  const here = Platform.OS === 'web' && typeof window !== 'undefined' ? window.location : null;
  return here && here.pathname.startsWith('/app') ? here.origin : server;
}

function whyNot(error: unknown): string {
  const status = statusOf(error);
  if (status === 401 || status === 403) return 'Student reviews are shown only with the owner’s access token.';
  if (status === 404) return 'This server does not keep student reviews for this lesson.';
  return `Student reviews could not be loaded. ${say(error)}`;
}

export function StudentReviews({ server, job, onSeek }: { server: string; job: Job; onSeek: (seconds: number) => void }) {
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(true);
  const [summary, setSummary] = useState<FeedbackSummary | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [link, setLink] = useState<Link>({ state: 'idle' });
  // Text questions whose every answer is shown.
  const [opened, setOpened] = useState<string[]>([]);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  // Briefly delayed, so typing a server URL does not send a request per keystroke.
  useEffect(() => {
    let stopped = false;
    const request = new AbortController();
    const timer = setTimeout(() => {
      api.feedbackSummary(server, job.job_id, request.signal).then(
        (found) => {
          if (stopped) return;
          setSummary(found);
          setFailure(null);
          setBusy(false);
        },
        (error) => {
          if (stopped) return;
          setFailure(whyNot(error));
          setBusy(false);
        },
      );
    }, 300);
    return () => {
      stopped = true;
      clearTimeout(timer);
      request.abort();
    };
  }, [server, job.job_id, attempt]);

  const refresh = () => {
    setBusy(true);
    setAttempt((n) => n + 1);
  };

  const copyLink = async () => {
    if (link.state === 'busy') return;
    setLink({ state: 'busy' });
    try {
      const { path } = await api.reviewLink(server, job.job_id);
      if (typeof path !== 'string' || !path) throw new Error('The server returned no link.');
      const url = linkBase(server) + path;
      let copied = false;
      if (Platform.OS === 'web') {
        try {
          await navigator.clipboard.writeText(url);
          copied = true;
        } catch {
          // No clipboard here (an insecure page, or permission refused): the link is shown to copy by hand.
        }
      }
      if (!alive.current) return;
      setLink({ state: 'ready', url, copied });
      if (Platform.OS !== 'web') await Share.share({ message: url }).catch(() => {});
    } catch (error) {
      if (alive.current) setLink({ state: 'failed', message: say(error) });
    }
  };

  const count = summary?.count ?? 0;
  const titles = new Map((job.chapters ?? []).map((chapter) => [String(chapter.id), chapter.title]));
  const ratings = Object.entries(summary?.ratings ?? {}).filter(([, rating]) => rating.n > 0 && rating.mean !== null);
  const choices = Object.entries(summary?.choices ?? {}).filter(([, choice]) => Object.values(choice.counts ?? {}).some((n) => n > 0));
  const chapterPicks = Object.entries(summary?.chapters ?? {})
    .map(([id, picked]) => ({
      id,
      prompt: picked.prompt,
      top: Object.entries(picked.counts ?? {})
        .filter(([, n]) => n > 0)
        .sort((a, b) => b[1] - a[1])
        .slice(0, TOP_CHAPTERS),
    }))
    .filter((picked) => picked.top.length > 0);
  const moments = summary?.confused_at ?? [];
  const texts = Object.entries(summary?.texts ?? {}).filter(([, written]) => (written.items ?? []).length > 0);
  const share = summary?.quiz?.mean_correct_share;

  return (
    <View style={styles.card}>
      <View style={styles.head}>
        <Text style={styles.title}>Student reviews</Text>
        {busy ? <ActivityIndicator color={C.teal} size="small" /> : null}
        <Pressable accessibilityRole="button" disabled={busy} onPress={refresh} style={({ pressed }) => [styles.link, (pressed || busy) && styles.pressed]}>
          <Text style={styles.linkText}>Refresh</Text>
        </Pressable>
      </View>

      {failure ? (
        <Text style={styles.fine}>{failure}</Text>
      ) : summary ? (
        <>
          <View style={styles.row}>
            <Pressable
              accessibilityRole="button"
              disabled={link.state === 'busy'}
              onPress={copyLink}
              style={({ pressed }) => [styles.button, (pressed || link.state === 'busy') && styles.pressed]}>
              <Text style={styles.buttonText}>{link.state === 'busy' ? 'Getting the link…' : 'Copy review link'}</Text>
            </Pressable>
            <Text style={styles.count}>{count === 0 ? 'No reviews yet' : `${count} review${count === 1 ? '' : 's'}`}</Text>
          </View>
          {link.state === 'ready' ? (
            <View style={styles.linkBox} aria-live="polite">
              <Text style={styles.fine}>{link.copied ? '✓ Link copied. Send it to your students:' : 'Send this link to your students:'}</Text>
              <Text selectable style={styles.url}>
                {link.url}
              </Text>
            </View>
          ) : link.state === 'failed' ? (
            <Text style={styles.problem}>The link could not be made. {link.message}</Text>
          ) : count === 0 ? (
            <Text style={styles.fine}>Students open the link, watch the lesson and answer a short form. Their answers show up here.</Text>
          ) : null}

          {count > 0 ? (
            <>
              {(summary.signals ?? []).length > 0 ? (
                <View style={styles.block}>
                  <Text style={styles.label}>Worth a look</Text>
                  {(summary.signals ?? []).map((signal, index) => (
                    <Text key={index} style={styles.signal}>
                      • {signal.message}
                    </Text>
                  ))}
                </View>
              ) : null}

              {ratings.length > 0 ? (
                <View style={styles.grid}>
                  {ratings.map(([id, rating]) => (
                    <View key={id} style={styles.rating}>
                      <Text style={styles.prompt}>{rating.prompt}</Text>
                      <View style={styles.ratingRow}>
                        <View>
                          <Text style={styles.mean}>{(rating.mean ?? 0).toFixed(1)}</Text>
                          <Text style={styles.fine}>
                            of 5 · {rating.n} answer{rating.n === 1 ? '' : 's'}
                          </Text>
                        </View>
                        <Histogram counts={rating.histogram ?? []} />
                      </View>
                    </View>
                  ))}
                </View>
              ) : null}

              {choices.map(([id, choice]) => (
                <View key={id} style={styles.block}>
                  <Text style={styles.prompt}>{choice.prompt}</Text>
                  <Text style={styles.body}>
                    {Object.entries(choice.counts)
                      .map(([value, n]) => `${choice.labels?.[value] ?? value} ${n}`)
                      .join(' · ')}
                  </Text>
                </View>
              ))}

              {chapterPicks.map((picked) => (
                <View key={picked.id} style={styles.block}>
                  <Text style={styles.prompt}>{picked.prompt}</Text>
                  {picked.top.map(([chapter, n]) => (
                    <Text key={chapter} style={styles.body}>
                      {titles.get(chapter) ?? `Chapter ${chapter}`} — {n}
                    </Text>
                  ))}
                </View>
              ))}

              {moments.length > 0 ? (
                <View style={styles.block}>
                  <Text style={styles.prompt}>Marked as confusing — tap a time to watch it</Text>
                  <View style={styles.chips}>
                    {moments.map((moment) => (
                      <Pressable
                        key={moment.t}
                        accessibilityRole="button"
                        aria-label={`Watch from ${clock(moment.t)}, marked ${moment.count} time${moment.count === 1 ? '' : 's'}`}
                        onPress={() => onSeek(moment.t)}
                        style={({ pressed }) => [styles.chip, pressed && styles.pressed]}>
                        <Text style={styles.chipText}>
                          <Text style={styles.time}>{clock(moment.t)}</Text>
                          {`  ×${moment.count}`}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                </View>
              ) : null}

              {typeof share === 'number' ? (
                <Text style={styles.body}>
                  Questions in the video: {Math.round(share * 100)}% answered right on average ({summary.quiz?.responses ?? 0} viewing
                  {summary.quiz?.responses === 1 ? '' : 's'}).
                </Text>
              ) : null}

              {texts.map(([id, written]) => {
                const all = opened.includes(id);
                const items = all ? written.items : written.items.slice(0, TEXTS_SHOWN);
                return (
                  <View key={id} style={styles.block}>
                    <Text style={styles.prompt}>{written.prompt}</Text>
                    {items.map((item, index) => (
                      <Text key={index} style={styles.quote}>
                        “{item.text}”{item.reviewer ? <Text style={styles.fine}>{`  — ${item.reviewer}`}</Text> : null}
                      </Text>
                    ))}
                    {written.items.length > TEXTS_SHOWN ? (
                      <Pressable
                        accessibilityRole="button"
                        onPress={() => setOpened(all ? opened.filter((one) => one !== id) : [...opened, id])}
                        style={({ pressed }) => [styles.link, styles.linkStart, pressed && styles.pressed]}>
                        <Text style={styles.linkText}>{all ? 'Show fewer' : `Show all ${written.items.length}`}</Text>
                      </Pressable>
                    ) : null}
                  </View>
                );
              })}
            </>
          ) : null}
        </>
      ) : null}
    </View>
  );
}

// Five bars, 1 to 5, each with its count: readable without colour or hover.
function Histogram({ counts }: { counts: number[] }) {
  const bars = [0, 1, 2, 3, 4].map((i) => (Number.isFinite(counts[i]) ? counts[i] : 0));
  const top = Math.max(1, ...bars);
  return (
    <View style={styles.bars} aria-label={bars.map((n, i) => `${i + 1}: ${n}`).join(', ')}>
      {bars.map((n, i) => (
        <View key={i} style={styles.barColumn}>
          <Text style={styles.barCount}>{n}</Text>
          <View style={[styles.bar, { height: n > 0 ? Math.max(3, (BAR_HEIGHT * n) / top) : 1 }, n > 0 && styles.barOn]} />
          <Text style={styles.barLabel}>{i + 1}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 14, padding: 14, gap: 12 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  title: { flex: 1, color: C.ink, fontSize: 16, fontWeight: '600' },
  row: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', columnGap: 14, rowGap: 8 },
  button: { borderWidth: 1, borderColor: C.teal, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 10, minHeight: 44, justifyContent: 'center' },
  buttonText: { color: C.teal, fontSize: 15, fontWeight: '600' },
  count: { color: C.ink, fontSize: 15, fontWeight: '600' },
  linkBox: { gap: 4 },
  url: { color: C.ink, fontSize: 13, lineHeight: 19, fontFamily: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' }) },
  fine: { color: C.muted, fontSize: 13, lineHeight: 19 },
  problem: { color: C.pink, fontSize: 13, lineHeight: 19 },
  block: { gap: 4 },
  label: { color: C.gold, fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase', fontWeight: '600' },
  signal: { color: C.gold, fontSize: 14, lineHeight: 20 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  rating: { flexGrow: 1, flexBasis: 250, borderWidth: 1, borderColor: C.line, borderRadius: 10, padding: 10, gap: 6 },
  ratingRow: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: 12 },
  prompt: { color: C.muted, fontSize: 13, lineHeight: 18 },
  mean: { color: C.teal, fontSize: 26, fontWeight: '600', fontVariant: ['tabular-nums'] },
  body: { color: C.ink, fontSize: 14, lineHeight: 20 },
  quote: { color: C.ink, fontSize: 14, lineHeight: 20, borderLeftWidth: 2, borderLeftColor: C.line, paddingLeft: 10 },
  bars: { flexDirection: 'row', alignItems: 'flex-end', gap: 5 },
  barColumn: { width: 20, alignItems: 'center', gap: 2 },
  barCount: { color: C.muted, fontSize: 10, fontVariant: ['tabular-nums'] },
  bar: { width: 14, backgroundColor: C.line, borderRadius: 2 },
  barOn: { backgroundColor: C.teal },
  barLabel: { color: C.muted, fontSize: 11, fontVariant: ['tabular-nums'] },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 2 },
  chip: { borderWidth: 1, borderColor: C.line, backgroundColor: C.bg, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 9 },
  chipText: { color: C.muted, fontSize: 14 },
  time: { color: C.teal, fontVariant: ['tabular-nums'] },
  // Text buttons, with padding that widens the tap target without moving the layout.
  link: { padding: 10, margin: -10 },
  linkStart: { alignSelf: 'flex-start', marginTop: -4 },
  linkText: { color: C.teal, fontSize: 14, fontWeight: '600', textDecorationLine: 'underline' },
  pressed: { opacity: 0.6 },
});
