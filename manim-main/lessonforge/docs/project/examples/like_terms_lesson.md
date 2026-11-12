# Draft lesson on why like terms combine

This original draft demonstrates the requested handoff from teaching script to code-generated video and practice. Intended audience: Classes 8–9, subject to the school's curriculum check. It is not adapted from a particular teacher's transcript. External teacher approval and rendering of the complete script below are pending.

**Prototype update:** A condensed [79-second narrated clip](../prototype/output/like_terms.mp4) now demonstrates the opening concept, operation contrast, and one quick practice question. It does not yet implement this full 5-minute-50-second lesson and its five-problem sequence. [Source and validation](../prototype/README.md) are available for review.

## Objective and prerequisites

By the end, the learner can explain and apply `ax² + bx² = (a+b)x²`, distinguish unlike terms, and reject the mistake `2x² + 3x² = 5x⁴`.

Prerequisites: multiplication, distributivity, variables, and the meaning of a square. Pre-checks: explain what `3a` means; calculate `2 × 4 + 3 × 4` in two ways. If these fail, provide a brief prerequisite explanation before the main lesson.

Key distinction: x is a variable, 2 and 3 in the example are coefficients, and the superscript 2 is an exponent. Use these precise terms rather than the transcript's uncertain use of “suffix.”

## Visual and mathematical contract

Use five identical square tiles to represent five quantities of x², with x treated as a positive length for the area picture. Split them into groups of two and three, then regroup without resizing. The general algebraic identity is justified by distributivity and holds for all real x; the area picture is an illustration within its stated domain.

Keep `x²` the same color and label throughout. Use both labels and grouping, so color alone does not convey meaning. For unlike terms, represent x and x² with distinct labeled objects rather than relying on shape proportions to prove anything.

## Timed script and storyboard

Target **5 minutes 50 seconds**, including guided pauses and the two worked examples. Times are production targets, not measured audio duration. Learner practice follows separately.

| Time | Narration draft | Visual direction and pause |
| --- | --- | --- |
| 0:00–0:35 | “Two notebooks plus three notebooks make five notebooks. We add how many there are, while the kind of thing stays the same. What if the same kind of thing is a mathematical expression?” | Show two and three labeled notebooks, group them into five, then fade to an empty workspace. Allow a short prediction pause. |
| 0:35–1:20 | “Imagine a square with side length x, where x is positive. Its area is x squared. Two such squares have total area two x squared. Three more have area three x squared. We have not changed any square—only collected them.” | Draw one square with side x and area x². Copy to two and three groups. Labels stay attached while groups move. |
| 1:20–2:05 | “There are now five copies of x squared. So two x squared plus three x squared equals five x squared. Algebra expresses the same idea by taking out the shared factor: two plus three, multiplied by x squared.” | Reveal `2x² + 3x² = (2+3)x² = 5x²` one step at a time. Highlight the unchanged x² in every term. Ask what changed and pause. |
| 2:05–2:45 | “Could the answer be five x to the fourth? No. We are adding quantities here. Multiplying x squared by x squared is a different operation, and that gives x to the fourth. Try x equals two: the original sum is twenty, while five x to the fourth would be eighty.” | Place addition and multiplication in separate labeled rows. Show `2·4 + 3·4 = 20` and `5·16 = 80`. Mark the false identity, then remove it. State that this substitution disproves it. |
| 2:45–3:35 | “Worked example one: simplify four a squared plus seven a squared minus two a squared. Each term has the same variable part. Combine the coefficients: four plus seven minus two is nine. The result is nine a squared.” | Reveal problem, identify common a², display `(4+7−2)a²`, then `9a²`. Pause before revealing the coefficient result. |
| 3:35–4:35 | “Worked example two: simplify three x squared plus two x plus four x squared minus x. First collect the x-squared terms: three plus four makes seven. Then collect the x terms: two minus one makes one. The result is seven x squared plus x. The two groups have different variable parts, so we keep them separate.” | Group x² and x terms with labels and outlines. Display `(3+4)x² + (2−1)x = 7x² + x`. Pause to ask why the final terms cannot generally combine. |
| 4:35–5:20 | “Here is the rule: terms are like terms when their variable parts match, including the exponents. Add or subtract their coefficients and keep that variable part unchanged. The square picture helped us see one case; distributivity explains the algebraic rule, including when x is negative.” | Show a concise rule with `ax² + bx² = (a+b)x²`. Compare x² with x and x² with y². Briefly verify x = −2 in the opening identity without using negative physical lengths. |
| 5:20–5:50 | “Now try three problems yourself. Show how you group the terms. If you get stuck, ask for a hint about the step you are trying. You can replay the tile explanation or either worked example.” | Show links or chapter markers to the two examples and transition to the three text problems. |

