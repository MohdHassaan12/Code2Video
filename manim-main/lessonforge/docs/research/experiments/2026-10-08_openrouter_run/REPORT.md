# 2026-10-08 — First real-model run, problem list, approaches adopted

Budget: 10 USD on an OpenRouter key (ledger `lessonforge spend`). Spent at the time of
writing: about 0.45 USD. Every number below comes from the ledger, the build's own
check files, or a script in this folder's parent session; nothing is estimated unless
it says so.

## 1. One topic, end to end

Brief: *Why the Pythagorean theorem works* — class 8, standard level, framework
"Watch one, do one", tutor voice, English, 6 minutes, running example "a ladder
leaning against a wall", known mistake "they add the two sides instead of squaring".

| Stage | Model / tool | Result | Cost |
|---|---|---|---|
| Script (plan + 6 chapters) | google/gemini-3.8-flash via OpenRouter, JSON mode | 809 words (target 810), 15 beats, running example in 6/6 chapters, 46/46 steps anchored to spoken phrases | 0.09 USD |
| Critic | same model (now a different family by default, see §3) | caught a **critical contradiction** (ladder stated as 4 m in beat 1, solved as 5 m later), fixed it with text-only edits in beats 01 and 05; 13 arithmetic claims checked by code, 0 failed | 0.01 USD |
| Speech | google/gemini-3.8-flash-tts, voice Kore, instruction "clear, warm maths teacher, pause after questions" | 429.7 s of narration in 15 blocks (113 wpm incl. pauses) | 0.093 USD |
| Alignment | openai/whisper-large-v3 word timestamps | 15/15 blocks trusted, 793/809 words matched (98%) | 0.011 USD |
| Render + checks | Manim 0.20, 720p, 6 chapters in parallel | all 13 technical checks pass; 0 counted layout findings; worst cue lateness 0 | — |
| Vision review | google/gemini-2.5-flash, one frame per beat | 8 findings on 15 frames (6 "mismatch", 1 "empty", 1 "stale") | 0.02 USD |
| **Total** | | 657 s wall clock | **≈ 0.20 USD** |

### Measured: how wrong were the old timing estimates? (RQ-12)

Comparing the pause-based estimate the previous build used against the aligned word
times on the same 15 blocks:

| | n | median error | p90 | max |
|---|---|---|---|---|
| Sentence starts | 68 | 0.37 s | 0.79 s | 3.17 s |
| Step anchors (where a visual fires) | 45 | 0.40 s | 1.17 s | 3.24 s |

18 of 45 anchors were off by more than 0.5 s and 6 by more than 1 s. With alignment
every anchor is a measured word onset; the runtime now fires the picture 250 ms
before the word (saccade latency; viewers tolerate picture-first).

### Writer model comparison (same brief, one call each, before the per-chapter fix)

| Model | words (target 810) | beats | example in chapters | reasoning tokens | cost | time |
|---|---|---|---|---|---|---|
| gemini-3.8-flash | 507 | 12 | 6/6 | 795 | 0.017 | 31 s |
| gemini-3.8-flash, effort=low | 560 | 15 | 6/6 | 0 | 0.016 | 41 s |
| gemini-3.5-flash-lite | 438 | 7 (one 91-word beat) | 6/6 | 0 | 0.004 | 7 s |
| gemini-2.5-flash | 727 | 18 | 4/6 | 0 | 0.013 | 23 s |

Every model under-wrote a one-call script by 10–45%. Writing chapter by chapter with
an explicit per-chapter word budget landed on 809/810. Gemini 3.x cannot have
reasoning disabled on OpenRouter (HTTP 400), only its effort lowered.

## 2. Problems found on this one video (against the catalogue)

| # | Problem | Evidence | Catalogue |
|---|---|---|---|
| P1 | **Frames mostly empty; no diagram** — the writer's free-text `visual` was never drawn; "The idea in one picture" showed only `c²` | contact sheets; vision review 7/15 frames not showing the intended picture | RQ-17 composition, new |
| P2 | Contradiction across chapters (ladder 4 m → 5 m) | critic finding, fixed | RQ-04 consistency |
| P3 | Known mistake repeated in chapters 1, 3 and 5 | 5-gram repeat measure: "many students simply add three" | RQ-04 |
| P4 | Glossary pronunciation respellings leaked into narration, captions and screen ("high-pot-en-yoos") | script text | new (introduced by the ledger) |
| P5 | Thinking pauses placed after statements, not questions (beats 08, 13) | pause gate | pedagogy lint (CAT 7) |
| P6 | Visual onset lagged the word by up to 3 s on estimated anchors | alignment comparison above | RQ-12 |
| P7 | Wording slightly above class 8 in 10/15 beats (FK 7.3 vs ≤7 band) | readability lint | new |
| P8 | Vision judge flagged "not visible yet" items as mismatches when sampled before their cue | 6 "mismatch" findings | RQ-20 judge calibration |
| P9 | LaTeX written into plain-text steps (`\text{Wall height} = 4\text{ m}`) | script | new |
| P10 | Receded steps hard to read at 42% on the dark theme; text small for the frame | contact sheets | composition |

