# PIPELINE_WALKTHROUGH — how a topic becomes a finished video

This document walks the video pipeline start to finish, as it actually works in the
code of this working tree (verified 2026-07-28 by reading the code, not the docs;
where docs and code disagree, this document follows the code and says so).

**The system in one paragraph.** This repo turns a school topic ("Photosynthesis",
"Ohm's Law") into a narrated animated video. A large language model (LLM — an AI
text model) writes a scene-by-scene plan called a *storyboard*. Deterministic code —
not the AI — converts that plan into a Python script for Manim (an open-source
animation library). The server renders that script to a video file, synthesizes the
narration audio, measures the result for layout defects, repairs what it can, and
records what happened next to the file. The server is a FastAPI web service in
`stem_animation_lab/app/` on port 5000. Several different clients feed it (Step 1).
The design has two ruling ideas that repeat at every stage: **the AI decides content,
plain code decides structure**, and **a verified artifact is never lost** — every
automatic "improvement" must prove itself better, or it is thrown away and the
original kept.

A note on words used below: *persona* is the narration style (`en` = plain English,
`hybrid` = Hinglish code-mix, `native` = fully native-script); *TTS* is
text-to-speech (turning written narration into audio); *ffmpeg* is the standard
command-line video tool; JSON is the structured-text format all the stages exchange.

---

## Step 1 — A request arrives (all the ways in)

**What comes in:** a topic plus optional settings (language, persona, voice, visual
style, grade, subject, quality).

There are seven distinct entrances, and they do not all send the same fields:

1. **The creator web page** (`stem_animation_lab/static/index.html` + `static/app.js`).
   A form with dropdowns for style, language, persona, technical-term policy, voice,
   and TTS provider. One button runs the whole chain: storyboard → asset check →
   code → compile, then polls the job every 2 seconds. Quirk found in the code: this
   page does **not** send `scene_scripts` or `env_overrides` when compiling
   (`app.js:506-510`), so videos started here always render as one single script —
   the parallel per-scene render path (Step 11) is never exercised from this page.
2. **The bulk web page** (`static/bulk.html`, served at `/bulk`). Sends a topic list
   plus shared settings and repair knobs. Its form defaults to English (`en-IN`).
3. **The bulk command line** (`stem_animation_lab/bulk_runner.py`):
   `python3 bulk_runner.py plan.json [--parallel N] [--dry-run] [--resume RUN_ID]`.
   Its built-in defaults are Hindi (`hi-IN`) / `hybrid` — so the same empty settings
   mean English from the bulk page but Hindi from the CLI (`bulk.html:87` vs
   `bulk_runner.py:53`).
4. **The bulk API** (`POST /api/bulk/start`, `GET /api/bulk/runs`,
   `GET /api/bulk/status/{run_id}`, `POST /api/bulk/retry/{run_id}` — routes live in
   `bulk_runner.py:345-387`).
5. **The lesson pipeline** (`ce/`), described in Step 2. It calls the same three
   endpoints over HTTP. `ce/builder.py:46-51` first pings `GET /health` (2-second
   timeout) and skips video generation if the server is down; the Streamlit lesson
   console's own video button (`app.py:418`) has no such guard.
6. **The debug sandbox** (`debug_sandbox/sandbox_app.py`) — see the side-project
   section at the end.
7. **Raw API calls.** Anyone can POST directly. Defaults then come from the request
   models in `app/schemas.py`: `language="hi-IN"`, `persona="hybrid"`,
   `speaker="shubh"`, `tts_provider="sarvam"`, `quality="l"` (480p),
   `aspect_ratio="widescreen"`.

**API keys** are resolved per request (`stem_animation_lab/dependencies.py:49-91`):
headers `X-Gemini-API-Key` (or `Authorization: Bearer`), `X-OpenRouter-API-Key`,
`X-Groq-API-Key` each fall back to the server's `stem_animation_lab/.env`. The
creator page stores a pasted Gemini key in the browser's localStorage and sends it
as a header, so the server can run keyless for casual use. Background jobs use
environment keys only.

**Why this design:** every entrance funnels into the same three endpoints
(`/api/generate_storyboard` → `/api/generate_code` → `/api/compile_video`), so
quality machinery added to the server automatically covers every client. The
failure this prevents: five clients each growing their own half-correct pipeline.

## Step 2 — (Lesson-pipeline entrance only) deciding what to make

**What comes in:** a lesson JSON with typed nodes (hook, concept, practice, …),
built by the authoring console (see side projects).

