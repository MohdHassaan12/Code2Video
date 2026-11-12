# Video pipeline — usage guide

How to set up, generate videos (single, debugged, or in bulk), control the
language, and tune the pipeline. For the design itself see
[video_pipeline.md](video_pipeline.md); for improvement priorities see
[pipeline-roadmap.md](pipeline-roadmap.md).

## 1. Setup (Linux)

```bash
python3 -m venv .venv                       # `python` is not on PATH; use python3
.venv/bin/pip install -r stem_animation_lab/requirements.txt
```

API keys live in `stem_animation_lab/.env` (`GEMINI_API_KEY`,
`OPENROUTER_API_KEY`, `GROQ_API_KEY`; no SARVAM key ⇒ TTS falls back to Gemini
TTS via OpenRouter). `ce/agents.py` reads `OPENROUTER_API_KEY` **at import
time** — load the .env before importing anything under `ce/`.

Start the lab server (everything talks to it):

```bash
cd stem_animation_lab && ../.venv/bin/uvicorn app:app --port 5000
```

After editing `app.py`, restart the server — a running uvicorn keeps old code.

| Page | URL | What it is |
|---|---|---|
| Lab index | `http://localhost:5000/` | Single-video playground |
| Render timeline | `http://localhost:5000/timeline` | Every rendered video, newest-first, with Clean / Repaired ×N / ⚠ overlaps / Raw badges |
| **Bulk generation** | `http://localhost:5000/bulk` | Queue many topics; resumable manifest-driven runs |
| Debugger | `http://localhost:8502/` | Streamlit sandbox (see §5) |

## 2. Why are my videos in Hindi? (language settings)

Narration language is decided by **three layers**; the first one that sets a
value wins:

1. **Per-node `videoSpec`** in the lesson JSON: `{"language": "en-IN", "persona": "en", "speaker": "...", "style": "..."}`
2. **Environment variables** (run-wide defaults for the `ce/` pipeline):
   `VIDEO_LANGUAGE`, `VIDEO_PERSONA`, `VIDEO_SPEAKER`, `VIDEO_STYLE`
3. **Hardcoded fallbacks** in [`ce/stem_animation.py`](../ce/stem_animation.py):
   `language="hi-IN"`, `persona="hybrid"` — **this is why everything defaults
   to Hindi/Hinglish narration.** The lab server's own request models default
   to `hi-IN` too, so a bare API call without a `language` field gets Hindi.

**In the lab web UI** (`http://localhost:5000/`) the left panel now has explicit
**Language Persona**, **Voiceover Language**, **TTS Provider**, and **Voice
Narrator** dropdowns (the Voice list repopulates from the language + provider).
Before, the playground sent none of these and silently used the `hi-IN`/`hybrid`
server defaults — so pick them there instead of setting env vars or hand-editing
the API call. (These controls also feed the codegen + compile requests.)

So, for English videos from the lesson pipeline:

```bash
VIDEO_LANGUAGE=en-IN VIDEO_PERSONA=en python3 -m ce.videos_build ...
```

**Persona** controls the narration style, not just the language:

| Persona | Narration (voiceover) | On-screen text |
|---|---|---|
| `en` | Plain English | English |
| `hybrid` (default) | Code-mixed "Hinglish" — native-script sentences with English STEM terms, later transliterated to Latin script for TTS | English (a sanitizer strips any Indic characters from `Text(...)`) |
| `native` | Fully in the selected language's native script | Native script allowed on screen |

If you see Devanagari **on screen** (not just hear Hindi), the persona was
`native` — with `en`/`hybrid` the codegen sanitizer removes Indic characters
from on-screen `Text()` elements.

**Technical terms in narration** (`tech_terms`, since 2026-07-22) controls how
STEM vocabulary is *spoken* — it kills the "point... yaani bindu" double-speak
where a term said in English was re-said in the native language. Resolution
follows the same three layers: per-node `videoSpec.tech_terms` →
`VIDEO_TECH_TERMS` env → default `english`. It also has its own dropdown in the
lab UI ("Technical Terms in Narration"), the bulk UI, and the debug sandbox.

