# Chapter 4 — A Reference Architecture for Autonomous Educational Video Generation

Everything before this chapter built the evidence that direct LLM-to-code generation is
architecturally insufficient for educational video. This chapter presents the
constructive answer:

> If we were designing NotebookLM, an AI 3Blue1Brown, or the next generation of
> educational video systems from scratch, what would the architecture look like?

## 4.1 Design Philosophy

The central thesis of this work is that educational video generation is **not a code
generation problem**. It is a **hierarchical planning problem** spanning several domains
of reasoning — pedagogy, visual storytelling, spatial geometry, motion design — each
operating at a different level of abstraction, and each with different tolerance for
error. Asking a single model to solve all of them simultaneously, in one pass, in the
syntax of a rendering library, is why the failure classes catalogued in Chapter 3 are
systemic rather than incidental: layout collisions, absent visual hierarchy, static
composition, and objects that never leave the screen are not code bugs. They are
planning decisions that were never made.

Two mature engineering disciplines already solve problems of this shape:

- **Animation studios** never begin with rendering. A production advances through
  treatment → storyboard → layout → animatic → animation → compositing, and each
  department consumes a *reviewed artifact* from the previous one. No animator invents
  the camera plan.
- **Compilers** never translate a high-level language directly to machine code. They
  lower the program through typed intermediate representations (IRs), run verification
  and optimization passes over each, and report errors against the representation where
  the error actually lives — a type error is reported against the AST, not against the
  emitted assembly.

The proposed architecture applies both analogies literally. Instead of

```text
Topic ──▶ LLM ──▶ Manim code ──▶ Video
```

we propose the pipeline of Figure 4.1, in which an educational goal is *progressively
lowered* through a sequence of typed, individually-validated representations, and
**exactly one stage emits Python**.

```text
Educational Goal
      │
      ▼
 Learning Planner          (reason)     learning plan
      │
      ▼
 Storyboard Planner        (reason)     storyboard
      │
      ▼
 Visual Director           (reason)     composition annotations
      │
      ▼
 Component Retriever       (retrieve)   component bindings
      │
      ▼
 Layout Solver             (solve)      layout graph
      │
      ▼
 Animation Planner         (solve*)     timeline graph
      │
      ▼
 Scene DSL Assembler       (solve)      Scene DSL          ◀────────┐
      │                                                             │
      ▼                                                             │
 Compiler                  (solve)      renderer code               │
      │                                                             │
      ▼                                                             │
 Renderer                  (execute)    frames + video              │
      │                                                             │
      ▼                                                             │
 Static Validator          (solve)      geometry report             │
      │                                                             │
      ▼                                                             │
 Vision Critic             (reason)     perceptual critique         │
      │                                                             │
      ▼                                                             │
 Repair Planner            (reason)     patch, applied at the ──────┘
                                        highest responsible IR
```

*Figure 4.1 — The reference pipeline. Each stage is labeled with its reasoning class
(§4.2). The repair edge re-enters the pipeline at whichever representation owns the
defect, never at the generated code. (\*) The Animation Planner is deterministic by
default with a reasoning override; see §4.5.*

The consequence worth stating immediately: in this architecture, **hallucination is
confined by construction**. A stage can only hallucinate within its own output type —
the Learning Planner can propose a poor teaching sequence, but it *cannot* produce an
overlapping layout, because layout is not predicted by any model at all.

## 4.2 The Determinism Boundary

A naïve reading of "multi-agent pipeline" replaces one large prompt with eleven small
ones. That preserves the original disease: if a *Layout Agent* predicts coordinates,
layout is still guessed, merely by a more specialized guesser. The single most important
design decision in this architecture is therefore not the decomposition itself but the
**determinism boundary**: an explicit classification of every stage into one of three
reasoning classes, with a hard rule about which class is allowed to answer which kind of
question.