**What happens:** `ce/videos_build.py:14` loops the lesson's nodes. For each node,
`ce/video_planner.py` asks an LLM one question — does this node need a video, and
what should it show — and stores the answer on the node as `videoSpec`. Offline
(no key), a deterministic rule answers instead: node types hook/reveal/concept/
simulation/recap get videos (`video_planner.py:48-69`). Nodes that already carry a
`node["video"]` entry are skipped unless the caller forces regeneration
(`videos_build.py:29-33`) — this presence check is the only cache at this layer.
`ce/clip_planner.py` nominally splits a node into clips but is hardcoded to always
return exactly one clip (`clip_planner.py:5-16`), so "merge clips" is in practice a
one-input merge. `ce/stem_animation.py` then resolves settings with a strict
precedence: per-node `videoSpec` field → environment variable (`VIDEO_LANGUAGE`,
`VIDEO_PERSONA`, `VIDEO_SPEAKER`, `VIDEO_STYLE`, `VIDEO_TECH_TERMS`) → hardcoded
default (`hi-IN`, `hybrid`, `shubh`, `3blue1brown/minimalist/neon`, `english`)
(`stem_animation.py:26-33`). The hardcoded tail is why videos default to Hinglish.
Target duration is not trusted from the plan; it is recomputed from narration word
count at a grade-appropriate speaking pace — 90 words/minute up to grade 4, else
150, minimum 20 seconds (`ce/planner_agent.py:42-53`, `stem_animation.py:63-71`).

**What comes out:** one HTTP request per node to the server, carrying the topic,
settings, and a rich `context` (the node's textbook content, a pedagogical plan,
optional source chunks).

**Why:** the precedence chain lets one node, one run, or one machine override
language without touching code. Recomputing duration from words prevents a common
failure: an LLM-invented duration that leaves the animation waiting in silence or
cutting off narration.

## Step 3 — Writing the storyboard (the only truly creative step)

**What comes in:** topic + settings + optional context, at
`POST /api/generate_storyboard` (`app/api/generation.py:14-39`).

**What happens** (`app/storyboard.py:237-517`): the server builds a large prompt —
scene and layout rules, a per-node-type directive (a hook scene is prompted
differently from a recap), the persona's language contract, and the technical-terms
policy (`narration_tech_terms_rule`, `storyboard.py:196-234`: with `english`, a STEM
term said in English must not be re-said in the native language — this kills the
"point, yaani bindu" double-speak). Each scene must include a `composition` field —
a 1–2 sentence layout intent the later stages can read. The call goes through one
shared router, `call_llm_with_fallback` (`app/llm.py:355-389`).

**Providers and fallbacks — how the system picks:** the router walks a provider
list from `LLM_PROVIDER_ORDER`, default **OpenRouter → Gemini → Groq**
(`llm.py:349` — note the docs and module docstrings claim Gemini first; the code
says otherwise). Providers without a key are skipped. Each provider has a per-task
model chain: storyboard-tier chains for OpenRouter default to
`google/gemini-2.5-flash, deepseek/deepseek-v4-pro, meta-llama/llama-3.3-70b-instruct:free`;
Gemini to `gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash`; Groq to
`llama-3.3-70b-versatile, llama-3.1-8b-instant` (all env-overridable). Within
Gemini, a transient 503 is retried up to 3 times with backoff, but a 429 rate limit
fails over to the next model immediately — retrying a throttled model just burns
time (`llm.py:29-72`).

**Three protections against bad output:** (1) the response is parsed with
`loads_json_lenient` (`llm.py:392-405`), which uses the `json_repair` library so a
trailing comma doesn't kill the run; (2) a completion whose `finish_reason` says it
was truncated or filtered is rejected outright and the next model tried
(`llm.py:248-273`) — repaired JSON can *parse* and still be *incomplete*, so
parsing leniency is deliberately paired with completeness rejection; (3) output
tokens are capped (`LLM_MAX_TOKENS`, default 16000) sized so a full storyboard
(~6.3k tokens) fits.

After parsing, two cheap follow-up LLM passes run for `hybrid`: a transliteration
pass (native-script narration → Latin script, which the TTS voices need) and a
label-translation pass (feeds Step 4).

**What comes out:** a storyboard JSON — scenes, each with elements (text, math,
shapes, axes, icons), narration cues, animation events, and a composition line.

**Why:** this is the one place where creativity lives, so it gets the premium
model chain, the multi-provider failover, and the anti-truncation checks. Every
later stage is designed to *not* need this level of trust.

## Step 4 — Healing, then gating the storyboard

**What comes in:** the raw parsed storyboard.

**What happens:** two mechanisms, deliberately layered:

- **Heal first** (`normalize_onscreen_language`, `app/storyboard.py:85-125`): for
  `hybrid`/`en` personas, every on-screen text/math element containing Indic script
  is collected and sent through one LLM translation call. A translation is accepted
  **only** if it is non-empty and the Indic script is actually gone; otherwise the
  original is kept — the code's own comment: never trade a loud failure for a
  silent one. If the translation call itself fails, everything is left as-is.