| `tech_terms` | Behavior |
|---|---|
| `english` (default) | Technical terms are spoken in English only — never translated or restated in the native language ("coordinate plane" stays "coordinate plane") |
| `bilingual` | First mention gives the native equivalent once ("point, yaani bindu"), English-only afterwards — a deliberate teaching aid |
| `native` | Technical terms are translated where a standard native term exists |

It only shapes narration under `hybrid`/`native` personas (persona `en` is
all-English already) and is enforced at the storyboard prompt plus the
transliteration pass, which drops a redundant native duplicate of a term the
sentence already says in English.

Languages: `en-IN`, `hi-IN`, `bn-IN`, `ta-IN`, `te-IN`, `kn-IN`, `ml-IN`,
`mr-IN`, `gu-IN`, `pa-IN`, `od-IN`.

## 3. Generate a single video (API)

```bash
# 1. Storyboard
curl -s localhost:5000/api/generate_storyboard -H 'Content-Type: application/json' \
  -d '{"topic": "Photosynthesis", "language": "en-IN", "persona": "en"}' > sb.json
# 2. Code
curl -s localhost:5000/api/generate_code -H 'Content-Type: application/json' \
  -d "{\"storyboard\": $(cat sb.json), \"language\": \"en-IN\", \"persona\": \"en\"}" > code.json
# 3. Render (async — poll the job)
curl -s localhost:5000/api/compile_video -H 'Content-Type: application/json' \
  -d "$(python3 -c "import json;d=json.load(open('code.json'));print(json.dumps({'code':d['code'],'scene_class':d['scene_class'],'scene_scripts':d.get('scene_scripts'),'quality':'l'}))")"
curl -s localhost:5000/api/render_status/<job_id>
```

Always pass `scene_scripts` to `compile_video` when `generate_code` returns
them — they unlock the parallel per-scene render and scene-scoped overlap
repair; without them every video takes the sequential single-script path.

`compile_video` (and `batch_render_and_merge`) also accept an optional
`env_overrides` object to retune the repair loop per job, allowlisted to:
`OVERLAP_REPAIR`, `OVERLAP_REPAIR_ROUNDS`, `LAYOUT_STRICT`, `PARALLEL_RENDER`,
`PARALLEL_RENDER_WORKERS`, `LAYOUT_REVIEW`. (These set process env — last
submission wins across concurrent jobs; meant for single-user debug/bulk use.)

### Grounding the storyboard in real sources (deep path)

By default the storyboard is written from the topic string alone. To ground it in
actual material — and to get the multi-agent path (screen plan → one writer per
screen), which is what makes scenes dense and connected — set `DEEP_STORYBOARD=1`
in `stem_animation_lab/.env` (or the process env) and pass `sources`:

```bash
# Inspect what would be ingested — costs NO LLM call:
curl -s localhost:5000/api/research -H 'Content-Type: application/json' -d '{
  "topic": "Projectile motion",
  "sources": ["https://youtu.be/SOME_VIDEO_ID",
              "https://en.wikipedia.org/wiki/Projectile_motion",
              "Paste raw notes here — anything that is not a URL is treated as text."]}'

# Then generate against the same sources:
curl -s localhost:5000/api/generate_storyboard -H 'Content-Type: application/json' -d '{
  "topic": "Projectile motion", "language": "en-IN", "persona": "en",
  "sources": ["https://youtu.be/SOME_VIDEO_ID"]}'
```

Studio has the same thing in the brief (**Source material** + **Check sources**).
A source that fails (transcript disabled, dead link) becomes a warning and the rest
still generate — grounding never fails a video.

**Cost:** the deep path spends 1 ideator call + 1 call per screen instead of a single
call, which is why it is off by default. The board is cached against the *source
digest*, so re-running the same topic with the same sources costs nothing and editing
a source regenerates automatically.

**Simulations and drawn objects:** boards may carry `type: "simulation"` elements (a
projectile arc, a wave, an orbit) — the server writes and *verifies* real Manim
animation code for each and caches it per description. Since 2026-08-15 the same
generator also **draws** `svg_icon` and `shape` objects instead of importing clipart or
stamping a fixed primitive (`DRAW_WITH_MANIM=1`, on by default), so the frame carries
real geometry the theme can colour and the layout can place. One call per distinct
description, cached forever; anything that cannot be drawn or verified falls back to the
old icon cascade and shows up in `asset_warnings`.

