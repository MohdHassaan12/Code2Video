# Problem Decomposition — the video engine from first principles

**Written 2026-08-22.** This document maps the *problem* the video engine solves,
independent of how the current code solves it, and then grades the current code against
that map. It is not a bug list ([`pipeline-roadmap.md`](pipeline-roadmap.md) §4), not a
roadmap ([`improvement-timeline.md`](improvement-timeline.md)), and not an architecture
doc ([`architecture/reference-architecture.md`](architecture/reference-architecture.md)).
Those describe the built thing. This describes the space the built thing sits in, so that
the next version can be chosen rather than accreted.

**How numbers are used here.** Every measured number is quoted from an artifact on disk
and names its file; nothing is quoted from memory. Where no artifact exists the figure is
marked **(est)**. The artifact set, as of today:

| Artifact | What it holds | Where |
|---|---|---|
| 46 render sidecars | repair rounds, violations left, beats, voice health | `stem_animation_lab/static/videos/*.mp4.json` |
| 27 cached storyboards (148 scenes, 876 elements, 426 cues) | the IR the model actually writes | `stem_animation_lab/.storyboard_cache/` |
| 185 debugger traces (171 with timings + the debugger's own cost estimate) | stage timings, failure stage, tokens | `debug_sandbox/debug_traces/` |
| 1 bulk run (5 topics) | per-topic wall time, cache hits | `stem_animation_lab/bulk_runs/bulk_20260731_071737_9195/manifest.json` |
| 1 server log (3,993 lines, last written 2026-08-02) | composition + voice-degradation markers | `stem_animation_lab/logs/uvicorn_5000.log` |
| the IR schema | every enum the model may choose from | `stem_animation_lab/schemas/storyboard-ir.schema.json` |
| the roadmap's audit sections §3–§3e | frame-level findings from watched runs | `docs/pipeline-roadmap.md` |

Two caveats on the corpus. The debugger traces span code older than today's pipeline
(the oldest predate the July split of the server), and their `costs` field is the
debugger's own pricing estimate, not a billing record — there is no billing record
anywhere. The sidecar set is everything with verification metadata; 86 more mp4s on disk
(`debug_sandbox/static/videos/` 72, `generated_videos/` 14) have none.

---

## 1. The transformation chain

A short educational video is produced by turning a *commission* (a topic, for a grade,
in a language) into a *verified artifact* (an mp4 with a measurement record) through a
chain of intermediate representations. Written one arrow per transformation — where two
transformations could be owned by different components or make independently different
decisions, they are separate links:

```
 commission (topic · grade · subject · persona · language · style · optional sources)
   │
   ▼  L1  commissioning        should a video exist? what kind? how long?
   ▼  L2  grounding            raw material → citable chunks
   ▼  L3  lesson decomposition topic + material → teachable units, scene count, pace
   ▼  L4  narrative            units → an arc: through-line, running example, scene roles
   ▼  L5  screen planning      arc → per-screen contracts (what must be shown, what must be said)
   ▼  L6  scene authoring      contract → elements + narration cues + events   ← THE WAIST (Storyboard IR)
   ▼  L7  language realisation narration in the persona's language; on-screen text in English
   ▼  L8  admission            shape / truncation / language gates; cache write
   ▼  L9  IR enrichment        importance, lifetime, emphasis, motion directives
   ▼  L10 object realisation   an element's prose → a drawable thing (primitive, drawing, simulation, photo)
   ▼  L11 spatial composition  things → positions (zones, templates, graphs, containment, split-screen)
   ▼  L12 temporal composition things → entrance class, timing within the beat, event animations, beat filler
   ▼  L13 theming              canvas, palette, colour harmonisation
   ▼  L14 program synthesis    Layout IR + Animation IR → Manim scripts (master + per-scene), sanitise, critic
   ▼  L15 voice                narration text → audio per cue
   ▼  L16 render + measure     scripts + audio → clips; instrumented dry-run → violation lines
   ▼  L17 repair               violations → rewritten scene → accept-if-better
   ▼  L18 assembly + record    clips → one video; sidecar; (lesson side: concat + background music)
   ▼  L19 delivery + review    timeline, editor, bulk manifest; a human watches
   │
   ▼  verified video artifact
```

Nineteen links. The single most important structural fact about the chain is at L6:
the Storyboard IR is the **waist** — everything above it is pedagogy and is
renderer-agnostic; everything below it is presentation and never sees the source
material again. What L6 does not record, no later link can recover (§5.10).

---

## 2. The hidden decisions, link by link

The test for a "hidden decision": if it were made differently, would the output be a
materially different product? Every yes is named. **Who decides today** uses four values:
**code** (deterministic, ours), **model** (an LLM call, ours), **external** (a service
whose behaviour we do not control), **nobody** (the outcome is whatever falls out).

| Link | Hidden decisions | Who decides today |
|---|---|---|
| L1 commissioning | whether a node gets a video at all; the video's *type*; its length; one clip or several | model (lesson-side planner) for *whether/type*; **code** for length — `ce/planner_agent.py:39-78`: floor 4 scenes, cap 10, 25 s/scene; `ce/clip_planner.py` hard-codes **1** clip per node |
| L2 grounding | which sources count; how much of them; chunk size; whether to search; what "fresh" means | code (3-tier lookup: given link → transcript search → NCERT text; optional web search **off** by default); **nobody** decides relevance ranking within a source |
| L3 lesson decomposition | what the teachable units are; their order; how many; the pace in words/minute | model (PARTS plan) for units; **code** for count (word-count ÷ wpm ÷ 25 s, floored at 4) and wpm (by grade band) |
| L4 narrative | the question the video answers; the one running example; which scene is the hook/turn/payoff | model; **code measures** cold opens and anchor recurrence but never rejects |
| L5 screen planning | how many screens; what each must show (countable) and say (cited); visual kind per screen; variety | model, **clamped by code** (5–8 screens, ≤6 objects/screen, arc forced: first opens, last closes). *Only on the deep path, which is off by default* — on the default path this link is **implicit inside L6** |
| L6 scene authoring | element count and types per scene; element ids; which cue shows/hides what; the event vocabulary actually used; colour per element; scale per element; a composition sentence; a layout template | model. The schema bounds the vocabulary (10 element types, 6 event actions, 5 layout templates, 5 roles, 6 zones — `schemas/storyboard-ir.schema.json`); everything inside those bounds is the model's |
| L7 language realisation | script for narration (Devanagari vs romanised Hinglish); whether STEM terms are spoken in English, bilingually, or translated; on-screen language | code (policy from the request → a prompt rule + a transliteration pass + a heal pass); the *wording* is model |
| L8 admission | what counts as a complete board; what counts as on-contract language; what keys the cache; how long a board lives | code (shape gate, finish-reason gate, language gate, heal-accept rule; 48 h TTL keyed on topic+persona+language+style+grade+subject+tech_terms+prompt version+duration+deep version) |
| L9 enrichment | which element is primary; when an element is finished; what is emphasised; what *moves* | model proposes, code disposes; Visual Director **off** by default, Motion Director **on**; caps 2 motions/cue, 4/scene (`app/pipeline/motion.py:52-53`) |
| L10 object realisation | what "a circle containing 84" IS; whether an object is a primitive, a verified drawing, a simulation, a clipart icon, or a photo; what is *not* drawn (edges, bare primitives) | code routes by kind; **model writes the drawing/simulation code** for anything non-primitive; **external** (Iconify / Wikimedia) decides what a photo or icon looks like |
| L11 spatial composition | which zone each element takes; fallback order when a zone is taken; when to split the screen; node positions in a declared graph; how contained children are distributed; where the frame's visual weight sits | code, entirely. 8 zones with fixed fallback chains (`transpiler.py:97-120`), 5 templates, BFS layering for ≥3-node graphs, split on ≥2 free-standing texts or any math. **Nobody** decides balance: there is no whole-frame pass |
| L12 temporal composition | entrance class per element; how much of the beat an entrance takes; what fills the rest of the beat; event animation durations; when within the beat a named thing appears | code: entrance by element type (`transpiler.py:69-82`), duration as a fraction-of-beat with a floor (`_TIMING`, `transpiler.py:182-192`: axes 0.9/1.5 s … shape 0.35/0.5 s), beat remainder filled by round-trip gestures. **Nobody** aligns an entrance to the word that names it |
| L13 theming | canvas colour; whether a model-authored colour survives; the palette a colour snaps to; font | code (five style profiles; keep a colour if WCAG ≥3.0 against the canvas and not a raw primary, else snap by hue; text never hue-snaps; font fixed) |
| L14 program synthesis | one script or one per scene; what a critic may rewrite; what a sanitiser strips; which cross-scene references are legal | code; the Layout QA critic is a **model** rewrite accepted only under three invariants (no element lost, no structural helper lost, no zone anchor lost) |
| L15 voice | the voice; provider order; what a transient failure is vs a real one; whether silence is acceptable; what is cached | code (primary → Gemini → keyless gTTS → silence-off-by-default; retry on 5xx/429/empty-200; content-addressed cache); the *sound* is **external** |
| L16 render + measure | quality/resolution; what a violation IS (three text classes counted; shape-on-shape measured but not counted; images skipped; mid-animation unmeasured); how many violations to report | code (`_OVL_MAX_REPORTS=12`; 480p15 from the lesson side, hard-coded) |
| L17 repair | what to feed the repair model; how many rounds; the acceptance rule; what must survive a rewrite; when to stop | code for acceptance (renders AND fewer violations; four preservation guards); **model** for the fix itself; rounds capped at 2 (+ vision rounds); **nobody** decides "this is unfixable here" |
| L18 assembly + record | cut vs cross-fade; what the sidecar records; where artifacts live; retention | code: hard cuts; 9 sidecar fields; `static/videos/` swept after 24 h; **no cost field, no duration field, no per-run folder** |
| L19 delivery + review | what a reviewer sees first; what can be edited and re-rendered; what "bad" looks like in a badge | code (timeline badges from geometry only); **a human** decides quality by watching |

Reading down the right-hand column: **the content decisions are the model's, the
structural decisions are code's, and the quality decision is a human's.** Four outcomes
have no owner at all — relevance within a source (L2), frame balance (L11),
word-to-entrance alignment (L12), and repair termination (L17). Those four recur in every
section below.

---

## 3. The four acts

The nineteen links cluster by the *kind* of problem being solved, not by the module that
solves them:

| Act | Links | Kind of problem | Representation it produces |
|---|---|---|---|
| **I — Semantic** | L1–L8 | *What is true, what is worth teaching, in what order, in which words* | Storyboard IR (the waist) |
| **II — Presentational** | L9–L11, L13 | *What appears, what it looks like, where it sits* | Layout IR |
| **III — Temporal** | L12, L15 | *When things happen, and how the voice and the picture share time* | Animation IR + audio |
| **IV — Realisation & verification** | L14, L16–L19 | *Make the artifact, measure it, improve it without breaking it, deliver it* | Render IR, Verification IR, the mp4 |

### Couplings that reach backwards

The most valuable findings in a decomposition are constraints from a late act that
reach into an early one. Seven are load-bearing here:

1. **Act IV's verifier defines Act II's vocabulary.** The overlap probe measures against a
   fixed frame, so camera zoom/pan is deliberately absent from the IR; it ignores images
   and simulations, so three separate preservation guards had to be added to the repair
   loop after repairs silently traded photos, simulations and drawings for icons
   (`pipeline-roadmap.md` §3e, §E, §D-sim). **Every visual capability is gated by what the
   verifier can see** — a rule the catalogue states as problem 4.
2. **Act III's cost structure decides where Act I's gates belong.** Voice synthesis is the
   largest metered spend (debugger estimate: TTS 57 % of total, `debug_sandbox/debug_traces/`,
   171 traces; the sibling project measured ~85 %). A script review *before* synthesis is
   therefore the cheapest gate protecting the costliest step — and it does not exist
   (catalogue 8). The same coupling makes per-element voice clips (the obvious fix for
   L12 sync) expensive and pushes the design toward bookmarks inside one clip.
3. **Act IV's isolation breaks Act I's continuity.** Per-scene scripts render from a blank
   canvas, so the narrative anchor introduced in scene 1 is *re-drawn from nothing* in
   every later scene; a master script shares one namespace but may only reference
   backwards. The story is continuous in the narration and discontinuous on screen
   (roadmap §B-story, "Open").
4. **One model call's token budget shapes the whole board.** A single call spends its
   budget on scene 1 and sketches the rest; that is why the deep path fans out one writer
   per screen (`deep-storyboard-design.md` §1). The prompt it replaces is 17,576
   characters (`app/storyboard.py:610`); each decomposed prompt is ~3.3–3.6 k
   (`app/pipeline/screens.py:51`, `scene_writers.py:45`).
5. **The cache key is a content contract.** Every Act I decision that changes output must
   partition the cache or the fix silently doesn't apply — learned three times (tech
   terms 07-22, prompt version 08-14, deep version 08-15). The corollary from the 07-30
   audit still stands: two prompt-shaping inputs (`SCREEN_TEXT_LANG`, `learning_objective`)
   and the pedagogical plan are *not* in the key.