- **Then gate** (`storyboard_shape_problems`, `app/storyboard.py:32-82`): a pure-code
  checker rejects boards with no scenes, scenes with no narration cues, empty cues,
  cues with unbalanced `[`/`]` brackets (the signature of a response cut off inside
  a pacing tag), on-screen native script under `hybrid`/`en` (nine Indic scripts
  checked), and — for `hybrid` — boards whose narration is entirely plain English
  (the contract says code-mix; one genuine Hinglish cue is enough to pass).
  Rejection raises an error that surfaces as an HTTP 500. There is no automatic
  retry; the caller decides.

**What comes out:** a storyboard that is structurally complete and honors the
language contract — or a loud failure.

**Why the order matters:** the heal is a metered (paid, fallible) AI call; the gate
is free and deterministic. The heal runs first so a fixable board doesn't die; the
gate runs last so a failed heal still cannot ship. And the gate runs **before** the
cache write (next step) so a degenerate board can never be cached and poison two
days of later runs (`storyboard.py:619-631`).

## Step 5 — The storyboard cache (the main cost control)

**What comes in:** the gated storyboard, and — on later requests — the same inputs.

**What happens** (`StoryboardCache`, `app/storyboard.py:131-190`): each result is
stored as a file in `stem_animation_lab/.storyboard_cache/`, keyed by a hash of
nine inputs: topic, persona, language, style, grade, subject, node type, a hash of
any source-content chunks, and the technical-terms policy. A later identical
request returns the file instead of paying for a new LLM call. Entries keyed only
by topic expire after 48 hours; entries carrying a content hash never expire —
if the source content changes, the hash changes and that *is* the invalidation.
Cache reads and writes swallow their own errors: a broken cache degrades to
"generate again", never to "fail the request".

**Why:** storyboard generation is the most expensive call in the pipeline. The key
is exhaustive on purpose — anything that changes the prompt is in the key, because
a cache hit on a stale key would silently serve the wrong language or policy. The
repo's standing rule applies: a cache-key change is a billing change.

## Step 6 — Asset preflight (check before you promise)

**What comes in:** the storyboard's icon and molecule elements (`svg_icon`,
`chemical_molecule`).

**What happens** (`app/assets.py:123-191`, called from
`app/codegen_pipeline.py:17-26`): before any code is written, each such element is
probed over the network in a small thread pool — molecules against RDKit's formula
parser and the PubChem database, icons against the Iconify search service and the
Bootstrap icon set. Probes that fail come back marked `fallback`, and the code
generator's prompt receives an explicit "ASSET FALLBACK SUBSTITUTIONS (REQUIRED)"
section telling it to build those items from native shapes instead of fetching art.

**What comes out:** the same storyboard plus a warnings list, and a codegen prompt
that never promises an asset the render can't fetch.

**Why:** the failure this prevents is a render that dies (or shows a blank) at
minute three because an icon URL 404s. Finding out in a half-second probe is
cheaper than finding out inside a render.

## Step 7 — The Visual Director (optional taste pass, applied by code)

**What comes in:** the storyboard, before any code generation reads it.

**What happens** (`app/pipeline/director.py`, called from
`codegen_pipeline.py:164-169`; off by default, enabled with `VISUAL_DIRECTOR=1`):
two halves with different failure rules.

- **Deterministic half** (`_enlarge_sparse_scenes`): pure code, no AI. A scene with
  at most 4 elements and no axes/graphs gets every element's scale multiplied by
  1.3, clamped at 1.4. This runs even when every AI provider is down.
- **LLM half:** one call ranks element importance and proposes when elements should
  be hidden, highlighted, or spotlighted. The proposals are *not* trusted:
  `_apply_directives` deep-copies the board and applies each proposal only through
  safety gates — never rescale axes or graphs (scale clamped 0.4–1.15), never hide
  something on the final cue, before it appears, while later cues still reference
  it, or while a label is still anchored to it; at most 3 highlights per scene, one
  per cue; at most one spotlight per scene, never sharing a cue with a highlight.
  Everything applied becomes ordinary storyboard events — the downstream code
  needed no new vocabulary, and stripping the directives yields a byte-identical
  board.

If the LLM half fails in any way, the stage logs "stood aside" and returns the
board with only the deterministic half applied.

**What comes out:** the same storyboard, possibly with better pacing directives.

**Why:** this is the house pattern for using AI safely — *the model ranks and
schedules; code applies*. A stage may improve the artifact or stand aside; it may
never block or corrupt it.

## Step 8 — Storyboard to Python: the deterministic transpiler

**What comes in:** the storyboard, at `POST /api/generate_code`
(`app/api/generation.py:42-67` → `app/codegen_pipeline.py:16-250`).

