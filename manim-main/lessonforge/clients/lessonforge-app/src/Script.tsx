// The second way to start a video: paste the words, and the video is made from them.
//
//   ModeSwitch      "Describe a topic" (the questions) or "Use my script", on the start screen
//   ScriptForm      the script itself and, optionally, who it is for
//   ScriptPlanCard  the server's read-back before anything is spent: length, parts, what will
//                   not be spoken, the narration language and whether the words may be changed
//
// The server decides what a script becomes (POST /script/preview); the count under the
// box is only an estimate while typing.
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { ScriptPlan } from './api';
import { C } from './theme';

export type Mode = 'topic' | 'script';
// "keep": spoken exactly as written. "fix": a reviewer model may rewrite what it finds wrong.
export type ScriptEdit = 'keep' | 'fix';

// The server's own limits (harness/scripted.py), used only for the hint while typing.
export const MIN_SCRIPT_WORDS = 20;
const MAX_SCRIPT_WORDS = 3500;
const WORDS_PER_MINUTE = 125;

const MODES: { value: Mode; label: string; hint: string }[] = [
  { value: 'topic', label: 'Describe a topic', hint: 'Answer a few questions; the script is written for you' },
  { value: 'script', label: 'Use my script', hint: 'Paste your own words; the video is made from them' },
];
const EDITS: { value: ScriptEdit; label: string; hint: string }[] = [
  { value: 'keep', label: 'Keep my words exactly', hint: 'Spoken as written. The script check still tells you what it found.' },
  { value: 'fix', label: 'Fix mistakes it finds', hint: 'A reviewer may rewrite a sentence it finds wrong, repeated or unclear.' },
];

