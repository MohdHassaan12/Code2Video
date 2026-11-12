# lessonforge

Narrated STEM lesson videos with Manim, generated rather than hand-built.

You give it a topic. It asks who the lesson is for, what they should be able to do
afterwards, how it should sound and in which language; picks a teaching framework for
that learner; writes the script; records the narration **first**; and renders every
visual against the measured audio, with captions, chapter markers and a check report.

Or you give it the **script**: paste the words you want narrated and the video is made
from them — spoken as written, with the picture designed to match (see
"A video from your own script" below).

It is one package merged from three repositories — a storyboard-to-Manim engine with
layout verification, an audio-first long-form lesson builder, and their research
documents. `PROVENANCE.md` records what came from where and what was pruned.

> **Status, 2026-10-07 — working proof of concept.** The pipeline runs end to end and
> its checks pass. That is not the same as a good lesson: the script writer has not
> yet been run against a real language model (see "What is not done"), and no teacher
> or learner has reviewed any output.

## Quick start

Full developer setup (system packages, keys, the app, tests): [`docs/DEV_SETUP.md`](docs/DEV_SETUP.md).

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[all,dev]"          # needs ffmpeg; LaTeX + dvisvgm for equations
lessonforge doctor                   # what is installed and configured

cp .env.example .env                 # add GEMINI_API_KEY / OPENROUTER_API_KEY / GROQ_API_KEY
lessonforge serve                    # http://localhost:5000
```

Then either open the client (below) or drive the API:

```bash
curl -X POST localhost:5000/api/harness/sessions -H 'content-type: application/json' \
     -d '{"opening": "Why the Pythagorean theorem works, for class 8, about 5 minutes"}'
# → answer each returned question at /api/harness/sessions/{id}/answer, then
#   POST /api/harness/sessions/{id}/generate and poll /api/harness/jobs/{job_id}
```

With no model key the harness still runs, but writes a placeholder outline instead of
a lesson. With no voice configured the video is silent with captions. Both are
reported in the job result and shown in the client.

### The client (web, iOS, Android — one codebase)

```bash
cd clients/lessonforge-app && npm install
npm run export:web                                   # → dist/
LESSONFORGE_WEB_APP=$PWD/dist lessonforge serve      # open http://localhost:5000/app/

EXPO_PUBLIC_API_URL=http://<your-ip>:5000 npx expo start   # phones / emulators
```

`lessonforge serve` binds to localhost because `/api/compile_video` executes posted
Python. To reach it from a phone, bind wider only on a network you trust
(`lessonforge serve --host 0.0.0.0`) or put it behind authentication.

## How a video is made

```
 topic ─▶ intake ─▶ brief ─▶ framework ─▶ script ─▶ speech ─▶ timeline ─▶ chapters ─▶ video + checks
          (asks)            (3, by level)  (model)   (first)   (measured)   (rendered)
```

| Stage | Module | What it guarantees |
| --- | --- | --- |
| Intake | `harness/intake.py` | One question at a time, each with its reason; never re-asks what you already said; pushes back on a topic too broad to teach |
| Framework | `harness/frameworks.py` | Three explanation shapes — *See it, then name it* (new to the idea), *Watch one, do one* (building fluency), *Why must it be true?* (wants the proof) — each an ordered list of stages with a job |
| Script | `harness/writer.py` | The model writes words; code assigns structure, verifies every on-screen step is anchored to a phrase actually in the narration, and measures continuity |
| Speech | `longform/audio.py`, `speech.py` | Whole teaching blocks synthesized (not isolated sentences), never retimed to hit a length; every timing labelled by how it was obtained |
| Scenes | `longform/runtime.py` | `GuidedChapter` renders a chapter from data: each step waits for its spoken phrase, two fixed columns are laid out once so nothing reflows, the step being spoken is at full strength |
| Checks | `longform/build.py`, `layout_probe.py` | Layout measured after every animation; the finished file is read back; the report lists its own limits |

### The four problems this is aimed at

| Problem | What addresses it now | What is still open |
| --- | --- | --- |
| **Long-form consistency** | Lessons over 6 minutes are written chapter by chapter against a ledger (running example, glossary, what is already established, how the previous chapter ended); one chrome, palette and voice for every chapter; continuity reported as counts | Never run with a real model. Visual objects do not persist across chapters. RQ-24, RQ-25 |
| **Overlap and composition** | Generated chapters are collision-free by construction; hand-written and engine scenes are measured by the per-play probe; a flagged chapter is re-laid compact and kept only if measurably better | `GuidedChapter` shows text and equations only — no diagrams. Composition quality is unmeasured. RQ-07, RQ-08, RQ-17 |
| **Audio and picture out of step** | Audio is made first and measured; visuals anchor to spoken phrases | Position inside a sentence is a word-count estimate; there is no forced alignment yet. RQ-12 |
| **No highlighting** | Each step is revealed on its phrase, earlier steps recede, the key step is boxed as it is introduced | Highlights point at whole steps, not at parts of a diagram or terms inside an equation. RQ-15 |

RQ numbers refer to `docs/research/RESEARCH_QUESTIONS.md`, the unified register of 30
open questions from both projects.

## Other ways in

```bash
# A script you wrote: your words are narrated as written, a model designs the screen
lessonforge script my_script.txt --check                             # read it back; nothing is spent
lessonforge script my_script.txt --audience "Class 8 students" -q m