**What happens — engine selection:** there are two code generators, and the choice
is mechanical (`codegen_pipeline.py:171-237`). The **transpiler**
(`stem_animation_lab/transpiler.py`) — a plain-code translator with no AI in it —
runs first and produces a complete Manim script. That script is syntax-checked
(`ast.parse`). If it parses, it is used as-is and the LLM writes nothing. Only if
the transpiler raises or emits invalid syntax does the **LLM code generator** run
(code-tier model chain, temperature 0.1), followed by up to 2 rounds of automatic
syntax repair. The batch and single-scene entrances always use the LLM path.

**What the transpiler actually does** (the clever part — all deterministic):

- **Zones.** The screen is divided into 8 named zones (top/bottom center, four
  corners, left/right center). An element asks for a zone; if it's taken, a
  fallback chain ordered by spatial distance finds the nearest free one; if all are
  taken, elements stack within the zone — and stacking in a bottom zone shifts
  *upward*, into the frame, not off the edge (`transpiler.py:112-131`).
- **Axes awareness.** Before placing anything, the zones that would overlap the
  scene's axes are pre-claimed (`_seed_axes_zones`, `transpiler.py:621-638`), so
  free text routes *around* diagrams by construction. Labels positioned near an
  axis are flipped to the side away from the tick numbers
  (`_fix_label_slots`, `transpiler.py:646-685`). Points that carry data coordinates
  are placed with the axes' own coordinate mapping (`c2p`), so a dot at (2,3) lands
  on the graph's (2,3), not the screen's.
- **Entrances.** Each element type maps to an idiomatic entrance animation (text
  fades, math writes, shapes grow, axes draw), with a keyword pass for shapes
  ("arrow" → GrowArrow) whose match order deliberately mirrors the object-builder's
  precedence so "arrow pointing at X", which builds a dot, doesn't animate like an
  arrow. Ten animation classes are whitelisted; a storyboard override wins only if
  whitelisted (`transpiler.py:164-200`). Animation run-times are derived from the
  narration audio's actual duration, so visuals sync to speech.
- **Split-screen management.** When a cue would pile free-standing text onto an
  on-screen diagram — any math element, or two or more text lines — the diagram is
  shrunk to the left half (scale 0.55) and the text stacked in a right-hand column.
  Never on the first cue (the diagram is still arriving), and labels anchored to
  the diagram don't count (they shrink with it)
  (`_maybe_minimize_diagram`, `transpiler.py:719-760`).
- **Theming** (`stem_animation_lab/theme.py`): the style dropdown resolves to one
  of five themes (3blue1brown, chalkboard, cyberpunk, minimalist-mono, powerpoint).
  A dark theme paints the canvas; uncoloured shapes cycle the theme's palette
  (model-chosen colours are never overridden; text keeps high contrast); highlights
  use the theme accent. A light canvas is only reachable via the `white_canvas`
  background, which forces the light theme and lets the runtime helpers recolour
  default-white text dark. The font is pinned to one family for every theme because
  a font swap changes text metrics and would invalidate the layout measurements of
  Step 10.
- **Two output shapes.** The transpiler emits one **master script** (all scenes in
  one file) *and*, when there are 2+ scenes, a set of **per-scene scripts** for the
  parallel render (Step 11). Per-scene scripts are isolated renders from a blank
  canvas, so any animation event that targets another scene's element is dropped
  (with a logged count) — on the master path the same event is legitimate and kept
  (`transpiler.py:1097-1144`). This asymmetry fixed a real incident where 3 of 4
  scenes crashed on cross-scene fade-outs.

**Hygiene:** generated code then passes through `sanitize_generated_code`
(`app/codegen.py:14-151`): hallucinated imports stripped; a selective
`from viz_helpers import X` widened to the star import (a selective import once
silently satisfied an "is it imported?" check and broke renders); oversized font
constants capped; and, for `hybrid`/`en`, any Indic script inside on-screen
`Text(...)` strings stripped (nine scripts, both quote styles — an earlier
single-quote blind spot shipped Devanagari headings). Caveat found in the code:
on the happy path (transpiler output valid, layout review skipped) the sanitizer
is not invoked at all — it only runs inside the repair and layout-review wrappers
(`codegen_pipeline.py:229-241`).

**What comes out:** a complete Python script (plus per-scene scripts), the scene
class name, and asset warnings.

**Why the transpiler exists:** early versions let the LLM write the scene code and
spent enormous effort repairing it. Structure — where things go, how they enter,
when the screen splits — is decidable by rules, so rules decide it. The result is
reproducible output, free codegen on the happy path, and bugs that can be fixed
once in code instead of re-prompted forever. The LLM fallback is kept because a
storyboard the transpiler can't express is better served slowly than not at all.

## Step 9 — Submitting the render job

