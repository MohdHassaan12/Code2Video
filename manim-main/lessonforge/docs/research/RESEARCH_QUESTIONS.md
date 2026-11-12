# Research questions — unified register

Written 2026-10-07 for the lessonforge merge. This file is a synthesis of two existing
document sets. No new measurement was taken for it; every number is quoted from a
source file that is named next to it.

> **After this register was written (same day, 2026-10-07)** the long-form port, the
> bridge and a first content harness landed, so entries below that say "porting" or
> "being built" describe code that now exists. Measured during the merge — these are
> the only new measurements, and they are production checks, not learner evidence:
> - The engine's per-play probe, run on the reviewed Pythagoras lesson for the first
>   time, reported 3 counted findings where the beat-end bounds audit had reported 0:
>   one real collision (a label on the ladder rungs, chapter 7, since fixed) and two
>   flags on labels with an opaque backing plate (now exempt). Relevant to RQ-17.
> - Block-level synthesis of the same script (40 blocks instead of 274 sentences, no
>   retiming) gives 1185.6 s; 268 of 274 sentence starts were located on a real pause,
>   6 are arithmetic estimates and are labelled as such. Against per-sentence
>   synthesis of five beats, boundaries differed by a median 0.19 s (max 0.63 s, n=33)
>   — a sanity check between two syntheses, not alignment accuracy. Nobody has
>   listened to the result. Relevant to RQ-11 and RQ-12.
> - The harness (`src/lessonforge/harness/`) writes long lessons chapter by chapter
>   against a ledger and reports continuity as counts. It has only been run with a
>   stubbed model and with the no-model outline. Relevant to RQ-24 and RQ-25.

