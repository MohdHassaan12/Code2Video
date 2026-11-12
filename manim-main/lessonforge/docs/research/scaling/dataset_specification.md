# Initial dataset specification

Version 0.1 proposal, 6 October 2026. This defines collection and export rules for educational animation data. The existing prototype provides one candidate source family with nine scenes; no record has been exported as teacher-approved training data.

## Record types

Use `scene_generation`, `scene_repair`, `lesson_planning`, `preference_pair`, and `visual_review` as explicit task types. Keep lesson-level artifacts and scene records linked, but do not duplicate a lesson's code nine times and count those copies as independent examples.

Every record requires `record_id`, `source_family_id`, `parent_ids`, `task`, `input`, `target`, `artifact_refs`, `provenance`, `reviews`, `split`, and `eligibility`. Artifacts should have relative locations and SHA-256 hashes. Use null for unknown metadata; do not invent model identifiers, costs, teacher reviews, or failed-code snapshots.

## Input contract

For scene generation, include the actual reviewed script segment, objective, audience prerequisites, notation, mathematical domain, available component/API version, narration duration, and incoming scene state when relevant. The target is a complete scene specification or runnable code with dependencies included or identified.

For repair, add the failing output and actual observations: exception text, failed invariant, frame reference, or reviewer defect. A text-only model can receive a verified structured defect description. Raw frames require a model with image inputs or a separate visual analysis step.

Store an explicit export policy for prompts, assistant targets, and tool observations. Future verdicts remain in the metadata and never leak into ordinary-generation inputs.

## Independent review axes

Each axis has a status from `pending`, `passed`, `failed`, or `not_applicable`, with reviewer/tool ID, version, timestamp, and evidence.

| Axis | Meaning |
| --- | --- |
| Schema | Required objects and supported operations |
| Execution | Clean build and valid media |
| Semantics | Correct mathematical or scientific statements |
| Visual | Legible and accurate objects, labels, and transitions |
| Narration | Pronunciation, synchronization, and caption agreement |
| Pedagogy | Objective alignment, explanation, and prerequisite fit |
| Rights | Permitted source, asset, and teacher-output use for the intended training/release |

Training eligibility is explicit and task-specific. A technically valid scene with pedagogy pending can be retained as a candidate, but cannot silently become a gold instructional example. A failed scene may be an input to a repair task whose corrected target passes the required checks.

## Split policy

Assign source families before expansion. Keep paraphrases, coefficient substitutions, translations, inherited code variants, and repairs of the same authored example together. Connected parent/derivative relationships must not cross splits.

One proposed ordinary split is 70% training, 15% validation, and 15% test by source family, stratified by concept and representation where feasible. Add an explicitly held-out concept-family test and an unseen-composition test using supported primitives. Do not imply that a model can use an unavailable primitive without extending the renderer.

Generic shared renderer code is allowed across splits; derivative lesson examples are not. Deduplicate natural-language targets and normalized scene specifications, and inspect near-duplicate code beyond boilerplate. Freeze the final test before prompt and checker tuning. Newly discovered defects may improve training validators without repeatedly selecting a model on final-test results.

## Storage layout

```text
dataset_v001/
  manifest.json
  raw_attempts.jsonl
  curated_records.jsonl
  rejected_records.jsonl
  family_splits.json
  artifacts/<content_hash>/
  exports/scene_sft_train.jsonl
  exports/repair_sft_train.jsonl
  exports/preferences_train.jsonl
  evaluation/locked_tasks.jsonl
  reports/coverage_and_quality.json
```

This is a proposed layout, not an existing generated corpus. Raw and rejected records support debugging and provenance. Training exports contain only records explicitly eligible for that task and split.

## Collection priorities

Collect failures involving stale scene objects, label overlap, invalid equations, missing assumptions, narration timing, unreadable exponents, inconsistent symbols, unsupported API calls, and cross-scene continuity. Pair real failures with actual corrections. Deliberately constructed faults are useful tests but must be labeled synthetic injections rather than observed production errors.

Measure unique source families, unique concept families, representation coverage, accepted examples per task, human review coverage, rejection reasons, code/media reproducibility, and dataset length distributions. Raw JSONL row count is insufficient evidence of coverage.
