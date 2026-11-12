// The owner's dashboard: who opened the app, what they made and watched, what came back
// as reviews, and what it cost. One call (GET /stats) answers all of it; the screen asks
// again every half minute while it is open.
//
// Visits, visitors and plays are counted from the day the server began recording them;
// lessons, conversations and spend are read from what the server already keeps, so those
// go back further. The screen says which is which. Owner token only.
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { api, dashboardTests, JobStatus, Stats, StatsDay, StatsEvent, StatsVisitor, statusOf } from './api';
import { ago, clock, say } from './format';
import { C } from './theme';

const PERIODS = [
  { days: 1, label: 'Today' },
  { days: 7, label: '7 days' },
  { days: 30, label: '30 days' },
  { days: 0, label: 'All time' },
];
type Metric = 'visits' | 'lessons' | 'plays' | 'spend';
const METRICS: { key: Metric; label: string }[] = [
  { key: 'visits', label: 'Visits' },
  { key: 'lessons', label: 'Lessons made' },
  { key: 'plays', label: 'Video plays' },
  { key: 'spend', label: 'Spend' },
];
const REFRESH_MS = 30_000;
const COLUMNS_MAX = 31;
const CHART_HEIGHT = 96;
const VISITORS_SHOWN = 8;
const EVENTS_SHOWN = 12;
const LESSONS_SHOWN = 10;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const STATUS_TONE: Record<JobStatus, string> = { done: C.teal, running: C.gold, queued: C.gold, failed: C.pink };
const SCREEN_NAMES: Record<string, string> = {
  ask: 'describing a lesson',
  script: 'pasting a script',
  confirm: 'checking the brief',
  making: 'waiting for a video',
  watch: 'watching a lesson',
  failed: 'looking at a failed lesson',
  feedback: 'the feedback form',
  dashboard: 'this dashboard',
  review: 'reviewing a lesson',
};

function money(amount: number): string {
  return `$${amount.toFixed(2)}`;
}

function two(n: number): string {
  return String(n).padStart(2, '0');
}

// A moment on the viewer's clock: the time today, the date too on any other day.
function when(at: number, now: number): string {
  const then = new Date(at * 1000);
  const today = new Date(now * 1000);
  const time = `${two(then.getHours())}:${two(then.getMinutes())}`;
  const sameDay = then.getFullYear() === today.getFullYear() && then.getMonth() === today.getMonth() && then.getDate() === today.getDate();
  return sameDay ? time : `${then.getDate()} ${MONTHS[then.getMonth()]}, ${time}`;
}

// "2026-10-08" → "8", with the month where a reader needs it (the first column, a new month).
function dayLabel(day: string, first: boolean): string {
  const [, month, date] = day.split('-').map(Number);
  return first || date === 1 ? `${date} ${MONTHS[month - 1] ?? ''}` : String(date);
}

function country(code: string): string {
  try {
    return new Intl.DisplayNames(['en'], { type: 'region' }).of(code) ?? code;
  } catch {
    return code; // an engine without Intl.DisplayNames
  }
}

