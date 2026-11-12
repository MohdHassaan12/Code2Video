# Studio — editor-UX redesign (design doc)

Status: **first cut SHIPPED 2026-07-31** — `/studio` (`static/studio.{html,css,js}`)
implements the editor front end: brief → storyboard → scene rail with blueprint
thumbnails + drag reorder + add/duplicate/delete → Content/Motion/Audio/Style
inspector tabs editing the IR → render through `generate_code` + `compile_video`
**with `scene_scripts` forwarded** (parallel path + scene-scoped repair) → WS
progress (poll fallback) → video + Advanced drawer (report / storyboard JSON /
code / logs). Voice catalogue + cue audition shipped server-side
(`app/api/voices.py`: `GET /api/voices`, `POST /api/tts/preview` — cached, honest
Sarvam→Gemini fallback note). P0 wiring debt fixed in the classic UI too
(scene_scripts + `err.detail` + nav links). **Not yet built:** server-side project
store (projects live in browser localStorage, capped at 20), per-scene re-render
route (edits re-render the whole video — the shared TTS cache still makes that
cheap), server-side PATCH validation (edited boards bypass the storyboard gate;
codegen sanitizers are the only guard), AI edit box, full sandbox absorption.
Visual pitch with wireframes: [`studio_proposal.html`](../studio_proposal.html)
(repo root; also published as a claude.ai artifact). Roadmap stage: §J in
[`pipeline-roadmap.md`](pipeline-roadmap.md). The problem statement below is
kept as written 2026-07-30; wiring-debt items marked fixed where they are.

### Simplification note (2026-08-03)

The design doc below is comprehensive — it specifies a full editor with four
inspector tabs, a project library, per-scene rendering, AI edits, and sandbox
absorption. The four-phase plan (P0–P4) maps out a feature-complete Studio. This
is the *right* end state but the *wrong* sequence: the feature surface is wide
enough to feel complicated, and the gaps (browser-only persistence, whole-video
re-renders, no PATCH gate) make it fragile even where it works.

**Before adding more editing surface, close the foundation gaps.** Two weeks of
narrow, structural work would simplify the *experience* without adding a single
feature:

| What | Why it simplifies the Studio |
|---|---|
| **Server-side project store** (§H per-run folder) | Project outlives the browser tab; share a link; no localStorage cap; an in-flight render is resumable without the "resume from stored job id" hack. |
| **Per-scene re-render route** | One cue edit → one scene render, not the whole video. The whole-video re-render on every edit is what makes Studio feel slow and expensive. |
| **Storyboard PATCH gate** | Edited boards currently bypass the shape + language gates — only codegen sanitizers guard them. Adding gate validation before render makes editing feel *trustworthy* instead of *brittle*. |
| **Delete the four disconnected surfaces.** | `/studio` replaces the lab page, `/timeline`, the sandbox, and the classic `app.js` one-shot flow — today all four coexist with no shared nav and no shared state. Consolidating into Studio + Library + Advanced is less code than maintaining four UIs. |

After these four are closed, the inspector already works (Content/Motion/Audio/Style
tabs map to real IR fields, edit→render loop runs) — and it will feel like a
*polished editor* instead of a *fragile prototype*.

## Problem

The UI is organized around the pipeline's stages; the user thinks in **scenes**.
Concretely:

- **One black-box button.** `#btn-generate` runs storyboard → preflight → codegen
  → compile unattended (`app.js:330-492`). No pause to review/fix the storyboard,
  no re-run of a single stage, no cancel.
- **The editable thing is the wrong thing.** The storyboard renders read-only
  (`<code>` block); the only editable intermediate anywhere in the browser is the
  **Manim Python textarea** — educators want to fix a narration line or a label,
  not source code.
- **All-or-nothing regeneration.** One word of narration = re-render everything.
  Yet per-scene clips ARE rendered server-side and then discarded after concat
  (`render.py:1166`, uuid-named, index-anonymous, unreachable).
- **Four disconnected surfaces.** Lab page, `/timeline` (read-only), `/bulk`, and
  the Streamlit sandbox share no nav and no state. Voice audition, repair history,
  env knobs, and cost readouts live only in the sandbox; per-unit regenerate lives
  only in ce/'s Streamlit `_video_view`.
- **Wiring debt** (each of these is a bug today, independent of any redesign):
  - The browser never forwards `scene_scripts` (compile payload `app.js:506-510`),
    so **every web render takes the slow sequential path and never gets
    scene-scoped repair** — `render.py:1114` requires `scene_scripts` to take the
    parallel path. Same class as the roadmap-§F4 "production never used the fast
    path" find.
  - Client reads `err.error`; FastAPI sends `detail` — server error messages are
    silently swallowed and replaced by a generic string.
  - Voice lists are hardcoded in `app.js:282-313` as a manual mirror of the
    sandbox's table (drift by construction).
  - Asset "Re-test" fixes patch the storyboard **in browser memory only** — there
    is no storyboard GET/PUT, so corrections die with the tab.
  - The WS job-status endpoint (`render_routes.py:106`) exists; no page uses it —
    pages poll a free-text `progress` string every 2 s, then dump raw logs.

