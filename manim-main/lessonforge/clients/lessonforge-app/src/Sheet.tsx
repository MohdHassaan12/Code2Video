// A feedback sheet, as both forms draw it: the student's review of one lesson
// (Review.tsx) and the tester's account of making lessons (Feedback.tsx). The server
// sends the questions; this file is how each kind is asked, what counts as answered,
// and the send button with its rules — nothing is sent while a required answer is
// missing, the missing ones are named, and a failed send keeps every answer.
//
//   useSheet         the answers, and which required ones are still missing
//   SheetQuestions   the questions, grouped by section
//   SheetField       an optional one-line field (a name, a contact)
//   SheetSend        what is missing, what went wrong, and the button
import { ReactNode, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { FeedbackAnswer, FeedbackForm, FeedbackQuestion, Job } from './api';
import { C } from './theme';

export type Answers = Record<string, FeedbackAnswer>;
// `final`: trying again cannot help (the link is no longer accepted).
export type Problem = { final: boolean; message: string };
type Chapters = NonNullable<Job['chapters']>;

function answered(value: FeedbackAnswer | undefined): boolean {
  if (value === undefined) return false;
  if (Array.isArray(value)) return value.length > 0;
  return typeof value === 'number' || value.trim() !== '';
}

// Tap to add, tap again to take away; `many` false keeps at most one.
export function flip<T>(list: T[], item: T, many: boolean): T[] {
  if (list.includes(item)) return list.filter((one) => one !== item);
  return many ? [...list, item] : [item];
}

export function minutesLine(form: FeedbackForm): string {
  return Number.isFinite(form.minutes) && form.minutes > 0 ? `about ${form.minutes} minute${form.minutes === 1 ? '' : 's'}` : '';
}

export type Sheet = ReturnType<typeof useSheet>;

export function useSheet(form: FeedbackForm, initial: Answers = {}) {
  const [answers, setAnswers] = useState<Answers>(initial);
  // Required questions found unanswered at the last press of the send button.
  const [missing, setMissing] = useState<string[]>([]);
  const left = form.questions.filter((question) => question.required && !answered(answers[question.id]));

  const put = (id: string, value: FeedbackAnswer | undefined) => {
    setAnswers((old) => {
      const next = { ...old };
      if (value === undefined) delete next[id];
      else next[id] = value;
      return next;
    });
    if (answered(value)) setMissing((old) => (old.includes(id) ? old.filter((one) => one !== id) : old));
  };

  return {
    answers,
    missing,
    left,
    put,
    // For the send button: true when nothing required is missing; otherwise what is
    // missing is now marked on the sheet.
    complete: () => {
      setMissing(left.map((question) => question.id));
      return left.length === 0;
    },
    // What is sent: every answer given, text trimmed.
    given: () => {
      const filled: Answers = {};
      for (const question of form.questions) {
        const value = answers[question.id];
        if (answered(value)) filled[question.id] = typeof value === 'string' ? value.trim() : value;
      }
      return filled;
    },
    clear: () => {
      setAnswers({});
      setMissing([]);
    },
  };
}

// `chapters`: the lesson's own, for the questions answered by picking chapters.
export function SheetQuestions({ form, sheet, chapters = [] }: { form: FeedbackForm; sheet: Sheet; chapters?: Chapters }) {
  const sections = [...new Set(form.questions.map((question) => question.section || ''))];
  return (
    <>
      {sections.map((section) => (
        <View key={section} style={sheetStyles.section}>
          {section ? <Text style={sheetStyles.sectionTitle}>{section}</Text> : null}
          {form.questions
            .filter((question) => (question.section || '') === section)
            .map((question) => {
              const needed = sheet.missing.includes(question.id);
              return (
                <View key={question.id} style={[sheetStyles.card, needed && styles.cardMissing]}>
                  <Text style={styles.prompt}>
                    {question.prompt}
                    {question.required ? null : <Text style={styles.optional}>{'  optional'}</Text>}
                  </Text>
                  {needed ? <Text style={styles.needed}>Please answer this one.</Text> : null}
                  <Control question={question} value={sheet.answers[question.id]} chapters={chapters} put={sheet.put} />
                </View>
              );
            })}
        </View>
      ))}
    </>
  );
}

// One question's answer control, by kind.
function Control({
  question,
  value,
  chapters,
  put,
}: {
  question: FeedbackQuestion;
  value: FeedbackAnswer | undefined;
  chapters: Chapters;
  put: Sheet['put'];
}) {
  if (question.kind === 'rating') {
    const low = Number.isFinite(question.min) ? Number(question.min) : 1;
    const high = Math.min(Number.isFinite(question.max) ? Number(question.max) : 5, low + 9);
    const steps = Array.from({ length: Math.max(1, high - low + 1) }, (_, i) => low + i);
    return (
      <>
        <View style={styles.scale} role="radiogroup" aria-label={question.prompt}>
          {steps.map((n) => {
            const on = value === n;
            const end = n === low ? question.low_label : n === high ? question.high_label : '';
            return (
              <Pressable
                key={n}
                role="radio"
                aria-checked={on}
                aria-label={end ? `${n}, ${end}` : String(n)}
                onPress={() => put(question.id, n)}
                style={({ pressed }) => [styles.step, on && styles.stepOn, pressed && sheetStyles.pressed]}>
                <Text style={[styles.stepText, on && styles.stepTextOn]}>{n}</Text>
              </Pressable>
            );
          })}
        </View>
        <View style={styles.ends}>
          <Text style={styles.end}>{question.low_label}</Text>
          <Text style={[styles.end, styles.endRight]}>{question.high_label}</Text>
        </View>
      </>
    );
  }
  if (question.kind === 'text') {
    const written = typeof value === 'string' ? value : '';
    const max = Number.isFinite(question.max_length) && Number(question.max_length) > 0 ? Number(question.max_length) : 400;
    return (
      <>
        <TextInput
          value={written}
          onChangeText={(next) => put(question.id, next)}
          multiline
          maxLength={max}
          aria-label={question.prompt}
          placeholder={question.placeholder || 'Write here'}
          placeholderTextColor={C.muted}
          style={[styles.input, styles.area]}
        />
        <Text style={[styles.counter, written.length >= max && styles.counterFull]}>
          {written.length} / {max}
        </Text>
      </>
    );
  }
  if (question.kind === 'chapters') {
    const picked = Array.isArray(value) ? (value as number[]) : [];
    const many = question.multiple === true;
    return (
      <Choices
        round={!many}
        label={question.prompt}
        items={chapters.map((chapter) => ({ key: String(chapter.id), label: chapter.title, on: picked.includes(chapter.id) }))}
        onPress={(key) => put(question.id, flip(picked, Number(key), many))}
      />
    );
  }
  const options = question.options ?? [];
  if (question.kind === 'multi') {
    const picked = Array.isArray(value) ? (value as string[]) : [];
    return (
      <Choices
        round={false}
        label={question.prompt}
        items={options.map((option) => ({ key: option.value, label: option.label, on: picked.includes(option.value) }))}
        onPress={(key) => put(question.id, flip(picked, key, true))}
      />
    );
  }
  return (
    <Choices
      round
      label={question.prompt}
      items={options.map((option) => ({ key: option.value, label: option.label, on: value === option.value }))}
      onPress={(key) => put(question.id, value === key ? undefined : key)}
    />
  );
}

// Buttons to pick from: `round` for one of them (radio), square for any number (checkboxes).
function Choices({
  items,
  round,
  label,
  onPress,
}: {
  items: { key: string; label: string; on: boolean }[];
  round: boolean;
  label: string;
  onPress: (key: string) => void;
}) {
  // Short answers sit two to a row.
  const paired = items.length > 2 && items.every((item) => item.label.length <= 12);
  return (
    <View style={styles.choices} role={round ? 'radiogroup' : 'group'} aria-label={label}>
      {items.map((item) => (
        <Pressable
          key={item.key}
          role={round ? 'radio' : 'checkbox'}
          aria-checked={item.on}
          onPress={() => onPress(item.key)}
          style={({ pressed }) => [styles.choice, paired && styles.choicePaired, item.on && styles.choiceOn, pressed && sheetStyles.pressed]}>
          <Mark round={round} on={item.on} />
          <Text style={styles.choiceText}>{item.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

// The tick box (or radio dot) beside a choice: shape as well as colour says "picked".
export function Mark({ on, round = false }: { on: boolean; round?: boolean }): ReactNode {
  return (
    <View style={[styles.mark, round && styles.markRound, on && styles.markOn]}>
      {on ? round ? <View style={styles.dot} /> : <Text style={styles.tick}>✓</Text> : null}
    </View>
  );
}

export function SheetField({
  label,
  value,
  onChangeText,
  maxLength,
  placeholder = 'You can leave this empty',
}: {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  maxLength: number;
  placeholder?: string;
}) {
  return (
    <View style={sheetStyles.card}>
      <Text style={styles.prompt}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        maxLength={maxLength}
        autoCorrect={false}
        aria-label={label}
        placeholder={placeholder}
        placeholderTextColor={C.muted}
        style={styles.input}
      />
    </View>
  );
}

// The button looks (and reads) unavailable until every required question is answered,
// yet it can be pressed: the press is what names the questions still missing.
export function SheetSend({
  form,
  sheet,
  sending,
  problem,
  label,
  onSend,
}: {
  form: FeedbackForm;
  sheet: Sheet;
  sending: boolean;
  problem: Problem | null;
  label: string;
  onSend: () => void;
}) {
  const left = sheet.left.length;
  const waiting = `${left} question${left === 1 ? '' : 's'} still to answer before you can send.`;
  return (
    <>
      {sheet.missing.length > 0 ? (
        <View style={[sheetStyles.card, styles.cardMissing]} aria-live="polite">
          <Text style={styles.needed}>Please answer these first:</Text>
          {form.questions
            .filter((question) => sheet.missing.includes(question.id))
            .map((question) => (
              <Text key={question.id} style={sheetStyles.body}>
                • {question.prompt}
              </Text>
            ))}
        </View>
      ) : null}
      {problem ? (
        <Text style={styles.problem} aria-live="polite">
          {problem.message}
        </Text>
      ) : null}
      {problem?.final ? null : (
        <Pressable
          accessibilityRole="button"
          aria-label={left > 0 && !sending ? `${label}: ${waiting}` : undefined}
          disabled={sending}
          onPress={onSend}
          style={({ pressed }) => [styles.primary, (left > 0 || sending || pressed) && styles.dimmed]}>
          <Text style={styles.primaryText}>{sending ? 'Sending…' : problem ? 'Try again' : label}</Text>
        </Pressable>
      )}
      {left > 0 ? <Text style={styles.hint}>{waiting}</Text> : null}
    </>
  );
}

// Shared with the screens a sheet sits in.
export const sheetStyles = StyleSheet.create({
  card: { backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 14, padding: 14, gap: 10 },
  cardTitle: { color: C.ink, fontSize: 17, fontWeight: '600' },
  body: { color: C.ink, fontSize: 15, lineHeight: 22 },
  section: { gap: 10, marginTop: 8 },
  sectionTitle: { color: C.ink, fontSize: 19, fontWeight: '600' },
  thanks: { borderColor: C.teal },
  thanksTitle: { color: C.teal, fontSize: 18, lineHeight: 25, fontWeight: '600' },
  // Text buttons, with padding that widens the tap target without moving the layout.
  link: { alignSelf: 'flex-start', padding: 10, margin: -10 },
  linkText: { color: C.teal, fontSize: 15, fontWeight: '600', textDecorationLine: 'underline' },
  secondary: { minHeight: 48, justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: C.teal, borderRadius: 12, paddingHorizontal: 18 },
  secondaryText: { color: C.teal, fontSize: 16, fontWeight: '600' },
  pressed: { opacity: 0.7 },
});

const styles = StyleSheet.create({
  cardMissing: { borderColor: C.pink },
  prompt: { color: C.ink, fontSize: 17, lineHeight: 24, fontWeight: '600' },
  optional: { color: C.muted, fontSize: 13, fontWeight: '400' },
  needed: { color: C.pink, fontSize: 14, lineHeight: 20, fontWeight: '600' },
  scale: { flexDirection: 'row', gap: 8 },
  step: { flex: 1, minHeight: 54, justifyContent: 'center', alignItems: 'center', backgroundColor: C.bg, borderWidth: 1.5, borderColor: C.line, borderRadius: 12 },
  stepOn: { backgroundColor: C.teal, borderColor: C.teal },
  stepText: { color: C.ink, fontSize: 20, fontWeight: '600' },
  stepTextOn: { color: C.bg, fontWeight: '800' },
  ends: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 },
  end: { flex: 1, color: C.muted, fontSize: 13, lineHeight: 18 },
  endRight: { textAlign: 'right' },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  choice: { flexGrow: 1, flexBasis: '100%', minHeight: 50, flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: C.bg, borderWidth: 1.5, borderColor: C.line, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10 },
  choicePaired: { flexBasis: '46%' },
  choiceOn: { borderColor: C.teal },
  choiceText: { flex: 1, color: C.ink, fontSize: 16, lineHeight: 22 },
  mark: { width: 24, height: 24, borderRadius: 6, borderWidth: 2, borderColor: C.muted, justifyContent: 'center', alignItems: 'center' },
  markRound: { borderRadius: 12 },
  markOn: { borderColor: C.teal, backgroundColor: C.teal },
  tick: { color: C.bg, fontSize: 15, lineHeight: 18, fontWeight: '800' },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: C.bg },
  input: { color: C.ink, backgroundColor: C.bg, borderWidth: 1.5, borderColor: C.line, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, minHeight: 50 },
  area: { minHeight: 96, textAlignVertical: 'top' },
  counter: { color: C.muted, fontSize: 12, textAlign: 'right', fontVariant: ['tabular-nums'] },
  counterFull: { color: C.gold },
  problem: { color: C.pink, fontSize: 15, lineHeight: 22 },
  primary: { minHeight: 56, justifyContent: 'center', alignItems: 'center', backgroundColor: C.teal, borderRadius: 14, paddingHorizontal: 18, paddingVertical: 14 },
  primaryText: { color: C.bg, fontSize: 18, fontWeight: '700' },
  dimmed: { opacity: 0.45 },
  hint: { color: C.muted, fontSize: 14, lineHeight: 20, textAlign: 'center' },
});