6. **One language contract spans three acts.** Narration language (I), on-screen language
   (II), and the TTS language parameter (III) must agree; the Dalton run shipped 8/8 cues
   in English with 7 on-screen labels in Devanagari and a `hi-IN` voice reading English
   (roadmap §3c). The contract now lives in one function used by both authoring paths.
7. **A crashing scene changes which renderer produced the file.** One dead per-scene
   render drops the whole video onto the sequential whole-video path, which self-heals
   differently (drawings shipped at 0.63 u instead of the emitted 1.90 u — roadmap §3e).
   Act IV's fallback quietly changes the Act II outcome being graded.

---

## 4. The sub-problems

Maturity scale: **L0** absent · **L1** prototype · **L2** reliable (fallbacks, non-fatal)
· **L3** measured (real numbers, pinned by tests) · **L4** closed-loop (grades itself and
self-corrects). The two verdicts answer different questions: *fine for v1?* asks whether
it is good enough to ship the current 90–140 s product; *the v2 move* names the next
qualitative capability, not the next patch.

### Act I — Semantic

#### 4.1 Commissioning — deciding that a video should exist and what shape it takes

- **Statement.** Given a unit of a lesson, decide whether a video would help, of what
  kind, and how long, before spending anything.
- **Hidden decisions.** Needed at all; type (visualisation / experiment / misconception /
  recap); duration; one clip or many; what the video is *for* in the lesson.
- **Today.** A lesson-side model call returns `needed/type/objective/duration`, with an
  offline fallback that maps five node types to 45 s visualisations
  (`docs/video_pipeline.md` §3A). Duration is then **re-decided** by code from the source
  text's word count (floor 4 scenes, cap 10, 25 s each — `ce/planner_agent.py:39-78`) and
  only since 2026-08-15 travels to the engine as `target_duration_s`. The clip planner
  always returns one clip. The measured envelope: over the 46 sidecar'd videos, duration
  by ffprobe is **min 2.9 s, median 94.2 s, max 236.9 s** — against a stated prompt target
  of "60–90 seconds" (`app/storyboard.py:221`).
- **Maturity.** L2 (the length contract is measured in `[DURATION]` lines but not
  enforced; the 2.9 s video is a truncated board that shipped before the gates existed).
- **Fine for v1?** ✅ — for one-topic explainers. The ~4 min ceiling is by construction.
- **v2 move.** Commission *chapters*, not videos: an outline that decides total length
  once, with each chapter a proper short video (roadmap §6). This is also the only route
  to lesson-length output.

#### 4.2 Grounding — turning raw material into something a claim can point at