**What comes in:** code + scene class + quality/aspect + optional per-scene scripts
and `env_overrides`, at `POST /api/compile_video`
(`app/api/render_routes.py:21-50`).

**What happens:** the code is sanitized and syntax-checked *before* anything is
queued — invalid code gets an immediate HTTP 400 rather than a doomed render. A
short job id is minted, the job is placed on a thread pool of `RENDER_WORKERS`
(default 2) render workers, and `202 {job_id}` returns at once. Callers watch
progress via `GET /api/render_status/{job_id}` or the WebSocket
`/ws/render_status/{job_id}`, which pushes the job state every second. The job
registry is a bounded in-memory store (50 jobs; oldest finished pruned).
`env_overrides` lets a caller flip repair knobs per request — but only keys on an
allowlist of 11 (`app/config.py:16-40`); anything else is logged and ignored, and
the override is process-global last-writer-wins (a single-user debug affordance,
by design).

**Why:** renders take minutes; the queue keeps the API responsive and the worker
cap keeps a bulk run from launching twenty simultaneous Manim processes. The
fast-fail syntax check prevents the most wasteful failure: spinning up a renderer
to discover a typo.

## Step 10 — The measurement rehearsal (dry run)

**What comes in:** the render job, before the real render.

**What happens** (`compile_manim_code`, `app/render.py:465-527`; on by default,
`DRY_RUN_ENABLED=0` disables): the script is copied and instrumented with a probe
(`_OVERLAP_PROBE_SNIPPET`, `render.py:95-298`) that monkeypatches Manim's
`Scene.play`, so after **every animation beat** the scene is measured. Narration is
stubbed with a fake half-second timer, so the rehearsal costs no TTS money and
little time; Manim runs in `--dry_run` mode (no frames written; 300-second cap).
Three violation classes are measured, each printed as a parseable
`LAYOUT_VIOLATION:` line to stdout:

- **overlap** — two visible text objects whose boxes intersect by ≥15% of the
  smaller one;
- **off-frame** — text only 5–85% visible at the frame edge (fully off-screen is
  allowed: it's parked for a slide-in);
- **text-over-shape** — a diagram's stroke path crossing a text box.

Backdrop grids are exempt; near-invisible objects (opacity below 0.3, measured
family-aware because `MathTex` reports 0.0 at top level) are skipped; reports cap
at 12. With `LAYOUT_STRICT=1` any violation aborts the job; by default (0) the
violations ride along as input to Step 12.

**What comes out:** the violation list for this exact script.

**Why:** prompts cannot guarantee layout — only measurement can. The stdout-marker
pattern (`LAYOUT_VIOLATION:` lines from the subprocess) is the house channel for
getting structured facts out of a child process, and the same pattern is reused for
voice degradation (Step 11) and vision findings (Step 13).

## Step 11 — The real render, and the voice chain inside it

**What comes in:** the script (or per-scene scripts) plus the violation list.

**Engine selection:** if per-scene scripts exist (2+ scenes) and `PARALLEL_RENDER`
isn't 0, scenes render **concurrently** — up to `PARALLEL_RENDER_WORKERS` (default
4) at once (`_render_scenes_parallel`, `render.py:805-843`) — and the clips are
joined by ffmpeg in stream-copy mode (no re-encode, no quality loss,
`render.py:846-883`). If any scene fails, the successful clips are deleted and the
whole job falls back to the sequential single-script render. Each Manim process is
killed after `RENDER_TIMEOUT_SECONDS` (default 600).

**Narration happens inside the render.** Generated scripts speak through
`UniversalTTSService` (`stem_animation_lab/viz_helpers.py:989-1108`), which walks a
fallback chain: the primary provider (Sarvam by default; Gemini if selected) → a
Gemini TTS route via OpenRouter → **keyless Google-Translate TTS** (`gTTS`, no
account needed, on by default) → optional silence (`TTS_SILENT_FALLBACK`, default
**off** — a failed render gets retried; a silent video would get published).
Details that matter:

- **Retry before failover** (`_tts_post_with_retry`, `viz_helpers.py:755-787`):
  transient shapes — 5xx, 429, timeouts, and the observed-in-production "HTTP 200
  with an empty body" — are retried (default 3 attempts, linear backoff) before
  moving down the chain; a 401 fails fast because retrying a bad key is pointless.
- **Degradation is never silent, but never false either:** every fallback hop
  prints `TTS_DEGRADED: <tier>` to stdout, counted into the video's metadata
  (Step 14). Except: a hop from a provider that was *never configured* (this box
  has no Sarvam key by design) is expected routing, not degradation — otherwise
  the health counter would fire on 100% of healthy runs and mean nothing
  (`_tts_config_absent`, `viz_helpers.py:737-740`).
