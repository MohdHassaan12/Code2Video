// Every field of the brief, editable before the lesson is made. The intake fills the brief from a conversation;
// this shows what it holds and lets the requester change any of it, or set what the intake never asks for
// (the class, the audience, a second drawing, a fresh take). The choice lists come from the server
// (GET /frameworks), so they are the intake's own. Folded by default behind the summary card.
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { api, Brief, Choice, FrameworkList } from './api';
import { C } from './theme';

type Field = { key: string; label: string; hint?: string; kind: 'text' | 'long' | 'number' | 'choice' | 'toggle'; choices?: Choice[] };

export function BriefEdit({ server, base, value, onChange }: { server: string; base: Brief; value: Brief; onChange: (next: Brief) => void }) {
  const [lists, setLists] = useState<FrameworkList | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const request = new AbortController();
    api
      .frameworks(server, request.signal)
      .then(setLists)
      .catch(() => setLists(null));
    return () => request.abort();
  }, [server]);
  const fields: Field[] = [
    { key: 'topic', label: 'Topic', kind: 'text' },
    { key: 'focus', label: 'Focus', hint: 'The one idea, when the topic is broad.', kind: 'text' },
    { key: 'school_subject', label: 'Subject', kind: 'choice', choices: [{ value: 'maths', label: 'Maths' }, { value: 'science', label: 'Science' }] },
    { key: 'grade', label: 'Class', hint: 'Picks the textbook chapter the sources are read from.', kind: 'number' },
    { key: 'audience', label: 'Audience', hint: 'Who watches, in your words.', kind: 'text' },
    { key: 'level', label: 'Starting point', kind: 'choice', choices: lists?.levels ?? [] },
    { key: 'style', label: 'Voice of the narration', kind: 'choice', choices: lists?.styles ?? [] },
    { key: 'language', label: 'Language', kind: 'choice', choices: lists?.languages ?? [] },
    { key: 'duration_minutes', label: 'Length (minutes)', hint: 'At least 3.', kind: 'choice', choices: lists?.durations ?? [] },
    {
      key: 'framework',
      label: 'Kind of video',
      kind: 'choice',
      choices: (lists?.frameworks ?? []).map((f) => ({ value: f.id, label: f.plain || f.name || f.id })),
    },
    { key: 'goal', label: 'They will be able to', kind: 'long' },
    { key: 'context', label: 'Example', hint: 'A suggestion: the writer uses it only if it is simpler than the thing itself.', kind: 'long' },
    { key: 'misconception', label: 'Known mistake', kind: 'long' },
    { key: 'more_pictures', label: 'Ask for more drawings', hint: 'Up to three more from the drawing service.', kind: 'toggle' },
    { key: 'card', label: 'Teaching card from sources', hint: 'Also set by “How it is planned” above.', kind: 'toggle' },
    { key: 'fresh', label: 'A fresh take', hint: 'Do not reuse a script or review kept for the same brief.', kind: 'toggle' },
  ];
  const changed = Object.keys(value).length;
  const current = (key: string): unknown => (key in value ? value[key] : base[key]);
  const set = (key: string, next: unknown) => {
    const copy = { ...value };
    const same = next === base[key] || (next === undefined && base[key] === undefined) || (next === '' && (base[key] === undefined || base[key] === ''));
    if (same) delete copy[key];
    else copy[key] = next;
    onChange(copy);
  };
  return (
    <View style={styles.wrap}>
      <Pressable onPress={() => setOpen(!open)} style={styles.head} aria-label="Change the details">
        <Text style={styles.title}>Change the details</Text>
        <Text style={styles.count}>{changed > 0 ? `${changed} changed` : 'as answered'}</Text>
        <Text style={styles.arrow}>{open ? '▾' : '▸'}</Text>
      </Pressable>
      {open ? (
        <View style={styles.card}>
          {changed > 0 ? (
            <Text style={styles.link} onPress={() => onChange({})}>
              Reset all
            </Text>
          ) : null}
          {fields.map((field) => {
            const now = current(field.key);
            const isChanged = field.key in value;
            return (
              <View key={field.key} style={styles.row}>
                <View style={styles.labelRow}>
                  <Text style={[styles.label, isChanged && styles.labelOn]}>{field.label}</Text>
                  {isChanged ? (
                    <Text style={styles.link} onPress={() => set(field.key, base[field.key])}>
                      reset
                    </Text>
                  ) : null}
                </View>
                {field.kind === 'choice' ? (
                  <View style={styles.chips}>
                    {(field.choices ?? []).map((choice) => {
                      const on = String(now ?? '') === String(choice.value);
                      return (
                        <Pressable key={String(choice.value)} onPress={() => set(field.key, on ? undefined : choice.value)} style={[styles.chip, on && styles.chipOn]}>
                          <Text style={[styles.chipText, on && styles.chipTextOn]}>{choice.label}</Text>
                        </Pressable>
                      );
                    })}
                    {field.key === 'duration_minutes' ? (
                      <TextInput
                        value={typeof now === 'number' || typeof now === 'string' ? String(now) : ''}
                        onChangeText={(text) => {
                          const n = Number.parseInt(text, 10);
                          set(field.key, text.trim() === '' ? undefined : Number.isFinite(n) ? n : text);
                        }}
                        placeholder="minutes"
                        placeholderTextColor={C.muted}
                        keyboardType="numeric"
                        style={[styles.input, styles.short, isChanged && styles.inputOn]}
                      />
                    ) : null}
                  </View>
                ) : field.kind === 'toggle' ? (
                  <View style={styles.chips}>
                    {[true, false].map((v) => {
                      const on = Boolean(now) === v;
                      return (
                        <Pressable key={String(v)} onPress={() => set(field.key, v || undefined)} style={[styles.chip, on && styles.chipOn]}>
                          <Text style={[styles.chipText, on && styles.chipTextOn]}>{v ? 'Yes' : 'No'}</Text>
                        </Pressable>
                      );
                    })}
                  </View>
                ) : (
                  <TextInput
                    value={typeof now === 'number' || typeof now === 'string' ? String(now) : ''}
                    onChangeText={(text) => {
                      if (field.kind === 'number') {
                        const n = Number.parseInt(text, 10);
                        set(field.key, text.trim() === '' ? undefined : Number.isFinite(n) ? n : text);
                      } else set(field.key, text);
                    }}
                    multiline={field.kind === 'long'}
                    numberOfLines={field.kind === 'long' ? 2 : 1}
                    keyboardType={field.kind === 'number' ? 'numeric' : 'default'}
                    placeholder={field.kind === 'number' ? 'e.g. 8' : ''}
                    placeholderTextColor={C.muted}
                    textAlignVertical="top"
                    style={[styles.input, field.kind === 'long' && styles.long, isChanged && styles.inputOn]}
                  />
                )}
                {field.hint ? <Text style={styles.hint}>{field.hint}</Text> : null}
              </View>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 8, marginTop: 6 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  title: { color: C.ink, fontSize: 19, fontWeight: '600', flex: 1 },
  count: { color: C.muted, fontSize: 12 },
  arrow: { color: C.muted, fontSize: 14 },
  card: { backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 12, padding: 12, gap: 10 },
  link: { color: C.teal, textDecorationLine: 'underline', fontSize: 12 },
  row: { gap: 6, borderTopWidth: 1, borderTopColor: C.line, paddingTop: 10 },
  labelRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  label: { color: C.ink, fontSize: 14, flex: 1 },
  labelOn: { color: C.teal },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'center' },
  chip: { borderWidth: 1, borderColor: C.line, backgroundColor: C.bg, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7 },
  chipOn: { borderColor: C.teal },
  chipText: { color: C.muted, fontSize: 13 },
  chipTextOn: { color: C.teal },
  input: { color: C.ink, backgroundColor: C.bg, borderWidth: 1, borderColor: C.line, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 9, fontSize: 14 },
  short: { minWidth: 90 },
  long: { minHeight: 56 },
  inputOn: { borderColor: C.teal },
  hint: { color: C.muted, fontSize: 12, lineHeight: 17 },
});