// Roughly the words that will be SPOKEN: headings, [directions] and "Visual:" lines are not.
export function countWords(text: string): number {
  const spoken = text
    .split('\n')
    .filter((line) => !/^\s*(#|(visuals?|on[- ]screen|screen|show|animation|picture|graphic)\s*:)/i.test(line))
    .join(' ')
    .replace(/\[[^\]\n]*\]/g, ' ');
  return spoken.trim().split(/\s+/).filter(Boolean).length;
}

function lengthOf(words: number): string {
  const seconds = (words / WORDS_PER_MINUTE) * 60;
  return seconds < 90 ? `about ${Math.max(10, Math.round(seconds / 10) * 10)} seconds` : `about ${Math.round(seconds / 60)} min`;
}

export function ModeSwitch({ mode, onChange, disabled }: { mode: Mode; onChange: (mode: Mode) => void; disabled?: boolean }) {
  const hint = MODES.find((m) => m.value === mode)?.hint;
  return (
    <View style={styles.block}>
      <View style={styles.switch}>
        {MODES.map((m) => (
          <Pressable
            key={m.value}
            disabled={disabled}
            onPress={() => onChange(m.value)}
            style={[styles.segment, mode === m.value && styles.segmentOn]}>
            <Text style={[styles.segmentText, mode === m.value && styles.segmentTextOn]}>{m.label}</Text>
          </Pressable>
        ))}
      </View>
      {hint ? <Text style={styles.fine}>{hint}</Text> : null}
    </View>
  );
}

export function ScriptForm({
  script,
  onScript,
  audience,
  onAudience,
  busy,
  onCheck,
}: {
  script: string;
  onScript: (text: string) => void;
  audience: string;
  onAudience: (text: string) => void;
  busy: boolean;
  onCheck: () => void;
}) {
  const words = countWords(script);
  const tooLong = words > MAX_SCRIPT_WORDS;
  const ready = words >= MIN_SCRIPT_WORDS && !tooLong;
  return (
    <View style={styles.block}>
      <View style={styles.lead}>
        <Text style={styles.leadText}>Paste the script you want narrated.</Text>
        <Text style={styles.why}>Your words are spoken as you wrote them, and the picture is designed to match what they say.</Text>
      </View>
      <TextInput
        multiline
        numberOfLines={12}
        value={script}
        onChangeText={onScript}
        editable={!busy}
        placeholder="Paste or type your script here…"
        placeholderTextColor={C.muted}
        textAlignVertical="top"
        style={[styles.script, busy && styles.disabled]}
      />
      <Text style={[styles.fine, tooLong && styles.over]}>
        {words === 0
          ? `At least ${MIN_SCRIPT_WORDS} words.`
          : tooLong
            ? `${words} words: one video takes up to ${MAX_SCRIPT_WORDS}. Split it into parts.`
            : words < MIN_SCRIPT_WORDS
              ? `${words} of at least ${MIN_SCRIPT_WORDS} words`
              : `${words} words · ${lengthOf(words)} of video`}
      </Text>
      <View style={styles.tips}>
        <Text style={styles.tip}>
          <Text style={styles.mark}># </Text>at the start of a line names a part of the video.
        </Text>
        <Text style={styles.tip}>
          <Text style={styles.mark}>[square brackets] </Text>hold a direction for the picture. They are not spoken.
        </Text>
        <Text style={styles.tip}>A blank line starts a new paragraph.</Text>
      </View>
      <Text style={styles.label}>Who is it for? (optional)</Text>
      <TextInput
        value={audience}
        onChangeText={onAudience}
        editable={!busy}
        placeholder="e.g. Class 8 students"
        placeholderTextColor={C.muted}
        style={[styles.line, busy && styles.disabled]}
      />
      <Pressable disabled={busy || !ready} onPress={onCheck} style={({ pressed }) => [styles.primary, (pressed || busy || !ready) && styles.dim]}>
        <Text style={styles.primaryText}>{busy ? 'Reading it…' : 'Check my script'}</Text>
      </Pressable>
    </View>
  );
}

export function ScriptPlanCard({
  plan,
  language,
  onLanguage,
  edit,
  onEdit,
}: {
  plan: ScriptPlan;
  language: string;
  onLanguage: (value: string) => void;
  edit: ScriptEdit;
  onEdit: (value: ScriptEdit) => void;
}) {
  const chosen = plan.languages.find((l) => l.value === language);
  return (
    <View style={styles.block}>
      <View style={styles.card}>
        {plan.summary.map((row) => (
          <View key={row.label} style={styles.row}>
            <Text style={styles.label}>{row.label}</Text>
            {/* The language can still be changed below; the row follows the choice. */}
            <Text style={styles.value}>{row.label === 'Language' && chosen ? chosen.label : row.value}</Text>
          </View>
        ))}
      </View>
      {plan.chapters.length > 0 ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>The parts, from your headings</Text>
          {plan.chapters.map((chapter, i) => (
            <View key={`${i}-${chapter.title}`} style={styles.row}>
              <Text style={styles.value}>
                {i + 1}. {chapter.title}
              </Text>
              <Text style={styles.fine}>
                {chapter.words} words · opens “{chapter.opens}…”
              </Text>
            </View>
          ))}
        </View>
      ) : (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>It opens with</Text>
          <Text style={styles.value}>“{plan.opens}…”</Text>
        </View>
      )}
      {plan.notes.map((note) => (
        <Text key={note} style={styles.fine}>
          {note}
        </Text>
      ))}
      <Text style={styles.heading}>Narration language</Text>
      <View style={styles.chips}>
        {plan.languages.map((l) => (
          <Pressable key={String(l.value)} onPress={() => onLanguage(String(l.value))} style={[styles.chip, language === l.value && styles.chipOn]}>
            <Text style={[styles.chipText, language === l.value && styles.chipTextOn]}>{l.label}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={styles.heading}>Your words</Text>
      <View style={styles.chips}>
        {EDITS.map((e) => (
          <Pressable key={e.value} onPress={() => onEdit(e.value)} style={[styles.chip, edit === e.value && styles.chipOn]}>
            <Text style={[styles.chipText, edit === e.value && styles.chipTextOn]}>{e.label}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={styles.fine}>{EDITS.find((e) => e.value === edit)?.hint}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  block: { gap: 10 },
  switch: { flexDirection: 'row', gap: 8 },
  segment: { flex: 1, borderWidth: 1, borderColor: C.line, backgroundColor: C.panel, borderRadius: 12, paddingVertical: 12, paddingHorizontal: 10, alignItems: 'center' },
  segmentOn: { borderColor: C.teal },
  segmentText: { color: C.muted, fontSize: 15, fontWeight: '600', textAlign: 'center' },
  segmentTextOn: { color: C.teal },
  lead: { alignSelf: 'flex-start', maxWidth: '88%', backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 14, paddingVertical: 11, paddingHorizontal: 14 },
  leadText: { color: C.ink, fontSize: 17, lineHeight: 24 },
  why: { color: C.muted, fontSize: 13, lineHeight: 19, marginTop: 6 },
  script: { color: C.ink, backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, lineHeight: 23, minHeight: 260 },
  line: { color: C.ink, backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16 },
  disabled: { opacity: 0.4 },
  dim: { opacity: 0.5 },
  fine: { color: C.muted, fontSize: 12, lineHeight: 18 },
  over: { color: C.pink },
  tips: { gap: 3 },
  tip: { color: C.muted, fontSize: 13, lineHeight: 19 },
  mark: { color: C.teal, fontWeight: '600' },
  label: { color: C.muted, fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase' },
  heading: { color: C.ink, fontSize: 19, fontWeight: '600', marginTop: 6 },
  primary: { backgroundColor: C.teal, borderRadius: 12, paddingVertical: 15, alignItems: 'center', marginTop: 4 },
  primaryText: { color: C.bg, fontSize: 16, fontWeight: '600' },
  card: { backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 14, padding: 14, gap: 10 },
  cardTitle: { color: C.ink, fontSize: 16, fontWeight: '600' },
  row: { gap: 2 },
  value: { color: C.ink, fontSize: 15, lineHeight: 22 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: 1, borderColor: C.line, backgroundColor: C.panel, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 9 },
  chipOn: { borderColor: C.teal },
  chipText: { color: C.muted, fontSize: 14 },
  chipTextOn: { color: C.teal },
});
