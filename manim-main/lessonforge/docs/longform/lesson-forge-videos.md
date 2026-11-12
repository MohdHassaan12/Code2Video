# Videos from Lesson Forge plans (2026-10-16)

Status: record of the first batch; the code it describes is live.

Lesson Forge is the lecture planner in `lesson-board` (`server/forge`, `/api/forge/v1`): `POST /plan` returns
lectures (story, running example, keypoints with brief, moves, goal, check aim) and `POST /build` streams each
keypoint's sections (narrate, card, mark, graphic, image, source, check). This repo now turns those into videos.

## How to run it

```
LESSON_FORGE_URL=http://localhost:8010 LESSON_FORGE_USER=<id> \
lessonforge forge "Solving linear equations" --level "Class 8" --save runs/t01            # plan, build, video
lessonforge forge --plan runs/t01/plan.json --save runs/t01 --check                       # stop after script review
lessonforge forge --plan runs/t01/plan.json --save runs/t01 --words writer                # our writer, Forge's plan
```

`--save` keeps `plan.json` and `built_N.json`, so a second run never asks Forge again. `--check` stops after
the verify stage (`brief["stop_after"] = "verify"`), which is the cheap way to read every script before paying for
voice and render; the stage store keeps the script and its review, so the full run that follows does not pay twice
(`stop_after` is in `store._NOT_CONTENT`).

## Two ways to get the words (`--words`)

- `forge` (default, `harness/forge.py`): Forge's sections become beats directly. Narrate sections lose their
  greeting; a card becomes narration plus steps; a check becomes a question beat with a 5 s pause and quiz, then an
  answer beat with the leading praise stripped; plots become our `graph` figure, number lines our `number_line`,
  any other graphic is drawn from its SVG (kit CSS inlined, `standalone_svg`) as a `picture`.
- `writer`: Forge's plan becomes a writer brief (`forge.writer_brief`: story, running example, each part's brief,
  opening, check aim and moves as notes) and our own writer writes the script.

Compared on four topics after the review: the writer path scored as well or better on three of four and wrote
shorter scripts (420 to 465 words against 520 to 690). Forge's own words were arithmetically right (claims are
checked with code) but the reviewer rated pedagogy 1 to 2 on most: an opening question never answered, narration
pointing at pictures that are not on screen, "your turn" answers never revealed, the same example narrated
several times.

## What the first batch showed (14 videos, Classes 6 to 10, about 2.7 USD for the renders)

Frames were read for every video; nobody has listened to them yet.

- Forge's `tape` graphic drew "3x + 5 = 14" as one total ("Total: 22"): left out (`forge.UNTRUSTED_LAYOUTS`).
- Forge's graphic text lists "marked: Base (3) at x = 0" for points it drew; those lines are no longer steps.
- The `graph` figure numbered a 0.5 step with no decimals ("0 1 1 2 2"): axes stepped under 1 now show one place.
- Content errors the review did not catch: "Sine = Cosecant" on screen (trig), "(3, 20.4)" for (3, 29.4) in a
  line of working (free fall). A wrong statement on a card is not a claim the critic checks with code.
- Forge-direct lessons are mostly text and flow charts; Forge's lists and flows become small pictures with tiny
  type. The writer path's model-written scenes move but can be wrong (dots not on the line in the taxi lesson).
- ~~The writer path does not know the `graph` figure~~ (told since 2026-10-20; see the end of this file).
- A delivered mp4 with the subtitle and chapter tracks did not play in the project's file preview; deliver a copy
  with only the video and audio streams (`-map 0:v:0 -map 0:a:0`, H.264 Main, AAC, `+faststart`).
- Forge-side issues sent to the lesson-board thread: tape graphic, plot facts missing an asymptote and a hole,
  SVG not standalone, your-turn cards with no answer, greetings and praise in feedback, openings not answered,
  repetition across keypoints, prices in "$".