# A lesson you wrote (or reviewed): lesson.json (+ optional hand-written scenes)
lessonforge lesson build examples/like_terms --voice silent -q l     # script only → animatic
lessonforge lesson build examples/pythagoras --voice kokoro          # 20 min, 10 hand-written chapters

# The engine's storyboard path (model-written storyboard → deterministic transpiler)
lessonforge lesson to-board examples/like_terms -o board.json
lessonforge board render board.json --mute                           # probe + sidecar, no speech
# Studio editor, bulk runs and the render timeline: http://localhost:5000/studio  /bulk  /timeline
```

Voices: `silent`, `kokoro[:voice@speed]` (local; set `KOKORO_MODEL` and `KOKORO_VOICES`),
`gtts[:lang]`, `engine:<sarvam|gemini>/<locale>/<speaker>` (the engine's provider chain).

## Layout

```
src/lessonforge/
  harness/        intake · frameworks · writer · scripted · service · api     (/api/harness)
  longform/       contract · speech · audio · runtime · build · review
  engine/         storyboard → codegen → render → repair; FastAPI app, Studio  (see engine/README.md)
  transpiler.py   viz_helpers.py   theme.py   layout_probe.py   bridge.py   paths.py   cli.py
clients/lessonforge-app/     Expo client (React Native + web)
examples/                    pythagoras (hand-written chapters), like_terms (script only)
docs/                        engine · longform · research · project      (map: docs/README.md)
tests/                       unit (pytest) · engine (24 script harnesses) · manual
```

Everything written at runtime goes under `LESSONFORGE_HOME` (default
`./lessonforge_workspace`): renders, videos, caches, and one complete directory per
generated lesson in `lessons/<job_id>/`.

## Tests

```bash
python -m pytest tests/unit                # 183 tests: contract, timeline, bridge, harness, script path, layout
python tests/run_engine_checks.py --fast   # 18 engine harnesses, no render
python tests/run_engine_checks.py          # all 24, six of them real manim renders (~5 min)
```

## What is not done

- **The script writer is untested against a real model.** Prompts and the chapter
  ledger are exercised with a stubbed model only. Expect to iterate on them.
- **Frameworks are first drafts**, written from common teaching practice, not yet
  extracted from reviewed expert-teacher lessons and not validated with learners.
- **Generated visuals are text and equations.** Diagrams, constructions and
  simulations exist on the engine path (storyboard IR) but are not yet driven from a
  harness script; `bridge.py` is the seam.
- **No forced alignment**, no teacher review step in the product, no accounts, no job
  persistence across a server restart (each lesson's directory is the durable record).
- **The Pythagoras narration was rejected by its reviewer** as disconnected. It is now
  synthesized in blocks for that reason; nobody has listened to the new audio.
- The client has been run on web only; the iOS and Android builds are untested.
- The `chem` (rdkit) and `rag` (chromadb) extras were not installed in the environment
  the merge was verified in; `requirements.lock.txt` is that environment's exact set.

## 2026-10-08 — first run with real models

With an OpenRouter key in `.env` the harness now runs end to end with real models
(`docs/research/experiments/2026-10-08_openrouter_run/REPORT.md`): Gemini 3.8 Flash
writes chapter by chapter against a ledger, a different-family critic checks the
maths with code before any speech is bought, Gemini 3.8 Flash TTS narrates, whisper
word timestamps align every cue, code-drawn figures (`longform/figures.py`) give
chapters a picture, and a vision pass reviews one frame per beat. A six-minute lesson
costs about 0.20 USD and 11 minutes. `lessonforge spend` shows the ledger against the
budget; `lessonforge harness BRIEFS.json` runs a batch. To expose the server for
testing: set `LESSONFORGE_ACCESS_TOKEN`, `LESSONFORGE_WEB_APP`, then
`lessonforge serve` and `cloudflared tunnel --url http://127.0.0.1:5000 --protocol http2`.

### Later the same day — first user test

A tester's 15-minute job failed in its last step and the intake questions were generic.
Both are fixed and tested in a real browser through the tunnel (intake → generate →
playback → reload → history): jobs and sessions now survive restarts and a built video
is never lost to a later step; intake questions are written for the topic by a fast
model with tappable answers (`harness/interviewer.py`); figures are drawn from their
labelled numbers; the critic re-reviews any script it edited. Details and what is
still open: section 6 of the report above. Tests: `pytest -q` (unit),
`pytest tests/integration -q` (one real job through the service).

### Later still — motion, Hinglish, cuts and reviews

- **Motion and in-video questions.** Figures are built in stages and steps animate from
  the part they refer to; a `scene` figure is a model-written animation, verified in a
  sandbox and replayed inside its box; thinking pauses become questions the player
  stops on (`longform/figures.py`, `longform/runtime.py`, `clients/…/Questions.tsx`).
- **Hinglish.** Hindi for the conversation, English for numbers and technical terms
  ("three by four", never "teen bata char"), enforced by a language gate in the critic.
- **One video, several ways to watch.** Every beat carries a depth tag; full, standard,
  revision and summary cuts are time ranges of the same video, playable in the app or
  exported as a file (`harness/service.py`, `lessonforge plan` splits a chapter into lessons).
