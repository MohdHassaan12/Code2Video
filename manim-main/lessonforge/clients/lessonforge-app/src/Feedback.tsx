// Tester feedback: "Tell us how it went", for the people who MAKE lessons (teachers,
// parents, colleagues) rather than the students who watch one. The sheet comes from the
// server and is drawn with the same question components as the student review
// (Sheet.tsx). Owner mode only: a student's review link is not allowed these calls.
//
//   FeedbackEntry    the way in, on the start screen, with how many forms have come in
//   TesterFeedback   the screen itself
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { api, FeedbackForm, statusOf } from './api';
import { say } from './format';
import { Answers, minutesLine, Problem, SheetField, SheetQuestions, SheetSend, sheetStyles, useSheet } from './Sheet';
import { C } from './theme';

const NAME_MAX = 40;
const CONTACT_MAX = 80;
// The question a lesson's title answers, when the form is opened from that lesson.
const TOPICS = 'topics';

export function FeedbackEntry({ server, onOpen }: { server: string; onOpen: () => void }) {
  const [count, setCount] = useState<number | null>(null);
  // Briefly delayed, so typing a server URL does not send a request per keystroke.
  useEffect(() => {
    let stopped = false;
    const request = new AbortController();
    const timer = setTimeout(() => {
      api.testerCount(server, request.signal).then(
        (found) => {
          if (!stopped) setCount(found);
        },
        () => {
          if (!stopped) setCount(null);
        },
      );
    }, 300);
    return () => {
      stopped = true;
      clearTimeout(timer);
      request.abort();
    };
  }, [server]);

  return (
    <View style={styles.entry}>
      <View style={styles.entryRow}>
        <Text style={styles.entryText}>Made a video with this? Tell us how it went.</Text>
        <Pressable accessibilityRole="button" onPress={onOpen} style={({ pressed }) => [styles.entryButton, pressed && sheetStyles.pressed]}>
          <Text style={styles.entryButtonText}>Feedback</Text>
        </Pressable>
      </View>
      {count !== null ? (
        <Text style={styles.fine}>
          {count} tester form{count === 1 ? '' : 's'} received
        </Text>
      ) : null}
    </View>
  );
}

type Lesson = { id: string; title: string };
type Loaded = { state: 'loading' } | { state: 'ready'; form: FeedbackForm } | { state: 'failed'; message: string };

// `lesson`: the one the tester had open, if any. `onMakeAnother`: back to the start.
export function TesterFeedback({ server, lesson, onMakeAnother }: { server: string; lesson: Lesson | null; onMakeAnother: () => void }) {
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });

  useEffect(() => {
    let stopped = false;
    const request = new AbortController();
    api.feedbackForm(server, 'tester', request.signal).then(
      (form) => {
        if (!stopped) setLoaded({ state: 'ready', form });
      },
      (error) => {
        if (!stopped) setLoaded({ state: 'failed', message: say(error) });
      },
    );
    return () => {
      stopped = true;
      request.abort();
    };
  }, [server, attempt]);

  if (loaded.state === 'loading') {
    return (
      <View style={styles.waiting}>
        <ActivityIndicator color={C.teal} />
        <Text style={styles.fine}>Fetching the questions…</Text>
      </View>
    );
  }
  if (loaded.state === 'failed') {
    return (
      <View style={sheetStyles.card}>
        <Text style={sheetStyles.cardTitle}>The feedback form did not open.</Text>
        <Text style={sheetStyles.body}>{loaded.message}</Text>
        <Pressable
          accessibilityRole="button"
          onPress={() => {
            setLoaded({ state: 'loading' });
            setAttempt((n) => n + 1);
          }}
          style={({ pressed }) => [sheetStyles.secondary, pressed && sheetStyles.pressed]}>
          <Text style={sheetStyles.secondaryText}>Try again</Text>
        </Pressable>
      </View>
    );
  }
  return <TesterSheet server={server} form={loaded.form} lesson={lesson} onMakeAnother={onMakeAnother} />;
}

