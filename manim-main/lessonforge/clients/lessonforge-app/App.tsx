// lessonforge — ask before generating. One codebase for web, iOS and Android.
//
//   ask      a Socratic intake: one question at a time, each with its reason; the
//            start of it also lists recent videos, so nothing made is ever lost
//   script   the other way to start: paste the words to be narrated (src/Script.tsx);
//            the video is made from them instead of from answers
//   confirm  the brief, or the pasted script as the server read it, before anything is spent
//   making   script → verify → speech → render → assemble → check (→ repair) → review,
//            polled from the server; the step list comes from the job itself
//   watch    the video with chapters, its questions (the player stops for each one) and
//            its watch modes (full, or a shorter cut that skips), the task to try by hand
//            afterwards and what the lesson stands on (src/TryIt.tsx), plus what was
//            measured and what was not
//   failed   what went wrong, a retry, and the video if one was built before the failure
//
// The last three are one job seen at different moments, so the screen is derived from
// the job's status. The job id is remembered (api.rememberJob), so a reload reopens it.
//
// On a viewer site (the finished lessons on Render, `GET /mode` → "viewer") nothing is made: the app opens
// on the list of lessons, and every way to make or change one (the questions, a pasted script, "Add the
// voice", "Finish this lesson", "Try again", remove, saving a cut) is left out. Watching is the same.
//
// Three more, beside that flow:
//   feedback  "Tell us how it went", for the people who make lessons (src/Feedback.tsx)
//   dashboard who opened the app, what they made and watched, what it cost: for the
//             owner, opened from `#dashboard` (src/Dashboard.tsx)
//   review    a student's review of one lesson, opened from a review link; it replaces
//             the whole app, because that link may do nothing else (src/Review.tsx)
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';

import {
  Alignment,
  api,
  Brief,
  Continuity,
  dashboardLinked,
  defaultServer,
  Finding,
  getToken,
  Job,
  JobStatus,
  JobSummary,
  knowsDashboard,
  rememberedJob,
  rememberJob,
  reviewJob,
  ScriptPlan,
  ServerMode,
  serverMode,
  Session,
  Settings,
  setToken,
  showDashboard,
  statusOf,
  track,
  Verification,
  VisionKind,
  VisionReview,
} from './src/api';
import { Dashboard } from './src/Dashboard';
import { FeedbackEntry, TesterFeedback } from './src/Feedback';
import { ago, clock, say } from './src/format';
import { LessonHandle, LessonVideo } from './src/LessonVideo';
import { ReviewScreen } from './src/Review';
import { ModeSwitch, ScriptEdit, ScriptForm, ScriptPlanCard } from './src/Script';
import { ScriptEditor } from './src/ScriptEditor';
import { StudentReviews } from './src/StudentReviews';
import { TeachingCard, TryIt } from './src/TryIt';
import { BriefEdit } from './src/BriefEdit';
import { Controls } from './src/Controls';
import { VoicePick } from './src/VoicePick';
import { C } from './src/theme';

// A brief's language as the voice list is asked for it (none when it is not a string).
const asLanguage = (value: unknown): string | null => (typeof value === 'string' && value ? value : null);

// `note`: something the assistant decided on its own. `notice`: something that happened
// to the conversation (the server lost it).
type Turn = { from: 'harness' | 'you'; text: string; why?: string; tone?: 'note' | 'notice' };
type Stage = 'ask' | 'script' | 'confirm' | 'job';
type Screen = 'ask' | 'script' | 'confirm' | 'making' | 'watch' | 'failed';
// Why the last status read failed, while the making screen keeps trying.
type Link = { tries: number; status: number | null; message: string };
// `at` is the clock when the list arrived (unix seconds), so ages are not read in render.
type RecentList = { jobs: JobSummary[]; at: number };

const QUALITIES = [
  { value: 'l', label: 'Draft · 480p', hint: 'fastest' },
  { value: 'm', label: 'Standard · 720p', hint: '' },
  { value: 'h', label: 'Full · 1080p', hint: 'slowest' },
  { value: 'p', label: '1440p', hint: 'very slow' },
  { value: 'k', label: '4K · 2160p', hint: 'very slow' },
];
const OPENING: Turn = {
  from: 'harness',
  text: 'What should this video teach?',
  why: 'Say it the way you would to a colleague — the class, language or length can go here too.',
};
const RECENT_SHOWN = 8;
const POLL_MS = 2000;
const POLL_MAX_MS = 10000;
// Labels for stages the server is known to report; an unknown stage shows its raw name.
const STAGE_LABELS: Record<string, string> = {
  queued: 'Waiting for a worker',
  // Only when the lesson is planned from sources first (a teaching card): the textbook chapter, lectures, lesson plans.
  research: 'Reading how this topic is taught',
  script: 'Writing the script',
  verify: 'Checking the script',
  visuals: 'Drawing the animations',
  // A preview of every screen as stills, before the narration is made: the layout is tried and looked at.
  compose: 'Trying the layout',
  speech: 'Recording narration',
  render: 'Animating chapters',
  assemble: 'Joining chapters',
  check: 'Checking the result',
  repair: 'Fixing layout',
  review: 'Reviewing the frames',
  done: 'Finishing up',
};
// A video made from a pasted script: nothing is written, the picture is planned for the words.
const SCRIPT_STAGE_LABELS: Record<string, string> = {
  script: 'Planning the picture for your script',
  verify: 'Checking your script',
};

function fromScript(job: Job | null): boolean {
  return job?.brief?.mode === 'script';
}

function stageLabel(job: Job | null, stage: string): string {
  return (fromScript(job) ? SCRIPT_STAGE_LABELS[stage] : undefined) ?? STAGE_LABELS[stage] ?? stage;
}

const SCORE_LABELS: { key: keyof NonNullable<Verification['scores']>; label: string }[] = [
  { key: 'conceptual_accuracy', label: 'Accuracy' },
  { key: 'visual_truthfulness', label: 'Visual truth' },
  { key: 'explanatory_clarity', label: 'Clarity' },
  { key: 'pedagogy', label: 'Pedagogy' },
];
const VISION_KINDS: VisionKind[] = ['overlap', 'clipped', 'unreadable', 'stale', 'mismatch', 'empty', 'other'];

