# Scope and delivery plan

Deliver a complete teaching experience on a small number of concepts before expanding the content catalogue. The immediate review should make script quality, visual accuracy, and student practice inspectable. The following sequencing and estimates are proposed planning choices.

## Scope by milestone

| Milestone | Included | Deferred | Evidence required |
| --- | --- | --- | --- |
| Review on the 9th | One common math script implemented by both Manideep and Durgesh; science and biology script drafts; five verified math problems; one feedback example | Broad curriculum coverage, personalized generation, school-wide release | Script, source notes, playable video per implementer, source code, answer key, defect log |
| Small internal pilot | Three accepted lessons across math, physics, and biology; narration and captions; typed feedback and a supervised image-upload trial | Automatic high-stakes grading and unrestricted tutoring | Teacher sign-off and structured learner observations |
| One-school pilot | Approved lesson subset, support route, usage and learning measures, release rollback | General public rollout | School acceptance and recorded defect resolution |
| Expansion | Additional lessons, reusable scene templates, supported and advanced variants | Automatic curriculum-wide generation until error rates are understood | Repeatable quality and measured production cost |

The common lesson allows a fair technical comparison; the meeting did not prescribe using the same topic. Science and biology script coverage should appear in the first review even if their videos are scheduled next. If time permits, the second implementer may also demonstrate one science scene.

## Definition of a complete lesson

Each lesson package has an objective, prerequisite check, curriculum reference, source observation notes, reviewed narration, a timed storyboard, a notation and units table, renderable code, licensed assets, video, captions, five problems, separate answer key, hint ladders, and a review log. A content revision invalidates affected questions and scenes until they are checked again.

## Workstream dependencies

| Workstream | Starts with | Produces | Suggested accountable role |
| --- | --- | --- | --- |
| 1 Curriculum and evidence | Topic and target class | Verified brief and teaching observations | Content lead, to be named |
| 2 Script design | Brief | Approved script and storyboard | Subject author and independent teacher |
| 3 Code to video | Approved storyboard | Video, captions, code, build record | Manideep and Durgesh |
| 4 Science representations | Subject brief and diagram plan | Verified diagrams and dynamics | Science and biology authors, to be named |
| 5 Assessment | Approved objectives and script | Two worked and three independent problems | Subject author with separate verifier |
| 6 Feedback | Verified question and student attempt | Localized diagnosis or clarification plus hint | Proposed Durgesh lead; confirm allocation |
| 7 Validation | Accepted lesson packages | Pilot report and release decision | Proposed QA coordinator and school liaison |

## Suggested two-day work sequence

This is an effort allocation for a demonstration, not a claim that every subsystem can be completed within two days. Calendarize it after confirming the review date and capacity.

| Window | Content contributors | Manideep and Durgesh | Review result |
| --- | --- | --- | --- |
| Day 1 morning | Select common math topic; compare three teaching approaches; draft science and biology briefs | Verify renderer setup; build a short exact-geometry scene | Agreed concept, constraints, and functioning renderer |
| Day 1 afternoon | Finish script, storyboard, questions, and answer key | Implement common lesson independently or with a documented responsibility split | Freeze reviewed script and scene plan |
| Day 2 morning | Check explanations, diagrams, solutions, and spoken notation | Render; correct defects; align audio; add captions | Playable complete lesson and correction log |
| Day 2 afternoon | Teacher review and rehearsal | Demonstrate five-problem flow and one feedback case | Review bundle with remaining defects and next decisions |

If a component cannot pass review, show the failed case and repair estimate. Keep the lesson complete by using a manually authored scene or prerecorded narration. A working baseline is useful evidence even when automation fails.

## Acceptance gates

- **Script:** correct claims and assumptions; objective visible; a misconception addressed; teacher reviewer named.
- **Video:** follows approved script; exact figures and equations; no unreadable critical labels; narration and captions agree; at most 15 minutes.
- **Practice:** exactly five problems for the meeting demonstration; two worked; three independent; all five independently verified.
- **Feedback:** distinguishes a reading problem from a reasoning error; points to evidence; gives a useful next step.
- **Pilot:** no unresolved critical teaching errors; school partner accepts the proposed limited use.

## Main risks and responses

| Risk | Observable trigger | Response |
| --- | --- | --- |
| Missing content ownership | Engineer receives topic name without script | Require the brief and storyboard handoff |
| Visual correctness failure | Equation, graph, or diagram disagrees with narration | Stop that scene; use deterministic primitives and review rendered frames |
| Excessive repair time | Scene exceeds two automated repair rounds | Switch to manual edit and record effort |
| Curriculum mismatch | Reviewer disagrees with required prerequisites | Resolve against the school's actual edition before approval |
| Attractive but ineffective lesson | Learners like the video but cannot solve a transfer problem | Revise explanation and practice sequence |
| Overloaded short deadline | No complete render halfway through Day 2 | Finish the common math package; retain other subjects as reviewed script drafts |

## Proposed measures of progress

Count accepted lesson packages, open critical defects, reviewer minutes, and total cost per accepted minute of video. Track hours spent as a capacity measure, but do not substitute hours or video count for accepted quality. Report failed attempts as part of the production cost.