## The unlock

The backend is already scene-modular; only the UI isn't. Editor capability →
existing primitive:

| Editor capability | Already exists | Missing |
|---|---|---|
| Edit one slide, re-render one slide | per-scene `scene_scripts`; `_render_scenes_parallel` + `_concat_scene_clips`; scene-scoped repair | a route addressing scene *k* of a persisted project; clips kept instead of discarded |
| Cheap edit loops | shared TTS cache (unchanged cues re-bill ₹0); storyboard + bulk stage caches | dirty-scene tracking (hash scene IR subtree vs last-rendered hash) |
| Field-level content/motion/audio editing | the storyboard IR (`elements`, `animation_events`, `narration_cues`, `composition`, `layout_template`); deterministic transpiler owns geometry | validated `PATCH` through the existing shape gate + `normalize_onscreen_language` |
| Edits never break a good video | accept-if-better contract; `_discard_video`; sidecars | nothing — reuse verbatim |
| Voice audition | sandbox already synthesizes samples; TTS cache keyed on request intent → **a previewed cue pre-warms the render** | `/api/tts/preview` + server-owned `/api/voices` |
| Live progress | WS endpoint; per-scene logs index-aligned with scripts | structured per-scene events; a page that subscribes |
| A library you return to | `/timeline` + sidecar badges; `bulk_runs/<id>/` per-topic folders | generalize the bulk folder into a **project folder** for every video (= roadmap §H per-run folder, made load-bearing) |

## Design

**IA: three views over persistent projects** — **Library** (grown out of
/timeline; cards carry sidecar badges, primary action "Open in Studio"; bulk runs
appear as grouped rows) · **Studio** (the editor) · **Advanced drawer** (absorbs
the sandbox per project: repair-round history + diffs, cost/latency, generated
code read-mostly with the recompile escape hatch, env-override knobs, raw sidecar).

