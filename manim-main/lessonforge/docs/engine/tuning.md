# Tuning the video pipeline AFTER generation (not by regenerating)

Audited 2026-07-30 by tracing every knob to its read site and every cache to its
key. The point of this doc: **most tuning does not require regenerating the
storyboard** — the pipeline has a cache ladder that makes downstream re-runs
nearly free, and knowing which tier a knob lives in is the difference between a
₹0 re-render and re-billing every LLM + TTS call.

## The cache ladder (why post-gen tuning is cheap)

| Layer | Where | Key | What a hit saves |
|---|---|---|---|
| Storyboard cache | `stem_animation_lab/.storyboard_cache/sb_<sha>.json` (`app/storyboard.py:128-190`) | `[topic, persona, language, style, grade, subject, node_type, content_hash, tech_terms]`; 48 h TTL, **infinite TTL when grounded** | The storyboard LLM call (~6.3k tokens) |
| Bulk stage caches | `bulk_runs/<run_id>/<key>/storyboard.json` + `code.json` (`bulk_runner.py:186-227`) | file existence only; `--force` busts | Storyboard AND codegen per topic; `--resume` re-bills zero |
| Deterministic transpiler | `transpiler.py` — sole full-scene codegen path | n/a — it's code, not a model | Codegen is **free** on the normal path (LLM codegen only fires if the transpiler fails, `codegen_pipeline.py:179-213`) |
| Shared TTS cache | `.tts_cache/` at repo root (`viz_helpers.py:925-985`) | `sha256(provider, model, speaker, language, raw cue text)` | All audio — a re-render with unchanged cue text bills **zero** TTS |
| Manim frame cache | per-render `media_*` (`app/render.py:450`) | scene content | Unchanged scenes reuse frames across repair rounds |

Consequence: **narration text is the expensive substance** (storyboard tokens +
TTS seconds). Everything downstream of the storyboard — codegen, layout, theme,
render, repair — can be re-run against a cached board for Manim CPU only.

## Tuning tiers — what re-runs when you change each module

### Tier 0 — post-render, nothing re-renders
| Module / knob | Where |
|---|---|
| BGM mix level / presence | `ce/video_merger.py:41` (`volume=0.08`), search paths `:24-30` |
| Vision QA as *measurement* (findings → sidecar, no repair) | `VISION_QA=1` + `VISION_QA_REPAIR=0` (`app/render.py:746`) |
| `VISION_QA_FRAMES`, `VISION_QA_MODELS` | `vision_qa.py:151`, `app/model_routing.py` (chain) |
| Timeline/sidecar retention `SWEEP_MAX_AGE_HOURS` | `app/__main__.py:15` (boot-read) |

### Tier 1 — re-render only (storyboard + code + audio all cached)
| Module / knob | Where | Notes |
|---|---|---|
| `quality` (`l`/`m`/`h`), `aspect_ratio` | `app/render.py:448-456` | ce hardcodes `"l"` — see Traps |
| `OVERLAP_REPAIR`, `OVERLAP_REPAIR_ROUNDS`, `LAYOUT_STRICT` | `app/render.py:659-665, 899-911, 514` | allowlisted for `env_overrides` |
| `PARALLEL_RENDER`, `PARALLEL_RENDER_WORKERS` | `app/render.py:1114, 816` | allowlisted |
| `VISION_QA_REPAIR`, `VISION_QA_REPAIR_ROUNDS` | `app/render.py:746-755` | allowlisted |
| `RENDER_TIMEOUT_SECONDS` | `app/config.py:52` | import-time read — needs restart |
| TTS resilience: `TTS_RETRY_ATTEMPTS/BACKOFF`, `TTS_KEYLESS_FALLBACK`, `TTS_SILENT_FALLBACK` | `viz_helpers.py:721-1100` | server env, not allowlisted |
| Probe thresholds (`_OVL_MAX_REPORTS=12`, opacity/slack constants) | `app/render.py` probe snippet | code constants |

### Tier 2 — codegen + render (still zero LLM/TTS re-bill on the normal path)
The transpiler is deterministic, so this tier costs the same as Tier 1 plus a
free code pass — this is where most *visual* tuning lives:
| Module / knob | Where |
|---|---|
| Beat timing map `_TIMING` (fraction-of-beat, floors) | `transpiler.py:135-157` |
| `wait_time` handling, inter-scene FadeOut 0.5s, focus hold 0.3s | `transpiler.py:854-871, 1049` |
| Zones, label slots, split-screen trigger, z-order, entrance map | `transpiler.py` (`_SAFE_ZONE_MAP`, `_fix_label_slots`, `_maybe_minimize_diagram`, `_ENTRANCE_CONFIG`) |
| Theme (canvas/palette/accent per style profile) | `theme.py` |
| Visual Director (`VISUAL_DIRECTOR`, sparse-scene boost, scale tiers) | `app/pipeline/director.py` — the LLM ranking half is one metered `task="general"` call |
| `speaker`, `tts_provider`, `gemini_tts_model` | baked into generated code (`codegen_pipeline.py:57-78`) — **changing voice re-bills TTS** (cache keys on voice) |
| `LAYOUT_REVIEW` / `skip_layout_review` | `app/codegen.py:363`, `codegen_pipeline.py:240` — metered when on |

