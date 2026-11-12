// "Try it yourself": the task a learner does by hand after the video, and, for the owner,
// what the lesson stands on.
//
//   TryIt         what you need → guess first → the steps → what did you see → the "why"
//                 question → check. The answer is kept on the server with the lesson, and
//                 only then is the expected result shown.
//   TeachingCard  the lesson's teaching card as its owner reads it: the big idea, why it is
//                 true, the picture, where learners go wrong, and the sources by title.
//
// The order is the point. A demonstration watched without a guess teaches little, and what
// people say they saw is often not what happened, so the steps stay hidden until a guess is
// in, and the true outcome is shown after the learner has said what they saw.
import { useEffect, useRef, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { api, CardView, Job, statusOf, TryItStored, TryItSummary } from './api';
import { ago, say } from './format';
import { C } from './theme';

const ANSWER_MAX = 400;
const KIND_LINE: Record<string, string> = {
  hands: 'With things from home',
  paper: 'With paper and pencil',
  simulation: 'On a screen',
};

// `owner`: the person who made the lesson (may read what learners wrote). A student's
// review link may only send an answer.
export function TryIt({ server, job, owner = false }: { server: string; job: Job; owner?: boolean }) {
  const task = job.try_it;
  const [guess, setGuess] = useState('');
  const [locked, setLocked] = useState(false);
  const [saw, setSaw] = useState('');
  const [answer, setAnswer] = useState('');
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [reveal, setReveal] = useState<TryItStored | null>(null);
  const [classOpen, setClassOpen] = useState(false);
  // What learners wrote, with the clock when it arrived (unix seconds) so ages are not read in render.
  const [others, setOthers] = useState<{ list: TryItSummary; at: number } | null>(null);
  const [othersOpen, setOthersOpen] = useState(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  if (!task) return null;
  const count = reveal?.count ?? job.try_it_answers ?? 0;
  const ready = saw.trim().length > 0 || answer.trim().length > 0;

  const check = async () => {
    if (sending || !ready) return;
    setSending(true);
    setProblem(null);
    try {
      const stored = await api.sendTryIt(server, job.job_id, {
        prediction: guess.trim() || undefined,
        observation: saw.trim() || undefined,
        answer: answer.trim() || undefined,
      });
      if (alive.current) setReveal(stored);
    } catch (error) {
      if (!alive.current) return;
      const status = statusOf(error);
      setProblem(
        status === 401 || status === 403
          ? 'This link cannot send answers.'
          : status === 400 || status === 404
            ? say(error).replace(/^\d+:\s*/, '')
            : 'Your answer was not sent. Check the internet and try again: what you wrote is still here.',
      );
    } finally {
      if (alive.current) setSending(false);
    }
  };

  const again = () => {
    setGuess('');
    setLocked(false);
    setSaw('');
    setAnswer('');
    setReveal(null);
    setProblem(null);
  };

  const showOthers = async () => {
    if (othersOpen) {
      setOthersOpen(false);
      return;
    }
    setOthersOpen(true);
    try {
      const summary = await api.tryItAnswers(server, job.job_id);
      if (alive.current) setOthers({ list: summary, at: Date.now() / 1000 });
    } catch {
      if (alive.current) setOthers(null);
    }
  };

  return (
    <View style={styles.card}>
      <Text style={styles.eyebrow}>TRY IT YOURSELF · {KIND_LINE[task.kind] ?? KIND_LINE.hands}</Text>
      {task.title ? <Text style={styles.title}>{task.title}</Text> : null}

      {task.materials.length > 0 ? (
        <View style={styles.block}>
          <Text style={styles.label}>You need</Text>
          {task.materials.map((item) => (
            <Text key={item} style={styles.body}>
              • {item}
            </Text>
          ))}
          {task.stands_for ? <Text style={styles.fine}>{task.stands_for}</Text> : null}
        </View>
      ) : null}

      <View style={styles.block}>
        <Text style={styles.label}>1 · Guess first</Text>
        <Text style={styles.body}>{task.predict}</Text>
        {locked ? (
          <Text style={styles.mine}>Your guess: {guess.trim() || 'not sure yet'}</Text>
        ) : (
          <>
            <TextInput
              value={guess}
              onChangeText={setGuess}
              maxLength={ANSWER_MAX}
              placeholder="My guess is…"
              placeholderTextColor={C.muted}
              style={styles.input}
            />
            <View style={styles.row}>
              <Pressable
                disabled={!guess.trim()}
                onPress={() => setLocked(true)}
                style={({ pressed }) => [styles.primary, styles.grow, (pressed || !guess.trim()) && styles.dim]}>
                <Text style={styles.primaryText}>Lock in my guess</Text>
              </Pressable>
              <Pressable onPress={() => setLocked(true)} style={({ pressed }) => [styles.ghost, pressed && styles.dim]}>
                <Text style={styles.ghostText}>I can’t guess</Text>
              </Pressable>
            </View>
            <Text style={styles.fine}>The steps appear once your guess is in. Guessing first is what makes the task teach.</Text>
          </>
        )}
      </View>

      {locked ? (
        <>
          <View style={styles.block}>
            <Text style={styles.label}>2 · Do it</Text>
            {task.steps.map((step, i) => (
              <Text key={`${i}-${step}`} style={styles.body}>
                <Text style={styles.number}>{i + 1}. </Text>
                {step}
              </Text>
            ))}
          </View>

          <View style={styles.block}>
            <Text style={styles.label}>3 · What did you see?</Text>
            <TextInput
              value={saw}
              onChangeText={setSaw}
              editable={!reveal}
              maxLength={ANSWER_MAX}
              multiline
              placeholder="Say what happened, in your own words"
              placeholderTextColor={C.muted}
              style={[styles.input, styles.tall]}
            />
          </View>

          <View style={styles.block}>
            <Text style={styles.label}>4 · Now answer</Text>
            <Text style={styles.body}>{task.question}</Text>
            <TextInput
              value={answer}
              onChangeText={setAnswer}
              editable={!reveal}
              maxLength={ANSWER_MAX}
              multiline
              placeholder="Because…"
              placeholderTextColor={C.muted}
              style={[styles.input, styles.tall]}
            />
            {task.write ? <Text style={styles.fine}>Then write or say: {task.write}</Text> : null}
          </View>

          {reveal ? (
            <View style={[styles.block, styles.reveal]} aria-live="polite">
              <Text style={styles.revealTitle}>✓ Saved with this lesson</Text>
              {reveal.observe ? (
                <>
                  <Text style={styles.label}>What should happen</Text>
                  <Text style={styles.body}>{reveal.observe}</Text>
                </>
              ) : null}
              <Text style={styles.label}>The answer</Text>
              <Text style={styles.body}>{reveal.expected}</Text>
              <Pressable onPress={again} style={({ pressed }) => [styles.link, pressed && styles.dim]}>
                <Text style={styles.linkText}>Try it again</Text>
              </Pressable>
            </View>
          ) : (
            <>
              <Pressable disabled={sending || !ready} onPress={check} style={({ pressed }) => [styles.primary, (pressed || sending || !ready) && styles.dim]}>
                <Text style={styles.primaryText}>{sending ? 'Saving…' : 'Check my answer'}</Text>
              </Pressable>
              {problem ? <Text style={styles.problem}>{problem}</Text> : null}
            </>
          )}
        </>
      ) : null}

      {task.in_class ? (
        <View style={styles.block}>
          <Pressable onPress={() => setClassOpen((open) => !open)} style={({ pressed }) => [styles.link, pressed && styles.dim]}>
            <Text style={styles.linkText}>{classOpen ? 'Hide the class version' : 'Doing this with a whole class?'}</Text>
          </Pressable>
          {classOpen ? <Text style={styles.body}>{task.in_class}</Text> : null}
        </View>
      ) : null}

      {owner ? (
        <View style={styles.block}>
          <View style={styles.row}>
            <Text style={[styles.fine, styles.grow]}>
              {count === 0 ? 'No answers yet.' : `${count} answer${count === 1 ? '' : 's'} so far.`}
            </Text>
            {count > 0 ? (
              <Pressable onPress={showOthers} style={({ pressed }) => [styles.link, pressed && styles.dim]}>
                <Text style={styles.linkText}>{othersOpen ? 'Hide them' : 'Read them'}</Text>
              </Pressable>
            ) : null}
          </View>
          {othersOpen
            ? (others?.list.answers ?? []).slice(0, 12).map((one) => (
                <View key={one.id} style={styles.other}>
                  <Text style={styles.fine}>
                    {one.reviewer || 'A learner'}
                    {others && typeof one.at === 'number' ? ` · ${ago(others.at - one.at)}` : ''}
                  </Text>
                  {one.prediction ? <Text style={styles.body}>Guessed: {one.prediction}</Text> : null}
                  {one.observation ? <Text style={styles.body}>Saw: {one.observation}</Text> : null}
                  {one.answer ? <Text style={styles.body}>Answered: {one.answer}</Text> : null}
                </View>
              ))
            : null}
          {othersOpen && !others ? <Text style={styles.fine}>Could not load the answers.</Text> : null}
        </View>
      ) : null}
    </View>
  );
}

const SOURCE_KIND: Record<string, string> = {
  textbook: 'textbook',
  lecture: 'lecture',
  lesson_plan: 'lesson plan',
  misconceptions: 'learner mistakes',
  web: 'web page',
  given: 'given by you',
};

export function TeachingCard({ card }: { card: CardView }) {
  const rows: [label: string, text: string][] = [
    ['The big idea', card.big_idea],
    ['Why it matters', card.why_it_matters],
    ['Why it is true', card.the_why],
    ['The one picture', card.picture],
  ];
  return (
    <View style={styles.card}>
      <Text style={styles.eyebrow}>WHAT THIS LESSON STANDS ON</Text>
      {rows
        .filter(([, text]) => text)
        .map(([label, text]) => (
          <View key={label} style={styles.block}>
            <Text style={styles.label}>{label}</Text>
            <Text style={styles.body}>{text}</Text>
            {label === 'The one picture' && card.picture_standard ? (
              <Text style={styles.fine}>Drawn the way it is in class: {card.picture_standard}</Text>
            ) : null}
          </View>
        ))}
      {card.opening_question.question ? (
        <View style={styles.block}>
          <Text style={styles.label}>The question it opens with</Text>
          <Text style={styles.body}>{card.opening_question.question}</Text>
          {card.opening_question.answer ? <Text style={styles.fine}>Answered by the end: {card.opening_question.answer}</Text> : null}
        </View>
      ) : null}
      {card.mistakes.length > 0 ? (
        <View style={styles.block}>
          <Text style={styles.label}>Where learners go wrong</Text>
          {card.mistakes.map((one) => (
            <View key={one.mistake}>
              <Text style={styles.body}>• {one.mistake}</Text>
              {one.why_it_fails ? <Text style={styles.fine}>{one.why_it_fails}</Text> : null}
            </View>
          ))}
        </View>
      ) : null}
      {card.needs_first.length > 0 ? (
        <View style={styles.block}>
          <Text style={styles.label}>Needs first</Text>
          <Text style={styles.body}>{card.needs_first.join(' · ')}</Text>
        </View>
      ) : null}
      {card.sources.length > 0 ? (
        <View style={styles.block}>
          <Text style={styles.label}>Sources</Text>
          {card.sources.map((source) =>
            source.url ? (
              <Pressable key={source.id + source.title} onPress={() => Linking.openURL(source.url).catch(() => {})} style={({ pressed }) => pressed && styles.dim}>
                <Text style={styles.body}>
                  <Text style={styles.sourceLink}>{source.title}</Text>
                  <Text style={styles.fine}> · {SOURCE_KIND[source.kind] ?? source.kind}</Text>
                </Text>
              </Pressable>
            ) : (
              <Text key={source.id + source.title} style={styles.body}>
                {source.title}
                <Text style={styles.fine}> · {SOURCE_KIND[source.kind] ?? source.kind}</Text>
              </Text>
            ),
          )}
          <Text style={styles.fine}>Read and said in the lesson’s own words; nothing is copied from them.</Text>
        </View>
      ) : (
        <Text style={styles.fine}>No sources were found for this lesson, so its plan comes from the model alone.</Text>
      )}
      {card.problems > 0 ? (
        <Text style={styles.problem}>
          {card.problems} line{card.problems === 1 ? '' : 's'} of this plan could not be checked against the sources.
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: C.panel, borderWidth: 1, borderColor: C.teal, borderRadius: 14, padding: 14, gap: 12 },
  eyebrow: { color: C.teal, fontSize: 12, letterSpacing: 1.2, fontWeight: '700' },
  title: { color: C.ink, fontSize: 19, lineHeight: 26, fontWeight: '600' },
  block: { gap: 6 },
  label: { color: C.muted, fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase' },
  body: { color: C.ink, fontSize: 16, lineHeight: 23 },
  number: { color: C.teal, fontWeight: '700' },
  fine: { color: C.muted, fontSize: 13, lineHeight: 19 },
  mine: { color: C.gold, fontSize: 15, lineHeight: 22 },
  input: { color: C.ink, backgroundColor: C.bg, borderWidth: 1, borderColor: C.line, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16 },
  tall: { minHeight: 76, textAlignVertical: 'top' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  grow: { flex: 1 },
  primary: { backgroundColor: C.teal, borderRadius: 12, paddingVertical: 14, paddingHorizontal: 16, alignItems: 'center' },
  primaryText: { color: C.bg, fontSize: 16, fontWeight: '600' },
  ghost: { paddingHorizontal: 12, paddingVertical: 12 },
  ghostText: { color: C.muted, fontSize: 14 },
  dim: { opacity: 0.5 },
  reveal: { borderWidth: 1, borderColor: C.teal, borderRadius: 12, padding: 12 },
  revealTitle: { color: C.teal, fontSize: 16, fontWeight: '600' },
  link: { alignSelf: 'flex-start', paddingVertical: 6 },
  linkText: { color: C.teal, fontSize: 15, fontWeight: '600', textDecorationLine: 'underline' },
  sourceLink: { color: C.teal, textDecorationLine: 'underline' },
  problem: { color: C.pink, fontSize: 14, lineHeight: 20 },
  other: { borderLeftWidth: 2, borderLeftColor: C.line, paddingLeft: 10, gap: 2 },
});
