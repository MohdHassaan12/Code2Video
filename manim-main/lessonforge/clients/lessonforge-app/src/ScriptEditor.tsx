// The person in the loop: a lesson's script, beat by beat, to read and change (server: harness/edit.py).
//
// Each beat shows what is said, what the screen shows, and what the review noted. The person can change the words,
// say what the screen should show instead (a model designs that beat's screen again; it cannot touch a word), or
// take the beat out. "Make the video" starts a NEW lesson with the changes; the one shown here stays as it is.
// "Save and check again" makes the new script only, to read it once more before anything else is paid for.
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { api, BeatEdit, Job, ScriptBeat, ScriptView } from './api';
import { VoicePick } from './VoicePick';
import { C } from './theme';

type Draft = Record<string, BeatEdit>;

export function ScriptEditor({
  server,
  job,
  voice,
  onStarted,
  waiting,
}: {
  server: string;
  job: Job;
  voice?: string | null;
  onStarted: (next: Job) => void;
  // The lesson stopped after its script for this person to check: the editor is open and says so.
  waiting?: boolean;
}) {
  const [view, setView] = useState<ScriptView | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [open, setOpen] = useState(!!waiting);
  const [chosenVoice, setChosenVoice] = useState<string | null>(voice ?? null);
  const [draft, setDraft] = useState<Draft>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || view) return;
    const request = new AbortController();
    api
      .scriptOf(server, job.job_id, request.signal)
      .then(setView)
      .catch((e: unknown) => {
        if (!request.signal.aborted) setFailed(e instanceof Error ? e.message : String(e));
      });
    return () => request.abort();
  }, [server, job.job_id, open, view]);

  const changed = useMemo(() => Object.entries(draft).filter(([, e]) => e.remove || e.note?.trim() || e.narration !== undefined), [draft]);

  const set = (id: string, patch: BeatEdit) => setDraft((d) => ({ ...d, [id]: { ...d[id], ...patch } }));

  const start = async (film: boolean) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const edits: Record<string, BeatEdit> = {};
      for (const [id, e] of changed) {
        edits[id] = e.remove ? { remove: true } : { ...(e.narration !== undefined ? { narration: e.narration } : {}), ...(e.note?.trim() ? { note: e.note.trim() } : {}) };
      }
      onStarted(await api.editLesson(server, job.job_id, edits, film, chosenVoice));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Edit this video</Text>
        <Text style={styles.muted}>
          Change what a part says, ask for a different picture on it, or take it out. The changes are made into a new video;
          this one stays as it is.
        </Text>
        <Pressable onPress={() => setOpen(true)} style={({ pressed }) => [styles.secondary, pressed && styles.pressed]}>
          <Text style={styles.secondaryText}>Open the script</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.card}>
      <Text style={styles.title}>{waiting ? 'Check the script before it is filmed' : 'Edit this video'}</Text>
      <Text style={styles.muted}>
        {waiting
          ? 'The script is written and reviewed. Nothing has been narrated or filmed yet. Change anything below, then make the video.'
          : 'Change what a part says, ask for a different picture on it, or take it out. A new video is made; this one stays as it is.'}
      </Text>
      {failed ? <Text style={styles.warn}>The script could not be loaded: {failed}</Text> : null}
      {!view && !failed ? <ActivityIndicator color={C.teal} size="small" /> : null}
      {view ? (
        <Text style={styles.muted}>
          {view.beats} parts, {view.words} words.{changed.length > 0 ? ` ${changed.length} changed.` : ''}
        </Text>
      ) : null}
      {view?.chapters.map((chapter) => (
        <View key={chapter.id} style={styles.chapter}>
          <Text style={styles.chapterTitle}>{chapter.title}</Text>
          {chapter.beats.map((beat) => (
            <BeatCard key={beat.id} beat={beat} edit={draft[beat.id]} onChange={(patch) => set(beat.id, patch)} disabled={busy} />
          ))}
        </View>
      ))}
      {view ? (
        <>
          <VoicePick server={server} value={chosenVoice} onChange={setChosenVoice} language={job.brief?.language} />
          <View style={styles.actions}>
            <Pressable disabled={busy} onPress={() => start(true)} style={({ pressed }) => [styles.primary, (pressed || busy) && styles.pressed]}>
              <Text style={styles.primaryText}>{busy ? 'Starting…' : changed.length > 0 ? 'Make the video with these changes' : 'Looks good: make the video'}</Text>
            </Pressable>
          {changed.length > 0 ? (
            <Pressable disabled={busy} onPress={() => start(false)} style={({ pressed }) => [styles.secondary, (pressed || busy) && styles.pressed]}>
              <Text style={styles.secondaryText}>Save the changes and check the script again</Text>
            </Pressable>
          ) : null}
            {changed.length > 0 ? (
              <Pressable disabled={busy} onPress={() => setDraft({})} style={styles.ghost}>
                <Text style={styles.ghostText}>Undo all changes</Text>
              </Pressable>
            ) : null}
          </View>
        </>
      ) : null}
      {error ? <Text style={styles.warn}>{error}</Text> : null}
    </View>
  );
}

