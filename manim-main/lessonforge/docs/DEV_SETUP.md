# Developer setup

How to get lessonforge running on your machine, work on it, and test it. Last checked on 2026-10-15 on Ubuntu Linux,
Python 3.12 and Node 20. What the project is: [`../README.md`](../README.md). The rules each learned the hard way:
[`../CLAUDE.md`](../CLAUDE.md). Every other document: [`README.md`](README.md).

## 1. System packages

```bash
sudo apt install -y python3-dev python3-venv build-essential pkg-config \
    libcairo2-dev libpango1.0-dev ffmpeg \
    texlive texlive-latex-extra texlive-fonts-extra dvisvgm \
    wamerican fonts-lato
```

| what | why |
|---|---|
| Cairo and Pango headers | Manim's `pycairo` and `manimpango` build against them |
| ffmpeg (with ffprobe) | joining clips, measuring audio, cutting frames |
| LaTeX and dvisvgm | equations; without them maths falls back to plain text |
| `wamerican` | `/usr/share/dict/american-english`, the word list the Hinglish voice uses |
| Lato | the font lessons are set in (`LESSONFORGE_FONT` changes it) |
| Google Chrome or Chromium | draws and measures the diagram service's drawings headless; set `LESSONFORGE_CHROME` if it is not on the path as `google-chrome` or `chromium` |
| Node 20 (nvm is fine) | the app in `clients/lessonforge-app` |
| `cloudflared` (optional) | only to give testers a public link |

SoX is not needed: the engine writes a stand-in on first start.

## 2. Code and Python

```bash
git clone git@github.com:ManideepDonkena/manim.git
cd manim/lessonforge
python3.12 -m venv .venv
.venv/bin/pip install -e ".[all,dev]"
.venv/bin/lessonforge doctor          # what is installed and configured
```

The three folders beside `lessonforge/` (`concept_explorer`, `Stem_Animation_Manim`, `education_content_review`) are
git submodules: the original repositories lessonforge was merged from. Nothing here needs them;
`git submodule update --init` fetches them if you want to read their history.

## 3. Settings (`.env`)

```bash
cp .env.example .env
```

`.env` is read from the folder the server starts in, and is never committed. **With no keys at all everything still
runs**: the questions are the plain ones, the script is a placeholder outline, and the voice is the basic one. That is
enough for work on the app, the renderer, or anything that takes a finished lesson.

| setting | what it is for | where it comes from |
|---|---|---|
| `OPENROUTER_API_KEY` | every paid model call: the writer, the reviewer, the teaching card, looks at frames, timing the words | the owner |
| `OPENROUTER_BUDGET_USD` | a hard cap on what this machine's ledger may spend | the owner decides it |
| `DIAGRAM_API_URL`, `DIAGRAM_API_KEY` | the owner's drawing service (the address changes when its tunnel restarts) | the owner |
| `INDIC_TTS_URL`, `INDIC_TTS_KEY` | the owner's speech service, the first voice (address changes too) | the owner |
| `KOKORO_MODEL`, `KOKORO_VOICES` | the voice on your own machine, used when the speech service cannot be reached: `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the kokoro-onnx project's releases (or put both in `lessonforge_workspace/models/`) | download |
| `TAVILY_API_KEY` | web search for a lesson's sources (optional) | the owner |
| `TTS_HTTP_URL`, `TTS_HTTP_KEY`, `TTS_HTTP_VOICES` | your own speech server as a voice: `POST {"text","voice","language"}` answers WAV or MP3 | optional |
| `GEMINI_API_KEY`, `GROQ_API_KEY` | the older storyboard engine (`/studio`); the lesson path does not need them | optional |
| `LESSONFORGE_ACCESS_TOKEN` | required on every request once the server is reachable from outside | make one |
| `LESSONFORGE_WEB_APP` | the folder of the built app, served at `/app` | `clients/lessonforge-app/dist` |

**Voices.** A lesson is narrated in the voice chosen in the app's voice list (`GET /api/harness/voices`, each with
its cost), else the usual order: the owner's speech service, Kokoro on the machine, Google's basic voice, silence.
The list: the owner's service (free to this app), Microsoft's online neural voices (free; `edge-tts`; not an official
service, so only when chosen), Kokoro (free, local), your own HTTP server, Google basic, the learner's device (the
video is silent and the web player reads the captions aloud), and Sarvam and Gemini (paid: Gemini measured at about
1.4 cents a minute). Every narrated voice also pays about 0.15 cents a minute for timing its words.

**Money.** Every paid call goes through `lessonforge.spend`: it is written to a ledger and refused when the cap is
reached. `lessonforge spend` shows the ledger, this key's own count and the account's credit; `lessonforge budget +10`
raises the cap without a restart. The OpenRouter account is shared with other keys, so its credit can fall while you
spend nothing. A lesson costs about 0.10 to 0.15 USD; a test run of one stage costs cents. Say what a paid trial will
cost before you run it.

## 4. Run it

```bash
.venv/bin/lessonforge serve           # http://localhost:5000 (localhost only: /api/compile_video runs posted Python)
```

| address | what |
|---|---|
| `/app/` | the app (after building it, section 5) |
| `/api/harness/...` | the lesson API (section 6) |
| `/studio`, `/bulk`, `/timeline` | the older storyboard engine's editor, bulk runs, render history |

Everything the server writes goes under `LESSONFORGE_HOME` (default `./lessonforge_workspace`): one folder per lesson in
`lessons/<job_id>/`, caches, the library of sources and drawings, the ledger, logs. It is never committed.

After changing Python code, restart the server: it runs the code it was started with. On the shared server, never
restart while a lesson is being made (`GET /api/harness/jobs` lists them), and use `bash scripts/public_link.sh
--restart`, which refuses in that case and keeps the public link.

## 5. The app (`clients/lessonforge-app`)

One Expo codebase for web, Android and iOS (Expo SDK 57). Read its `AGENTS.md` first: Expo's APIs change every
release, and packages are added with `npx expo install`, not `npm install <pkg>`.

```bash
cd clients/lessonforge-app
npm install
EXPO_PUBLIC_API_URL=http://localhost:5000 npm run web     # live-reloading dev server
npm run typecheck && npm run lint                          # before calling anything done
npm run export:web                                         # build into dist/, which the server serves at /app
```

- **Server address:** the app finds the server from `EXPO_PUBLIC_API_URL`. When the server serves it at `/app`, it
  uses its own address. An Android emulator reaches your machine at `http://10.0.2.2:5000`.
