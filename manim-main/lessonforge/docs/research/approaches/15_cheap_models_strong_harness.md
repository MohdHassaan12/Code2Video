# 15. Cheap models, a stronger harness, and prompt caching (2026-10-12, night)

The owner, while demo lessons were being made: "Current models are taking a very heavy cost. Try to route the models to
cheaper versions … also try to use prompt caching", and then: "Use cheap models and try to improve the harness. You need
to work on the harness, not by taking costly models." This is what was measured, what was changed, and what a lesson
costs now. Trial scripts and their outputs: `lessonforge_workspace/pilot/cheap/`.

## 1. Where a lesson's money went

"Friction: Why Things Stop" (class 8, Hinglish, 3 min 16 s), made by the pipeline as it stood at 19:16, read from the
ledger by job (`note`) and model: **0.69 USD**.

| job | model | calls | USD | share | tokens in / out (of which thinking) |
|---|---|---|---|---|---|
| the script, its voice pass, its revisions, the question pass | Sonnet 5.5 | 7 | 0.410 | 59% | 46,406 / 31,732 (23,280) |
| the teaching card | GPT-5.6 Terra | 1 | 0.103 | 15% | 22,722 / 3,870 |
| the plan of drawing the picture, the hand's marks | Sonnet 5.5 | 6 | 0.083 | 12% | 22,334 / 3,839 |
| looks at stills and frames | Gemini 2.5 Flash | 40 | 0.039 | 6% | 106,895 / 2,598 |
| how each source teaches it | Gemini 3.5 Flash-Lite | 8 | 0.027 | 4% | |
| the reviewer | Haiku 5.5 | 5 | 0.020 | 3% | 15,429 / 36,435 (26,413) |
| everything else (topic, picture requests, voice script, word times) | | 48 | 0.009 | 1% | |