- **Reviews stored with the lesson.** A student opens a review-only link, does five
  tasks and answers a question sheet; people who make lessons use the Feedback tab.
  Read results with `lessonforge feedback [JOB]` or `GET /api/harness/feedback/summary`
  (`harness/feedback.py`, report section 9).

### Dashboard and the public link

- **Dashboard.** `…/app/?token=<token>#dashboard` shows who opened the app, how far they
  got (conversation, video asked for, played, watched half, feedback), every lesson with
  its plays, the visitors by device and country, the latest activity and the spend against
  the budget. The same numbers: `lessonforge stats [--days N]` and `GET /api/harness/stats`.
  A visitor is a random cookie; no names or addresses are stored (`harness/analytics.py`).
- **The link.** `bash scripts/public_link.sh` starts the server and a Cloudflare quick
  tunnel if they are not running and prints the link to share. After a reboot the old link
  is dead and this prints a new one. `--new` forces a fresh link, `--restart` reloads the
  server and refuses while a lesson is being generated.
- **Browser tests** are in `tests/browser/` (see its README).
- **Budget.** `lessonforge budget` shows what is spent and left; `lessonforge budget 20` sets the
  cap and `lessonforge budget +10` raises it. A running server uses the new cap from its next
  paid call, with no restart.

## 2026-10-09 — a video from your own script

