# 16. Choosing the writer's model by the owner's Model Choice Protocol (2026-10-14 to 15)

The owner pasted a "Model Choice Protocol" with "see this also try to make better by using this models". In short: pick
the cheapest model that clears a measured bar, then put the remaining effort into the harness. Thinking is off by
default and the choice is remembered per model. Every call of a run uses the same model.

## 1. The unit, the test set, the checks

- **Unit:** one lesson script, written by one model end to end and then put through the reviewer and the code gates
  (`critic.verify`, with the reviewer on the SAME model). That is what reaches the voice, so it is what is scored. The
  raw script is scored too, as the "written" stage.
- **Test set** (`evals/writer/cases/`, frozen): twelve briefs with their teaching cards, taken from real lessons, without
  source passages. They are friction, heat, angles, atom, AP, reflection, magnets, floating, heart, triangle area, third
  law and photosynthesis, in Hinglish and in English.
- **Checks in code** (`scripts/eval_writer.py`, `structure`): the script is whole (`writer.too_little`), with no
  language, setting, pause or figure finding, and at most 1.15 times its word budget.
- **Judge:** `openai/gpt-5.4-mini` with thinking low. Its cost is kept apart from the unit's. It scores five criteria
  from 1 to 5 (correctness, teaching, language, picture, economy), and those five give a score out of 100. One eval
  mistake was found by reading the judge's reasons, then fixed and re-judged: it marked down English screen lines in
  Hinglish lessons, which are English by design.

## 2. Results (`evals/writer/scorecard.csv`; outputs in `lessonforge_workspace/evals/writer/<run>/`)

On six cases, after review:

| model (thinking) | score | correctness | cost a script | seconds |
|---|---|---|---|---|
| qwen/qwen3.8-flash (off) | **84.7** | **4.5** | 0.0054 | 148 |
| anthropic/claude-haiku-5.5 (provider's default) | 81.3 | 4.0 | 0.0394 | 327 |
| anthropic/claude-haiku-5.5 (off) | 74.4 | 3.4 | 0.0087 | 62 |
| deepseek/deepseek-v3.2 (off) | 71.3 | 3.8 | 0.0139 | 590 |
| openai/gpt-5.4-nano (off) | 68.7 | 4.0 | 0.0186 | 91 |
| google/gemini-3.1-flash-lite (off) | 66.7 | 3.5 | 0.0275 | 51 |

Before review, Haiku with thinking was best (83.3) and Qwen came out at 68.8. The review step lifts Qwen more than any
other model. GLM 4.7 Flash was dropped at the written stage (44.8: it wrote English for Hinglish briefs).

On the six further cases (2026-10-15, after the owner added credit), after review: Haiku 74.0 / correctness 3.83,
Qwen 73.3 / 3.67. Over all twelve:

| writer and reviewer | score | correctness | cost a script | seconds |
|---|---|---|---|---|
| Qwen 3.8 Flash (off), reviewing itself | **79.0** | **4.08** | 0.0065 | 175 |
| Haiku 5.5, reviewing itself (the live pairing) | 77.7 | 3.92 | 0.0453 | 340 |
| **Qwen writes, Haiku reviews** | 70.7 | 3.67 | 0.0236 | 250 |

**No model reaches the protocol's correctness bar of 4.8.** The third row is what the pipeline would do if Qwen were
simply made the first writer, because the reviewer is a chain of its own (`critic.CRITIC_MODELS_DEFAULT`, Haiku
first): it is the worst of the three. Haiku's review cut Qwen's scripts to about 0.85 of their budget and lost what
they said. So the writer's first model was NOT changed. Qwen reviewing itself ties Haiku reviewing itself at a seventh
of the cost, but the reviewer's chain also listens to questions and answers cards, and those jobs have not been
measured on Qwen. A lesson can already be made that way from the controls (writer and reviewer models).

What the judge found wrong is mostly the same in every row: claims stated too absolutely, a picture said to show what
it does not, and one question card per few lessons that asks another thing than the voice or marks a wrong option
right (Qwen marked "20 cm²" right for the 6 by 4 triangle; Haiku without thinking marked "108 degrees" as the third
angle of a 36 and 72 degree triangle). The cards are what section 4 cures.

## 3. What was changed

- **Thinking per model** (`engine.llm.THINKING_BY_MODEL`, `thinking_for`): Qwen, DeepSeek, Gemini Flash-Lite, nano and
  GLM are called with `reasoning: {effort: "none"}` unless the caller or `OPENROUTER_REASONING_EFFORT` says otherwise.
  The frame judge (`vision_review.default_judge`) follows the same table. Haiku is absent on purpose: with thinking off
  it wrote worse lessons. This matters now because a lesson's controls can choose any model for a job, and a cheap
  model chosen there should run the way it was measured.
- **The writer's fallback order** is Haiku 5.5, then Qwen 3.8 Flash, then nano (`writer.WRITER_MODELS_DEFAULT` and the
  controls catalogue, kept equal by `test_knobs`). Gemini 3.8 Flash, whose thinking cannot be switched off, is out of
  the chain. Haiku stays first until Qwen is confirmed.