- **Statement.** Collect the material a video may draw on and make every fact in it
  addressable, so that later stages can cite it and later checks can audit it.
- **Hidden decisions.** Which tiers of source count and in what priority; how much of a
  source to keep; chunk size; freshness; whether to search the web at all; relevance
  ranking within a source.
- **Today.** Three tiers on the lesson side (given link → transcript search → NCERT text,
  `ce/storyboard_context.py`) and, since 2026-08-15, an engine-side intake that resolves
  YouTube links, pages, pasted notes and optional search into numbered chunks (`[S2#1]`)
  whose digest keys the cache. Every tier degrades to a warning. Web search needs a key and
  is **off**. Of the 27 cached boards, the three newest carry a `research` block; 24 have
  none — the default caller (Studio, `/bulk`, curl) generated from the topic string alone
  until the intake shipped. Relevance ranking inside a source is nobody's decision: a
  transcript is chunked in order.
- **Maturity.** L2. Citable, resilient, unaudited.
- **Fine for v1?** ⚠️ — fine for STEM topics the model already knows; a liability for
  narrative Social Science topics, where an invented date is indistinguishable from a
  sourced one.
- **v2 move.** Close the loop from chunk to narration: sample N cited facts per video and
  report how many survive to the spoken text (catalogue 6 — "8 of 10 traced" is a number
  anyone can act on). Provenance without audit is bookkeeping.

#### 4.3 Lesson decomposition — what the teachable units are

- **Statement.** Split a topic into the minimal sequence of ideas a learner at this grade
  must meet, in an order where each is reachable from the last.
- **Hidden decisions.** Granularity (one idea per scene? per cue?); ordering; what to
  leave out; pace in words per minute; whether the structure is pedagogical (PARTS) or
  narrative (arc).
- **Today.** A PARTS plan (Hook → Core → Misconception → Recall → Summary) from one model
  call, with scene count from code. PARTS produced five self-contained mini-lessons — the
  root of the 2026-08-14 "no story" report — and was reframed as a skeleton under the
  narrative layer (4.4). Pace is a code table by grade band; the `"grade 1" in "grade 11"`
  substring bug narrated Grades 10–12 at 90 wpm until 2026-07-20 (roadmap §B). Nothing
  checks that the unit the video is named after is ever stated: the Dalton run never
  stated Dalton's law and passed every gate (catalogue 7).
- **Maturity.** L1–L2. Works; no measurement of whether the units are the right ones.
- **Fine for v1?** ⚠️ — acceptable because the model is usually competent on textbook
  topics; there is no signal when it is not.
- **v2 move.** Mechanical pedagogy lints on the board before any spend: the named law is
  stated; every term is introduced before use; the last scene answers the first scene's
  question. These are cheap, deterministic, and would have caught the one real failure on
  record. Whether a lesson *works* for a learner stays a study, not a feature.

#### 4.4 Narrative — making the units an arc instead of a syllabus

- **Statement.** Thread the units with one question and one concrete running example so
  that each scene continues the last rather than restarting the topic.
- **Hidden decisions.** The through-line; the anchor (an *example*, not a topic name);
  which scene is hook/turn/payoff; whether a scene may cold-open; whether the ending
  answers the opening.
- **Today.** `narrative {through_line, anchor}` and per-scene `role` in the IR; prompt
  rules; a measurement (`narrative_problems`) logged as warnings, never enforced. In the
  cache: `narrative` present on **4 of 27** boards and `role` on **23 of 148** scenes —
  the field is 8 days old and the cache is older. Visually the anchor is re-drawn every
  scene (coupling 3).
- **Maturity.** L2 on the narration side; L0 on the visual side (no object persists
  across a cut).
- **Fine for v1?** ✅ — the first board after the change had a clean arc and the anchor in
  all six scenes (roadmap §3d).
- **v2 move.** Visual continuity: an anchor that persists or match-cuts across scenes.
  That needs either a shared-canvas render or a cross-fade at assembly, and it is the
  first capability on this list that needs L18 to be more than a concat.

#### 4.5 Screen planning — turning the arc into countable contracts

- **Statement.** Before writing any scene, decide what each screen must show and must
  say, so that under-delivery is a number rather than a feeling.
- **Hidden decisions.** Screen count; objects per screen (floor and ceiling); facts per
  screen and their citations; visual kind (diagram / simulation / derivation / comparison
  / image / data); variety across screens; whether the plan is enforced or advisory.
- **Today.** The deep path's ideator emits `must_show` / `must_say[+cite]` per screen,
  clamped 5–8 screens and ≤6 objects (`app/pipeline/screens.py:44`); `coverage()` grades
  the written scene against it. Measured on the live board
  (`.storyboard_cache/sb_bca1cb68b866b8f0.json`, `deep_trace.coverage`): screens 1–4
  over-deliver (5 required → 7 written, 4 → 9) and **screens 5 and 6 deliver 2 objects
  against 4 required** — recorded, not repaired. The plan is also not shown in the editor,
  though it is the most reviewable artifact the pipeline makes and comes before the
  expensive fan-out. **On the default path this link does not exist**: `DEEP_STORYBOARD`
  is absent from `.env` and defaults to `0` (`app/pipeline/deep_storyboard.py:44`).
- **Maturity.** L3 where it runs (measured, pinned by 72 checks); L0 for the default
  product.
- **Fine for v1?** ❌ — the one mechanism that makes "thin" measurable is off by default,
  and the reason it is off is that nobody can price it (4.21).
- **v2 move.** Make the plan the editable artifact: show it, let a person edit it, then
  fan out; and enforce coverage with a *single-screen* rewrite rather than a full
  regeneration.

#### 4.6 Scene authoring — the waist

- **Statement.** Write each scene as a finite set of named things, a sequence of spoken
  cues, and the events that bind them — in a vocabulary a deterministic renderer can
  honour.
- **Hidden decisions.** Everything the schema leaves open: how many elements (2–13 in the
  cache, mean 5.92 per scene); which of 10 types; ids (unique per scene, *not* per board);
  which of 6 event actions; colour (747 of 876 elements carry one); scale (default 0.7);
  whether structure is expressed as fields (`connects`, `inside`) or smuggled into prose;
  a composition sentence; a layout template.
- **Today — what the model actually writes** (`.storyboard_cache/`, all 27 boards):
  - events: **show 832 · hide 309 · highlight 54 · focus 19 · move_to 3 · transform 3** —
    show+hide are 93.5 % of 1,220 events; the two expressive verbs are 0.49 %.
  - structure fields: `connects` on **23/876** elements; `relation: "inside"` on **0/876**.
  - `composition` on 98/148 scenes; `layout_template` on 49/148, of which FullCanvas 33,
    SplitScreen 10, TitleStageCaption 6 — the two archetypes added on 08-15 (ProcessFlow,
    BeforeAfter) appear **0** times.
  - element types: text 357 · shape 249 · svg_icon 104 · math 85 · image 39 ·
    coordinate_system 23 · simulation 12 · chemical_molecule 6 · graph 1.
  - entrance: FadeIn 554 of 876 (63 %).
  - narration: 426 cues, mean 19.5 words, range 5–39.
  The gates around it are real: truncation and terminal-reason checks, a shape gate, a
  language gate with a heal pass, and a 48 h cache keyed on nine inputs. Three audits
  found the board-as-written *correct* and the video wrong anyway (§3c, §3d, §3e).
- **Maturity.** L3 for *admission* (gated, tested, 35 checks); L1 for *content quality*
  (no signal beyond shape).
- **Fine for v1?** ✅ — as a contract it is the strongest thing in the system. The
  numbers above are not a defect of the waist; they are what the waist reveals about the
  stages feeding it.
- **v2 move.** Stop asking one call for everything (the deep path, on by default once
  priced) and move the four most-ignored decisions out of the model entirely: colour
  (4.11 already overrides 96 % of it), scale (the director re-tiers it), entrance
  (code maps it by type and overrides unsafe ones), and position (code owns it for every
  graph, edge and child). What remains for the model is the part only it can do — *what*
  to show and *what* to say.