function BeatCard({ beat, edit, onChange, disabled }: { beat: ScriptBeat; edit?: BeatEdit; onChange: (patch: BeatEdit) => void; disabled?: boolean }) {
  const removed = !!edit?.remove;
  const words = edit?.narration ?? beat.narration;
  const [noting, setNoting] = useState(!!edit?.note);
  return (
    <View style={[styles.beat, removed && styles.removed, (edit?.narration !== undefined || edit?.note) && styles.changed]}>
      <View style={styles.beatHead}>
        <Text style={styles.beatId}>Part {beat.id}</Text>
        <Pressable disabled={disabled} onPress={() => onChange({ remove: !removed })} style={styles.ghost}>
          <Text style={styles.ghostText}>{removed ? 'Keep it' : 'Remove'}</Text>
        </Pressable>
      </View>
      {removed ? (
        <Text style={styles.muted}>This part will be taken out.</Text>
      ) : (
        <>
          <Text style={styles.label}>What is said</Text>
          <TextInput
            editable={!disabled}
            multiline
            value={words}
            onChangeText={(text) => onChange({ narration: text === beat.narration ? undefined : text })}
            style={styles.input}
          />
          <Text style={styles.label}>On screen</Text>
          <Text style={styles.muted}>
            {beat.figure ? `${beat.figure}. ` : ''}
            {beat.visual || (beat.shows.length > 0 ? beat.shows.join(' · ') : 'words only')}
          </Text>
          {beat.quiz ? <Text style={styles.muted}>Question: {beat.quiz}</Text> : null}
          {beat.findings.map((f, i) => (
            <Text key={i} style={styles.finding}>
              Review: {f}
            </Text>
          ))}
          {noting ? (
            <TextInput
              editable={!disabled}
              multiline
              placeholder="What should the screen show here instead? e.g. a number line from 0 to 10, with 7 lit up"
              placeholderTextColor={C.muted}
              value={edit?.note ?? ''}
              onChangeText={(text) => onChange({ note: text })}
              style={styles.input}
            />
          ) : (
            <Pressable disabled={disabled} onPress={() => setNoting(true)} style={styles.ghost}>
              <Text style={styles.ghostText}>Change the picture</Text>
            </Pressable>
          )}
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: C.panel, borderColor: C.line, borderWidth: 1, borderRadius: 14, padding: 14, gap: 10 },
  title: { color: C.ink, fontSize: 17, fontWeight: '700' },
  muted: { color: C.muted, fontSize: 14, lineHeight: 20 },
  warn: { color: C.gold, fontSize: 14 },
  finding: { color: C.gold, fontSize: 13, lineHeight: 18 },
  chapter: { gap: 8, marginTop: 6 },
  chapterTitle: { color: C.teal, fontSize: 13, fontWeight: '700', letterSpacing: 1 },
  beat: { borderColor: C.line, borderWidth: 1, borderRadius: 12, padding: 10, gap: 6 },
  changed: { borderColor: C.teal },
  removed: { opacity: 0.55 },
  beatHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  beatId: { color: C.ink, fontSize: 14, fontWeight: '600' },
  label: { color: C.muted, fontSize: 12, fontWeight: '600', textTransform: 'uppercase' },
  input: { color: C.ink, backgroundColor: C.bg, borderColor: C.line, borderWidth: 1, borderRadius: 10, padding: 10, fontSize: 15, minHeight: 64, textAlignVertical: 'top' },
  actions: { gap: 8, marginTop: 6 },
  primary: { backgroundColor: C.teal, borderRadius: 12, paddingVertical: 14, alignItems: 'center' },
  primaryText: { color: C.bg, fontSize: 16, fontWeight: '700' },
  secondary: { borderColor: C.teal, borderWidth: 1, borderRadius: 12, paddingVertical: 12, alignItems: 'center' },
  secondaryText: { color: C.teal, fontSize: 15, fontWeight: '600' },
  ghost: { paddingVertical: 6 },
  ghostText: { color: C.teal, fontSize: 14 },
  pressed: { opacity: 0.7 },
});
