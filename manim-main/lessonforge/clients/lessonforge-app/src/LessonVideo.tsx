// The lesson player as every screen shows it: the video with its questions, its watch
// modes and its chapters, and the two things a viewer must know before trusting it.
// A question is drawn over the video, inside the video's own box.
// The captions are a line of the page directly under the video (web): a lesson's frame keeps
// no band for them, so nothing is drawn on the picture, and here they are large enough to read.
import { forwardRef, ReactNode, useImperativeHandle, useRef, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { Job, mediaUrl, track, Viewing } from './api';
import { CAPTION_CHARS, CAPTION_FONT, CAPTION_LINE, captionRoom } from './captions';
import { CutEnd, CutPicker, depthTag, useCuts } from './Cuts';
import { clock } from './format';
import { Player, PlayerHandle } from './Player';
import { QuestionBar, QuestionOverlay, useQuestions } from './Questions';
import { C } from './theme';

export type LessonHandle = {
  // Jump there and play.
  seek: (seconds: number) => void;
  // Where the video is now, in seconds.
  time: () => number;
  // What has been watched since this player appeared.
  viewing: () => Viewing;
};
type Props = {
  job: Job;
  server: string;
  // false: no watch modes, the full lesson only.
  modes?: boolean;
  // Drawn directly under the video, above the chapters.
  children?: ReactNode;
};

// Whether this viewer wants captions, kept in the browser. Storage may be missing or
// refuse (a private window): captions are then on, and the choice lasts for the page.
const CAPTIONS_KEY = 'lessonforge.captions';

function captionsWanted(): boolean {
  try {
    return typeof localStorage === 'undefined' || localStorage.getItem(CAPTIONS_KEY) !== 'off';
  } catch {
    return true;
  }
}

function keepCaptionsChoice(on: boolean): void {
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(CAPTIONS_KEY, on ? 'on' : 'off');
  } catch {
    // Not remembered; nothing else depends on it.
  }
}

// Time that passes in steps longer than this was not watched: the reports had stopped.
// The language a lesson narrated by the learner's own device is read in (voice `browser:<language>`), else null.
function deviceVoice(voice: string | null | undefined): string | null {
  return voice && voice.startsWith('browser') ? voice.split(':')[1] || 'en-IN' : null;
}

const STEP_S = 3;
// Within this of the end, the lesson counts as watched to the end.
const END_S = 5;
// Shares of the version being watched that are reported to the dashboard as they are
// reached by playing. The last is short of 1: a question's own thinking pause is skipped,
// not played, so a lesson watched in full never quite adds up to its length.
const MARKS: [share: number, reported: number][] = [
  [0.25, 25],
  [0.5, 50],
  [0.75, 75],
  [0.88, 100],
];

