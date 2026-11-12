// Client for the lessonforge content harness (FastAPI, /api/harness/*).
import { Platform } from 'react-native';

export type Option = { value: string | number; label: string; hint?: string };
export type Question = {
  id: string;
  prompt: string;
  why: string;
  kind: 'text' | 'choice';
  options: Option[];
  optional: boolean;
  placeholder: string;
  // "model": written for this topic; "default": the built-in wording.
  source?: 'model' | 'default';
};
// A "text" question may still carry options: topic-specific suggestions to tap,
// next to the composer. A "choice" question is answered only by tapping one.
export type Brief = Record<string, unknown>;

// A lesson's script as a person reads and edits it (GET /jobs/{id}/script).
export type ScriptBeat = {
  id: string;
  narration: string;
  words: number;
  visual: string;
  figure: string;
  shows: string[];
  quiz: string | null;
  findings: string[];
};
export type ScriptView = {
  job_id: string;
  title: string;
  thesis: string;
  status: string;
  script_only: boolean;
  edit_of: string | null;
  beats: number;
  words: number;
  chapters: { id: number; title: string; beats: ScriptBeat[] }[];
};
// What a person changed on one beat: new words, a note on what the screen should show, or taking it out.
export type BeatEdit = { narration?: string; note?: string; remove?: boolean };

// A lesson's own values for the pipeline's switches, by control id (`GET /controls` lists them).
export type Settings = Record<string, string>;
export type ControlOption = { value: string; label: string };
export type Control = {
  id: string;
  group: string;
  label: string;
  kind: 'toggle' | 'choice' | 'number' | 'text';
  default: string;
  // The server's own value right now: what a lesson gets when nothing is chosen here.
  current: string;
  hint?: string;
  options?: ControlOption[];
  low?: number;
  high?: number;
};
export type ControlList = { groups: string[]; controls: Control[] };
export type Choice = { value: string | number; label: string; hint?: string };
export type FrameworkList = {
  frameworks: { id: string; name?: string; plain?: string; for?: string }[];
  levels: Choice[];
  styles: Choice[];
  languages: Choice[];
  durations: Choice[];
};

// A voice a lesson can be narrated in (`GET /voices`). `paid`: charged to the model account per lesson.
// `group`, `cost`, `usd_per_minute` and `languages` come from servers since 2026-10-15; older ones send none.
export type VoiceRow = {
  id: string;
  label: string;
  paid: boolean;
  ours?: boolean;
  kind?: string;
  group?: string;
  cost?: string;
  usd_per_minute?: number | null;
  languages?: string[];
};
export type VoiceList = { voices: VoiceRow[]; default: string | null; timing?: { usd_per_minute: number; text: string } | null };
export type Session = {
  session_id: string;
  question: Question | null;
  brief: Brief;
  summary: { label: string; value: string }[];
  progress: { answered: number; of: number; complete: boolean };
  // Something the assistant decided on its own, said before the next question.
  note?: string | null;
};

// The critic's read of the script, filled in once the "verify" stage finishes.
export type Severity = 'critical' | 'major' | 'minor';
export type Finding = { severity: Severity; beat: string; what: string; fix: string; resolved: boolean };
export type Verification = {
  status: 'passed' | 'needs_review';
  scores: {
    conceptual_accuracy: number | null;
    visual_truthfulness: number | null;
    explanatory_clarity: number | null;
    pedagogy: number | null;
  } | null;
  claims_checked: number;
  critical_unresolved: number;
  edits_applied: string[];
  summary: string;
  findings: Finding[];
  claims_failed: { beat: string; claim: string; python: string; result: unknown }[];
  // Only for a lesson written from a teaching card: yes/no questions about the teaching, reported and not enforced.
  teaching?: { checks: TeachingCheck[]; passed: number; of: number } | null;
};
export type TeachingCheck = { check: number; question: string; pass: boolean; beat: string; evidence: string; fix: string };

// A vision model's look at one frame per beat, against the words spoken then.
export type VisionKind = 'overlap' | 'clipped' | 'unreadable' | 'stale' | 'mismatch' | 'empty' | 'other';
export type VisionReview = {
  frames: number;
  findings: number;
  by_kind: Partial<Record<VisionKind, number>>;
  frames_showing_intended: number;
  frames_unreadable: number;
};

// Forced alignment of the narration, when a backend provided it.
export type Alignment = {
  clips: number;
  trusted: number;
  words: number;
  matched_words: number;
  enabled: boolean;
  word_match_rate: number | null;
};

export type Continuity = {
  warnings: string[];
  steps: number;
  steps_anchored_to_speech: number;
  highlights: number;
  words?: number;
  target_words?: number;
  cross_chapter_repeats?: number;
  repeated_phrases?: string[];
};

export type Checks = {
  status: string;
  duration_seconds: number;
  chapters: number;
  captions: number;
  animation_anchors: number;
  layout_counted: number;
  failed: string[];
  review_limits: string[];
  sentence_timing?: Record<string, number> & { aligned?: number };
};

export type JobStatus = 'queued' | 'running' | 'done' | 'failed';

// One row of GET /jobs (newest first). Jobs outlive a server restart.
export type JobSummary = {
  job_id: string;
  status: JobStatus;
  stage: string;
  title: string;
  video_url: string | null;
  created: number; // unix seconds
  duration_seconds?: number | null;
  language?: string | null;
  // "script": made from words the requester pasted; "intent" (or absent, on an older server): from the questions.
  mode?: string | null;
  // True while another process on the server is making it.
  elsewhere?: boolean;
  error?: string | null;
};