Suggested Hindi or Hinglish key sentence for subject review: “यहाँ x² वाली एक जैसी quantities जुड़ रही हैं। Coefficients जोड़ेंगे, लेकिन x² वही रहेगा।” Confirm language and pronunciation before recording the complete narration.

## Five problems

| ID | Mode | Student prompt | Skill |
| --- | --- | --- | --- |
| Q1 | Worked in video | Simplify `4a² + 7a² − 2a²`. | Combine signed coefficients |
| Q2 | Worked in video | Simplify `3x² + 2x + 4x² − x`. | Group unlike term types separately |
| Q3 | Independent | Simplify `6m² − 2m² + m²`. Show your coefficient calculation. | Near transfer |
| Q4 | Independent | A learner claims `2p² + 3p = 5p²` for every real p. Is the claim true? Explain and test p = 2. | Reject an invalid general rule |
| Q5 | Independent | A collection has seven square tiles, each of side s, and four rectangular tiles, each with sides s and 1, where s > 0. Write and simplify an expression for their total area. | Translate a concrete representation |

## Teacher answer key

Q1: `(4+7−2)a² = 9a²`.

Q2: `(3+4)x² + (2−1)x = 7x² + x`.

Q3: `(6−2+1)m² = 5m²`; the unwritten coefficient of the last term is 1.

Q4: False as a general identity. The variable parts p² and p differ. At p = 2, the left side is 8 + 6 = 14 and the right side is 20. Equality at isolated values such as p = 0 or p = 1 does not make it an identity. Factoring `p(2p+3)` is valid but is not required by this lesson.

Q5: `7s² + 4s` square units. A square has area s² and a rectangle has area s. Keep both term types; at s = 2, the total is 28 + 8 = 36 square units. Accept the equivalent factored form `s(7s+4)` if justified.

## Hint ladders for independent problems

| Problem | First hint | Second hint | Stronger support |
| --- | --- | --- | --- |
| Q3 | What variable part is shared by all three terms? | What is the coefficient of an unwritten `1m²`? | Calculate `6−2+1`, then attach the unchanged m². |
| Q4 | Do p² and p have the same variable part? | Substitute 2 for p in each side separately. | Compare `2·4 + 3·2` with `5·4`. What does a mismatch tell you? |
| Q5 | What is the area of one tile of each type? | Multiply each tile area by its count. | Write `7·s² + 4·s`; explain why the terms have different variable parts. |

## Feedback demonstration

Attempt: “6m² − 2m² + m² = 5m⁶.”

Diagnosis: the coefficient is correct, but the exponent changed during addition. Proposed first feedback: “Your coefficient calculation gives 5 correctly. Each quantity is still measured in copies of m². Are these copies being added or multiplied?”

If the uploaded exponent could be either 2 or 6, first ask the student to confirm it. Do not diagnose an exponent misconception from an uncertain reading.

## Review and rendering checks

- Exactly five equal-area tiles survive the opening regrouping; no scaling implies a changed quantity.
- Every mathematical transformation is valid under its stated domain.
- Numeral, superscript, minus sign, and variable remain visually distinct.
- The multiplication contrast does not imply that coefficients should be ignored in multiplication generally.
- The final scene points to exactly three independent questions, with answers kept in the teacher key.
- Teacher approval, narration rehearsal, render review, and learner trial remain pending.