## 3. What other people do, and what was adopted today

Full write-ups with sources: `docs/research/approaches/01…05`. Adopted (all in code, all
run on the next job):

| Problem | Approach (source) | Adopted as |
|---|---|---|
| P1 | Closed inventory of parametric figures chosen by the model with numbers; code owns geometry (Code2Video anchors; SGA scene-graph grounding; "registered mobject inventory" in 03) | `longform/figures.py`: `right_triangle` (with squares-on-sides), `number_line`, `bars`; writer schema `figure`; GuidedChapter lays figure left, words+maths right |
| P2 | Typed chapter contract + model-emitted ledger diff validated in code (CourseBlueprint, EduStory, NstAgent in 01) | per-chapter `uses_from_before`, `running_example_step`, `hands_forward`, `ledger_update`; unexplained references counted |
| P3 | One stage owns the misconception; "say it once" | framework `MISCONCEPTION_ROLE`; 5-gram cross-chapter repeat metric with warning |
| P4 | — | glossary carries `meaning` not `say_it_as`; respellings reverted in code; rule in the system prompt |
| P5 | Pedagogy lints (CAT 7; 01) | `critic.pause_gate` |
| correctness | Cross-family verification: same-model self-check accepts its own errors ~14% (X-SGRV in 01); claims as code (SymCode) | critic chain `anthropic/claude-haiku-5.5 → openai/gpt-5.4-nano → deepseek/deepseek-v4-pro`; claims evaluated under a whitelist; universal-quantifier sentences listed for the reviewer |
| P6 | Transcript-constrained alignment; picture leads word by ~250 ms (03) | whisper word timestamps matched to the script (`longform/align.py`); `CUE_LEAD = 0.25` |
| P7 | Readability bands per class (05) | `critic.readability` (Flesch–Kincaid + sentence length; English only) |
| P8 | Sample at cue onsets, tell the judge what is expected yet (02, 03) | `vision_review.sample_points` uses aligned word onsets; prompt lists "later" items |
| P9 | — | discipline routes LaTeX-looking text to MathTex |
| P10 | One evoked cue, rest dimmed ~0.35 (cueing meta-analyses in 03) | `RECEDE = 0.35` |
| frameworks | worked-example/faded practice (g≈0.48), refutation (d≈0.8), activation and retrieval (04) | three frameworks rewritten, 7 stages each |
| cost | one ledger, budget enforced before every call (RQ-26) | `lessonforge.spend`, `lessonforge spend` |

