// The voice a lesson is narrated in. The server says what it has (GET /voices), grouped (its owner's own voice
// service, Microsoft's online voices, the voice on the server's machine, the learner's own device, the paid ones),
// with what each costs; given the lesson's language, only the voices that can speak it. Nothing picked means the
// server's usual voice. Renders nothing when the server offers no choice (an older server, or one voice only).
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { api, VoiceList, VoiceRow } from './api';
import { C } from './theme';

function groups(voices: VoiceRow[]): [string, VoiceRow[]][] {
  const out = new Map<string, VoiceRow[]>();
  for (const voice of voices) {
    const name = voice.group ?? (voice.paid ? 'Paid' : 'Voices');
    out.set(name, [...(out.get(name) ?? []), voice]);
  }
  return [...out.entries()];
}

function costLine(voice: VoiceRow | undefined, list: VoiceList): string {
  if (!voice) return "The server's usual voice.";
  const own = voice.cost ?? (voice.paid ? 'A paid voice: charged to the model account for every lesson made with it.' : 'No charge per lesson.');
  const timing = list.timing && voice.kind !== 'browser' ? ` ${list.timing.text}` : '';
  return own + timing;
}

export function VoicePick({
  server,
  value,
  onChange,
  language,
}: {
  server: string;
  value: string | null;
  onChange: (voice: string | null) => void;
  language?: string | null;
}) {
  const [list, setList] = useState<VoiceList | null>(null);
  useEffect(() => {
    const request = new AbortController();
    api
      .voices(server, request.signal, language)
      .then(setList)
      .catch(() => setList(null));
    return () => request.abort();
  }, [server, language]);
  if (!list || list.voices.length < 2) return null;
  const chosen = value ?? list.default;
  const voice = list.voices.find((row) => row.id === chosen);
  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>Voice</Text>
      {groups(list.voices).map(([name, rows]) => (
        <View key={name} style={styles.group}>
          <Text style={styles.groupName}>{name}</Text>
          <View style={styles.chips}>
            {rows.map((row) => {
              const on = row.id === chosen;
              return (
                <Pressable
                  key={row.id}
                  aria-label={`${row.label}${row.paid ? ', paid voice' : ''}`}
                  onPress={() => onChange(row.id === list.default ? null : row.id)}
                  style={[styles.chip, on && styles.chipOn]}>
                  <Text style={[styles.chipText, on && styles.chipTextOn]}>
                    {row.label}
                    {row.paid ? <Text style={styles.paid}>{'  paid'}</Text> : null}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      ))}
      <Text style={styles.finePrint}>{costLine(voice, list)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 8 },
  title: { color: C.ink, fontSize: 19, fontWeight: '600', marginTop: 6 },
  group: { gap: 6 },
  groupName: { color: C.muted, fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: 1, borderColor: C.line, backgroundColor: C.panel, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 9 },
  chipOn: { borderColor: C.teal },
  chipText: { color: C.muted, fontSize: 14 },
  chipTextOn: { color: C.teal },
  paid: { color: C.gold, fontSize: 12 },
  finePrint: { color: C.muted, fontSize: 12, lineHeight: 18 },
});