## Better explanations (2026-10-16): best-teacher rules and an explanations database

The owner after the first batch: "it is not good explanation", "Research best teachers and gen better scripts",
"Get the best explanations database and approaches to improve the videos".

- `harness/skills/teaching-script/explainers.md`: 17 rules from Muller (refutation videos, d = 0.79),
  Sanderson, Khan, Feynman, Mayer's multimedia principles, Rosenshine and the worked-example and prediction
  studies: open on a situation, recall the prerequisite, say the mistake early and break it, predict before a
  reveal, the formula as a name, worked then faded then alone, a new case gets a new picture, one NCERT line near
  the end. Read by the writer (`skill.for_writer`), not by the card, so no card is rebuilt; it IS in
  `skill.version()`, so every stored script and review is written again once (a billing change).
- `harness/explanations.py` (`HARNESS_EXPLANATIONS`, default on; off in tests): attaches to the brief, by code
  and with no model call, (a) the checked NCERT row for the concept (`key_idea` with its misconception,
  `prerequisites`) from `<workspace>/library/explanations/*.csv`, matched only when the topic names the concept
  (two shared words, class within one), and (b) the most common real student mistakes for the closest maths skill
  from the Eedi Misconceptions Graph (CC BY 4.0, credited in the brief), matched by IDF-weighted overlap of at
  least 0.45. Unmatched topics get nothing: a wrong expert explanation is worse than none. Lecture titles are NOT
  passed: a Hindi title leaked Hindi into an English script.
- Three videos remade with both (trig, pressure, fractions; 1080p): every script now opens on a situation, meets
  the mistake early, asks a prediction and answers its question; the trig triangle changes with each case.
  The critic's scores barely moved (trig 1/1/1, fractions 4/2/3/2) and are noisy. Faults still seen in frames:
  words about one triangle over another for one beat, faint ghost lines of the previous picture, an overlapping
  "20 N" / "0.01 m²", a blurred earlier scene behind one chapter.
- Gaps: no open science misconception bank; Classes 6 and 7 missing from the NCERT table. Source survey and
  licences: the project share, `whiteboard/video-principles/explanations-database.md`.

## Questions that teach after a wrong answer (2026-10-17)
From the research guide: a feedback ladder (nudge, then the answer with its reason, then a way back to where the idea
was shown), "How sure are you?" (sure and wrong marks a misconception), and every question tagged with its concept
and, where the concept base names one, the student mistake a wrong option stands for. Data only: no model call, no
change to the video. Details in `lessonforge/CLAUDE.md` (2026-10-17). Not built from the guide's list: per-learner
choice of worked example vs try-first in the video player, spaced review of missed questions, a transfer question
without the picture, and A/B judged on delayed retention.

## What the frames of the three remakes showed, and the fixes (2026-10-17)
LGLG: "Yes the visuals are not good". One frame per sentence of trig, fractions and pressure. Fixed in code, each
with a unit test: the figure follows the beat that SPEAKS its numbers, a right triangle's "?" becomes the side once
the voice states it, a scaled copy shows the triangle it came from (shaded, dashed, true size), formulas are set in
a sans face at the words' size for new lessons (look key `math`), units after a number are upright, and a model-
written scene whose labels rest on each other between its stages is refused. Trig and fractions were rendered again
from their own audio (no model call). Open: listed in the roadmap §5c.

## 2026-10-20 — the other 11 remade through the writer path
LGLG: "Use credits but try to improve the system to tackle the bugs in future". The 11 Forge topics not remade
before were made again with `forge.writer_brief(plan, L, card=True)`, edge voice, 1080p (`/home/user/work/v10`),
about 0.25 USD each. Before they were made the writer learnt the `graph` figure; after, the survey of the new
lessons drove four code fixes (CLAUDE.md, 2026-10-20) and the graph and number-line lessons were filmed again from
their own audio. Files: `/mnt/project-files/whiteboard/videos/forge/v5/`.