Not adopted yet, in order of expected value: SGA-style mid-animation sampling (K=11)
and minimum-separation-vector repair in the probe; Code2Video 6×6 anchor grid with
measure-then-fit; MFA/MMS forced alignment self-hosted (20 ms vs whisper's ~110 ms);
scene-graph geometry checks for "right angle at which corner"; planted-fault
calibration set for every judge; TeachQuiz-style learner-model pre/post test.

## 4. Prices measured through OpenRouter (for scale planning)

| Item | Price | Per 6-minute lesson |
|---|---|---|
| Gemini 3.8 Flash TTS | 9 USD / M audio tokens, 25 tokens/s ≈ 1.35 ¢/min | ≈ 0.09 USD |
| Gemini 3.8 Flash-Lite TTS | 6 USD / M ≈ 0.9 ¢/min | ≈ 0.06 USD |
| whisper-large-v3 word timestamps | ≈ 0.19 ¢/min | ≈ 0.011 USD |
| Gemini 3.8 Flash writer (plan + 6–7 chapters, reasoning on) | | ≈ 0.09 USD |
| Critic (Haiku 5.5) | | ≈ 0.005 USD |
| Vision review (gemini-2.5-flash, 15 frames) | | ≈ 0.02 USD |
| **Lesson total** | | **≈ 0.20–0.25 USD**, ≈ 11 minutes wall clock |

At this rate the remaining budget covers roughly 35–40 more six-minute lessons.
Self-hosting (04 §Q3): TTS is ~45% of the bill; Kokoro (English) / Veena or
Chatterbox-Hindi (Hinglish) plus MMS forced alignment would bring a lesson-minute to
≈ 0.3–1.5 ¢; a script LoRA is premature until ≥500 stage-labelled scripts exist.

## 5. Open after today

- Nobody has **listened** to the Gemini-TTS narration or watched the video end to end.
- The figure inventory has three kinds; most topics need more (axes/plots, grids,
  angles, molecules…). Each new kind is ~40 lines of deterministic Manim.
- Hinglish/Hindi: TTS works (Gemini auto-detects), alignment coverage unmeasured;
  readability lint is English-only.
- Vision review remains advisory: every measured frame-level VLM layout judge is
  weakly or negatively human-aligned (02).
- From `approaches/05_*` (personalization, interactivity, readability, palette), built
  today: readability bands per class (6–8: ≤14 words/sentence, FK fail >8; 9–10: ≤17,
  >10; 11–12: ≤20, >12) as critic findings; `output/interactions.json`
  (`lessonforge.interactions/0.1`: one `predict`/`recall` card per thinking pause, with
  the question, the answer that follows, and the beat's self-check as a hint) for a
  player that pauses; the dark teaching palette (background `#1C1F26`, ink `#F2F3F5`,
  accent `#FFE566`, given `#80B1E7`, unknown `#D19461`, result `#56FAAA`, wrong
  `#E57A9E`, all ≥ 6:1 contrast). Not built: a light theme, level-dependent scaffold
  density beyond the frameworks, vocabulary gates (CEFR/wordfreq), the player side of
  interactions, and any Hindi readability measure.

## 6. First user test (same day): what broke, and what changed

A tester asked for *Trigonometric equations — class 9, rural government school,
Hinglish, 15 minutes* through the web client over the tunnel.

**What broke.** The job ran every stage (35 narration blocks, 7 chapters, 12.3 minutes
of video) and then failed in the last step with `TypeError: 'Chapter' object is not
subscriptable` — a bug in the interaction-file code added an hour earlier and shipped
without one job being run through it. The client showed a failure and the result was
only in memory. Nothing was lost on disk; the job was recovered from its lesson
directory.

| Defect | Fix |
|---|---|
| A sidecar file's failure cost the whole job | Everything after the checks is advisory (`service._run`: vision review, review page, interactions); result fields are computed from disk by one function (`results_from_disk`) used both at the end of a run and for recovery |
| Job and session state only in memory | `job.json` per lesson directory, `sessions/<id>.json`; a finished lesson directory alone rebuilds the job record; `GET /jobs` lists every lesson on disk |
| No test ran a job through the service | `tests/integration/test_harness_job.py`: a real (silent, 480p) job end to end, a restart, and a forced failure after the video is built |
| Intake questions generic; "You decide" stored as the running example and the known mistake; goal "they should do problems on trigonometry" accepted | `harness/interviewer.py`: code picks the field, a fast model (gemini-3.5-flash-lite, 2–5 s, ≈0.5–1 ¢ per conversation) writes the question for the topic with 3–4 tappable answers; a vague goal is pushed back on once; a topic that is a whole chapter gets a narrowing question after the audience is known; "you decide" takes the first suggestion |
| The level was guessed from the class number, so "what do they already know" was never asked | Level is always asked, with topic-specific hints |
| Figure labels in LaTeX shown as raw text; θ written as a side label | Labels with LaTeX are typeset; θ on a side becomes an angle mark; `angle` parameter |
| One triangle requested 3-4-5 but labelled with a 4 m hypotenuse | `longform/figure_math.py`: the drawing follows the labelled numbers; mismatches are critic findings |
| A figure vanished between beats that kept discussing it | A figure stays until a different one replaces it |
| Client lost the result on reload, had no history, no failure view | Recent videos list, resume via `#job=`, failure view with retry, reconnecting state |

**Seen in that lesson and still open.** Hinglish alignment: 25 of 35 blocks trusted
(word match 90% against 98% for English), so 24 of 83 cues fell back to estimates —
the speech-to-text model writes Hinglish in a different spelling than the script.
16 phrases repeated across chapters. The critic scored conceptual accuracy 2/4 and
repaired three overclaims ("geometry guarantees one solution") before speech; three
minor pause findings were left. The topic itself was pitched wrong for class 9 because
nothing asked which idea inside the chapter to teach — the narrowing question now does.

**Browser test of the fixed build (through the tunnel, headless Chrome).** Run 1
(1180×860, "Area of a circle"): intake with model-written questions, typed and tapped
answers, a pushed-back goal, "You decide", confirm, generate, all stages, video
playing with captions (readyState 4, 171 s), reload reopens the lesson, history lists
it — no console errors, no failed requests. Run 2 (430×900) hit a one-minute network
outage on the build machine: the client kept polling and recovered, speech fell back
from Gemini TTS to local Kokoro, the critic's re-check was skipped with a logged
reason, and the job finished. That run exposed two cues firing 0.55 s late (an
animation running into the next cue); animations are now sized to the gap before the
next cue and lateness is judged against the spoken word.

**Critic, after the fixes.** Reviewer beat ids such as "beat-05" are normalised (they
had silently dropped every edit of one run); a script the critic edited is reviewed a
second time so the reported scores are those of the narrated text; an open critical
or major finding with no edit triggers one rewrite request for exactly those beats.
The arithmetic lint no longer judges the tail of a longer expression ("twenty-two
over seven times fourteen gives forty-four" was reported as a wrong product).

## 7. Second user review: language, motion, interaction, flexible length

The tester's verdict on the first videos: the Hinglish used Hindi number words ("teen
bata char" for three by four), "the dynamics are very minimal", there was "not much
interaction in the video", and one lesson should serve both a first-time learner and
a student revising. Stronger models were explicitly allowed.

**Language.** Rule: Hindi for the conversation, English for every number, fraction,
unit, operation and subject term. `critic.language_gate` found Hindi technical words in
25 of the 35 beats of the tester's lesson. It is now in the writer's language note, in
the critic (a major finding that triggers the rewrite round), and in the narrator
instruction given to the TTS model.

**Writer model** — one Hinglish brief (sin θ = 3/4, class 10, 3 minutes) through four models:

| Model | time | cost | words | beats with Hindi technical words | quizzes | steps with a figure focus |
|---|---|---|---|---|---|---|
| google/gemini-3.8-flash | 30 s | $0.017 | 336 | 1 | 2 | 20 / 23 |
| google/gemini-3.1-pro-preview | 59 s | $0.120 | 446 | 0 | 1 | 27 / 27 |
| anthropic/claude-sonnet-5.5 | 105 s | $0.155 | 437 | 2 | 3 | 24 / 30 |
| openai/gpt-5.6-terra | 59 s | $0.089 | 465 | 1 | 3 | 35 / 35 |

All four follow the language rule once it is stated with examples. Terra and Sonnet
wrote the fullest scripts; Terra is the default writer now (Gemini 3.8 Flash is the
fallback), the critic stays on a different family.

**Motion** (`longform/figures.py`, `runtime.GuidedChapter`): figures are drawn stroke by
stroke in a longer lead-in before the voice starts; a step with a `focus` makes that
part of the figure pulse and, for a formula step, its label travels into the formula;
each formula line grows out of the previous one; a figure of the same kind morphs into
the next; two more figure kinds (circle with sectors and the cut-and-rearrange layout,
rectangle with a unit grid).

**Interaction.** A thinking pause now carries a `quiz` (three options, the wrong ones
being real mistakes). In the video: a question card with a countdown, then the right
option lights up. For the player: `interactions.json` carries the options with
feedback, and `resume_at`.

**One video, several viewers.** Every beat has a `depth` (basics / core / practice /
extra); `output/outline.json` lists the cuts built from them — full, skip the basics,
quick revision (core only), summary — as time ranges of the one rendered video, and
`POST /api/harness/jobs/{id}/cuts/{cut}` writes any of them as its own mp4 with captions.
Core beats are written to stand alone so a revision viewing does not point back at
skipped parts.

**A chapter as a series.** `harness/planner.py` (`lessonforge plan`, `POST /api/harness/plan`):
"Introduction to Trigonometry", class 10 → 12 single-idea lessons in NCERT order with
prerequisites, 67 minutes, each with a ready brief for `lessonforge harness`.

**Also fixed here.** A step whose phrase occurs twice in a beat was matched to the first
occurrence, pulling a later step back to the start (4.7 s "late" on the demo); steps are
now matched in narration order.

## 8. Any topic gets a moving picture: model-written scenes

A tester's chemistry lesson (dynamic equilibrium) came out text-only: the figure
inventory covered geometry and fractions and nothing else. The engine already had the
right tool — `engine/sim_gen.py`, where a model writes one bounded
`build(width, height)` + `animate(group, run_time)` pair that is executed and verified
without a renderer (it draws something, something moves, nothing leaves its box, no
file or network access). It is now a figure kind:

    {"kind": "scene", "describe": "A closed flask holding 12 brown NO2 molecules and 6 colourless N2O4
      molecules; pairs of NO2 keep joining into N2O4 while N2O4 keep splitting, at the same rate"}

- **Stage `visuals`** (`service.resolve_scenes`): one call per distinct description,
  three in parallel, cached for ever by the engine; a scene that cannot be verified is
  removed from its beats (no picture rather than a placeholder).
- **Model**: `OPENROUTER_CODE_MODELS=openai/gpt-5.6-terra,anthropic/claude-sonnet-5.5,…`.
  Measured: the water-tank scene was written and verified first time in 43 s for
  $0.068 (3.6k output tokens, 1.9k of them reasoning).
- **Motion for the whole beat** (`runtime.GuidedChapter._start_motion`): the animation is
  stepped by hand from an updater, on a copy sitting at the origin, and mirrored into the
  picture's place every frame.
- **Why "at the origin"**: the first flask scene, written by the weaker default chain,
  animated with absolute coordinates — correct where the verifier checked it, 3 units off
  once the lesson moved the picture into its column, molecules drifting over the text
  (5 counted layout findings). Replaying exactly what was verified removes that class of
  failure without asking a model to behave. The engine's own placement has the same
  exposure; a translated second pass in `sim_gen.verify` would close it there.

**Process finding.** A server restart during this work killed a lesson the tester had
started 14 minutes earlier (the "is anything running" check printed its answer and the
command carried on). The restart helper now refuses while any job is queued or running;
the lesson was resubmitted. Job state on disk meant the tester saw a clear failure with
a retry, not a hang — but the right number of interrupted jobs is zero.

**Intake finding from the same job.** Asked "which one idea inside gradient descent?",
the tester answered "we need full coverage of all of them" and that sentence became the
topic. Declining to narrow now keeps the topic, records the wish for the writer, and
points to the chapter planner.

## 9. Reviews from real people, stored with the lesson

Every number above is the pipeline measuring itself. `harness/feedback.py` adds the other
half: two sheets, answered in the app and stored on the server.

- **Student review** (one lesson, opened from a review-only link): five tasks, twenty
  questions (thirteen required, about four minutes), a "This part is confusing" button
  that records the video time, and what the player saw (in-video questions answered
  right, seconds watched). Stored in `lessons/<id>/feedback/` and `feedback.jsonl`.
- **Tester feedback** (the people who make lessons): the ten questions of the tester
  walkthrough, in a Feedback tab instead of a separate form. Stored in
  `feedback/tester/` and `feedback_testers.jsonl`; contact details never enter a summary.
- **Each question names the part of the pipeline it informs**, and a summary ends with
  signals — a rating under 3.5, 40% finding it too fast, 30% seeing an overlap, any
  reported mistake, in-video questions right under half the time — each pointing at code.
  Confusing moments are mapped to the beat and its narration.
- **A review link is weaker than the app link.** `LESSONFORGE_REVIEW_TOKEN` can load one
  lesson and send one review. Verified through the tunnel: jobs list, generate, cut
  export, summaries and the engine all answer 403; no token answers 401.
- **Tested in a real browser through the public link**: a student review (18 answers,
  two confusing moments) and a tester form were stored; the review link made only its
  three permitted calls. The test entries were removed afterwards.

Also from this round: formula steps are cut to one line and words inside a formula keep
their spaces ("24records, 1update" was on screen); LaTeX that does not compile now falls
back to readable words instead of raw markup; a highlight box no longer reaches into the
next step. One counted finding remains in a model-written scene (two number labels at
the same place): scenes are verified to move and stay in their box, not for overlapping
text inside them.

## 10. A dashboard, and the first real traffic

Testers were using the link while this was built (three lessons generated between 15:45
and 16:10 by people other than the author), and nothing said who or how many.

- **What is counted** (`harness/analytics.py`): one line per event in
  `<workspace>/analytics/events.jsonl` — a page load, a conversation started, a video asked
  for, a video played, 25/50/75/100% of it watched, a review or feedback form sent, a cut
  saved. Lessons, conversations and spend are read from what the workspace already holds,
  so those go back to the start; visits and plays exist only from the first recorded
  event, and the screen says from when.
- **Who is a visitor**: a random cookie set on the first admitted page load, or a salted
  hash of address and user agent for a client that keeps no cookies. No name, address or
  full user agent is stored. Reopening within 30 minutes is the same visit.
- **Watched share is played time, not position**: a seek adds nothing. "To the end" is
  88% of the chosen version, because a question's own thinking pause is skipped rather
  than played and a lesson watched in full never adds up to its length.
- **Tested in a real browser through the public link** (`tests/browser/e2e_dashboard.js`):
  dashboard opens, a lesson opened from it is played through, the play and the four
  progress marks arrive, the lesson's row and the funnel change, and leaving one's own
  visits out removes exactly that browser. Desktop and phone widths.
- **First 5 minutes on a new link**: 5 visitors (4 Android phones, 1 Mac, all India),
  3 plays, one conversation that became a lesson. The phone share is the finding: the
  watch screen is used far more on phones than the desktop it was mostly checked on.
- **The reboot.** The machine restarted at 16:22 during the browser test. The server, the
  tunnel, the restart helper and the browser drivers were all in `/tmp` or in memory and
  were lost; the link testers had was dead for about 85 minutes until someone said so.
  The helper is now `scripts/public_link.sh`, its logs and the current link are in the
  workspace, and the drivers are in `tests/browser/`. Nothing restarts by itself yet.

Spend at this point: 6.93 USD of 10 (OpenRouter's own figure runs about 0.08 higher).
Testers' lessons with scenes cost 0.5 to 1 USD each, so about three to five more fit.

## 11. One bad lesson, taken apart ("Square Numbers through Prime Factorization")

A tester's report on job `20261008-175321-620d35`: the same things again and again, no
animation, questions inside the video that could not be answered, and (of this and the
gradient-descent lessons) an example too complicated to follow. Every claim below was
read from that lesson's own files.

| What was wrong | Evidence | Cause | Change |
|---|---|---|---|
| No animation at all | `scenes: asked 8, made 0`; all 19 beats ended with `figure: none`; frames are two or three lines of text on a dark screen, one frame fully blank | The code-safety check matched LETTERS: `"os."` is inside `ladoos.`. Seven of eight scenes were "unsafe", and an unsafe reply is never retried. The eighth asked for 1764 objects and failed verification twice | `engine/code_safety.py`: one token-anchored list for both generators. A failed scene gets one simpler try. A crowd is asked for small from the start (`service.scene_brief`). A lesson whose animations ALL fail stops before speech |
| The same things again and again | 18 phrases repeated across chapters; the scene ("Diwali mela ke stall par…") set in six of seven chapters; "one thousand seven hundred sixty-four" spoken 12 times (about 36 s); pairing 2,3,7 explained in chapters 4, 5 and 7; `42 × 42 = 1764` shown in 3, 4 and 5 | Every chapter was handed the full example sentence with "use it", none saw the others' words, each stage's job said "the running example", and `continuity` warned when a chapter did NOT use it. The count of repeats was a warning nobody acted on | The example is described in ONE chapter and named after that; each chapter is handed the whole script so far; `critic.repetition_gate` turns repeats and re-read numbers into findings the revision round removes |
| Questions inside the video, not answerable | The video drew "YOUR TURN", three answer boxes and a countdown, then lit up the right box by itself | By design, so an exported file was self-contained. In the app it duplicated the player's own question, looked like buttons nobody could press, and gave the answer away | The video shows the question and thinking time only (`runtime._quiz_card`); answering is the player's job. `LESSONFORGE_QUIZ_IN_VIDEO=options` restores the old card for a file watched without the app |
| The example was harder than the idea | Anchor: 29 words, a mela, a stall, an owner, a gift box, 1764 ladoos. Gradient descent: a cricket squad's 24 fatigue-sensor records, 44 words | The intake asked for "a setting … these learners will recognise" with "cricket ground" as its hint, the question model was told to offer "a real running example with a setting", and the writer had to carry it through every chapter | The intake asks for one simple example and offers the plain small-number version first; the writer's rule is "the example serves the idea": one object, no story, smallest case first; the reviewer checks each part of the example stands for part of the idea |
| The method was never taught | 1764 was found by trying 42 × 42, then 42 was factorised; no division of 1764 is ever shown; the only non-square is 12, in the last ten seconds | Nothing asked whether the goal's method is carried out. The reviewer scored it 3,3,3,4 and passed it | The plan lists the method's steps; every chapter is told them; the reviewer checks they are done on screen, including a case that fails |
| 8:36 for a six-minute request | 985 words against 810; every lesson measured overran by 22 to 100% | 135 words a minute assumed (125 measured), pauses uncounted, a floor of 120 words a chapter, and "short chapters are the usual failure" in the prompt | `writer.word_budget`: 125 a minute less the pauses; "at most", not "about" |
| English in a Hinglish lesson | Six of nineteen beats spoken entirely in English | The language gate looked only for Hindi number words; the reviewer called it minor | `critic.english_only_sentences`: a beat mostly in English is a major finding |
| The three kinds of video meant nothing | "See it, then name it / Watch one, do one / Why must it be true?" | Names of teaching shapes, shown to someone choosing a video | Plain names ("Start from a picture…"), and the question model writes what each video would do with THIS topic |
| Marked done regardless | `technical_checks_failed` (a cue 1.82 s late; 6 of 19 blocks not aligned), 10 frame findings, 0 of 8 animations | Every one of these was reported and none stopped or flagged the lesson | Zero animations now stops the job; the rest are still only shown (open) |

Not fixed here: the sync failures (speech-to-text recognised none of the words in four
Hinglish blocks), text clipped at the right edge in two frames, and the long-number
habit in on-screen steps. A viewer watching fullscreen does get the question: the player
leaves fullscreen and asks (`tests/browser/check_fullscreen.js`, desktop Chrome only).

### The same brief, regenerated (job `20261008-184720-e88dd6`)

| | Reported lesson | Regenerated |
|---|---|---|
| Animations drawn | 0 of 8 | 6 of 6 (two asked for small from the start) |
| Beats with a picture | 0 of 19 | 8 of 14 |
| Length (6 minutes asked) | 8.6 min, 985 words | 5.1 min, 615 words |
| Phrases repeated across chapters | 18 | 1 |
| "one thousand seven hundred sixty-four" spoken in full | 12 times | 2 times |
| Beats spoken entirely in English | 8 | 0 |
| The example | a mela, a stall, an owner, a gift box, 1764 ladoos (29 words) | "ladoos in a square gift box", met first as 9 ladoos in 3 rows of 3 |
| The method | 1764 found by trying 42 × 42 | 1764 divided step by step on screen; 1800 worked as a case that fails |
| In-video question | answer boxes and a self-revealing answer | the question and thinking time only |
| Cost | about 0.9 USD | 0.66 USD |

It is not a clean lesson, and what it got wrong was mostly done by the new checks themselves:

- **The repetition gate cut a definition in half.** "Jis total ko equal rows aur equal columns mein
  sajaya ja sake, use square number kehte hain" lost its rows and columns, because that
  five-word phrase had been said in an earlier chapter. One short phrase said again is usually
  the idea's own name. The gate now needs a phrase of seven words or two separate phrases, and
  the rewrite instruction says what must survive a cut.
- **A reviewer's rewrite put digits and symbols into the narration** ("1800 = 2 x 900"), in a
  beat it rightly wanted to carry out the factorisation. `writer.speakable` now writes digits
  and symbols out as words at both doors (the writer's output and every rewrite).
- **A question at the end of a chapter was never answered**: "the next beat confirms the answer"
  stopped at the chapter's edge. The next chapter is now told the question and its answer.
- **The opening question was never answered in so many words**; the worked-example stage must
  now end by answering it.
- **A layout violation in a code-drawn figure**: "16 cells" printed on the grid lines of a
  `rectangle`. The label gets a backing plate on a grid.
- Still open: the reviewer marked it "needs review" (three major items, two of them above); one
  scene drew 1800 splitting into 18 and 100 while the voice divided by 2 (scenes are verified
  to draw and move, not to match the words); 10 of 14 narration blocks were aligned.

The lesson from the lesson: **a new check is new code that edits scripts**. The first real run
after adding one must be read for what the check itself broke, not only for what it fixed.

## 12. Fifteen lessons' records, read together

Asked to look past the one lesson. Every finished lesson's `job.json`, chapter audits,
`final_checks.json`, `vision_review.json` and the server log were read by script
(the survey is a few lines of Python over `lessonforge_workspace/lessons/*`). What
recurs, with its cause:

| What recurs | How often | Cause | Change |
|---|---|---|---|
| Longer than asked | 14 of 15 lessons, by 22 to 100% | 135 words a minute assumed, pauses uncounted, a floor of words per chapter | `writer.word_budget` (§11). Regenerated: 5.1 and 5.9 minutes for 6 asked |
| Phrases repeated across chapters | every lesson written chapter by chapter: 11 to 48 phrases each | chapters could not see each other's words (§11) | regenerated: 1 and 5 |
| Hinglish narration not aligned to its audio | 123 of 155 blocks in 9 Hinglish lessons; 100% in every English and Devanagari lesson | The recogniser was told "hi" for Hindi written in Latin letters and answered in Devanagari: nothing matched. Told "en" it sometimes TRANSLATES the Hindi | `align.sound_key` matches Devanagari to Latin by consonant sounds; `align_best` hears a Hinglish block both ways and keeps the better. On the reported lesson's 19 blocks: 13 trusted before; "hi" by sound 18, "en" 15, the better of the two 19 (least coverage 96%) |
| Late cues | 3 of 840, all in unaligned Hinglish blocks, all `fallback-spread` | follows from the row above | same |
| Captions out of order | 1 lesson | The recogniser stamped the last word of an 18.2 s clip at 29.8 s; that block's last caption ran six seconds into the next | `align.tidy_heard` clamps to the clip's length |
| Numbers never matched | every lesson with a spoken number | script says "one thousand seven hundred sixty-four", the recogniser writes "1764" | digits are split into the words they stand for; "forty-two" and "42" meet |
| Text on text inside a scene | 2 lessons failed their layout check on it ('74' on '80', '2' on '12') | a scene was verified to draw, move and stay in its box, never for labels on labels | the sandbox rejects labels that rest on each other, before or after the motion |
| Frame review says "clipped" or "not visible" | 8 + 29 of 88 findings | the frame was taken 1.0 s after the key step's cue, while it was still being written ("coll" of "colloid") | taken 1.6 s after |
| Screen empty while the voice talks | 7 frames in 5 lessons | every step of a beat tied to its last sentence, and no picture | `writer.open_with_something`: the first step comes in with the beat's first words |
| English sentences in a Hinglish lesson | 14 beats in 3 lessons, plus one written by the reviewer's own rewrite | the gate looked only for Hindi number words; the reviewer was never told the language | English-only gate; the reviewer is told the language; a rewrite that adds English sentences is refused; the code gates get one rewrite of their own after the last review |
| Marked "passed" and "done" with a failed check | 5 of the 7 lessons with a failed technical check | the reviewer reads the script, the checks read the video, and nothing joins them | still open: the app shows "Technical checks failed", the job is still done |

Two things the survey could NOT answer, because the records do not hold them: whether a
scene shows what the words say (one drew 1800 splitting into 18 and 100 while the voice
divided by 2), and what a learner makes of any of it. Zero student reviews exist.

### Two more real runs after the cross-lesson fixes

| | Square numbers, second regeneration (`20261008-190847-5038ab`) | Gradient descent, same brief as the "cricket" lesson (`20261008-194756-66003b`) |
|---|---|---|
| Animations | 6 of 6 | 6 of 6 (one only on the simpler second try) |
| Length (6 asked) | 5.9 min, 688 words | 5.8 min, 704 words (was 8.1 min, 996) |
| Phrases repeated across chapters | 5 (was 18) | 1 (was 11) |
| Narration blocks aligned | 9 of 14 (run before the alignment fix) | 14 of 14, 97% of words (was 18 of 19, 87%) |
| Technical checks | failed: '2' on '12' inside a scene (run before the label check) | passed |
| Frame review | 10 of 14 as intended | 14 of 14, no clipped, empty or stale |
| Reviewer | needs review: one beat in English | needs review: one claim without its condition, three questions answered with no pause |

What these two taught, and what was changed after them (so NOT yet seen on a real run):
the requester's suggested example is now only a suggestion (the gradient-descent lesson
kept a shortened cricket example because its brief still said cricket; asked again, the
planner chose "eight records: gradients plus four, minus two…"); and a beat that ends by
asking gets three seconds to answer. The reviewer is stricter than before (scores of 2
where the old lessons got 3) and marks all three new lessons "needs review" for content
points a person should read.

One process slip in this round: the server was restarted once while the real-job test was
red. The chain ran the restart after `pytest | tail`, whose exit status is `tail`'s. The
failure was a stale expectation in the test (seven thinking pauses where it expected
one), the job itself had run to a playable video, and it was fixed and re-run at once —
but the rule is to gate on the result, and `set -o pipefail` or a separate command does.
