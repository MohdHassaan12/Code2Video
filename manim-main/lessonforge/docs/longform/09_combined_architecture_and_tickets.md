# Combined architecture and implementation assignments

Build a narration-led lesson compiler with an editable whole-lesson plan, persistent visual state, and independent checks. Integrate selected ideas from the research systems through common contracts rather than concatenating their prompts and agents. The [detailed method comparison](research/04_long_form_method_comparison.md) explains forty alternatives; the [code audit](research/05_paper_and_code_audit.md) identifies which release paths actually exist.

## Five end to end configurations to compare

| Configuration | Composition | What the experiment answers |
| --- | --- | --- |
| Direct strong model | One full script, direct scene code, standard render, human review | How much quality comes from the model alone? |
| Simple staged baseline | Manimator-style scene descriptions, code generation, explicit narration added | Does an intermediate visual plan justify extra calls? |
| Narration and retrieval | TheoremExplainAgent-style plans, narration, relevant implementation examples | Do separate planning artifacts and retrieval improve fidelity? |
| Code and visual repair | Code2Video-style planner, section coder, scoped repair and visual feedback, plus audio | Do repair and critique improve accepted quality enough to pay for themselves? |
| Proposed integrated system | Whole manuscript, teaching retrieval, shared state/events, audio anchors, reusable compiler, independent validators, scoped repair | Does explicit continuity and verification improve long lessons and local edits? |

Use the same approved scripts for code-only comparisons. For complete systems, record script quality separately because a better explanation can conceal a worse renderer. Compare complete lesson duration, semantic errors, overlap intervals, unwanted resets, review time, and cost per accepted lesson. Keep a fixed retry allowance and preserve failures. These are proposed configurations; the current small pilot does not reproduce these five systems.

## Shared artifacts

The system should maintain a small number of versioned artifacts:

- `lesson_brief`: audience, prerequisites, objectives, subject evidence, required misconceptions, language, approximate duration.
- `teaching_plan`: concept dependencies, running examples, notation, required inferences, section purposes, deliberate recaps.
- `narration`: complete spoken text, pronunciations, pauses, references to visual entities, measured audio assets and anchors.
- `visual_program`: persistent objects, parameter sources, visual events, start/end states, renderer/components and assets.
- `validation`: exact artifact versions, observed results, unresolved defects, review decisions and patch history.

Do not store the same mathematical value independently in several places. A line's slope parameter should drive its graph, equation label, slope triangle, and verbal value references. A subject check can still reject the selected parameter or interpretation, but this eliminates a common source of internal disagreement.

## Example contract for changing an intercept

This illustrative JSON specifies a beat, not a currently implemented compiler API:

```json
{
  "beat_id": "intercept_change",
  "requires_facts": ["intercept_is_y_at_zero", "slope_is_change_ratio"],
  "establishes_facts": ["changing_b_preserves_slope"],
  "state_in": {
    "axes_id": "main_axes",
    "axis_units": "equal",
    "line_id": "main_line",
    "parameters": {"m": 1, "b": 1},
    "visible": ["main_axes", "main_line", "equation", "intercept_marker"]
  },
  "speech": {
    "text": "Keep the slope at one. Now increase the intercept from one to two. Every point moves up by one, while the rise for each step right stays the same.",
    "anchors": ["increase the intercept", "Every point moves up", "stays the same"]
  },
  "events": [
    {"on": "increase the intercept", "operation": "animate_parameter", "target": "b", "from": 1, "to": 2, "minimum_seconds": 3},
    {"on": "Every point moves up", "operation": "show_displacement", "target": "main_line", "delta_y": 1},
    {"on": "stays the same", "operation": "highlight", "target": "slope_ratio"}
  ],
  "state_out": {
    "axes_id": "main_axes",
    "line_id": "main_line",
    "parameters": {"m": 1, "b": 2}
  },
  "checks": ["equation_matches_line", "intercept_label_matches_b", "triangle_on_current_line", "no_unintended_text_overlap", "caption_region_clear"]
}
```

The audio scheduler must resolve the anchors against actual speech and ensure enough time for the events. If an anchor is missing or two incompatible events need the same interval, fail the schedule and revise it. Do not guess timings silently. A complete schema also needs versioned state equality, asset hashes, object lifecycle, camera, and dependency information.

## Preventing the defects observed in the pilot

The live generated sample demonstrates why a shared specification matters. The line and equation changed to an intercept of 2 while a separate text label still said 1. Another sample displayed slope−1 while the line continued rising. Those are semantic synchronization defects, not merely ugly formatting.

Generate dependent labels from the same parameter source. Validate the line by evaluating several data points, not by reading its label. Validate the triangle endpoints against the current line and calculate signed rise/run independently. During animation, define whether labels display the current interpolated value, the destination value, or a clearly marked transition; do not leave that ambiguous.