The harness now has two ways in. The first starts from an **intent** (a topic and the
answers to the intake's questions) and a model writes the words. The second starts from
the **words**: in the app choose "Use my script", paste the narration, press "Check my
script", and generate.

```
 your script ─▶ read back ─▶ parts and beats ─▶ the screen for each beat ─▶ check ─▶ speech ─▶ video
                (no model)    (code)             (model: picture and steps only)   (reports)
```

- **Your words are spoken as written.** Code only makes them speakable: digits and symbols
  become words ("3/4" is said "three by four", "in 1905" is said as a year), and markdown,
  links and speaker labels are removed. The captions are the same words.
- **How to write it.** A line starting with `#` (or "Chapter 2: …", or a short Title Case
  line on its own) names a part. A blank line starts a new paragraph, and a paragraph is one
  beat (a long one is cut at sentence ends, a very short one joins its neighbour). Text in
  `[square brackets]`, or a line starting with `Visual:`, is a direction for the picture: it
  guides what is drawn and is never spoken. With no headings, the parts are chosen from the
  script when the video is planned.
- **A model designs only the screen** (`harness/scripted.py`): one planning call (title,
  the picture that carries the video, the parts when you gave none), then one call per part
  for each beat's figure, steps and depth. It is given the same screen rules as the script
  writer and its answer goes through the same checks, so every step is tied to words that
  are really in your narration.
- **Questions.** Where your script ends a paragraph with a question that the next paragraph
  answers, the player stops and asks it with choices. Nothing is asked that you did not ask.
- **The script check reports and does not rewrite**, unless you choose "Fix mistakes it
  finds" (then it behaves as it does for a generated script). Its findings are shown under
  the video.
- **Limits.** 20 to 3500 words (about 28 minutes). The picture uses the same renderer as
  generated lessons, so it has the same limits. Lengths in the read-back are estimates at
  125 words a minute.
- **API.** `POST /api/harness/script/preview {script, language?}` reads a script back with no
  model call; `POST /api/harness/generate` with `brief: {mode: "script", script, language?,
  audience?, script_edit: "keep" | "fix"}` makes the video.
- **Tests.** `tests/unit/test_scripted.py`, a rendered job in `tests/integration`, and
  `tests/browser/e2e_script.js` (the whole flow in a browser; `GENERATE=0` stops at the
  read-back and spends nothing).

### Try it yourself (same day)

Goal 3 of the script plan (`docs/research/approaches/06_teaching_script_plan.html`): the
learner does something by hand. A lesson may now carry one task, shown under the video
in the app and on a student's review link:

```
 you need ─▶ guess first ─▶ the steps ─▶ what did you see? ─▶ a question that asks why ─▶ check
             (steps stay hidden          (shown after a guess)                             (the answer is kept with the
              until a guess is in)                                                          lesson; only then the reveal)
```

- **Where a task comes from.** For a pasted script, the model that plans the screen also
  writes the task (it is shown in the app and adds no words to the script). For a lesson
  written from a teaching card, it is the card's `try_it`. An older lesson has none.
- **Code decides whether it is shown** (`harness/tryit.py`, `clean`): at most five steps;
  something to guess, a question and an expected answer must be there; nothing that burns
  or cuts. A refused task is left out and the job log says why.
- **Answers are kept with the lesson** (`lessons/<job_id>/tryit/`). The owner reads them
  under the video ("Read them"); a student's link may send one and read none.
- **What the lesson stands on.** When a lesson has a teaching card, the owner also sees its
  big idea, why it is true, the one picture, where learners go wrong and the sources by
  title and link. The sources' own text (`teaching_pack.json`) is never served.
- **API.** `POST /api/harness/jobs/{id}/tryit {prediction?, observation?, answer?}` keeps an
  answer and returns what to reveal; `GET` the same path lists them (owner only). The job
  record carries `try_it`, `try_it_answers` and `card`.
- **Tests.** `tests/unit/test_tryit.py`; `tests/browser/e2e_tryit.js` (a real browser on a
  finished lesson, as owner and as a student; spends nothing).

### The account ran dry, and the Sarvam voice (same day)

- **Three ceilings, not two.** The ledger's cap and OpenRouter's count for the key were both
  under 20 USD when the ACCOUNT's own credit reached 0.57 USD and OpenRouter began answering
  402. A 16-minute lesson that had paid for its script and its animations was narrated by
  the fallback voice. Now `lessonforge spend` prints "account credit left", and a lesson
  the account cannot pay for is refused before it starts (HTTP 402 with the amount and
  where to add credit; estimate 0.30 + 0.07 USD per minute).
- **Sarvam voice.** With `SARVAM_AI_KEY` set, narration uses Sarvam AI's `bulbul:v3`
  (`sarvam:<speaker>/<locale>`, default speaker `shubh`, `HARNESS_SARVAM_SPEAKER` to change
  it) before Gemini TTS. It reads Hinglish written in Latin letters as Hinglish. It is
  billed by Sarvam on its own key, so it appears in the ledger at zero dollars. One failed
  clip moves the whole lesson to the next voice: a lesson never changes narrator mid-way.
- **A lesson narrated by the basic voice says so** under its video.
- **Plan from sources first (opt-in).** On the confirm screen, "From sources first (new)"
  sends `card: true` (and any links or notes as `sources`), which turns on the research
  stage: textbook chapter, lectures and lesson plans → a teaching card → the script.

### Stopping a run, and a history that stays readable (same day)

- **Stop and remove.** The making screen has "Stop and remove this run" and a failed run has
  "Remove this run" (two taps). A run that is waiting or being made stops at its next step
  (a narration or a render in progress finishes first) and leaves the list at once. The
  lesson's folder is moved to `lessonforge_workspace/removed/`, never deleted.
  `POST /api/harness/jobs/{id}/remove`; a student's review link cannot call it.
- **A lesson made from the command line shows as running**, with a note, while its process
  is alive: it used to be listed as "failed … Start it again", and pressing "Try again" on
  four of them made four duplicates. It cannot be removed until that process has finished.
- **Recent videos** hides failed runs that left nothing to watch, behind a "Show" link.
- **Sarvam pace.** The harness asks Sarvam for pace 0.75 (`HARNESS_SARVAM_PACE`): at its own
  pace the voice speaks about 196 words a minute, and a six-minute request came out at
  3 min 47 s. At 0.75 it measured about 157 raw words a minute.

### A script that is a production table (same day)

The first script a user pasted was not narration alone: it was a table copied from a
document, with notes above it and an answer key below.

```
 Characters (…): …            ← notes for the picture, never spoken
 Scene | Time | On-screen visual | Voiceover
 1 | 0:00–0:30 | a cart rolls in | Narrator: Aaj Meera …     ← only this column is spoken
 Scene 3 on-screen questions … Answer: 1/2                    ← notes, never spoken
```

- **Only the voiceover column is spoken.** The visual column directs the picture for its
  row, the scene and time columns are dropped, and every line outside the table is passed to
  the model that plans the picture as the author's notes. Read both when the table arrives
  one cell per line (how a table copied from a document pastes), tab-separated, or as a
  markdown table with `|`.
- **Labelled scripts** work too: `**Scene 2 (0:30–1:00)**`, `**Visual:** …`,
  `**Voiceover:** …`. Lines labelled Visual, On-screen, Camera, SFX, Characters, Look and
  feel, Answer and the like are directions; "Narrator:" and "Voiceover:" are removed and
  their words spoken.
- **Symbols a voice cannot read** are put into words: `9²` is "nine squared", `n × n` is
  "n into n" (Hinglish) or "n times n".
- **The read-back says what it did**: "This is a script table with 13 rows. Only its
  voiceover column is spoken …", and the word count is the spoken words only. On that first
  script it is 793 words of 2012.
- **Any other structured script** (a screenplay with "VO:" lines, notes mixed into the
  prose) is shown to a small reader model that labels each line as spoken, picture, note or
  for the teacher; the spoken script is then cut from your own lines, so the words stay
  yours. It costs about a third of a cent, once per document, and the read-back says
  "A reader model picked out the spoken lines: N of M words are spoken".

### A bigger picture that keeps up with the voice, and narration paid for once (same day)

A tester called the composition bad and the picture and the voice out of step. Two lessons
read a frame at a time showed what that was made of:

- the picture sat small in the left of the frame under small type;
- the words on the right DID arrive on their spoken words, but **an animated scene stood
  frozen for most of its beat**: it moved only in the instants a line of text was arriving
  and jumped to its end when the beat ended (in one beat, six short bursts with a
  six-second freeze between them). This had been so in every lesson with a scene;
- a grid kept its "?" while the voice said "four into four equals sixteen";
- a part of a script whose picture was not planned showed three words for twenty seconds.

What changed:

- **Scenes really move, and with the words.** The freeze is fixed. A scene's animation is
  cut into as many stages as its beat has steps; each stage starts when that step's words
  are spoken, plays in about the time those words take, and waits for the next. Nothing
  moves before the first. The model that plans the screen is asked to describe a scene's
  motion in those stages ("first …, then …, then …"), and a scene is played once, by the
  beat it was written for; later beats find it as it ended.
- **Layout.** A picture is enlarged to fill the left of the frame (until now it was only
  ever shrunk), the type is a size larger, a line that is too wide is narrowed by itself
  instead of shrinking every line in the column, and a long list of formulas
  ("17² = 289, 18² = 324, …") is written on two lines at full size.
- **What is being talked about stays marked.** The part of a figure a step points at keeps a
  gold outline until the talk moves on. When a line of working ends on a value
  ("4 × 4 = 16") the "?" on the picture becomes that value, and a rectangle with
  whole-number sides fills its unit squares as it does.
- **The picture outlives the chapter heading.** A chapter that opens on the picture the last
  one ended on does not draw it again, and a chapter that has no picture of its own keeps
  the last one instead of showing text alone.
- **Fewer scenes lost.** The checker that tries every model-written scene called parts that
  APPEAR one after another "nothing moved" (it compared positions only), and could not run
  the sequence form the scene writer had been told to use. Both are fixed, and a scene that
  shows nothing at its start is sent back (a staircase whose every block "appears" opened a
  lesson on six seconds of empty frame).
- **A part of a script left without a screen is asked for once more** before it falls back
  to its opening words.
- **Narration is kept for every lesson** in `<workspace>/cache/speech/`, named by voice
  settings and exact text: "Try again" and "Edit the script and make it again" no longer
  buy the same blocks a second time. `LESSONFORGE_SPEECH_CACHE=0` turns it off; a lesson's
  `audio_report.json` counts `clips_reused_from_other_lessons`.
- **What the Sarvam voice costs.** Sarvam bills by the CHARACTER sent (3 rupees per 1,000
  for `bulbul:v3` when read on 2026-10-09), not by the minute or the word, and has no
  cheaper bulk rate below its enterprise plans. `pace` changes how long the audio is, not
  what it costs, so speaking fast and slowing the file down saves nothing. At the pace
  used here that is about 3 rupees per minute of lesson; the saving is in not paying for
  the same words twice, which is what the shared folder above does. When the Sarvam key
  has no credit left (it answers "No credits available"), the whole lesson is narrated by
  the second voice (Gemini).

Still true: the frame is two columns (picture left, steps right) under a chapter heading,
a model-written scene is a 6 by 4 canvas whose quality varies from scene to scene, and a
scene made before this change is cut into equal stages that only roughly match its words.

### Pictures from the diagram service in a pasted script (same day)

The owner runs a diagram service that draws a real thing the way a textbook does (the water
cycle, a cell). Until now only a lesson written from a teaching card could use it. A pasted
script can too:

- **The plan decides.** When the model that plans a script's screen says the script explains
  a real thing or a natural process that a textbook shows as ONE labelled picture, it names
  that picture ("Water cycle showing evaporation, condensation and precipitation") and the
  service is asked for it. Numbers, shapes, graphs and things to count are still drawn here.
- **Two ways to show it.** A drawing whose labels point at parts (a cell with pointer lines)
  becomes the `diagram` figure: a step lights the part it names. A flat drawing with boxes of
  words (the water cycle) is shown WHOLE, as the service drew it, on a white card: the
  `picture` figure. Either way it is the lesson's one picture of that thing, it stays up from
  beat to beat and across chapter headings, and no model-drawn scene of the same thing is
  made beside it.
- **Settings.** `DIAGRAM_API_URL` and `DIAGRAM_API_KEY` in `.env` (the address is a quick
  tunnel and changes; nothing else needs editing when it does). `HARNESS_SCRIPT_PICTURES=0`
  switches the asking off. Without the service, or when it gives nothing usable, the script
  is drawn as before.

Not yet: nothing inside a whole picture reacts to the voice, and its small print cannot be
read on a phone (the steps beside it carry the words). Filling a flat drawing's boxes one
by one as they are spoken is being built in `harness/diagrams.py`.

### When the money runs out mid-lesson, and adding the voice afterwards (same day)

An 8.5-minute script lesson was started with 2.27 USD left under the spending cap while two
other runs were spending from the same cap. It was planned, all 25 of its pictures were
drawn, and then its narration was refused: the video came out silent, with captions, and its
steps timed by estimate. Three things changed:

- **A lesson the cap cannot cover is refused before it starts**, with what is left and what
  it needs ("The spending cap of 30.00 USD leaves 1.10 and a lesson of about 9 minutes needs
  about 1.33. Nothing was started."). Until now only the account's credit was checked up
  front; the cap was checked one call at a time. The estimate also leans higher than it did.
- **A lesson without a real voice says why** (the cap or the account's credit ran out; the
  voice services failed; none is set up) instead of "no voice is configured".
- **"Add the voice".** A finished lesson that is silent or in the basic voice shows this
  button. It makes a NEW lesson from the old one's script, pictures and review, and pays for
  the narration only (about 3 cents a minute with its timing and frame review); the old
  lesson is left as it is. If the voice still cannot be paid for, nothing is rendered and
  the reason is shown. `POST /api/harness/jobs/{id}/voice`; from a shell,
  `service.narrate_again(job_id)`.

### Nothing is made twice, and a failed lesson is finished, not restarted (same day)

"When gen got failed it is starting from scratch … store content so we dont need to regen
again things in the pipeline." An 8.5-minute lesson had stuck in its LAST chapter's render;
"Try again" then planned its screen, reviewed it and drew its pictures all over again.

- **Every paid step keeps what it made** (`harness/store.py`, `<workspace>/cache/stages/`):
  the screen planned for a pasted script (or the script written for a request) and its
  review, under a key made from everything they were made from: the script or brief, the
  models asked, and the code and prompts that asked. Animations were already kept by their
  description and narration by voice and words. So the same request again, after a failure
  or by "Try again", pays for none of them: the log says "[store] … is used again: nothing
  is paid for it". A changed script, prompt or model is made anew. `"fresh": true` in a
  brief asks for a new take on the same script; `HARNESS_STORE=0` switches the store off.
- **"Finish this lesson"** on a failed lesson whose script and pictures were finished: a new
  lesson from them, with only the narration and the video made (the same route as "Add the
  voice"). "Try again" stays, and now costs little too.
- **A chapter that crashes ends, with its error.** One model-written animation raised inside
  the renderer; Manim then waited for ever at shutdown, so the lesson stayed "rendering" and
  nothing could be restarted. The picture is now copied frame by frame in a way that cannot
  raise on a part that has not been drawn yet, a frame that cannot be made keeps the last
  one, a chapter that does raise exits at once, and a render is stopped after an hour
  (`LESSONFORGE_RENDER_TIMEOUT`).

### A prepared drawing takes the frame (same day)

After the first demo with the diagram service's drawings the owner said they were "not being
intelligently used … at the centre": a drawing took about a quarter of the frame under a
chapter heading that stayed for the whole chapter, and was only dimmed and lit.

- **The heading gives way.** For a prepared drawing (`diagram`, `picture`) the chapter heading
  becomes one small line (lesson title, chapter title) and the stage gains its height. A
  chapter that opens on such a drawing has the small heading from its first frame.
- **The drawing takes the stage's full height**, at the left, with the steps in a narrow
  column beside it: about 43% of the frame for a 3:2 drawing. Beside, not under: the frame is
  16:9 and the band for subtitles stays free, so a drawing is limited by height, and a caption
  row under it would cost the height the heading gave back.
- **A before-and-after drawing shows "before" first.** A drawing in panels shows its first
  panel; the step whose words reveal the next one carries `focus: "panel2"`, and each panel is
  revealed once.
- What happens INSIDE the drawing (a poster built up process by process with beads running
  along its arrows, an anatomy drawing cross-fading to a close-up of the part) is
  `figures.DiagramFigure`, written the same afternoon by the other session
  (`docs/research/approaches/08_voice_blueprints_and_posters.md`).

### Your own voice first, and reviews that repair (same day, evening)

- **The owner's voice service narrates.** When `INDIC_TTS_URL` and `INDIC_TTS_KEY` are set,
  every lesson is narrated by that service (voices Kavya, Agastya, Maitri, Vinaya;
  `HARNESS_INDIC_SPEAKER` picks the usual one). For a Hinglish lesson the voice is given the
  same words with the Hindi in Devanagari; captions and timing keep the lesson's own text.
  The paid voices (Sarvam, Gemini) are used only when chosen for a lesson (the app's
  **Voice** row on the read-back, paid ones marked) or for every lesson with
  `HARNESS_PAID_VOICES=1`. A chosen voice that fails falls back to the owner's, then to the
  basic free voice. `GET /api/harness/voices` lists what a server has.
  Still paid, on purpose: hearing the finished audio to time the steps to the spoken words
  (about 0.2 cents a minute). Without it the steps are timed by estimate.
- **A check that fails causes a repair.** Three now do:
  - something OUTSIDE the stage at a beat's end: that chapter is laid out again, as a chapter
    with an overlap already was, and kept only if the total of faults drops;
  - the frame review saying the SCREEN does not show what the voice is saying ("asks to guess
    between nine, six or three, but the numbers are not on screen"): that beat's on-screen
    steps are written again, its chapter rendered again, only that frame reviewed again, and
    the change kept only if the review then finds less (`harness/repairs.py`;
    `HARNESS_SCREEN_REPAIR=0` switches it off; six beats a lesson at most). The lesson's
    record says what was tried, kept and put back (`screen_repair`);
  - a drawing from the diagram service that does not show what was asked is asked for again
    (`diagrams.prepare_checked`, the other session's).
  Not yet: the teaching checks still only report.
- **Two faults of the afternoon's layout work, found on a real lesson and fixed:** the gold
  outline of a focused part copied the part's label, so "3² = 9" lay on itself; and an
  animated picture was sized by its first frame and grew out of the stage. Outlines are now
  made from shapes only, and a scene is sized once by everything it will show.

### Reference lessons for a pasted script (same evening)

A pasted script's pictures are now planned with how lectures on its topic SHOW it: what they
draw or demonstrate and in what order, how their examples progress, the mistakes they expect
(`library.reference_for_script`, a couple of small model calls, kept by the script's own
text). The notes go to the model that plans and designs the screen and nowhere else: the
narration stays the author's, word for word. The lesson's page lists the lessons used, by
title and link. `HARNESS_SCRIPT_REFERENCES=0` switches it off.

### Pictures come from the drawing service, part by part (same night)

"The visuals are bad how they are made." They were made by a model sketching one scene per
paragraph from a sentence, checked only for running and staying in its box: 33 separate
sketches in one lesson, the same tree in four shapes. For a pasted script that is now the
last resort:

- The plan names ONE picture for each part of the script, as a request to the owner's
  drawing service (a labelled real thing, a demonstration, a standard diagram, tiles, fraction
  strips, a division ladder). Parts on the same thing share a request and so a picture.
- Each different request is asked for once, three at a time; a drawing whose pieces can be
  named has them shown as the voice names them, any other is shown whole. A part keeps its
  picture for all its beats and the picture stays when the chapter heading changes.
- A model-written scene is written only for a beat no prepared picture can serve.

First real lesson made this way through the app (a 135-word, three-part dialogue script,
the owner's voice): two drawings, NO model-written scene, 7.5 cents in all (a lesson of that
length with scenes had cost 21 to 25), checks passed. What it also showed: the shared
water-cycle picture had been asked for from the first part's words only, so it had no rain
or river when the second part spoke of them (the plan is now told to ask for everything
the sharing parts talk about); both drawings came back as the kind with no separable
pieces, so nothing in them reacted to the voice; and only 2 of 5 narration blocks could be
timed from the heard words with the owner's voice.

## 2026-10-09 (night) — timing from heard words, with your voice

Each narration block is listened to by a speech recogniser so the on-screen steps appear on the
words that name them. With your own voice only 2 blocks in 5 were being timed that way; the rest
were timed by estimate. The cause was not your voice: the recogniser is served by three companies
behind one address, and one of them returns the text with no word times. A block whose hearing
comes back without times is now heard by a sibling model that always returns them
(`longform/align.py`, `STT_ORDER`). On the proof lesson's five blocks: 5 of 5 timed from heard
words. The cost is unchanged in practice (a hearing is about a thirtieth of a cent).

## 2026-10-09 (night) — a typeset drawing is pointed at too

About half of the drawings your service returns are typeset (a circuit, a division ladder,
fraction strips, a before-and-after demonstration). Their words are outlines, so until now
nothing in them could be named and the drawing stood still while the voice walked through it.
Now the place of every printed label is measured exactly (a browser lays the drawing out; no
model), one look by a small vision model says what each label reads, and when a step talks
about "Bulb" or "Cell" that word is highlighted on the drawing, the way a teacher runs a
marker over it, and the highlight moves on with the talk (`harness/typeset.py`,
`longform/figures.py`). A label that appears twice on a drawing (two "3"s on a ladder) is
left alone: nobody could tell which was meant.

Also since the evening: a block's steps are pointed at the drawing again after any rewrite
(the reviewer's, a repair's), so a drawing no longer goes bare; the frame review looks when
a step has finished appearing, not while it is half written; a drawing your service fails
is asked for once more, and requests are kept short (the ones it failed were 45 to 60 words).

## 2026-10-09 (night) — better questions

The questions a lesson stops for are now written by a step of their own, after the script
is reviewed (`harness/questions.py`). Each question has a job: a guess before the idea is
told, the idea used on a NEW case after it, the usual mistake to spot, or the idea recalled.
A question may not be about the lesson itself ("which step…"), the beat ends on the question
with nothing said after it, the three options are built alike with no reason inside one, and
every option gets its own line of feedback in the player (why the right one is right, why a
wrong one is tempting and fails). A rewritten question is kept only if code then finds no
more wrong with it than before; a stop that has no honest question is taken out. For a
pasted script no word changes: only the options and their feedback are improved.

On the script of the 20:30 "Why sky is blue" lesson: four stops, all four rewritten and kept
("What colour would the Moon's daytime sky appear?" in place of a question whose answer the
voice gave in the same breath). About 4 cents a lesson.

## 2026-10-10 — questions, second pass; a new frame and local pictures on trial

**Questions.** The owner: "The options in the question are like the next narration now and the
question is giving narration script itself." The step that writes questions again
(`harness/questions.py`) now does one of three jobs at each question card, chosen by code:
keep the question and write only three short answers and a reason for each; cut the beat so
that it ends on its question; or, only when the question cannot stand, write another one. An
option is an answer of one to three words, never a sentence. A second model is given just the
last sentences before each question and must quote the words that give the answer away; a
question it can answer by repeating the voice is replaced by one about a new case that comes
out differently, or the stop is taken out. A pause that has no card (the opening question,
the try-it task) is left alone, and so is every word of a pasted script. The writer is given
the same rules (`writer.QUESTION_RULES`). Tried on copies of five finished lessons; about 2 to
6 cents a lesson. Live since the restart of 05:55.

**The frame and the pictures** (`docs/research/approaches/10_frame_and_local_pictures.md`).
Not live. A new frame (one line of words at a time in type a phone can read, the picture as
large as the frame allows with its words beside or above, pictures that can fill the frame)
was tried on copies of eleven lessons and is kept in
`lessonforge_workspace/pilot/stage_layout/`. The image model already on the machine
(Z-Image-Turbo in the owner's ComfyUI) draws a text-free picture in 10 to 15 seconds for
nothing: good for things and places, wrong for diagrams and spelling. Both wait for the
owner's decision.

## 2026-10-10 (morning) — three lessons made end to end on a second server; a drawing repainted
Asked for by the owner ("try end to end pipeline to gen few videos, you won't interfere the system"). A second server on its
own port and with its own lessons folder made three three-minute lessons from a typed topic (photosynthesis, the area of a
triangle, Newton's third law) in the trial frame; nothing entered the live history. Report with the videos:
https://claude.ai/artifact/QkJCnxybgao9FYLkgDBnDb. What it cost: 0.92 USD in all. What it found, and what is now in the code
(the answer to a question is always spoken; no pause after a plain statement; no animator's note on screen; a drawing's second
panel is never lost to a rewrite): `CLAUDE.md`, the section of the same date. The owner's idea of the same morning, an SVG
drawing as the skeleton and a diffusion model for its look, was tried on five drawings: `docs/research/approaches/10_frame_and_local_pictures.md` §6.
The trial frame and the repainting are not in the lesson path; both wait for the owner.

## 2026-10-10 (afternoon, evening) — the new frame is live; a lesson is previewed before it is paid for

The owner said yes to the five decisions of the trial page and, the same evening, sent a note on composition
("render previews, detect problems, apply localized fixes, rerender, and run regression tests … vision-based
assessment … adaptive composition … split scenes"). What a lesson made now gets, and where it lives:

- **Its own look**, written into `lesson.json` (`longform/look.py`): the stage frame (the picture as large as the
  frame allows, one line of words at a time), no caption band, the light page when every picture is a prepared
  drawing, formula working that stays while the words beside it change. A lesson without a look renders as before;
  `HARNESS_FRAME=columns` makes new lessons as before.
- **Captions under the video** in the app, for every lesson (`clients/lessonforge-app/src/captions.ts`).
- **"From sources first"** is the app's default.
- **A preview before the speech stage** (`longform/preview.py`, `harness/compose.py`, stage "compose"): the lesson as
  stills in seconds, measured (type too small for a phone, a picture left small), code-drawn pictures enlarged when
  the preview shows no new fault, and a vision model's look at each beat's still for what no box can find. Report:
  `<lesson>/composition.json`. One finding is acted on: a beat spoken over a drawing of something else is given a
  drawing of its own from the drawing service (since 2026-10-12; `HARNESS_COMPOSE_DRAW=0` leaves that out), or, when
  none can be had and it never had a picture, is shown without one (`HARNESS_COMPOSE_MEND=0` for a report only;
  `=words` also rewrites words, which was tried and is not recommended).
- **The look of paint on paper** for a poster's scene (2026-10-12; `harness/paperlook.py`, `HARNESS_DRAWING_LOOK=0`
  to leave drawings as drawn): arithmetic, no model, nothing in the drawing can go missing.
- **A drawing draws itself** (2026-10-12): its SVG is taken apart into a sequence of parts (`harness/sequence.py`,
  `<drawing>/sequence.json`) and a drawing shown whole is drawn part by part when it arrives
  (`figures.PictureFigure.paint`; `HARNESS_DRAWINGS=shown` makes new lessons fade it in as before).
- **... and with the words** (2026-10-12 evening): each thing in the drawing (a line with its arrowhead and name, an
  angle's arc with its number) is drawn when the voice reaches it, and what would show a question's answer waits for
  the answer. Code says what the things are, one look by a model says when each is drawn, code keeps that
  consistent with the drawing (`harness/sequence.with_words`; `HARNESS_DRAW_WITH_WORDS=0` leaves it out;
  `docs/research/approaches/11_composition_previews.md` §9). About 2 to 4 cents a drawing.
- **A hand annotates the drawing** (2026-10-12 night; `harness/annotate.py`, `HARNESS_ANNOTATE=0` leaves it out;
  `docs/research/approaches/14_annotation_harness.md`): every value the voice says is written on the picture where it
  belongs, when it is said; what is spoken of is ringed, gone over, pointed at, crossed out. A model ideates, code
  places and checks, the model looks at its own work once; each mark has a start and an end, and a filmed lesson lists
  them all on its own clock in `output/annotations.json`. A new kind of mark is one entry in `annotate.KINDS`. About
  4 cents a drawing (measured on nine).
- **Cheap models, a stronger harness** (2026-10-12 late night; `docs/research/approaches/15_cheap_models_strong_harness.md`): the writer,
  the teaching card, the drawing plan and the hand's marks run on the small model of the family; five contracts in code
  make up for what it gets wrong (a script that is not the whole lesson, a card that spreads, a plan with a thing out of
  place, a mark code counts as wrong); prompt caching is on and the ledger records what was read from the cache. A
  three-minute lesson: about 0.09 USD with an existing card, about 0.12 on a new topic (it was 0.69).
- **A reference lecture beside ours** (`docs/research/approaches/12_reference_lecture_compared.md`): three Khan Academy
  lectures and our lessons on the same topics, measured from the videos themselves.
- **A voice on this machine for Hindi and Hinglish** (2026-10-12): when the speech service does not answer, the local
  Kokoro model narrates (`kokoro:hf_alpha`; `HARNESS_LOCAL_VOICE=0` takes it out), before the basic voice.
- **The writer is told what its drawing holds** (2026-10-11; `harness/card.py: add_holds`, `HARNESS_PICTURE_HOLDS=0`
  to switch it off): the finished drawing is read once, and the script may point only at what is in it.
- **`scripts/layout_regress.py`**: every finished lesson previewed with the renderer as it stands and compared with a
  kept baseline. Run it before changing `longform/runtime.py` or `figures.py`.
- **Not on:** repainting a drawing with the local image model (`harness/repaint.py`, `HARNESS_REPAINT=1`); its own
  check showed it loses small things. **Not possible from here:** the drawing service returning scene, arrows and
  labels as three groups (the contract for its maintainer: `docs/research/approaches/09_open_diagrams.md` §9).

Numbers, frames and what is open: `docs/research/approaches/11_composition_previews.md`; lessons learned the hard
way that day: `CLAUDE.md`, the section of the same date.