Two things follow. **The money is in OUTPUT tokens of a costly model that thinks before it writes** (three quarters of
the writer's output was thinking). And **input is the small part**: the writer's 46,000 input tokens were about 9 cents
of its 41, so caching the prompt could have saved at most 5 to 7 cents of that lesson; routing is the lever.

Prices that evening (USD per million tokens, in / out / cached read): Sonnet 5.5 2.00 / 10.00 / 0.10; Terra 2.00 / 12.00 /
0.20; Gemini 3.8 Flash 0.75 / 3.75; Gemini 3.5 Flash-Lite and 2.5 Flash 0.30 / 2.50; GPT-5.4 nano 0.20 / 1.25; DeepSeek
v4 pro 0.44 / 0.88 (no pictures); **Haiku 5.5 0.10 / 0.50 / 0.01** (pictures, thinking optional). The small model of the
writer's own family costs a twentieth per token.

## 2. What the cheap models did on the same real inputs

**The script** (same brief and teaching card; `pilot/values/try_writer.py`). Budget "at most 343 words".

| brief | model | words | by the harness's own measures | USD |
|---|---|---|---|---|
| Friction | Sonnet 5.5 (its draft) | 350 | language 0, repetition 0, pauses 0, question faults 2, voice 1 | 0.26 |
| Friction | Haiku 5.5, twice | 352, 388 | language 0, repetition 1, pauses 0, question faults 1, voice 0 | 0.02 |
| Friction | DeepSeek v4 pro | 369 | repetition 1, question faults 3, voice 2; six minutes | 0.12 |
| Friction | GPT-5.4 nano | 395 | 8 beats, 4 questions, talks about the screen twice | 0.008 |
| Friction | Gemini 3.5 Flash-Lite | | answered with a string where the lesson was asked for | 0.009 |
| Reflection (English) | Haiku 5.5 | 353 | (Terra, as made: 484) | 0.02 |
| Heat | Haiku 5.5 | 338 | (Terra, as made: 422) | 0.02 |

**The card** (`pilot/cheap/try_card.py`). Haiku's first Friction card cited 24 of 25 lines and passed every code check,
and **spread**: it listed "coefficients of static and kinetic friction" under what it leaves out and then gave static
against sliding friction as two of its four mistakes and one of its three questions. 1.3 cents against Terra's 10.

**The plan of drawing with the words, and the hand's marks** (`try_looks.py`, `try_votes.py`). Less steady than the large
model: on the reflection drawing one answer brought the incident ray at the start, another brought the angle's mark five
steps late and the words "Reflected ray" eight steps before the ray; for the marks, one answer gave every angle as "the
angle between these two lines" and the hand would have drawn a second arc beside the printed one seven times.

## 3. What the harness now does instead of a costlier model

| what the small model did | what code does about it |
|---|---|
| returned three of seven chapters (111 words of 343) and stopped; the lesson went on to its review as if whole (the first lesson made on the cheap routing) | `writer.too_little`: a script with fewer chapters than the framework has stages, or under six tenths of its words, is asked for once more with what is missing; still short, it is written chapter by chapter (one small job a call) |
| a card that spreads into another idea of the chapter | `card.scope`: one small question per mistake and question ("this idea, or another? which?"); code acts only on an answer that NAMES the other idea, and the card's one repair round is told. A check on the words of `leave_out` was tried first and called 14 of the library's 18 good cards wrong (a lesson on convection leaves out "convection currents in sea breezes"); it was thrown away |
| one plan in three with a thing far too early or too late | `sequence.plan` asks `PLAN_VOTES` = 3 times and each thing comes at the MEDIAN step; a thing is held back as "showing an answer" only when most answers say so. Three looks cost about half a cent against three for the large model's one |
| a printed name brought before the thing it names | `sequence.settle`: a name that stands alone is not there before the thing it stands beside (`NAME_REACH`) |
| every angle given as a pair of lines | `annotate.honest`: where exactly one mark of the drawing rests on both lines, the value is written at that mark |
| a mark code counted as wrong after the model's look was kept and only reported (an arrow's words written across the atom drawing's legend) | `annotate.seen_right`: what a viewer would see as wrong is left out |
| **second round, after the owner's "try harder" (the faults listed as still open in the first report):** | |
| every script over its budget, and longer after each rewrite (350 words as written, 391 after review, for 343; 31 of 45 lessons over by more than 3%, the worst at 164%) | `critic.length_gate`: the longest beats of an over-length script get a finding with `at_most`; the reviser is told each beat's own limit and `apply_edits` holds it; a rewrite of a script already at its length gets the same words or fewer (it used to get a fifth more); the code gates get a second rewrite round for what the first leaves open (`GATE_ROUNDS`). On the three demo scripts, one round: 401 → 368, 382 → 375, 391 → 353 |
| "think of an atom as big as a cricket stadium" (the owner's bar: no cricket or festival stories) | `critic.setting_gate`: whole words (cricket, stadium, festival, Diwali, mela, …) in the words or the lines are a major finding the gates' rewrite acts on. Run over the 53 lessons made so far it flags 13 beats in 5 lessons, every one a story of that kind (a cricket squad's fatigue sensors, a Diwali mela stall); on the atom script the rewrite said "a room" |
| "F₁ (Lower)" printed beside the first of two cases while the lesson asks on which the reading is lower; a formula printed under the question it answers | `sequence.asked_over` finds, by code, the questions a lesson stops on over a drawing, their right answers and the step each is answered at; `printed_tells` asks ONE decision per printed word ("tells" or "names"), and a word that tells waits for the answer. Words the voice has already spoken before the question were taught, not told, and stay. Asked for a list of telling tags, the small model answered one time in three; asked word by word, three of three on three real drawings. Filmed on the Friction lesson: the two labels now arrive with "Sand paper: F₂ higher" |

Routing after the change (`HARNESS_WRITER_MODELS`, `HARNESS_CARD_MODELS`, `HARNESS_PLAN_MODEL`, `HARNESS_ANNOTATE_MODEL`
put another order): writer, card, plan and marks on Haiku 5.5; the reviewer was already on it; the small looks stay on
Gemini 2.5 Flash and Flash-Lite. No job is on Sonnet, Opus or Terra.

## 4. Prompt caching

`engine/llm.py: system_message` marks a long system prompt as cacheable for the model family that caches only what is
marked (Anthropic's; `LLM_PROMPT_CACHE=0` switches it off); OpenAI's, Google's and DeepSeek's cache a repeated prefix by
themselves. The ledger now keeps `cached_tokens` for every call (`engine.llm.cached_of`), so the saving is a number.

Measured: the writer's standing rules (12,665 characters, 4,592 tokens) sent twice to Haiku 5.5: the first call wrote
4,573 tokens to the cache, the second read them and cost a third of the first (0.00025 against 0.00074 USD). GPT-5.4 nano
cached 2,816 of 3,243 tokens with no mark. Gemini 3.5 Flash-Lite cached nothing at that size. In a real card step, the
repair call read 4,554 tokens from the cache.

What it is worth: on the cheap routing, fractions of a cent a lesson, because input at 0.10 USD a million was never
where the money was. It is in, it is measured, and it would matter again if a costly model were ever put back.

## 5. What a lesson costs now

Two three-minute lessons made end to end on the cheap routing the same night, on a second server, the way the app
starts one (both passed all 13 technical checks; the voice is the one on this machine, because the owner's speech
service's address did not resolve):

| lesson | USD | where it went |
|---|---|---|
| Finding the nth term of an AP (class 10; its card was already in the library) | **0.085** | writer and its passes 0.042 (11 calls, 58,000 thinking tokens), frame looks 0.025 (28), plan x3 and marks 0.007, the rest 0.011 |
| Protons, neutrons and electrons: reading an atom (class 9; new topic) | **about 0.12** | 0.158 was spent in its window together with a first AP run that was stopped (about 0.035): writer 0.070, frame looks 0.041, card 0.014, plan x3 and marks 0.013, sources' plans 0.010 |
| Friction: Why Things Stop (class 8; new topic), three hours earlier on the costly routing | 0.69 | section 1 |

So a lesson costs about a sixth to an eighth of what it did. What was seen in the two: the atom lesson's opening
compares an atom with a cricket stadium (the owner's bar says no cricket stories; it is the textbook's size comparison,
and it is still a miss); one of its nine marks, an arrow with the words "which particles?", was written across the
drawing's legend (code had counted it wrong and it was kept: `annotate.seen_right` now leaves such a mark out, added
after that lesson); in the AP lesson the hand wrote "21", "18", "15" at the points of the falling sequence's graph as
they are said, the frame review found two beats whose words are about another case than the picture, and the repair
of those was tried and put back. Both scripts ran over their budget (401 and 382 words for 343). The reviewer scored
them 2 to 3 of 5, as it had scored the costly lesson (2 to 3). Nobody has watched them with their sound.

The largest item is now the writer's thinking (58,000 tokens for one lesson's script and passes, 4 cents) and the 28 to
47 small looks at frames (2.5 to 4 cents).

## 5b. Two cost levers tried in the second round and NOT taken

**Capping the writer's thinking.** `reasoning.max_tokens` 6000 was not kept (20,000 and 44,000 tokens of thinking) and
one first answer came back with one chapter of seven (the whole-lesson contract caught it and the second asking was
whole). `effort: low` halved the thinking (16,000), saving about a cent and a minute a script; that script talked
about the screen three times where the others did once at most. Left as it was.

**The small model as the frame judge.** The same 24 frames of two lessons, judged by both: Gemini 2.5 Flash 7 findings
for 1.6 cents, Haiku 4 findings for 0.7. Both found the two real faults (an arrow's words across a legend; words about
another case than the picture); each had one or two debatable ones, and Haiku called a words-only opening "empty",
which is a finding that starts a repair. About a cent a lesson; not switched on two lessons' reading.

## 6. Not done

The frame looks (40 calls, 4 cents) send a picture each time and cannot share a cache. The reviewer's and the writer's
thinking is not capped (at Haiku's price it is 1 to 2 cents a lesson). A lesson that fails its checks still pays for a
second render's looks. Nobody has compared a cheap-routing lesson with a costly one by watching both with their sound.