For layout, maintain measured bounds in screen coordinates. A region assignment alone does not ensure fit. The compiler should expose positions, occupied regions, and object IDs for each event interval. Use constraint rules for placement and a temporal checker for motion. If text cannot fit at the minimum size, choose another arrangement or stage the reveal.

For duration, sum actual scheduled event durations and measure the rendered streams. Comments claiming “60 seconds” and section metadata claiming “20 minutes” are not checks. The pilot found both kinds of mismatch. Keep a single timebase, account for frame rounding, and verify joins after audio assembly.

## Scoped repair protocol

1. Classify the defect and capture reproducible evidence: artifact hashes, interval, objects, intended relation, observed relation, relevant frames and source region.
2. Try a deterministic parameter/layout/lifecycle correction when the cause is known.
3. Otherwise ask a model for a bounded specification or code patch, including invariants it must preserve.
4. Confirm that the patch changed the intended artifact. Reject no-op patches unless the diagnostic was independently shown to be false.
5. Rerender the affected interval and adjacent joins. Run the original violated check, semantic invariants, layout/timing checks, and selected visual review.
6. Accept, expand repair scope, or escalate. A finite retry budget prevents repeated plausible but ineffective fixes.

The pilot's repair request used diagnostics written after source and frame inspection. It is a measured diagnostic-guided repair example, not evidence of fully automatic fault detection. Production automation needs a labeled defect suite and measured detection/repair performance first.

## Data and distillation interfaces

Preserve four linked record types: whole-lesson planning, narration, visual production, and observed repair. Every scene record includes the whole-lesson summary, relevant concept dependencies, and starting state. Every repair includes the failing artifact and actual observation; do not train on a fabricated claim that a patch passed.

Keep teacher/source families together when splitting data, and add a held-out set of unseen concept combinations. Evaluate whole lessons separately from scene records. Ten scenes from one lesson are not ten independent teaching examples.

Begin with the untuned smaller model plus relevant component examples. Then use supervised fine-tuning, followed by student-failure collection and correction. Compare separate adapters for narration and code against a shared multi-task model only if sufficient data justify the experiment. Code and narration have different acceptance criteria and output structures.

Choose sequence lengths from the actual record distribution. Full scripts and plans may exceed short code-record budgets. Do not silently truncate a record's dependencies or target ending. Use shorter beat tasks for efficient training, plus genuine long-context examples for planning and continuity. Distillation must use source and model outputs permitted for that purpose; research pilot outputs are not automatically a training corpus.

Retain the existing Transformers, TRL, PEFT, Accelerate, and vLLM stack from the [framework handoff](07_frameworks_and_implementation_handoff.md). The six Blackwell GPUs require profiling before a specific parallelism plan is chosen. A30Bmixture-of-experts model's active-parameter count is not its full resident memory requirement.

## Assignments for implementation models

| Task | Inputs and deliverable | Acceptance criterion |
| --- | --- | --- |
| T1 Corpus contracts | Authorized teacher episodes; typed lesson/episode/move/correction schemas and annotation guide | Source lineage and explicit missing-data fields; sample reviewed against original teaching |
| T2 Script experiments | Fixed briefs, verified facts, example corpus; baseline, fixed-example and retrieved-example generation | Same budgets, preserved failures, whole-script review, no fabricated teacher scores |
| T3 Shared semantic state | Beat/state schema and parameter-driven graph components | Equation, line, marker and slope triangle agree at tested parameter values, including negatives and zero |
| T4 Audio schedule | Narration, pronunciation data and event anchors | Measured speech timing, explicit missing-anchor failures, preserved pauses, reviewed joins |
| T5 Temporal layout | Object registry, bounds, camera transforms and overlap rules | Precision/recall report on labeled moving and static defect fixtures, including valid intersections |
| T6 Repair executor | Diagnostics, artifact versions and patch contract | Real change detected, target defect removed, regression checks passed, failed patches retained |
| T7 Long lesson assembly | Accepted beats, state boundaries and audio | One complete lesson with consistent notation, no accidental reset, synchronized streams and reviewed content |
| T8 Cost and training baseline | Actual stage logs and reviewed exports | Cost per accepted lesson, reviewer time, learning curves and measured hardware profile |

Each assignment should return its changed files, runnable commands, observed results, unresolved defects, and cost where applicable. Use isolated environments for third-party research code. No generation stage should have access to unrelated workspace credentials. The live pilot runner keeps the OpenRouter key in process memory and records only prompts, outputs and accounting.

## Long form lesson seed

The [slope and intercept narration draft](examples/long_form_slope_script_draft.md) is a concrete starting manuscript generated in this session and edited for several clarity issues. The [production notes](examples/long_form_slope_production_notes.md) list the required visual states, timing questions, and remaining review tasks. It is not yet a narrated 20-minute video or teacher-approved lesson. Use it to exercise continuity and synchronization rather than substituting a chain of unrelated clips.