export type Job = {
  job_id: string;
  status: JobStatus;
  // One of `stages`, or "queued" before work starts, or "repair" (between check and review).
  stage: string;
  stages: string[];
  progress: string[];
  title: string;
  // What the job was made from; "Try again" posts it back.
  brief?: Brief;
  quality?: string | null;
  // The switches this lesson was made with (only those that differ from the server's own).
  settings?: Settings;
  created?: number;
  voice: string | null;
  // Why the lesson has no real narration, when it has none: "budget" (the spending cap or the voice
  // account's credit ran out), "unavailable" (the voice services failed), "none" (no voice is set up).
  voice_note?: string | null;
  // A FAILED job whose script and pictures were finished and kept: it can be completed from them
  // (`addVoice`) without paying for either again.
  can_finish?: boolean;
  // Stopped after its script was written and reviewed, as asked: nothing narrated or filmed yet. The person reads
  // the script (`scriptOf`) and approves it, with or without changes (`editLesson`).
  script_only?: boolean;
  awaiting_approval?: boolean;
  // Made from another lesson's script with a person's edits: which lesson, and which beats changed.
  edit?: { of: string; words?: string[]; screens?: string[]; removed?: string[]; screens_kept?: string[] } | null;
  generated_by?: string;
  error: string | null;
  // A FAILED job may still carry a video: it was built before a later step failed.
  video_url: string | null;
  captions_url: string | null;
  review_url: string | null;
  interactions_url?: string | null;
  interactions?: number | null;
  // Only for a video made from a pasted script: how it was read, and the beats whose screen no model designed.
  // `references`: lectures whose way of SHOWING the topic the pictures were designed with (never their words).
  script?: {
    words: number;
    beats: number;
    parts_from: string;
    undesigned?: string[];
    directions?: number;
    references?: { title: string; url?: string }[];
  } | null;
  // The task to do by hand after the video, how many learners answered it, and what the lesson stands on
  // (its teaching card, without the sources' own text). Older lessons have none of the three.
  try_it?: TryItTask | null;
  try_it_answers?: number | null;
  card?: CardView | null;
  // The animations the script asked for and how many could be drawn (older jobs have none).
  scenes?: { asked: number; made: number; failed?: string[] } | null;
  // Set by the server when it rebuilt this job from the lesson files after a restart, or to say who is making it.
  note?: string | null;
  // True while another process on the server (a command-line run) is making it: it cannot be stopped from here.
  elsewhere?: boolean;
  // `depths`: what the chapter holds, from "basics" | "core" | "practice" | "extra".
  chapters?: { id: number; title: string; start: number; depths?: string[] }[];
  cuts?: Cut[] | null;
  continuity: Continuity | null;
  checks: Checks | null;
  verification?: Verification | null;
  vision_review?: VisionReview | null;
  alignment?: Alignment | null;
};

// The task a learner does by hand after the video (harness/tryit.py). The order of its fields is the
// order it is done in: a guess, the steps, what was seen, a question that asks why.
export type TryItTask = {
  title: string;
  kind: 'hands' | 'paper' | 'simulation';
  materials: string[];
  // What each object stands for in the idea.
  stands_for: string;
  predict: string;
  steps: string[];
  // Shown only after the learner has answered.
  observe: string;
  question: string;
  expected: string;
  // What the learner should write or say at the end.
  write: string;
  // The same task for a teacher with a full class.
  in_class: string;
};
export type TryItAnswer = { prediction?: string; observation?: string; answer?: string; reviewer?: string; done_in_class?: boolean };
// The server kept the answer; `observe` and `expected` are what to reveal now.
export type TryItStored = { stored: boolean; id: string; count: number; observe: string; expected: string };
export type TryItSummary = {
  count: number;
  answers: { id: string; at?: number | null; reviewer?: string | null; prediction?: string; observation?: string; answer?: string }[];
};
// What the lesson stands on: its teaching card as an owner reads it. Sources by title and link only.
export type CardView = {
  big_idea: string;
  why_it_matters: string;
  the_why: string;
  picture: string;
  // The standard way the topic is drawn in class ("division ladder", "number line"), when the sources use one.
  picture_standard: string;
  opening_question: { question: string; answer: string };
  mistakes: { mistake: string; why_it_fails: string }[];
  needs_first: string[];
  sources: { id: string; kind: string; title: string; url: string }[];
  // Lines of the card that could not be checked against a source.
  problems: number;
};

// What a pasted script will become, read back before anything is spent (POST /script/preview).
export type ScriptPlan = {
  title: string;
  // Read from the script itself; the requester may choose another before generating.
  language: string;
  words: number;
  minutes: number;
  beats: number;
  // "headings": the parts are the author's own; "planned": chosen from the script while the video is made.
  parts_from: 'headings' | 'planned';
  chapters: { title: string; beats: number; words: number; opens: string }[];
  opens: string;
  directions: number;
  notes: string[];
  summary: { label: string; value: string }[];
  languages: Option[];
};

