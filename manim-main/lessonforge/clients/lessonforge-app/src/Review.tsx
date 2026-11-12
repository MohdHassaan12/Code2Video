// The student review: one lesson, opened from a link (`#review=<job id>`) that carries a
// review-only token. The student gets a few tasks, the video with its questions, a
// button for "this part is confusing", and a short form; the answers are kept on the
// server with the lesson, together with what the player saw of the viewing.
//
// That token may read this one lesson and the form, and send a review — nothing else.
// So this screen makes exactly those three calls, and shows none of the rest of the app.
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';

import { api, FeedbackForm, Job, rememberReview, reviewSent, statusOf, track } from './api';
import { clock, say } from './format';
import { LessonHandle, LessonVideo } from './LessonVideo';
import { flip, Mark, minutesLine, Problem, SheetField, SheetQuestions, SheetSend, sheetStyles, useSheet } from './Sheet';
import { C } from './theme';
import { TryIt } from './TryIt';

type Loaded = { state: 'loading' } | { state: 'ready'; job: Job; form: FeedbackForm } | { state: 'failed'; status: number | null; message: string };

const LINK_GONE = 'This review link is not valid any more.';
const NAME_MAX = 40;
// Two presses of "confusing" closer than this in the video are one confusing part.
const SAME_PART_S = 5;

function refused(status: number | null): boolean {
  return status === 401 || status === 403;
}

