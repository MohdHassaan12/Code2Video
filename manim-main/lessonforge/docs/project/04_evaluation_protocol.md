# Evaluation protocol for lessons generation and feedback

Assess correctness first, instructional usefulness second, and production efficiency alongside both. The numerical thresholds here are proposed initial engineering gates; they require calibration with reviewers and the school before becoming release policy.

## Separate four evaluation questions

| Question | Unit of analysis | Suitable evidence |
| --- | --- | --- |
| Can the pipeline produce a valid artifact? | Generation attempt and scene | Build logs, runtime checks, final media |
| Does the artifact teach the intended concept accurately? | Claim, teaching point, and lesson | Independent subject review and visual inspection |
| Does the student learn and transfer it? | Learner and assessment item | Pre-check, unassisted post-check, delayed and transfer tasks |
| Can the team produce and maintain it affordably? | Accepted lesson and revision | All-attempt cost and human labor |

## Technical experiment

Use the same approved objective, narration, notation, target duration, and output settings across generation conditions. Keep prompts and budgets in the run record. Compare the conditions in the [Code2Video assessment](research/02_code2video_assessment.md). Conduct a within-topic comparison; do not rank methods by combining easy topics for one with hard topics for another.

Report first-pass render success, final acceptance rate, conceptual defects, visual defects, manual repair minutes, total latency, and total cost. Count every started generation in the relevant denominator. Publish both automated output quality and quality after manual repair. A method with better final output but much more intervention may still be useful, but that tradeoff must be visible.

Use a separate set of topics after tuning prompts. Treat three runs per condition as an engineering stress check, not a statistically strong general ranking.

## Reviewer rubric

Score each dimension from 0 to 4: 0 unusable, 1 major revision, 2 mixed, 3 acceptable with minor corrections, 4 strong. Reviewers should provide the scene or sentence behind each low score.

| Dimension | What reviewers inspect |
| --- | --- |
| Conceptual accuracy | Definitions, assumptions, reasoning, causal claims, units |
| Visual truthfulness | Graphs, labels, transformations, containment, intermediate states |
| Explanatory clarity | Why each step follows; connection between representation and rule |
| Pacing and readability | Reading time, notation size, competing movements, pauses |
| Audio alignment | Spoken symbols, pronunciation, visual timing, captions |
| Assessment alignment | Coverage of objectives, valid solutions, meaningful transfer |

Proposed internal gate: no unresolved critical error and at least 3 in every dimension after correction. Do not turn this into a weighted average that hides a false concept. Two independent reviewers should adjudicate disagreements and retain original scores.

## Defect severity

- **Critical:** wrong mathematical or scientific claim, incorrect answer key, misleading essential visual, or feedback that teaches an incorrect rule. Blocks acceptance.
- **Major:** unreadable essential label, missing reasoning, narration contradicting the displayed step, or feedback tied to the wrong submission. Requires correction.
- **Minor:** cosmetic issue that does not change meaning or obstruct comprehension. Track and prioritize.

## Feedback evaluation set

Proposed starting set: 30 teacher-labeled attempts across three topics. Include correct conventional work, valid alternative work, common misconceptions, incomplete reasoning, and ambiguous images. Label both reading accuracy and the earliest supported error. Keep a held-out subset out of prompt development.

Measure:

- Transcription accuracy on symbols that affect the answer.
- Diagnosis precision: correct diagnoses divided by all error diagnoses issued.
- Coverage: attempts receiving a supported diagnosis or confirmation divided by all attempts.
- Clarification quality on ambiguous inputs.
- Correct recognition of alternative solutions.
- Hint usefulness and premature answer disclosure, judged independently.
- Visual localization accuracy when highlights are shown.

Report counts as well as percentages. An abstaining system can have high precision and low usefulness; a low-error score must be interpreted alongside coverage. Do not use this small set to claim deployment-wide reliability.

## Learner pilot

Begin with approximately 6–12 pupils for formative observation, including varied prerequisites. This proposed size is intended to reveal usability and explanation defects, not to establish an effect size. Obtain the school's appropriate participation arrangements before collecting real pupil work.

Give a short prerequisite check, the lesson, three independent tasks, and a brief interview. Ask the learner to explain a concept or reject an incorrect rule. Observe whether optional context helps or distracts. Record the amount of assistance received.

For a later comparison, use matched static and animated lessons with the same narration and practice. Counterbalance topic and order if pupils see both formats. Use equivalent assessment forms to reduce answer memorization. Add a delayed check around one week later, with timing recorded. Report missing data and whether assistance was allowed.

The [Bastani study](https://hamsabastani.github.io/education_llm.pdf) is a reason to measure unassisted performance separately from success while using a tutor. This proposed pilot should answer its own local question rather than attempt to inherit results from another population.

## School release decision

Record the accepted lesson versions, unresolved issues, reviewer approvals, device checks, teacher-support process, and school acceptance. The meeting requires one school's positive validation before public launch. A favorable small pilot justifies a controlled next step; broader learning claims require a stronger study with a prespecified analysis and adequate sample.

## Result table template

| Lesson version and condition | Started attempts | Accepted lessons | Critical defects before repair | Human minutes | Total cost and currency | Unassisted outcome | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| To be measured | — | — | — | — | — | — | Pending |