// What the requester asked the lesson to build on: each link by itself, the rest as one note.
function sourcesGiven(text: string): { sources?: string[] } {
  const links = text.split(/\s+/).filter((word) => /^https?:\/\//.test(word));
  const notes = text.replace(/https?:\/\/\S+/g, ' ').replace(/\s+/g, ' ').trim();
  const sources = [...links, ...(notes ? [notes] : [])];
  return sources.length > 0 ? { sources } : {};
}

function isQuality(value: unknown): value is string {
  return QUALITIES.some((q) => q.value === value);
}

// The server logs "— repair —" when it enters the optional repair stage; a 2 s poll
// can miss the stage itself, so the log is the second witness.
function repairLogged(job: Job): boolean {
  return job.stage === 'repair' || job.progress.some((line) => line.trim() === '— repair —');
}

// Steps to draw: the job's own stage list (minus the terminal "done"), with "repair"
// slipped in after "check" once the server has entered it.
function trackerSteps(job: Job, withRepair: boolean): string[] {
  const steps = job.stages.filter((s) => s !== 'done');
  if (withRepair && !steps.includes('repair')) {
    const after = steps.indexOf('check');
    steps.splice(after < 0 ? steps.length : after + 1, 0, 'repair');
  }
  return steps;
}

export default function App() {
  // Read once on load: a student's review link opens that review and nothing else.
  const [review] = useState(reviewJob);
  const [server] = useState(defaultServer);
  return review ? <ReviewScreen server={server} jobId={review} /> : <Studio />;
}

function Studio() {
  const [server, setServer] = useState(defaultServer());
  const [token, setTokenState] = useState(getToken());
  const [editingServer, setEditingServer] = useState(false);
  // Read once on load: the job this browser was last making or watching, if any.
  const [resumed] = useState(rememberedJob);
  const [stage, setStage] = useState<Stage>(resumed ? 'job' : 'ask');
  const [session, setSession] = useState<Session | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quality, setQuality] = useState(isQuality(resumed?.quality) ? resumed.quality : 'm');
  // The voice picked for the next lesson; null is the server's usual one (its owner's own voice when it has one).
  const [voicePick, setVoicePick] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(resumed?.id ?? null);
  const [job, setJob] = useState<Job | null>(null);
  const [sawRepair, setSawRepair] = useState(false);
  const [link, setLink] = useState<Link | null>(null);
  const [recent, setRecent] = useState<RecentList | null>(null);
  const [recentFailed, setRecentFailed] = useState(false);
  // What this server is: null until it has said. Making a lesson is offered only once it says "studio",
  // so a viewer site never shows, even for a moment, a way in that it would refuse.
  const [mode, setMode] = useState<ServerMode | null>(null);
  const canMake = mode === 'studio';
  // The tester feedback form, when open, with the lesson it was opened from (if any).
  const [feedback, setFeedback] = useState<{ lesson: { id: string; title: string } | null } | null>(null);
  // The owner's dashboard covers the app while it is open. Testers share the owner's link,
  // so the way in is shown only in a browser that has already opened it (from `#dashboard`).
  const [dashboard, setDashboard] = useState(dashboardLinked);
  const [dashboardKnown, setDashboardKnown] = useState(knowsDashboard);
  // The other way to start: the words themselves. `plan` is the server's read-back of them.
  const [script, setScript] = useState('');
  const [audience, setAudience] = useState('');
  const [plan, setPlan] = useState<ScriptPlan | null>(null);
  // The narration language the requester chose; until they do, the one read from the script.
  const [languagePick, setLanguagePick] = useState<string | null>(null);
  const [scriptEdit, setScriptEdit] = useState<ScriptEdit>('keep');
  // Stop once the script is written and reviewed, so the person reads and edits it before it is narrated and filmed.
  const [checkFirst, setCheckFirst] = useState(false);
  // For a lesson made from the questions: read how the topic is taught first (textbook chapter, lectures,
  // lesson plans) and plan from that, with anything the requester wants built on.
  // Planned from sources first unless the requester chooses otherwise (the owner, 2026-10-10).
  const [fromSources, setFromSources] = useState(true);
  const [ownSources, setOwnSources] = useState('');
  // What the requester changed in the brief the intake wrote (BriefEdit), and this lesson's own values for
  // the pipeline's switches (Controls); both empty unless they opened those panels.
  const [briefEdits, setBriefEdits] = useState<Brief>({});
  const [settings, setSettings] = useState<Settings>({});
  const lesson = useRef<LessonHandle>(null);
  const scroll = useRef<ScrollView>(null);
  // `busy` only disables inputs on the NEXT render; this stops a second tap in the same one.
  const inFlight = useRef(false);
  // Bumped whenever the user leaves for another screen, so a reply still on its way is dropped.
  const epoch = useRef(0);
  // What the user first asked for: the opening of a replacement session if the server loses this one.
  const opener = useRef('');

  const question = session?.question ?? null;
  const options = question?.options ?? [];
  // A choice question with nothing to tap would be a dead end, so it falls back to typing.
  const asksChoice = question?.kind === 'choice' && options.length > 0;
  const opened = job !== null;
  const screen: Screen =
    stage !== 'job' ? stage : !job ? 'making' : job.status === 'done' ? 'watch' : job.status === 'failed' ? 'failed' : 'making';
  // Status is read only while there is something left to learn; done and failed are final.
  // (Anything else, even a status this client has never heard of, keeps the loop going.)
  const live = stage === 'job' && jobId !== null && (!job || (job.status !== 'done' && job.status !== 'failed'));
  const atStart = stage === 'ask' && !session && turns.length === 0;
  // What is on screen: the dashboard and the feedback form cover whichever screen they were opened from.
  const view: Screen | 'feedback' | 'dashboard' = dashboard ? 'dashboard' : feedback ? 'feedback' : screen;

  const reset = useCallback((message: string | null = null) => {
    epoch.current += 1;
    inFlight.current = false;
    opener.current = '';
    rememberJob(null);
    setBusy(false);
    setSession(null);
    setTurns([]);
    setDraft('');
    setJob(null);
    setJobId(null);
    setSawRepair(false);
    setLink(null);
    setFeedback(null);
    setScript('');
    setAudience('');
    setPlan(null);
    setLanguagePick(null);
    setScriptEdit('keep');
    setFromSources(true);
    setOwnSources('');
    setError(message);
    setStage('ask');
  }, []);

  // Runs one request at a time. `alive()` turns false once the user has moved on.
  const run = useCallback(async (work: (alive: () => boolean) => Promise<void>) => {
    if (inFlight.current) return;
    inFlight.current = true;
    const mine = epoch.current;
    const alive = () => epoch.current === mine;
    setBusy(true);
    setError(null);
    try {
      await work(alive);
    } catch (e) {
      if (alive()) setError(say(e));
    } finally {
      if (alive()) {
        inFlight.current = false;
        setBusy(false);
      }
    }
  }, []);

  const absorb = (next: Session, notice?: string) => {
    setSession(next);
    setTurns((old) => [
      ...old,
      ...(notice ? [{ from: 'harness' as const, tone: 'notice' as const, text: notice }] : []),
      // With no next question the note is read back on the confirm screen instead.
      ...(next.note && next.question ? [{ from: 'harness' as const, tone: 'note' as const, text: next.note }] : []),
      ...(next.question ? [{ from: 'harness' as const, text: next.question.prompt, why: next.question.why }] : []),
    ]);
    if (!next.question) setStage('confirm');
  };

  // `shown` is what the bubble says for a tapped option; a typed answer shows itself.
  const send = (value: string | number, shown?: string) =>
    run(async (alive) => {
      if (session && !question) return;
      const typed = shown === undefined;
      const mine: Turn = { from: 'you', text: shown ?? String(value) };
      setTurns((old) => [...old, mine]);
      if (typed) setDraft('');
      try {
        let next: Session;
        let notice: string | undefined;
        let asked = question?.id;
        if (!session || !question) {
          next = await api.start(server, String(value));
          if (alive()) opener.current = String(value);
          asked = undefined;
        } else {
          try {
            next = await api.answer(server, session.session_id, question.id, value);
          } catch (e) {
            // The server restarted and no longer has this conversation: begin another from
            // the topic. (A later answer sent as the opening would BECOME the topic.)
            if (statusOf(e) !== 404) throw e;
            next = await api.start(server, opener.current || undefined);
            notice = opener.current
              ? 'The server restarted and lost our conversation, so I started again from your topic. A few questions may repeat.'
              : 'The server restarted and lost our conversation, so we are starting again.';
          }
        }
        if (!alive()) return;
        absorb(next, notice);
        // The answer that was lost goes back in the box when the same question returns.
        if (notice && typed && asked && next.question?.id === asked) setDraft(String(value));
      } catch (e) {
        if (alive()) {
          // Not recorded: take the bubble back and return the words to the composer.
          setTurns((old) => old.filter((turn) => turn !== mine));
          if (typed) setDraft(String(value));
        }
        throw e;
      }
    });

  const submitDraft = () => {
    const text = draft.trim();
    if (text) send(text);
  };

  // A job this client just started.
  const adopt = (next: Job, madeAt: string) => {
    rememberJob({ id: next.job_id, quality: madeAt });
    setSawRepair(false);
    setLink(null);
    setJob(next);
    setJobId(next.job_id);
    setStage('job');
  };

  const scriptLanguage = languagePick ?? plan?.language ?? 'en-IN';

  // The pasted script, read back by the server: no model is called, nothing is spent.
  const checkScript = () =>
    run(async (alive) => {
      const next = await api.scriptPreview(server, script, languagePick ?? undefined);
      if (!alive()) return;
      setPlan(next);
      setStage('confirm');
    });

  const generate = () =>
    run(async (alive) => {
      // From a pasted script the brief IS the script; from the questions it is what they filled in.
      const brief = plan
        ? { mode: 'script', script, language: scriptLanguage, script_edit: scriptEdit, ...(audience.trim() ? { audience: audience.trim() } : {}) }
        : session
          ? { ...session.brief, ...(fromSources ? { card: true, ...sourcesGiven(ownSources) } : {}), ...briefEdits }
          : null;
      if (!brief) return;
      const asked = { ...brief, ...(voicePick ? { voice_choice: voicePick } : {}), ...(checkFirst ? { stop_after: 'verify' } : {}) };
      const next = await api.generate(server, asked, quality, settings);
      if (alive()) adopt(next, quality);
    });

  // Back to the words of a video that was made from a script: change them and make it again.
  const editScript = (from: Job) => {
    const brief = from.brief ?? {};
    reset();
    setScript(typeof brief.script === 'string' ? brief.script : '');
    setAudience(typeof brief.audience === 'string' ? brief.audience : '');
    setLanguagePick(typeof brief.language === 'string' ? brief.language : null);
    setScriptEdit(brief.script_edit === 'fix' ? 'fix' : 'keep');
    setStage('script');
  };

  const retry = () =>
    run(async (alive) => {
      if (!job?.brief) return;
      // The same switches the failed run had, unless they were changed here for the retry.
      const next = await api.generate(server, job.brief, quality, Object.keys(settings).length > 0 ? settings : job.settings);
      if (alive()) adopt(next, quality);
    });

  // The lesson on screen has no real narration: make a new one from its script and pictures, paying for the voice only.
  const addVoice = () =>
    run(async (alive) => {
      if (!job) return;
      const next = await api.addVoice(server, job.job_id, voicePick);
      if (alive()) adopt(next, quality);
    });

  // Take the run on screen out of the history (stopping it first if it is still being made).
  const removeRun = () =>
    run(async (alive) => {
      if (!jobId) return;
      const gone = await api.removeJob(server, jobId);
      if (!alive()) return;
      reset(gone.stopping ? 'That run is stopping at its next step and will leave the list.' : null);
    });

  // A job known only by id (a recent video, or the one remembered across a reload):
  // the status loop below fetches it and the screen follows from what comes back.
  const openJob = (id: string) => {
    epoch.current += 1;
    inFlight.current = false;
    const known = rememberedJob();
    rememberJob(known?.id === id ? known : { id });
    setBusy(false);
    setError(null);
    setSawRepair(false);
    setLink(null);
    setJob(null);
    setJobId(id);
    setStage('job');
  };

  const changeToken = (value: string) => {
    setTokenState(value);
    setToken(value);
  };

  const closeDashboard = () => {
    setDashboard(false);
    showDashboard(false);
  };

  // A resumed job found only in storage gets its link back in the address bar.
  useEffect(() => {
    if (resumed) rememberJob(resumed);
  }, [resumed]);

  // After the effect above, which would otherwise put the job's link in place of `#dashboard`.
  useEffect(() => {
    if (!dashboard) return;
    showDashboard(true);
    setDashboardKnown(true);
  }, [dashboard]);

  // Which kind of server this is; asked again when the address or the token changes.
  useEffect(() => {
    const request = new AbortController();
    serverMode(server, request.signal).then(
      (next) => {
        if (!request.signal.aborted) setMode(next);
      },
      () => {},
    );
    return () => request.abort();
  }, [server, token]);

  // For the dashboard: which screen is up (and, on a job's screens, which lesson). On a viewer site the
  // start screen is the list of lessons, not the questions.
  const seenJob = view === 'making' || view === 'watch' || view === 'failed' ? jobId : null;
  const seen = view === 'ask' && mode === 'viewer' ? 'lessons' : view;
  useEffect(() => {
    if (mode === null) return;
    track(server, 'screen', { value: seen, job_id: seenJob });
  }, [server, seen, seenJob, mode]);

  // Read the job's status while it runs. Generation takes minutes; nothing is held open.
  // A failed read never ends the loop: it backs off (2 s → 10 s) and says so, because the
  // usual cause is a server restart or a dropped tunnel and the job is still there after.
  useEffect(() => {
    if (!live || !jobId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let request: AbortController | undefined;
    let tries = 0;
    const poll = async () => {
      timer = undefined;
      request = new AbortController();
      let final = false;
      try {
        const next = await api.job(server, jobId, request.signal);
        if (stopped) return;
        tries = 0;
        setLink(null);
        if (repairLogged(next)) setSawRepair(true);
        if (isQuality(next.quality)) setQuality(next.quality);
        setJob(next);
        final = next.status === 'done' || next.status === 'failed';
      } catch (e) {
        if (stopped) return;
        const status = statusOf(e);
        // Never seen and unknown to the server: a stale link, not an outage.
        if (status === 404 && !opened) {
          reset('That video is no longer on this server.');
          return;
        }
        tries += 1;
        setLink({ tries, status, message: say(e) });
      }
      if (!final) timer = setTimeout(poll, tries ? Math.min(POLL_MS * 1.5 ** (tries - 1), POLL_MAX_MS) : POLL_MS);
    };
    timer = setTimeout(poll, opened ? POLL_MS : 0);
    return () => {
      stopped = true;
      if (timer !== undefined) clearTimeout(timer);
      request?.abort();
    };
  }, [live, jobId, server, opened, reset]);

  // Recent videos for the start screen. Briefly delayed so typing a server URL or a
  // token does not send a request per keystroke; a failure just hides the section.
  useEffect(() => {
    if (!atStart) return;
    let stopped = false;
    const request = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const jobs = await api.jobs(server, request.signal);
        if (!stopped) {
          setRecent({ jobs, at: Date.now() / 1000 });
          setRecentFailed(false);
        }
      } catch {
        if (!stopped) {
          setRecent(null);
          setRecentFailed(true);
        }
      }
    }, 300);
    return () => {
      stopped = true;
      clearTimeout(timer);
      request.abort();
    };
  }, [atStart, server, token]);

  // A conversation follows its newest bubble; every other screen starts at its top.
  useEffect(() => {
    if (view === 'ask' && turns.length > 0) scroll.current?.scrollToEnd({ animated: true });
  }, [view, turns, busy]);
  useEffect(() => {
    scroll.current?.scrollTo({ y: 0, animated: false });
  }, [view]);

  const progress = session?.progress;
  const failedStage = job ? stageLabel(job, job.stage) : '';
  // A job the server rebuilt from disk may have no brief to post back.
  const retryable = !!job?.brief && Object.keys(job.brief).length > 0;
  return (
    <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <StatusBar style="light" />
      <View style={styles.shell}>
        <View style={styles.header}>
          <View style={styles.flex}>
            <Text style={styles.eyebrow}>LESSONFORGE</Text>
            <Text style={styles.title}>{view === 'dashboard' ? 'Dashboard' : canMake ? 'Make a lesson video' : 'Lesson videos'}</Text>
          </View>
          {dashboard ? (
            <Pressable onPress={closeDashboard} style={styles.ghost}>
              <Text style={styles.ghostText}>Back</Text>
            </Pressable>
          ) : feedback ? (
            <Pressable onPress={() => setFeedback(null)} style={styles.ghost}>
              <Text style={styles.ghostText}>Back</Text>
            </Pressable>
          ) : stage === 'job' ? (
            <View style={styles.headerActions}>
              {view === 'watch' && job && canMake ? (
                <Pressable onPress={() => setFeedback({ lesson: { id: job.job_id, title: job.title } })} style={styles.ghost}>
                  <Text style={styles.headerLink}>Feedback</Text>
                </Pressable>
              ) : null}
              <Pressable onPress={() => reset()} style={({ pressed }) => [styles.secondary, pressed && styles.pressed]}>
                <Text style={styles.secondaryText}>{canMake ? 'New video' : 'All lessons'}</Text>
              </Pressable>
            </View>
          ) : (
            <View style={styles.headerActions}>
              {dashboardKnown ? (
                <Pressable onPress={() => setDashboard(true)} style={styles.ghost}>
                  <Text style={styles.headerLink}>Dashboard</Text>
                </Pressable>
              ) : null}
              {!atStart ? (
                <Pressable onPress={() => reset()} style={styles.ghost}>
                  <Text style={styles.ghostText}>Start over</Text>
                </Pressable>
              ) : null}
            </View>
          )}
        </View>
        {progress && progress.of > 0 && view === 'ask' ? (
          <View style={styles.track}>
            <View style={[styles.fill, { width: `${Math.min(100, (100 * progress.answered) / progress.of)}%` }]} />
          </View>
        ) : null}

        <ScrollView ref={scroll} style={styles.flex} contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
          {view === 'ask' && !canMake ? (
            mode === null ? (
              <View style={[styles.card, styles.stage]}>
                <ActivityIndicator color={C.teal} size="small" />
                <Text style={styles.stageText}>Opening…</Text>
              </View>
            ) : recent && recent.jobs.length > 0 ? (
              <RecentVideos list={recent} onOpen={openJob} title="Lessons" all />
            ) : (
              <Text style={styles.finePrint}>
                {recentFailed
                  ? 'The lessons could not be loaded. If this site needs an access token, open it with the link you were given.'
                  : recent
                    ? 'No lessons are published here yet.'
                    : 'Loading the lessons…'}
              </Text>
            )
          ) : null}

          {canMake && (atStart || view === 'script') ? (
            <ModeSwitch
              mode={view === 'script' ? 'script' : 'topic'}
              disabled={busy}
              onChange={(mode) => {
                setError(null);
                setStage(mode === 'script' ? 'script' : 'ask');
              }}
            />
          ) : null}

          {view === 'script' ? (
            <ScriptForm script={script} onScript={setScript} audience={audience} onAudience={setAudience} busy={busy} onCheck={checkScript} />
          ) : null}

          {view === 'ask' && canMake ? (
            <>
              <Bubble turn={OPENING} />
              {atStart ? <FeedbackEntry server={server} onOpen={() => setFeedback({ lesson: null })} /> : null}
              {atStart && recent && recent.jobs.length > 0 ? <RecentVideos list={recent} onOpen={openJob} /> : null}
              {turns.map((turn, i) => (
                <Bubble key={i} turn={turn} />
              ))}
              {busy ? (
                <View style={[styles.bubble, styles.theirs, styles.thinking]}>
                  <ActivityIndicator color={C.teal} size="small" />
                  <Text style={styles.noticeText}>Thinking…</Text>
                </View>
              ) : null}
              {!busy && question && options.length > 0 ? (
                <View style={styles.options}>
                  {asksChoice ? null : <Text style={styles.finePrint}>Suggestions for this topic — tap one, or type your own below.</Text>}
                  {options.map((option, i) => (
                    <Pressable
                      key={`${i}-${option.value}`}
                      onPress={() => send(option.value, option.label)}
                      style={({ pressed }) => [styles.option, pressed && styles.pressed]}>
                      <Text style={styles.optionLabel}>{option.label}</Text>
                      {option.hint ? <Text style={styles.optionHint}>{option.hint}</Text> : null}
                    </Pressable>
                  ))}
                </View>
              ) : null}
            </>
          ) : null}

          {view === 'confirm' && session ? (
            <>
              {session.note ? <Bubble turn={{ from: 'harness', tone: 'note', text: session.note }} /> : null}
              <Text style={styles.sectionTitle}>Here is what I will make</Text>
              <View style={styles.card}>
                {session.summary.map((row) => (
                  <View key={row.label} style={styles.row}>
                    <Text style={styles.rowLabel}>{row.label}</Text>
                    <Text style={styles.rowValue}>{row.value}</Text>
                  </View>
                ))}
              </View>
              <BriefEdit server={server} base={session.brief} value={briefEdits} onChange={setBriefEdits} />
              <Text style={styles.sectionTitle}>How it is planned</Text>
              <View style={styles.chips}>
                <Pressable onPress={() => setFromSources(true)} style={[styles.chip, fromSources && styles.chipOn]}>
                  <Text style={[styles.chipText, fromSources && styles.chipTextOn]}>From sources first</Text>
                </Pressable>
                <Pressable onPress={() => setFromSources(false)} style={[styles.chip, !fromSources && styles.chipOn]}>
                  <Text style={[styles.chipText, !fromSources && styles.chipTextOn]}>From your answers only</Text>
                </Pressable>
              </View>
              <Text style={styles.finePrint}>
                {fromSources
                  ? 'Reads the textbook chapter, lectures and lesson plans for this topic, writes a one-page teaching plan (why it is true, the one picture, where learners go wrong, a task to try by hand), then writes the script from it. Takes a few minutes longer.'
                  : 'The script is written from what you answered above.'}
              </Text>
              {fromSources ? (
                <TextInput
                  multiline
                  numberOfLines={3}
                  value={ownSources}
                  onChangeText={setOwnSources}
                  placeholder="Optional: paste links (a video, a page) or your own notes to build on"
                  placeholderTextColor={C.muted}
                  textAlignVertical="top"
                  style={[styles.input, styles.notes]}
                />
              ) : null}
              <VoicePick server={server} value={voicePick} onChange={setVoicePick} language={asLanguage(briefEdits.language ?? session?.brief.language)} />
              <Text style={styles.sectionTitle}>Quality</Text>
              <QualityChips value={quality} onChange={setQuality} />
              <Controls server={server} value={settings} onChange={setSettings} />
              <CheckFirst value={checkFirst} onChange={setCheckFirst} />
              <Pressable disabled={busy} onPress={generate} style={({ pressed }) => [styles.primary, (pressed || busy) && styles.pressed]}>
                <Text style={styles.primaryText}>{busy ? 'Starting…' : checkFirst ? 'Write the script' : 'Generate video'}</Text>
              </Pressable>
            </>
          ) : null}

          {view === 'confirm' && plan && !session ? (
            <>
              <Text style={styles.sectionTitle}>Here is what I will make</Text>
              <ScriptPlanCard plan={plan} language={scriptLanguage} onLanguage={setLanguagePick} edit={scriptEdit} onEdit={setScriptEdit} />
              <VoicePick server={server} value={voicePick} onChange={setVoicePick} language={scriptLanguage} />
              <Text style={styles.sectionTitle}>Quality</Text>
              <QualityChips value={quality} onChange={setQuality} />
              <Controls server={server} value={settings} onChange={setSettings} />
              <CheckFirst value={checkFirst} onChange={setCheckFirst} />
              <Pressable disabled={busy} onPress={generate} style={({ pressed }) => [styles.primary, (pressed || busy) && styles.pressed]}>
                <Text style={styles.primaryText}>{busy ? 'Starting…' : checkFirst ? 'Write the script' : 'Generate video'}</Text>
              </Pressable>
              <Pressable
                disabled={busy}
                onPress={() => {
                  setPlan(null);
                  setStage('script');
                }}
                style={({ pressed }) => [styles.secondary, pressed && styles.pressed]}>
                <Text style={styles.secondaryText}>Edit the script</Text>
              </Pressable>
            </>
          ) : null}

          {view === 'making' ? (
            <>
              <Text style={styles.sectionTitle}>{job ? job.title || 'Your lesson' : 'Opening your video…'}</Text>
              {job ? (
                <StageTracker job={job} withRepair={sawRepair || repairLogged(job)} />
              ) : (
                <View style={[styles.card, styles.stage]}>
                  <ActivityIndicator color={C.teal} size="small" />
                  <Text style={styles.stageText}>Fetching it from the server</Text>
                </View>
              )}
              {link ? <Reconnecting link={link} /> : null}
              {job && job.progress.length > 0 ? <Text style={styles.log}>{job.progress.slice(-6).join('\n')}</Text> : null}
              {job ? (
                <Text style={styles.finePrint}>
                  This takes several minutes and runs on the server.
                  {Platform.OS === 'web' ? ' You can close or reload this page: the same link reopens this video.' : ''}
                </Text>
              ) : null}
              {job?.elsewhere && job.note ? <Text style={styles.warn}>{job.note}</Text> : null}
              {job && !job.elsewhere && canMake ? (
                <>
                  <RemoveRun label="Stop and remove this run" busy={busy} onRemove={removeRun} />
                  <Text style={styles.finePrint}>Started by mistake, or twice? This stops it at its next step and takes it out of the list.</Text>
                </>
              ) : null}
            </>
          ) : null}

          {view === 'watch' && job ? (
            <>
              <Text style={styles.sectionTitle}>{job.title}</Text>
              {job.note ? <Text style={styles.warn}>{job.note}</Text> : null}
              {job.script_only ? null : <LessonVideo key={job.job_id} ref={lesson} job={job} server={server} />}
              {canMake && (job.script_only || job.video_url) ? (
                <ScriptEditor
                  key={`edit-${job.job_id}`}
                  server={server}
                  job={job}
                  voice={voicePick}
                  waiting={!!job.script_only}
                  onStarted={(next) => adopt(next, quality)}
                />
              ) : null}
              {canMake && !job.script_only && (lacksVoice(job) || !!job.video_url) ? (
                <View style={styles.card}>
                  <Text style={styles.title}>{lacksVoice(job) ? 'Add the voice' : 'Audio / voice options'}</Text>
                  <Text style={styles.rowValue}>
                    {lacksVoice(job)
                      ? 'Add the voice to this lesson. Nothing is planned or drawn again: only the narration is made, and the result is a new lesson in your list. This one stays as it is.'
                      : `Currently voiced by: ${job.voice || 'server default'}. Choose a different voice to narrate this saved video with. Only the narration is made; visuals and timing are preserved.`}
                  </Text>
                  <VoicePick server={server} value={voicePick} onChange={setVoicePick} language={asLanguage(job?.brief?.language)} />
                  <Pressable
                    disabled={busy}
                    onPress={addVoice}
                    style={({ pressed }) => [styles.primary, (pressed || busy) && styles.pressed]}>
                    <Text style={styles.primaryText}>{busy ? 'Starting…' : lacksVoice(job) ? 'Add the voice' : 'Re-voice video with selected audio'}</Text>
                  </Pressable>
                  {error ? <Text style={styles.warn}>{error}</Text> : null}
                </View>
              ) : null}
              {fromScript(job) ? <ScriptSource job={job} onEdit={canMake ? () => editScript(job) : undefined} /> : null}
              {job.try_it ? <TryIt key={`tryit-${job.job_id}`} server={server} job={job} owner /> : null}
              {job.card ? <TeachingCard card={job.card} /> : null}
              <StudentReviews key={`reviews-${job.job_id}`} server={server} job={job} onSeek={(seconds) => lesson.current?.seek(seconds)} />
              <LessonReports job={job} />
            </>
          ) : null}

          {view === 'failed' && job ? (
            <>
              <Text style={styles.sectionTitle}>{job.title || 'Your lesson'}</Text>
              {job.video_url ? (
                <>
                  <View style={styles.banner}>
                    <Text style={styles.bannerText}>
                      The video was built, but a later step failed ({failedStage}). You can watch it here; whatever that step would
                      have added is missing. Details are below the video.
                    </Text>
                  </View>
                  <LessonVideo key={job.job_id} job={job} server={server} />
                </>
              ) : null}
              <View style={[styles.card, styles.failCard]}>
                <Text style={styles.failTitle}>Generation failed</Text>
                <Text style={styles.rowValue}>{job.error || 'The server reported a failure without a message.'}</Text>
                <Text style={styles.finePrint}>Stopped at: {failedStage}</Text>
                {job.progress.length > 0 ? <Text style={styles.log}>{job.progress.slice(-6).join('\n')}</Text> : null}
                {!canMake ? null : retryable ? (
                  <>
                    <Text style={styles.settingLabel}>Quality for the retry</Text>
                    <QualityChips value={quality} onChange={setQuality} />
                    <Controls server={server} value={Object.keys(settings).length > 0 ? settings : (job.settings ?? {})} onChange={setSettings} />
                  </>
                ) : (
                  <Text style={styles.finePrint}>The server did not keep this job’s brief, so it cannot be retried from here.</Text>
                )}
                <View style={styles.actions}>
                  {canMake && fromScript(job) && typeof job.brief?.script === 'string' ? (
                    <Pressable onPress={() => editScript(job)} style={({ pressed }) => [styles.secondary, styles.action, pressed && styles.pressed]}>
                      <Text style={styles.secondaryText}>Edit the script</Text>
                    </Pressable>
                  ) : null}
                  {canMake && job.can_finish ? (
                    <Pressable
                      disabled={busy}
                      onPress={addVoice}
                      style={({ pressed }) => [styles.primary, styles.action, (pressed || busy) && styles.pressed]}>
                      <Text style={styles.primaryText}>{busy ? 'Starting…' : 'Finish this lesson'}</Text>
                    </Pressable>
                  ) : null}
                  {canMake && retryable ? (
                    <Pressable
                      disabled={busy}
                      onPress={retry}
                      style={({ pressed }) => [job.can_finish ? styles.secondary : styles.primary, styles.action, (pressed || busy) && styles.pressed]}>
                      <Text style={job.can_finish ? styles.secondaryText : styles.primaryText}>{busy ? 'Starting…' : 'Try again'}</Text>
                    </Pressable>
                  ) : null}
                  <Pressable onPress={() => reset()} style={({ pressed }) => [styles.secondary, styles.action, pressed && styles.pressed]}>
                    <Text style={styles.secondaryText}>{canMake ? 'New video' : 'All lessons'}</Text>
                  </Pressable>
                  {canMake && !job.video_url ? <RemoveRun row label="Remove this run" busy={busy} onRemove={removeRun} /> : null}
                </View>
                {error ? <Text style={styles.warn}>{error}</Text> : null}
                {canMake && job.can_finish ? (
                  <Text style={styles.finePrint}>
                    Finish this lesson keeps the script and the pictures that were already made and makes only the narration
                    and the video: a new lesson in your list, at a fraction of the cost.
                  </Text>
                ) : null}
                {canMake && retryable ? (
                  <Text style={styles.finePrint}>
                    Try again makes it again from the same brief. What was already planned, reviewed, drawn or narrated for it
                    is kept on the server and used again, not paid for twice.
                  </Text>
                ) : null}
              </View>
              <StageTracker job={job} withRepair={sawRepair || repairLogged(job)} />
              {job.video_url ? <LessonReports job={job} /> : null}
            </>
          ) : null}

          {view === 'feedback' && feedback ? <TesterFeedback server={server} lesson={feedback.lesson} onMakeAnother={() => reset()} /> : null}

          {view === 'dashboard' ? (
            <Dashboard
              server={server}
              onOpen={(id) => {
                closeDashboard();
                openJob(id);
              }}
            />
          ) : null}

          {error ? <Text style={styles.error}>{error}</Text> : null}
        </ScrollView>

        {view === 'ask' && canMake && !asksChoice ? (
          <View style={styles.composer}>
            <TextInput
              value={draft}
              onChangeText={setDraft}
              editable={!busy}
              placeholder={
                !session
                  ? 'e.g. Why the Pythagorean theorem works, for class 8'
                  : options.length > 0
                    ? 'Or type your own…'
                    : question?.placeholder || 'Type your answer…'
              }
              placeholderTextColor={C.muted}
              style={[styles.input, busy && styles.disabled]}
              onSubmitEditing={submitDraft}
              returnKeyType="send"
            />
            {question?.optional ? (
              <Pressable disabled={busy} onPress={() => send('skip', 'Skip')} style={[styles.ghost, busy && styles.disabled]}>
                <Text style={styles.ghostText}>Skip</Text>
              </Pressable>
            ) : null}
            <Pressable disabled={busy || !draft.trim()} onPress={submitDraft} style={[styles.sendButton, (busy || !draft.trim()) && styles.disabled]}>
              <Text style={styles.primaryText}>{busy ? '…' : 'Send'}</Text>
            </Pressable>
          </View>
        ) : null}

        <Pressable onPress={() => setEditingServer((v) => !v)}>
          <Text style={styles.serverLine}>
            Server: {server}
            {token ? ' · access token set' : ''}
          </Text>
        </Pressable>
        {editingServer ? (
          <View style={styles.settings}>
            <Text style={styles.settingLabel}>Server URL</Text>
            <TextInput value={server} onChangeText={setServer} autoCapitalize="none" autoCorrect={false} style={[styles.input, styles.serverInput]} />
            <Text style={styles.settingLabel}>Access token</Text>
            <TextInput
              value={token}
              onChangeText={changeToken}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="Only if the server requires one"
              placeholderTextColor={C.muted}
              style={[styles.input, styles.serverInput]}
            />
          </View>
        ) : null}
      </View>
    </KeyboardAvoidingView>
  );
}

