# `lessonforge.engine` — the storyboard → Manim → verified-video server

Formerly `stem_animation_lab/app` in concept_explorer (the pre-split monolith
`app_legacy.py` was not carried over). Importing the package builds the FastAPI `app`
and re-exports the public surface: `from lessonforge.engine import X` works for
everything the old `from app import X` did.

**Launch:** `lessonforge serve` (= `uvicorn lessonforge.engine:app --port 5000`).
Restart after editing anything here — a running uvicorn keeps old code. Paths below
written as `app/…` or `stem_animation_lab/…` in older docs now mean
`src/lessonforge/engine/…`; `transpiler.py`, `viz_helpers.py` and `theme.py` sit one
level up in `src/lessonforge/`, and the overlap probe moved to `layout_probe.py`.
Runtime files (renders, videos, caches) live in the workspace — see `../paths.py`.

## Module map (follows the video-pipeline stages)

| Module | Responsibility |
|---|---|
| `config.py` | Anchored paths (`RENDER_DIR`, `VIDEO_DIR`, `VIZ_HELPERS_SRC`, `GENERATED_DIR`), render limits, `_ENV_OVERRIDE_ALLOWLIST` / `_apply_env_overrides` |
| `bootstrap.py` | ffmpeg / LaTeX / SoX / sound-asset self-healing (`ensure_all()` runs once at import) |
| `schemas.py` | Pydantic Scene-DSL (`StoryboardResponse` etc.) + request bodies |
| `llm.py` | Provider routing (Gemini → OpenRouter → Groq), per-task model chains, `loads_json_lenient` / `strip_code_fences` |
| `rag.py` | ChromaDB error→repair pairs + component retrieval (`CHROMADB_ENABLED=1`) |
| `sources.py` | Source intake — YouTube transcripts, web pages, pasted notes, optional search → a `ResearchPack` of numbered, citable chunks whose digest is the cache-freshness signal. Every tier degrades to a warning; a dead link never fails a video |
| `manim_context.py` | Manim knowledge for the simulation writer: the **installed** package introspected in a subprocess and cached as JSON, plus curated `build`/`animate` patterns. Keyword retrieval, no vector DB, no new dependency |
| `sim_gen.py` | Generated simulations — the one place an LLM writes Manim (`build(w,h)` + `animate(group, run_time)`), gated, executed and **verified** (it runs, stays in its box, something moves) before its module path is spliced into the board |
| `codegen.py` | Manim code sanitize / validate / self-heal / Layout-QA critic / LaTeX→Text fallback + `LAYOUT_RULES` |
| `assets.py` | Non-Manim item detection + svg_icon / chemical_molecule preflight probe + background selection |
| `storyboard.py` | Storyboard generation, pre-cache shape/language gate, on-screen-language healing, `StoryboardCache` |
| `codegen_pipeline.py` | Storyboard → Manim script (deterministic `transpiler.py` first, LLM fallback), per-scene scripts, asset blueprint |
| `render.py` | Compile + dry-run overlap probe + accept-if-better repair loop + async job runners |
| `jobs.py` | `JobStore` (bounded in-memory registry) + render thread pool + per-video sidecars |
| `api/*.py` | FastAPI routers grouped by concern (generation, render, assets, content, batch, pages) |
| `pipeline/*.py` | Typed stage protocol, the IR-enrichment **agent registry** (Visual Director, Motion Director), and the **deep storyboard** front half (`screens.py` ideator → `scene_writers.py` one call per screen → `deep_storyboard.py` orchestrator, `DEEP_STORYBOARD=1`) |

Import DAG is acyclic, leaf→root: `config`/`schemas` at the bottom; `render` imports its
monkeypatch seams (`repair_code_with_gemini`, `llm_available`, `_store_repair_pair`)
**by name** so the overlap/repair test harness patches them on `app.render`.

## The pipeline & the two agent stages (implemented 2026-07-21, default-off)

`pipeline/stages.py` documents the full stage sequence and defines `PipelineContext` +
the `PipelineStage` protocol. All ten stages are now concrete; the two agent stages
ship **implemented but flag-gated** (both flags are `env_overrides`-allowlisted):

- `pipeline/director.py` — `VisualDirectorStage` (flag `VISUAL_DIRECTOR=1`), called from
  `codegen_pipeline.generate_code_impl` before any codegen path reads the board. Two
  halves with different failure semantics: a **deterministic** pass
  (`_enlarge_sparse_scenes` — sparse, axes-free scenes get every scale ×1.3 clamped at
  1.4; pure code, so it applies even when the model is unreachable), then a
  **best-effort LLM** pass — one storyboard-tier call ranks importance / schedules
  lifetimes / picks highlights and one `focus` spotlight per scene, and
  `_apply_directives` applies them deterministically as **ordinary IR constructs**
  (scale tiers — never axes/graphs; appended `hide`/`highlight`/`focus` events, each
  individually safety-gated), so the transpiler needed no new vocabulary and a stripped
  board is byte-identical. On LLM failure the stage stands aside, keeping the
  deterministic half. Pinned by `test_director.py` (33 checks).
- `pipeline/vision_qa.py` — `VisionQAStage` (flag `VISION_QA=1`), called from
  `render._run_vision_qa`: ffmpeg frame extraction (`VISION_QA_FRAMES`, default 6) →
  one multimodal call (`app.llm.call_vision_llm`, chain `VISION_QA_MODELS`) → whitelist-
  gated findings as `LAYOUT_VIOLATION: vision-<class>` lines (never counted by the
  geometric `_overlap_violations`). Sequential path: full accept-if-better vision-repair
  round (`VISION_QA_REPAIR`, geometric non-regression guard, incumbent never lost).
  Parallel path: **scene-scoped** repair (`_repair_scenes_vision` — findings attributed
  to clips by timestamp, only flagged scenes re-rendered, acceptance at the concat level
  because a critique is metered; clips must outlive this stage). Both feed the sidecar
  (`vision_findings`). Pinned by `test_vision_qa.py` (35 checks, which also cover
  `_classify_render_failure` infra/latex/code triage and `_tts_degraded_lines`).

House rules both stages keep: a stage improves or stands aside (never blocks), a
verified artifact is never lost, every metered call is task-tier routed.
