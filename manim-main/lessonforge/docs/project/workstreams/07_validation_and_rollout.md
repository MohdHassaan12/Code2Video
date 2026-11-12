# Validation and school rollout

Require evidence of teaching quality before broad release. The meeting's minimum condition is positive validation from at least one school; the plan below defines evidence that can make that decision meaningful.

## Scope and formal task

Evaluate a lesson package across correctness C, clarity V, learning L, usability U, and total production cost K. Treat critical correctness failures as disqualifying. Do not allow high aesthetics or low cost to compensate for a false concept.

The internal demonstration, small school pilot, and general release are separate milestones. This document proposes decision criteria; it does not grant release approval.

## Literature implications

[Tutor CoPilot](https://arxiv.org/abs/2410.03017v2) supports evaluating assistance in the human teaching workflow it actually serves. [Bastani et al.](https://hamsabastani.github.io/education_llm.pdf) motivates distinguishing assisted performance from unassisted learning. These sources support the choice of outcomes, not a prediction of this product's effect size.

## Proposed approach

First, two reviewers independently inspect claims, equations, diagrams, narration, and answer keys. Resolve disagreements before student exposure. Ask an experienced teacher and a strong student whether the lesson is accurate and worthwhile, reflecting the meeting's quality bar.

Next, observe a small group with varied prerequisites. Use a short pre-check, the lesson, independent tasks, and a brief explanation in the student's own words. Note where pupils pause, replay, skip, ask for help, or misinterpret a visual. These behaviors are useful evidence for revision.

For a later comparative study, use matched content and assessment, record prior knowledge, and counterbalance conditions where feasible. Include an unassisted transfer question and a delayed check. If using classroom-level allocation, analyze at the appropriate clustered level. Choose sample size from a stated precision or power objective before claiming efficacy.

## Launch evidence

| Gate | Required evidence |
| --- | --- |
| Content ready | Reviewed script and answer key; all critical defects closed |
| Media ready | Full playback reviewed on intended devices; captions and audio checked |
| Feedback ready | Clear handling of ambiguous and alternative attempts; teacher fallback |
| Pilot ready | Named school, agreed lesson subset, support owner, and data-handling process |
| Release ready | Recorded school acceptance, pilot findings, corrections, and rollback owner |

Use participant identifiers in logs and collect only the student work needed for evaluation. Let the school establish applicable permission and retention arrangements before a real pilot. The present documentation contains no student dataset.

## Deliverables and acceptance

Deliver reviewer rubrics, issue tracker, observation protocol, de-identified results, school acceptance record, and a release decision. A school endorsement is a launch condition from the meeting, not proof of general effectiveness.

Suggested owners: QA coordinator and school liaison, both to be named. Dependencies: completed lesson and practice packages. Track critical defects, independent task performance, supported versus unassisted performance, teacher interventions, and accepted-production cost. Use the [evaluation protocol](../04_evaluation_protocol.md) for operational details.

The largest risks are selecting only enthusiastic or high-performing learners, confusing satisfaction with learning, and shipping a polished video before checking its questions and feedback.