function named(text: string): string {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

function who(visitor: string, me: string | null | undefined): string {
  return `Visitor ${visitor.slice(-4).toUpperCase()}${visitor === me ? ' (you)' : ''}`;
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

// What one recorded event means, in words.
function told(event: StatsEvent): string {
  const title = event.title ? `“${event.title}”` : 'a lesson';
  switch (event.event) {
    case 'visit':
      return 'opened the app';
    case 'intake_start':
      return 'started describing a lesson';
    case 'generate':
      return `asked for a video: ${title}`;
    case 'play':
      return `played ${title}${event.value && event.value !== 'full' ? ` (${event.value} version)` : ''}`;
    case 'progress':
      return event.value === 100 ? `watched ${title} to the end` : `watched ${event.value}% of ${title}`;
    case 'review_sent':
      return `sent a student review of ${title}`;
    case 'tester_feedback':
      return 'sent tester feedback';
    case 'cut_export':
      return `saved the ${event.value ?? ''} version of ${title}`;
    case 'plan':
      return 'planned a chapter';
    default:
      return event.event;
  }
}

function whyNot(error: unknown): string {
  const status = statusOf(error);
  if (status === 401 || status === 403) return 'The dashboard is shown only with the owner’s access token.';
  if (status === 404) return 'This server does not have the dashboard yet. It appears after the server is restarted on the current version.';
  return `The dashboard could not be loaded. ${say(error)}`;
}

export function Dashboard({ server, onOpen }: { server: string; onOpen: (jobId: string) => void }) {
  const [days, setDays] = useState(7);
  const [countMe, setCountMe] = useState(true);
  const [metric, setMetric] = useState<Metric>('visits');
  const [attempt, setAttempt] = useState(0);
  const [stats, setStats] = useState<Stats | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  // True while the numbers on screen are for another period than the one chosen.
  const [stale, setStale] = useState(true);
  const [allVisitors, setAllVisitors] = useState(false);
  const [allEvents, setAllEvents] = useState(false);
  const [allLessons, setAllLessons] = useState(false);
  // Read once: whether this was opened to check the app's own test browsers.
  const [tests] = useState(dashboardTests);

  useEffect(() => {
    let stopped = false;
    const request = new AbortController();
    api.stats(server, days, countMe, tests, request.signal).then(
      (found) => {
        if (stopped) return;
        setStats(found);
        setFailure(null);
        setStale(false);
      },
      (error) => {
        if (stopped) return;
        setFailure(whyNot(error));
        setStale(false);
      },
    );
    const timer = setTimeout(() => setAttempt((n) => n + 1), REFRESH_MS);
    return () => {
      stopped = true;
      clearTimeout(timer);
      request.abort();
    };
  }, [server, days, countMe, tests, attempt]);

  const choose = (next: number) => {
    if (next === days) return;
    setStale(true);
    setDays(next);
  };
  const toggleMe = () => {
    setStale(true);
    setCountMe((on) => !on);
  };

  const period = PERIODS.find((p) => p.days === days)?.label ?? `${days} days`;
  return (
    <View style={styles.page}>
      <View style={styles.controls}>
        <View style={styles.chips}>
          {PERIODS.map((p) => (
            <Pressable
              key={p.days}
              accessibilityRole="button"
              accessibilityState={{ selected: p.days === days }}
              onPress={() => choose(p.days)}
              style={[styles.chip, p.days === days && styles.chipOn]}>
              <Text style={[styles.chipText, p.days === days && styles.chipTextOn]}>{p.label}</Text>
            </Pressable>
          ))}
        </View>
        <Pressable accessibilityRole="switch" accessibilityState={{ checked: countMe }} onPress={toggleMe} style={[styles.chip, countMe && styles.chipOn]}>
          <Text style={[styles.chipText, countMe && styles.chipTextOn]}>{countMe ? 'Counting my own visits' : 'Leaving my own visits out'}</Text>
        </Pressable>
      </View>

      {failure ? <Text style={styles.problem}>{failure}</Text> : null}
      {!stats && !failure ? (
        <View style={styles.loading}>
          <ActivityIndicator color={C.teal} size="small" />
          <Text style={styles.fine}>Counting…</Text>
        </View>
      ) : null}

      {stats ? (
        <View style={[styles.sections, stale && styles.stale]}>
          <Text style={styles.fine}>
            {period} · updated {when(stats.generated_at, stats.generated_at)}
            {stats.totals.online > 0 ? ` · ${plural(stats.totals.online, 'person', 'people')} on the app now` : ''}
          </Text>
          <Budget stats={stats} />
          <Tiles stats={stats} />
          {stats.series.length > 1 ? (
            <View style={styles.card}>
              <View style={styles.head}>
                <Text style={styles.cardTitle}>Each day</Text>
                <View style={styles.metrics}>
                  {METRICS.map((m) => (
                    <Pressable
                      key={m.key}
                      accessibilityRole="button"
                      accessibilityState={{ selected: m.key === metric }}
                      onPress={() => setMetric(m.key)}
                      style={[styles.smallChip, m.key === metric && styles.chipOn]}>
                      <Text style={[styles.smallChipText, m.key === metric && styles.chipTextOn]}>{m.label}</Text>
                    </Pressable>
                  ))}
                </View>
              </View>
              <Columns series={stats.series} metric={metric} />
              {metric === 'visits' || metric === 'plays' ? <Since stats={stats} /> : null}
            </View>
          ) : null}
          <Funnel stats={stats} />
          <Lessons stats={stats} all={allLessons} onAll={() => setAllLessons(true)} onOpen={onOpen} />
          <Visitors stats={stats} all={allVisitors} onAll={() => setAllVisitors(true)} />
          <Recent stats={stats} all={allEvents} onAll={() => setAllEvents(true)} />
          <Text style={styles.fine}>
            A visitor is one browser or phone, counted with a random cookie: no names, addresses or accounts are stored. Opening the app
            again within 30 minutes is the same visit.{' '}
            {tests ? 'The automated browsers used to test the app are counted here too.' : 'The automated browsers used to test the app are left out.'}
            {stats.totals.blocked > 0 ? ` ${plural(stats.totals.blocked, 'request')} without a valid key ${stats.totals.blocked === 1 ? 'was' : 'were'} refused in this period.` : ''}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

// Visits are newer than lessons and spend: say from when, wherever a visit number is read.
function Since({ stats }: { stats: Stats }) {
  return (
    <Text style={styles.fine}>
      {stats.tracking_since
        ? `Visits and plays are counted since ${when(stats.tracking_since, stats.generated_at)}. Lessons, conversations and spend go back further.`
        : 'No visit has been recorded yet. Lessons, conversations and spend below come from what the server already keeps.'}
    </Text>
  );
}

function Budget({ stats }: { stats: Stats }) {
  const { remaining, budget, per_finished_lesson: each } = stats.spend;
  if (remaining === null || budget === null) return null;
  const left = each && each > 0 ? Math.floor(Math.max(0, remaining) / each) : null;
  const low = remaining <= 0 || (left !== null && left <= 5);
  if (!low) return null;
  return (
    <View style={styles.banner}>
      <Text style={styles.bannerText}>
        {remaining <= 0
          ? `The ${money(budget)} budget is used up: new lessons will fail until it is raised on the server.`
          : `${money(remaining)} of the ${money(budget)} budget is left${
              left !== null && each ? `: about ${plural(left, 'more lesson')} at ${money(each)} each` : ''
            }. New lessons fail once it is used up.`}
      </Text>
    </View>
  );
}

function Tiles({ stats }: { stats: Stats }) {
  const t = stats.totals;
  const { spend } = stats;
  const tiles: { label: string; value: string; note: string; tone?: string }[] = [
    { label: 'Visitors', value: String(t.visitors), note: `${t.new_visitors} new · ${plural(t.visits, 'visit')}` },
    { label: 'Conversations', value: String(t.intakes), note: `${t.intakes_completed} reached a full brief` },
    {
      label: 'Lessons made',
      value: String(t.lessons),
      note: [`${t.finished} finished`, t.failed ? `${t.failed} failed` : '', t.in_progress ? `${t.in_progress} in progress` : ''].filter(Boolean).join(' · '),
      tone: t.failed > 0 && t.failed >= t.finished ? C.pink : undefined,
    },
    { label: 'Video plays', value: String(t.plays), note: `by ${plural(t.viewers, 'visitor')}` },
    { label: 'Reviews', value: String(t.student_reviews + t.tester_forms), note: `${t.student_reviews} student · ${t.tester_forms} tester` },
    {
      label: 'Spend',
      value: money(spend.period),
      note: spend.budget !== null && spend.remaining !== null ? `${money(spend.spent)} of ${money(spend.budget)} used` : `${money(spend.spent)} in all`,
    },
  ];
  return (
    <View style={styles.tiles}>
      {tiles.map((tile) => (
        <View key={tile.label} style={styles.tile}>
          <Text style={styles.tileLabel}>{tile.label}</Text>
          <Text style={[styles.tileValue, tile.tone ? { color: tile.tone } : null]}>{tile.value}</Text>
          <Text style={styles.fine}>{tile.note}</Text>
        </View>
      ))}
    </View>
  );
}

function Columns({ series, metric }: { series: StatsDay[]; metric: Metric }) {
  const shown = series.slice(-COLUMNS_MAX);
  const top = Math.max(...shown.map((day) => day[metric]), 0);
  const label = (value: number) => (metric === 'spend' ? (value >= 10 ? value.toFixed(0) : value.toFixed(2)) : String(value));
  // With many columns the numbers would collide, so only the tallest keeps its label.
  const crowded = shown.length > 14;
  if (top <= 0) return <Text style={styles.fine}>Nothing in this period.</Text>;
  return (
    <View style={styles.columns}>
      {shown.map((day, index) => {
        const value = day[metric];
        return (
          <View key={day.day} style={styles.column} accessibilityLabel={`${day.day}: ${label(value)}`}>
            <Text style={styles.columnValue} numberOfLines={1}>
              {value > 0 && (!crowded || value === top) ? label(value) : ' '}
            </Text>
            <View style={styles.columnTrack}>
              <View style={[styles.columnBar, { height: value > 0 ? Math.max(3, (CHART_HEIGHT * value) / top) : 1 }, value > 0 && styles.columnBarOn]} />
            </View>
            <Text style={styles.columnDay} numberOfLines={1}>
              {!crowded || index === 0 || index === shown.length - 1 || index % 5 === 0 ? dayLabel(day.day, index === 0) : ' '}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

function Funnel({ stats }: { stats: Stats }) {
  const first = stats.funnel[0]?.visitors ?? 0;
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>How far visitors get</Text>
      {first === 0 ? (
        <Since stats={stats} />
      ) : (
        <>
          {stats.funnel.map((step) => {
            const share = step.visitors / first;
            return (
              <View key={step.id} style={styles.step}>
                <View style={styles.stepHead}>
                  <Text style={styles.body}>{step.label}</Text>
                  <Text style={styles.stepCount}>
                    {step.visitors}
                    <Text style={styles.fine}>{`  ${Math.round(share * 100)}%`}</Text>
                  </Text>
                </View>
                <View style={styles.stepTrack}>
                  <View style={[styles.stepBar, { width: `${Math.max(step.visitors > 0 ? 2 : 0, Math.min(100, share * 100))}%` }]} />
                </View>
              </View>
            );
          })}
          <Text style={styles.fine}>Visitors who did each thing at least once in this period, as a share of those who opened the app.</Text>
        </>
      )}
    </View>
  );
}

function Lessons({ stats, all, onAll, onOpen }: { stats: Stats; all: boolean; onAll: () => void; onOpen: (jobId: string) => void }) {
  const rows = all ? stats.lessons : stats.lessons.slice(0, LESSONS_SHOWN);
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Lessons</Text>
      {rows.length === 0 ? <Text style={styles.fine}>No lesson was made in this period.</Text> : null}
      {rows.map((lesson) => {
        const tone = STATUS_TONE[lesson.status] ?? C.muted;
        const watched = [
          lesson.plays > 0 ? `${plural(lesson.plays, 'play')} by ${plural(lesson.viewers, 'visitor')}` : 'not played yet',
          lesson.watched_half > 0 ? `${lesson.watched_half} watched half` : '',
          lesson.watched_end > 0 ? `${lesson.watched_end} to the end` : '',
          lesson.reviews > 0 ? `${plural(lesson.reviews, 'review')}${typeof lesson.rating === 'number' ? `, rated ${lesson.rating.toFixed(1)} of 5` : ''}` : '',
        ].filter(Boolean);
        const facts = [
          when(lesson.created, stats.generated_at),
          typeof lesson.duration_seconds === 'number' && lesson.duration_seconds > 0 ? clock(lesson.duration_seconds) : '',
          lesson.language ?? '',
          lesson.made_by ? `made by ${who(lesson.made_by, stats.me)}` : '',
        ].filter(Boolean);
        return (
          <Pressable
            key={lesson.job_id}
            accessibilityRole="button"
            onPress={() => onOpen(lesson.job_id)}
            style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
            <View style={styles.flex}>
              <Text style={styles.rowTitle} numberOfLines={2}>
                {lesson.title}
              </Text>
              <Text style={styles.fine}>{facts.join(' · ')}</Text>
              {lesson.status === 'done' ? <Text style={[styles.body, lesson.plays === 0 && styles.dim]}>{watched.join(' · ')}</Text> : null}
            </View>
            <View style={[styles.statusChip, { borderColor: tone }]}>
              <Text style={[styles.statusText, { color: tone }]}>{lesson.status}</Text>
            </View>
          </Pressable>
        );
      })}
      {!all && stats.lessons.length > rows.length ? <More label={`Show all ${stats.lessons.length} lessons`} onPress={onAll} /> : null}
    </View>
  );
}

function did(visitor: StatsVisitor): string {
  const parts = [
    plural(visitor.visits, 'visit'),
    visitor.intakes > 0 ? plural(visitor.intakes, 'conversation') : '',
    visitor.lessons > 0 ? `${plural(visitor.lessons, 'video')} asked for` : '',
    visitor.plays > 0 ? plural(visitor.plays, 'play') : '',
    visitor.feedback > 0 ? `${plural(visitor.feedback, 'form')} sent` : '',
  ];
  return parts.filter(Boolean).join(' · ');
}

function Visitors({ stats, all, onAll }: { stats: Stats; all: boolean; onAll: () => void }) {
  const rows = all ? stats.visitors : stats.visitors.slice(0, VISITORS_SHOWN);
  const splits = [
    ...stats.devices.map((d) => `${named(d.name)} ${d.visitors}`),
    ...stats.countries.map((c) => `${country(c.name)} ${c.visitors}`),
  ];
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Visitors</Text>
      {rows.length === 0 ? <Since stats={stats} /> : null}
      {splits.length > 0 ? (
        <View style={styles.chips}>
          {splits.map((text) => (
            <View key={text} style={styles.tag}>
              <Text style={styles.tagText}>{text}</Text>
            </View>
          ))}
        </View>
      ) : null}
      {rows.map((visitor) => {
        const device = [named(visitor.device), visitor.os, visitor.browser, visitor.country ? country(visitor.country) : ''].filter(Boolean).join(' · ');
        const screen = visitor.last_screen ? SCREEN_NAMES[visitor.last_screen] ?? visitor.last_screen : '';
        return (
          <View key={visitor.visitor} style={styles.row}>
            <View style={styles.flex}>
              <Text style={styles.rowTitle}>
                {who(visitor.visitor, stats.me)}
                {visitor.role === 'review' ? <Text style={styles.fine}>{'  student review link'}</Text> : null}
                {visitor.new ? <Text style={styles.newText}>{'  new'}</Text> : null}
              </Text>
              <Text style={styles.fine}>{device}</Text>
              <Text style={styles.body}>{did(visitor)}</Text>
              <Text style={styles.fine}>
                Last seen {ago(Math.max(0, stats.generated_at - visitor.last_seen))}
                {screen ? ` · last on: ${screen}` : ''}
              </Text>
            </View>
          </View>
        );
      })}
      {!all && stats.visitors.length > rows.length ? <More label={`Show all ${stats.visitors.length} visitors`} onPress={onAll} /> : null}
    </View>
  );
}

function Recent({ stats, all, onAll }: { stats: Stats; all: boolean; onAll: () => void }) {
  const rows = all ? stats.recent : stats.recent.slice(0, EVENTS_SHOWN);
  if (rows.length === 0) return null;
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Latest activity</Text>
      {rows.map((event, index) => (
        <View key={`${event.at}-${index}`} style={styles.event}>
          <Text style={styles.eventTime}>{when(event.at, stats.generated_at)}</Text>
          <Text style={[styles.body, styles.flex]}>
            <Text style={styles.eventWho}>{who(event.visitor, stats.me)} </Text>
            {told(event)}
          </Text>
        </View>
      ))}
      {!all && stats.recent.length > rows.length ? <More label="Show more" onPress={onAll} /> : null}
    </View>
  );
}

function More({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => [styles.more, pressed && styles.pressed]}>
      <Text style={styles.moreText}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  page: { gap: 12 },
  flex: { flex: 1 },
  controls: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: 1, borderColor: C.line, backgroundColor: C.panel, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 9, minHeight: 40, justifyContent: 'center' },
  chipOn: { borderColor: C.teal },
  chipText: { color: C.muted, fontSize: 14 },
  chipTextOn: { color: C.teal },
  // Bounded by the card, so on a phone the chips wrap instead of running off its edge.
  metrics: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, maxWidth: '100%' },
  smallChip: { borderWidth: 1, borderColor: C.line, borderRadius: 999, paddingHorizontal: 11, paddingVertical: 6 },
  smallChipText: { color: C.muted, fontSize: 13 },
  loading: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 },
  sections: { gap: 12 },
  stale: { opacity: 0.5 },
  fine: { color: C.muted, fontSize: 13, lineHeight: 19 },
  problem: { color: C.pink, fontSize: 14, lineHeight: 20 },
  body: { color: C.ink, fontSize: 14, lineHeight: 20 },
  dim: { color: C.muted },
  banner: { borderWidth: 1, borderColor: C.gold, backgroundColor: 'rgba(255, 209, 124, 0.12)', borderRadius: 10, padding: 12 },
  bannerText: { color: C.gold, fontSize: 14, lineHeight: 20, fontWeight: '600' },
  tiles: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  tile: { flexGrow: 1, flexBasis: 150, backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 14, padding: 14, gap: 2 },
  tileLabel: { color: C.muted, fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase' },
  tileValue: { color: C.ink, fontSize: 30, fontWeight: '600', fontVariant: ['tabular-nums'] },
  card: { backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 14, padding: 14, gap: 10 },
  head: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  cardTitle: { color: C.ink, fontSize: 16, fontWeight: '600' },
  columns: { flexDirection: 'row', alignItems: 'flex-end', gap: 3 },
  column: { flex: 1, alignItems: 'center', gap: 3, minWidth: 0 },
  columnValue: { color: C.ink, fontSize: 11, fontVariant: ['tabular-nums'] },
  columnTrack: { height: CHART_HEIGHT, width: '100%', justifyContent: 'flex-end', alignItems: 'center' },
  columnBar: { width: '70%', maxWidth: 34, backgroundColor: C.line, borderTopLeftRadius: 3, borderTopRightRadius: 3 },
  columnBarOn: { backgroundColor: C.teal },
  columnDay: { color: C.muted, fontSize: 11, fontVariant: ['tabular-nums'] },
  step: { gap: 4 },
  stepHead: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 },
  stepCount: { color: C.ink, fontSize: 15, fontWeight: '600', fontVariant: ['tabular-nums'] },
  stepTrack: { height: 8, backgroundColor: C.bg, borderRadius: 4, overflow: 'hidden' },
  stepBar: { height: 8, backgroundColor: C.teal, borderRadius: 4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, borderTopWidth: 1, borderTopColor: C.line, paddingTop: 10 },
  rowTitle: { color: C.ink, fontSize: 15, fontWeight: '600' },
  newText: { color: C.gold, fontSize: 12, fontWeight: '600' },
  statusChip: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  statusText: { fontSize: 12, fontWeight: '600', letterSpacing: 0.3 },
  tag: { borderWidth: 1, borderColor: C.line, backgroundColor: C.bg, borderRadius: 999, paddingHorizontal: 11, paddingVertical: 6 },
  tagText: { color: C.muted, fontSize: 13 },
  event: { flexDirection: 'row', gap: 10, borderTopWidth: 1, borderTopColor: C.line, paddingTop: 8 },
  eventTime: { color: C.muted, fontSize: 13, lineHeight: 20, minWidth: 44, fontVariant: ['tabular-nums'] },
  eventWho: { color: C.teal, fontWeight: '600' },
  more: { alignSelf: 'flex-start', paddingVertical: 8 },
  moreText: { color: C.teal, fontSize: 14, fontWeight: '600', textDecorationLine: 'underline' },
  pressed: { opacity: 0.6 },
});
