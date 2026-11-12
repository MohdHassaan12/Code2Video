# Provenance and pruning ledger

lessonforge was assembled on 2026-10-07 from three repositories. Nothing was deleted
from them; this file records what was taken, what was left, and why, so anything left
behind can be found again.

| Source | Commit | What it was |
| --- | --- | --- |
| `concept_explorer` (branch `Final-Vid-Gen`) | `db58144c` | GyanSetu Concept Explorer: a Streamlit lesson console (`ce/`) plus `stem_animation_lab/`, the storyboard → Manim video engine |
| `education_content_review-` | `b7e749c` | Meeting minutes, research review, a paid model pilot, and a hand-repaired 20-minute Pythagoras lesson built audio-first |
| `Stem_Animation_Manim` | `75dc5ee` | A docs-only snapshot of the engine's research documents |

## What was taken

| From | To | Change |
| --- | --- | --- |
| `stem_animation_lab/app/` | `src/lessonforge/engine/` | One import namespace; repo-relative paths replaced by the workspace (`paths.py`); manim subprocesses run in the render dir |
| `stem_animation_lab/{transpiler,viz_helpers,theme}.py` | `src/lessonforge/` | Imports only; `viz_helpers` reads the workspace from the environment because it is also staged next to rendered scripts |
| `_OVERLAP_PROBE_SNIPPET` in `app/render.py` | `src/lessonforge/layout_probe.py` | Moved verbatim, then one exemption added (labels with an opaque backing plate) |
| `stem_animation_lab/{dependencies,bulk_runner,seed_manim_components}.py` | `src/lessonforge/engine/` | Imports and paths |
| `stem_animation_lab/static/`, `schemas/`, `assets/backgrounds/` | `src/lessonforge/web/static/`, `schemas/`, `assets/backgrounds/` | Shipped as package data |
| `stem_animation_lab/test_*.py` (26 files) | `tests/engine/` (24 harnesses) + `tests/manual/` (2) | Paths only; run with `tests/run_engine_checks.py` |
| `long_form_pythagoras/{lesson_runtime,build_audio,assemble,finalize_checks,build_review}.py` | `src/lessonforge/longform/{runtime,audio,build,review}.py` + `contract.py`, `speech.py` | Rewritten as a library: any lesson, any chapter count, pluggable voice, block-level synthesis, no forced retiming, per-play probe, non-crashing checks |
| `long_form_pythagoras/{lesson.json,chapters_first_four.py,chapters_rest.py,verify_*.py}` | `examples/pythagoras/` | Runtime import; one label moved in chapter 7 (probe finding) |
| `prototype/narration.json` | `examples/like_terms/lesson.json` | Converted to the lesson contract |
| Live engine docs, research docs, review docs, handoff, case study, drafts | `docs/` | Copied unmodified — see `docs/README.md` |
| `Stem_Animation_Manim/CLAUDE.md` | `CLAUDE.md` | Paths rewritten, repo-specific sections replaced |

New in this package: `paths.py`, `bridge.py`, `cli.py`, `harness/`, `longform/runtime.GuidedChapter` and `AutoChapter`, `tests/unit/`, `clients/lessonforge-app/`.

## What was left behind

**concept_explorer** (956 MB checkout, of which 491 MB is `.git`)

| Left | Size | Why |
| --- | --- | --- |
| `cloudflared`, `cloudflared.deb` | 57 MB | Tunnel binaries; unrelated to the product |
| `debug_sandbox/` | 264 MB | Streamlit debugger plus rendered mp4s and traces; a single-user debugging aid |
| `content_store/`, `generated_videos/`, `static/videos/`, `temp_renders/` | 75 MB | Generated output |
| `ce/`, `app.py`, `seed/`, `tests/` (KG tests), `scripts_*.py`, `Concept Explorer/`, `GyanSetu … Design System/`, `Interactive simulation framework templates/` | — | The lesson-authoring console, images, interactions, question galleries, personalization: a different product, marked stale by the owner on 2026-07-19. `ce/stem_animation.py` (an HTTP client for the engine) is superseded by the CLI and the harness routes |
| `stem_animation_lab/app_legacy.py` | 3995 lines | The frozen pre-split monolith; not imported by anything |
| `stem_animation_lab/chroma_db/` | binary | Optional RAG store; rebuild with `engine/seed_manim_components.py` |
| `stem_animation_lab/antigravity_scene.py`, `*.mp3`, `docs/flask-to-fastapi-migration.md` | — | A one-off scene; sound effects regenerated at startup; a finished migration |
| `docs/image_*`, `interaction_*`, `visual_overhaul_*`, `personalization_design.md`, `concept_teacher_improvements.md`, `kg-input.md`, `task_sheet.md`, `engine_improvement_plan.md`, `agent_pipeline_v1.md`, `*_migration_blueprint.md`, `superpowers/`, benchmark and comparison images, `interaction_demos.zip` | ~50 MB | Stale or superseded per the repo's own `DOCS.md` |
| `LAYMAN_SERVICES_GUIDE.md`, `concept_explorer_*.md`, `run_app.ps1`, `setup_git.ps1`, `.devcontainer/`, an empty file named `a bicycle wheel spinning rapidly in place` | — | About the console, Windows-only, or accidental |

**education_content_review** (56 MB)

| Left | Why |
| --- | --- |
| `long_form_pythagoras/models/` (Kokoro voice pack; the model is an LFS pointer) | Weights are downloaded, not committed |
| `long_form_pythagoras/{audio,media,media_rest}/`, `output/` media, `*.log`, `timeline.json`, `output/editable_lesson_source.zip` | Regenerated by `lessonforge lesson build`, or a zip of files already here |
| `long_form_pythagoras/make_contact_sheets.py` | Not ported (frame sampling for visual review); a candidate to bring back |
| `prototype/` scene code, flite audio scripts, lockfiles | Written against an earlier runtime; the script is kept as `examples/like_terms` |
| `research/repositories/` | Empty placeholders for third-party clones; `docs/research/review/repository_manifest.json` records the commits |
| `experiments/openrouter_pilot/*.log` | Render logs; results, prompts, drafts, repairs and ledgers are kept |

**Stem_Animation_Manim** — every `.md` and the `.csv` are byte-identical to `concept_explorer/docs/`, so one copy is kept. `Video Engine Research Agenda.html` and its `_files/` (5 MB) are a browser save of the rendered `research-agenda.md` and were dropped; `DOCS.md` is folded into `docs/README.md`.

## Fixes made along the way

- **SoX stand-in** (`engine/bootstrap.py`): on Linux without SoX the generated stand-in printed a greeting, which makes the `sox` package raise at import and kills every render subprocess. It now answers in SoX's format. Three render harnesses failed on a SoX-less machine before this.
- **Render sweep** kept `thud.mp3` and `whoosh.mp3` but deleted `pop.mp3` and the staged helpers after 24 h; all are kept now.
- **Static mounts**: rendered videos are served from the workspace, the UI from the package.

## Licences

The source repositories carry no licence file; treat this package as proprietary to their owner until one is added. Kokoro-82M is Apache-2.0 and kokoro-onnx is MIT; neither is redistributed here. `clients/lessonforge-app/LICENSE` came with the Expo template.