| Class | Mechanism | Answers questions of… | Allowed to touch geometry? |
|---|---|---|---|
| **Reason (R)** | LLM / VLM | intent, pedagogy, narrative, emphasis, critique | **Never** |
| **Solve (S)** | deterministic code: constraint solvers, rule maps, compilers | position, size, timing, code emission, geometric verification | Always — it is the *only* class that may |
| **Retrieve (V)** | indexed lookup over curated libraries | "does a vetted implementation already exist?" | Only vetted, pre-validated assets |

The governing rule is:

> **The LLM never emits geometry.** Models decide *what* and *why*; code decides
> *where*, *when*, and *how big*. Every number that positions, scales, or times an
> object on screen is computed by a solver from declared relationships, or copied from
> a retrieved component — never sampled from a language model.

This rule is not aspirational; it is the empirical result of the reference
implementation accompanying this thesis. Every geometry decision that was migrated from
the model to a solver eliminated its failure class outright — data-space coordinate
mapping removed off-grid points, axes-aware zone claiming removed axis-through-text
collisions (measured 4 → 0 violations on the regression fixture), and computed label
slots removed tick-label occlusion — while no amount of prompt refinement had removed
any of them reliably. Prompting reduces the *rate* of a geometric error; moving the
decision across the determinism boundary removes its *possibility*.

The boundary also explains two deliberate asymmetries in Figure 4.1. The **Compiler is a
solver, not an agent**: DSL-to-Python translation is mechanical, and making it a model
reintroduces syntax hallucination at the exact point the architecture exists to protect.
And the **Vision Critic is a reasoner that is only trusted to *describe*, never to
*fix***: its output is a critique report handed to the Repair Planner, not edited code —
perception and correction are separated for the same reason detection and repair are
separate passes in a compiler.

## 4.3 Architectural Principles

Eight principles govern the design. Each is stated with the failure class it exists to
prevent — every one of which was observed in the systems analyzed in Chapter 3.

**P1 — Separation of concerns.** Each stage answers exactly one class of question. The
Learning Planner never chooses a font size; the Layout Solver never chooses a teaching
strategy. *Prevents:* the entangled mega-prompt in which improving pedagogy degrades
layout and vice versa, because both compete for the same finite attention budget.

**P2 — Typed intermediate representations.** Every stage boundary is a schema-validated
artifact (learning plan, storyboard, layout graph, timeline graph, Scene DSL). Each IR
can be independently validated, visualized, diffed, cached, and repaired. *Prevents:*
the all-or-nothing property of direct generation, where the only inspectable artifact is
final Python and the only possible retry is total regeneration. Caching is not
incidental economics: because artifacts are immutable and content-addressed, an edit to
any stage invalidates only *downstream* IRs, so iteration cost is proportional to the
depth of the change, not to pipeline length — and in generation-scale systems the
dominant costs (speech synthesis, rendering, model calls) are precisely the cacheable
ones.

**P3 — Declarative intent.** Upstream stages state *what should happen*
(`show: circle, importance: primary, entrance: emphatic`), never *how to call the
renderer* (`self.play(FadeIn(circle))`). The Compiler owns the mapping from intent to
API, in one audited place. *Prevents:* hallucinated API usage (`GrowFromBottom`,
invalid `Angle` kwargs) and monotone animation vocabulary — the intent-to-animation map
is code, so widening it is a table edit, not a prompt renegotiation.

**P4 — Layout is solved, not predicted.** Spatial arrangement is expressed as
relationships and constraints (`label RIGHT_OF point, margin 0.2, never overlapping`)
and lowered to coordinates by a constraint solver over safe zones, margins, and
occupancy. *Prevents:* the entire overlap/clipping/collision family — the largest
single defect class measured in Chapter 3 — by making it inexpressible rather than
merely discouraged.

**P5 — Components are retrieved, not regenerated.** Recurring educational objects
(coordinate planes, graphs, molecules, circuits, timelines, matrices) live in a
versioned, parameterized, individually-tested component library. Generation is the
fallback for the tail, not the default for the head. *Prevents:* re-deriving (and
re-breaking) a coordinate plane in every video; converts recurring quality from a
per-run gamble into an accumulating asset.