## 4. A question card checked by someone who answers it (`questions.solve`, in the question pass)

The card is the one place a learner is TOLD an answer, and nothing checked whether its marked option is true or whether
it asks what the voice asks. Now, inside `questions.improve` (live lessons only; the eval stops before it):

- **Before the cards are written again**, one call on the listener's model gets the whole script and every card WITHOUT
  its marked option. For each card it says what the voice asks, what the card asks, whether one answer answers both,
  and works the answer out (`pick`). Code turns a disagreement into a fault: `wrong_answer` (the card is written again
  with that reason) or `asks_other` (the stop gets another question, voice and card written together).
- **A card may name only numbers the voice has said** (`unsaid_number`, code, no model). It cannot be left in place
  after the pass, and a question this pass writes must say its own numbers in its own beat.
- **Once the cards stand**, a second look. A card whose marked option is still not the one worked out is taken out on
  that look alone. A card asking another thing goes only if it was rewritten here or both looks say so, because one
  look wavered on a fair card.
- **Cost:** two calls a lesson, about 0.15 cents.

Measured before it went live:

- **On 284 cards** of the app's lessons and the eval scripts: 5 marked options disputed. Three were real errors: "108
  degrees" for the third angle of 36 and 72, "20 cm²" for a 6 by 4 triangle, and a wrong order of steps. One was a
  card with no whole answer. One was the judge's own mistake.
- **"Asks another thing":** 25 cards flagged. Most were real, including two in the app's list: a voice asking whether
  a box stops over a card about a bus passenger, and "what do the two bean shapes give?" over a card about the nucleus.
- **The unsaid-number rule on 400 cards:** 8 flagged, 5 of them real ("a ray 40 degrees from the normal" where the
  voice never says forty). Of the other three, two needed the number reader to learn thousands ("one thousand eight
  hundred" had been read as 1 and 800; `annotate.spoken_numbers`, which the marks use too), and one is a Hindi ordinal.
- **The pass on copies of six real lessons**, every card read, three times while it was being shaped
  (nothing was written back). The wrong options were corrected, and the bus and bean-shapes
  cards were replaced or taken out. A lesson with nothing wrong was left as it was.
- **Two faults seen in those readings and cured:** a new card naming a 12 by 4 rectangle under a voice that said "cut
  it along the diagonal", and a fair card taken out because one of two looks wavered.

## 5. Still to do

- Qwen for BOTH writer and reviewer ties today's Haiku pair at a seventh of the cost. Making it the default needs the
  reviewer chain's other jobs (listening to questions, answering cards, the claims check) measured on Qwen first, and
  the owner's word on a reviewer of the same model as the writer. Until then a lesson can be made that way from the
  controls.
- The reviewer (`critic.CRITIC_MODELS_DEFAULT`) and the card (`card.CARD_MODELS_DEFAULT`) have not been through the
  protocol. Each needs its own unit and test set.
- Nobody has listened to a lesson written by Qwen.
