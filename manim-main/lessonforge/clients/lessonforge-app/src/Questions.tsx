// Questions inside the video. The lesson stops at each interaction point, the question
// is drawn over the picture, and the learner answers (or skips) before it goes on.
//
//   useQuestions      loads the job's interactions and decides when to stop the player
//   QuestionOverlay   the card over the video; render it inside the video's own box
//   QuestionBar       the running score and the "Pause for questions" switch
//
// Without an interactions file — none was written, or it could not be read — all three
// do nothing and the player behaves as it always has.
import { RefObject, useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { api, Interaction, InteractionOption, QuizTally, Range } from './api';
import type { PlayerHandle } from './Player';
import { C } from './theme';

// correct / wrong: an option was tapped. retried: wrong first, right on the second try after
// the nudge. shown: the answer was revealed. skipped: neither.
type Outcome = 'correct' | 'retried' | 'wrong' | 'shown' | 'skipped';
// "How sure are you?" Asked with the options; optional. Sure and wrong is a misconception, not a slip.
export type Sure = 'guess' | 'fairly' | 'sure';
const SURE: { id: Sure; label: string }[] = [
  { id: 'guess', label: 'Guessing' },
  { id: 'fairly', label: 'Fairly sure' },
  { id: 'sure', label: 'Sure' },
];
type Asking = { question: Interaction; turn: number };

// Time may slip back this much (a pause settling on a frame) without counting as a seek.
const REWIND_S = 0.3;
// No two reports of plain playing are this far apart, even at double speed in a
// throttled tab; a longer step means the reports stopped for a while (Android pauses
// JS in fullscreen), and what lies inside it is treated as seeked over.
const LEAP_S = 3;
// Seeking back to here is watching again from the start: the score starts again too.
const START_S = 1;
const NARROW = 560;

function canScore(question: Interaction): boolean {
  return question.scored && question.options.some((option) => option.correct);
}

function count(n: number, of: number, what: string): string {
  return `${n} of ${of} ${what}`;
}

export type Questions = ReturnType<typeof useQuestions>;

// `ranges` / `keeps`: the watch mode in force (Cuts.tsx). A question is asked only if
// the selected cut keeps its moment; `ranges` is null while the whole video plays.
export function useQuestions(
  server: string,
  url: string | null | undefined,
  player: RefObject<PlayerHandle | null>,
  ranges: Range[] | null = null,
  keeps: (t: number) => boolean = () => true,
) {
  const [all, setAll] = useState<Interaction[]>([]);
  const [asking, setAsking] = useState<Asking | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, Outcome>>({});
  const [enabled, setEnabled] = useState(true);
  // What the player callbacks decide from. They run between renders, several a second,
  // so this is kept beside the state above rather than read from a render's closure.
  const live = useRef({
    list: [] as Interaction[],
    enabled: true,
    at: 0,
    asked: new Set<string>(),
    open: null as Interaction | null,
    settled: false,
    turn: 0,
    // Every question shown in this sitting with how it last went (null: left unanswered).
    // Unlike the score, it is not wiped when the video is watched again from the start.
    seen: new Map<string, Outcome | null>(),
    sure: new Map<string, Sure>(),
    // The known mistake behind the wrong option chosen first, when the lesson named one.
    mistake: new Map<string, string>(),
  });

  useEffect(() => {
    if (!url) return;
    let stopped = false;
    const request = new AbortController();
    api.interactions(server, url, request.signal).then(
      (found) => {
        if (stopped) return;
        live.current.list = found;
        setAll(found);
      },
      () => {
        // No questions: the video plays straight through, and nothing is said about it.
      },
    );
    return () => {
      stopped = true;
      request.abort();
    };
  }, [server, url]);

  // Returns true while a question is holding the video.
  const onTime = useCallback(
    (now: number, seeked: boolean): boolean => {
      const state = live.current;
      const before = state.at;
      state.at = now;
      if (state.open) {
        // A question is up: the video waits for it, whatever set it going again.
        player.current?.pause();
        return true;
      }
      if (seeked || now < before - REWIND_S || now - before > LEAP_S) {
        if (now >= before) {
          // Seeked over by hand: those questions are not asked.
          for (const question of state.list) if (question.t >= before && question.t <= now) state.asked.add(question.id);
        } else if (now < START_S) {
          state.asked.clear();
          setOutcomes((old) => (Object.keys(old).length > 0 ? {} : old));
        } else {
          // Seeking back puts the questions ahead of the new position in play again.
          for (const question of state.list) if (question.t > now) state.asked.delete(question.id);
        }
        return false;
      }
      if (!state.enabled) return false;
      const next = state.list.find(
        (question) => question.t >= before && question.t <= now && !state.asked.has(question.id) && keeps(question.t),
      );
      if (!next) return false;
      state.asked.add(next.id);
      if (!state.seen.has(next.id)) state.seen.set(next.id, null);
      state.open = next;
      state.settled = false;
      state.turn += 1;
      player.current?.pause();
      player.current?.leaveFullscreen();
      setAsking({ question: next, turn: state.turn });
      return true;
    },
    [player, keeps],
  );

  const record = useCallback((outcome: Outcome) => {
    const open = live.current.open;
    if (!open) return;
    live.current.settled = true;
    // The first answer stands: a question asked again after watching that part again is practice.
    const before = live.current.seen.get(open.id);
    if (!before || before === 'skipped' || before === 'shown') live.current.seen.set(open.id, outcome);
    setOutcomes((old) => ({ ...old, [open.id]: outcome }));
  }, []);

  // How the questions with a right answer went, for a review. Predict and recall
  // questions have none, so they are left out rather than counted as not correct.
  const tally = useCallback((): QuizTally => {
    const state = live.current;
    const went = state.list.filter((question) => canScore(question) && state.seen.has(question.id)).map((question) => ({ id: question.id, as: state.seen.get(question.id) }));
    const wrong = went.filter((one) => one.as === 'wrong' || one.as === 'retried');
    const sureWrong = wrong.filter((one) => state.sure.get(one.id) === 'sure');
    return {
      asked: went.length,
      answered: went.filter((one) => one.as === 'correct').length + wrong.length,
      correct: went.filter((one) => one.as === 'correct').length,
      skipped: went.filter((one) => one.as === 'skipped').length,
      wrong_ids: wrong.map((one) => one.id),
      retried_right: went.filter((one) => one.as === 'retried').length,
      sure_wrong_ids: sureWrong.map((one) => one.id),
      misconceptions: [...new Set(wrong.map((one) => state.mistake.get(one.id)).filter((m): m is string => !!m))],
    };
  }, []);

  // Take the question down. `resume`: carry on from where the lesson's own pause ends.
  const close = useCallback(
    (resume: boolean) => {
      const state = live.current;
      const open = state.open;
      if (!open) return;
      state.open = null;
      setAsking(null);
      if (!resume) return;
      if (open.resume_at !== null && open.resume_at > state.at) player.current?.seek(open.resume_at);
      else player.current?.play();
    },
    [player],
  );

  // `attempt` 1 or 2; `last`: no second try follows (a wrong first try with a retry to come records nothing yet).
  const answer = useCallback(
    (option: InteractionOption, attempt: 1 | 2, sure: Sure | null, last: boolean) => {
      const state = live.current;
      const open = state.open;
      if (!open) return;
      if (attempt === 1) {
        if (sure && !state.seen.get(open.id)) state.sure.set(open.id, sure);
        if (!option.correct && option.misconception && !state.mistake.has(open.id)) state.mistake.set(open.id, option.misconception);
      }
      if (option.correct) record(attempt === 1 ? 'correct' : 'retried');
      else if (last) record('wrong');
    },
    [record],
  );
  // After a wrong answer: back to where the idea was shown. The question comes up again when it is reached.
  const rewatch = useCallback(() => {
    const back = live.current.open?.on_wrong;
    if (!back) return;
    close(false);
    player.current?.seek(back.seek_to);
    player.current?.play();
  }, [close, player]);
  const reveal = useCallback(() => record('shown'), [record]);
  const proceed = useCallback(() => {
    if (!live.current.settled) record('shown');
    close(true);
  }, [close, record]);
  const skip = useCallback(() => {
    record('skipped');
    close(true);
  }, [close, record]);

  const toggle = useCallback(() => {
    const state = live.current;
    state.enabled = !state.enabled;
    setEnabled(state.enabled);
    // Switched off with a question on screen: it goes away with the rest.
    if (!state.enabled && state.open) {
      if (!state.settled) record('skipped');
      close(true);
    }
  }, [close, record]);

  // A chapter chip: the question on screen, if any, belongs to the place being left.
  const jump = useCallback(
    (seconds: number) => {
      close(false);
      player.current?.seek(seconds);
    },
    [close, player],
  );

  // What this way of watching will ask: the score and "n of N" count these.
  const list = ranges ? all.filter((question) => ranges.some(([start, end]) => question.t >= start && question.t <= end)) : all;
  const scorable = list.filter(canScore);
  const correct = scorable.filter((question) => outcomes[question.id] === 'correct').length;
  const retried = scorable.filter((question) => outcomes[question.id] === 'retried').length;
  const done = list.filter((question) => outcomes[question.id] && outcomes[question.id] !== 'skipped').length;
  const skipped = list.filter((question) => outcomes[question.id] === 'skipped').length;
  const score =
    'Questions: ' +
    (list.length === 0
      ? 'none in this version'
      : scorable.length > 0
        ? count(correct, scorable.length, 'correct')
        : count(done, list.length, 'done')) +
    (retried > 0 ? ` · ${retried} on the second try` : '') +
    (skipped > 0 ? ` · ${skipped} skipped` : '');

  return { any: all.length > 0, list, asking, enabled, score, onTime, answer, reveal, proceed, skip, rewatch, toggle, jump, tally };
}

export function QuestionOverlay({ questions }: { questions: Questions }) {
  const { asking, list } = questions;
  if (!asking) return null;
  return (
    <QuestionCard
      key={asking.turn}
      question={asking.question}
      // 0: asked under another watch mode, so it has no place in this one's count.
      number={list.indexOf(asking.question) + 1}
      of={list.length}
      questions={questions}
    />
  );
}

// "Not quite" is already the heading; the server's line for a wrong option starts with it too.
function explain(chosen: InteractionOption, right: InteractionOption | undefined): string {
  if (chosen.correct) return chosen.feedback;
  return chosen.feedback.replace(/^not quite[\s.!:,—-]*/i, '') || right?.feedback || '';
}

function QuestionCard({ question, number, of, questions }: { question: Interaction; number: number; of: number; questions: Questions }) {
  const [chosen, setChosen] = useState<InteractionOption | null>(null);
  // A wrong first try: the learner is nudged and tries once more before the answer is shown.
  const [first, setFirst] = useState<InteractionOption | null>(null);
  const [sure, setSure] = useState<Sure | null>(null);
  const [revealed, setRevealed] = useState(false);
  // On a phone the card is as small as the video, so it scrolls; `more` says there is
  // something below the fold.
  const [more, setMore] = useState(false);
  const scroller = useRef<ScrollView>(null);
  const scrolled = useRef({ view: 0, content: 0, y: 0 });
  const narrow = useWindowDimensions().width < NARROW;
  const measure = (change: Partial<{ view: number; content: number; y: number }>) => {
    const next = { ...scrolled.current, ...change };
    scrolled.current = next;
    setMore(next.content - next.view - next.y > 12);
  };

  const options = question.options;
  const right = options.find((option) => option.correct);
  const reveals = question.answer?.text || question.hints[0] || '';
  const finished = chosen !== null || revealed || (options.length === 0 && !reveals);
  // Short options sit two to a row, so four of them fit a phone-sized video.
  const paired = options.length > 1 && options.every((option) => option.text.length <= 22);
  const place = number > 0 ? `Question ${number} of ${of}` : 'Question';
  // With two options a second try is a free answer, so only three or more get one.
  const retries = options.length >= 3;

  const choose = (option: InteractionOption) => {
    if (chosen || option === first) return;
    if (!first && !option.correct && retries) {
      setFirst(option);
      questions.answer(option, 1, sure, false);
      return;
    }
    setChosen(option);
    questions.answer(option, first ? 2 : 1, sure, true);
  };
  const show = () => {
    setRevealed(true);
    questions.reveal();
  };

  return (
    <View style={[styles.scrim, narrow && styles.scrimNarrow]} role="dialog" aria-label={place}>
      <ScrollView
        ref={scroller}
        style={styles.fill}
        contentContainerStyle={[styles.center, narrow && styles.centerNarrow]}
        scrollEventThrottle={64}
        onLayout={(event) => measure({ view: event.nativeEvent.layout.height })}
        onScroll={(event) => measure({ y: event.nativeEvent.contentOffset.y })}
        onContentSizeChange={(_, height) => {
          measure({ content: height });
          // The verdict and "Continue" are added at the bottom: bring them into view.
          if (chosen !== null || revealed) scroller.current?.scrollToEnd({ animated: true });
        }}>
        <View style={[styles.card, narrow && styles.cardNarrow]}>
          <View style={styles.head}>
            <Text style={styles.label}>Your turn</Text>
            <Text style={[styles.place, styles.fill]}>{place}</Text>
            {finished ? null : (
              <Pressable accessibilityRole="button" onPress={questions.skip} style={({ pressed }) => [styles.skip, pressed && styles.pressed]}>
                <Text style={styles.skipText}>Skip</Text>
              </Pressable>
            )}
          </View>
          <Text style={[styles.prompt, narrow && styles.promptNarrow]}>{question.prompt.text}</Text>

          {question.confidence && !chosen && !first ? (
            <View style={styles.sureRow}>
              <Text style={styles.place}>How sure are you?</Text>
              {SURE.map((one) => (
                <Pressable
                  key={one.id}
                  accessibilityRole="radio"
                  aria-checked={sure === one.id}
                  onPress={() => setSure(sure === one.id ? null : one.id)}
                  style={({ pressed }) => [styles.chip, sure === one.id && styles.chipOn, pressed && styles.pressed]}>
                  <Text style={[styles.chipText, sure === one.id && styles.right]}>{one.label}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}

          {options.length > 0 ? (
            <View style={styles.options}>
              {options.map((option, index) => {
                const picked = chosen === option;
                const tried = first === option;
                const marked = (chosen !== null && (picked || option.correct)) || tried;
                const mark = !marked ? String.fromCharCode(65 + index) : option.correct ? '✓' : '✗';
                const said = !marked ? '' : option.correct ? (picked ? ', your answer, correct' : ', the correct answer') : tried && !picked ? ', your first answer, not correct' : ', your answer, not correct';
                return (
                  <Pressable
                    key={option.id}
                    accessibilityRole="button"
                    accessibilityLabel={option.text + said}
                    disabled={chosen !== null || tried}
                    onPress={() => choose(option)}
                    style={({ pressed }) => [
                      styles.option,
                      paired && styles.optionPaired,
                      marked && (option.correct ? styles.optionRight : styles.optionWrong),
                      chosen !== null && !marked && styles.optionOther,
                      pressed && styles.pressed,
                    ]}>
                    <Text style={[styles.mark, marked && (option.correct ? styles.right : styles.wrong)]}>{mark}</Text>
                    <Text style={styles.optionText}>{option.text}</Text>
                  </Pressable>
                );
              })}
            </View>
          ) : null}

          {first && !chosen ? (
            <View style={styles.verdict} aria-live="polite">
              <Text style={[styles.verdictTitle, styles.wrong]}>Not yet. Try once more.</Text>
              {explain(first, undefined) ? <Text style={styles.body}>{explain(first, undefined)}</Text> : null}
            </View>
          ) : null}
          {chosen ? (
            <View style={styles.verdict} aria-live="polite">
              <Text style={[styles.verdictTitle, chosen.correct ? styles.right : styles.wrong]}>
                {chosen.correct ? (first ? '✓ Right, on the second try' : '✓ Correct') : '✗ Not quite'}
              </Text>
              {!chosen.correct && right ? (
                <Text style={styles.body}>
                  <Text style={styles.right}>✓ </Text>
                  The answer is: {right.text}
                </Text>
              ) : null}
              {explain(chosen, right) ? <Text style={styles.body}>{explain(chosen, right)}</Text> : null}
            </View>
          ) : null}
          {revealed ? (
            <View style={styles.verdict} aria-live="polite">
              <Text style={styles.label}>Answer</Text>
              <Text style={styles.body}>{reveals}</Text>
            </View>
          ) : null}

          {finished && chosen && !chosen.correct && question.on_wrong ? (
            <Pressable accessibilityRole="button" onPress={questions.rewatch} style={({ pressed }) => [styles.secondary, pressed && styles.pressed]}>
              <Text style={styles.secondaryText}>↺ Watch that part again</Text>
            </Pressable>
          ) : null}
          {finished ? (
            <Pressable accessibilityRole="button" onPress={questions.proceed} style={({ pressed }) => [styles.primary, pressed && styles.pressed]}>
              <Text style={styles.primaryText}>Continue</Text>
            </Pressable>
          ) : options.length === 0 ? (
            <Pressable accessibilityRole="button" onPress={show} style={({ pressed }) => [styles.primary, pressed && styles.pressed]}>
              <Text style={styles.primaryText}>Show answer</Text>
            </Pressable>
          ) : null}
        </View>
      </ScrollView>
      {more ? (
        <View style={styles.more}>
          <Text style={styles.moreText}>▾ Scroll for more</Text>
        </View>
      ) : null}
    </View>
  );
}

export function QuestionBar({ questions }: { questions: Questions }) {
  if (!questions.any) return null;
  const on = questions.enabled;
  return (
    <View style={styles.bar}>
      <Text style={styles.score} aria-live="polite">
        {questions.score}
      </Text>
      <Pressable
        accessibilityRole="switch"
        accessibilityLabel="Pause for questions"
        aria-checked={on}
        onPress={questions.toggle}
        hitSlop={8}
        style={({ pressed }) => [styles.toggle, pressed && styles.pressed]}>
        <Text style={styles.toggleText}>Pause for questions</Text>
        <View style={[styles.track, on && styles.trackOn]}>
          <View style={[styles.knob, on && styles.knobOn]} />
        </View>
        <Text style={[styles.toggleState, on && styles.right]}>{on ? 'On' : 'Off'}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  scrim: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, backgroundColor: 'rgba(5, 9, 17, 0.84)' },
  // On a phone the video is small, so the question takes all of it rather than a card in it.
  scrimNarrow: { backgroundColor: 'rgba(5, 9, 17, 0.92)' },
  fill: { flex: 1 },
  center: { flexGrow: 1, justifyContent: 'center', padding: 14 },
  centerNarrow: { padding: 10 },
  card: {
    width: '100%',
    maxWidth: 560,
    alignSelf: 'center',
    backgroundColor: 'rgba(17, 30, 49, 0.94)',
    borderWidth: 1,
    borderColor: C.line,
    borderRadius: 12,
    padding: 14,
    gap: 10,
  },
  cardNarrow: { padding: 0, gap: 8, borderWidth: 0, backgroundColor: 'transparent' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  label: { color: C.teal, fontSize: 11, letterSpacing: 1.2, fontWeight: '700', textTransform: 'uppercase' },
  place: { color: C.muted, fontSize: 12 },
  prompt: { color: C.ink, fontSize: 17, lineHeight: 24, fontWeight: '600' },
  promptNarrow: { fontSize: 15, lineHeight: 21 },
  options: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  option: {
    flexGrow: 1,
    flexBasis: '100%',
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: C.bg,
    borderWidth: 1.5,
    borderColor: C.line,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 9,
  },
  optionPaired: { flexBasis: '46%' },
  optionRight: { borderColor: C.teal },
  optionWrong: { borderColor: C.pink },
  optionOther: { opacity: 0.5 },
  mark: { color: C.muted, fontSize: 15, fontWeight: '700', width: 16, textAlign: 'center' },
  optionText: { color: C.ink, fontSize: 15, lineHeight: 20, flex: 1 },
  verdict: { gap: 4 },
  verdictTitle: { fontSize: 16, fontWeight: '700' },
  right: { color: C.teal },
  wrong: { color: C.pink },
  body: { color: C.ink, fontSize: 14, lineHeight: 20 },
  primary: { minHeight: 44, justifyContent: 'center', alignItems: 'center', backgroundColor: C.teal, borderRadius: 10, paddingHorizontal: 18, paddingVertical: 10 },
  primaryText: { color: C.bg, fontSize: 16, fontWeight: '600' },
  secondary: { minHeight: 44, justifyContent: 'center', alignItems: 'center', borderWidth: 1.5, borderColor: C.teal, borderRadius: 10, paddingHorizontal: 18, paddingVertical: 10 },
  secondaryText: { color: C.teal, fontSize: 15, fontWeight: '600' },
  sureRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 },
  chip: { minHeight: 32, justifyContent: 'center', borderWidth: 1, borderColor: C.line, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  chipOn: { borderColor: C.teal, backgroundColor: 'rgba(87, 214, 191, 0.12)' },
  chipText: { color: C.muted, fontSize: 13 },
  // A text link, with padding that widens the tap target without moving the layout.
  skip: { padding: 12, margin: -12 },
  skipText: { color: C.muted, fontSize: 14, textDecorationLine: 'underline' },
  more: { position: 'absolute', left: 0, right: 0, bottom: 4, alignItems: 'center', pointerEvents: 'none' },
  moreText: { color: C.ink, fontSize: 12, fontWeight: '600', backgroundColor: 'rgba(41, 57, 79, 0.96)', borderRadius: 999, overflow: 'hidden', paddingHorizontal: 10, paddingVertical: 3 },
  pressed: { opacity: 0.7 },
  bar: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', columnGap: 14, rowGap: 6 },
  score: { color: C.ink, fontSize: 14, lineHeight: 20, fontVariant: ['tabular-nums'] },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: 32 },
  toggleText: { color: C.muted, fontSize: 14 },
  track: { width: 38, height: 22, borderRadius: 11, borderWidth: 1.5, borderColor: C.muted, padding: 2, justifyContent: 'center' },
  trackOn: { borderColor: C.teal, backgroundColor: 'rgba(87, 214, 191, 0.18)' },
  knob: { width: 14, height: 14, borderRadius: 7, backgroundColor: C.muted },
  knobOn: { backgroundColor: C.teal, alignSelf: 'flex-end' },
  toggleState: { color: C.muted, fontSize: 13, fontWeight: '600', width: 24 },
});