### Tier 3 — full regeneration (storyboard LLM + TTS re-billed)
| Module / knob | Where |
|---|---|
| `topic, persona, language, style, grade, subject, node_type, tech_terms`, grounding text | storyboard cache key (`app/storyboard.py:150-154`) |
| Storyboard prompt constants (scene/cue/element density, `storyboard.py:399-408, 459`) | **prompt text is NOT in the cache key** — see Traps |
| Planner: `MIN_LESSON_SCENES=4`, 25s/scene target, cap 10 | `ce/planner_agent.py:39, 74, 78` |
| Narration pace: `narration_wpm()` (90/150), `[SPEED]` tags (±15%, `viz_helpers.py:1172-1176`) | pace tags are Tier 3 because they live in cue text |

## The cheap tuning loop (the setup)

1. **Single video, knob sweep:** take an existing board from
   `.storyboard_cache/sb_*.json` (or `bulk_runs/<run>/<key>/storyboard.json`),
   POST it to `/api/generate_code` then `/api/compile_video` with
   `env_overrides` for the allowlisted knobs. Cost: Manim CPU only — identical
   cue text hits `.tts_cache/`, the transpiler is free.
2. **Interactive:** the debug sandbox (`debug_sandbox/sandbox_app.py`, :8502)
   drives the same server compile path. It currently exposes only 4 of the 11
   allowlisted knobs (no `VISION_QA*`, `VISUAL_DIRECTOR`, `LAYOUT_REVIEW`,
   `PARALLEL_RENDER_WORKERS` in the UI).
3. **Batch A/B:** `bulk_runner.py --resume <run_id>` with per-run
   `env_overrides` — done rows and cached stages are never re-billed, so a
   settings A/B over the same topics re-renders only.
4. **Evidence:** compare `.mp4.json` sidecars (`violations_remaining`,
   `repair_rounds`, `vision_findings`, `voice_degraded`) — one lever per
   experiment, per the roadmap rules.

## Traps (verified, will silently waste money or hide your change)

- **Prompt and planner changes are invisible until you purge the cache.** The
  pedagogical plan and the prompt text are not in the storyboard cache key —
  editing `MIN_LESSON_SCENES` or `storyboard.py`'s density rules returns the
  stale cached board on the next run. `rm -rf stem_animation_lab/.storyboard_cache/`
  (and the bulk run's `storyboard.json`) or the experiment measures nothing.
  (The missing `SCOPE_VERSION` key field is tracked in roadmap §B.)
- **`SCREEN_TEXT_LANG` and `learning_objective` change the prompt but not the
  key** (`storyboard.py:357, 248`) — flipping them on a cached topic serves a
  board generated under the old setting.
- **Grounded boards never expire** (`content_hash` ⇒ `ttl=inf`) — the only
  invalidation is the grounding text itself changing.
- **The ce/ production path can't reach the tuning surface:** it hardcodes
  `quality:"l"`/widescreen and sends **no `env_overrides`**
  (`ce/stem_animation.py:183-184`) — every lesson video runs at server
  defaults, 480p15.
- **Changing voice/provider/language re-bills all audio** — the TTS cache keys
  on them. Repair rounds that only move geometry stay ₹0.
- **Not runtime-tunable** (import/boot-time reads, need a restart):
  `RENDER_WORKERS` (`jobs.py:23`), `RENDER_TIMEOUT_SECONDS`,
  `SWEEP_MAX_AGE_HOURS`. Not allowlisted (need server env): `DRY_RUN_ENABLED`,
  `CODEGEN_WORKERS`, `LLM_MAX_TOKENS`, all `TTS_*`.
- **Model routing IS runtime-tunable, via its own surface** (2026-08-02):
  `LLM_PROVIDER_ORDER` and every `*_MODELS` chain are read per call and settable
  from the **Model routing panel** on `/` and `/studio` (`GET|POST /api/models`,
  `POST /api/models/reset`) — no restart. Process-global, lost on restart; `.env`
  is still the durable config. Changing a chain is a **billing change** (different
  model, different price) but not a cache-key change: the storyboard cache does
  not key on model, so switching models does NOT invalidate cached boards.
- **`LLM_MAX_TOKENS` does NOT govern the storyboard task** (since 2026-07-31):
  storyboard calls send no request-level cap (`_max_tokens_for_task`,
  `app/llm.py`) — the model's own output window is the only limit, and the
  `finish_reason` gate still rejects model-truncated boards loudly. Restore a
  storyboard cap with `LLM_MAX_TOKENS_STORYBOARD=<n>` (`0` = uncapped). Other
  tasks (codegen/repair/director) keep `LLM_MAX_TOKENS`.

## Which levers actually change video LENGTH

Final length ≈ Σ TTS audio per cue (dominant) + Σ `wait_time` (~1s/scene) +
0.5s/scene-transition. Animations never extend a beat (`_TIMING` caps at
`tracker.duration`). So:
- Tier 1–2 levers move length by **seconds** (`wait_time`, transition, focus hold).
- Length is decided at **stage B**: scene count (planner, cap 10) × cue count
  (2–4/scene) × cue verbosity (~150 wpm). Today's output: modal 90–140s
  (measured over `static/videos/` + `generated_videos/`), ceiling ≈ 4 min.
- The storyboard **token ceiling no longer binds** (uncapped 2026-07-31, see
  Traps) — the remaining stage-B walls are the planner's 10-scene cap, the
  prompt's "4–6 scenes" instruction, and the model's own output window.
- 10–15 min therefore needs the **chapterized long-form design** — see
  `docs/pipeline-roadmap.md` §6, not a knob.