- **The shared voice cache** (`.tts_cache/` at the repo root,
  `viz_helpers.py:925-1040`): audio is keyed by a hash of the *requested* voice
  configuration plus the exact text — not by which provider actually produced it —
  so a repair re-render of the same narration bills **zero** TTS calls, and a clip
  synthesized by a fallback still satisfies future identical requests. Writes are
  atomic (audio file first, then the metadata file as the commit marker) so
  parallel scene renders can't read half-written entries. Any cache failure
  degrades to "synthesize again", never to a failed render.
- **A trap encoded in the code:** the repo monkeypatches manim-voiceover's
  `GTTSService` to route into `UniversalTTSService`, so the keyless gTTS tier
  imports the raw `gtts` package directly — going through the patched class would
  recurse into the very chain that is failing (`viz_helpers.py:1117-1144, 1249-1263`).

**What comes out:** an mp4 in `stem_animation_lab/static/videos/`, plus full logs.

**Why:** the chain ends keyless on a different vendor and network path, so no
single provider outage can stop production. The cache exists because repair loops
(next step) re-render the same narration repeatedly; without it, every repair
round would re-bill the entire voice track.

## Step 12 — When it fails, classify; when it's ugly, repair — but never lose the original

**Failure classification first** (`_classify_render_failure`,
`render.py:357-382`): failure logs are matched against marker lists and classed as
`infra` (TTS outage, network, rate limit), `latex` (formula typesetting), or
`code`. An `infra` failure **fails loudly and names the failing system** — it never
reaches the AI repair agent, because the agent would "fix" a script that was never
broken and re-render straight into the same outage (this happened live; the
classifier is the fix). In the code as written, `latex` failures *do* still reach
the repair agent (the guard excludes only `infra`, `render.py:1202`) — the
docstring claims otherwise; the code wins.

**Syntax/runtime self-heal:** a `code`-classed failure goes to the LLM repair agent
(`repair_code_with_gemini`) for up to 2 rounds, each attempt re-rendered.

**Overlap repair — the accept-if-better loop:** if the render succeeded but Step
10 measured violations, the violation lines (only them, with an explicit "do not
change the narration or teaching flow" brief, `_overlap_error_report`,
`render.py:624-644`) go to the repair agent, and the result is re-rendered. The
candidate is accepted **only if it renders AND strictly reduces the violation
count**; otherwise it is rejected. Two implementations share this contract:
per-scene (`_repair_scenes_parallel`, `render.py:886-969` — only flagged scenes
re-render, then one re-join) on the parallel path, and whole-video
(`_repair_overlaps`, `render.py:647-703`) on the sequential path. Default budget:
`OVERLAP_REPAIR=1`, `OVERLAP_REPAIR_ROUNDS=2`.

**Loser hygiene:** every rejected candidate, superseded original, and orphaned clip
is explicitly deleted (`_discard_video`, `render.py:600-621`, sidecars included).
Before this rule, rejected attempts piled up in the videos folder and appeared on
the timeline as fake "Raw" entries.

**Why:** "accept only if measurably better" turns a fallible AI into a safe
optimizer — the worst case of any repair round is the video you already had. This
is the repo's most important invariant, and both vision repair (Step 13) and any
future enhancement pass are required to copy it.

## Step 13 — Vision QA (a second opinion with eyes)

**What comes in:** the finished video. Off by default; `VISION_QA=1` enables
(`app/pipeline/vision_qa.py`).

