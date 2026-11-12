# System architecture for reviewed educational lessons

**Scope update:** The [narration-led long-form approach](08_narration_led_long_form_approach.md) extends this design with whole-lesson continuity, measured speech anchors, and temporal overlap checks. Follow that document where the designs differ.

Use one versioned lesson specification to connect content, video, practice, and feedback. Rendering and tutoring should share verified content while retaining separate checks and failure handling. This is a proposed architecture, not a description of the existing Concept Explorer implementation.

## Processing flow

```text
Curriculum and teaching evidence
          |
          v
Lesson brief -> Original script -> Subject review
                                      |
                           Approved lesson version
                            /                   \
                           v                     v
                 Scene contracts          Problem specifications
                       |                         |
                 Renderable code          Independent solutions
                       |                         |
             Semantic and visual checks   Verified answer keys
                       |                         |
              Audio and final video       Hints and rubrics
                       \                         /
                        v                       v
                         Reviewed lesson package
                                   |
                           Student lesson and practice
                                   |
                            Typed or image attempt
                                   |
                      Read -> Verify -> Diagnose -> Hint
                                   |
                          Teacher fallback when needed
                                   |
                      Pilot evidence and lesson revision
```

## Lesson contract

| Record | Required fields | Validation |
| --- | --- | --- |
| Lesson | ID, version, class, board, edition, language, objective, prerequisites, sources, reviewer status | Curriculum scope explicit; approval linked to exact version |
| Script | Narration, ordered scenes, glossary, assumptions, misconception targets | Every factual claim reviewed; notation consistent |
| Scene | ID, duration target, visual objects, narration cue, geometry/data, invariants, transition intent | References resolve; required objects and checks supplied |
| Asset | ID, path, author/source, permission status, checksum | Correct file and allowed use |
| Question | ID, objective, prompt, domain, solution, valid alternatives, hint ladder, mode | Independently solved and reviewed |
| Attempt | Problem version, learner pseudonym, submission type, transcription, step boundaries | Correct problem association; uncertain readings visible |
| Feedback | Diagnosis, evidence, first error when supported, hint, confidence basis, fallback | Consistent with rubric and attempt |
| Review | Reviewer, timestamp, version, defects, severity, disposition | No release with unresolved critical defects |

Store pedagogical intent separately from drawing coordinates. The same statement, such as “add the quantities of identical terms,” should survive a renderer or language change.

## Example scene contract

This illustrative JSON specifies data and review expectations. It is not executable code or a validated production schema.

```json
{
  "lesson_id": "math_like_terms",
  "lesson_version": "draft-1",
  "scene_id": "combine_equal_tiles",
  "duration_target_seconds": 50,
  "narration": "Two x-squared tiles and three x-squared tiles give five of the same tile.",
  "objects": [
    {"id": "left_tiles", "kind": "tile_group", "count": 2, "label": "x^2"},
    {"id": "right_tiles", "kind": "tile_group", "count": 3, "label": "x^2"},
    {"id": "result", "kind": "equation", "latex": "2x^2+3x^2=5x^2"}
  ],
  "assumptions": ["The area picture uses positive x as a length"],
  "invariants": [
    "There are five tiles after grouping",
    "Every tile retains the x^2 label",
    "No tile changes area during regrouping"
  ],
  "review_status": "pending"
}
```

The algebraic identity holds for all real x, but a literal area model uses nonnegative lengths and is clearest for positive x. State this distinction rather than using a physical analogy as proof for every domain.

## Build and review states

Use states draft, subject_review, approved_script, rendered_draft, media_review, accepted_internal, pilot_approved, and released. Store the person or process responsible for each transition. A render may be technically successful while remaining in rendered_draft because of a conceptual defect.

When a shared definition changes, mark its scenes, questions, and hints stale. When only layout changes, rerun visual checks and affected timing checks. When an answer key changes, review feedback examples before reuse. Keep prior accepted versions available for rollback.

## Minimal implementation boundaries

- **Authoring:** local lesson files and review records initially; no new content-management platform required for the prototype.
- **Rendering:** isolated scene worker, pinned dependencies, reproducible assets, and cached audio.
- **Verification:** mathematical checks plus explicit subject-review checklists; numerical checks do not replace domain reasoning.
- **Delivery:** video player, text problems, and a basic attempt submission path using the existing product only after its interfaces are inspected.
- **Feedback:** separate service or module that receives a verified rubric and a single attempt; it can request clarification.
- **Reporting:** build logs and review results tied to lesson versions.

## Observability and cost

For each production attempt, record model and prompt version, token usage where available, generation and render time, retries, asset source, manual edits, review time, and outcome. Keep secrets and student identities out of these logs.

Estimate cost per accepted lesson as:

`(model calls + speech + assets + compute + valued author/reviewer time for all attempts) / accepted lessons`

Report currency, rate date, and labor assumptions. If no lesson is accepted, report total expenditure and zero accepted lessons; do not divide by zero. Cache reuse should be reported separately so first-production and later revision costs remain interpretable.

## Existing product integration

Before integration, inspect the actual Concept Explorer APIs, lesson storage, playback, authentication, and upload handling. Those components were discussed in the meeting but are not present as a verified project in this workspace. Until then, define the interface contract and demonstrate the flow locally with sample attempts.