**P6 — Rendering begins verification; it does not end the pipeline.** Every render
passes through layered verification — cheap deterministic geometry checks first, then
perceptual critique by a vision-language model — before a video is considered produced.
*Prevents:* the silent-failure property in which a structurally valid but visually
broken video ships because nothing ever *looked* at it.

**P7 — Educational constraints are explicit objectives.** Cognitive-load limits
(concurrent-element budgets), pacing (grade-indexed narration rate, pauses after
reveals), emphasis (exactly one primary focus per beat), and coherence (terminology
stability across scenes) are machine-checkable constraints attached to the storyboard
and timeline IRs — not qualities the model is assumed to possess implicitly. *Prevents:*
information-dump scenes that are geometrically clean yet pedagogically broken, which no
purely visual verifier can catch.

**P8 — Closed-loop refinement with monotone quality.** Verification feeds repair;
repair re-enters the pipeline; the loop iterates. Two sub-rules make the loop safe
rather than churning. *Accept-if-better:* a repaired artifact replaces its predecessor
only if it verifiably improves the measured defect count; otherwise the predecessor is
kept. *Never lose a verified artifact:* the best-so-far video is never discarded until
a strictly better one exists. Together they make quality monotone in repair effort.
*Prevents:* repair loops that oscillate, regress, or destroy a good render while
chasing a marginal one — all observed behaviors of unguarded self-repair.

Three of these principles (P4, P6, P8) are validated directly by the reference
implementation's measurements; the remainder are grounded in the compiler and animation-
production analogies and in the failure analysis of Chapter 3.

## 4.4 Layered Architecture

The stages of Figure 4.1 group into six layers with strictly narrowing concerns. The
layer boundary is also the *competence* boundary: each layer may be implemented,
evaluated, and upgraded independently — a better constraint solver improves Layer 4
without retraining or re-prompting anything in Layers 1–2.

**Layer 1 — Educational intelligence** *(reason).* Input: topic, audience, grade,
source material. Output: learning objectives, known misconceptions, worked examples,
teaching strategy. One grounding rule is absolute: facts, numbers, and named entities
must come from the source material, never be invented — and fidelity is spot-checked
downstream (P6 applies to *content*, not only pixels).

**Layer 2 — Visual planning** *(reason).* Converts pedagogy into visual storytelling:
scene sequence, narration, per-scene focus, composition strategy, camera language,
object lifetimes, visual hierarchy. No code, no coordinates — importance ranks and
relationships only.

**Layer 3 — Scene representation** *(solve + retrieve).* The planning layers' declared
intent is lowered into the **Scene DSL** (Chapter 5): objects bound to library
components, relations resolved to a layout graph, intent resolved to a timeline graph,
plus camera plan, constraints, and voice cues. This is the architectural midpoint —
everything above it is renderer-independent reasoning; everything below it is
renderer-specific mechanics.

**Layer 4 — Compilation** *(solve).* Scene DSL → renderer code. Python appears here
and only here. Because the input is a validated IR rather than free text, compilation
is total and deterministic: the same DSL always yields the same code.

**Layer 5 — Rendering** *(execute).* Pure execution under resource limits (timeouts,
sandboxing, artifact hygiene). No reasoning of any kind.

**Layer 6 — Verification and repair** *(solve, then reason).* Deterministic geometry
validation, perceptual critique, educational review, and the repair loop of §4.6.

## 4.5 Stage Decomposition

Table 4.1 specifies every stage with its reasoning class and input/output contract.
Contracts are the load-bearing element: because each interface is a schema, any stage
can be swapped — a different model, a better solver, even a human editor — without its
neighbors noticing.

*Table 4.1 — Pipeline stages. R = reason (LLM/VLM), S = solve (deterministic),
V = retrieve.*