// A question the player stops for (interactions.json, schema lessonforge.interactions/0.1).
// `misconception`: the known student mistake this wrong option stands for, when the lesson's concept base named one.
export type InteractionOption = { id: string; text: string; correct: boolean; feedback: string; misconception?: string };
export type Interaction = {
  id: string;
  type: 'mcq' | 'predict' | 'recall';
  // Seconds: the question has just been asked — the player pauses here.
  t: number;
  // Seconds: where the video's own silent thinking pause ends. Older files lack it.
  resume_at: number | null;
  scored: boolean;
  prompt: { text: string };
  // Empty for predict / recall.
  options: InteractionOption[];
  // For predict / recall: the answer the lesson gives next.
  answer: { text: string } | null;
  hints: string[];
  // After a wrong answer: where the idea was shown, to watch it again. Null for a prediction (asked before it).
  on_wrong: { seek_to: number; allow_skip: boolean } | null;
  // Ask "how sure are you?" with the options (sure and wrong marks a misconception, not a slip).
  confidence: boolean;
};

// One way of watching the one video ("full", "standard", "revision", "summary"): the
// time ranges of it that are kept, in order. "full" comes first; older jobs have no cuts.
export type Range = [start: number, end: number];
export type Cut = { id: string; label: string; hint: string; seconds: number; ranges: Range[] };
// A cut written out as its own file (POST /jobs/{id}/cuts/{cut}).
export type SavedCut = { cut: string; video_url: string; captions_url?: string | null; seconds?: number };

// ---- Student reviews (/feedback/form, /jobs/{id}/feedback, /jobs/{id}/review_link) ----
// The sheet a student fills in after watching. `chapters` questions take their options
// from the lesson's own chapters and are answered with chapter ids.
export type FeedbackQuestion = {
  id: string;
  section: string;
  kind: 'rating' | 'choice' | 'multi' | 'text' | 'chapters';
  prompt: string;
  required: boolean;
  options?: { value: string; label: string }[]; // choice, multi
  min?: number; // rating
  max?: number;
  low_label?: string;
  high_label?: string;
  placeholder?: string; // text
  max_length?: number;
  multiple?: boolean; // chapters
};
// Two sheets share one shape: "student" (reviewing one lesson) and "tester" (the people
// who make lessons, on how making them went).
export type FeedbackKind = 'student' | 'tester';
export type FeedbackForm = {
  version: string;
  title: string;
  minutes: number;
  tasks: { id: string; text: string }[];
  questions: FeedbackQuestion[];
};
export type FeedbackAnswer = string | number | string[] | number[];
// What the player saw of the viewing; sent with the answers.
export type QuizTally = {
  asked: number;
  answered: number;
  // Right on the first try only.
  correct: number;
  skipped: number;
  // Wrong on the first try (also when the second try was right).
  wrong_ids: string[];
  // Right on the second try, after the nudge.
  retried_right?: number;
  // Wrong while the learner said they were sure.
  sure_wrong_ids?: string[];
  // The known mistakes the wrong options they chose stand for.
  misconceptions?: string[];
};
export type Viewing = { watch_mode: string; seconds_watched: number; completed: boolean; quiz: QuizTally };
export type FeedbackBody = {
  reviewer?: string;
  answers: Record<string, FeedbackAnswer>;
  // `confused_at`: video times (seconds) where the student pressed "This part is confusing".
  auto: Viewing & { confused_at: number[] };
};
export type TesterBody = {
  kind: 'tester';
  // The lesson the tester had open, when there was one.
  job_id?: string;
  reviewer?: string;
  contact?: string;
  answers: Record<string, FeedbackAnswer>;
};
// What a lesson's reviews say, for its owner. Every part may be missing on an older server.
export type FeedbackSummary = {
  job_id: string;
  title: string;
  count: number;
  ratings?: Record<string, { prompt: string; mean: number | null; n: number; histogram: number[] }>;
  choices?: Record<string, { prompt: string; counts: Record<string, number>; labels: Record<string, string> }>;
  chapters?: Record<string, { prompt: string; counts: Record<string, number> }>;
  texts?: Record<string, { prompt: string; items: { text: string; reviewer?: string | null; at?: number | string | null }[] }>;
  confused_at?: { t: number; chapter?: number | null; count: number }[];
  quiz?: { responses: number; mean_correct_share: number | null } | null;
  signals?: { message: string }[];
};

// ---- Dashboard (/stats, /events) ------------------------------------------------
// Who opened the app and what they did, for the owner. Visitors are random ids, never names.
export type StatsDay = {
  day: string; // YYYY-MM-DD on the viewer's calendar
  visits: number;
  visitors: number;
  intakes: number;
  lessons: number;
  finished: number;
  plays: number;
  spend: number;
};
export type StatsLesson = {
  job_id: string;
  title: string;
  status: JobStatus;
  stage: string;
  created: number;
  language?: string | null;
  duration_seconds?: number | null;
  plays: number;
  viewers: number;
  watched_half: number;
  watched_end: number;
  reviews: number;
  rating?: number | null;
  made_by?: string | null;
};
export type StatsVisitor = {
  visitor: string;
  first_seen: number;
  last_seen: number;
  new: boolean;
  visits: number;
  device: string;
  browser: string;
  os: string;
  country: string;
  role: string;
  intakes: number;
  lessons: number;
  plays: number;
  feedback: number;
  last_screen?: string | null;
};
export type StatsEvent = {
  at: number;
  event: string;
  visitor: string;
  device?: string | null;
  country?: string;
  value?: string | number | null;
  job_id?: string | null;
  title?: string | null;
};
export type Stats = {
  generated_at: number;
  days: number;
  // Unix seconds of the first visit ever recorded; null while there is none.
  tracking_since: number | null;
  // The visitor id of the browser asking.
  me?: string | null;
  totals: {
    visitors: number;
    new_visitors: number;
    visits: number;
    online: number;
    intakes: number;
    intakes_completed: number;
    lessons: number;
    finished: number;
    failed: number;
    in_progress: number;
    plays: number;
    viewers: number;
    minutes_made: number;
    student_reviews: number;
    tester_forms: number;
    blocked: number;
  };
  series: StatsDay[];
  funnel: { id: string; label: string; visitors: number }[];
  lessons: StatsLesson[];
  devices: { name: string; visitors: number }[];
  countries: { name: string; visitors: number }[];
  visitors: StatsVisitor[];
  recent: StatsEvent[];
  spend: { spent: number; period: number; budget: number | null; remaining: number | null; per_finished_lesson: number | null };
};