export function ReviewScreen({ server, jobId }: { server: string; jobId: string }) {
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });

  useEffect(() => {
    let stopped = false;
    const request = new AbortController();
    Promise.all([api.job(server, jobId, request.signal), api.feedbackForm(server, 'student', request.signal)]).then(
      ([job, form]) => {
        if (!stopped) setLoaded({ state: 'ready', job, form });
      },
      (error) => {
        if (!stopped) setLoaded({ state: 'failed', status: statusOf(error), message: say(error) });
      },
    );
    return () => {
      stopped = true;
      request.abort();
    };
  }, [server, jobId, attempt]);

  // For the owner's dashboard: a student opened this lesson to review it.
  useEffect(() => {
    track(server, 'screen', { value: 'review', job_id: jobId });
  }, [server, jobId]);

  const retry = () => {
    setLoaded({ state: 'loading' });
    setAttempt((n) => n + 1);
  };

  return (
    <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <StatusBar style="light" />
      <ScrollView style={styles.flex} contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
        {loaded.state === 'loading' ? (
          <View style={styles.notice}>
            <ActivityIndicator color={C.teal} />
            <Text style={styles.noticeText}>Opening the lesson…</Text>
          </View>
        ) : loaded.state === 'failed' ? (
          refused(loaded.status) ? (
            <Notice title={LINK_GONE} text="Ask your teacher for a new link." />
          ) : loaded.status === 404 ? (
            <Notice title="This lesson is not here any more." text="Ask your teacher for a new link." />
          ) : (
            <Notice title="The lesson did not open." text={loaded.message} onRetry={retry} />
          )
        ) : !loaded.job.video_url ? (
          <Notice title="This lesson is not ready to watch yet." text="Try again in a few minutes." onRetry={retry} />
        ) : (
          <Review key={loaded.job.job_id} server={server} job={loaded.job} form={loaded.form} />
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function Notice({ title, text, onRetry }: { title: string; text: string; onRetry?: () => void }) {
  return (
    <View style={styles.notice}>
      <Text style={styles.noticeTitle}>{title}</Text>
      <Text style={styles.noticeText}>{text}</Text>
      {onRetry ? (
        <Pressable accessibilityRole="button" onPress={onRetry} style={({ pressed }) => [sheetStyles.secondary, pressed && sheetStyles.pressed]}>
          <Text style={sheetStyles.secondaryText}>Try again</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function Review({ server, job, form }: { server: string; job: Job; form: FeedbackForm }) {
  const lesson = useRef<LessonHandle>(null);
  const sheet = useSheet(form);
  const [ticked, setTicked] = useState<string[]>([]);
  const [name, setName] = useState('');
  // Video times marked confusing, in the order pressed; `marked` is what the last press did.
  const [marks, setMarks] = useState<number[]>([]);
  const [marked, setMarked] = useState<{ t: number; again: boolean } | null>(null);
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  // 'before': this browser sent a review of this lesson earlier. 'now': it just did.
  const [sent, setSent] = useState<'before' | 'now' | null>(() => (reviewSent(job.job_id) ? 'before' : null));
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const about = minutesLine(form);

  const mark = () => {
    const t = Math.round((lesson.current?.time() ?? 0) * 10) / 10;
    const near = marks.find((one) => Math.abs(one - t) < SAME_PART_S);
    if (near !== undefined) {
      setMarked({ t: near, again: true });
      return;
    }
    setMarks([...marks, t]);
    setMarked({ t, again: false });
  };
  const undo = () => {
    setMarks(marks.slice(0, -1));
    setMarked(null);
  };

  const send = async () => {
    if (sending || !sheet.complete()) return;
    const viewing = lesson.current?.viewing() ?? {
      watch_mode: 'full',
      seconds_watched: 0,
      completed: false,
      quiz: { asked: 0, answered: 0, correct: 0, skipped: 0, wrong_ids: [] },
    };
    setSending(true);
    setProblem(null);
    try {
      await api.sendFeedback(server, job.job_id, {
        reviewer: name.trim().slice(0, NAME_MAX) || undefined,
        answers: sheet.given(),
        auto: { ...viewing, confused_at: [...marks].sort((a, b) => a - b) },
      });
      if (!alive.current) return;
      rememberReview(job.job_id);
      setSent('now');
    } catch (error) {
      if (!alive.current) return;
      const status = statusOf(error);
      // The answers stay where they are: only the message changes.
      setProblem(
        refused(status)
          ? { final: true, message: LINK_GONE }
          : status === 400
            ? { final: false, message: say(error).replace(/^\d+:\s*/, '') }
            : { final: false, message: 'Your review was not sent. Check the internet and try again — your answers are still here.' },
      );
    } finally {
      if (alive.current) setSending(false);
    }
  };

  const another = () => {
    sheet.clear();
    setMarks([]);
    setMarked(null);
    setProblem(null);
    setSent(null);
  };

  return (
    <>
      <View style={styles.header}>
        <Text style={styles.eyebrow}>LESSON REVIEW</Text>
        <Text style={styles.title}>{job.title || 'Your lesson'}</Text>
        <Text style={styles.sub}>
          {form.title || 'Help us make this lesson better'}
          {about ? ` · ${about}` : ''}
        </Text>
      </View>

      {sent ? (
        <View style={[sheetStyles.card, sheetStyles.thanks]} aria-live="polite">
          <Text style={sheetStyles.thanksTitle}>
            {sent === 'now' ? '✓ Thank you! Your review was sent.' : 'You already sent your review — thank you.'}
          </Text>
          {sent === 'now' ? <Text style={sheetStyles.body}>It helps us make the next lesson better. You can close this page.</Text> : null}
          <Pressable accessibilityRole="button" onPress={another} style={({ pressed }) => [sheetStyles.link, pressed && sheetStyles.pressed]}>
            <Text style={sheetStyles.linkText}>Send another</Text>
          </Pressable>
        </View>
      ) : form.tasks.length > 0 ? (
        <View style={sheetStyles.card}>
          <Text style={sheetStyles.cardTitle}>Your tasks</Text>
          {form.tasks.map((task, index) => {
            const done = ticked.includes(task.id);
            return (
              <Pressable
                key={task.id}
                role="checkbox"
                aria-checked={done}
                onPress={() => setTicked(flip(ticked, task.id, true))}
                style={({ pressed }) => [styles.task, pressed && sheetStyles.pressed]}>
                <Mark on={done} />
                <Text style={[styles.taskText, done && styles.taskDone]}>
                  {index + 1}. {task.text}
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}

      <LessonVideo ref={lesson} job={job} server={server} modes={false}>
        {sent ? null : (
          <View style={styles.confusing}>
            <Pressable accessibilityRole="button" onPress={mark} style={({ pressed }) => [styles.confusingButton, pressed && sheetStyles.pressed]}>
              <Text style={styles.confusingText}>This part is confusing</Text>
            </Pressable>
            <View style={styles.confusingLine} aria-live="polite">
              <Text style={sheetStyles.body}>
                {marked ? `${marked.again ? 'Already marked' : 'Marked'} ${clock(marked.t)} · ` : ''}
                {marks.length === 0 ? 'Press it whenever you feel lost.' : `${marks.length} part${marks.length === 1 ? '' : 's'} marked`}
              </Text>
              {marks.length > 0 ? (
                <Pressable accessibilityRole="button" onPress={undo} style={({ pressed }) => [sheetStyles.link, pressed && sheetStyles.pressed]}>
                  <Text style={sheetStyles.linkText}>Undo last</Text>
                </Pressable>
              ) : null}
            </View>
          </View>
        )}
      </LessonVideo>

      {/* After the video and before the form: the task is part of the lesson, not of the review. */}
      {job.try_it ? <TryIt server={server} job={job} /> : null}

      {sent ? null : <SheetQuestions form={form} sheet={sheet} chapters={job.chapters} />}
      {sent ? null : (
        <View style={sheetStyles.section}>
          <SheetField label="Your name or nickname — optional" value={name} onChangeText={setName} maxLength={NAME_MAX} />
          <SheetSend form={form} sheet={sheet} sending={sending} problem={problem} label="Send my review" onSend={send} />
        </View>
      )}
    </>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  flex: { flex: 1 },
  page: { width: '100%', maxWidth: 760, alignSelf: 'center', paddingHorizontal: 16, paddingTop: Platform.OS === 'web' ? 20 : 52, paddingBottom: 40, gap: 12 },
  header: { gap: 4 },
  eyebrow: { color: C.teal, fontSize: 12, letterSpacing: 1.5, fontWeight: '600' },
  title: { color: C.ink, fontSize: 24, lineHeight: 30, fontWeight: '600' },
  sub: { color: C.muted, fontSize: 15, lineHeight: 21 },
  notice: { alignItems: 'center', gap: 12, paddingVertical: 60 },
  noticeTitle: { color: C.ink, fontSize: 20, lineHeight: 27, fontWeight: '600', textAlign: 'center' },
  noticeText: { color: C.muted, fontSize: 15, lineHeight: 22, textAlign: 'center' },
  task: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, minHeight: 44, paddingVertical: 6 },
  taskText: { flex: 1, color: C.ink, fontSize: 16, lineHeight: 23 },
  taskDone: { color: C.muted },
  confusing: { gap: 6 },
  confusingButton: { minHeight: 56, justifyContent: 'center', alignItems: 'center', borderWidth: 2, borderColor: C.gold, backgroundColor: 'rgba(255, 209, 124, 0.12)', borderRadius: 14, paddingHorizontal: 16, paddingVertical: 12 },
  confusingText: { color: C.gold, fontSize: 18, fontWeight: '700' },
  confusingLine: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', columnGap: 14, rowGap: 4, minHeight: 24 },
});