function TesterSheet({ server, form, lesson, onMakeAnother }: { server: string; form: FeedbackForm; lesson: Lesson | null; onMakeAnother: () => void }) {
  // Opened from a lesson: its title is a first answer to "what did you make?", to edit.
  const [start] = useState((): Answers =>
    lesson?.title && form.questions.some((question) => question.id === TOPICS && question.kind === 'text') ? { [TOPICS]: lesson.title } : {},
  );
  const sheet = useSheet(form, start);
  const [name, setName] = useState('');
  const [contact, setContact] = useState('');
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [sent, setSent] = useState(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const about = minutesLine(form);

  const send = async () => {
    if (sending || !sheet.complete()) return;
    setSending(true);
    setProblem(null);
    try {
      await api.sendTesterFeedback(server, {
        kind: 'tester',
        job_id: lesson?.id,
        reviewer: name.trim().slice(0, NAME_MAX) || undefined,
        contact: contact.trim().slice(0, CONTACT_MAX) || undefined,
        answers: sheet.given(),
      });
      if (alive.current) setSent(true);
    } catch (error) {
      if (!alive.current) return;
      const status = statusOf(error);
      // The answers stay where they are: only the message changes.
      setProblem({
        final: false,
        message:
          status === 400
            ? say(error).replace(/^\d+:\s*/, '')
            : status === 0
              ? 'Your feedback was not sent. Check the connection and try again — your answers are still here.'
              : `Your feedback was not sent (${say(error)}). Your answers are still here.`,
      });
    } finally {
      if (alive.current) setSending(false);
    }
  };

  if (sent) {
    return (
      <View style={[sheetStyles.card, sheetStyles.thanks]} aria-live="polite">
        <Text style={sheetStyles.thanksTitle}>✓ Thank you — your feedback was sent.</Text>
        <Text style={sheetStyles.body}>It goes straight to the people building this.</Text>
        <Pressable accessibilityRole="button" onPress={onMakeAnother} style={({ pressed }) => [sheetStyles.secondary, pressed && sheetStyles.pressed]}>
          <Text style={sheetStyles.secondaryText}>Make another video</Text>
        </Pressable>
      </View>
    );
  }
  return (
    <>
      <View style={styles.head}>
        <Text style={styles.title}>{form.title || 'Tell us how it went'}</Text>
        {about ? <Text style={styles.fine}>{about}</Text> : null}
      </View>
      {form.tasks.length > 0 ? (
        <View style={sheetStyles.card}>
          <Text style={sheetStyles.cardTitle}>What to look for</Text>
          {form.tasks.map((task) => (
            <Text key={task.id} style={sheetStyles.body}>
              • {task.text}
            </Text>
          ))}
        </View>
      ) : null}
      <SheetQuestions form={form} sheet={sheet} />
      <View style={sheetStyles.section}>
        <SheetField label="Your name — optional" value={name} onChangeText={setName} maxLength={NAME_MAX} />
        <SheetField
          label="Phone or email — only if you are happy for us to follow up"
          value={contact}
          onChangeText={setContact}
          maxLength={CONTACT_MAX}
        />
        <SheetSend form={form} sheet={sheet} sending={sending} problem={problem} label="Send feedback" onSend={send} />
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  entry: { gap: 4, marginTop: 8 },
  entryRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  entryText: { flex: 1, color: C.muted, fontSize: 14, lineHeight: 20 },
  entryButton: { borderWidth: 1, borderColor: C.teal, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 10 },
  entryButtonText: { color: C.teal, fontSize: 15, fontWeight: '600' },
  fine: { color: C.muted, fontSize: 13, lineHeight: 19 },
  waiting: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 24 },
  head: { gap: 2, marginTop: 6 },
  title: { color: C.ink, fontSize: 22, lineHeight: 28, fontWeight: '600' },
});