// Served by the engine at /app → same origin. In `expo start` the server is elsewhere:
// set EXPO_PUBLIC_API_URL (an Android emulator reaches the host at http://10.0.2.2:5000).
export function defaultServer(): string {
  const configured = process.env.EXPO_PUBLIC_API_URL;
  if (configured) return configured.replace(/\/$/, '');
  if (Platform.OS === 'web' && typeof window !== 'undefined' && window.location.pathname.startsWith('/app')) {
    return window.location.origin;
  }
  return Platform.OS === 'android' ? 'http://10.0.2.2:5000' : 'http://localhost:5000';
}

// ---- Access token -----------------------------------------------------------
// The server may require LESSONFORGE_ACCESS_TOKEN on every request. On web the
// token arrives once in the page URL (?token=…) and is remembered in localStorage;
// elsewhere it lives in memory for the session. The server also sets a cookie on
// web, so same-origin video/caption requests need nothing extra there.
const TOKEN_KEY = 'lessonforge.token';
let token = '';
let tokenLoaded = false;

function readStored(key: string): string {
  try {
    return typeof localStorage !== 'undefined' ? localStorage.getItem(key) ?? '' : '';
  } catch {
    return '';
  }
}

function writeStored(key: string, value: string): void {
  try {
    if (typeof localStorage === 'undefined') return;
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {
    // Private mode or blocked storage: the in-memory copy still serves this session.
  }
}

function tokenFromUrl(): string {
  if (Platform.OS !== 'web' || typeof window === 'undefined') return '';
  try {
    return new URLSearchParams(window.location.search).get('token') ?? '';
  } catch {
    return '';
  }
}

export function getToken(): string {
  if (!tokenLoaded) {
    tokenLoaded = true;
    const fromUrl = tokenFromUrl();
    token = fromUrl || readStored(TOKEN_KEY) || (process.env.EXPO_PUBLIC_ACCESS_TOKEN ?? '');
    // A review link's token opens one lesson and nothing else: it serves this page, and
    // is not kept in place of the token this browser may already hold for the whole app.
    if (fromUrl && !reviewJob()) writeStored(TOKEN_KEY, fromUrl);
  }
  return token;
}

export function setToken(value: string): void {
  tokenLoaded = true;
  token = value.trim();
  writeStored(TOKEN_KEY, token);
}

// A media URL (video, captions) for the given server. Native players cannot send a
// header, so the token rides as a query parameter there; on web the cookie covers it.
export function mediaUrl(server: string, path: string): string {
  const url = server + path;
  const t = getToken();
  if (!t || Platform.OS === 'web') return url;
  return `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(t)}`;
}

// ---- The job in hand ---------------------------------------------------------
// A generation runs for minutes, so the job being made or watched must survive a
// reload. On web its id is kept twice: in localStorage, and as `#job=<id>` in the
// address bar so the link itself reopens it. Elsewhere it lives in memory.
const JOB_KEY = 'lessonforge.job';
const JOB_ID = /^[\w.-]{1,80}$/;
export type RememberedJob = { id: string; quality?: string };
let remembered: RememberedJob | null = null;

function onWeb(): boolean {
  return Platform.OS === 'web' && typeof window !== 'undefined' && !!window.location;
}

function idFromHash(key: string): string {
  if (!onWeb()) return '';
  try {
    const id = new URLSearchParams(window.location.hash.replace(/^#/, '')).get(key) ?? '';
    return JOB_ID.test(id) ? id : '';
  } catch {
    return '';
  }
}

function jobFromHash(): string {
  return idFromHash('job');
}

// A student's review link is `…/app/?token=<review token>#review=<job id>`: the lesson
// to review, or '' when this is not such a link (and always '' off the web).
export function reviewJob(): string {
  return idFromHash('review');
}

// The dashboard has no button for testers, who share the owner's link: it opens from
// `…/app/?token=<token>#dashboard`, and a browser that has opened it once is shown a
// link to it from then on.
const DASHBOARD_KEY = 'lessonforge.dashboard';
export function dashboardLinked(): boolean {
  if (!onWeb()) return false;
  dashboardTests(); // read now: the address bar changes as soon as a job is in hand
  try {
    return new URLSearchParams(window.location.hash.replace(/^#/, '')).has('dashboard');
  } catch {
    return false;
  }
}

// `#dashboard&tests=1` also counts the automated browsers that test the app (left out
// otherwise). Read from the link the page was opened with, and kept until it is closed.
let countTests: boolean | null = null;
export function dashboardTests(): boolean {
  if (countTests === null) {
    try {
      countTests = onWeb() && new URLSearchParams(window.location.hash.replace(/^#/, '')).get('tests') === '1';
    } catch {
      countTests = false;
    }
  }
  return countTests;
}

export function knowsDashboard(): boolean {
  // Off the web there is no link to open it from, and the app is the owner's own build.
  return !onWeb() || readStored(DASHBOARD_KEY) !== '';
}

// Keep the address bar in step: `#dashboard` while it is open, the job in hand after.
export function showDashboard(open: boolean): void {
  if (!onWeb()) return;
  if (open) writeStored(DASHBOARD_KEY, '1');
  try {
    const { pathname, search } = window.location;
    const hash = open ? (dashboardTests() ? '#dashboard&tests=1' : '#dashboard') : remembered ? `#job=${encodeURIComponent(remembered.id)}` : '';
    window.history.replaceState(null, '', pathname + search + hash);
  } catch {
    // An embedding that forbids history changes: the dashboard still opens and closes.
  }
}

// Whether this browser already sent a review of the lesson.
const REVIEWED_KEY = 'lessonforge.reviewed.';
export function reviewSent(jobId: string): boolean {
  return readStored(REVIEWED_KEY + jobId) !== '';
}

export function rememberReview(jobId: string): void {
  writeStored(REVIEWED_KEY + jobId, '1');
}

function jobFromStorage(): RememberedJob | null {
  try {
    const stored = JSON.parse(readStored(JOB_KEY) || 'null');
    if (!stored || typeof stored.id !== 'string' || !JOB_ID.test(stored.id)) return null;
    return { id: stored.id, quality: typeof stored.quality === 'string' ? stored.quality : undefined };
  } catch {
    return null;
  }
}

export function rememberedJob(): RememberedJob | null {
  if (!onWeb()) return remembered;
  const linked = jobFromHash();
  const stored = jobFromStorage();
  // A link wins over storage: it may be someone else's job, opened in this browser.
  if (linked) return stored?.id === linked ? stored : { id: linked };
  return stored;
}

// Pass null to forget (the "New video" button).
export function rememberJob(job: RememberedJob | null): void {
  remembered = job;
  if (!onWeb()) return;
  writeStored(JOB_KEY, job ? JSON.stringify(job) : '');
  try {
    const { pathname, search } = window.location;
    window.history.replaceState(null, '', pathname + search + (job ? `#job=${encodeURIComponent(job.id)}` : ''));
  } catch {
    // An embedding that forbids history changes: storage still remembers the job.
  }
}

// ---- Requests ----------------------------------------------------------------
// `status` is the HTTP status; 0 means no answer at all (offline, restarting, timed out).
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// Read off the thrown value rather than `instanceof`, which a transpiled subclass
// of Error does not always satisfy. null: not a request failure.
export function statusOf(error: unknown): number | null {
  const status = (error as { status?: unknown } | null)?.status;
  return typeof status === 'number' ? status : null;
}

const CALL_TIMEOUT_MS = 90_000; // an intake answer waits on a model writing the next question
const POLL_TIMEOUT_MS = 15_000; // a status read that hangs must not stall the polling loop
const SAVE_TIMEOUT_MS = 120_000; // writing a cut as its own file re-encodes it the first time

// `media`: the path is a file the job points at (served like the video), not an API route.
type CallOptions = { signal?: AbortSignal; timeoutMs?: number; media?: boolean };

// The readable part of an error body: FastAPI's {"detail": …}, or plain text. A proxy's
// HTML error page is dropped — the status already says what it had to say.
function reason(body: string): string {
  const text = body.trim();
  if (text.startsWith('<')) return '';
  try {
    const detail = JSON.parse(text)?.detail;
    if (typeof detail === 'string') return detail;
  } catch {
    // Not JSON: shown as it came.
  }
  return text;
}

async function call<T>(server: string, path: string, body?: unknown, options: CallOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers['content-type'] = 'application/json';
  const t = getToken();
  if (t) headers['X-Access-Token'] = t;

  // One controller serves both the caller's cancel and the timeout.
  const controller = new AbortController();
  const outer = options.signal;
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, options.timeoutMs ?? CALL_TIMEOUT_MS);
  const relay = () => controller.abort();
  if (outer?.aborted) controller.abort();
  else outer?.addEventListener('abort', relay);

  try {
    const response = await fetch(options.media ? mediaUrl(server, path) : `${server}/api/harness${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok) {
      const detail = reason(await response.text());
      if (response.status === 401) {
        throw new ApiError(401, `401: this server needs an access token — set it below. ${detail.slice(0, 120)}`.trim());
      }
      throw new ApiError(response.status, `${response.status}: ${detail.slice(0, 200) || 'the server answered with an error.'}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (statusOf(error) !== null || outer?.aborted) throw error;
    if (timedOut) throw new ApiError(0, 'The server took too long to answer.');
    if (error instanceof SyntaxError) throw new ApiError(0, 'The server sent something that is not JSON.');
    throw new ApiError(0, `Cannot reach the server at ${server}.`);
  } finally {
    clearTimeout(timer);
    outer?.removeEventListener('abort', relay);
  }
}

// Older and half-written jobs may lack the lists the screens iterate over.
function tidy(job: Job): Job {
  return {
    ...job,
    stages: job.stages ?? [],
    progress: job.progress ?? [],
    cuts: tidyCuts(job.cuts),
    try_it: tidyTask(job.try_it),
    card: tidyCard(job.card),
  };
}

function strings(value: unknown): string[] {
  return (Array.isArray(value) ? value : []).map(text).filter(Boolean);
}

// A task a learner can actually do: steps, something to guess and a question; anything else is not shown.
function tidyTask(task: unknown): TryItTask | null {
  const row = task as Record<string, unknown> | null | undefined;
  const steps = strings(row?.steps);
  if (!row || steps.length === 0 || !text(row.predict) || !text(row.question)) return null;
  const kind = row.kind === 'paper' || row.kind === 'simulation' ? row.kind : 'hands';
  return {
    title: text(row.title),
    kind,
    materials: strings(row.materials),
    stands_for: text(row.stands_for),
    predict: text(row.predict),
    steps,
    observe: text(row.observe),
    question: text(row.question),
    expected: text(row.expected),
    write: text(row.write),
    in_class: text(row.in_class),
  };
}

function tidyCard(card: unknown): CardView | null {
  const row = card as Record<string, any> | null | undefined;
  if (!row || typeof row !== 'object') return null;
  return {
    big_idea: text(row.big_idea),
    why_it_matters: text(row.why_it_matters),
    the_why: text(row.the_why),
    picture: text(row.picture),
    picture_standard: text(row.picture_standard),
    opening_question: { question: text(row.opening_question?.question), answer: text(row.opening_question?.answer) },
    mistakes: (Array.isArray(row.mistakes) ? row.mistakes : [])
      .filter((one: any) => text(one?.mistake))
      .map((one: any) => ({ mistake: text(one.mistake), why_it_fails: text(one.why_it_fails) })),
    needs_first: strings(row.needs_first),
    sources: (Array.isArray(row.sources) ? row.sources : [])
      .filter((one: any) => text(one?.title))
      .map((one: any) => ({ id: text(one.id), kind: text(one.kind), title: text(one.title), url: /^https?:\/\//.test(text(one.url)) ? text(one.url) : '' })),
    problems: Number.isFinite(row.problems) ? row.problems : 0,
  };
}

// Cuts a player can follow: each with at least one real range, ranges in playing order.
function tidyCuts(cuts: unknown): Cut[] {
  const found: Cut[] = [];
  (Array.isArray(cuts) ? cuts : []).forEach((row: Record<string, any> | null) => {
    const id = text(row?.id);
    if (!row || !id || found.some((cut) => cut.id === id)) return;
    const ranges: Range[] = (Array.isArray(row.ranges) ? row.ranges : [])
      .filter((range: any) => Array.isArray(range) && Number.isFinite(range[0]) && Number.isFinite(range[1]) && range[0] >= 0 && range[1] > range[0])
      .map((range: any): Range => [range[0], range[1]])
      .sort((a: Range, b: Range) => a[0] - b[0]);
    if (ranges.length === 0) return;
    const seconds = Number.isFinite(row.seconds) && row.seconds > 0 ? row.seconds : ranges.reduce((sum, [start, end]) => sum + end - start, 0);
    found.push({ id, label: text(row.label) || id, hint: text(row.hint), seconds, ranges });
  });
  return found;
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

// The questions a player can use, in playing order. The file is written by a best-effort
// step on the server, so every field is checked and a row that cannot be asked is dropped.
function tidyInteractions(file: unknown): Interaction[] {
  const rows = (file as { interactions?: unknown } | null)?.interactions;
  const found: Interaction[] = [];
  const ids = new Set<string>();
  (Array.isArray(rows) ? rows : []).forEach((row: Record<string, any> | null, index) => {
    const prompt = text(row?.prompt?.text);
    if (!row || typeof row.t !== 'number' || !Number.isFinite(row.t) || row.t < 0 || !prompt || row.pause === false) return;
    const options: InteractionOption[] = (Array.isArray(row.options) ? row.options : [])
      .filter((option: any) => text(option?.text))
      .map((option: any, k: number) => ({
        id: text(option.id) || String(k + 1),
        text: text(option.text),
        correct: option.correct === true,
        feedback: text(option.feedback),
        ...(text(option.misconception) ? { misconception: text(option.misconception) } : {}),
      }));
    const back = row.on_wrong && typeof row.on_wrong.seek_to === 'number' && Number.isFinite(row.on_wrong.seek_to) && row.on_wrong.seek_to >= 0 && row.on_wrong.seek_to < row.t
      ? { seek_to: row.on_wrong.seek_to as number, allow_skip: row.on_wrong.allow_skip !== false }
      : null;
    let id = text(row.id) || `q${index + 1}`;
    if (ids.has(id)) id = `${id}-${index + 1}`;
    ids.add(id);
    const answer = text(row.answer?.text);
    found.push({
      id,
      type: row.type === 'predict' || row.type === 'recall' ? row.type : 'mcq',
      t: row.t,
      resume_at: typeof row.resume_at === 'number' && Number.isFinite(row.resume_at) ? row.resume_at : null,
      scored: row.scored === true,
      prompt: { text: prompt },
      options,
      answer: answer ? { text: answer } : null,
      hints: (Array.isArray(row.hints) ? row.hints : []).map(text).filter(Boolean),
      on_wrong: back,
      confidence: row.confidence === true && options.length > 1,
    });
  });
  return found.sort((a, b) => a.t - b.t);
}

// The read-back with its lists in place (an older or half-answering server must not break the screen).
function tidyPlan(plan: ScriptPlan): ScriptPlan {
  const list = <T,>(value: unknown): T[] => (Array.isArray(value) ? (value as T[]) : []);
  return {
    ...plan,
    title: text(plan?.title),
    language: text(plan?.language) || 'en-IN',
    opens: text(plan?.opens),
    chapters: list<ScriptPlan['chapters'][number]>(plan?.chapters).filter((chapter) => text(chapter?.title)),
    notes: list<string>(plan?.notes).map(text).filter(Boolean),
    summary: list<ScriptPlan['summary'][number]>(plan?.summary).filter((row) => text(row?.label) && text(row?.value)),
    languages: list<Option>(plan?.languages).filter((option) => text(option?.label) && text(option?.value)),
  };
}

const QUESTION_KINDS = ['rating', 'choice', 'multi', 'text', 'chapters'];

// The sheet with its lists in place; a question of a kind this client cannot draw is left out.
function tidyForm(form: FeedbackForm): FeedbackForm {
  return {
    ...form,
    tasks: (Array.isArray(form?.tasks) ? form.tasks : []).filter((task) => text(task?.id) && text(task?.text)),
    questions: (Array.isArray(form?.questions) ? form.questions : []).filter(
      (question) => text(question?.id) && text(question?.prompt) && QUESTION_KINDS.includes(question.kind),
    ),
  };
}

export const api = {
  // Both intake calls take a few seconds: a model writes the next question.
  start: (server: string, opening?: string) => call<Session>(server, '/sessions', opening ? { opening } : {}),
  answer: (server: string, id: string, question_id: string, value: unknown) =>
    call<Session>(server, `/sessions/${encodeURIComponent(id)}/answer`, { question_id, value }),
  // A pasted script, read back: instant, no model is called and nothing is spent.
  scriptPreview: (server: string, script: string, language?: string) =>
    call<ScriptPlan>(server, '/script/preview', language ? { script, language } : { script }).then(tidyPlan),
  // From the brief, not the session: it still works after the server forgot the session. A brief with
  // `mode: "script"` carries the words themselves (`script`) and the video is made from them.
  generate: (server: string, brief: Brief, quality: string, settings?: Settings | null) =>
    call<Job>(server, '/generate', settings && Object.keys(settings).length > 0 ? { brief, quality, settings } : { brief, quality }).then(tidy),
  // Every switch a lesson can carry, grouped, with the server's current value for each.
  controls: (server: string, signal?: AbortSignal) =>
    call<Partial<ControlList>>(server, '/controls', undefined, { signal, timeoutMs: POLL_TIMEOUT_MS }).then((reply) => ({
      groups: Array.isArray(reply.groups) ? reply.groups.filter((g): g is string => typeof g === 'string') : [],
      controls: Array.isArray(reply.controls)
        ? reply.controls.filter((c) => c && typeof c.id === 'string' && typeof c.label === 'string' && typeof c.kind === 'string')
        : [],
    })),
  // The choice lists the intake uses (levels, styles, languages, lengths, kinds of video).
  frameworks: (server: string, signal?: AbortSignal) =>
    call<Partial<FrameworkList>>(server, '/frameworks', undefined, { signal, timeoutMs: POLL_TIMEOUT_MS }).then((reply) => ({
      frameworks: Array.isArray(reply.frameworks) ? reply.frameworks.filter((f) => f && typeof f.id === 'string') : [],
      levels: Array.isArray(reply.levels) ? reply.levels : [],
      styles: Array.isArray(reply.styles) ? reply.styles : [],
      languages: Array.isArray(reply.languages) ? reply.languages : [],
      durations: Array.isArray(reply.durations) ? reply.durations : [],
    })),
  jobs: (server: string, signal?: AbortSignal) =>
    call<{ jobs?: JobSummary[] }>(server, '/jobs', undefined, { signal, timeoutMs: POLL_TIMEOUT_MS }).then(
      (reply) => reply.jobs ?? [],
    ),
  job: (server: string, id: string, signal?: AbortSignal) =>
    call<Job>(server, `/jobs/${encodeURIComponent(id)}`, undefined, { signal, timeoutMs: POLL_TIMEOUT_MS }).then(tidy),
  // Take a run out of the history. One that is waiting or being made is stopped first, at its next step
  // (`stopping`). The lesson's files are moved aside on the server, not deleted.
  removeJob: (server: string, id: string) =>
    call<{ removed: boolean; stopping?: boolean }>(server, `/jobs/${encodeURIComponent(id)}/remove`, {}),
  // A NEW lesson from a finished one's script and pictures, with only the narration made again: for a lesson
  // that came out silent or in the basic voice. 402 when the cap or the account cannot pay for the voice.
  addVoice: (server: string, id: string, voice?: string | null) =>
    call<Job>(server, `/jobs/${encodeURIComponent(id)}/voice`, voice ? { voice } : {}).then(tidy),
  // The script of a lesson, to read and change before it is filmed (or after).
  scriptOf: (server: string, id: string, signal?: AbortSignal) =>
    call<ScriptView>(server, `/jobs/${encodeURIComponent(id)}/script`, undefined, { signal, timeoutMs: POLL_TIMEOUT_MS }),
  // A NEW lesson from a lesson's script with these edits. `film` false: stop again after the script, to read it once more.
  editLesson: (server: string, id: string, edits: Record<string, BeatEdit>, film: boolean, voice?: string | null) =>
    call<Job>(server, `/jobs/${encodeURIComponent(id)}/edit`, { edits, film, ...(voice ? { voice } : {}) }).then(tidy),
  // The voices this server can narrate with: its owner's own first, the paid ones marked.
  // `language`: only the voices that can narrate a lesson in it.
  voices: (server: string, signal?: AbortSignal, language?: string | null) =>
    call<Partial<VoiceList>>(server, language ? `/voices?language=${encodeURIComponent(language)}` : '/voices', undefined, {
      signal,
      timeoutMs: POLL_TIMEOUT_MS,
    }).then((reply) => ({
      voices: Array.isArray(reply.voices) ? reply.voices.filter((v) => v && typeof v.id === 'string' && typeof v.label === 'string') : [],
      default: typeof reply.default === 'string' ? reply.default : null,
      timing: reply.timing && typeof reply.timing.text === 'string' ? reply.timing : null,
    })),
  // Up to a minute the first time (the server re-encodes the cut), instant after that.
  saveCut: (server: string, id: string, cut: string, signal?: AbortSignal) =>
    call<SavedCut>(server, `/jobs/${encodeURIComponent(id)}/cuts/${encodeURIComponent(cut)}`, {}, { signal, timeoutMs: SAVE_TIMEOUT_MS }),
  // The student sheet is asked for by its bare path: the one a review link may read.
  feedbackForm: (server: string, kind: FeedbackKind, signal?: AbortSignal) =>
    call<FeedbackForm>(server, kind === 'tester' ? '/feedback/form?kind=tester' : '/feedback/form', undefined, {
      signal,
      timeoutMs: POLL_TIMEOUT_MS,
    }).then(tidyForm),
  sendFeedback: (server: string, id: string, body: FeedbackBody, signal?: AbortSignal) =>
    call<{ stored: boolean; id: string; count: number }>(server, `/jobs/${encodeURIComponent(id)}/feedback`, body, { signal }),
  // A learner's answer to the lesson's task; a review link may send one too. The reply holds what to reveal.
  sendTryIt: (server: string, id: string, body: TryItAnswer, signal?: AbortSignal) =>
    call<TryItStored>(server, `/jobs/${encodeURIComponent(id)}/tryit`, body, { signal }),
  // Everything below answers only to the owner's token, never to a review link.
  tryItAnswers: (server: string, id: string, signal?: AbortSignal) =>
    call<TryItSummary>(server, `/jobs/${encodeURIComponent(id)}/tryit`, undefined, { signal, timeoutMs: POLL_TIMEOUT_MS }).then((summary) => ({
      count: typeof summary?.count === 'number' ? summary.count : 0,
      answers: Array.isArray(summary?.answers) ? summary.answers : [],
    })),
  sendTesterFeedback: (server: string, body: TesterBody, signal?: AbortSignal) =>
    call<{ stored: boolean; id: string; count: number }>(server, '/feedback', body, { signal }),
  // How many tester forms the server holds.
  testerCount: (server: string, signal?: AbortSignal) =>
    call<{ count?: number }>(server, '/feedback/summary?kind=tester', undefined, { signal, timeoutMs: POLL_TIMEOUT_MS }).then((summary) =>
      typeof summary?.count === 'number' ? summary.count : null,
    ),
  feedbackSummary: (server: string, id: string, signal?: AbortSignal) =>
    call<FeedbackSummary>(server, `/jobs/${encodeURIComponent(id)}/feedback`, undefined, { signal, timeoutMs: POLL_TIMEOUT_MS }),
  reviewLink: (server: string, id: string, signal?: AbortSignal) =>
    call<{ path: string }>(server, `/jobs/${encodeURIComponent(id)}/review_link`, undefined, { signal, timeoutMs: POLL_TIMEOUT_MS }),
  // `days`: calendar days to cover, 0 for everything. `countMe`: false leaves this browser out.
  // `tests`: count the automated browsers that test the app too.
  stats: (server: string, days: number, countMe: boolean, tests: boolean, signal?: AbortSignal) =>
    call<Stats>(server, `/stats?days=${days}&tz=${-new Date().getTimezoneOffset()}&me=${countMe ? 1 : 0}${tests ? '&tests=1' : ''}`, undefined, {
      signal,
      timeoutMs: POLL_TIMEOUT_MS,
    }),
  // `path` is the job's `interactions_url`.
  interactions: (server: string, path: string, signal?: AbortSignal) =>
    call<unknown>(server, path, undefined, { signal, timeoutMs: POLL_TIMEOUT_MS, media: true }).then(tidyInteractions),
};

// Tell the server's dashboard what only the client can see: the screen that is up, a video
// starting, how much of it was watched. Nothing waits on it and a failure is silent (an
// older server has no such route).
export type Seen = 'screen' | 'play' | 'progress';
export function track(server: string, event: Seen, fields: { job_id?: string | null; value?: string | number } = {}): void {
  const body: Record<string, unknown> = { event };
  if (fields.job_id) body.job_id = fields.job_id;
  if (fields.value !== undefined) body.value = fields.value;
  call<unknown>(server, '/events', body, { timeoutMs: POLL_TIMEOUT_MS }).catch(() => {});
}

// ---- Which kind of server (GET /mode) ------------------------------------------
// "studio" makes lessons (the GPU machine); "viewer" is the site on Render that only shows the finished
// ones, where the app hides every way to make or change a lesson. An older server has no such route, and
// one that cannot be asked yet (no token) is taken for a studio: that screen is where the token is set.
export type ServerMode = 'studio' | 'viewer';
let modeNow: ServerMode = 'studio';

// For the parts of a screen that are not handed the mode (the "Save this version" link under a cut).
export function viewerMode(): boolean {
  return modeNow === 'viewer';
}

export async function serverMode(server: string, signal?: AbortSignal): Promise<ServerMode> {
  try {
    const reply = await call<{ mode?: unknown }>(server, '/mode', undefined, { signal, timeoutMs: POLL_TIMEOUT_MS });
    modeNow = reply?.mode === 'viewer' ? 'viewer' : 'studio';
  } catch (error) {
    if (signal?.aborted) throw error;
    modeNow = 'studio';
  }
  return modeNow;
}