function Bubble({ turn }: { turn: Turn }) {
  const mine = turn.from === 'you';
  const text = mine ? styles.mineText : turn.tone === 'notice' ? styles.noticeText : turn.tone === 'note' ? styles.noteText : styles.theirsText;
  return (
    <View style={[styles.bubble, mine ? styles.mine : styles.theirs]}>
      <Text style={text}>{turn.text}</Text>
      {turn.why ? <Text style={styles.why}>{turn.why}</Text> : null}
    </View>
  );
}

function QualityChips({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <View style={styles.chips}>
      {QUALITIES.map((q) => (
        <Pressable key={q.value} onPress={() => onChange(q.value)} style={[styles.chip, value === q.value && styles.chipOn]}>
          <Text style={[styles.chipText, value === q.value && styles.chipTextOn]}>{q.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

const STATUS_TONE: Record<JobStatus, string> = { done: C.teal, running: C.gold, queued: C.gold, failed: C.pink };

// `all`: every lesson, not only the newest few (the viewer site opens on this list).
function RecentVideos({ list, onOpen, title = 'Recent videos', all = false }: { list: RecentList; onOpen: (id: string) => void; title?: string; all?: boolean }) {
  // A run that failed and left nothing to watch is set aside: a history of them hid the lessons.
  const [showFailed, setShowFailed] = useState(false);
  // The newest few first; every lesson the server has is one press away (2026-10-15, "show all videos").
  const [showAll, setShowAll] = useState(false);
  const empty = list.jobs.filter((item) => item.status === 'failed' && !item.video_url);
  const listed = showFailed ? list.jobs : list.jobs.filter((item) => !empty.includes(item));
  const shown = all || showAll ? listed : listed.slice(0, RECENT_SHOWN);
  return (
    <View style={styles.recent}>
      <Text style={styles.sectionTitle}>{showAll && !all ? `All videos (${listed.length})` : title}</Text>
      {shown.map((item) => {
        const tone = STATUS_TONE[item.status] ?? C.muted;
        const facts = [
          typeof item.created === 'number' ? ago(list.at - item.created) : null,
          typeof item.duration_seconds === 'number' && item.duration_seconds > 0 ? clock(item.duration_seconds) : null,
          // The reason this list exists: a run that failed late still has something to watch.
          item.status === 'failed' && item.video_url ? 'video was built' : null,
          item.mode === 'script' ? 'from a script' : null,
          item.status === 'failed' && !item.video_url && item.error ? item.error.slice(0, 70) : null,
        ].filter(Boolean);
        return (
          <Pressable key={item.job_id} onPress={() => onOpen(item.job_id)} style={({ pressed }) => [styles.recentRow, pressed && styles.pressed]}>
            <View style={styles.flex}>
              <Text style={styles.optionLabel} numberOfLines={2}>
                {item.title || 'Untitled lesson'}
              </Text>
              {facts.length > 0 ? <Text style={styles.optionHint}>{facts.join(' · ')}</Text> : null}
            </View>
            <View style={[styles.statusChip, { borderColor: tone }]}>
              <Text style={[styles.statusText, { color: tone }]}>{item.status}</Text>
            </View>
          </Pressable>
        );
      })}
      {!all && listed.length > RECENT_SHOWN ? (
        <Pressable onPress={() => setShowAll((on) => !on)} style={styles.ghost}>
          <Text style={styles.headerLink}>{showAll ? 'Show only the newest' : `Show all ${listed.length} videos`}</Text>
        </Pressable>
      ) : null}
      {empty.length > 0 ? (
        <View style={styles.hiddenLine}>
          <Text style={styles.finePrint}>
            {showFailed ? `${empty.length} failed run${empty.length === 1 ? '' : 's'} shown.` : `${empty.length} failed run${empty.length === 1 ? '' : 's'} with nothing to watch ${empty.length === 1 ? 'is' : 'are'} hidden.`}
          </Text>
          <Pressable onPress={() => setShowFailed((on) => !on)} style={styles.ghost}>
            <Text style={styles.headerLink}>{showFailed ? 'Hide' : 'Show'}</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

function Reconnecting({ link }: { link: Link }) {
  // A few 404s in a row from a job that was loading fine: the server came back without it.
  const unknown = link.status === 404 && link.tries >= 4;
  return (
    <View style={styles.banner}>
      <View style={styles.stage}>
        <ActivityIndicator color={C.gold} size="small" />
        <Text style={[styles.bannerText, styles.flex]}>Reconnecting…</Text>
      </View>
      <Text style={styles.warn}>
        {unknown
          ? 'The server answers, but does not know this job — it may have restarted without it. Still checking; “New video” starts over.'
          : `${link.message} Trying again automatically (attempt ${link.tries}).`}
      </Text>
    </View>
  );
}

// A finished lesson with no real narration: silent, or in the basic voice the server falls back to.
// "Let me check the script first": the human in the loop before anything is narrated or filmed.
function CheckFirst({ value, onChange }: { value: boolean; onChange: (next: boolean) => void }) {
  return (
    <Pressable onPress={() => onChange(!value)} style={[styles.card, value && { borderColor: C.teal }]}>
      <Text style={styles.rowValue}>{value ? '☑' : '☐'}  Let me check the script before it is filmed</Text>
      <Text style={styles.finePrint}>
        The script is written and reviewed, then it waits for you. You can change any part’s words or picture, then make the
        video. Nothing is narrated or filmed until you say so.
      </Text>
    </Pressable>
  );
}

function lacksVoice(job: Job): boolean {
  return job.status === 'done' && !!job.video_url && (job.voice === 'silent' || !!job.voice?.startsWith('gtts'));
}

// Two taps, so a run is never removed by a slip of the thumb.
// `row`: it sits in a row of buttons and shares the width; alone it is a full-width button of ordinary height.
function RemoveRun({ label, busy, onRemove, row = false }: { label: string; busy: boolean; onRemove: () => void; row?: boolean }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const timer = setTimeout(() => setArmed(false), 4000);
    return () => clearTimeout(timer);
  }, [armed]);
  return (
    <Pressable
      disabled={busy}
      onPress={() => (armed ? onRemove() : setArmed(true))}
      style={({ pressed }) => [styles.secondary, row && styles.action, styles.remove, (pressed || busy) && styles.pressed]}>
      <Text style={[styles.secondaryText, styles.removeText]}>{busy ? 'Removing…' : armed ? 'Tap again to remove' : label}</Text>
    </Pressable>
  );
}

// What was measured about the lesson. After a late failure some of these are simply absent.
function LessonReports({ job }: { job: Job }) {
  const checks = job.checks;
  const limits = checks?.review_limits ?? [];
  const questions = job.interactions ?? 0;
  const undrawn = job.scenes ? Math.max(0, job.scenes.asked - job.scenes.made) : 0;
  return (
    <>
      {undrawn > 0 && job.scenes ? (
        <View style={styles.banner}>
          <Text style={styles.bannerText}>
            {undrawn} of {job.scenes.asked} animations could not be drawn, so those parts of the video show text only.
          </Text>
        </View>
      ) : null}
      {job.verification ? <ScriptCheck verification={job.verification} kept={fromScript(job) && job.brief?.script_edit !== 'fix'} /> : null}
      {job.vision_review ? <FrameReview review={job.vision_review} /> : null}
      {checks ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>
            {checks.status === 'technical_checks_passed' ? 'Technical checks passed' : 'Technical checks failed'}
          </Text>
          <Text style={styles.rowValue}>
            {clock(checks.duration_seconds)} · {checks.chapters} chapters · {checks.captions} captions · {checks.animation_anchors}{' '}
            visuals tied to spoken phrases · {checks.layout_counted} layout collisions
          </Text>
          <Text style={styles.rowValue}>{alignmentLine(job.alignment ?? null)}</Text>
          <ContinuityLines continuity={job.continuity} />
          {(checks.failed ?? []).map((line) => (
            <Text key={line} style={styles.error}>
              Failed: {line}
            </Text>
          ))}
          {limits.length > 0 ? <Text style={styles.finePrint}>{limits[limits.length - 1]}</Text> : null}
        </View>
      ) : null}
      {questions > 0 ? (
        <Text style={styles.finePrint}>
          {questions} practice question{questions === 1 ? '' : 's'} prepared to go with this video.
        </Text>
      ) : null}
    </>
  );
}

// Under a video made from a pasted script: what it was made from, and the way back to the words
// (`onEdit`, only where lessons are made).
function ScriptSource({ job, onEdit }: { job: Job; onEdit?: () => void }) {
  const plain = job.script?.undesigned?.length ?? 0;
  const editable = !!onEdit && typeof job.brief?.script === 'string';
  const references = (job.script?.references ?? []).filter((source) => source && typeof source.title === 'string' && source.title);
  return (
    <View style={styles.card}>
      <Text style={styles.rowValue}>
        Made from your script
        {job.script ? ` · ${job.script.words} words` : ''}
        {job.brief?.script_edit === 'fix' ? ' · mistakes were fixed where found' : ' · your words kept as written'}
      </Text>
      {plain > 0 ? (
        <Text style={styles.warn}>
          The picture could not be planned for {plain} of {job.script?.beats ?? plain} paragraphs, so those show plain text.
        </Text>
      ) : null}
      {references.length > 0 ? (
        <Text style={styles.finePrint}>
          The pictures were planned with how these lessons show the topic (your words were not changed):{' '}
          {references.map((source, index) => (
            <Text
              key={`${source.title}-${index}`}
              onPress={source.url ? () => Linking.openURL(source.url as string) : undefined}
              style={source.url ? styles.link : undefined}>
              {index > 0 ? ' · ' : ''}
              {source.title}
            </Text>
          ))}
        </Text>
      ) : null}
      {editable ? (
        <Pressable onPress={onEdit} style={({ pressed }) => [styles.secondary, pressed && styles.pressed]}>
          <Text style={styles.secondaryText}>Edit the script and make it again</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function StageTracker({ job, withRepair }: { job: Job; withRepair: boolean }) {
  const steps = trackerSteps(job, withRepair);
  const queued = job.stage === 'queued';
  // A job that fails after its last listed stage reports "done": every step is behind it.
  const at = queued ? -1 : job.stage === 'done' ? steps.length : steps.indexOf(job.stage);
  return (
    <View style={styles.card}>
      {queued ? (
        <View style={styles.stage}>
          <View style={[styles.dot, styles.dotNow]} />
          <Text style={styles.stageText}>{STAGE_LABELS.queued}</Text>
          {job.status !== 'failed' ? <ActivityIndicator color={C.teal} size="small" /> : null}
        </View>
      ) : null}
      {steps.map((stage, index) => {
        const state = job.status === 'failed' && index === at ? 'failed' : index < at ? 'done' : index === at ? 'now' : 'todo';
        const extra = stage === 'repair';
        return (
          <View key={stage} style={[styles.stage, extra && styles.stageExtra]}>
            <View style={[styles.dot, state === 'done' && styles.dotDone, state === 'now' && styles.dotNow, state === 'failed' && styles.dotFailed]} />
            <Text style={[styles.stageText, state === 'todo' && styles.dim]}>
              {stageLabel(job, stage)}
              {extra ? <Text style={styles.finePrint}>  (extra step: the probe found a collision)</Text> : null}
            </Text>
            {state === 'now' && job.status !== 'failed' ? <ActivityIndicator color={C.teal} size="small" /> : null}
          </View>
        );
      })}
    </View>
  );
}

function severityStyle(severity: Finding['severity']) {
  return severity === 'critical' ? styles.sevCritical : severity === 'major' ? styles.sevMajor : styles.sevMinor;
}

// `kept`: the words are the requester's own and were not to be changed, so the check only reports.
function ScriptCheck({ verification: v, kept }: { verification: Verification; kept?: boolean }) {
  const needsReview = v.status === 'needs_review';
  const edits = v.edits_applied?.length ?? 0;
  const open = (v.findings ?? []).filter((f) => !f.resolved && f.severity !== 'minor').length + (v.claims_failed?.length ?? 0);
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Script check</Text>
      {needsReview ? (
        <View style={styles.banner}>
          <Text style={styles.bannerText}>
            {kept
              ? `Your words were kept as you wrote them. The check found ${open} thing${open === 1 ? '' : 's'} worth a look before you use this video.`
              : `Needs review: the script critic found ${v.critical_unresolved} critical problem${v.critical_unresolved === 1 ? '' : 's'} it could not fix. Watch for them before using this video.`}
          </Text>
        </View>
      ) : null}
      <View style={styles.chips}>
        {SCORE_LABELS.map(({ key, label }) => {
          const score = v.scores?.[key] ?? null;
          return (
            <View key={key} style={styles.scoreChip}>
              <Text style={styles.scoreLabel}>{label}</Text>
              <Text style={[styles.scoreValue, score !== null && score <= 1 && styles.sevCritical, score === 2 && styles.sevMajor]}>
                {score === null ? '–' : score}/4
              </Text>
            </View>
          );
        })}
      </View>
      {v.summary ? <Text style={styles.rowValue}>{v.summary}</Text> : null}
      <Text style={styles.finePrint}>
        {v.claims_checked} claim{v.claims_checked === 1 ? '' : 's'} checked with code · {edits} edit{edits === 1 ? '' : 's'} applied
        {v.claims_failed?.length ? ` · ${v.claims_failed.length} claim${v.claims_failed.length === 1 ? '' : 's'} failed` : ''}
      </Text>
      {v.teaching && v.teaching.of > 0 ? (
        <View style={styles.finding}>
          <Text style={styles.cardTitle}>
            Teaching checks: {v.teaching.passed} of {v.teaching.of} met
          </Text>
          {(v.teaching.checks ?? [])
            .filter((check) => !check.pass)
            .map((check) => (
              <View key={check.check} style={styles.row}>
                <Text style={styles.rowValue}>
                  ✗ {check.question}
                  {check.beat ? <Text style={styles.finePrint}>{`  (beat ${check.beat})`}</Text> : null}
                </Text>
                {check.fix ? <Text style={styles.finePrint}>What would meet it: {check.fix}</Text> : null}
              </View>
            ))}
          <Text style={styles.finePrint}>Reported for you to read. Nothing is rewritten because of them yet.</Text>
        </View>
      ) : null}
      {(v.findings ?? [])
        .filter((finding) => !finding.what.startsWith('teaching check'))
        .map((finding, i) => (
        <View key={`${finding.beat}-${i}`} style={styles.finding}>
          <Text style={[styles.findingSeverity, severityStyle(finding.severity)]}>
            {finding.resolved ? 'fixed · ' : ''}
            {finding.severity}
            {finding.beat ? ` · beat ${finding.beat}` : ''}
          </Text>
          <Text style={[styles.rowValue, finding.resolved && styles.struck]}>{finding.what}</Text>
          {finding.fix && !finding.resolved ? <Text style={styles.finePrint}>Fix: {finding.fix}</Text> : null}
        </View>
      ))}
      {v.claims_failed?.map((claim, i) => (
        <View key={`claim-${i}`} style={styles.finding}>
          <Text style={[styles.findingSeverity, styles.sevCritical]}>claim failed{claim.beat ? ` · beat ${claim.beat}` : ''}</Text>
          <Text style={styles.rowValue}>{claim.claim}</Text>
          <Text style={styles.finePrint}>{claim.python} → {String(claim.result)}</Text>
        </View>
      ))}
    </View>
  );
}

function FrameReview({ review }: { review: VisionReview }) {
  const kinds = VISION_KINDS.filter((kind) => (review.by_kind?.[kind] ?? 0) > 0);
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Frame review</Text>
      <Text style={styles.rowValue}>
        {review.frames_showing_intended} of {review.frames} frames show what the script intended
        {review.frames_unreadable > 0 ? ` · ${review.frames_unreadable} unreadable` : ''}
      </Text>
      {kinds.length ? (
        <View style={styles.chips}>
          {kinds.map((kind) => (
            <View key={kind} style={styles.kindChip}>
              <Text style={styles.kindText}>
                {kind} {review.by_kind[kind]}
              </Text>
            </View>
          ))}
        </View>
      ) : (
        <Text style={styles.finePrint}>No layout or content problems seen in the sampled frames.</Text>
      )}
    </View>
  );
}

function alignmentLine(alignment: Alignment | null): string {
  if (alignment && alignment.enabled && alignment.clips > 0) {
    const rate = alignment.word_match_rate === null ? null : Math.round(alignment.word_match_rate * 100);
    return `Narration aligned word-by-word on ${alignment.trusted} of ${alignment.clips} blocks${rate === null ? '' : ` (match rate ${rate}%)`}`;
  }
  return 'Narration timing estimated (no alignment)';
}

function ContinuityLines({ continuity }: { continuity: Continuity | null }) {
  if (!continuity) return null;
  const repeats = continuity.cross_chapter_repeats ?? 0;
  const first = continuity.repeated_phrases?.[0];
  // The server's own warning for repeats is replaced by the line below, not shown twice.
  const warnings = (continuity.warnings ?? []).filter((line) => !(repeats > 2 && line.includes('repeated across chapters')));
  return (
    <>
      {typeof continuity.words === 'number' ? (
        <Text style={styles.rowValue}>
          {continuity.words} words
          {typeof continuity.target_words === 'number' && continuity.target_words > 0 ? ` (target ${continuity.target_words})` : ''}
        </Text>
      ) : null}
      {repeats > 2 ? (
        <Text style={styles.warn}>
          {repeats} phrases repeat across chapters{first ? `, e.g. “${first}”` : ''}.
        </Text>
      ) : null}
      {warnings.map((line) => (
        <Text key={line} style={styles.warn}>
          {line}
        </Text>
      ))}
    </>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  shell: { flex: 1, width: '100%', maxWidth: 820, alignSelf: 'center', paddingHorizontal: 16, paddingTop: Platform.OS === 'web' ? 20 : 52, paddingBottom: 10 },
  flex: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'flex-end', marginBottom: 10 },
  headerActions: { flexDirection: 'row', alignItems: 'center' },
  headerLink: { color: C.teal, fontSize: 14, fontWeight: '600' },
  eyebrow: { color: C.teal, fontSize: 12, letterSpacing: 1.5, fontWeight: '600' },
  title: { color: C.ink, fontSize: 26, fontWeight: '600', marginTop: 2 },
  track: { height: 3, backgroundColor: C.line, borderRadius: 2, marginBottom: 6 },
  fill: { height: 3, backgroundColor: C.teal, borderRadius: 2 },
  body: { paddingVertical: 12, gap: 10 },
  bubble: { maxWidth: '88%', paddingVertical: 11, paddingHorizontal: 14, borderRadius: 14 },
  theirs: { alignSelf: 'flex-start', backgroundColor: C.panel, borderWidth: 1, borderColor: C.line },
  mine: { alignSelf: 'flex-end', backgroundColor: C.teal },
  theirsText: { color: C.ink, fontSize: 17, lineHeight: 24 },
  noteText: { color: C.ink, fontSize: 15, lineHeight: 22 },
  noticeText: { color: C.muted, fontSize: 15, lineHeight: 22 },
  thinking: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  mineText: { color: C.bg, fontSize: 16, lineHeight: 22, fontWeight: '500' },
  why: { color: C.muted, fontSize: 13, lineHeight: 19, marginTop: 6 },
  options: { gap: 8, marginTop: 2 },
  option: { backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 12, padding: 14 },
  optionLabel: { color: C.ink, fontSize: 16, fontWeight: '500' },
  optionHint: { color: C.muted, fontSize: 13, lineHeight: 19, marginTop: 3 },
  pressed: { opacity: 0.7 },
  composer: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingTop: 8 },
  input: { flex: 1, color: C.ink, backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16 },
  sendButton: { backgroundColor: C.teal, borderRadius: 12, paddingHorizontal: 18, paddingVertical: 13 },
  disabled: { opacity: 0.4 },
  primary: { backgroundColor: C.teal, borderRadius: 12, paddingVertical: 15, alignItems: 'center', marginTop: 8 },
  primaryText: { color: C.bg, fontSize: 16, fontWeight: '600' },
  ghost: { paddingHorizontal: 12, paddingVertical: 10 },
  ghostText: { color: C.muted, fontSize: 14 },
  secondary: { borderWidth: 1, borderColor: C.teal, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 10, alignItems: 'center' },
  secondaryText: { color: C.teal, fontSize: 15, fontWeight: '600' },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 2 },
  action: { flexGrow: 1, flexBasis: 140, marginTop: 0, paddingVertical: 14 },
  recent: { gap: 8, marginTop: 8 },
  recentRow: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 12, padding: 14 },
  statusChip: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  statusText: { fontSize: 12, fontWeight: '600', letterSpacing: 0.3 },
  failCard: { borderColor: C.pink },
  failTitle: { color: C.pink, fontSize: 18, fontWeight: '600' },
  remove: { borderColor: C.pink },
  removeText: { color: C.pink },
  hiddenLine: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  sectionTitle: { color: C.ink, fontSize: 19, fontWeight: '600', marginTop: 6 },
  card: { backgroundColor: C.panel, borderWidth: 1, borderColor: C.line, borderRadius: 14, padding: 14, gap: 10 },
  cardTitle: { color: C.ink, fontSize: 16, fontWeight: '600' },
  row: { gap: 2 },
  rowLabel: { color: C.muted, fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase' },
  rowValue: { color: C.ink, fontSize: 15, lineHeight: 22 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: 1, borderColor: C.line, backgroundColor: C.panel, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 9 },
  chipOn: { borderColor: C.teal },
  chipText: { color: C.muted, fontSize: 14 },
  chipTextOn: { color: C.teal },
  stage: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  stageExtra: { paddingLeft: 14 },
  dot: { width: 10, height: 10, borderRadius: 5, borderWidth: 1.5, borderColor: C.line },
  dotDone: { backgroundColor: C.teal, borderColor: C.teal },
  dotNow: { borderColor: C.gold, backgroundColor: C.gold },
  dotFailed: { borderColor: C.pink, backgroundColor: C.pink },
  stageText: { color: C.ink, fontSize: 16, flex: 1 },
  dim: { color: C.muted },
  log: { color: C.muted, fontSize: 12, lineHeight: 18, fontFamily: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' }) },
  warn: { color: C.gold, fontSize: 14, lineHeight: 20 },
  error: { color: C.pink, fontSize: 14, lineHeight: 20 },
  finePrint: { color: C.muted, fontSize: 12, lineHeight: 18 },
  link: { color: C.teal, textDecorationLine: 'underline' },
  banner: { borderWidth: 1, borderColor: C.gold, backgroundColor: 'rgba(255, 209, 124, 0.12)', borderRadius: 10, padding: 12 },
  bannerText: { color: C.gold, fontSize: 14, lineHeight: 20, fontWeight: '600' },
  scoreChip: { borderWidth: 1, borderColor: C.line, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, alignItems: 'center', minWidth: 92 },
  scoreLabel: { color: C.muted, fontSize: 11, letterSpacing: 0.4, textTransform: 'uppercase' },
  scoreValue: { color: C.teal, fontSize: 18, fontWeight: '600', fontVariant: ['tabular-nums'], marginTop: 2 },
  finding: { borderLeftWidth: 2, borderLeftColor: C.line, paddingLeft: 10, gap: 2 },
  findingSeverity: { fontSize: 12, letterSpacing: 0.4, textTransform: 'uppercase', fontWeight: '600' },
  sevCritical: { color: C.pink },
  sevMajor: { color: C.gold },
  sevMinor: { color: C.muted },
  struck: { color: C.muted, textDecorationLine: 'line-through' },
  kindChip: { borderWidth: 1, borderColor: C.gold, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7 },
  kindText: { color: C.gold, fontSize: 13 },
  settings: { gap: 4, marginTop: 6 },
  settingLabel: { color: C.muted, fontSize: 11, letterSpacing: 0.4, textTransform: 'uppercase', marginTop: 4 },
  serverLine: { color: C.line, fontSize: 11, textAlign: 'center', paddingTop: 8 },
  serverInput: { flex: 0, fontSize: 13 },
  notes: { flex: 0, minHeight: 84 },
});