**What happens:** ffmpeg extracts `VISION_QA_FRAMES` (default 6) evenly spaced
frames, downscaled to 640px. One multimodal LLM call (cheap vision-model chain,
OpenRouter) reviews them against a rubric. Findings are only accepted from a fixed
whitelist of 7 classes (clipped-text, colliding-text, unreadable-text, crowding,
dead-frame, low-contrast, broken-hierarchy); each is emitted as a
`LAYOUT_VIOLATION: vision-<class>` line whose `vision-` prefix guarantees the
geometric counter of Step 12 never counts it — opinions and measurements are kept
in separate ledgers. On the sequential path one repair round may run, accepted only
if the candidate renders, does **not** increase the measured geometric violations,
and a fresh critique finds strictly fewer issues. On the parallel path findings are
attributed to individual scene clips by timestamp arithmetic over clip durations;
only flagged scenes re-render, and acceptance is judged once at the re-joined
video (a critique is a paid call, so it isn't spent per scene). The critic "stands
aside" on any failure — a broken critic never blocks a good video.

**Why:** the geometric probe measures boxes; it cannot see "this frame is
unreadable mush". The vision pass catches what rulers can't, under the same
never-lose-the-original contract.

## Step 14 — Records, serving, and cleanup

**What happens:** next to every finished mp4, a JSON *sidecar*
(`<video>.mp4.json`, `app/jobs.py:67-77`) records the job id, repair rounds,
violations remaining, animation beats, vision findings, voice degradation count,
and (parallel path) which scenes were repaired. `GET /api/video_history` scans the
video folders newest-first, attaches sidecar data, and feeds the `/timeline` page,
where each video wears a badge — Clean, Repaired ×N, ⚠ overlaps, or Raw (no
sidecar). Per-render scratch (scripts, media dirs) is deleted on success; on
failure the script is kept for debugging. A startup sweep deletes videos and
scratch older than `SWEEP_MAX_AGE_HOURS` (default 24) — but note: the sweep is
wired only into `python -m app` (`app/__main__.py:15`); launching with
`uvicorn app:app` (the documented command) never runs it.

**Why:** the sidecar is the evidence trail. When a video looks wrong, the first
question is *which stage let it through* — storyboard, code, render, or repair —
and the sidecar plus logs answer it without guesswork. A video without a sidecar
is visibly "Raw" instead of silently unaudited.

## Step 15 — Back on the client: download, merge, bookkeeping

**What happens** (`ce/stem_animation.py:200-260`, `ce/video_merger.py`): the
lesson-pipeline client waits on the WebSocket push (or 2-second HTTP polling if the
websocket library is missing — with no overall timeout), downloads the mp4 into
`generated_videos/`, and hands the clip list to the merger. The merger writes an
ffmpeg concat list and joins clips in stream-copy mode; if a `bgm.mp3` exists in
any of four searched locations, it is looped under the narration at 8% volume
(video stream still copied; audio re-encoded). The final path is written onto the
lesson node as `node["video"]`, and the caller saves the lesson JSON. On rebuilds,
`ce/builder.py:197-207` carries existing `video`/`videoSpec` entries over to the
new lesson so paid work survives regeneration.

**Why:** stream-copy joining is instant and lossless. The carry-over plus the
node-level skip is the lesson layer's whole caching story — crude (presence-based,
not content-based) but enough to make "rebuild the lesson" not mean "re-pay for
every video".

## Step 16 — Bulk production (the resumable assembly line)

**What happens** (`stem_animation_lab/bulk_runner.py`): a run is a directory
`bulk_runs/<run_id>/` whose `manifest.json` (written atomically — temp file +
rename, under a lock) holds one row per topic with a status
(`pending → storyboard → codegen → render → done | failed`). Each topic gets a
folder with two stage caches: `storyboard.json` and `code.json`. Every stage is
cache-first: on resume (`--resume`, or the retry endpoint), finished rows are
skipped and cached stages load from disk, so a run that died mid-way resumes with
**zero re-billed LLM calls** — only unfinished renders re-run. Topics run in a
small thread pool (default 2), but the real throttle is the server's own 2-worker
render pool: excess compile jobs simply queue. A `--dry-run` prints what would run
and spends nothing. Rendered videos land in the normal folder with sidecars, so
bulk output appears on `/timeline` like everything else.

**Why:** bulk is where cost discipline pays or fails. The manifest-plus-stage-cache
design means a crash, a rate limit, or an overnight kill costs render time only,
never a second storyboard bill.

---

## Separate side projects in this repo

These share the repo (and some share the store) but are not part of the main
topic-to-video pipeline above.

### The lesson authoring console (root `app.py` + the lesson side of `ce/`)

A Streamlit app (port 8501) implementing ingest → store → sectioner → builder for
written lessons. Ingest is deliberately AI-free (`ce/ingest.py`): chapters split on
`##` headings, paragraphs packed into ~600-character chunks, `[[page:N]]` markers
preserved so every concept can cite its source page. The store (`ce/store.py`) is a
filesystem layout plus SQLite index under `content_store/`, with an optional
MongoDB backend selected by `CE_MONGO_URI`. Agent 1 (`ce/sectioner.py`) proposes a
concept list a human can edit; Agent 2 (`ce/builder.py`) fans out ten specialist
part-writers (hook, misconception, concept, practice, recap, …), assembles a node
graph, and validates it against a strict schema (`ce/schema.py`) — including a
"no dead ends" check that every answer-gated node is escapable. The single model
seam is `ce/agents.py:complete_json`: with no API key it returns None and every
agent uses a deterministic stub, so the whole pipeline runs offline for free; with
a key it fails loudly rather than silently stubbing. Export is a zip of the
validated `lesson.json`. A knowledge-graph import path exists
(`ce/kg_import.py`), deduplicating snapshots by manifest hash. This console is what
produces the lessons that enter the video pipeline at Step 2. (`ce/video.py`, a
YouTube search curator, is unrelated to the animation flow despite the name.)

### The debug sandbox (`debug_sandbox/`)