| # | Stage | Class | Consumes → Produces | The one question it answers |
|---|---|---|---|---|
| 1 | Learning Planner | R | goal → learning plan | What must the learner understand, and what will they get wrong? |
| 2 | Storyboard Planner | R | learning plan → storyboard | What sequence of scenes teaches it? |
| 3 | Visual Director | R | storyboard → composition annotations | How is each scene staged — focus, hierarchy, camera, lifetimes? |
| 4 | Component Retriever | V | storyboard → component bindings | Does a vetted implementation of this object already exist? |
| 5 | Layout Solver | S | objects + relations → layout graph | Where does everything go? |
| 6 | Animation Planner | S* | annotations + narration → timeline graph | When does everything move, and how? |
| 7 | Scene DSL Assembler | S | all above → Scene DSL | One validated artifact describing the whole video |
| 8 | Compiler | S | Scene DSL → renderer code | Mechanical translation, nothing else |
| 9 | Renderer | — | code → frames + video | Execution |
| 10 | Static Validator | S | frames/geometry → violation report | Is anything measurably broken (overlap, clipping, occlusion)? |
| 11 | Vision Critic | R | sampled frames → critique report | Would a human reviewer object to what this *looks* like? |
| 12 | Repair Planner | R | reports + IR stack → targeted patch | Which representation owns this defect, and what is the minimal fix? |

Four stages deserve elaboration beyond the table.

**The Visual Director (stage 3)** is the least obvious and, after layout solving, the
highest-leverage addition. It is the film-director role: for each scene it decides the
composition strategy (centered, split-screen, timeline, focus-object), assigns every
element a hierarchy rank (primary / secondary / tertiary — later mapped by the solver
to size, weight, and z-order tiers), plans each object's lifetime
(birth → active → inactive → destroy, so nothing lingers), and scripts camera and
emphasis language (zoom, pan, dim-unrelated, spotlight) synchronized to narration
beats. Chapter 3 showed that systems without this role produce videos that are
geometrically clean yet visually dead: everything equally sized, statically framed,
accumulating forever. Crucially, the Director only *annotates* the storyboard —
its output is ranks and intents, which downstream solvers make geometric, preserving
the determinism boundary.

**The Animation Planner (stage 6)** is deliberately hybrid, marked S\*. Its default
path is a deterministic mapping from element type and semantic keyword to entrance,
transformation, and exit templates, with timing computed against measured narration
duration — the reference implementation demonstrates that such a map produces diverse,
idiomatic motion (grow-arrow for arrows, draw-then-fill for closed shapes, write for
mathematics) with zero hallucination risk. A reasoning override may *select among*
registered templates for expressive intent, but may not invent animation calls: the
vocabulary itself lives in code.

**Verification is layered on cost (stages 10–11).** The Static Validator is
deterministic geometry analysis — bounding-box overlap, frame-boundary clipping,
stroke-path-through-text occlusion, measured after every animation beat, not only on
final frames (mid-scene pile-ups are invisible to end-state checks). It is fast, free,
and runs on every render. The Vision Critic is expensive and perceptual, so it runs on
sampled frames and answers only what geometry cannot: crowding, dead space, contrast,
readability, hierarchy legibility, narration-visual mismatch. Running the cheap
deterministic pass first is what makes closed-loop verification economically viable at
generation scale.

**The Repair Planner (stage 12)** is a reasoner operating under the two P8 safety
rules and under the routing discipline of §4.6. It produces *patches to
representations*, never patches to Python.

## 4.6 Information Flow and the Highest-Level Repair Rule

Information flows in exactly two directions. **Downward**, as immutable structured
artifacts: each stage consumes validated IRs and produces one. **Upward**, as
critiques: verification reports that name defects but change nothing.

Every IR boundary is also a **gate**: an artifact that fails schema or completeness
validation is rejected *at that boundary*, loudly, before anything downstream spends on
it. This matters more than it appears. Generation-scale systems lean on lenient parsing
to survive imperfect model output, and a lenient parser converts a *truncated* response
into a *structurally valid but gutted* one — the reference implementation observed a
truncated storyboard ship as a well-formed three-second video, with no error in any
log, precisely because parsing succeeded and nothing else checked completeness. The
rule that follows: **a parser proves syntax; only a gate proves an artifact**. Every
IR gets both.

Repair is governed by a single routing discipline, which we state as the architecture's
third named rule:

