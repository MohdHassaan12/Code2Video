# Problem generation and verification

Produce five problems tied to the reviewed lesson: two worked examples and three independent tasks. The purpose is to reveal understanding of the concept, including transfer and common mistakes.

## Scope and formal task

Given lesson objectives O, allowed operations A, prerequisite constraints P, and difficulty targets D, generate Q = {q1, q2, q3, q4, q5}. Require alignment(qi, O), solvability(qi), an independently checked answer, and an explanation of the targeted skill. q1 and q2 include worked solutions; q3–q5 hide solutions until the intended review stage.

The exact two-plus-three split comes from the meeting. It is a demonstration requirement, not an experimentally established optimum.

## Literature implications

The [IES guide](https://ies.ed.gov/ncee/wwc/PracticeGuide/1) supports worked-example and problem-solving combinations. [SymPy](https://docs.sympy.org/latest/guides/solving/solve-equation-algebraically.html) provides symbolic tools for checking algebra. Neither guarantees that a generated word problem is unambiguous or appropriate for the learner.

## Proposed generation method

Start with teacher-authored templates and constrained parameters. Generate the problem and a reference solution, then have a separate verifier solve it from the problem statement without seeing the proposed answer. For algebra, add symbolic equivalence checks and explicit domain assumptions. For word problems, check units, referents, missing data, and whether the described situation is possible.

Use q1 for the basic method, q2 for a contrast or misconception, q3 for near transfer, q4 for distinguishing a wrong rule, and q5 for application in a new representation. These assignments are proposed and may change with the subject.

Keep a problem specification with objective, prompt, representation, expected reasoning, valid alternatives, answer, domain, misconception tags, and hint ladder. Inspect for duplicate reasoning even if surface numbers differ. Questions that look different but use the same operation do not establish broad coverage.

## Validation rules

- Solve every problem independently and verify the worked steps.
- State domain restrictions and units when relevant.
- Accept equivalent answers and valid alternative methods.
- Check counterexamples to any generalized rule.
- Keep student prompts free of answer-key leakage.
- Have a teacher judge difficulty and reading load; do not rely on a model's difficulty label.

For like terms, 2x² + 3x² = 5x² follows by factoring the shared x². In contrast, 2x² + 3x cannot generally combine into a single like term. A numerical substitution can disprove an incorrect identity but cannot prove a universal identity by itself.

## Deliverables and acceptance

Deliver five prompts, two worked solutions, a separate five-answer teacher key, three hint ladders, and verification notes. Acceptance requires every item to be correct, unambiguous under stated assumptions, objective-aligned, and reviewed independently.

Suggested owner: subject author; verifier should be a different reviewer where possible. Dependency: stable script and notation. Evaluate correctness, objective coverage, ambiguity, duplication, and learner error patterns. Main risks are plausible wrong solutions, answer leakage, and confusing reading difficulty with conceptual difficulty.