## 4. Bulk generation

Modeled on the NotebookLM bulk tool: a JSON **manifest is the source of
truth**, every stage artifact is cached on disk, and a dead run **resumes from
its last completed stage with zero re-billed LLM calls**.

**Web UI** — `http://localhost:5000/bulk`: paste topics one per line, pick
language/persona/quality/repair settings, *Dry run* to see the plan (spends
nothing), *Start* to run. Rows show per-stage status live; failed rows get a
one-click *Retry failed* that reuses cached storyboards/code.

**CLI** — `stem_animation_lab/bulk_runner.py` (server must be running):

```bash
# Plan file: JSON {settings, topics} or plain .txt (one topic per line)
cat > plan.json <<'EOF'
{"settings": {"language": "en-IN", "persona": "en", "quality": "l", "parallel": 2},
 "topics": ["Photosynthesis", {"topic": "Ohm's Law", "grade": "10"}]}
EOF
.venv/bin/python stem_animation_lab/bulk_runner.py plan.json --dry-run   # plan only
.venv/bin/python stem_animation_lab/bulk_runner.py plan.json             # run
.venv/bin/python stem_animation_lab/bulk_runner.py --resume bulk_20260720_1  # continue a dead run
```

State lives in `stem_animation_lab/bulk_runs/<run_id>/` (git-ignored):
`manifest.json` plus per-topic `storyboard.json` / `code.json` stage caches.
Videos render into the lab's `static/videos/` with `.mp4.json` sidecars, so
they also appear on `/timeline`. `--force` ignores all caches.

## 5. The debugger (stem animation sandbox)

Streamlit app at `debug_sandbox/sandbox_app.py`, port 8502:

```bash
.venv/bin/streamlit run debug_sandbox/sandbox_app.py --server.port 8502
```

It traces the pipeline stage-by-stage (storyboard JSON → generated code →
per-round compile logs with crashed-line highlighting → cost/latency
telemetry) and has a manual code editor + recompile panel.

Sidebar settings:
- **Language / TTS provider / speaker / persona / style / background** — flow
  into the storyboard + codegen requests.
- **⚙️ Pipeline Settings** — aspect ratio, and the repair knobs (overlap
  repair on/off, repair rounds, strict layout, parallel scene render) sent to
  the server as `env_overrides`.
- **Compile Path** — *Lab Server (full pipeline)* routes rendering through the
  real `/api/compile_video` (parallel scenes, overlap-repair loop, sidecars,
  `/timeline` history); *In-Process (legacy trace)* compiles inside the
  sandbox with the older 2-round self-heal only, but keeps the richest
  per-round code/log traces. The repair knobs only apply on the server path.

## 6. Environment knob reference