#### 4.7 Language realisation — the words in the learner's language

- **Statement.** Produce narration in the persona's language and script, on-screen text in
  the display language, and speak technical terms by a stated policy — consistently across
  every scene.
- **Hidden decisions.** Devanagari vs romanised Hinglish for narration; English-only,
  bilingual-once, or translated STEM terms; on-screen language; what the voice engine is
  told the language is.
- **Today.** One rule source (`language_rules`) shared by both authoring paths; a
  transliteration pass; a heal pass for on-screen labels that is accepted only if it
  removed the Indic script; a deterministic strip as the last line; `tech_terms` in the
  cache key. Pinned by 35 checks. The unsolved direction: a board whose narration came
  out all-English under a Hinglish persona fails loudly — inventing Hinglish from English is
  a content decision, not a normalisation.
- **Maturity.** L3.
- **Fine for v1?** ✅.
- **v2 move.** A script review before synthesis (the same pass 4.15 needs) that checks
  double-speak, filler and read-aloud quality in the *actual* language, since every word
  here is paid for twice — once to write, once to speak.

#### 4.8 Admission and memory — what is allowed in, and what is remembered

- **Statement.** Decide what counts as a complete, on-contract board; remember it so the
  same commission never pays twice; and make sure a change in how boards are written
  invalidates what was remembered.
- **Hidden decisions.** Completeness (empty cues, mid-tag cuts, terminal reason ≠ stop);
  language contract; the cache key's members; TTL; what a prompt change does to the cache.
- **Today.** Three gates, all pre-cache. Key = topic+persona+language+style+grade+subject
  +node_type+tech_terms+`PROMPT_VERSION` (`"2026-08-15-drawn-shapes"`,
  `app/storyboard.py:207`) +duration+deep-version, 48 h TTL (no TTL when grounding chunks
  key it). Bulk run: a fully cached topic ran in **105.1 s vs 769.8 s** cold — 7.3×
  (`bulk_runs/…/manifest.json`). Known holes: two prompt-shaping inputs and the pedagogical
  plan are not keyed (`docs/tuning.md`).
- **Maturity.** L3.
- **Fine for v1?** ✅.
- **v2 move.** A per-run folder that remembers *every* stage artifact (board, plan, code,
  clips, frames, cost) rather than a storyboard cache plus scattered directories — the
  one piece of plumbing that projects, resume, and chapters all need (4.19).

### Act II — Presentational

#### 4.9 Object realisation — what a named thing looks like

- **Statement.** Turn an element's description into a drawable object whose form
  carries the element's meaning, without letting the description's prose decide geometry.
- **Hidden decisions.** Primitive vs drawing vs simulation vs icon vs photo; what is
  *never* drawn (an edge derives from its endpoints; a bare primitive names nothing); the
  minimum complexity that distinguishes a drawing from a placeholder; whether a resolved
  asset is the *right* asset; what a degraded element becomes.
- **Today.** A head-noun table for primitives (word-start match on the description's head;
  contained values rendered inside); Manim-drawn objects for icons and shapes through the
  same verified `build(width,height)` contract as simulations (floors: 3 parts for an
  icon, 2 for a shape); a matplotlib tier; Wikimedia photos resolved server-side; a
  simulation that can't animate is drawn as a still. Caches on disk: 9 drawings, 4
  simulations, 3 generated SVGs, 29 photos (`stem_animation_lab/assets/*_cache/`).
  Measured history: **16 of 17 shapes drew wrong** on the Prime-Factorization board
  (roadmap §D-5); **14 of 16 shapes were content-free** and 14 icons were one keyword on
  the projectile board (§E-draw); simulations resolved **1/4 → 3/4** once a contract error
  stopped being treated as a security event (§3d). Nothing checks *resemblance*: a
  drawing is verified to exist, have parts, and stay in its box — not to look like a
  grandfather clock (catalogue 14).
- **Maturity.** L3 for existence/containment (112 checks incl. real renders); L0 for
  resemblance.
- **Fine for v1?** ✅ — the 08-15 jump from clipart to drawn objects is the largest
  visible quality gain on record.