- **Access token:** when the server has `LESSONFORGE_ACCESS_TOKEN`, open the app once with `?token=…` (it is
  remembered), or set `EXPO_PUBLIC_ACCESS_TOKEN` for the dev server.
- **Shared server:** `expo export` into the live `dist/` deletes the bundle a tester's open page still needs. Export to
  a side folder and swap `index.html` last (`CLAUDE.md`, "Publishing a new web build without a gap").

## 6. The lesson API (`src/lessonforge/harness/api.py`, under `/api/harness`)

| route | what |
|---|---|
| `GET /mode` | `{"mode": "studio"}` here; the viewer site on Render answers `viewer` and makes nothing (`DEPLOY_RENDER_VIEWER.md`) |
| `GET /controls` | every switch the pipeline has (models per job, voice, pictures, checks), with its default and allowed values: the "All controls" panel is drawn from it |
| `POST /generate` | start a lesson: `{"brief": {...}, "settings": {control id: value}, "voice": ..., "quality": "m"}` |
| `POST /sessions`, `/sessions/{id}/answer`, `/sessions/{id}/generate` | the question-by-question intake the app uses |
| `POST /script/preview` | read a pasted script back before anything is spent |
| `GET /jobs`, `GET /jobs/{id}` | lessons and their progress; a finished lesson's files are under `/lessons/<job_id>/` |
| `POST /jobs/{id}/voice` | narrate a finished lesson again (no model call) |
| `POST /jobs/{id}/remove` | take a lesson out of the list (it is moved, never deleted) |
| `GET /voices` | voices this server can use |
| `GET /stats` | the dashboard's numbers |

A brief looks like `{"topic": "Why the sky is blue", "audience": "Class 7", "language": "hinglish", "goal": "...",
"duration_minutes": 3}`, or `{"mode": "script", "script": "<your words>"}` for a pasted script. A lesson's own
`settings` are validated against `/controls` (`src/lessonforge/knobs.py`): a new switch is one `Control` there plus
the `knobs.get(...)` that reads it.

## 7. Tests

```bash
.venv/bin/python -m pytest tests/unit -q            # 452 tests, about 15 s
.venv/bin/python -m pytest tests/integration -q     # 15 tests, real renders, 3 to 10 minutes
.venv/bin/python tests/run_engine_checks.py --fast  # the storyboard engine's harnesses, no render
```

- **No network:** a test cannot reach the network, whatever keys are in your shell. `tests/conftest.py` refuses every
  outside request and lists what it refused. A test that needs a model's answer gets a stub; never loosen the guard.
- **Before a restart:** run the integration tests as their own command, never piped into `tail`. A pipe hides a
  failure from `&&`.
- **Browser checks:** the drivers in `tests/browser/` (puppeteer-core) need a running server and Chrome.

## 8. Ways to try a change without making a lesson

- **A finished lesson's screens:** `lessonforge.longform.preview.stills(<lesson folder>)` saves the screen after every
  step as pictures in seconds, with no voice and no money. `scripts/layout_regress.py` does it for every lesson and
  compares against a kept baseline: run it before a change to `longform/runtime.py` or `figures.py`.
- **A model's job:** `scripts/eval_writer.py` scores the writer on frozen briefs (`evals/writer/`; doc 16 explains the
  method). It is paid, so name the cost first.
- **Whole lessons:** run them on a second server with its own `LESSONFORGE_HOME`, so they never enter the shared list
  (`CLAUDE.md`, 2026-10-10).

## 9. Where things are

```
src/lessonforge/
  harness/    the lesson pipeline: intake, writer, critic (review), questions, card, diagrams, annotate, service, api
  longform/   narration first, then the picture: speech, audio, runtime (the renderer), figures, build, preview
  engine/     the older storyboard → Manim engine and the FastAPI app that serves everything
  knobs.py    every per-lesson switch     spend.py   the ledger and the cap     cli.py   the `lessonforge` command
clients/lessonforge-app/    the app
docs/                       design notes and trials; docs/research/approaches/ is numbered by date
evals/                      frozen test sets and scorecards for model choices
scripts/                    public_link.sh, eval_writer.py, layout_regress.py, ...
tests/                      unit · integration · engine · browser · manual
```

## 10. Working on a shared tree

- Commit on a branch and open a pull request. Never commit `.env`, `lessonforge_workspace/` or lesson builds:
  `.gitignore` covers them, so check `git status` before `git add`.
- Several people and AI sessions edit this tree. Look at recent file times before starting on something, and say
  which files you are taking.
- A rule earns its place in `CLAUDE.md` only with what taught it. Read the sections near the part you change before
  changing it: most of them record a real failure.