| Var | Default | Meaning |
|---|---|---|
| `VIDEO_LANGUAGE` / `VIDEO_PERSONA` / `VIDEO_SPEAKER` / `VIDEO_STYLE` | `hi-IN` / `hybrid` / `shubh` / 3b1b | Run-wide defaults for the `ce/` lesson pipeline (per-node `videoSpec` still wins) |
| `VIDEO_TECH_TERMS` | `english` | How STEM terms are narrated: `english` (never re-said natively), `bilingual` (native once at first mention), `native` (translated) |
| `OVERLAP_REPAIR` | `1` | Layout probe + LLM repair loop on renders |
| `OVERLAP_REPAIR_ROUNDS` | `2` | Max repair attempts per video/scene |
| `LAYOUT_STRICT` | `0` | Treat remaining layout violations as render failure |
| `PARALLEL_RENDER` | `1` | Render scenes concurrently, concat with ffmpeg |
| `PARALLEL_RENDER_WORKERS` | `4` | Concurrent scene renders per job |
| `RENDER_WORKERS` | `2` | Server-wide concurrent render jobs |
| `TTS_PROVIDER` | `sarvam` | `sarvam` or `gemini` |
| `GEMINI_TTS_MODEL` | gemini-3.1-flash-tts-preview | Model for Gemini TTS fallback |
| `TTS_SHARED_CACHE` / `TTS_SHARED_CACHE_DISABLE` | `.tts_cache/` / off | Cross-render TTS cache (repair re-renders bill zero TTS) |
| `DEEP_STORYBOARD` | `0` | Multi-agent storyboard: sources → screen plan → one LLM call per screen. Costs 1+N calls instead of 1 |
| `SOURCE_AUTO_SEARCH` | `0` | Search the web for sources when none are given (needs `TAVILY_API_KEY` / `SERPER_API_KEY` / `BRAVE_API_KEY`) |
| `SOURCE_MAX_CHARS` / `SOURCE_MAX_COUNT` | `12000` / `6` | Per-source text cap and max sources per request |
| `SCREENS_MIN` / `SCREENS_MAX` | `5` / `8` | Screens the ideator plans per video |
| `SCENE_WRITER_WORKERS` | `4` | Screens written concurrently |
| `SIM_GEN` | `1` | Generate + verify Manim code for `simulation` elements (`0` degrades them to static visuals) |
| `DRAW_WITH_MANIM` | `1` | Manim DRAWS `svg_icon` and `shape` objects (LLM writes verified `build()` geometry) instead of importing clipart or stamping a primitive. `0` restores the old icon cascade + prose→shape table |
| `DRAW_MIN_PARTS` / `DRAW_SHAPE_MIN_PARTS` | `3` / `2` | Complexity floor a drawing must meet — below it, the "drawing" is the placeholder it replaces |
| `DRAW_WORKERS` | `4` | Distinct objects drawn concurrently (one call per distinct description, cached forever) |
| `SIM_GEN_TIMEOUT` / `SIM_GEN_REPAIR_ROUNDS` | `90` / `1` | Verification time limit and repair attempts per simulation |
| `SWEEP_MAX_AGE_HOURS` | `24` | Startup retention for `/timeline` history |
| `BULK_LAB_URL` | `http://localhost:5000` | Lab server URL for `bulk_runner.py` |

## 7. Tests

All run without API keys (LLM stubbed); run from the directory shown.

| Command (from repo root unless noted) | Covers |
|---|---|
| `cd stem_animation_lab && ../.venv/bin/python test_overlap_probe.py` | 32-check probe + both repair loops (real renders) |
| `.venv/bin/python stem_animation_lab/test_axes_zones.py` | Transpiler axes-aware zones + label slots |
| `.venv/bin/python stem_animation_lab/test_event_sanitize.py` | Free-text event sanitization |
| `cd stem_animation_lab && ../.venv/bin/python test_minimize_split.py` | Split-screen screen management |
| `.venv/bin/python stem_animation_lab/test_entrance_map.py` | Entrance-animation vocabulary (per-type + shape-keyword map) |
| `.venv/bin/python stem_animation_lab/test_storyboard_gate.py` | Pre-cache storyboard gate (truncation + hybrid language contract) |
| `.venv/bin/python stem_animation_lab/test_tts_shared_cache.py` | Shared TTS cache billing contract |
| `python test_layout_safety.py` (in stem_animation_lab) | Deterministic viz_helpers layer |
| `.venv/bin/python stem_animation_lab/test_deep_storyboard.py` | Source intake, screen ideator, per-screen writers, deep-path wiring (67) |
| `cd stem_animation_lab && ../.venv/bin/python test_simulation.py` | Generated simulations: safety gate, verification, codegen, real render (66) |

## 8. Troubleshooting

- **Storyboard 500 on JSONDecodeError** → `json_repair` missing from the venv
  (lenient parsing silently degrades to strict `json.loads`).
- **Storyboard 500 mentioning "language-contract violation"** → the model wrote
  English narration or Devanagari on-screen text under `hybrid`; the gate
  rejected it before caching. Re-run the request — a retry usually obeys.
- **Server behaves like your edit didn't happen** → restart uvicorn.
- **Every video renders sequentially / repair never scene-scopes** → the
  client dropped `scene_scripts` from the codegen response.
- **Bulk CLI exits immediately** → lab server not running on port 5000.
- **"Raw" rows on /timeline** → videos without `.mp4.json` sidecars (old
  renders, or a new `compile_manim_code` caller that isn't writing sidecars /
  discarding losers).