A second Streamlit app (port 8502) for taking the pipeline apart. It runs the three
stages one at a time against real textbook nodes or custom scripts, with two
compile paths: "Lab Server" (the real `/api/compile_video`, with repair loops and
sidecars — repair knobs sent as `env_overrides`) and "In-Process legacy trace"
(bypasses overlap repair *by design*, but keeps per-round code and log traces).
Every run is recorded to `debug_traces/trace_<job>.json` by
`trace_logger.py` — payloads, each repair round's code and logs, per-stage timings,
and per-stage cost in tokens, dollars, and rupees, including TTS characters.
`error_analyzer.py` extracts the crashing line from a Manim traceback and, when a
model is available, asks it for a ≤3-sentence explanation (deterministic one-liner
otherwise). A manual editor lets you fix code by hand and recompile with zero LLM
calls.

### The student portal (inside the lab server, separate from the pipeline)

Two endpoints (`app/api/content.py`) build a 3-slide personalized mini-course from
a topic plus a student's stated interest, each slide with its own animation and an
AI-generated interactive widget. Widgets render in a sandboxed iframe
(`sandbox="allow-scripts"`, strict content-security policy, no network) and fall
back to a built-in keyword simulation if generation fails.

### Frozen and stale corners

`stem_animation_lab/app_legacy.py` is the pre-split 3995-line server, frozen and
never imported — a reference copy only. The image-generation scripts
(`scripts_*imagegen*.py` and friends), interaction galleries, question galleries,
and personalization design are **stale workstreams** — present, unmaintained, and
out of scope per the standing focus note. There is no Docker or docker-compose
anywhere; the launchers are PowerShell scripts (`run_app.ps1`,
`debug_sandbox/run_sandbox.ps1`) plus the documented `uvicorn app:app --port 5000`
for the server, and a `.devcontainer` that boots the Streamlit console. A
`cloudflared` tunnel binary sits in the root for exposing the local server but is
not wired into any script.

---

## Where the code disagrees with the docs (found while writing this)

The working tree is the source of truth; these are the places the docs (or the
code's own comments) say otherwise:

1. **Default provider order** is `openrouter, gemini, groq` (`app/llm.py:349`).
   README, CLAUDE.md, and the module's own docstring all say Gemini first.
2. **LaTeX-classed failures reach the AI repair agent.** The guard excludes only
   `infra` (`app/render.py:1202`); the docstring and CLAUDE.md claim only `code`
   is repaired. The batch path (`_run_batch_render_job`) never classifies at all.
3. **The startup retention sweep only runs under `python -m app`** — the
   recommended `uvicorn app:app` launch never calls it (`app/__main__.py:15`).
4. **Latent bug:** `transpiler.py` calls `logger.info(...)` for its
   `[COMPOSITION]` lines (`transpiler.py:857, 1201`) but never imports or defines
   `logger`. A storyboard scene with a `composition` or `layout_template` value
   therefore raises a NameError inside the transpiler, which the pipeline catches
   — silently demoting that request to the slower LLM code generator and losing
   the parallel per-scene render.
5. **The sanitizer is skippable.** On the transpiler-valid path with layout review
   skipped, `sanitize_generated_code` never runs (`codegen_pipeline.py:229-241`),
   though docs present it as an always-on layer.
6. **The creator web page never sends per-scene scripts**, so the parallel render
   and scene-scoped repair paths are exercised only by the bulk, lesson-pipeline,
   and sandbox entrances (`static/app.js:506-510`).
7. Small ones: CLAUDE.md's `_run_parallel_render` is actually
   `_render_scenes_parallel`; the "default 720p" comment in `render.py:448-452` is
   dead (the API default is `"l"`/480p); the stem lab README still describes the
   voice system as plain gTTS; bulk UI defaults to English while bulk CLI defaults
   to Hindi.

---

## The whole flow in one breath

A topic enters through one of seven doors and lands on the lab server, where an AI
writes a scene-by-scene storyboard that is immediately healed, gated by a
deterministic checker, and cached against a nine-part key so it is never paid for
twice; assets are probed before they are promised; an optional director pass lets
an AI *suggest* pacing that plain code then *applies* through safety gates; a
deterministic transpiler — not the AI — turns the storyboard into Manim code
(zones, entrances, split-screens, themes), falling back to an LLM only when it
must; the render queue rehearses the script with narration stubbed to measure text
overlaps beat by beat, renders scenes in parallel and stream-copies them together,
speaks through a four-tier voice chain that retries transient blips, ends keyless,
caches every clip, and marks every degradation; failures are classified so
infrastructure outages fail loudly instead of being "repaired"; measured layout
violations and optional vision critiques drive repair loops that accept a fix only
if it provably improves the video and delete every loser; the result ships with a
metadata sidecar onto the timeline, gets downloaded, background-scored, and
stitched into the lesson by the client, and at scale the bulk runner's
manifest-and-stage-cache design guarantees that a crashed overnight run resumes
without re-billing a single AI call.