export const LessonVideo = forwardRef<LessonHandle, Props>(function LessonVideo({ job, server, modes = true, children }, ref) {
  const player = useRef<PlayerHandle>(null);
  const cuts = useCuts(server, job, player, modes);
  const questions = useQuestions(server, job.interactions_url, player, cuts.ranges, cuts.keeps);
  const chapters = job.chapters ?? [];
  const length = cuts.total || job.checks?.duration_seconds || 0;
  const watch = useRef({ at: 0, played: 0, completed: false });
  // What the dashboard has been told about this viewing: that it began, and how far it got.
  const told = useRef({ play: false, marks: 0 });
  const mode = cuts.current?.id ?? 'full';
  const version = cuts.current?.seconds || length;
  // The words being spoken, from the player ('' between sentences). Only the web player
  // reports them; the native one draws the file's own subtitles.
  const [caption, setCaption] = useState('');
  const [captionsOn, setCaptionsOn] = useState(captionsWanted);
  // How much the line has room for: a caption is cut to fit it, so the line never grows.
  const [room, setRoom] = useState({ most: CAPTION_CHARS, lines: 2 });
  const ownCaptions = Platform.OS === 'web' && !!job.captions_url;
  const toggleCaptions = () => {
    keepCaptionsChoice(!captionsOn);
    setCaptionsOn(!captionsOn);
  };

  const onTime = (now: number, seeked: boolean, duration: number) => {
    const seen = watch.current;
    const step = now - seen.at;
    // Played time only: a seek moves the position without anything being watched.
    if (!seeked && step > 0 && step < STEP_S) {
      seen.played += step;
      const sent = told.current;
      if (!sent.play) {
        sent.play = true;
        track(server, 'play', { job_id: job.job_id, value: mode });
      }
      const whole = version || duration;
      while (whole > 0 && sent.marks < MARKS.length && seen.played >= MARKS[sent.marks][0] * whole) {
        track(server, 'progress', { job_id: job.job_id, value: MARKS[sent.marks][1] });
        sent.marks += 1;
      }
    }
    seen.at = now;
    const end = duration || length;
    if (end > 0 && now >= end - END_S) seen.completed = true;
    // A question, when one is up, holds the video; otherwise the watch mode may move it on.
    cuts.onTime(now, questions.onTime(now, seeked));
  };

  useImperativeHandle(ref, () => ({
    seek: questions.jump,
    time: () => watch.current.at,
    viewing: () => ({
      watch_mode: mode,
      seconds_watched: Math.round(watch.current.played),
      completed: watch.current.completed,
      quiz: questions.tally(),
    }),
  }));

  return (
    <>
      {job.video_url ? (
        <View style={styles.stage}>
          <View style={styles.videoBox}>
            <Player
              key={job.video_url}
              ref={player}
              uri={mediaUrl(server, job.video_url)}
              captionsUri={job.captions_url ? mediaUrl(server, job.captions_url) : null}
              captions={captionsOn}
              captionChars={room.most}
              onCaption={setCaption}
              onTime={onTime}
              locked={questions.asking !== null}
              speak={deviceVoice(job.voice)}
            />
            <CutEnd cuts={cuts} />
            <QuestionOverlay questions={questions} />
          </View>
          {ownCaptions ? (
            <View style={[styles.captions, !captionsOn && styles.captionsOff]}>
              {captionsOn ? (
                <Text
                  aria-live="off"
                  onLayout={(event) => {
                    const next = captionRoom(event.nativeEvent.layout.width);
                    if (next.most !== room.most || next.lines !== room.lines) setRoom(next);
                  }}
                  style={[styles.captionText, { minHeight: room.lines * CAPTION_LINE }]}>
                  {caption}
                </Text>
              ) : null}
              <Pressable
                aria-label={captionsOn ? 'Turn captions off' : 'Turn captions on'}
                aria-pressed={captionsOn}
                onPress={toggleCaptions}
                style={[styles.captionSwitch, captionsOn && styles.captionSwitchOn]}>
                <Text style={[styles.captionSwitchText, captionsOn && styles.captionSwitchTextOn]}>
                  {captionsOn ? 'CC' : 'Captions off'}
                </Text>
              </Pressable>
            </View>
          ) : null}
        </View>
      ) : (
        <Text style={styles.warn}>The server marked this job done but returned no video.</Text>
      )}
      {children}
      <CutPicker cuts={cuts} />
      <View style={styles.chips}>
        {chapters.map((chapter, index) => {
          // A chapter runs to the next one's start; one the selected cut keeps nothing of
          // is still offered, as the way back to the full lesson at that point.
          const skipped = cuts.skips(chapter.start, chapters[index + 1]?.start ?? (length || Infinity));
          const depth = depthTag(chapter.depths);
          return (
            <Pressable
              key={chapter.id}
              aria-label={skipped ? `${chapter.title}, skipped in this version: watch it in the full lesson` : undefined}
              onPress={() => {
                if (skipped) cuts.showFull();
                questions.jump(chapter.start);
              }}
              style={[styles.chip, skipped && styles.chipSkipped]}>
              <Text style={styles.chipText}>
                <Text style={styles.time}>{clock(chapter.start)} </Text>
                {chapter.title}
                {depth ? <Text style={styles.chipTag}>{`  ${depth}`}</Text> : null}
                {skipped ? <Text style={styles.chipTag}>{'  · skipped'}</Text> : null}
              </Text>
            </Pressable>
          );
        })}
      </View>
      <QuestionBar questions={questions} />
      {job.voice === 'silent' ? (
        <Text style={styles.warn}>
          {job.voice_note === 'budget'
            ? 'This video is silent, with captions: the spending limit was reached before its narration could be made. Its script and pictures are kept, so the voice can be added without making it again.'
            : job.voice_note === 'unavailable'
              ? 'This video is silent, with captions: the narration voices did not answer when it was made. Its script and pictures are kept, so the voice can be added without making it again.'
              : 'No voice is configured on the server, so this video is silent with captions.'}
        </Text>
      ) : null}
      {job.voice?.startsWith('gtts') ? (
        <Text style={styles.warn}>
          The main narration voice was not available when this was made (usually the spending limit or the account&apos;s
          credit had run out), so it uses a basic voice. Its script and pictures are kept, so the proper voice can be added
          without making it again.
        </Text>
      ) : null}
      {job.generated_by && job.generated_by !== 'model' && job.generated_by !== 'script' ? (
        <Text style={styles.warn}>
          {job.generated_by.startsWith('written by hand')
            ? 'This lesson was written out by hand as a demonstration: no model wrote or reviewed its script.'
            : job.generated_by.startsWith('script')
              ? 'No language model is configured on the server: your script is narrated over plain text, without a designed picture.'
              : 'No language model is configured on the server: this is a placeholder outline, not a written lesson.'}
        </Text>
      ) : null}
    </>
  );
});

const styles = StyleSheet.create({
  stage: { width: '100%', gap: 6 },
  videoBox: { width: '100%', borderRadius: 12, overflow: 'hidden', backgroundColor: '#000' },
  // The words' own box keeps its height whether or not anything is being said (the Text's
  // minHeight, set where it is drawn), so the page under it does not move.
  captions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: C.panel,
    borderWidth: 1,
    borderColor: C.line,
    borderRadius: 12,
    paddingVertical: 8,
    paddingLeft: 14,
    paddingRight: 8,
  },
  captionsOff: { justifyContent: 'flex-end', backgroundColor: 'transparent', borderWidth: 0, paddingVertical: 0 },
  captionText: { flex: 1, minWidth: 0, color: C.ink, fontSize: CAPTION_FONT, lineHeight: CAPTION_LINE, textAlign: 'center' },
  captionSwitch: { borderWidth: 1, borderColor: C.line, borderRadius: 8, paddingHorizontal: 9, paddingVertical: 6 },
  captionSwitchOn: { borderColor: C.teal },
  captionSwitchText: { color: C.muted, fontSize: 12, fontWeight: '700', letterSpacing: 0.4 },
  captionSwitchTextOn: { color: C.teal },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: 1, borderColor: C.line, backgroundColor: C.panel, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 9 },
  chipSkipped: { opacity: 0.5, borderStyle: 'dashed' },
  chipTag: { fontSize: 11, letterSpacing: 0.4, textTransform: 'uppercase' },
  chipText: { color: C.muted, fontSize: 14 },
  time: { color: C.teal, fontVariant: ['tabular-nums'] },
  warn: { color: C.gold, fontSize: 14, lineHeight: 20 },
});