Contents: [1 How to read this](#1-how-to-read-this) ·
[2 Master table](#2-master-table) ·
[3 The questions](#3-the-questions) ·
[4 Where the two projects disagree](#4-where-the-two-projects-disagree-or-pull-in-different-directions) ·
[5 What each side already solves for the other](#5-what-each-side-already-solves-for-the-other) ·
[6 One prioritised sequence](#6-a-single-prioritised-sequence-proposal) ·
[7 Appendix: ID crosswalk](#7-appendix-id-crosswalk)

---

> **Status 2026-10-08 (second note).** First end-to-end run with real models is done and measured —
> see `experiments/2026-10-08_openrouter_run/REPORT.md`. Answered or moved today: RQ-12 (estimated
> anchors were off by a median 0.40 s, p90 1.17 s; alignment now measures every word), RQ-26 (one
> ledger, budget enforced), RQ-04 (chapter contract + model-updated ledger + repeat metric),
> RQ-01/05 (cross-family critic, code-checked claims, pause gate), RQ-20 (vision sampling at cue
> onsets; still advisory). Approach surveys per problem are in `approaches/01…05`.

## 1. How to read this

**The two sources.**

- **A — "the engine"** (from the concept_explorer repo). An LLM writes a storyboard IR, a
  deterministic transpiler turns it into Manim, a layout probe measures every play, and
  an accept-if-better loop repairs. Short videos, Hinglish narration by default. Its
  research documents are dated 2026-08-22 (the problems site was audited 2026-07-27 and
  updated 08-01/08-03); the pipeline roadmap has dated entries from 2026-07-19 onward.
- **B — "the review"** (from the education_content_review repo). A meeting-driven
  literature and code review, a small paid model pilot, and one hand-repaired,
  audio-first, 20-minute English lesson on Pythagoras. Its documents are dated
  6–7 October 2026.

**IDs.**

| Prefix | Meaning | Source file |
|---|---|---|
| `RQ-01`…`RQ-30` | unified question (this file) | — |
| `ENG-1`…`ENG-5` | engineering task that is honestly not a research question (§7.9) | — |
| `R1`…`R18` | A's research problems | [research-agenda][agenda] |
| `cat-1`…`cat-25` | A's problem catalogue | [problem-catalogue][catalogue] |
| `P01`…`P11` | A's deep-dive site | [problems/index.html][site] |
| `dec-4.1`…`dec-4.19`, `dec-6.1`…`dec-6.8` | A's sub-problems and cross-cutting problems | [problem-decomposition][decomp] |
| `M1`…`M7`, `v1.1`…`v3.0` | A's milestones and version plan | [improvement-timeline][timeline], [agenda §8][agenda] |
| `road-§X`, `road-#N` | A's roadmap stage section / priority row | [pipeline-roadmap][roadmap] |
| `B-A`…`B-H` | B's eight problems (lettered A–H in the source; prefixed here so they do not collide with A's roadmap stages A–J). `B-E3` is approach E3 | [method comparison][methods] |
| `T01`…`T14` | B's prioritised tasks | [HANDOFF_REPORT][handoff] |
| `09-T1`…`09-T8` | a second, separately numbered task list in B | [09 combined architecture][lf09] |
| `HD-1`…`HD-8` | the eight rows of B's known-defects table, in order | [HANDOFF_REPORT][handoff] |
| `WS1`…`WS7` | B's workstreams | [project/workstreams](../project/workstreams/) |
| `LH-1`…`LH-6` | B's six testable hypotheses, in order | [literature review][lit] |
| `S01`…`S19` | B's source register | [source register][sources] |
| `csv:<id>` | a row of A's paper table | [research-papers.csv][csv] |

**Difficulty.** A's tiers are reused where A grades the problem: **T1** answer known ·
**T2** shape known, needs experiments · **T3** no reliable solution anywhere
([catalogue §1][catalogue]). Where neither source grades a question it says
**ungraded**. Nothing in this file is graded by me.

**Status vocabulary** (the "current state in the merged code" column):

| Word | Meaning |
|---|---|
| absent | nothing in `src/lessonforge` addresses it |
| docs-only | a design or prompt exists in `docs/`, no code path uses it |
| measured-only | a number is logged or written to a sidecar; nothing acts on it |
| built-off | implemented, default off |
| built-on | implemented and on by default; the open question is its limit |
| porting | being ported from B's scripts into `src/lessonforge/longform/` and `src/lessonforge/bridge.py` on 2026-10-07. The only evidence for these capabilities is what B's original scripts did |
| hand-done | done once by a person or coding assistant for B's lesson, not by a reusable mechanism |

**Evidence caveats that apply everywhere.**

- A's numbers are "as documented". A's documents name artifact files (46 render
  sidecars, 27 cached storyboards, one bulk run, 185 debugger traces —
  [decomposition, artifact table][decomp]). Those artifacts are not in the merged
  tree. In the checkouts on this machine I found only the 185 debugger traces
  (`concept_explorer/debug_sandbox/debug_traces/`); no sidecars or cached boards. An
  experiment below that says "classify the 23 residues" needs those files from the
  machine they were written on, or fresh renders.
- B's check files and ledgers are in this tree. B's rendered video, its narration
  audio, and the pilot's frames and videos are referenced by B's documents but are not
  in this tree. The lesson source and Kokoro model files are in the
  education_content_review checkout, so the audio can be rebuilt locally without a
  paid call ([case-study README](../longform/pythagoras_case_study/README.md)).
- B states its own limits and they are carried here: the model pilot is "a one-topic
  diagnostic pilot, not a statistically reliable model ranking" ([pilot RESULTS][pilot]);
  the user reviewed the 20-minute lesson and "reported that the narration is poor and
  lacks coherence", so it "is not an accepted quality benchmark" ([handoff][handoff]).
- Numbers that originate in papers are the papers' own, as relayed by the source file.
- Engine code was read only to confirm what exists. `longform/` and `bridge.py` were
  being written while this file was drafted; I describe them as "porting" and do not
  credit them with anything B's originals did not do.

---

## 2. Master table

Columns: id · question · area · difficulty · source ids merged · current state in the
merged code · next experiment (detail in §3).

| ID | Question | Area | Difficulty | Merges | Current state in merged code | Next experiment |
|---|---|---|---|---|---|---|
| RQ-01 | Is what the narrator says true to its sources and to the subject, and where does legitimate invention end? | Semantic | T2 (R12, cat-6, P08) | R12, cat-6, P08, dec-4.2, dec-6.2, road-#25 · LH-1, B-B (factual-defect measure) | absent for checking: `engine/sources.py` makes chunks citable and the deep-path plan records `must_say[].cite`; nothing compares narration to them. B's answer checks (`verify_math.py`) are hand-written for one lesson | claim-class lint, then "N of M facts traced" on one sourced topic |
| RQ-02 | How is a lesson grounded in the actual curriculum (NCERT, the school's edition)? | Semantic | T1 (R18) | R18 · WS1, S18 | engine accepts source text passed in; no curriculum-aligned set, no curator step | confirm one topic's edition with the school; build a small aligned fact set |
| RQ-03 | What expert-teaching evidence should be collected, in what form, and does it improve scripts? | Semantic | ungraded | B-A, 09-T1, WS1 · (A: none; nearest is dec-4.2) | absent; `engine/sources.py` can ingest a transcript as chunks | B-A1 defect-rate test on a few transcripts |
| RQ-04 | Which authoring process yields a script with one line of reasoning, and how is under-delivery measured? | Semantic | T1 for the plan contract (R14); method comparison ungraded | R14, dec-4.3, dec-4.4 (narration side), dec-4.5, dec-4.6, road-#23 · B-B, T01, T09, 09-T2, WS2, LH-1, LH-2 | single-call board is default (built-on); screen plan + per-screen writers built-off; `narrative_problems()` and `coverage()` measured-only | run A's two measures over B's lesson; then B1 vs B2 vs B4 on fixed briefs |
| RQ-05 | Can a build-time gate catch a lesson that does not teach? | Semantic | T3 (R13, cat-7, P09) | R13 (lint half), cat-7, P09, dec-4.3 · WS2, evaluation rubric | absent (shape, truncation and language gates only) | deterministic lints over existing boards and B's recorded corrections |
| RQ-06 | Can worked and independent practice problems be generated and verified automatically? | Semantic | ungraded | WS5 · (A: none) | absent in engine; B's lesson has hand-checked answers | templates + independent solver for one lesson |
| RQ-07 | How does a scene's stated composition intent reach the layout engine? | Presentational | T1 (R6, cat-9, P05) | R6, cat-9, P05 · B-F1 | measured-only: `composition` is logged by `transpiler.py`, consumed by nothing | build the closed keyword map; A/B with and without it |
| RQ-08 | How is a frame composed (structure, balance, fill), not merely de-collided? | Presentational | T2 (R5, cat-10, P11); T1 for cat-11 | R5, cat-10, cat-11, P11, dec-4.10, dec-4.11 · B-F1, B-F2, B-F5 | zones, templates, tree layout, containment built-on; no rows/columns, no balance pass, no balance number | log a per-scene balance number for every render |
| RQ-09 | Which route produces visuals that are both correct and expressive: IR + compiler, tested components, or direct code? | Presentational | ungraded | dec-4.9, dec-4.15 · B-D, T06, 09-T3, WS3, HD-8, LH-2, LH-6 | IR → `transpiler.py` built-on; bounded LLM `build/animate` in `engine/sim_gen.py`; B's chapters hand-done; `bridge.py` porting | express one Pythagoras chapter as IR; list what the IR cannot say |
| RQ-10 | Does a generated drawing resemble its subject? | Presentational | T2 (R8, cat-14) | R8, cat-14, dec-4.9 · (B: WS4 only) | existence, min-parts and in-box checks built-on; resemblance absent | yes/no questions on cached drawings vs a human label |
| RQ-11 | What makes synthetic narration acceptable: synthesis unit, voice direction, and what gate before spend? | Temporal | T1 for the gate (cat-8); delivery ungraded | cat-8, dec-4.13, road-#4 · B-E (E1, E2), T02, T03, HD-1, HD-3 | engine: one clip per cue, no script gate; long-form speech build porting; voice-direction prompt docs-only | same script at three synthesis granularities, blind listening |
| RQ-12 | How do visual events land on the words that name them, including in code-switched speech? | Temporal | T2 (R10, cat-12, P06) | R10, cat-12, P06, dec-4.14, road-#11 · B-E (E3, E4), T05, 09-T4, HD-4 | engine: fraction-of-beat timing, no word marks; phrase-anchored cues porting (word-position estimate) | force-align B's narration; measure error of its 173 estimated anchors |
| RQ-13 | What pace, pause budget and length suit a grade band, and who decides duration? | Temporal | T2 (R11) | R11, dec-4.1, dec-4.3, road-#26 · HD-2, WS2, B-B1 | `target_duration_s` and `rendered_duration_s` measured-only; one planning rate (150 wpm) in `engine/storyboard.py`; the grade-band table A describes lived on the lesson side (`ce/`), which is not in this package | deterministic section-budget checks; estimate vs measured per beat |
| RQ-14 | How does motion explain (systems that evolve with the narration) rather than point? | Temporal | T2 (R9, cat-13) | R9, cat-13, dec-4.12, road-#24 · WS4, B-D4 | simulations built-on but play once per cue; Motion Director built-on; B's angle sweep hand-done | count how often explanatory motion is requested at all |
| RQ-15 | Should attention (highlight, focus, gesture) be a separate, purposeful, scheduled layer? | Temporal | ungraded | T07, HD-5 · dec-4.11, dec-4.12 | `sustain` gestures and colourless emphasis built-on; `focus` spotlight built-on; no purpose field, no scheduler | A/B a board with and without the beat filler |
| RQ-16 | One lesson in several languages: what is shared and what is re-derived per locale? | Temporal | ungraded | dec-4.7, dec-6.7 · T10, B-E5, T03 | engine language contract built-on (Hinglish narration, English on screen); long-form lesson exists in English only | T03 English/Hindi clips on one worked explanation |
| RQ-17 | How is layout verified across animation time and across object classes? | Realisation & verification | T2 (R7, cat-3) | R7, cat-3 (coverage), dec-4.16, P11 finding 3 · B-F (F3), T08, 09-T5, HD-6 | `layout_probe.py`: three text classes counted after every play; shape-on-shape reported, not counted; images skipped; no mid-transition sample. B's beat-end bounds check porting | run the probe over B's chapters with B's known crossfade overlap re-planted |
| RQ-18 | Can a verifier survive new visual capabilities (camera moves, other renderers)? | Realisation & verification | T2 (cat-4, P10) | cat-4, P10, R7 (tail), road-#17 · B-F3 | camera zoom/pan deliberately absent; no test pins the rule | harness check that fails on `MovingCameraScene` |
| RQ-19 | Can the pipeline check that the picture means what the lesson says (maths and science invariants)? | Realisation & verification | T2 (cat-3) | cat-3 · WS3, WS4, B-D (correctness), LH-3 | absent in engine beyond structure; B's `verify_math` / `verify_render_geometry` checks are per-lesson and hand-written | one invariant check on a transpiler-emitted graph scene |
| RQ-20 | Can a vision model's judgement be calibrated well enough to gate a release? | Realisation & verification | T3 (R2, cat-2, P03) | R2, cat-2, P03, dec-4.16 · B-F4, LH-3 | `engine/pipeline/vision_qa.py` built-off; samples evenly, not at scene midpoints | midpoint sampling; labelled fault set from real renders |
| RQ-21 | When should repair stop, at what scope and level should it act, and what must survive it? | Realisation & verification | T2 (R3, cat-15, cat-16, P04); T1 for cat-5 | R3, cat-5, cat-15, cat-16, P04, dec-4.17 · B-G (G1–G4), 09-T6, HD-8 | accept-if-better per scene with preservation guards, 2 rounds, built-on; edits code, not the plan; no stop rule | classify the residual violations by kind |
| RQ-22 | Can the system remember fixes without poisoning itself? | Realisation & verification | T2 (R4, cat-17, P07) | R4, cat-17, P07 · B-G5 | `engine/rag.py` built-off (`CHROMADB_ENABLED`) | switch on in isolation; measure hit rate; mine the 185 traces |
| RQ-23 | Is there a quality score that tracks human judgement? | Realisation & verification | T2→T3 (R1, cat-1, P01) | R1, cat-1, P01, dec-6.1 · evaluation rubric, dataset review axes | sidecar holds structural counters only; no scorecard | adopt one scorecard schema; rate ~20 existing videos; report κ |
| RQ-24 | How does the pipeline reach lesson length by chapters with consistent terminology? | Long-form & continuity | T1 (R15, cat-22) | R15, cat-22, dec-4.1, road-§6, road-#20 · B-C (C1, C2), B-B4, 09-T7, T09 | engine: no chapter orchestration (bulk runner is per topic); long-form chapter build porting | one full lesson end to end, graded where it breaks |
| RQ-25 | How does visual and conceptual state persist across chunk boundaries? | Long-form & continuity | ungraded (A rates the visual side L0 maturity) | dec-4.4 (visual side), dec-6.3 · B-C (C3–C5), T04, T06, HD-7 | absent: per-scene isolated renders, hard cuts, no object identity across scenes; B's chapters share helpers only | C2 vs C3 on identical scripts |
| RQ-26 | What does an accepted lesson cost, where does the cost concentrate, and how should calls be routed? | Scale, cost, data & distillation | T1 (R17, cat-18, P02) | R17, cat-18, P02 (cost half), dec-6.4, dec-4.18, road-#5 · B-H1, T02, T12, 09-T8 | absent in engine (no ledger); B's ledgers exist as files, not code | one ledger schema on one short video and one chapter |
| RQ-27 | Can a smaller model replace the strong one at the same acceptance bar and lower total cost, and what data makes that trustworthy? | Scale, cost, data & distillation | ungraded | B-H (H2–H5), T13, T14, 09-T8, B-D5 · (A: csv rows only) | absent; no dataset, no training | H1 routing baseline with cost per accepted output |
| RQ-28 | Do teachers accept the lessons and do learners learn from them? | Evaluation with teachers and learners | T3 (R13, cat-7, P09) | R13 (tail), cat-7 (open part), P09 (tail), M7 · T11, WS7, LH-4 | absent; no study has been run by either project | reviewer rubric on existing outputs; 6–12 pupil formative pilot |
| RQ-29 | Can a system read a student's attempt, find the first supported error and give a useful hint? | Evaluation with teachers and learners | ungraded | WS6, LH-5 · (A: none) | absent; outside the video pipeline | 30 teacher-labelled attempts, typed first |
| RQ-30 | How do people edit the plan and re-make only what changed? | Product/editing | T1 (R16, cat-24, cat-25) | R16, cat-24, cat-25, dec-4.19, dec-6.5, road-#22 · B-C5, T12, 09-T6 (patch history) | Studio editor over the IR built-on, projects in browser storage, full re-render on any edit; B's edits hand-done and logged | one-sentence edit: measure what is re-synthesised and re-rendered |

---

## 3. The questions

### Semantic — what is true and worth teaching

#### RQ-01 · Is the spoken content true, and where does invention end?

**Question.** Does the narration keep the facts of its sources, is it correct as
mathematics or science, and how does a checker tell a good invented example from a
fabricated fact?

**Why it is open.** A can cite sources but never audits them. B found subject errors in
model-drafted scripts only by review. Neither has a checker, and A's literature sweep
found no work that separates pedagogical invention from fabrication.

- **Evidence from A.**
  - Sources became citable on 2026-08-15 (`[S2#1]` chunks; the screen plan's
    `must_say[].cite`), but "nothing yet audits that the narration kept the cited
    fact"; the stage stays L2 ([roadmap §A][roadmap]).
  - Of 27 cached boards, the three newest carry a `research` block and 24 have none
    ([decomposition 4.2][decomp]).
  - "No active work found that formally separates pedagogical invention … from
    fabrication" ([agenda §2 R12][agenda]).
  - P08 says the IR has no provenance field ([P08][P08]); that page predates the
    2026-08-15 `must_say[].cite` change and is partly superseded by the roadmap.
- **Evidence from B.**
  - The premium script "needed corrections to the central-angle argument, translated
    coordinates, premature answer disclosure and the distinction between bounds on a
    leg versus a hypotenuse" ([case-study REVIEW][review]). Six critical corrections
    are listed and 33 of the 40 beats were edited ([editorial_changes.json][editorial]).
  - The pilot's full-script draft "initially used an overbroad statement about all
    straight lines and language suggesting a line starts at its intercept"
    ([pilot RESULTS][pilot]).
  - The lesson's stated answers and the area identity pass a symbolic and numeric
    check ([math_checks.json][mathchk]). This checks subject truth, not fidelity to a
    cited source; B's ten educator sources are "references, not a licensed training
    dataset" and are not cited per claim ([teacher comparison][teachers]).

**Prior work.** MiniCheck (`csv:minicheck`), conformal citation guard
(`csv:citation-faithfulness-conformal`), FaithLens (`csv:faithlens`) — [agenda §2][agenda].
PhyEduVideo (S06): visually coherent output can coexist with unreliable conceptual
accuracy. SymPy (S15) for answer checking.

**What would count as an answer.** A: fidelity rate = verified ÷ sampled claims per
board with a ≥95% bar, taken from a sibling project's pilot ([roadmap §A][roadmap]); a false-rejection rate on boards a
subject expert rates sound, and zero invented constants or formulas as a hard floor
([P08][P08]); v1.4 exit "fidelity number reads ~100% on a sourced topic and lower on an
unsourced one" ([agenda §8][agenda]). B: "critical conceptual defects per lesson"
(LH-1, [literature review][lit]) and "no unresolved critical error"
([evaluation protocol][evalp]).

**Cheapest first experiment.** P08's $0 claim-class lint (numbers, named laws and
formulas in narration with no cited chunk) on one sourced topic. B's six recorded
corrections are a ready set of real script errors to test any checker against; the raw
draft they correct (`generated/narrative_v2.txt`) is in the education_content_review
checkout, not in this tree.

#### RQ-02 · How is a lesson grounded in the actual curriculum?

**Question.** How does the pipeline get curriculum-aligned source material for Indian
school topics and verify alignment before spending?

**Why it is open.** A grades it T1: the shape is known (a curator step, an aligned test
set) and unbuilt. B could not verify the curriculum edition at all.

- **Evidence from A.** Grounding tiers were "given link → transcript search → NCERT
  text" on the lesson side, plus the engine's own intake since 2026-08-15
  ([decomposition 4.2][decomp]). What to take: "A curator step before spend
  (Shiksha's shape) and an NCERT-aligned test set for fidelity checks"
  ([agenda §2 R18][agenda]). The lesson-side resolver named in
  A's docs (`ce/storyboard_context.py`) is not in `src/lessonforge`; the engine takes
  source text passed in.
- **Evidence from B.** The NCERT portal entry reads "direct fetch failed. No exact
  chapter or current edition claim relies on it" (S18, [source register][sources]).
  "Do not assume a chapter number from an older edition is current" ([WS1][ws1]).
  Curriculum edition, board, chapter and language are open questions in the
  [meeting minutes][minutes].

**Prior work.** Shiksha Copilot (`csv:shiksha-copilot`), IndiMathQA (`csv:indimathqa`).

**What would count as an answer.** No numeric acceptance metric in either source. B's
acceptance condition for a brief is "a confirmed curriculum reference, correct
prerequisite assumptions, and a reason for every selected teaching move" ([WS1][ws1]).

**Cheapest first experiment.** Confirm one topic's board, class and edition with the
school and pass that chapter text through `engine/sources.py` as the only source.

#### RQ-03 · What expert-teaching evidence should be collected, and does it help?

**Question.** Should the project build a corpus of teaching episodes or teaching moves,
in what form, and does supplying it improve generated scripts?

**Why it is open.** Only B asks it, and B has built no corpus. A has no representation
of a teaching move at all.

- **Evidence from A.** None recorded as a problem. The nearest mechanism is source
  intake, where "relevance ranking inside a source is nobody's decision: a transcript
  is chunked in order" ([decomposition 4.2][decomp]).
- **Evidence from B.**
  - Five approaches (transcript corpus, multimodal episodes, teaching-move library,
    expert corrections, constrained synthetic expansion) are compared on paper
    ([method comparison §A][methods]).
  - For the Pythagoras lesson, ten sources were compared: "three primary-site
    transcripts and seven written explanations; not ten watched videos"
    ([handoff][handoff], [teacher comparison][teachers]).
  - "Public availability alone does not establish permission to train on complete
    teacher transcripts or reproduce their voice" ([handoff][handoff]).

**Prior work.** IES practice guide (S07), MathDial teaching moves (S08), the
3Blue1Brown catalogue as a candidate reference (S17). A's table has Shiksha Copilot's
curator step (`csv:shiksha-copilot`).

**What would count as an answer.** B: reference resolution, equation transcription and
"whether another teacher can reconstruct the instructional move"; two-teacher agreement
measured "before buying thousands of labels" ([method comparison A2, A4][methods]). No
threshold is given.

**Cheapest first experiment.** B-A1's defect-rate test: reviewers reconstruct an
explanation from a transcript alone and compare it with the video.

#### RQ-04 · Which authoring process yields a coherent script, and how is thinness measured?

**Question.** Whole-lesson prompt, few-shot examples, retrieval, a plan with per-screen
contracts, or a hierarchical manuscript: which gives a script that carries one line of
reasoning, and what number says a scene under-delivered?

**Why it is open.** Both projects hit the same failure from opposite ends. A's
single-call boards read as "a syllabus, not a story"; B's lesson was rejected as
lacking coherence. A has measures but does not enforce them. B has a comparison design
but has not run it.

- **Evidence from A.**
  - The plan contract (R14) is graded T1; the countable `must_show` / `must_say` plan
    is "ours to keep and publish" ([agenda §2 R14][agenda]).
  - On the one live deep-path board, screens 1–4 over-delivered and "screens 5 and 6
    deliver 2 objects against 4 required — recorded, not repaired"; the path is off by
    default ([decomposition 4.5][decomp]).
  - `narrative` is present on 4 of 27 cached boards; continuity is measured, never
    enforced ([decomposition 4.4][decomp]).
  - On the first live deep run "the IR was rich; the frame was not, and no number said
    so": 46 elements were written and a frame showed a clipped text placeholder
    ([roadmap §3d][roadmap]). A measure that stops at the IR misreports the video.
- **Evidence from B.**
  - User review, 7 October 2026: "the narration is poor and lacks coherence"
    ([handoff][handoff]).
  - "Repetition was reduced from 3,627 to 2,906 words" by editing
    ([case-study REVIEW][review]).
  - Pilot plans: with a 6,000-token output limit two models returned truncated JSON;
    with 12,000, Sonnet returned 12 sections totalling 1,300 s and Gemini 12 sections
    totalling 1,290 s against a required 1,200 s; Qwen's first plan had 8 sections and
    960 s. The results "do not establish relative teaching effectiveness"
    ([pilot RESULTS][pilot]).
  - One narrative call returned no visible script after spending its output allowance
    on reasoning, at $0.417120 ([costs.md][costs]).

**Prior work.** LASEV's executable script (`csv:lasev`), DeepSlides
(`csv:deepslides`), Code2Video storyboards (`csv:code2video`, S01), DOC outline control
(`csv:doc-detailed-outline-control`), TheoremExplainAgent's planner
(`csv:theoremexplainagent`, S03), TeachMaster's manuscript expansion (S04,
[audit][audit]).

**What would count as an answer.** A: "coverage gap = 0 on the 08-15 board"
([agenda §8 v1.4][agenda]). B: blind teacher ratings on the same briefs, factual defect
counts and measured audio duration ([method comparison §B][methods]); "no missing
prerequisite or accidental repeated introduction" ([08 §7][lf08]); for T01, "each
block has one clear explanatory purpose and a connection to its neighbors"
([handoff][handoff]).

**Cheapest first experiment.** Proposal: once `bridge.py` can express B's lesson as a
board, run A's `narrative_problems()` and `coverage()` over it. It costs nothing and
shows whether A's two measures register what B's user heard. Then B's B1 vs B2 vs B4
comparison on fixed briefs.

#### RQ-05 · Can a build-time gate catch a lesson that does not teach?

**Question.** Which pedagogy defects can be detected mechanically on the script before
any spend, and can any build-time score be trusted as a gate?

**Why it is open.** A grades it T3. Mechanical lints are cheap and unbuilt; a proxy for
"teaches" is unvalidated, and "a bad proxy is worse than none" ([P09][P09]).

- **Evidence from A.**
  - A 23.7 s, one-scene Dalton video "never stated the law" and passed every gate; the
    only pedagogy gate in the code is a four-scene floor ([roadmap §B][roadmap],
    [P09][P09]).
  - "A pedagogically weak learning plan compiles into a pedagogically weak video,
    flawlessly" ([chapter 4 §4.7][ch4]).
- **Evidence from B.**
  - The 20-minute lesson passed every technical check and was rejected on listening
    ([handoff, "What passed and what remains unacceptable"][handoff];
    [final_checks.json][final] lists its own review limits).
  - One editorial correction is a lintable pedagogy defect: "Third practice answer
    withheld until next beat" ([editorial_changes.json][editorial]).
  - "Evaluate scripts first as narrated static storyboards. If learners cannot follow
    that version, animation should not be used to conceal the explanation problem"
    ([WS2][ws2]).

**Prior work.** Hauk & Soujon (`csv:hauk-soujon-lesson-plans`): LLM coding is reliable
on explicit components, unreliable on coherence. SciEval (`csv:scieval`), LearnLM
(`csv:learnlm`), Mayer (`csv:mayer-segmenting`). IES guide (S07); MathDial on premature
answer disclosure (S08).

**What would count as an answer.** A: "lints catch the Dalton board"
([agenda §8 v1.4][agenda]); lint hit-rates on cached boards, then advisor-score vs
human-rating correlation ([P09][P09]). B's proposed internal gate: "no unresolved
critical error and at least 3 in every dimension after correction"
([evaluation protocol][evalp]).

**Cheapest first experiment.** P09's $0 lints (states the definition, term before use,
ending answers the opening). Proposal: add a lint for an answer revealed before its
thinking pause, taken from B's correction list, and test the lints on B's uncorrected
draft.

#### RQ-06 · Can practice problems be generated and verified automatically?

**Question.** Can a lesson's two worked and three independent problems be produced with
verified answers, valid alternatives and a hint ladder?

**Why it is open.** Only B asks it. "The reviewed literature does not establish an
automatic generator guaranteed to produce exactly five valid, grade-appropriate
problems" ([literature review][lit]).

- **Evidence from A.** None. A's own instructions mark its question-gallery work as
  stale and outside the video engine ([CLAUDE.md](../../CLAUDE.md), "Current focus").
- **Evidence from B.** The lesson contains two worked examples and three independent
  questions with eight seconds of thinking time each; the answers are checked
  ([case-study REVIEW][review], [math_checks.json][mathchk]). The method
  (templates, an independent solver, a separate reviewer) is a proposal
  ([WS5][ws5]).

**Prior work.** IES guide on worked examples (S07); SymPy (S15).

**What would count as an answer.** [WS5][ws5]: every item correct, unambiguous under
stated assumptions, objective-aligned and independently reviewed. No numeric metric.

**Cheapest first experiment.** Templates plus an independent solve for one lesson, as
[WS5][ws5] proposes.

### Presentational — frame composition, layout, drawings

#### RQ-07 · How does stated composition intent reach the layout engine?

**Question.** The script model writes a composition sentence for every scene. How does
it steer placement without letting a model emit geometry?

**Why it is open.** A grades it T1: the fix is specified and not built.

- **Evidence from A.**
  - `composition` is on 98 of 148 cached scenes, was logged 25 times in the server log
    and is "consumed by nothing" ([decomposition 4.10][decomp]). In the merged
    `transpiler.py` its only use is `[COMPOSITION]` log lines.
  - A seven-keyword vocabulary mapped to existing templates was specified on
    2026-08-03, about 60 lines, "not yet built" ([P05][P05]).
- **Evidence from B.** B's lesson fixes the layout by hand: diagram left, text panel
  right, in the shared runtime (`lesson_runtime.py` `fit`, `panel_to`). B treats prompt
  rules and fixed regions as a baseline and says to "never treat it as a checker"
  ([method comparison F1][methods]). The audit of Code2Video found its `place_in_area`
  "computes a center and applies a supplied scale. It does not measure an object's
  extent"; an area assignment is "placement guidance, not a fit guarantee"
  ([audit][audit]).

**Prior work.** DeepSlides (`csv:deepslides`), Code2Video anchors (`csv:code2video`),
ReLayout (`csv:relayout`) — [agenda §3 R6][agenda].

**What would count as an answer.** "A/B with and without the composition map differs
measurably" ([agenda §8 v1.2][agenda]); a harness where "derivation right column" puts
elements in the right column, and fewer first-render violations ([P05][P05]).

**Cheapest first experiment.** Build P05's keyword map; one lever, $0.

#### RQ-08 · How is a frame composed, not merely de-collided?

**Question.** What scene structure (rows, columns, pairs, containment) and what
placement method (zones, measured-geometry constraints, a solver, candidate search)
give balanced, full frames?

**Why it is open.** A grades the structure and solver question T2 and the balance
number T1. A has collision avoidance without composition. B proposes measured-geometry
constraints and has built none.

- **Evidence from A.**
  - On the audited board "content occupies roughly the upper two-thirds; scenes 5 and
    6 leave the bottom half empty" ([decomposition 4.10][decomp], quoting roadmap §3e).
  - Structure fields are barely used upstream: `connects` on 23 of 876 cached elements
    and `relation: "inside"` on 0 of 876; two templates added on 2026-08-15 appear on 0
    of 148 scenes ([decomposition 4.6][decomp]).
  - Where code owns the decision it works: an axes fixture went from 11 violations to
    0 and an A/B from 4 to 0 ([decomposition 4.10][decomp]).
  - Six ordered fix strategies, from keyword map to a constraint solver
    ([P11][P11]).
- **Evidence from B.**
  - Pilot: one candidate (Sonnet's original) had "late text overlap" and a crossed
    caption boundary; after repair the axes' bottom was −2.62854 against a −2.6 boundary.
    "Measuring rendered object extents is stronger than reasoning only from nominal
    axis lengths" ([pilot RESULTS][pilot]).
  - Premium drafts had "content outside the frame, overlapping equation layers"
    ([case-study REVIEW][review]).

**Prior work.** Penrose (`csv:penrose`), Feynman (`csv:feynman`), Bluefish
(`csv:bluefish`), sPyTial/CnD (`csv:spytial-cnd`), Visual Moment Equilibrium
(`csv:visual-moment-equilibrium`), ReLayout / LaySPA (`csv:relayout`, `csv:layspa`),
ELK (`csv:elk-layout`), ALGOGEN (`csv:algogen`), AeSlides (`csv:aeslides`).

**What would count as an answer.** "Vertical-centroid and white-space numbers move on
the 08-15 projectile board; 0 new violations on the planted set", with regression on
ManimLayout-1K / EduRequire-500 ([agenda §8 v1.2][agenda]). B gives no number; it asks
for validation "at target resolution" ([method comparison F2][methods]).

**Cheapest first experiment.** cat-11: log a per-scene balance number for every
render before changing any layout ([catalogue 11][catalogue]).

#### RQ-09 · Which route produces visuals that are both correct and expressive?

**Question.** A typed scene description compiled by code, retrieval of tested
components, or model-written Manim: which meets a correctness bar while still
expressing what a proof or a changing system needs?

**Why it is open.** A treats the route as settled (IR + transpiler) and lists its
ceilings. B's design documents recommend the same route (B-D3), but B's one long
lesson was produced by direct generation followed by manual reconstruction. Nobody has
tried to express that lesson in A's IR.

- **Evidence from A.**
  - "Every geometry decision that was migrated from the model to a solver eliminated
    its failure class outright" ([chapter 4 §4.2][ch4]).
  - Before head-noun parsing, 16 of 17 shapes drew wrong on one board; of 70 failed
    debugger traces (older code), 52 failed at compile ([decomposition 4.9, 4.15][decomp]).
  - The one place a model writes Manim is a bounded `build`/`animate` pair per
    element; resolution went from 1 of 4 to 3 of 4 on the same descriptions
    ([decomposition 4.9][decomp]).
  - Stated limits: the solver's constraint vocabulary "bounds what the Visual Director
    can express", and the component library "has a cold-start cost"
    ([chapter 4 §4.7][ch4]).
- **Evidence from B.**
  - "No code candidate passed the full requested contract" across three models on one
    topic; one failed on an API call incompatible with the pinned Manim 0.19.0
    ([pilot RESULTS][pilot]). Not a ranking.
  - Premium drafts "contained invalid central-square coordinates, non-square polygons
    described as squares, content outside the frame, overlapping equation layers,
    nonexistent spoken cues and a truncated final class"; the final code is a
    "substantial manual reconstruction" ([case-study REVIEW][review],
    [editorial_changes.json][editorial]).

**Prior work.** Read by both sides: Code2Video (`csv:code2video`, S01, S02),
TheoremExplainAgent (`csv:theoremexplainagent`, S03), Manimator (`csv:manimator`,
[audit][audit]), LASEV (`csv:lasev`, [audit][audit]). A only: OmniManim
(`csv:omnimanim`), ManiBench (`csv:manibench`). B only: TeachMaster's representation
routing (S04).

**What would count as an answer.** B: "equation, line, marker and slope triangle agree
at tested parameter values, including negatives and zero" (09-T3, [lf09][lf09]);
first-pass render success and semantic correctness reported separately
([method comparison D1][methods]); adopt the staged pipeline "only if it improves
accepted output quality or reduces total production effort relative to the simpler
baseline" ([Code2Video assessment][c2v]). A states no metric for the route.

**Cheapest first experiment.** Proposal: express one Pythagoras chapter (the
four-triangle proof board) as a lesson contract, render it through the transpiler, and
write down each beat the IR cannot say. The in-progress `bridge.py` describes its
long-form → engine direction as "a floor, not a director: one text panel and one
equation per beat", so the gap list is the result.

#### RQ-10 · Does a generated drawing resemble its subject?

**Question.** A drawing is verified to exist, to have parts and to stay in its box.
How is it verified to look like the thing?

**Why it is open.** A grades it T2 and rates resemblance L0. It inherits the vision
calibration problem (RQ-20) with a narrower question.

- **Evidence from A.** "Nothing checks resemblance: a drawing is verified to exist,
  have parts, and stay in its box — not to look like a grandfather clock"; caches hold
  9 drawings, 4 simulations, 3 generated SVGs and 29 photos
  ([decomposition 4.9][decomp]).
- **Evidence from B.** No resemblance evidence. The nearest statements are design
  rules: do not treat a generated image as "authoritative evidence for fine anatomy or
  physical law" ([method comparison D4][methods]); for biology, "boundaries and labels
  match the selected cell type" ([WS4][ws4]).

**Prior work.** OmniDiagram VIVA (`csv:omnidiagram`), VFIG (`csv:vfig`), DiagramEval
(`csv:diagrameval`), VectorGym (`csv:vectorgym`), SimuScene's question protocol
(`csv:simuscene`).

**What would count as an answer.** "Resemblance pass rate reported"
([agenda §8 v2.2][agenda]); 2–3 yes/no questions per drawing, accepted on majority
([agenda §3 R8][agenda]).

**Cheapest first experiment.** Generate the questions for the cached drawings, answer
them with the vision stage, and compare with a human label.

### Temporal — speech, alignment, pacing, motion

#### RQ-11 · What makes synthetic narration acceptable?

**Question.** What unit should be synthesised (sentence, cue, teaching block), what
voice direction and pronunciation data are needed, and what review must a script pass
before the audio is paid for?

**Why it is open.** A's open item is a missing gate (T1) and A has no listening
evidence. B has one strong negative listening result and a suspected cause that it
explicitly has not isolated.

- **Evidence from A.**
  - "Voice synthesis is the dominant per-video cost, and the script goes into it
    unreviewed" ([catalogue 8][catalogue]).
  - One clip per cue is the default; per-element clips were "rejected on cost"
    ([decomposition 5.6][decomp]). Cues average 19.5 words, range 5–39
    ([decomposition 4.6][decomp]).
  - 8 of 32 voiced sidecars show at least one degraded cue; the shared cache directory
    held 0 files, unexplained ([decomposition 4.13][decomp]).
  - A voice-direction prompt for Gemini TTS exists as a document
    ([audio_agent.md][audioagent]); I found no reference to it in `src/lessonforge`.
- **Evidence from B.**
  - "Each of 274 sentences was synthesized independently; the model received no
    preceding sentence context" (HD-1). "No explicit evaluated voice direction,
    pronunciation guide, or continuous listening gate" (HD-3). Both from the
    [handoff][handoff].
  - "Sentence fragmentation and retiming are plausible contributors, not isolated
    experimentally proven causes" ([handoff][handoff]).
  - The voice was Kokoro-82M `af_heart` at synthesis speed 0.85, local, no per-request
    charge ([handoff][handoff], [audio_report.json][audiorep]).
  - "No Google audio has been generated"; the block-size comparison (45–90 s vs
    90–180 s) is a proposal ([handoff][handoff]).

**Prior work.** LASEV's narration critic (`csv:lasev`), Sarvam Bulbul v3
(`csv:sarvam-bulbul-v3`), Azure and ElevenLabs TTS (`csv:azure-tts-wordboundary`,
`csv:elevenlabs-with-timestamps`). Manim Voiceover (S14).

**What would count as an answer.** B: "fluent listeners rate coherence, pronunciation
and pacing; zero critical math-speech errors" (T03) and "continuous listening/viewing
review, no repeated sentence joins" (T09), both in the [handoff][handoff]. A: a script
critic that makes "text-only edits, beat count fixed" with "TTS calls per video
unchanged" ([agenda §8 v1.3][agenda]). Neither gives a listening score threshold.

**Cheapest first experiment.** Proposal: keep the script and the Kokoro voice fixed and
re-synthesise one connected chapter at three granularities (sentence, cue-sized, whole
beat), then rate blind. It is local and unpaid, and it isolates the synthesis unit
from the voice. B's own first step is the same comparison with Google speech on a 2–3
minute excerpt ([NEXT_SESSION][next]).

#### RQ-12 · How do visual events land on the words that name them?

**Question.** Where do word or phrase times come from, how are events bound to them,
and does this hold for code-switched Hindi-English?

**Why it is open.** A grades it T2. A has no binding between a word and an event. B has
phrase anchors, but their times are estimates.

- **Evidence from A.**
  - Timing is "a per-type fraction-of-beat with a floor"; "no word is ever aligned to
    an event"; dead air is not measured anywhere ([decomposition 4.14][decomp]).
  - A voiceover block "plays 2–3 s of animation inside an 8–12 s beat"
    ([decomposition 4.12][decomp]).
  - The bookmark mechanism is in the dependency and unused ([roadmap #11][roadmap]).
    In the merged tree `viz_helpers.py` imports `remove_bookmarks`; I found no bookmark
    emission and no `time_until_bookmark` call.
  - A code-mixed MFA model reports 4.15 ms mean boundary error (the paper's number,
    [agenda §4 R10][agenda]); the table row notes the abstract does not say whether
    the text was romanised and that no model release is stated
    (`csv:mfa-hindi-english-codemixed`).
- **Evidence from B.**
  - 173 animation anchors; "sentence-based synchronization; within-sentence positions
    estimated" ([final_checks.json][final]). The runtime places a cue at sentence
    start + sentence duration × word-position fraction and raises if the phrase is not
    in the beat (`lesson_runtime.py` `cue`).
  - Premium drafts contained "nonexistent spoken cues" ([case-study REVIEW][review]).
  - Per-chapter video length matches the measured audio timeline to within 0.00067 s
    ([chapter_duration_checks.json][durchk]). That is beat-level agreement, not word
    accuracy.
  - "Equation pronunciation and Hindi-English switching can make automatic alignment
    unreliable. Validate a sampled set of anchors" ([method comparison E3][methods]).

**Prior work.** `csv:mfa-hindi-english-codemixed`, `csv:mms-forced-aligner`,
`csv:azure-tts-wordboundary`, `csv:elevenlabs-with-timestamps`,
`csv:manim-voiceover-bookmarks`, `csv:whisperx`, `csv:speech-synced-whiteboard`,
`csv:omni-judge` (automatic sync judging correlates τ 0.14 with humans). On B's side:
Manim Voiceover (S14) and LLM2Manim's narration alignment (S05).

**What would count as an answer.** A: "median bookmark hit ≤ 300 ms on 10 videos;
`dead_air_s` falls vs v1.2; TTS calls per video unchanged" ([agenda §8 v1.3][agenda]).
B: "all critical equation/highlight anchors resolved or manually reviewed; assess a
proposed 200 ms timing tolerance" (T05, [handoff][handoff]). The two tolerances differ
and both are proposals.

**Cheapest first experiment.** Proposal: rebuild B's narration locally, run a forced
aligner over it (English, the easy case) and report the error of the 173
word-position estimates. A's own first move is bookmarks plus a `dead_air_s` counter
([P06][P06]).

#### RQ-13 · What pace, pause budget and length suit a grade band?

**Question.** What words-per-minute, pause time and total length are right for a grade,
and which single place decides duration?

**Why it is open.** A grades it T2: the grade-band pace table "stays an assumption to
test in the learner study" ([agenda §4 R11][agenda]). B forced a duration and regrets
it.

- **Evidence from A.**
  - Over 46 sidecar'd videos, duration is "min 2.9 s, median 94.2 s, max 236.9 s"
    against a prompt target of 60–90 s ([decomposition 4.1][decomp]).
  - A substring bug narrated Grades 10–12 at 90 wpm until 2026-07-20
    ([decomposition 4.3][decomp]).
  - The duration contract is "measured, not enforced" and warns past ±20%
    ([roadmap #26][roadmap]). The merged engine plans at a single 150 wpm
    (`WPM_SPOKEN` in `engine/storyboard.py`); the grade-band table is lesson-side code
    (`ce/planner_agent.py`) that is not in `src/lessonforge`.
- **Evidence from B.**
  - Raw speech was 1,081.24 s; it was retimed with `atempo` 0.9552 and padded to a
    final 1,200.0 s ([audio_report.json][audiorep]). "Let approved speech determine
    timing; revise prose for duration" (HD-2, [handoff][handoff]).
  - Plan durations missed the requested 1,200 s in all three pilot plans; marked
    thinking pauses totalled 150 s against about 90 requested; one candidate and its
    repair both scheduled 58 s under comments suggesting 60 ([pilot RESULTS][pilot]).
  - The meeting asked for 5–10 minute videos and none above 15
    ([meeting minutes][minutes]); B's later scope document overrides this
    ([08][lf08]).

**Prior work.** Mayer's segmenting and temporal contiguity (`csv:mayer-segmenting`,
whose notes also carry the Guo, Kim & Rubin ~6-minute engagement reference), a 2026
temporal-contiguity study (`csv:temporal-contiguity-vr-2026`), LASEV's
duration-by-density rule (`csv:lasev`).

**What would count as an answer.** No validated acceptance metric in either source.
The only numbers are A's ±20% drift warning and B's instruction to "time the finished
video, not only the script estimate" ([WS3][ws3]).

**Cheapest first experiment.** B's deterministic arithmetic on section budgets
([pilot RESULTS, implications][pilot]); then compare A's word-count estimate with B's
measured per-beat durations in `timeline.json`.

#### RQ-14 · How does motion explain rather than point?

**Question.** How do things on screen move in ways that demonstrate (a vector
sweeping, a system changing as the narration describes it), and how is that verified?

**Why it is open.** A grades it T2. Explanatory motion depends on an intent the script
model almost never writes, and a simulation plays once and is seen by the probe only
in its final frame.

- **Evidence from A.**
  - Across 27 cached boards, `show` + `hide` are 93.5% of 1,220 events and the two
    expressive verbs are 0.49% ([decomposition 4.6][decomp]).
  - "A simulation plays once, in its cue, and the probe sees only its final frame"
    ([decomposition 4.12][decomp]).
  - SimuScene's best model reaches 21.5% Avg@8: "the task is hard"
    ([agenda §4 R9][agenda]).
- **Evidence from B.**
  - The lesson's angle sweep had to be repaired by hand: "Preserved leg lengths during
    angle sweep"; "Angle label updates from actual rotating geometry each frame"
    ([editorial_changes.json][editorial]).
  - In the pilot, one candidate's "trackers never actually change to requested b=2 or
    m=−1": parameter-driven motion failed without an error ([pilot RESULTS][pilot]).
  - "More movement alone is not an improvement" ([handoff][handoff]).

**Prior work.** SimuScene (`csv:simuscene`), LASEV (`csv:lasev`); PhET (S16),
PhyEduVideo (S06).

**What would count as an answer.** "A wave changes frequency as the narration does,
and the probe stays clean" ([agenda §8 v2.2][agenda]).

**Cheapest first experiment.** "Measure how often expressive motion is requested at
all before trying to render it better" ([catalogue 13][catalogue]).

#### RQ-15 · Should attention be a separate, purposeful, scheduled layer?

**Question.** Should highlights, focus and gestures be events with a target, a
purpose and a spoken anchor, scheduled independently of scene code?

**Why it is open.** Only B names it as a task, and has not built it. A has mechanisms
that fill time and add emphasis but no notion of purpose.

- **Evidence from A.**
  - `sustain` spends the leftover beat on round-trip gestures at whatever the cue
    introduced ([roadmap §D][roadmap]). Emphasis "is now colourless (a scale pulse)"
    ([decomposition 4.11][decomp]); the user request behind it, "remove the object
    highlight", is recorded in [CLAUDE.md](../../CLAUDE.md).
  - First live Visual Director run: "40 rescaled, 0 hides, 14 highlights (3 rejected)"
    ([decomposition 4.11][decomp]).
- **Evidence from B.**
  - "Highlights are embedded in individual scene code" (HD-5, [handoff][handoff]).
  - A proposed event shape with `target_id`, `purpose`, `spoken_anchor`, `effect`,
    `onset`, `offset`, `priority`; "Do not add pulses to every noun"
    ([handoff, "Highlight and attention layer"][handoff]).

**Prior work.** Mayer's signaling principle (`csv:mayer-segmenting`). GeoDial (S12):
correct feedback text and correct visual highlighting are separate capabilities.

**What would count as an answer.** T07: "each highlight has a teaching purpose, a
valid target and a checked interval" ([handoff][handoff]). No numeric metric in either
source.

**Cheapest first experiment.** Proposal: render one board with and without the beat
filler and have reviewers score "pacing and readability" on B's rubric.

#### RQ-16 · One lesson in several languages: what is shared, what is re-derived?

**Question.** Which artifacts are shared across languages (concepts, scene meanings)
and which must be rebuilt per locale (text, audio, alignment, captions, timing,
layout)?

**Why it is open.** A solved the language contract for one locale mix and not
alignment. B has produced English only.

- **Evidence from A.** One rule source for narration language, on-screen language and
  spoken technical terms, graded L3 ([decomposition 4.7][decomp]). Before the gate, a
  run "shipped 8/8 cues in English with 7 on-screen labels in Devanagari and a `hi-IN`
  voice reading English" ([decomposition §3, coupling 6][decomp]).
- **Evidence from B.** "No … multilingual final video … is claimed complete". "Do not
  stretch Hindi speech onto the English timeline". "Measure text after shaping and
  font selection, including Hindi" ([handoff][handoff]).

**Prior work.** Sarvam Bulbul v3 (`csv:sarvam-bulbul-v3`), HiACC (`csv:hiacc`),
IndicConformer (`csv:indicconformer`), Indic Parler-TTS (`csv:indic-parler-tts`),
Shiksha Copilot's English + Kannada deployment (`csv:shiksha-copilot`).

**What would count as an answer.** T10: "native-language review, same mathematics and
learning objectives" ([handoff][handoff]). No metric.

**Cheapest first experiment.** T03: English and independently adapted Hindi clips of
one worked explanation and one transition, rated by fluent listeners.

### Realisation & verification — render, repair, quality judgement

#### RQ-17 · How is layout verified across time and across object classes?

**Question.** Which defect classes should be measured (text, shapes, images,
captions), when (beat ends, after every play, mid-transition), and how are legitimate
overlaps exempted?

**Why it is open.** A grades it T2. Each project measures something the other does
not, and each has shipped a defect its own check missed.

- **Evidence from A.**
  - Three counted classes; shape-on-shape "present in 10 of 19 sidecars that record
    it" and not counted; images and mid-animation unmeasured
    ([decomposition 4.16][decomp]).
  - "Three audits in a row found defects in classes it doesn't" measure
    ([decomposition 4.16][decomp]).
  - "Zero violations" means "no text collided at a beat boundary", not "the frame is
    good" ([P11, finding 3][P11]).
- **Evidence from B.**
  - 40 beat-end bounds checks, 0 violations ([final_checks.json][final]). The check
    compares each top-level object's box with the stage and caption region; it does
    not test object against object (`lesson_runtime.py` `finish`).
  - "An overlap occurring during simultaneous equation crossfades" was found by
    looking at sampled frames, not by the check ([case-study REVIEW][review]).
  - "Bounds are checked at beat ends; sampled frames miss intermediate collisions"
    (HD-6, [handoff][handoff]).

**Prior work.** SGA's resting-vs-transient rule (`csv:sga-symbolic-geometric-agent`),
ALGOGEN (`csv:algogen`), OmniManim's pixel-level overlap (`csv:omnimanim`), manim4ai
(`csv:manim4ai`), weak-verifier aggregation (`csv:weak-verifiers-layout`).

**What would count as an answer.** B: a "precision/recall report on labeled moving and
static defect fixtures, including valid intersections" (09-T5, [lf09][lf09]). A: "0 new
violations on the planted set" ([agenda §8 v1.2][agenda]) and a shape-overlap
threshold set from sidecar data ([P11][P11]).

**Cheapest first experiment.** Proposal: run the shared per-play probe over B's ten
chapters with the crossfade overlap B fixed put back as a planted fault. One run says
whether A's probe catches the defect B found by eye and how many false alarms it
raises on hand-written scenes. `layout_probe.py`'s docstring says the long-form runtime
is meant to install it; that wiring is in progress and unmeasured.

#### RQ-18 · Can a verifier survive new visual capabilities?

**Question.** How does verification stay valid when a capability changes the mapping
from geometry to screen (camera moves, 3D, another renderer)?

**Why it is open.** A grades it T2 and has chosen to withhold the capability. Whether
to verify projected geometry or pixels is undecided.

- **Evidence from A.** Camera zoom and pan are "deliberately absent — not unbuilt,
  forbidden"; the rule is "enforced socially today … with no test pinning it"
  ([P10][P10]). The merged code has no `MovingCameraScene` use. "No work found"
  verifying continuous swept-path collisions ([agenda §3 R7][agenda]).
- **Evidence from B.** None measured. B's designs require camera transforms inside the
  overlap check and camera state in chunk contracts ([method comparison F3][methods],
  [08 §3][lf08]).

**Prior work.** P10's prior-art notes are flagged by A itself as "from general
knowledge … for citation-check" ([site][site]); A's table has
`csv:prism-spatiotemporal` and SGA.

**What would count as an answer.** "Under zoom, a planted off-view clipped text must
be caught and a legitimately off-frame element must not be flagged" ([P10][P10]).

**Cheapest first experiment.** A harness check that fails if generated code contains
`MovingCameraScene` while the probe is frame-fixed ([P10][P10]).

#### RQ-19 · Can the pipeline check that the picture means what the lesson says?

**Question.** Given declared mathematical or scientific invariants, can they be
checked against what was actually rendered, independent of the code that drew it?

**Why it is open.** A grades it T2 and says meaning-level verification "merges into"
quality scoring ([catalogue 3][catalogue]). B has working per-lesson checks, written
by hand for one lesson.

- **Evidence from A.** "The checker knows where things are. It doesn't know what they
  mean" ([catalogue 3][catalogue]). Data-space coordinates removed off-grid points by
  construction ([chapter 4 §4.2][ch4]).
- **Evidence from B.**
  - Pilot defects of exactly this kind: "stale b=1 text while graph shows b=2", and "a
    rising line appears with a slope −1 label" ([pilot RESULTS][pilot]).
  - Two check layers for the lesson: a symbolic and numeric check whose stated limit
    is "not whether every rendered polygon uses these coordinates"
    ([math_checks.json][mathchk]), and a check on "the vertices used by the actual
    renderer" ([render_geometry_checks.json][geomchk], [case-study REVIEW][review]).
  - "Generate dependent labels from the same parameter source. Validate the line by
    evaluating several data points, not by reading its label" ([lf09][lf09]).

**Prior work.** PhyEduVideo (S06), SymPy (S15); DiagramEval (`csv:diagrameval`),
OmniDiagram VIVA (`csv:omnidiagram`).

**What would count as an answer.** B: "all declared lesson invariants pass"
([Code2Video assessment][c2v]) and "zero unresolved critical mathematical errors"
([WS3][ws3]). A gives no metric.

**Cheapest first experiment.** B's proposed regression scene: for y = 2x + 3, compute
points from the expression, check the intercept and the unit slope against the
rendered objects ([WS3][ws3]), on a transpiler-emitted scene.

#### RQ-20 · Can a vision model's judgement gate a release?

**Question.** Can a vision critic be calibrated so its false-alarm rate on healthy
frames is low enough to act on?

**Why it is open.** A grades it T3. The stage is built and off. B used a person plus
sampled frames and warns against treating a vision model as an oracle.

- **Evidence from A.**
  - On a live run "all 6 sampled frames were flagged 'dead frame'". A's documents
    disagree about what that shows: the roadmap's §G says a manual frame pull
    "CONFIRMED it" on the refraction run, and its §D attributes the sampler artefact
    to three findings on a later optical-fibre run; the catalogue, the timeline and
    P03 describe the 6-of-6 result itself as the sampler artefact
    ([roadmap §G, §D][roadmap]; [catalogue 2][catalogue]; [timeline M4][timeline];
    [P03][P03]).
  - One vision round "spent 4 LLM rewrites + 4 scene re-renders + 1 re-critique and
    bought nothing on this board" ([roadmap §G][roadmap]).
  - The best judge in VIABLE reaches 52.6% single-fault accuracy (the paper's number,
    [agenda §5 R2][agenda]).
- **Evidence from B.**
  - Detection in the pilot "was partly manual, so it is not a benchmark of an
    autonomous visual critic" ([pilot RESULTS][pilot]).
  - "A vision model is not a reliable collision oracle and may overlook small errors
    or suggest damaging changes" ([method comparison F4][methods]).

**Prior work.** VIABLE (`csv:viable`), PRISM (`csv:prism-design-principles`), MLLM as a
UI judge (`csv:mllm-ui-judge`), AeSlides (`csv:aeslides`), weak verifiers
(`csv:weak-verifiers-layout`), TheoremExplainBench's human correlations
(`csv:theoremexplainagent`).

**What would count as an answer.** "Vision FPR < 10% on planted set"
([agenda §8 v2.0][agenda]); precision and recall on a golden-frame set, zero findings
on known-clean videos, and repair yield ([P03][P03]). B: "confirmed missed visual
errors" (LH-3, [literature review][lit]).

**Cheapest first experiment.** Sample at scene midpoints ([P03][P03]). Then label a
fault set. B's pilot candidates are real faulty programs with written defect lists;
their sources are in this tree
([openrouter_pilot/](experiments/openrouter_pilot/)), their frames are not.

#### RQ-21 · When should repair stop, where should it act, and what must survive?

**Question.** How many rounds, at what scope (line, scene, section), at which level
(code, specification, plan), and which properties must a repair be proven to keep?

**Why it is open.** A grades stopping and repair level T2. A's loop is safe and half
its videos still ship with a residue. B's only automated repair was partial; its long
lesson was repaired by hand.

- **Evidence from A.**
  - Over 46 sidecars: violations remaining 0 in 23 files and ≥1 in 23, tail up to 14;
    repair rounds 0/1/2/3/4 in 10/14/12/8/2 files ([decomposition 4.17][decomp]).
  - In older debugger traces the fix loop spent 3.6× the input tokens of the stage it
    fixes ([decomposition 4.17][decomp]).
  - Repairs traded away what the probe cannot see (photos, simulations, drawings)
    until four preservation guards were added ([decomposition 4.17][decomp],
    [catalogue 5][catalogue]).
  - "A defect is repaired at the highest representation that can causally resolve it"
    is the stated rule; the repair agent editing Python is the one place it is
    inverted ([chapter 4 §4.6][ch4], [catalogue 16][catalogue]).
- **Evidence from B.**
  - One diagnostic-guided repair cost $0.094278; it "improves right-panel spacing and
    synchronized b-state; fixes equal units; still fails 60 seconds, caption
    clearance, and some graph-label separation" ([pilot RESULTS][pilot]).
  - In Code2Video's inspected helper, unstructured feedback "returned unchanged code";
    "a helper-level finding, not a measured failure rate" ([audit][audit]).
  - The lesson's eleven code repairs were editorial ([editorial_changes.json][editorial]).

**Prior work.** VRR-Stop (`csv:vrr-stop`), Debugging Decay Index
(`csv:debugging-decay-index`), How Many Tries (`csv:how-many-tries`), blind resampling
(`csv:blind-resampling`), OmniManim (`csv:omnimanim`), Code2Video's scope escalation
(`csv:code2video`, S01), Paper2Video's enumerate-and-pick (`csv:paper2video`).

**What would count as an answer.** A: "the 7/17 residual rate → 0/N on a bulk suite, at
equal or lower repair spend" ([P04][P04]); "share of videos shipping with residual
violations falls from 50%" ([agenda §8 v2.0][agenda]). B: "real change detected,
target defect removed, regression checks passed, failed patches retained" (09-T6,
[lf09][lf09]).

**Cheapest first experiment.** Classify the residual violations by kind: "it costs
nothing but reading" ([catalogue 15][catalogue]). It needs the sidecars and job logs,
which are not in this tree.

#### RQ-22 · Can the system remember fixes without poisoning itself?

**Question.** When are two failures the same, does retrieval cut repair rounds, and
which fixes are safe to store?

**Why it is open.** A grades it T2. The store is built and off; the cheap A/B has
never been run.

- **Evidence from A.** "Retrieval returns [] and storage no-ops in every default
  render"; 185 debugger traces are "mined by nothing" ([P07][P07]). In the merged tree
  `engine/rag.py` returns early unless `CHROMADB_ENABLED=1`.
- **Evidence from B.** A failure-experience library is a proposal (B-G5,
  [method comparison][methods]). For the earlier prototype "the original failed source
  snapshots were not preserved … do not reconstruct them" ([06 scaling][lf06]). The
  pilot does preserve one full trajectory: prompt, candidate, defect, repair,
  post-repair result ([pilot RESULTS][pilot]).

**Prior work.** ExpeRepair (`csv:experepair`), ManimAgent memory
(`csv:manimagent-memory`), Faulty Memories (`csv:faulty-memories`).

**What would count as an answer.** Rounds-to-converge and repair spend with memory on
and off across a bulk suite; retrieval precision; poison events counted
([P07][P07]). B: "evaluate on new defect families and report fallback rate"
([method comparison G5][methods]).

**Cheapest first experiment.** Switch the store on in isolation and measure hit rate;
cluster the 185 traces to see whether failures recur at all ([P07][P07]).

#### RQ-23 · Is there a quality score that tracks human judgement?

**Question.** What goes on a per-video scorecard, which fields can a machine fill, and
does the score move when a person says quality moved?

**Why it is open.** A grades it T2→T3 and ranks it first. A has objective counters and
no rubric; B has a human rubric and no counters.

- **Evidence from A.**
  - "The system can prove a video is geometrically clean and cannot say whether it is
    any good"; every quality regression on record was found by a person watching
    ([decomposition 6.1][decomp]).
  - TheoremExplainBench's human correlations: visual relevance ρ 0.72, element layout
    0.42, accuracy and depth 0.14, logical flow 0.16 (the paper's numbers,
    [agenda §5 R1][agenda]).
- **Evidence from B.**
  - A six-dimension 0–4 reviewer rubric with severity classes; it has not been applied
    to anything ([evaluation protocol][evalp]).
  - Seven independent review axes for dataset records ([dataset specification][dataset]).
  - "Technical checks pass, but the user's narration feedback means this is not an
    accepted reference lesson" ([NEXT_SESSION][next]).

**Prior work.** TheoremExplainBench (`csv:theoremexplainagent`), EduIllustrate
(`csv:eduillustrate`), LASEV's 0–3 release rubric (`csv:lasev`), TeachQuiz
(`csv:code2video`), Teach2Eval (`csv:teach2eval`), Reliability without Validity
(`csv:reliability-without-validity`).

**What would count as an answer.** "Scorecard κ ≥ 0.5 on objective dims"
([agenda §8 v2.0][agenda]); agreement with blinded human ranking, stability across
reruns, and a drop when a known-bad change is injected ([P01][P01]). B: "do not turn
this into a weighted average that hides a false concept" ([evaluation protocol][evalp]).

**Cheapest first experiment.** Write one scorecard: A's objective fields plus B's six
rubric dimensions left blank until a person fills them. Rate about 20 existing videos
and report κ ([agenda §5 R1][agenda]).

### Long-form & continuity

#### RQ-24 · How does the pipeline reach lesson length?

**Question.** How is a 10–20 minute lesson planned, generated, rendered and assembled
so that a fault in one chapter re-makes one chapter and terminology stays consistent?

**Why it is open.** A grades it T1 ("fully understood, still the biggest item") and has
only a design. B has one complete lesson, built by hand, not accepted.

- **Evidence from A.**
  - The engine is "a ~90–140s machine by construction" with a ceiling near 4 minutes;
    the design is "chapterize, don't stretch" with a constraint ledger
    ([roadmap §6][roadmap]).
  - Estimated cost of a 12-minute video is about 8× today's per-video cost, "linear,
    not super-linear" ([roadmap §6][roadmap]). This is an estimate; no long run exists.
- **Evidence from B.**
  - One lesson: ten chapters, forty beats, 2,906 spoken words; encoded file 1,200.003 s,
    36,000 frames at 30 fps, 1920×1080, 274 caption segments ([handoff][handoff],
    [final_checks.json][final]).
  - "Even if each of 40 chunks independently has a 98% chance of passing, the
    illustrative all-pass probability is 0.98^40, about 45%" — an illustration, "not a
    forecast" ([method comparison §C][methods]).
  - A long first-half code request returned four complete chapters and part of a
    fifth ([costs.md][costs]).

**Prior work.** DOC (`csv:doc-detailed-outline-control`), dynamic hierarchical
outlining (`csv:dynamic-hierarchical-outlining`), EntityBench (`csv:entitybench`),
LLM2Manim's symbol ledger (`csv:llm2manim`, S05), PresentAgent (`csv:presentagent`),
TeachMaster (S04), TheoremExplainAgent's five-minute-plus videos (S03).

**What would count as an answer.** A: "a 12–15 min lesson end to end; a chapter-5 fix
re-makes chapter 5; terminology consistency measured across chapters"
([agenda §8 v3.0][agenda]). B: "one complete lesson with consistent notation, no
accidental reset, synchronized streams and reviewed content" (09-T7, [lf09][lf09]).

**Cheapest first experiment.** "Do one full lesson end to end and grade where it
actually breaks, rather than predicting" ([catalogue 22][catalogue]). B's lesson is
that run for the hand-built path; the engine path has none.

#### RQ-25 · How does state persist across chunk boundaries?

**Question.** What must be carried across a scene or chapter boundary (object
identity, geometry, labels, camera, established facts), and how is agreement between
neighbouring chunks checked?

**Why it is open.** A's IR "has no notion of 'the same object' across scenes"
([decomposition 6.3][decomp]). B specifies entry and exit state contracts and has not
implemented them.

- **Evidence from A.**
  - "The narrative anchor introduced in scene 1 is re-drawn from nothing in every
    later scene" ([decomposition §3, coupling 3][decomp]).
  - One live board had 5 repeated element ids and 2 forward references
    ([decomposition 6.3][decomp]).
  - "Object identity across scenes" is rung 8 of the representation ladder, "NOT
    kept" ([decomposition 5.10][decomp]).
- **Evidence from B.**
  - "Scenes share helpers, but no formal state contract governs every chapter
    boundary" (HD-7, [handoff][handoff]).
  - An earlier prototype's "first render succeeded technically but retained earlier
    objects over later scenes" ([06 scaling][lf06]).
  - C3 (explicit state at chunk boundaries) is the proposed starting point; independent
    clips under a shared outline are "a speed baseline" ([method comparison §C][methods]).

**Prior work.** EntityBench's entity schedules (`csv:entitybench`), LLM2Manim's symbol
ledger (`csv:llm2manim`).

**What would count as an answer.** B: "compare semantic state equality and
boundary-frame geometry" ([method comparison C3][methods]); T06: "object identities
survive transitions" ([handoff][handoff]). A: the anchor "persists or match-cuts across
scenes" ([decomposition 4.4][decomp]). No numeric metric in either source.

**Cheapest first experiment.** B's step 3: "compare C2 with C3 while using identical
scripts and render components. Measure continuity, repeated introductions, and edit
cost" ([method comparison, experiment order][methods]).

### Scale, cost, data & distillation

#### RQ-26 · What does an accepted lesson cost, and how should calls be routed?

**Question.** What is the all-attempt cost per accepted output, which stage dominates
it, and when should a cheaper model take a call?

**Why it is open.** A grades it T1 and has no ledger at all. B has real per-request
ledgers for a few dollars of calls and only hypothetical figures for everything else.

- **Evidence from A.**
  - "There is no cost tracking. Not partial — none" ([catalogue 18][catalogue]). The
    merged engine has no ledger; `engine/llm.py` reads provider usage only to explain
    truncations.
  - The only cost data is a debugger estimate over 171 traces: TTS 57% of total
    ([decomposition 6.4][decomp]). The "~85%" figure is the sibling project's
    measurement ([roadmap §C][roadmap]).
  - Three of four agent stages default off because nobody can price them
    ([decomposition 6.4][decomp]).
- **Evidence from B.**
  - Provider-reported spend: $0.48565189 across 13 pilot requests and $1.298211 for
    the lesson's generation, both including failed and truncated calls
    ([pilot RESULTS][pilot], [costs.md][costs]). These "exclude local compute,
    assistant work and human review" ([handoff][handoff]).
  - "This pilot has no defensible finite cost per accepted animation to report"
    ([pilot RESULTS][pilot]).
  - Illustrative, explicitly hypothetical lesson: LLM $2.1330 premium / $0.9355
    hybrid / $0.0808 economy per attempt; with $30 of assumed review time the attempt
    totals are $33.593 / $32.3955 / $31.5408 ([cost analysis][costan]).

**Prior work.** InflationAgent (`csv:inflationagent`), UCCI (`csv:ucci`),
FrugalGPT / RouteLLM (`csv:frugalgpt-routellm`). B's historical-cost table explains why
Code2Video, TheoremExplainAgent, TeachMaster and LASEV prices are not comparable
([cost analysis][costan]).

**What would count as an answer.** A: "any two runs comparable by cost and duration",
with two tests: a cached re-run is not free and unknown ≠ $0
([agenda §8 v1.1][agenda], [roadmap §H][roadmap]). B: "(model calls + speech + assets +
compute + valued author/reviewer time for all attempts) / accepted lessons"; "if no
lesson is accepted, report total expenditure and zero accepted lessons"
([03 system architecture][lf03]).

**Cheapest first experiment.** One ledger schema that satisfies both (see §4 row 8),
applied to one short engine video and one long-form chapter.

#### RQ-27 · Can a smaller model take over, and what data makes that trustworthy?

**Question.** After routing, does a retrieved-example or fine-tuned student meet the
same acceptance bar at lower total cost, and what record structure, review axes and
splits make its training data sound?

**Why it is open.** Only B plans it. No dataset has been exported and no model
trained.

- **Evidence from A.** No problem recorded. Two table rows bear on it: a 0.6B model
  reaching 86% with an explicit design plan (`csv:deepslides`) and a 30B coder
  reaching 94% render success with renderer-in-the-loop training (`csv:manimtrainer`).
  Both are the papers' numbers.
- **Evidence from B.**
  - "No record has been exported as teacher-approved training data"
    ([dataset specification][dataset]). "One Pythagoras lesson is insufficient
    evidence for reliable distillation" ([handoff][handoff]).
  - Under its stated assumptions, distilling only code generation saves at most about
    $0.8815 per lesson; a $3,085.67 setup breaks even after about 12,343 lessons at a
    $0.25 saving ([cost analysis][costan]). All hypothetical.
  - "Do not train on raw responses as if they were approved examples"
    ([NEXT_SESSION][next]).

**Prior work.** Self-Instruct, QLoRA, DPO and EasyOPD as cited in
[06 scaling][lf06]; `csv:manimtrainer`, `csv:deepslides`, `csv:blind-resampling`.

**What would count as an answer.** "Compare against unchanged premium baseline on
unseen concepts and teachers" (T14, [handoff][handoff]); break-even
`N > C_setup / (C_teacher − C_student)` at the same quality bar ([06 scaling][lf06]).

**Cheapest first experiment.** B-H1: route by task type with no training and record
cost per accepted output ([method comparison H1][methods]).

### Evaluation with teachers and learners

#### RQ-28 · Do teachers accept the lessons and do learners learn?

**Question.** Does a lesson pass independent subject review, and do students perform
better unassisted afterwards, including on delayed and transfer tasks?

**Why it is open.** A grades it T3 and places it on a research track. Neither project
has put a lesson in front of a teacher panel or a learner.

- **Evidence from A.** "Whether a lesson works for a learner stays a study, not a
  feature" ([decomposition 4.3][decomp]). The planned design copies LLM2Manim: "≥100
  students, post-test", once a scorecard exists to correlate with
  ([agenda §8, research track][agenda]).
- **Evidence from B.** "No teacher approval, learner study or continuous human
  listening review" ([final_checks.json][final]). The protocol proposes 6–12 pupils
  for formative observation and a later matched static-vs-animated comparison with a
  delayed check ([evaluation protocol][evalp]). Launch requires one school's
  validation ([meeting minutes][minutes]).

**Prior work.** LLM2Manim's learner study (`csv:llm2manim`, S05), Tutor CoPilot (S10),
Bastani et al. (S11), IES guide (S07); student perceptions of AI-generated videos
(`csv:knowlify-student-perceptions`), LearnLM (`csv:learnlm-may25`).

**What would count as an answer.** B: unassisted post-check, delayed check and transfer
tasks, with assistance recorded ([evaluation protocol][evalp]); LH-4's primary outcome
is "unassisted transfer performance" ([literature review][lit]). A: a score that
"predicts learning rather than plausibility" ([timeline §3][timeline]).

**Cheapest first experiment.** Apply B's reviewer rubric with two reviewers to outputs
that already exist, then the 6–12 pupil formative pilot.

#### RQ-29 · Can a system diagnose a student's attempt and hint usefully?

**Question.** Can a system read a typed or handwritten attempt, find the earliest
supported error, and give a hint without revealing the answer?

**Why it is open.** Only B asks it, and nothing is built. It sits outside the video
pipeline and is listed here so that it is not lost.

- **Evidence from A.** None.
- **Evidence from B.** The task is specified with explicit outcomes and a fallback to
  a teacher ([WS6][ws6]). The evaluation set is a proposal: 30 teacher-labelled
  attempts across three topics ([evaluation protocol][evalp]).

**Prior work.** DrawEduMath (S09), MathDial (S08), GeoDial (S12), Bastani et al. (S11).

**What would count as an answer.** Transcription accuracy on answer-affecting symbols,
diagnosis precision, coverage, premature answer disclosure, and localisation accuracy,
reported as counts ([evaluation protocol][evalp]).

**Cheapest first experiment.** Typed responses first, on the proposed 30-attempt set.

### Product/editing

#### RQ-30 · How do people edit the plan and re-make only what changed?

**Question.** What does a person edit (plan, script, IR), how are edits validated, and
how small is the set of artifacts that must be regenerated?

**Why it is open.** A grades it T1. A has an editor without durable projects or
partial re-render. B edited by hand and logged it.

- **Evidence from A.** "Projects live in browser storage; edited boards skip the
  generation-time gates; any edit re-renders everything"
  ([decomposition 4.19][decomp]). "The editor's ceiling is the IR's ceiling"
  ([decomposition 6.5][decomp]).
- **Evidence from B.** The lesson's human edits are recorded as data
  ([editorial_changes.json][editorial]). Unchanged sentences are not re-synthesised
  because clips are cached by content hash (`build_audio.py`). Dependency-tracked
  selective regeneration is a proposal: "Report both compute saved and stale-cache
  defects" ([method comparison C5][methods]).

**Prior work.** Script2Screen (`csv:script2screen`), Shiksha Copilot
(`csv:shiksha-copilot`), SketchDynamics (`csv:sketchdynamics`), textual-to-visual
self-verification (`csv:t2v-self-verification-slides`).

**What would count as an answer.** "One-sentence edit costs one scene; project
survives a machine change" ([agenda §8 v2.1][agenda]). B: "rerun only affected
artifacts after a local edit" (T12, [handoff][handoff]) and incremental output equal
to a clean rebuild ([method comparison C5][methods]).

**Cheapest first experiment.** Change one sentence in one beat on each path and record
what is re-synthesised and re-rendered.

---

## 4. Where the two projects disagree or pull in different directions

Each row says what each side does, what evidence it has, and what would settle it.
Rows 14–17 record agreements that could be mistaken for disagreements.

| # | Topic | A does | B does | Evidence each has | Experiment that would settle it |
|---|---|---|---|---|---|
| 1 | Target length and when to attempt it | 90–140 s videos; lesson length (12–15 min) is the last version, v3.0 / M6, after cost, composition, sync and judgement ([agenda §8][agenda]) | Starts from a ~20-minute lesson as the product ([08][lf08]). B's own meeting asked for 5–10 min and none above 15 ([minutes][minutes]); B says the later document takes precedence | A: median 94.2 s over 46 videos; no long run. B: one 1,200.003 s lesson, technically passing, rejected for narration; "one lesson is an integration test" ([methods][methods]) | Same concept as one continuous long lesson and as chaptered short videos, same script; reviewer rubric and unassisted post-check ([evaluation protocol][evalp]) |
| 2 | Default language | Hinglish narration, English on screen, English-spoken technical terms ([decomposition 6.7][decomp]) | English (US) narration; Hindi as a later independent adaptation with its own timeline (T10) | A: language contract at L3; no listening study. B: no Hindi produced; the English lesson was rejected for delivery, not language | T03: English and Hindi clips of the same excerpt, fluent listeners; include the engine's Indian-language voices |
| 3 | Synthesis unit | One clip per cue (mean 19.5 words); the finer per-element split was rejected on cost; plans word marks inside the cue clip ([decomposition 5.6][decomp]) | Built one clip per sentence (274); now recommends whole teaching blocks of 45–90 s or 90–180 s ([handoff][handoff]) | A: none on delivery quality. B: one user judgement; cause "plausible … not isolated experimentally" | Fixed script and voice at sentence, cue and block granularity; blind listening; also record alignment error and re-synthesis cost per edit, because A wants finer sync and B wants longer context |
| 4 | Where timing comes from | Audio is synthesised during the render inside a voiceover block; entrances take a fraction of the beat; a beat filler uses the rest ([decomposition 4.14][decomp]) | Audio is built and measured first; scenes wait on `timeline.json`; narration is muxed at assembly (`build_audio.py`, `lesson_runtime.py`, `assemble.py`) | A: "2–3 s of animation inside an 8–12 s beat"; dead air unmeasured. B: chapter length within 0.00067 s of the timeline; within-sentence times estimated. Both let measured audio set beat length; they differ on when audio exists and whether anchors exist | Render one lesson contract both ways; measure anchor error against a forced alignment and total dead air |
| 5 | Who writes the visuals | A model writes a storyboard IR; a deterministic transpiler writes all scene code ([chapter 4][ch4]) | A model drafted per-chapter Manim; the final code is a manual reconstruction ([editorial][editorial]). B's design documents recommend a typed specification and compiler (B-D3) | A: failure classes removed by construction; expressiveness limits listed. B: no pilot candidate passed; drafts had invalid geometry. The designs agree; the practice differs | RQ-09's experiment: express B's chapters as IR and count what cannot be said; compare defects and human minutes (LH-2) |
| 6 | What the layout check measures | Text-on-text, clipped text and text-over-shape after every play; shape-on-shape reported only; images skipped ([decomposition 4.16][decomp]) | Every top-level object against the stage and caption region at each beat end, plus sampled-frame review (`lesson_runtime.py`, [REVIEW][review]) | A: fixture 11 → 0; three audits found unmeasured classes. B: 0 of 40 violations, yet a crossfade overlap found by eye. The checks are complementary, not rival | Planted-fault suite run through both; precision and recall per class (09-T5) |
| 7 | Who repairs | An LLM rewrites flagged scene code; accepted only if it renders and reduces violations; two rounds ([decomposition 4.17][decomp]) | A person and a coding assistant repaired the lesson; one diagnostic-guided LLM repair in the pilot; the proposed protocol tries a deterministic fix first ([lf09][lf09]) | A: 23 of 46 videos ship with a residue. B: the one automated repair was partial. Both say repair should act on the specification, not the code (A's highest-level repair rule; B-G3) | Same failing scenes through A's loop, B's protocol and a human; resolved defects, new defects, human minutes, spend, fixed retry budget |
| 8 | Cost accounting | No ledger. Plan: per-run `cost.json`, retries metered, cache hits at would-have-cost, unknown ≠ 0. Unit is a run; human time not counted ([roadmap §H][roadmap]) | Per-request provider-reported ledgers with a price snapshot and failed calls included. Unit is the accepted lesson; human review is counted ([cost analysis][costan]) | A: debugger estimate, TTS 57%. B: $1.78386289 of real calls; review time is an assumed $30. They disagree on what dominates: A says speech, B's model says human review, and B's speech was local | One schema: provider-reported usage per call, retries, cache-hit would-have-cost, human minutes, accepted flag. Run on one short video and one chapter |
| 9 | What a chapter is | "A properly-structured short video with its own arc", threaded by a running summary ([catalogue 22][catalogue]); hard cuts between chapters ([roadmap §6][roadmap]) | Independent clips under a shared outline are "a speed baseline"; "avoid treating it as the final long-form design"; wants explicit entry and exit state ([methods §C][methods]) | A: design only; the anchor is re-drawn every scene. B: its own ten chapters have no state contract (HD-7) | B's C2 vs C3 comparison on identical scripts: continuity, repeated introductions, edit cost |
| 10 | Filling the beat | Code fills idle time with gestures so the frame is never frozen ([catalogue 13][catalogue], [roadmap §D][roadmap]) | "Decorative continuous movement is not a quality criterion"; "a held diagram during reasoning can be intentional" ([08 §1][lf08]) | Both rest on user reports: A's "there are no dynamic motion in the gen video" ([roadmap §D][roadmap]), B's request for "purposeful highlights" ([NEXT_SESSION][next]). No measurement on either side | RQ-15's A/B with and without the filler |
| 11 | Where the human gate sits | "No human drawing, recording, or editing at any step" ([timeline §1][timeline]); a curator step and an editable plan are future work | Script approved before visuals; teacher review; school validation before launch ([Code2Video assessment][c2v], [minutes][minutes]) | A: every quality regression was found by a person watching after render. B: the lesson was rejected by a person after render | Human minutes per accepted lesson with the gate before spend vs after render |
| 12 | Is code-switched alignment solved? | The agenda says "solved enough for bookmarks" ([agenda §0][agenda]); A's catalogue, timeline and decomposition, dated the same day, call it open ([catalogue 12][catalogue], [timeline §3][timeline], [decomposition 6.7][decomp]) | "Hindi-English switching can make automatic alignment unreliable. Validate" ([methods E3][methods]) | A: one paper's 4.15 ms; the table row notes the script is unstated and no model release is known. B: none | Align a handful of Hinglish cue clips with an off-the-shelf aligner; hand-label word boundaries |
| 13 | Sync tolerance | ±300 ms ([P06][P06]; v1.3 exit) | 200 ms, proposed and still to be assessed (T05) | Neither is measured | Human A/B at several offsets, inside RQ-12 |
| 14 | Vision critics | Advisory until calibrated; built and off ([catalogue 2][catalogue]) | "One signal and must not manufacture acceptance" ([08 §5][lf08]) | — | **They agree.** |
| 15 | Repair round cap | Two rounds by default ([P04][P04]) | "Cap automated repair at two rounds per scene for the demonstration" ([Code2Video assessment][c2v]) | — | **They agree.** |
| 16 | A passing render is not acceptance | "Exit code 0 proves nothing" ([roadmap §D-sim][roadmap]); a measure that stops at the IR misreports the video ([roadmap §3d][roadmap]) | "A successful process exit or plausible screenshot is not acceptance" ([handoff][handoff]) | Each has shipped a technically clean output that a person rejected | **They agree.** |
| 17 | When to study learners | A ≥100-student study on a research track, after a scorecard exists | A 6–12 pupil formative pilot right after the revised lesson (T11) | Neither has run one | Not a conflict: formative first, summative later. The timing differs (see §6) |

---

## 5. What each side already solves for the other

Only pairs with a file on both sides. "Solves" means "is a working starting point",
with the stated limit.

### From A to B

| A has | B needs | Limit |
|---|---|---|
| Per-play layout probe: [`layout_probe.py`](../../src/lessonforge/layout_probe.py), design in [layout_framework.md][layoutfw] | T08 and HD-6: "inspect layout and motion intervals" ([handoff][handoff]); 09-T5 | Counts text classes only; no mid-transition sampling; images skipped. It does not check a caption region; B's bounds check does |
| Accept-if-better repair with preservation guards: [`engine/render.py`](../../src/lessonforge/engine/render.py) | The acceptance step of B's scoped repair protocol: "reject no-op patches", rerender, rerun the violated check ([lf09][lf09]) | The acceptance measure is a violation count, not B's semantic invariants |
| Typed storyboard IR with a schema drift gate and a deterministic compiler: [`engine/schemas.py`](../../src/lessonforge/engine/schemas.py), [`transpiler.py`](../../src/lessonforge/transpiler.py) | B-D3, T06, and Ticket 1 "Scene schema and renderer refactor" with Pydantic schemas ([lf07][lf07]) | The IR has no beat-level state contract and no parameter-driven graph components (09-T3) |
| Speech chain with retries, a keyless fallback, a content-addressed cache, a mute mode and a Gemini TTS service: [`viz_helpers.py`](../../src/lessonforge/viz_helpers.py) | T02: "speech adapter with … explicit model/voice/locale, cost ledger and bounded retries" ([handoff][handoff]) | Gemini TTS is reached through OpenRouter, which B says its Cloud prices do not cover; no cost ledger; per-cue requests |
| Voice-direction prompt for Gemini TTS: [audio_agent.md][audioagent] | HD-3: "no explicit evaluated voice direction" ([handoff][handoff]) | A document only; not wired into code and never evaluated |
| Story measures: `narrative_problems()` and `coverage()` in [`engine/storyboard.py`](../../src/lessonforge/engine/storyboard.py) and [`engine/pipeline/screens.py`](../../src/lessonforge/engine/pipeline/screens.py) | T01: mark "broken transitions, repetition and unclear references" ([handoff][handoff]) | They read the storyboard IR; A itself found `coverage()` over-reports when assets degrade |
| Source intake into numbered, citable chunks: [`engine/sources.py`](../../src/lessonforge/engine/sources.py) | B-A1 transcript corpus and B-B3 retrieval of subject evidence ([methods][methods]); WS1 evidence cards | Grounding, not a teaching-move library; rights are B's open decision |
| Verified per-element simulations: [`engine/sim_gen.py`](../../src/lessonforge/engine/sim_gen.py) | B-D4 "numerical simulation for changing systems"; WS4 simulations with stated update rules ([ws4][ws4]) | Plays once per cue; checks motion and containment, not physical correctness |
| Resumable manifest runner with per-row stage caches: [`engine/bulk_runner.py`](../../src/lessonforge/engine/bulk_runner.py) | T12 "resumable builds"; A's own design makes "rows are chapters" ([roadmap §6][roadmap]) | Rows are topics today; no dependency tracking |
| Failure classification before repair (infra / LaTeX / code): [`engine/render.py`](../../src/lessonforge/engine/render.py) | B-G2 "classify the failure" and the handoff's staged repair order | Three classes; B asks for layout, semantic, timing and continuity as well |
| Routing table that blocks reasoning models: [`engine/model_routing.py`](../../src/lessonforge/engine/model_routing.py) | B paid $0.417120 for a call that "returned no visible script after consuming its reasoning/output limit" ([costs.md][costs]) | The block list is by model name |
| 116-row paper table: [research-papers.csv][csv] | B's register has 19 entries and nothing on alignment, layout solvers or judge calibration ([sources][sources]) | A marks which rows were link-verified; the rest are from a sweep |

### From B to A

| B has | A needs | Limit |
|---|---|---|
| Per-request usage ledgers, a price snapshot, and failed calls included: [costs.md][costs], [usage.json](../longform/pythagoras_case_study/usage.json), [pilot usage](experiments/openrouter_pilot/usage.json) | cat-18, P02, v1.1 "Receipt" | Files written by one-off runner scripts, not a library; no TTS or render cost |
| Assembly with captions, chapter markers, loudness normalisation and a media probe that is asserted on (`assemble.py`, `finalize_checks.py`; output in [final_checks.json][final]) | dec-4.18 rates assembly L2 with hard cuts and a thin record ([decomp][decomp]); v3.0 needs chapter assembly | A's documents never list captions or loudness as gaps; they are simply absent. Porting |
| Audio-first measured timeline and phrase-anchored cues that fail loudly on a missing phrase (`build_audio.py`, `lesson_runtime.py`) | Rung 7 of A's ladder, "word marks in cues", is "NOT kept" ([decomposition 5.10][decomp]); P06 wants a `dead_air_s` measure | Anchor times are word-position estimates; authored in scene code, not in an IR. Porting |
| Subject checks: symbolic and numeric (`verify_math.py`, [math_checks.json][mathchk]) and on the renderer's actual vertices (`verify_render_geometry.py`, [render_geometry_checks.json][geomchk]) | cat-3 "verification only understands geometry, not meaning" ([catalogue][catalogue]) | Hand-written for one lesson |
| Reviewer rubric, defect severities and a result-table template: [evaluation protocol][evalp] | P01's first step, "write the rubric as a doc … add scored fields to the sidecar" ([P01][P01]) | Proposed thresholds, uncalibrated, never applied |
| Real, described faults: pilot candidates with written defect lists ([pilot RESULTS][pilot], sources in [openrouter_pilot/](experiments/openrouter_pilot/)) and six script corrections ([editorial][editorial]) | v1.1's planted-fault set and P03's golden-frame set ([agenda §8][agenda], [P03][P03]) | One topic each; frames and videos are not in this tree |
| Explicit thinking pauses that the build never trims (`thinking_pause_seconds` in `build_audio.py`) | R11 pacing; A has `[SPEED]/[PAUSE]` pacing tags ([roadmap §C][roadmap]) but no pause the build guarantees | One lesson |
| Dataset record types, seven review axes and family-level splits: [dataset specification][dataset] | The memory admission rule, "only fixes that stayed verified may be remembered" ([catalogue 17][catalogue]), and the 185 unmined traces ([P07][P07]) | Version 0.1 proposal; no records |
| Literature A's table lacks: TeachMaster (S04), PhyEduVideo (S06), MathDial (S08), DrawEduMath (S09), Tutor CoPilot (S10), Bastani et al. (S11), GeoDial (S12) — none appear in [research-papers.csv][csv] | R13 learner-study design; RQ-19 | B read several at abstract level only ([sources][sources]) |
| Code-level audit of four repositories at pinned commits: [audit][audit] | A's agenda cites the same systems from papers. The audit and A's table agree that Code2Video has no narration audio | Inspection, not reproduction |

Both projects independently give each concurrent Manim job its own media directory
(`engine/render.py`; B's [case-study README](../longform/pythagoras_case_study/README.md)).

---

## 6. A single prioritised sequence (proposal)

**This section is a proposal.** It reconciles two plans that were written without
knowledge of each other. Neither source endorses it.

**The two plans as written.**

- A: v1.1 Receipt → v1.2 Composed frames → v1.3 Synced narration → v1.4 Plan on by
  default → v2.0 Judges itself → v2.1 Projects & editing → v2.2 Semantic motion → v3.0
  Lesson-length, with a research track alongside. Mapping: M1→v1.1, M2→v1.1/1.2,
  M3→v1.3/1.4, M4→v2.0, M5→v2.1, M6→v3.0, M7→research track ([agenda §8][agenda]).
  The calendar starts 2026-08-24 and puts v1.3 at 10-05 → 10-25. On 2026-10-07 the
  merged code shows no cost ledger, `composition` is still only logged, and no
  bookmark is emitted, so the v1.1 and v1.2 exits are not evidenced in this tree.
- B: T01–T03 (script review, speech adapter, comparison clips) first; T04–T08 at P0;
  T09–T12 at P1; T13–T14 at P2 ([handoff][handoff]).

**Where their own priorities conflict.**

1. **Long-form.** A puts it last because "at ten times the length, everything
   unmeasured becomes expensive" ([timeline M6][timeline]). B builds the long lesson
   first "to expose continuity and pacing problems" ([08 §7][lf08]).
2. **Cost.** A puts the receipt first. B puts queueing and cost accounting at P1
   (T12), though T02 asks for a per-clip ledger at P0.
3. **Layout before sync, or after.** A does composition (v1.2) before sync (v1.3). B
   does speech and alignment (T01–T05) before layout checks (T08).
4. **Learners.** A waits for a scorecard. B runs a small pilot straight after T09.
5. **Script quality.** A reaches the plan and its lints at v1.4. B starts with a human
   script review (T01).

**Proposed order.** "Needs" lists hard dependencies only.

| Step | Work | From A | From B | RQs | Needs | Note |
|---|---|---|---|---|---|---|
| 0 | Finish the port: lesson contract, speech-first build, `LessonScene`, assembly, checks, bridge | — | B's scripts | — | — | In progress on 2026-10-07 |
| 1 | One receipt for both paths: per-run folder, cost ledger, record of duration and render path | v1.1, M1/M2 | T02 (ledger part), T12 (cost part) | RQ-26, ENG-1, ENG-2 | 0 | Follows A's order; B's ledgers show the shape. Conflict 2 resolved in A's favour because every later comparison needs it |
| 2 | Script review of the existing lesson | — | T01 | RQ-04, RQ-05 | — | Human work; runs in parallel with step 1 |
| 3 | Synthesis-unit and voice experiment on one excerpt | v1.3 (script critic) | T02, T03 | RQ-11, RQ-16 | 1 for paid voices, 2 | Start with the local voice so the unit is isolated before money is spent |
| 4 | Contracts and stable ids: beat, anchor, object identity | IR rungs 7 and 8 ([decomposition 5.10][decomp]) | T04 | RQ-25, RQ-12 | 2 | One schema change serves both projects |
| 5 | Alignment and anchor resolution; `dead_air` and anchor-hit measures | v1.3 | T05 | RQ-12 | 3, 4 | Conflict 3: this puts sync before composition, against A's order, because the only human verdict on a long lesson concerns its audio |
| 6 | Layout verification over time: probe on long-form chapters, shape-on-shape counted, mid-transition class, planted-fault set | v1.1 (fixtures), v1.2 (probe items) | T08 | RQ-17 | 0 | Independent of 2–5; can start at once. B lists T08 after T06–T07; running the probe needs neither |
| 7 | Composition: balance number, keyword map, row/column relations | v1.2, M3 | — | RQ-07, RQ-08 | 6 for the planted set | A only; parallel to 3–5 |
| 8 | Typed components and the IR expressiveness test; attention events | — | T06, T07 | RQ-09, RQ-19, RQ-15 | 4, 5 | The bridge experiment decides how much of B's lesson the transpiler can own |
| 9 | Plan on by default; pedagogy lints; fidelity spot-check | v1.4 | — | RQ-01, RQ-04, RQ-05 | 1 | A's reason for waiting is price, which step 1 supplies |
| 10 | Revised full English lesson, built by chapters with a running summary | v3.0, M6 | T09 | RQ-24, RQ-25 | 3–8 | Conflict 1: earlier than A's v3.0. A's prerequisites for v3.0 (ledger, per-run folder, script gate) are steps 1 and 3; parallel repair is not yet covered |
| 11 | Scorecard, reviewer rubric, small learner pilot | v2.0 (scorecard), M7 | T11 | RQ-23, RQ-28 | 10 | Conflict 4: formative pilot now, A's large study later |
| 12 | Vision calibration, repair stop rule and residue classes, fix memory | v2.0, M4 | 09-T6 | RQ-20, RQ-21, RQ-22 | 1, 6 | |
| 13 | Projects, validated edits, re-make only what changed | v2.1, M5 | T12 (rest) | RQ-30, ENG-1 | 1 | |
| 14 | Hindi adaptation with its own timeline | — | T10 | RQ-16, RQ-12 | 10 | The engine's Hinglish path already exists for short videos |
| 15 | Simulations across cues; resemblance checks | v2.2 | — | RQ-14, RQ-10 | 12 | |
| 16 | Dataset, then retrieval and distillation benchmark | — | T13, T14 | RQ-27, RQ-03 | 10, 11 | B: only after accepted lessons exist |
| — | Research track, no step depends on it | R12, R13, R7, R10 tails | — | RQ-01, RQ-28, RQ-18, RQ-12 | — | As in A |

Not placed in the order: RQ-02 (needs the school, not the code), RQ-06 and RQ-29
(outside the video pipeline).

---

## 7. Appendix: ID crosswalk

Every id maps to an RQ, or to an `ENG-*` entry (7.9) where the honest answer is "not a
research question: engineering task".

### 7.1 A — research agenda R1–R18

| ID | Problem (short) | Maps to |
|---|---|---|
| R1 | Quality score tracking human judgement | RQ-23 |
| R2 | Calibrating a vision critic | RQ-20 |
| R3 | When to stop repairing; repair the plan | RQ-21 |
| R4 | Remembering fixes without poisoning | RQ-22 |
| R5 | Composing a frame | RQ-08 |
| R6 | Honouring composition intent | RQ-07 |
| R7 | Verifying layouts across animation time | RQ-17; frame-aware tail RQ-18 |
| R8 | Drawings that resemble their subject | RQ-10 |
| R9 | Systems that evolve with the narration | RQ-14 |
| R10 | Word-synced entrances in Hinglish | RQ-12; locale side RQ-16 |
| R11 | Pacing for a grade band | RQ-13 |
| R12 | Narration fidelity; invention vs hallucination | RQ-01 |
| R13 | Does the lesson teach? | RQ-05 (lints), RQ-28 (learners) |
| R14 | Plan with contracts; measured coverage | RQ-04 |
| R15 | Lesson length by chapterisation | RQ-24; identity and terminology across units RQ-25 |
| R16 | Human-in-the-loop editing over the IR | RQ-30 |
| R17 | Cost accounting and routing under retries | RQ-26 |
| R18 | Grounding for Indian curricula | RQ-02 |

### 7.2 A — problem catalogue 1–25

| ID | Problem (short) | Maps to |
|---|---|---|
| cat-1 | Can't tell a good video from a bad one | RQ-23 |
| cat-2 | Machine visual judgement not trustworthy | RQ-20 |
| cat-3 | Verification understands geometry, not meaning | RQ-19 (meaning), RQ-17 (skipped classes) |
| cat-4 | New visual capability costs verification coverage | RQ-18 |
| cat-5 | Repair destroys what the verifier can't see | RQ-21 (T1; a discipline inside the repair question) |
| cat-6 | Nothing checks narration against the source | RQ-01 |
| cat-7 | Nothing checks whether the lesson teaches | RQ-05, RQ-28 |
| cat-8 | No gate before the most expensive step | RQ-11 |
| cat-9 | Composition intent never reaches the layout engine | RQ-07 |
| cat-10 | The scene has no structure to lay out | RQ-08 |
| cat-11 | Frames unbalanced and under-filled | RQ-08 |
| cat-12 | Animation timed against the clock, not the words | RQ-12 |
| cat-13 | Motion points; it doesn't explain | RQ-14; the pointing half RQ-15 |
| cat-14 | Drawings checked for existence, not resemblance | RQ-10 |
| cat-15 | Self-repair has no theory of when it's stuck | RQ-21 |
| cat-16 | Repair edits the code instead of the plan | RQ-21 |
| cat-17 | The system doesn't remember its fixes | RQ-22 |
| cat-18 | Can't say what a video cost | RQ-26 |
| cat-19 | Nothing survives a crash | not a research question: engineering task (ENG-1) |
| cat-20 | Experiments die silently between stages | not a research question: engineering task (ENG-2) |
| cat-21 | The same decision is made in two places | not a research question: engineering discipline (ENG-3); a live instance is duration, RQ-13 |
| cat-22 | Videos capped at about four minutes | RQ-24 |
| cat-23 | Batch generation never graded on real work | not a research question: engineering task (ENG-4) |
| cat-24 | Projects don't outlive the browser | RQ-30 |
| cat-25 | One small edit re-does the whole video | RQ-30 |

### 7.3 A — problems site P01–P11

| ID | Problem (short) | Maps to |
|---|---|---|
| P01 | No end-to-end quality score | RQ-23 |
| P02 | Durable state, cost and run ledger | RQ-26 (cost); state half is ENG-1 |
| P03 | Trustworthy machine perception | RQ-20 |
| P04 | Repair-loop convergence | RQ-21 |
| P05 | Composition intent never reaches the solver | RQ-07 |
| P06 | Narration–animation sync by construction | RQ-12 |
| P07 | Self-improving repair memory is inert | RQ-22 |
| P08 | Grounding without a fidelity gate | RQ-01 |
| P09 | Pedagogy compiles unverified | RQ-05; learner tail RQ-28 |
| P10 | The verifier sets the expressiveness ceiling | RQ-18 |
| P11 | The scene has no structure to lay out | RQ-08; finding 3 (probe blind spots) RQ-17 |

### 7.4 A — decomposition sub-problems and cross-cutting problems

| ID | Sub-problem | Maps to |
|---|---|---|
| dec-4.1 | Commissioning | RQ-13 (length), RQ-24 (chapters) |
| dec-4.2 | Grounding | RQ-01, RQ-02 |
| dec-4.3 | Lesson decomposition | RQ-04, RQ-05, RQ-13 (pace) |
| dec-4.4 | Narrative | RQ-04 (narration side), RQ-25 (visual side) |
| dec-4.5 | Screen planning | RQ-04 |
| dec-4.6 | Scene authoring | RQ-04 |
| dec-4.7 | Language realisation | RQ-16; script gate RQ-11 |
| dec-4.8 | Admission and memory | not a research question: engineering task (ENG-1, ENG-2) |
| dec-4.9 | Object realisation | RQ-10, RQ-09 |
| dec-4.10 | Spatial composition | RQ-07, RQ-08 |
| dec-4.11 | Hierarchy, lifetime, theme | RQ-08; emphasis RQ-15 |
| dec-4.12 | Motion | RQ-14, RQ-15 |
| dec-4.13 | Voice | RQ-11 |
| dec-4.14 | Sync | RQ-12 |
| dec-4.15 | Program synthesis | RQ-09 |
| dec-4.16 | Render and measurement | RQ-17, RQ-20 |
| dec-4.17 | Repair | RQ-21, RQ-22 |
| dec-4.18 | Assembly and the record | RQ-26; the record itself is ENG-1 |
| dec-4.19 | Delivery and review | RQ-30 |
| dec-6.1 | Evaluation | RQ-23 |
| dec-6.2 | Provenance and grounding | RQ-01; attribution line ENG-5 |
| dec-6.3 | Identity and continuity across units | RQ-25 |
| dec-6.4 | Cost as a design variable | RQ-26 |
| dec-6.5 | The human control surface | RQ-30 |
| dec-6.6 | Reproducibility and state | not a research question: engineering task (ENG-1) |
| dec-6.7 | Localisation | RQ-16, RQ-12 |
| dec-6.8 | Compliance | not a research question: engineering task (ENG-5) |

The eight unnumbered open questions in [timeline §3][timeline] map, in order, to
RQ-28 (with RQ-05 and RQ-23), RQ-20, RQ-21, RQ-12, RQ-01, RQ-22, RQ-18, RQ-08.

### 7.5 A — milestones and versions

Mapped by content. The agenda's own one-line mapping (M2→v1.1/1.2, M3→v1.3/1.4) does
not match content in two places: composition is M3 in the timeline and v1.2 in the
agenda, and "plan on by default" (v1.4) is in no milestone.

| ID | Promise (short) | Maps to |
|---|---|---|
| M1 | Tells you when it fell short | ENG-1, ENG-2; supports RQ-17, RQ-20, RQ-23 |
| M2 | Receipt; no work lost | RQ-26, ENG-1 |
| M3 | Composed, not merely tidy; entrances on the words | RQ-07, RQ-08, RQ-12 |
| M4 | Looks at its own work | RQ-20, RQ-21, RQ-22 |
| M5 | Real projects, real editing | RQ-30 |
| M6 | Lesson-length videos | RQ-24, RQ-25 |
| M7 | Tells a good lesson from a bad one | RQ-28, RQ-23, RQ-05, RQ-01 |
| v1.1 | Receipt | RQ-26, ENG-1; planted-fault set for RQ-17, RQ-20 |
| v1.2 | Composed frames | RQ-07, RQ-08, RQ-17 |
| v1.3 | Synced narration | RQ-12, RQ-11, RQ-13 |
| v1.4 | Plan on by default | RQ-04, RQ-05, RQ-01 |
| v2.0 | Judges itself | RQ-23, RQ-20, RQ-21, RQ-22 |
| v2.1 | Projects & editing | RQ-30 |
| v2.2 | Semantic motion | RQ-14, RQ-10 |
| v3.0 | Lesson-length | RQ-24, RQ-25 |
| Research track | R12, R13, R7, R10 tails | RQ-01, RQ-28, RQ-18, RQ-12 |

### 7.6 B — the eight problems

| ID | Problem | Maps to |
|---|---|---|
| B-A | Acquiring useful evidence from expert teachers | RQ-03 |
| B-B | Generating a script that teaches for twenty minutes | RQ-04; factual-defect measure RQ-01; B5 (fine-tuned script model) RQ-27 |
| B-C | Preserving continuity across long videos | RQ-25 (C3, C4); RQ-24 (C1, C2); RQ-30 (C5) |
| B-D | Producing expressive and correct visual code | RQ-09; correctness checks RQ-19; D4 RQ-14; D5 RQ-27 |
| B-E | Natural narration and audiovisual synchronization | RQ-11 (E1, E2); RQ-12 (E3, E4); RQ-16 (E5) |
| B-F | Detecting and preventing overlap and formatting defects | RQ-17 (F3); RQ-08 (F1, F2, F5); RQ-07 (F1); RQ-20 (F4) |
| B-G | Repairing failures without breaking the lesson | RQ-21 (G1–G4); RQ-22 (G5) |
| B-H | Training and scaling economically | RQ-26 (H1); RQ-27 (H2–H5) |

### 7.7 B — handoff tasks T01–T14

| ID | Deliverable (short) | Maps to |
|---|---|---|
| T01 | Review the existing script | RQ-04 |
| T02 | Google speech adapter with ledger and bounded retries | RQ-11; ledger RQ-26. The adapter itself is an engineering task |
| T03 | English/Hindi comparison clips | RQ-11, RQ-16 |
| T04 | Versioned lesson/scene/audio/highlight contracts and stable ids | engineering deliverable serving RQ-25, RQ-12, RQ-15 |
| T05 | Alignment and anchor resolver | RQ-12 |
| T06 | Persistent geometry and typed scene components | RQ-09, RQ-25, RQ-19 |
| T07 | Independent attention scheduler | RQ-15 |
| T08 | Layout and motion collision checks | RQ-17 |
| T09 | Revised full English lesson | RQ-24; integrates RQ-04, RQ-11, RQ-12 |
| T10 | Full Hindi adaptation and locale-specific timeline | RQ-16 |
| T11 | Teacher rubric and small learner pilot | RQ-28; rubric RQ-23 |
| T12 | Queue, content hashes, retry budgets, cost accounting, resumable builds | RQ-26 (cost), RQ-30 (rerun only affected artifacts); queue and resume are not a research question: engineering task (ENG-1) |
| T13 | Rights-aware accepted/failure dataset | RQ-27; rights also RQ-03 |
| T14 | Retrieval and distillation benchmark | RQ-27 |

### 7.8 B — other numbered items

| ID | Item | Maps to |
|---|---|---|
| 09-T1 | Corpus contracts | RQ-03 |
| 09-T2 | Script experiments | RQ-04 |
| 09-T3 | Shared semantic state | RQ-09, RQ-19 |
| 09-T4 | Audio schedule | RQ-12; reviewed joins RQ-11 |
| 09-T5 | Temporal layout | RQ-17 |
| 09-T6 | Repair executor | RQ-21 |
| 09-T7 | Long lesson assembly | RQ-24, RQ-25 |
| 09-T8 | Cost and training baseline | RQ-26, RQ-27 |
| HD-1 | Disconnected delivery | RQ-11; script coherence RQ-04 |
| HD-2 | Artificial pacing | RQ-13 |
| HD-3 | Weak teacher performance | RQ-11 |
| HD-4 | Approximate synchronization | RQ-12 |
| HD-5 | Ad hoc highlighting | RQ-15 |
| HD-6 | Residual overlap risk | RQ-17 |
| HD-7 | Long-form continuity | RQ-25 |
| HD-8 | Raw code reliability | RQ-09, RQ-21 |
| WS1 | Curriculum mapping and teacher evidence | RQ-02, RQ-03 |
| WS2 | Scripts and instructional design | RQ-04, RQ-05, RQ-13 |
| WS3 | Code to video and narration | RQ-09, RQ-19, RQ-12 |
| WS4 | Science and biology representations | RQ-19, RQ-14, RQ-10 |
| WS5 | Problem generation and verification | RQ-06 |
| WS6 | Student work diagnosis and feedback | RQ-29 |
| WS7 | Validation and school rollout | RQ-28 |
| LH-1 | Reviewed scripts improve generated lessons | RQ-04, RQ-01 |
| LH-2 | Explicit scene contracts reduce inconsistency | RQ-09 |
| LH-3 | Visual review catches additional defects | RQ-20, RQ-19 |
| LH-4 | Animation improves learning for selected concepts | RQ-28 |
| LH-5 | Targeted hints support learning | RQ-29 |
| LH-6 | Reusable components reduce accepted-production cost | RQ-09, RQ-26 |
| lf07 Tickets 0–7 | GPU inventory, schema and renderer refactor, verifier, dataset export, teacher generation, SFT, held-out evaluation, optional DPO | engineering tasks under RQ-27; Ticket 1 touches RQ-09, Ticket 2 RQ-17 and RQ-19 |
| lf06 milestones 1–5 | production foundation → scaled production | 1: RQ-09; 2–4: RQ-27; 5: ENG-1, ENG-4 |

Deliberately not made questions: the three learner levels (the meeting deferred them,
[minutes][minutes]); which model is best (B's pilot is explicitly not a ranking; the
routing question is inside RQ-26).

### 7.9 Engineering tasks that are not research questions

| ID | Task | Source ids |
|---|---|---|
| ENG-1 | Durable job list, one folder per run, resume, a record of duration and render path | cat-19, P02 (state half), dec-4.8, dec-4.18, dec-6.6, road-#5, road-#7; T12 (queue, resume) |
| ENG-2 | Every output-changing setting reachable per job and part of the cache identity | cat-20, dec-4.8, road-#19 |
| ENG-3 | One owner per decision; merge twins instead of aligning them | cat-21 |
| ENG-4 | Grade the batch runner on a real multi-topic run | cat-23 |
| ENG-5 | On-screen attribution for CC-BY images; sandbox for model-written code; rights records for assets | dec-6.8, dec-6.2; B's asset record in [03][lf03] |

[agenda]: engine/research-agenda.md
[catalogue]: engine/problem-catalogue.md
[decomp]: engine/problem-decomposition.md
[timeline]: engine/improvement-timeline.md
[csv]: engine/research-papers.csv
[ch4]: engine/chapter-4-architecture.md
[site]: engine/problems/index.html
[P01]: engine/problems/p01-quality-score.html
[P03]: engine/problems/p03-vision-qa.html
[P04]: engine/problems/p04-repair-convergence.html
[P05]: engine/problems/p05-semantic-composition.html
[P06]: engine/problems/p06-narration-sync.html
[P07]: engine/problems/p07-repair-memory.html
[P08]: engine/problems/p08-grounding-fidelity.html
[P09]: engine/problems/p09-pedagogy-gate.html
[P10]: engine/problems/p10-camera-and-verifier.html
[P11]: engine/problems/p11-layout-frameworks.html
[roadmap]: ../engine/pipeline-roadmap.md
[layoutfw]: ../engine/layout_framework.md
[audioagent]: ../engine/audio_agent.md
[lit]: review/01_literature_review.md
[c2v]: review/02_code2video_assessment.md
[sources]: review/03_source_register.md
[methods]: review/04_long_form_method_comparison.md
[audit]: review/05_paper_and_code_audit.md
[costan]: review/06_cost_analysis.md
[pilot]: experiments/openrouter_pilot/RESULTS.md
[dataset]: scaling/dataset_specification.md
[handoff]: ../longform/HANDOFF_REPORT.md
[next]: ../longform/NEXT_SESSION.md
[lf03]: ../longform/03_system_architecture.md
[lf06]: ../longform/06_scaling_dataset_and_distillation.md
[lf07]: ../longform/07_frameworks_and_implementation_handoff.md
[lf08]: ../longform/08_narration_led_long_form_approach.md
[lf09]: ../longform/09_combined_architecture_and_tickets.md
[review]: ../longform/pythagoras_case_study/REVIEW.md
[costs]: ../longform/pythagoras_case_study/costs.md
[final]: ../longform/pythagoras_case_study/checks/final_checks.json
[mathchk]: ../longform/pythagoras_case_study/checks/math_checks.json
[geomchk]: ../longform/pythagoras_case_study/checks/render_geometry_checks.json
[durchk]: ../longform/pythagoras_case_study/checks/chapter_duration_checks.json
[audiorep]: ../longform/pythagoras_case_study/audio_report.json
[editorial]: ../longform/pythagoras_case_study/editorial_changes.json
[teachers]: ../longform/pythagoras_case_study/research/teacher_comparison.md
[evalp]: ../project/04_evaluation_protocol.md
[minutes]: ../project/01_meeting_minutes.md
[ws1]: ../project/workstreams/01_curriculum_and_teacher_evidence.md
[ws2]: ../project/workstreams/02_scripts_and_instructional_design.md
[ws3]: ../project/workstreams/03_code_to_video_and_narration.md
[ws4]: ../project/workstreams/04_science_and_biology.md
[ws5]: ../project/workstreams/05_problem_generation.md
[ws6]: ../project/workstreams/06_student_feedback.md