> **The Highest-Level Repair Rule.** A defect is repaired at the highest
> representation that can causally resolve it; all artifacts downstream of the patch
> are regenerated mechanically; no stage ever edits an artifact more than one level
> below its own output.

Concretely:

| Observed defect | Patched representation | Never patched |
|---|---|---|
| Text overlaps a diagram | layout graph (relation/margin) | the generated Python |
| Animation outruns narration | timeline graph | the render call's `run_time` |
| A scene lacks emphasis | storyboard / Director annotations | the compiled scene |
| Wrong fact in narration | learning plan (against source) | the voiceover string |

The rule has three consequences that jointly distinguish this loop from naïve
self-repair. First, **fixes generalize**: a margin corrected in the layout graph is
enforced by the solver in every future scene, whereas a nudged coordinate in Python
fixes one frame once. Second, **the pipeline stays deterministic**: regeneration below
a patch is solver work, so the repaired video differs from the original only in the
repaired respect — no collateral drift. Third, **patches cannot accumulate as
sediment**: since code is always regenerated and never edited, the emitted Python
remains a pure function of the DSL, and the DSL a pure function of the plans. Combined
with accept-if-better and never-lose-a-verified-artifact (P8), the repair loop is
convergent, monotone, and auditable — every accepted repair leaves a diff at exactly
one IR.

## 4.7 What Is Genuinely Different

Measured against the direct-generation systems analyzed in Chapter 3 — and against the
first generation of multi-agent wrappers that decompose the *prompt* without
decomposing the *problem* — this architecture makes four claims of novelty:

1. **A determinism boundary, stated and enforced** (§4.2): the classification of every
   stage as reason / solve / retrieve, with geometry, timing, and code emission placed
   entirely on the deterministic side. Decomposition without this boundary merely
   distributes hallucination; decomposition with it eliminates whole failure classes by
   construction.
2. **A compiler pipeline over typed, gated, cacheable IRs** (P2, §4.6): planning is
   finalized before programming begins; the Scene DSL is a renderer-independent
   midpoint, making the planning layers portable beyond Manim; every boundary is a
   validation gate, so truncation and degeneration fail loudly at their origin.
3. **Layered closed-loop quality assurance** (P6, P8): deterministic geometric
   verification on every render, perceptual VLM critique on sampled frames, and a
   repair loop made safe by accept-if-better and artifact preservation — rendering is
   the beginning of verification, not the end of the pipeline.
4. **The Highest-Level Repair Rule** (§4.6): defect attribution routed to the owning
   representation with mechanical regeneration below, yielding repairs that
   generalize, converge, and leave an audit trail — in contrast to code-patching
   loops, which repair instances rather than causes.

**Scope and limitations.** The architecture is a reference design, and honesty about
its boundaries strengthens the claim. It does not eliminate reasoning error in the
planning layers — a pedagogically weak learning plan compiles into a pedagogically weak
video, flawlessly; the Educational Reviewer mitigates but cannot guarantee. Its
component library thesis (P5) has a cold-start cost that direct generation does not
pay. Its economics depend on IR caching and layered verification; a deployment that
disables either inherits generation-scale costs. And the constraint vocabulary of the
Layout Solver bounds what the Visual Director can express — extending expressiveness
means extending the solver, which is deliberate (that is where the determinism boundary
puts the burden) but is real engineering. These are the costs of moving structure from
models into code; the thesis of this chapter is that for educational video, the
exchange is decisively favorable.

## Transition to Chapter 5

This chapter fixed the architecture: the stages, the determinism boundary between
reasoning and solving, the layered structure, and the repair discipline that makes the
closed loop safe. Everything now depends on the artifact at the architectural
midpoint. Chapter 5 specifies the **Scene Domain-Specific Language** — the object
model, relations, constraints, timeline and camera semantics, animation primitives,
and validation rules that make the pipeline modular, verifiable, and
renderer-independent. The DSL is the load-bearing contract of the architecture: it is
simultaneously the last artifact the reasoning layers may touch and the only input the
deterministic layers will accept.