**Studio layout** — scene rail (bottom, film strip: thumbnails + status dot +
duration; drag to reorder, add/duplicate/delete), preview canvas (center: the
scene's clip; cue scrubber underneath), inspector (right, per selected scene):

```
┌ topic · status · [Ask AI] [Advanced] [Render N changed scenes] ┐
│ ┌───────────────────────────────┐ ┌ Content|Motion|Audio|Style ┐│
│ │        scene preview          │ │ composition                ││
│ │        (clip / blueprint)     │ │ elements[] (inline edit)   ││
│ └───────────────────────────────┘ │ cues[] / events / voice    ││
│  cues: ▮▮▮░░  2/3                 └────────────────────────────┘│
│ ┌ 1 ok ┐┌ 2 ● dirty ┐┌ 3 ok ┐┌ 4 ok ┐┌ + ┐                     │
└─────────────────────────────────────────────────────────────────┘
```

Selection model: **the rail selects a scene, the canvas scrubs its cues, the
inspector edits what's selected.** Before first render, thumbnails/canvas show a
schematic "blueprint" drawn client-side from the IR (zones + element types);
after, a real mid-scene frame.

**Inspector tabs map 1:1 to IR fields** (no invented concepts — anything the
editor can express, the pipeline can render and the gate can validate):

| Tab | IR fields | Controls |
|---|---|---|
| Content | `elements[].content/type/color/scale`, `composition`, `description` | element list w/ inline text/LaTeX edit, type-aware fields (SMILES, axis ranges), add/remove, theme-palette swatches |
| Motion | `elements[].entrance_animation`, `narration_cues[].animation_events` | entrance picker seeded from `_ENTRANCE_CONFIG`/`_SHAPE_ENTRANCES`; per-cue event chips (show/hide/transform/highlight/move_to/focus) with target dropdowns **limited to this scene's element ids** — cross-scene refs impossible by construction (the `_drop_cross_scene_events` bug class) |
| Audio | `narration_cues[].cue`, voice spec (language/persona/speaker/provider/tech_terms) | per-cue textarea + ▶ preview (shared TTS cache), voice picker from `/api/voices`, pacing tags as chips, per-cue cost chip (`cached · ₹0` vs `edited · will re-bill`) |
| Style | `layout_template`, `wait_time`; project-level style/background/quality/aspect | template picker w/ schematic previews; the five theme profiles; project knobs move here out of the global sidebar |

**Edit loop** (every edit, manual or AI):

1. Inspector patches the IR → scene subtree hash changes → scene marked dirty
   (undo/redo = patch stack).
2. Save runs the **existing** gates: `storyboard_shape_problems` + language
   contract + `normalize_onscreen_language`. Rejected edits bounce with the gate's
   reason, before any spend.
3. Dirty scenes only are re-transpiled (deterministic, free).
4. Candidate clip per dirty scene; probe + repair as today, scene-scoped;
   unchanged narration replays from the TTS cache.
5. **Accept-if-better, re-concat.** Candidate must render and not regress
   violations; losers discarded via `_discard_video`; the last good clip is never
   lost. On failure the scene shows "edit failed — showing last good render" with
   the `_classify_render_failure` reason.

Cost story: one narration tweak = one cue of TTS + one scene render + one concat.

**AI edits** — an "Ask AI" box on the selected scene sends instruction + scene IR
to the LLM and gets back a **storyboard patch, never code**; UI shows the diff as
chips with Apply/Discard; applied patches enter at step 1. Models own content,
code owns structure.

**New-video flow becomes two beats** — Beat 1 *brief* (topic + storyboard-shaping
knobs: persona, language, tech_terms, style) → storyboard reviewed in Studio as an
unrendered rail with blueprint thumbnails (where today's silent failures get
caught for free). Beat 2 *render all* (parallel). The 13-knob sidebar dissolves:
storyboard knobs → brief, render knobs → Style tab, debug knobs → Advanced.

## Proposed API surface

| Route | Purpose | Builds on |
|---|---|---|
| `POST /api/projects` | brief → storyboard-only project (no render) | `generate_storyboard` + project folder (§H) |
| `GET /api/projects[/{id}]` | library list; full project state (IR, per-scene status + clip URLs, sidecar) | `video_history`, sidecars, bulk manifest pattern |
| `PATCH /api/projects/{id}/storyboard` | validated IR patch; returns dirty scene set | shape gate + `normalize_onscreen_language` |
| `POST /api/projects/{id}/scenes/{n}/render` | one-scene candidate render, accept-if-better, re-concat | `_render_scenes_parallel`, `_concat_scene_clips`, repair loops |
| `POST /api/projects/{id}/render` | render all dirty scenes + concat | same |
| `GET /api/voices` | single source of truth for provider/language/speaker lists | replaces the hardcoded JS mirror |
| `POST /api/tts/preview` | cue text + voice → audio, via the shared TTS cache | `UniversalTTSService` + `.tts_cache/` |
| `POST /api/projects/{id}/ai_edit` | instruction + scene → proposed IR patch (never auto-applied) | storyboard-tier LLM chain, metered |
| `WS /ws/projects/{id}` | structured per-scene progress | existing WS pattern |

Non-goals: no code-editing API beyond the existing escape hatch; no concurrent
multi-user editing (`env_overrides` stays a process-global single-author
affordance).

## Phases (each independently shippable)

- **P0 — unblock what exists (~a day, pure wiring debt):** forward
  `scene_scripts` from the browser compile; read `err.detail`; shared nav header
  across / · /timeline · /bulk; `/api/voices`.
- **P1 — glass box + persistence (~a week):** split Generate into brief → review
  → render; storyboard as a read-only scene rail with blueprint thumbnails;
  project folders (keep clips); WS per-scene progress; /timeline cards gain "Open
  in Studio".
- **P2 — audio editing first (~a week):** Audio tab (cue text edit, voice
  audition via `/api/tts/preview`, per-scene re-render). Audio is the cheapest,
  highest-demand edit (the `tech_terms` knob exists because of a narration
  complaint) and exercises the whole PATCH → dirty → render loop on the least
  risky field.
- **P3 — content + motion (~1–2 weeks):** element editing, entrance pickers,
  event chips, composition/template controls; scene reorder/add/duplicate/delete.
- **P4 — AI edits + absorb the sandbox (~a week each):** Ask-AI prompt-to-patch
  with diff preview; Advanced drawer so the Streamlit sandbox can retire from
  daily use.

## Invariants the editor must never break

1. **Never lose a verified artifact** — edits are candidates, accept-if-better.
2. **Code owns structure, models own content** — the editor and the AI box edit
   the IR only; no UI control writes Python.
3. **Metered edges stay metered and visible** — cost chips; previews route
   through caches; no metered call in a render-blocking hot path.
4. **Validation before spend** — every PATCH gated before any render.
5. **Long operations narrate per-scene progress** — silence reads as a hang.

## Open questions

- Blueprint thumbnails: client-side SVG from IR zones is free but approximate; a
  probe-style dry-run frame would be exact but costs a manim boot per scene.
  Start client-side.
- Scene reorder renumbers `scene_index` — check nothing keys on it besides
  ordering (the sidecar's `beats` and bulk manifests don't; verify per-scene log
  attribution).
- Project store shape: generalize `bulk_runs/<id>/` (manifest + stage caches) vs
  a new `runs/<project>/` layout — decide together with roadmap §H's per-run
  folder so there is ONE folder convention.
- Sweep policy: project folders must be sweep-exempt (`sweep_old_artifacts`
  currently deletes anything old in `VIDEO_DIR`).
