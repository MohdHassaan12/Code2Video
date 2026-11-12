# Visual Teaching Engine (module 12) — the owner's requirement and where it stands

Status: **live requirement** (the owner, 2026-10-20: "Add this module to your master project prompt ... It makes dynamic
visual teaching a core system requirement rather than an optional feature"). CLAUDE.md points here. Every change to
pictures, timing or questions is judged against this page; update the status table in the same pass.

## The requirement (the owner's text, kept whole in meaning)

**Mission.** The system must not only explain verbally or make static videos. A Visual Teaching Engine decides what
the learner sees, when, how visual elements change, and why each visual action supports the learning objective. The
goal is not more animation or complexity: it is abstract ideas made understandable through well-timed highlights,
annotations, diagrams, progressive construction, comparisons, motion, simulations and interactive explanations. It
integrates with the curriculum model, student model, pedagogical planner, conversation model and renderer.

**A. Visual planning.** Per learning objective: the concept or relationship; the best representation; what appears
first; what deserves attention; what is highlighted, labelled, connected, drawn, moved, revealed or removed; what the
learner should notice at each step; which actions coincide with narration; where the learner predicts, explains or
interacts; what visual evidence reveals a misunderstanding; which actions are left out because they teach nothing.
Actions are chosen for a teaching purpose, not style.

**B. A typed vocabulary of visual actions**, at least: highlight/outline; dim the irrelevant; point, pulse, focus;
labels and annotations; arrows, braces, connectors, paths; progressive reveal; equations and diagrams built step by
step; comparing representations; animated change of position, shape, state or quantity; transforming one
representation into another; correct and incorrect examples; counters, measurements, graphs, live simulation state;
pause for prediction or reflection; hints and explanations revealed progressively; revisiting an earlier state. Each
with purpose, valid targets, parameters, duration, prerequisites, accessibility requirements and validation rules.

**C. Selection policy.** Number line when spatial relations between numbers matter; progressive equation construction
when the order of reasoning matters; labelled diagrams for parts and relations; motion or simulation for change over
time or cause and effect; side by side for distinctions and misconceptions; table or graph for quantitative patterns;
physical or molecular models for things hard to picture. Do not force every concept into an animation: a static
diagram with one well-timed highlight may be better.

**D. Narration and visuals are planned together.** Each scene: id, objective, narration segments, visual states,
actions and targets, start and end conditions, sync markers, interaction points, expected learner evidence, branching,
accessibility descriptions, validation results. Sync on semantic events (a term introduced is highlighted; a
comparison spoken is shown; a prediction pauses and holds the relevant state until the learner answers or asks for a
hint), adjustable to speech and interaction. Nothing keeps changing while the learner must inspect a critical state.

**E. Architecture, separated:** conceptual scene spec; visual planning; asset retrieval or generation; animation spec;
rendering; audio-visual sync; interaction handling; automated validation. Deterministic components where correctness
matters (equations, graphs, atom counts, exact diagrams); generated or external assets only when validated for
suitability, licence and fact. One component library across React and React Native where practical; one semantic scene
renderable in a browser, an app or an exported video without duplicating the teaching logic.

**F. Learner-aware adaptation**, from evidence and with uncertainty, never from a "learning style": a targeted
highlight for a learner who misses the relevant term; labels and progressive relations for one who cannot read a
diagram; an alternative representation to test transfer once one is understood; a controlled side-by-side for two
confused ideas; no repeated demonstration of what is mastered; after a prediction error, a visual that tests the
competing explanations directly.

**G. Validators:** missing or invalid targets; wrong equations, labels, quantities, relations; narration contradicting
the picture; highlights of nonexistent elements; actions too early or too late; too many simultaneous changes; text
unreadable on a phone; poor contrast; overlapping annotations; wrong animation end states; inconsistent state across
scene transitions; interaction branches that cannot be completed; content revealed before a required prediction;
unsupported or fabricated detail. Validate from the structured data where possible, not only from screenshots.

**H. Evaluation** of learning, not of how dynamic a video looks: understanding, retention, transfer, explaining a
diagram, errors caused by visual confusion, time to understand, engagement (kept separate from learning),
accessibility, rendering reliability and sync accuracy. Compare a static explanation, a signalled static diagram and a
synchronized animated one. More movement is not assumed to be better.

**I. Required example: balancing chemical equations**, through the actual system: (1) the unbalanced equation;
(2) reactants and product; (3) atoms highlighted and counted on both sides; (4) the mismatch revealed; (5) the learner
predicts a correction; (6) their answer decides the next teaching action; (7) a correct coefficient change animated;
(8) atoms recounted and the equation verified; (9) the learner explains why subscripts stay unchanged; (10) a transfer
question on a different equation. With scene JSON, components, animation definitions, interaction logic, validation
rules and tests; scientifically correct.

## Where it stands (2026-10-20)

| Part | What exists | Where | Open |
|---|---|---|---|
| A planning | Storyboard per beat (narration, visual intent, events, anchors) + gate before speech; the visual plan per scene after narration | `longform/storyboard.py`, `longform/visual_actions.py` → `output/visual_plan.json` | the plan is DERIVED from the script; the writer does not yet choose actions by purpose from this vocabulary |
| B vocabulary | 16 typed actions with purpose, targets, params, seconds, needs, accessibility, and which code performs each | `visual_actions.ACTIONS` | `dim` exists only on the engine path |
| C selection | code-drawn figures for exact things (reaction, graph, number line, triangle, bars, and since 2026-10-20 `shape`: polygons from points with angles, equal/parallel marks, convex/concave/crossed verdicts and a moving corner, all computed from one coordinate model); the writer's figure rules; prepared drawings for anatomy/process | `writer.FIGURE_RULES`, `figures.py`, `geometry.py`, `shape_figure.py` | no explicit "which representation" policy table the writer is held to |
| D sync | steps wait for their heard words; reaction hints light atoms and counts as the voice names them; shape hints light the side, corner or angle the voice names (`shape_hints.py`); a question card pauses the player | `runtime`, `reaction_hints.py`, `interactions.json` | no hold-state rule enforced in code beyond pauses |
| E architecture | stages are separate files (spec, plan, storyboard, timeline, render, QA); deterministic figures where correctness matters | `docs/longform/storyboard-and-timeline.md` | web/mobile player reads `interactions.json` + video, not the scene plan |
| F adaptation | player ladder: retry with the option's own reason, then the answer and "watch that part again"; misconception tags; confidence | `Questions.tsx`, `service.write_interactions` | no student model choosing a different VISUAL after an error |
| G validators | layout probe, bounds, lateness, storyboard gate, frame review, scene checker; plan checks: unknown action, too many at once, answer shown before its question, unheard anchor | `qa.py`, `visual_actions.validate` | mobile readability and contrast are measured only in previews |
| H evaluation | narration/visual comparison with Khan Academy; motion share per half-second | `pilot/khan/compare.py` | no learning measurement (needs real learners) |
| I example | see below | | |
| J subject kits | a subject is one registered `KitBase` (pure model, figure drawn from it, gaps and claims checked by code, writer rules, shipped cases): geometry (legacy adapter), motion (speed-time graph), chemistry (`chem_reaction`, over the reaction figure), components (the lesson-visuals library, through Node); a lesson may mix subjects, each beat checked by its own kit; `harness/kit_pipeline.py` routes a brief to kits by code and runs write, check, repair, film under a cost cap; `LESSONFORGE_KITS` gates the seams | `kits/`, `longform/motion_math.py`, `longform/reaction_math.py`, `longform/component_lib.py`, `longform/kit_figures.py`, `harness/kit_pipeline.py`, `docs/engine/kits.md`, `docs/engine/kits-coverage.md` | mixed-subject lessons by per-beat ownership (`LESSONFORGE_KITS_MIXED`); geometry not yet routed through the registry; the loader does not read number states of the newer lesson-visuals contract; no real render through a kit yet |

### The chemistry example, step by step (lesson "Balancing Chemical Equations", the owner's script)

| Step | In the lesson | How |
|---|---|---|
| 1 unbalanced equation | beat 01 | `figures.reaction` from "H2 + O2 -> H2O" |
| 2 reactants and product | beat 01 | molecules as balls per atom, formula under each |
| 3 highlight and count | beats 01, 03, 07 | `reaction_hints`: balls light one by one as the voice counts, then the count cell |
| 4 mismatch | beat 01 | count table: before 2 O, after 1 O in red, verdict "not balanced yet" |
| 5 predict | beat 02 | question card "Which change is a chemist allowed to make?" |
| 6 answer decides next action | beat 02 card | wrong first tap: the option's reason and one more try; second: the answer, and "watch that part again" seeks back |
| 7 coefficient change animated | beats 03→04, 07→08 | `figures.reaction_change`: a new molecule grows out of the one there |
| 8 recount, verify | same | each changed count rolls over to its new number, the verdict changes to "balanced" |
| 9 explain why subscripts stay | NOT in the script | the owner's script states it (beat 06) but asks nothing; a card there needs words that ask |
| 10 transfer question | beat 09 (ammonia) | a card made by code: "What number goes in front of NH3?", options and reasons worked out by `figure_math.balance` |