- **v2 move.** A resemblance judge with a narrow question ("is this a grandfather
  clock?") as the first calibrated use of machine visual judgement — cheaper and more
  checkable than whole-frame review, and a prerequisite for trusting the latter.

#### 4.10 Spatial composition — where things sit

- **Statement.** Arrange a scene's objects so that nothing collides or clips, related
  things read as related, and the frame as a whole is balanced and full.
- **Hidden decisions.** The zone grammar (8 zones, 6 exposed to the model); fallback
  order; when to split the screen; graph layering direction; containment distribution;
  template archetypes; *where the visual weight sits*; alignment of unrelated groups;
  whether the model's stated composition is honoured.
- **Today.** Code, entirely: zone claiming with axes-aware routing and stacking toward
  centre; 5 templates; BFS tree layering for ≥3-node graphs (overrides model coordinates);
  grid distribution inside containers; split-screen on text pile-up. Measured: the
  axes+derivation fixture went **11 → 0** and the A/B **4 → 0** violations
  (roadmap §D). What it does not do: honour `composition` (logged 25 times in
  `logs/uvicorn_5000.log`, consumed by nothing — catalogue 9); balance the frame (§3e:
  "content occupies roughly the upper two-thirds; scenes 5 and 6 leave the bottom half
  empty"); express rows, columns or pairs (catalogue 10). The structural fields that
  would feed a better layout are barely used upstream (4.6: `inside` 0/876).
- **Maturity.** L3 for collision-avoidance; L1 for composition.
- **Fine for v1?** ⚠️ — collision-free is shippable; top-heavy and sparse is the thing
  viewers notice first.
- **v2 move.** A whole-frame pass after placement — centre of mass, equalised gaps, fill
  — behind a flag, judged by a per-scene vertical-centroid number logged for every render
  (catalogue 11 first, then 9, then 10). The option space is in §5.2.

#### 4.11 Visual hierarchy, lifetime and theme — what matters, how long it stays, what it looks like

- **Statement.** Decide which element is primary, when each one has finished its job, and
  give the frame one coherent look regardless of what colours the model guessed.
- **Hidden decisions.** Scale tiers; when to hide; emphasis treatment; canvas; whether a
  model colour survives; palette snapping; font.
- **Today.** Visual Director (**off** by default): model ranks, code applies ×1.2/×1.0/×0.8
  and safety-gated hides; deterministic enlarge-to-fill for sparse scenes runs even when
  the model is down. First live run: `40 rescaled, 0 hides, 14 highlights (3 rejected)`
  (roadmap §D). Theme: five profiles; **190/198 elements (96 %)** on six boards carried a
  model colour, so v1 theming touched ~4 % of the frame until harmonisation
  (§D-colour); emphasis is now colourless (a scale pulse). Font fixed on purpose — a font
  swap moves text metrics and needs a fresh probe pass.
- **Maturity.** L3 for theme (52 checks); L2 for the director.
- **Fine for v1?** ✅.
- **v2 move.** Scene-level colour assignment (distinct hues per scene, neighbour-aware)
  and role-keyed archetypes that reconcile `role`, `visual_kind` and `layout_template`
  into one vocabulary instead of three.

### Act III — Temporal

#### 4.12 Motion — making the picture do what the words describe

- **Statement.** Make things on screen move in ways that *explain* — a vector sweeping, a
  curve tracing, a system evolving — rather than merely appearing, sitting, and leaving.
- **Hidden decisions.** The event vocabulary (6 actions); who authors motion (model vs an
  agent vs code); what fills a beat's dead air; whether a system can evolve over time at
  all; caps per cue and scene; what is never moved (axes, edges, children, simulations).
- **Today.** Three layers, each added after the previous proved insufficient: the Motion
  Director authors `move_to`/`transform`/`focus` the storyboard model never writes (census:
  92 show / 42 hide / 6 highlight / **0** motion across three live boards, roadmap §D);
  `sustain` fills the ~half-beat of dead air with round-trip gestures (a
  `with voiceover` block plays 2–3 s of animation inside an 8–12 s beat); `simulation`
  elements let a model write one verified `build/animate` pair for one element — the only
  place an LLM writes Manim. A simulation plays once, in its cue, and the probe sees only
  its final frame.
- **Maturity.** L3 for the mechanisms (real-render tests for round-trip drift < 1e-3, 112
  simulation checks); L1 for *explanatory* motion — gestures point, they don't demonstrate
  (catalogue 13).
- **Fine for v1?** ⚠️ — no longer a still picture of a moving thing, but the ordinary
  case (an existing element moving to make a point) still depends on an intent that is
  almost never produced upstream.
- **v2 move.** Simulations that evolve across cues (a wave whose frequency changes as the
  narration explains frequency) — a `simulation` + event vocabulary — and a mid-animation
  probe so motion is measured, not just final frames.

#### 4.13 Voice — the words as sound

- **Statement.** Synthesise each cue in the right voice and language, cheaply, and never
  let a provider blip become a lost render or a silent video.
- **Hidden decisions.** Provider order; retry vs failover; whether silence is acceptable;
  what is cached and under what key; what "degraded" means on a healthy run.
- **Today.** primary → Gemini → keyless gTTS → silence (opt-in); retries on 5xx/429/
  timeout/empty-200; `TTS_DEGRADED:` markers counted into the sidecar — **8 of 32** voiced
  sidecars show ≥1 degraded cue, worst 32 (`static/videos/*.mp4.json`); one muted render.
  A content-addressed cross-render cache is documented as the reason repair re-renders
  bill zero audio — and `.tts_cache/` at the repo root, the directory the code resolves
  to (`viz_helpers.py:1235-1245`), holds **0 files** as of today. Either every recent
  render degraded to a tier that does not store, or stores fail silently; this document
  records the observation and does not attribute it. The server log's last voice entry is
  an OpenRouter `HTTP 402: Insufficient credits` falling through to gTTS
  (`logs/uvicorn_5000.log:990`).
- **Maturity.** L3 on resilience (17 + 17 checks); the cache's *effect* is unverified on
  disk.
- **Fine for v1?** ✅ for resilience; ⚠️ until the empty cache is explained, because
  every repair round may be re-billing audio.
- **v2 move.** Voice as a *reviewable* artifact: a script gate before synthesis, and
  per-cue audio kept in the per-run folder so a one-sentence edit re-synthesises one cue.

#### 4.14 Sync — when the named thing appears

- **Statement.** Make each thing appear at the moment the narrator names it.
- **Hidden decisions.** Whether timing is clock-based (fraction of beat) or word-based;
  where word timestamps come from; whether audio adapts to animation or the reverse;
  what pacing is right for a grade.
- **Today.** Clock-based: a per-type fraction-of-beat with a floor (`transpiler.py:182`),
  capped at the beat; the rest of the beat is `sustain`. No word is ever aligned to an
  event. The mechanism for a middle path — bookmarks inside one voice clip — is in the
  dependency already and unused (roadmap row 11). Dead air is not measured anywhere; the
  only signal is Vision QA calling frames "dead", which it did for 6/6 sampled frames on a
  run where the sampler had landed on scene boundaries (§G).
- **Maturity.** L1.
- **Fine for v1?** ⚠️ — "accompanied, not explained" (catalogue 12); viewers tolerate it.
- **v2 move.** Bookmarks: the storyboard marks the word, the entrance waits for it, one
  clip per cue stays (nothing re-bills). The research tail — word alignment for
  code-switched Hinglish — stays research.

### Act IV — Realisation & verification

#### 4.15 Program synthesis and static safety — from IR to a script that cannot fail in the known ways

- **Statement.** Emit a program that realises the Layout and Animation IR exactly, and
  make every class of render-time failure already seen impossible by construction.
- **Hidden decisions.** One script vs per-scene scripts; what a critic may change; what a
  sanitiser strips; which references are legal across scenes; what an entrance may be on
  a given object family.
- **Today.** A 2,110-line deterministic transpiler (`transpiler.py`) with a 2,160-line
  runtime library (`viz_helpers.py`) is the sole full-scene path; the model-codegen path is
  a fallback. A model critic may rewrite layout under three invariants (no element, no
  structural helper, no zone anchor lost) — each invariant added after a *different*
  destruction (six sweets collapsed to one; a caption dropped through a tree). Per-scene
  isolation drops cross-scene events; the master script resolves ids per scene,
  backwards only. ~865 deterministic checks across 23 harnesses pin it
  (`stem_animation_lab/test_*.py`). The debugger traces show where failures *used* to
  land: of 70 failed traces, **52 failed at compile**, 11 at storyboard, 7 at codegen
  (`debug_sandbox/debug_traces/`).
- **Maturity.** L3.
- **Fine for v1?** ✅ — this is the system's strongest act.
- **v2 move.** Retire the critic. Every power it has is one the transpiler should own; a
  rewrite pass whose acceptance list keeps growing is a layout engine with a model in
  the loop. The same argument applies to repair (4.17).

#### 4.16 Render and measurement — making the clips and finding out what went wrong

- **Statement.** Render each scene and measure, after every beat, whether the frame is
  legible — with a measure that reads zero on a healthy run and never flags what is fine.
- **Hidden decisions.** What a violation is; which object kinds are visible to the
  measure; when to sample (after each play only); how many to report; render quality;
  parallel vs sequential; what a "render failure" is (infra / LaTeX / code).
- **Today.** Three counted classes (text-on-text, clipped text, text-over-shape), one
  measured-but-uncounted class (shape-on-shape, present in **10 of 19** sidecars that
  record it), two blind spots by design (images, simulations in motion), one by sampling
  (mid-animation). Vision QA (**off**) adds a seven-class whitelist from a multimodal call;
  31 of 34 sidecars show 0 findings because it rarely ran. Render is ~70 % of median wall
  time (compile median 94.0 s of 134.1 s total, `debug_traces/`, n=171); the parallel path
  cut one run from 313 s to 69 s (§3e). Failure classification keeps a TTS outage away
  from the code-repair model.
- **Maturity.** L3 for geometry (33 real-render checks); L1 for perception.
- **Fine for v1?** ✅ for what it measures; the honest caveat is that three audits in a
  row found defects in classes it doesn't (§3c, §3d, §3e).
- **v2 move.** Coverage before depth: count shape-on-shape, measure text-over-image with a
  centre-in-bbox test, sample mid-transition — each a new class with its own weight, graded
  passively on real runs before it may trigger repair. Then a frame-aware probe, which is
  what unblocks camera moves.

#### 4.17 Repair — improving without destroying

- **Statement.** Given measured defects, produce a better artifact, never a worse one, and
  know when to stop.
- **Hidden decisions.** What the repair model sees; what it may touch; acceptance rule;
  what must survive; round cap; whether to repair code or the plan; when a defect is not
  repairable at this stage; whether a fix is remembered.
- **Today.** Accept-if-better per scene (renders AND fewer violations), losers deleted,
  original never lost; four preservation guards (photos, simulations, sim playback,
  drawings) each added after a repair traded the asset away. Measured over 46 sidecars:
  repair rounds **0 → 10, 1 → 14, 2 → 12, 3 → 8, 4 → 2**; violations remaining
  **0 → 23 files (50 %)**, ≥1 → 23, tail up to 14. The debugger's older traces show what
  repair costs: compile-stage tokens **1.12 M in / 191 k out** versus codegen's
  312 k / 262 k — the fix loop spends 3.6× the input tokens of the stage it fixes, and
  its estimated cost exceeds initial codegen (`debug_traces/`, 171 traces). A vision
  round on the optical-fibre run spent 4 rewrites + 4 re-renders + 1 re-critique and
  bought nothing (§G). Nothing classifies the residue, and the fix memory (error→repair
  store) is built and off.
- **Maturity.** L3 on safety (the never-lose rule is the house template); L1 on
  convergence.
- **Fine for v1?** ⚠️ — safe, and half of videos still ship with a known unrepaired
  violation.
- **v2 move.** Classify the 23 residues by kind (it costs reading), then repair the
  *plan* and re-derive for the classes that are layout, and route upstream the classes
  that are content. A code-rewriting model is the one place the house rule is inverted
  (catalogue 16).

#### 4.18 Assembly and the record — one video, and the truth about it

- **Statement.** Join the clips into one artifact and attach everything a later reader
  needs to trust or reproduce it.
- **Hidden decisions.** Cut vs transition; what the record contains (geometry only, or
  cost, duration, elements, provenance, which renderer produced the file); where
  artifacts live; retention.
- **Today.** ffmpeg concat, hard cuts; a nine-field sidecar (`job_id, repair_rounds,
  violations_remaining, animation_beats, scenes_repaired, vision_findings,
  voice_degraded, shape_overlaps, voice_muted`) — **no duration, no cost, no element
  survival, no render-path field** in any of the 46. The lesson side's cost ledger reads ~0
  for every video because the engine reports no usage back (roadmap §H). Artifacts scatter
  across `static/videos/`, `temp_renders/`, `media/`, `bulk_runs/`; the sweep is 24 h.
- **Maturity.** L2.
- **Fine for v1?** ❌ — a video that cannot say what it cost, how long it is, or which
  renderer made it cannot be compared with its neighbour, and every default in this
  system is set by that missing comparison (4.21).
- **v2 move.** The per-run folder with `cost.json`, every stage artifact, and a sidecar
  that names the render path. This single move unblocks 4.5, 4.8, 4.13, 4.19, 4.21 and
  chapters.

#### 4.19 Delivery and review — the human in the loop

- **Statement.** Show a person what was made, let them steer the decisions that were made
  explicitly, and re-make only what they changed.
- **Hidden decisions.** What a badge means; what is editable (IR, not code); whether edits
  are validated; what an edit re-renders; where a project lives.
- **Today.** A timeline with geometry badges; a scene-first editor over the IR (Content /
  Motion / Audio / Style tabs, voice audition, polled task routes); a bulk runner that is
  resumable and has one real run on disk (5/5 done, 43.6 min of work across 5 topics).
  Projects live in browser storage; edited boards skip the generation-time gates; any edit
  re-renders everything (catalogue 24, 25). The blueprint preview is drawn from the
  pre-director IR with none of the layout logic and is routinely mistaken for an input.
- **Maturity.** L2.
- **Fine for v1?** ✅ for a single operator on one machine; ❌ for anything shared.
- **v2 move.** Server-side projects on the per-run folder, gate-validated edits, and
  per-scene re-render + re-join — and the screen plan as the thing a person edits first.

---

## 5. The option space

Each subsection takes a stage where the system implements **one** answer to a
many-answer question and lays out the family. Columns: what the option *teaches or buys*,
and what *representation* it needs to exist. The representation column is the point: it
is where the ladder in §5.10 comes from.

### 5.1 How a scene gets written

| Option | What it buys | Representation required | Status |
|---|---|---|---|
| One call writes the whole board | cheapest; one coherent voice | topic + plan | **default** |
| One call per screen against a plan (deep path) | detail per scene; thinness countable | screen plan with `must_show`/`must_say` | built, off |
| Plan → write → *critique* → targeted rewrite of one screen | fixes the two under-delivered screens without regenerating six | per-screen coverage + a rewrite entry point | coverage exists; rewrite absent |
| Retrieval of prior scenes/templates by visual kind | consistency across a corpus; fewer invented layouts | a library of verified scenes keyed by kind | absent |
| Human-authored plan, model-written scenes | the editor's real job | editable plan surfaced in the UI | plan exists, not surfaced |
| Iterative board refinement from rendered frames | closes the IR-vs-frame gap | frame→IR attribution | absent (vision attribution exists per scene) |

### 5.2 How a frame is laid out

| Option | What it buys | Representation required | Status |
|---|---|---|---|
| Model emits coordinates | nothing — measured wrong at every audit | — | **rejected on evidence** (D1) |
| Zone claiming with fallback chains | collision-free by construction | 8 zones, per-element zone | **default** |
| Templates / archetypes | a recognisable shape per pedagogical role | `layout_template` (5 values) | 3 used, 2 never |
| Graph auto-layout (tree / DAG) | correct diagrams from declared edges | `connects` | built; 2.6 % of elements use it |
| Containment distribution | contents inside their container | `relation: inside` | built; **0 % use it** |
| Radial / force-directed / left-to-right flow | the other diagram families (cycles, networks, processes) | `connects` + a layout-kind hint | absent |
| Row / column / pair primitives | ordinary composition ("these three in a row") | new relations with gap and alignment | absent |
| Whole-frame balance pass (centroid, gaps, fill) | frames that aren't top-heavy | bounding boxes of everything placed (exists at render) | absent |
| Composition-descriptor keyword map | honour the intent the model already wrote | the `composition` string (98/148 scenes have one) | absent — logged only |
| Constraint solver (Cassowary-class) | all relations at once; re-solvable after repair | rows/columns/inside/edges declarable | absent; premature until the relations are used |
| Grid / baseline system | alignment of unrelated groups | a global grid the zones snap to | absent |

### 5.3 How things move

| Option | What it buys | Representation required | Status |
|---|---|---|---|
| Entrance by element type, timed by fraction of beat | variety; safe | element type | **default** |
| Event verbs (show/hide/highlight/focus/move_to/transform) | intent-driven changes | 6-action events | 93.5 % show/hide in practice |
| Beat filler (round-trip gestures) | no frozen frames | what entered this cue | default |
| Motion Director (agent writes the verbs) | motion without the author | events + per-scene element registry | on |
| Verified per-element simulation | a system that evolves | `simulation` element + `build/animate` | on; plays once |
| Simulation driven across cues | the wave changes *as* the narration explains | simulation + parameter events | absent |
| Morph / match-cut across scenes | continuity of the anchor | persistent object identity across scenes | absent |
| Data-driven tracing (curve drawn as function is explained) | the 3Blue1Brown grammar | axes + function + a trace event | partial (axes exist; no trace verb) |
| Camera moves | emphasis by framing | a frame-aware verifier | **deliberately absent** |
| Word-synced entrances | explained, not accompanied | word bookmarks in cue text | mechanism present, unused |

### 5.4 What a named object becomes

| Option | What it buys | Representation required | Status |
|---|---|---|---|
| Primitive table by head noun | cheap, deterministic | shape `content` prose | default for primitives |
| Clipart icon cascade | a recognisable noun | keyword | demoted (nearest-match failure) |
| Matplotlib-drawn SVG | a drawing when the cascade misses | `def draw(ax)` | last-tier |
| Manim-drawn object (verified) | structure, not a symbol | `build(width,height)` + min-parts floor | **default** for icons/shapes |
| Real photograph | narrative topics | a Commons query + licence sidecar | on, ~80 % hit |
| Curated component library (verified, reusable) | consistency; zero calls | a keyed library of verified builds | the caches are a seed of one |
| 3D / physical renders | materials, volumes | a different renderer backend | out of scope |
| Resemblance-checked drawing | the drawing looks like the thing | an image judge with a narrow question | absent |

### 5.5 Where the facts come from

| Option | What it buys | Representation required | Status |
|---|---|---|---|
| Topic string only | nothing but the model's prior | — | the common case (24/27 cached boards) |
| NCERT node text | the syllabus's own words | lesson-side context | lesson path only |
| Given link transcript | the teacher's chosen source | chunked transcript | on |
| Web search | freshness; coverage | a search key | off |
| Citable chunks (`[S2#1]`) + `must_say.cite` | auditability | ResearchPack | on, unaudited |
| Fidelity spot-check | a number for invented facts | chunk ↔ narration trace | absent |

### 5.6 How the voice is made and timed

| Option | What it buys | Representation required | Status |
|---|---|---|---|
| One clip per cue | cacheable; simple | cue text | **default** |
| One clip per element | sync by construction | per-element narration split | rejected on cost |
| Bookmarks inside one clip | sync without re-billing | marked cue text | unused |
| Forced alignment after synthesis | word timestamps | an aligner that handles Hinglish | research |
| Script gate before synthesis | protect the costliest spend | a critic over cue text | absent |

### 5.7 How the output is judged

| Option | What it buys | Representation required | Status |
|---|---|---|---|
| Geometric probe (3 counted classes) | legibility, deterministically | instrumented play calls | **default** |
| Shape-on-shape, text-over-image, mid-animation classes | the defects the audits keep finding | same probe, new classes | first measured, rest absent |
| Vision-model frame review | what a person would say | sampled frames + whitelist | built, off, mis-sampled |
| Pixel-level checks (dead space, contrast, ink centroid) | cheap objective composition numbers | rendered frames | absent |
| Rubric LLM-judge over board + transcript | coherence, pacing, match | a rubric + calibration set | absent |
| Pedagogy lints (law stated, terms before use, question answered) | catches the one real failure on record | the board | absent |
| Fidelity spot-check | invented facts | chunks + narration | absent |
| Human rating on a fixed suite | the only ground truth | a fixed topic suite + the bulk runner | runner exists; suite doesn't |
| Learner outcome study | whether it teaches | learners | research |

### 5.8 How a defect is fixed

| Option | What it buys | Representation required | Status |
|---|---|---|---|
| Model rewrites the scene's code, accept-if-better | safe improvement | violation lines + the script | **default** |
| Parameter search on the deterministic emitter (zone, scale, split) | no model, re-solvable | layout knobs as data | absent |
| Repair the IR and re-transpile | consistent with the house rule | IR-level attribution of each violation | absent |
| Fix memory (fingerprint → known fix) | never pay twice | error store | built, off |
| Route upstream (content defects) | stop asking layout to fix a thin board | a classification of residues | absent |
| Stop rule | know when another round is waste | residue classification | absent |

### 5.9 How scenes relate to each other

| Option | What it buys | Representation required | Status |
|---|---|---|---|
| Isolated per-scene renders, hard cuts | parallel, robust | per-scene scripts | **default** |
| Master script, backward references only | cross-scene references | global namespace | fallback path |
| Cross-fade at assembly | softer seams | ffmpeg xfade on the parallel path | absent |
| Persistent anchor object | the story's example stays on screen | object identity across scenes | absent |
| Chapters with a running summary | lesson length | chapter outline + summary thread | designed, not built |

### 5.10 The representation ladder

You cannot climb higher than the representation you kept. Reading §5.1–5.9 by the
"representation required" column gives the ladder — each rung is information that must
exist in the IR (or a sidecar) before the capability above it is *possible*, regardless
of effort:

```
 rung 0  topic string                         → a plausible video
 rung 1  + citable chunks                     → auditable facts            (kept; unaudited)
 rung 2  + screen plan (must_show / must_say) → countable thinness         (kept on the deep path only)
 rung 3  + narrative (anchor, roles)          → an arc                     (kept; narration-side only)
 rung 4  + structure fields (connects/inside) → correct diagrams           (kept; ~0–3 % populated)
 rung 5  + row/column/pair relations          → composed frames            (NOT kept — blocks 5.2's solver/balance)
 rung 6  + composition intent as data         → honoured layout intent     (kept as prose; consumed by nothing)
 rung 7  + word marks in cues                 → synced entrances           (NOT kept — blocks 5.6 bookmarks)
 rung 8  + object identity across scenes      → persistent anchor, match-cuts (NOT kept — blocks 5.9)
 rung 9  + per-run record (cost, duration, path, element survival) → comparable runs, priced defaults (NOT kept — blocks every default decision)
 rung 10 + simulation parameters as events    → systems that evolve with the narration (NOT kept)
```

Three observations fall out of the ladder:

- **Rungs 1–4 and 6 are already kept and under-used.** The information exists; the
  consumers don't (composition), or the producers rarely emit it (`inside` 0/876). That
  is a producer/consumer problem, not a representation problem, and it is cheap.
- **Rungs 5, 7, 8 are the true ceilings on the visible product.** Composed frames, synced
  entrances and a persistent anchor are each blocked by one missing field, not by
  effort. All three are IR schema changes; the drift gate (`test_ir_contracts.py`) makes
  each a one-pass change.
- **Rung 9 is the ceiling on the *process*.** Without a per-run record, no default can be
  priced, so the three most capable stages ship off (§7).

---

## 6. Cross-cutting problems

These are not stages. Each cuts across the acts and is owned, today, by nobody in
particular.

### 6.1 Evaluation — is the output any good, and can the system tell?

What is measured: text geometry (three classes, counted), shape-on-shape (measured),
voice degradation, narrative cold-opens, duration drift, element survival, screen
coverage. What is not: whether a frame is composed, whether a drawing resembles its
subject, whether the narration is true to its source, whether the lesson teaches, whether
the video is *good*. Every quality regression on record was found by a person watching
(§3c, §3d, §3e), and every improvement was judged the same way. The bulk runner — the
natural evaluation harness — has one real run. **The system can prove a video is
geometrically clean and cannot say whether it is any good** (catalogue 1, P01). The
house rule that a health metric must read zero on a healthy run (the `voice_degraded: 24`
false positive) is the right discipline for every metric added here.

### 6.2 Provenance and grounding

Chunks are citable, `must_say.cite` records them, the Wikimedia sidecar records licence
and artist, the simulation/drawing caches record the code and attempt count. Nothing
checks that the narration kept a cited fact, and no on-screen attribution line exists
for CC-BY photos (a licence obligation). Provenance that is recorded and never read is
a cost without a return.

### 6.3 Identity and continuity across units

Element ids are unique within a scene and routinely repeated across scenes (measured: 5
repeated ids, 2 forward references on one board — CLAUDE.md, master-script rule). The IR
has no notion of "the same object" across scenes, so the anchor is redrawn, the theme's
per-scene palette cursor resets, and transitions are cuts. At chapter scale the same gap
becomes terminology drift across eight boards — the running-summary thread (roadmap §6)
is the same problem one level up.

### 6.4 Cost as a design variable

There is no billing record. The only cost data on disk is the debugger's own estimate
over 171 traces (TTS 57 %, compile-repair > initial codegen). Consequences, all measured:
three of the four agent stages default **off** (`DEEP_STORYBOARD`, `VISUAL_DIRECTOR`,
`VISION_QA` absent from `.env`, code defaults `0`), four flags cannot even be flipped per
job (`DEEP_STORYBOARD`, `MOTION_DIRECTOR`, `SIM_GEN`, `DRAW_WITH_MANIM` are not in the
12-entry override allowlist, `app/config.py`), and "is this experiment worth running
twice?" has no answer. Two rules from prior art are worth adopting verbatim: a cache hit
is recorded at would-have-cost, and unknown cost displays as *unknown*, never zero.

### 6.5 The human control surface

A person can only steer a decision some component makes explicitly. Steerable today:
persona, language, tech-terms policy, style profile, duration target, sources, the model
chains, the repair/render knobs in the allowlist, and — in the editor — every IR field per
scene. Not steerable because nobody decides it: frame balance, word-to-event timing,
which violation classes matter, when repair stops. Not steerable because it is decided
implicitly: the screen plan (not shown), the composition intent (not consumed), which
renderer produced the file (not recorded). **The editor's ceiling is the IR's ceiling**:
it cannot offer a control for a rung the IR does not keep.

### 6.6 Reproducibility and state

What is running lives in memory and dies with the process; a model call with no time
limit can leave a job "running" forever (21 of 185 debugger traces are still `running`);
artifacts live in five directories; a crashing scene silently swaps render paths; two
processes (the server and an in-process harness) can run different code against the
same artifacts and an hour was lost to that on 2026-08-15. None of this is exotic — it
is the per-run folder, a job file, and a render-path field in the sidecar.

### 6.7 Localisation

The product's default is Hinglish narration with English on screen, English-spoken STEM
terms, and an Indian-English voice chain. This is solved to L3 at the contract level
(4.7) and unsolved at the alignment level (4.14): every forced-alignment tool degrades on
code-switched romanised text, which is exactly the register this system speaks. The
grade-band pace table is the only pedagogy-of-language decision in the system and was
wrong for two years of grades until 07-20.

### 6.8 Compliance

CC-BY photographs require on-screen attribution; the data is in the sidecar and no
attribution line is rendered. Model-written code runs under a sandbox (`python -I`,
scrubbed env, static gate, timeout) at two sites (drawings, simulations); the gate is the
boundary and is tested as one.

---

## 7. Synthesis — what the decomposition reveals

**(a) Where the named problems cluster, and why.** Lay the register (§8) over the acts
and the pattern is stark. Act IV is L3 almost everywhere; Act II is L3 where code owns the
decision and L1 where it doesn't; Acts I and III are L1–L2 throughout. The line that
separates them is not effort — Act I has received as much work as Act IV this month. It is
**ownership**: every L3 is a decision code makes and a probe measures; every L1 is a
decision that was outsourced to a model (what to show, what colour, what moves) or to a
service (what a photo looks like, when the voice fails) and therefore never surfaced as a
*problem* — only as a complaint about a video. "Outsourced and invisible" is the finding.
It costs three things: reproducibility (the same commission yields a different board;
a 48 h cache hides it), steerability (nobody can tune what nobody decides — §6.5), and
ceilings (the model is asked to make layout, colour and motion decisions it makes badly,
at token cost, which code then overrides — §4.6's four migrations are the evidence).
The four unowned outcomes in §2 (relevance, balance, alignment, termination) are the
purest form: not outsourced to anyone, so not a problem anyone has.

**(b) The one move that unblocks several problems.** Two candidates, at different
altitudes:

- *Process altitude:* **the per-run record** — one folder per run holding every stage
  artifact plus `cost.json`, and a sidecar that names duration, render path and element
  survival. It is plumbing, and it is rung 9 of the ladder. It unblocks pricing the
  three off-by-default stages (the capability decisions this system most needs to make),
  resume, server-side projects, per-scene re-render, chapters, and the comparison of any
  two runs — which is what every other problem on this list needs to be *graded*.
- *Product altitude:* **keep rungs 5/7/8** — row/column relations, word marks, object
  identity. Three optional IR fields, each a one-pass schema change under the existing
  drift gate, and together they are the difference between "tidy" and "composed, synced,
  continuous". They are blocked by information thrown away at the waist, not by effort.

If one must come first, the record does: without it the three fields cannot be shown to
have helped, and this system's own discipline (grades are earned from evidence) forbids
shipping them on that basis.

**(c) What is genuinely good.** The decomposition is a map, not a complaint, and the map
has a strong quadrant. The Storyboard IR as a gated, cached, schema-drift-tested waist;
the deterministic transpiler with layout-by-construction, structure as fields, one table
driving object and entrance; the verify-before-ship contract for model-written code
(drawings and simulations stepped by hand with no renderer); the accept-if-better repair
loop that has never lost an incumbent; voice resilience that ends keyless; loud
degradation everywhere; ~865 deterministic checks pinning real failures; and the
operating discipline itself — attribute upstream first, one lever per experiment, a
health metric reads zero on a healthy run, a prompt change is a billing change. Those are
not v1 compromises. They are the reason the next version can be *chosen*.

---

## 8. Register

| # | Sub-problem | Who decides today | Maturity | v1 verdict | v2 move |
|---|---|---|---|---|---|
| 4.1 | Commissioning | model (whether/type), code (length) | L2 | ✅ one-topic explainers; 4 min ceiling by construction | chapter outline decides length once |
| 4.2 | Grounding | code (tiers), nobody (relevance) | L2 | ⚠️ fine for known STEM, risky for narrative topics | fidelity spot-check: N facts traced, pass rate |
| 4.3 | Lesson decomposition | model (units), code (count, pace) | L1–L2 | ⚠️ no signal when the units are wrong | mechanical pedagogy lints before spend |
| 4.4 | Narrative | model; code measures | L2 / L0 visual | ✅ arcs now measured | anchor persists across the cut |
| 4.5 | Screen planning | model, code-clamped; **absent on default path** | L3 / L0 | ❌ the thinness measure is off by default, unpriced | show + edit the plan; single-screen rewrite |
| 4.6 | Scene authoring (waist) | model within schema bounds | L3 admission / L1 content | ✅ strongest contract in the system | move colour/scale/entrance/position out of the model |
| 4.7 | Language realisation | code (policy), model (wording) | L3 | ✅ | script gate before synthesis |
| 4.8 | Admission + memory | code | L3 | ✅ | per-run folder replaces the board cache + scattered dirs |
| 4.9 | Object realisation | code routes; model draws; external for photos | L3 exist / L0 resemble | ✅ largest visible gain on record | narrow resemblance judge |
| 4.10 | Spatial composition | code; nobody (balance) | L3 collision / L1 composition | ⚠️ collision-free, top-heavy | whole-frame balance pass, measured by centroid |
| 4.11 | Hierarchy, lifetime, theme | code (director off) | L3 theme / L2 director | ✅ | scene-level colour; one role vocabulary |
| 4.12 | Motion | code + agent; model for simulations | L3 mech / L1 explanatory | ⚠️ points, doesn't demonstrate | simulations driven across cues; mid-animation probe |
| 4.13 | Voice | code (chain), external (sound) | L3 resilience | ✅ / ⚠️ shared cache empty on disk | script gate; per-cue audio in the run folder |
| 4.14 | Sync | code (clock); nobody (words) | L1 | ⚠️ accompanied, not explained | bookmarks in cue text |
| 4.15 | Program synthesis | code; model critic under invariants | L3 | ✅ strongest act | retire the critic into the transpiler |
| 4.16 | Render + measure | code | L3 geometry / L1 perception | ✅ for what it sees | new classes: shape-shape, text-image, mid-transition; frame-aware probe |
| 4.17 | Repair | code accepts; model fixes; nobody stops | L3 safety / L1 convergence | ⚠️ safe; 50 % ship with a residue | classify residues; repair the plan, route content upstream |
| 4.18 | Assembly + record | code | L2 | ❌ no cost, duration, path or survival in the record | per-run folder + `cost.json` + render-path field |
| 4.19 | Delivery + review | code; human judges | L2 | ✅ single operator / ❌ shared | server projects; validated edits; per-scene re-render |
| 6.1 | Evaluation | human | L1 | ❌ cannot tell good from bad | scorecard with honest unknowns; fixed suite through the bulk runner |
| 6.4 | Cost | nobody | L0 | ❌ | record it; unknown ≠ zero |

**The rows that decide the next version:**

1. **4.18 Assembly + record (with 6.4 Cost).** Rung 9. Everything off-by-default stays
   off until a run can say what it cost and which renderer made it. This is the smallest
   row with the largest unblocking radius.
2. **4.10 Spatial composition (with 4.14 Sync).** Rungs 5 and 7. The two defects a viewer
   notices first — top-heavy frames and entrances that don't track the words — are each
   one missing IR field away, and each has a deterministic consumer already half-built
   (zone allocator; bookmarks).
3. **4.5 Screen planning.** Rung 2, already built, off. Turning it on — priced by row 1,
   surfaced in the editor — is the difference between a model that sketches and a model
   with a contract, and it is where a human first gets to steer *content* rather than
   presentation.

Everything else on the register is either already good enough for the current product or
is research that should be scoped as a study (4.3's learner outcomes, 4.14's Hinglish
alignment, 6.1's pedagogy score).
