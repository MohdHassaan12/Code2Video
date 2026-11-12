# Student work diagnosis and feedback

Give the student a specific next step based on their actual attempt. Separate uncertainty about reading the submission from confidence about its mathematics.

## Scope and formal task

Input: reviewed problem q, solution rubric r, attempt u, and attempt history h. Produce a transcription t, supported diagnosis d, evidence location e, confidence category c, and a hint a. Permit explicit outcomes correct, partially correct, misconception, needs clarification, and needs teacher review.

First implement typed responses. Next add image upload with transcription confirmation. Broad autonomous marking of arbitrary handwritten work is outside the initial scope.

## Literature implications

[DrawEduMath](https://arxiv.org/abs/2501.14877) motivates testing student-work interpretation separately. [MathDial](https://arxiv.org/abs/2305.14536) motivates teaching moves rather than immediate solution disclosure. [GeoDial](https://arxiv.org/abs/2606.12419) reinforces that useful feedback text and accurate visual highlighting are different capabilities. These benchmarks do not guarantee correct diagnosis in this product.

## Proposed approach

1. Confirm which problem the attempt answers. Check whether all needed steps are visible.
2. Extract symbols and step boundaries. If a crucial symbol is unclear, ask the learner to confirm it or provide a clearer crop.
3. Compare the attempt with the problem constraints and mathematical rules, allowing alternative solution paths.
4. Identify the earliest supported error, not an imagined missing step. A correct final answer with insufficient working may require a question rather than a claim of full reasoning mastery.
5. Return the relevant step and one focused hint. Ask the learner to revise that step.
6. If the learner remains stuck, increase support through a reminder, a representation, a partial worked step, and finally a full explanation when pedagogically appropriate.

Example: for 2x² + 3x², a submission of 5x⁴ can receive: “You added the coefficients correctly. Here we are adding two quantities of the same kind, x². Which rule changes the exponent: addition or multiplication?” Only point to an image region if that region has been reliably identified.

## Confidence and fallback

Do not use an uncalibrated model probability as a guarantee. Record whether a human confirmed the transcription, whether symbolic checks apply, and which evidence supports the diagnosis. Calibrate any automated confidence threshold on held-out, teacher-labeled attempts. When the system cannot support a diagnosis, ask for clarification or route it to a teacher.

## Deliverables and acceptance

For the first demonstration, show a correct answer, an exponent misconception, an alternative valid method, and an ambiguous handwritten symbol. Deliver the rubric, feedback schema, sample conversations, and a defect log.

Acceptance requires factual feedback, evidence tied to the attempt, recognition of valid alternatives, no unsupported accusation of error, and appropriate clarification for ambiguous input. Keep full solutions separate from the first hint.

Suggested owner: Durgesh with a subject reviewer, pending team allocation. Dependencies: verified questions and an upload or typed-input interface. Evaluate transcription accuracy, diagnosis precision, answer leakage, hint usefulness, and abstention coverage. Main risks are misreading handwriting, confidently diagnosing the wrong error, and helping task completion without improving independent performance.
