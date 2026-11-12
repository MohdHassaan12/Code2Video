# 11. Composition tried before it is paid for (2026-10-10, evening)

The owner, 17:40, while the new frame was going in:

> Render previews, detect problems, apply localized fixes, rerender, and run regression tests. Add vision-based
> assessment for issues that bounding boxes cannot detect.
> 04 Adaptive composition. Learn or infer which layouts work for different content types, screen sizes, explanation
> complexity, and teaching styles. Split scenes when necessary rather than forcing everything into one frame.
> Some ideas for composition

Until that evening every decision about a lesson's screen was made blind. It was checked only after the narration had
been bought and every chapter filmed, by thirteen checks that passed on a lesson with six faults a viewer sees
(doc 10 §7) and by one frame per beat looked at afterwards. This document is what was built against the owner's note
the same evening, what the numbers said, and what is still only a report.

**State (2026-10-12, afternoon):** a drawing shown whole is drawn part by part from the sequence of its SVG's parts (§8).
**State (2026-10-12):** a beat about another situation gets a drawing of its own (§6), and posters get the look of paint on paper (§7); both live.
**State (2026-10-11, 23:00):** §1 to §5 are in `src` and live. Of §6, one fix is live (a picture taken off a beat it has
nothing to do with), one was tried and refused (rewriting words), and the cause behind it is cured upstream (the
writer is told what its drawing holds). §7: repainting stays off; an edge hint did not rescue it.

## 1. A lesson as stills, in seconds (`longform/preview.py`)

A beat is laid out ONCE, with every step in its place, before anything moves. So how it looks does not depend on the
voice. With manim's `-s` every animation jumps to its end, and the same code that films a chapter saves the screen
instead: after each step, at each pause, at each beat's end (`runtime.LessonScene.still`, only when
`LESSONFORGE_STILLS` names a folder). A lesson with no narration yet is given a timeline of estimated lengths, which
changes when a step appears and nothing about where.

- seven chapters: 4 to 14 seconds (a drawing with a dozen close-ups: up to 85); no voice, no model, no money;
- each beat's end still carries what the layout itself measured (`GuidedChapter._measure`): the real point size of
  every line of words (`Text.font_size` follows scaling, so a line shrunk to fit says the size it ended at), the
  picture's share of the frame, and how much of the room it was given it spans;
- `preview.measure` turns that into findings with the beat they are in: type under 28 points ("small": under 9 on a
  phone held upright, where the frame is about 203 points high) or under 22 ("unreadable"), a picture that spans
  under 0.6 of the room it was given (not its share of the frame's area: a strip of fraction bars is thin by nature
  and still reaches from side to side), and the renderer's own checks (outside the stage, counted collisions).

## 2. The regression test (`scripts/layout_regress.py`)

Every finished lesson in the workspace previewed with the renderer as it stands, compared with a kept baseline: a
lesson regresses when it has more chapters that could not be previewed, renderer notes, things outside the stage or
counted collisions than before. 43 lessons, 605 beats, 2,004 lines of words: 13 minutes on this machine.
It also prints the frame in numbers, which is how the next section was found.

## 3. What the numbers said, and the two changes they led to

| over 43 lessons, in the stage frame | as it went live at 17:55 | words one at a time, working stays | … and code-drawn pictures enlarged |
|---|---|---|---|
| beats laid out as a column of small lines beside the picture | 290 of 605 | 35 | 35 |
| lines of words under 38 points (12 on a phone) | 617 of 2,004 | 207 | 193 |
| lines under 30 points | 20 | 20 | 20 |
| code-drawn pictures spanning under 0.6 of their room | 46 | 46 | 0 |
| beats whose picture has under 16% of the frame | 98 | 98 | 59 |
| lessons with a fault the first column has not | – | 0 | 1 |

**Words one at a time; working stays** (`look`: `working: pinned`, `GuidedChapter._pin`). One formula anywhere in a
chapter had made every beat of that chapter a column of 30-point lines. Of those 290 beats, 44 work nothing out
themselves: they now show their lines one at a time like any other beat. The rest keep their formula lines, which
grow as before, and show their words one at a time ABOVE the working, at 40 points. Working that does not fit under
the words at full size is not shrunk: it goes on to a second screen, and the first leaves. No real lesson needed
that (0 of 224 beats); it is proved by a made-up beat with seven formula lines. A recap beside its picture still
lists (what a recap lists is meant to stand together).

**Enlarging is tried, never assumed** (`look`: `pictures: fill`, `harness/compose.settle`). A model-written scene
drawn two units wide stood two and a half units wide in a stage of thirteen, because enlarging one had once made
parts of a scene touch. Now a lesson with code-drawn pictures is previewed twice before its speech stage, as it is
and with those pictures enlarged to the room the frame has (their lines thickened with them), and gets the enlarged
ones only when that preview shows no fault the other has not. Of 43 lessons one is worse enlarged (a scene whose own
"2" touches its "9 × 9"); the trial leaves exactly that one as it was.

What is still small: 14 formula lines too WIDE for the working column (20 to 28 points). A second screen does not
help a line that is too wide; the working would need more of the frame's width than the column has.

## 4. In the pipeline

`service._run`, after the review and the look, before the speech (stage "compose", "Trying the layout" in the app):
`compose.settle` previews the lesson, settles `pictures`, measures, and (unless `HARNESS_COMPOSE_LOOK=0`) has a
vision model look at each beat's end still. It writes `composition.json` into the lesson's folder and lines into the
job's log. It runs as advisory: no failure in it can cost the lesson. About 10 to 30 seconds and two cents a lesson.
`HARNESS_COMPOSE=0` switches it off.

## 5. A look for what no box can find (`vision_review.assess`)

One look per beat, at its end still, with the beat's narration and the lines the script put on screen, for seven
kinds of fault: the drawing is of something else than the voice is about; the words speak of a thing that is not in
the drawing; print inside the drawing too small to read; half a drawing; a line that is a note to the animator;
crowded; lost in an empty frame.

Tried on the three trial lessons of that morning (23 stills, about two cents), whose faults had been found by eye
and listed as open:

| lesson | what a person had found | what the look found |
|---|---|---|
| How a Green Leaf Makes Food | an experiment with half a leaf that the picture never shows | beat 3: "about two halves of a leaf … the drawing shows a complete plant"; beat 6: leaves A to D spoken of, one generic leaf drawn |
| Area of a Triangle | b and h in the drawing, six and four centimetres in the voice; "faint squares" | both, in five beats; and an obtuse triangle spoken over an acute one, which nobody had noticed |
| Newton's Third Law | a balloon task over a foot and a ball | beat 5: "the drawing shows a foot and a ball, but the narration is about a balloon"; and "the red arrow" that is not in it |

It also over-reported: 18 to 23 findings a lesson, most of them not faults. Read on five lessons the next evening,
the open question "what is wrong here?" had been answered by checking the still against the REQUEST the drawing was
made from (eleven "does not show …, as described in the drawing request" on one beat of a drawing that is built up
part by part), by calling a number missing where the drawing prints a letter, by reporting lines that had left the
screen, and by listing the motion of an animation that a still cannot show. Telling it not to changed little.

**Since 2026-10-11 the look quotes, and code checks the quote** (`vision_review.ASSESS`, `findings_of`):

- one question with "same" as the answer in doubt: is the drawing of the SAME subject as the words, or of another
  object or situation (`mismatch`);
- the words that POINT AT the picture ("this", "here", "the dashed line"), copied exactly, with every thing those
  words say is there and which of them are not. A finding (`missing`) stands only when the quote is literally in the
  beat's narration or lines, the thing is named by the quote, and the drawing's own reading does not list it;
- a line that is a note to the animator, copied exactly, and only if it is one of the beat's lines;
- what can only be seen (unreadable print, half a drawing, crowded, lost in the frame) stays an open answer.

| lesson | findings, asked openly | findings, quoted and checked | what they are |
|---|---|---|---|
| Area of a Triangle | 17 to 22 | 5 | "sits on faint squares, with a six centimetre base … four centimetres" (3), a "twenty-four-square-centimetre parallelogram" (1), and in one run the obtuse triangle spoken over the acute one |
| How a Green Leaf Makes Food | 12 to 14 | 2 | the half-leaf experiment and the four leaf pieces, both spoken over the whole plant |
| Newton's Third Law | 1 to 2 | 2 | the balloon over the foot and ball; one false ("put both arrows on one object") |
| Water's Never-Ending Journey | 23 | 0 | (its 23 had all been of the kinds above) |

One thing the first wording missed: asked what a quote "points at", it answered "the blue triangle" for "this slanted
triangle sits on faint squares" and called it there. It is asked for EVERY thing the quoted words say is in the picture.

The drawing's own reading (`vision_review.holds`: things drawn, words printed; one look per drawing, kept beside it as
`holds.json`) is what "is it in the drawing?" is checked against, by the look and by code.

## 6. Acting on what is seen (2026-10-11)

The owner's loop: preview, detect, fix locally, preview again. Tried on scripts of finished lessons, with no narration
and no render, every change read. Trial scripts and outputs: `lessonforge_workspace/pilot/mend/`.

**Kept and live: a picture is taken off the beat it has nothing to do with** (`compose.mend`; `"picture": "off"` on the
beat; on unless `HARNESS_COMPOSE_MEND=0`). Only for a beat with NO picture of its own, over which the look says the
drawing is of another thing. The renderer takes the picture away for that beat, gives its words the frame, and draws
the picture in again with the next beat that is about it, within a chapter and across a chapter's end. The chapter is
previewed again; the preview's own record must say the picture has gone and the layout must be no worse, or the beat
is put back. On seven lessons it acted on six beats: two plainly right (a balloon to try at home, over a foot and a
ball; a rectangle to draw on squared paper, over the proof diagram), four that could go either way (a summing-up
shown as its list of lines, not beside an abstract scene), none worse. The frame reviewer after the render is told
such a beat holds words alone on purpose.

**Tried and refused: rewriting the words** (`HARNESS_COMPOSE_MEND=words`, off). A beat whose words speak of things
its drawing lacks went to the reviser with the drawing's reading; the lesson was previewed again and the beat looked at
again fault by fault (`vision_review.recheck`: each earlier finding by its number, cured or still, then anything new);
kept only with something cured and nothing new. Thirteen rewrites on three lessons passed. Read one by one:

| what the rewrite did | beats |
|---|---|
| tied a number to the drawing's letter, dropped "faint squares", put "imagine" before another case | 7 |
| changed nothing that matters, or read awkwardly | 2 |
| read the answer to the lesson's own question off the picture ("Picture mein arrow … ball pushes foot") | 1 |
| stated the conclusion ("only half") before the proof it comes from | 1 |
| talked about the caption, and dropped that chlorophyll captures sunlight | 1 |
| turned "chlorophyll captures sunlight" into "works with sunlight" because the drawing does not show it | 1 |

Four of thirteen worse, each "cured" by the second look. A judge that sees a still and the new words cannot see what
the lesson lost. (An earlier keep rule, "fewer findings on a second open look", was worse still: the same still gave
two findings once and six the next time.)

**The cause, cured upstream: the writer is told what its drawing holds** (`card.add_holds`, `holds_block`;
`HARNESS_PICTURE_HOLDS`). It had been told what the drawing was ASKED for. Its block now ends with what is in the
finished drawing and what is printed in it, and three rules: speak of a thing as being in the picture only if the list
has it; tie a number once to a letter the drawing prints; anything else is imagined, drawn or tried, never looked at.
Two lessons written again from their own brief and card (script only, 9 cents each):

| | places where the words point at something the drawing lacks | beats about another situation than the drawing |
|---|---|---|
| Area of a Triangle, as first written | 4 | 0 to 1 |
| … written with the reading | 0 | 0 |
| How a Green Leaf Makes Food, as first written | 0 | 2 |
| … written with the reading | 0 | 3 |

So it cures what it was built for (the triangle's "faint squares", "six centimetre base") and not the other fault: a
lesson whose experiment or task is about something its one drawing does not show. Both new scripts ran over their
word budget (420 and 395 for "at most 343"), as scripts did before.

**A drawing of its own for a beat about another situation (2026-10-12, live).** The remaining `mismatch` findings were
beats about something the lesson's one drawing does not show. Such a beat is now offered to the owner's drawing
service the way a lesson's model-written scenes are (`compose._own_drawings` → `writer.drawings_for_scenes`): a
small model writes the request from the beat's words, the drawing is taken apart, looked at and placed. Before it is
kept, the drawing itself is checked against the beat's words (`vision_review.fits`: the request once drifted to
another experiment) and, when the beat asks its learner something, for whether it already tells the answer
(`vision_review.tells`: one question, "list what could tell, then decide; in doubt it tells"). A drawing that tells is
asked for once more without what gave it away. The beats after it go on showing what they showed before
(`_keep_showing`). A beat that gets no drawing and never had a picture is shown without one, as before.

| beat | what the service drew | kept? |
|---|---|---|
| leaf: draw four leaf pieces A to D | four leaves, each with its condition (control, dark box, no CO₂ flask, variegated) | yes |
| leaf (second script): the same task | four paper leaves A to D on a sheet, a pencil | yes |
| Newton: blow up a balloon, which way will it go? | a balloon with an arrow "Predicted direction of motion" | no: it tells the answer |
| … asked again | an inflated balloon held by its pinched neck, the air inside | yes |
| triangle (second script): a 6 by 4 rectangle and its diagonal on squared paper | exactly that, one triangle shaded, 6 units, 4 units | yes |
| leaf: the half-leaf experiment (two scripts) | the service failed its own drawing, four requests of four | none |

**Not built**

1. **Working too wide for its column**: give the working the frame and the picture a corner, for that beat (14 lines).
2. **A second render for a phone held upright.** The boxes are arithmetic (`look.picture_boxes`).
3. **Learning.** Every lesson leaves `composition.json` (tried, measured, seen, mended). Nothing reads it yet.

## 7. Repainting a drawing (see doc 10 §6): corrected on 10 October, settled on 11 October

The morning's note of 10 October called two repaintings of the photosynthesis poster good. Run through the check that
was to be its gate, they were not: both had lost the three water drops at the roots and the three oxygen bubbles, and
one had gained a cloud. `harness/repaint.py` was built with the gate (a thing-by-thing comparison against a numbered
list of what the original holds, small lost things put back from the original, several seeds), and is OFF.

**The library's twelve posters through the gate (11 October, GPUs free, 240 s, plain image-to-image).** They are three
distinct drawings. The water cycle was accepted on the first try (share 0.6), the leaf poster on the third (0.54), the
ray diagram rightly left alone (a figure, not a scene). The gain is modest; on the accepted leaf poster one of three
water drops is gone and the soil has dark specks.

**With an edge hint (the first approach of `11_assets/styling_survey.md`).** Z-Image-Turbo with its "Fun ControlNet
Union 2.1" patch (apache-2.0 as read on its model card; ComfyUI core nodes), hint from the scene's own edges or the
scene in grey, 56 pictures of two posters at 4 to 9 s each (`pilot/look_live/controlnet_try.py`, sheets in
`pilot/look_live/cn/`):

| repainted share | what comes back |
|---|---|
| 0.75 to 0.8 | the original with a little texture; small losses (the river no longer blue, a third cloud behind the sun's rays) that the judge passed as SAME twice |
| 0.9 and 1.0, edges | a hand-made crayon look, and the sea green, the soil a meadow, a second sun, extra clouds |
| 0.9 and 1.0, grey | shapes held, colours gone (grey soil, green sea) |

An edge or grey hint carries no colour, and the prompt may name nothing in the picture (naming a thing made the model
add more of it). There is no setting in the sweep with a plainly richer look and the content whole, and the gate let
two small losses through. So: no repainting in lessons.
Not tried: an instruction-based editing model (ranked lower in the survey because it redraws the subject).

**The look that cannot lose or add anything: live since 2026-10-12** (`harness/paperlook.py`, after the owner's
"Start making"; `HARNESS_DRAWING_LOOK=0` leaves drawings as drawn). Arithmetic on the scene layer of a poster: a
wobble of at most about two pixels, pigment pooled on the darker side of edges, blotchy washes, grain, a little
warmth; arrows and labels laid back unchanged; made once per drawing (about three seconds) and kept beside it. A
drawing in one piece is left as drawn. Two lessons previewed with and without it: no fault either way, the same
stills, softer washes and darker edges (`pilot/own/paper/frames_plain_paper.jpg`, `crop_source.jpg`). Its first
version darkened a plant's thin cream roots into the soil; pooling is now on the darker side of an edge only.

## 8. A drawing that draws itself; the card that showed the narration; a voice on this machine (2026-10-12)

The owner: "the visuals are also static. We need to find a way to paint the images … take the SVG and divide the SVG
components into JSON. Different parts of the visual should be coming in a sequence as JSON, which contains the text
and parts of the SVG. Then you take the pattern and style it."

**The sequence** (`harness/sequence.py`). A drawing from the service is an SVG; every line, shape and label in it is an
element. A headless browser lays it out and one script reads, for each element: its outline as points
(`getPointAtLength`, each subpath a stroke of its own), its box, its colours, its stroke width, whether it is dashed,
and the piece of SVG it is. Glyphs are joined into labels (`typeset.labels_of`) and carry the words `typeset` read.
Code orders the parts (the SVG's order; an arrowhead after its line; a label after its shape) and writes
`<drawing>/sequence.json`: `{"parts": [{"n", "kind": stroke | fill | text, "svg", "text", "box", "points", "closed",
"stroke", "fill", "width", "dashed", "length"}, …]}`. Four drawings of today's lessons: 23 to 35 parts each, 0.4 s each.

**The painting** (`figures.PictureFigure.paint`). In sequence: a stroke is drawn along its outline in its own colour,
a dashed line dash by dash, a filled shape outlined and then filled, a label arrives after the shape it names; then
the finished picture, exactly as the service drew it, settles over the pen-work. Two and a half to five and a half
seconds, beside the beat's first words. Frames from real drawings: `pilot/paint/frames/angles_c1.jpg` (a lesson made
that morning, with its own audio), `balloon.jpg`, `rectangle.jpg`.

| | before | now |
|---|---|---|
| a drawing shown whole arrives | fades in, 0.5 to 1.5 s, and stands still | is drawn part by part, 2.5 to 5.5 s |
| the last frame | the drawing | the same drawing, pixel for pixel |
| a preview of stills, an older lesson | the drawing | the same (no painting) |

Not painted yet: a poster that is built up by its arrows (its scene still fades in), an anatomy drawing shown by
close-ups, a drawing re-laid in panels. Not done: tying WHICH part is drawn to the words being said (the whole
drawing is drawn at its first appearance, in the SVG's order), and a hand-drawn STYLE that stays (the pen-work has a
slight unevenness and gives way to the exact drawing).

**The card.** A pause with no question card of its own put the narration's last sentence on screen as its card: 70
of 211 pauses in 46 lessons. It now shows the beat's own line for the screen (`runtime.screen_question`).

**The voice.** When the owner's speech service cannot be reached, a Hindi or Hinglish lesson is narrated by the
Kokoro model on this machine (`kokoro:hf_alpha`), as an English one already was; the basic voice comes after it.
See CLAUDE.md of the same date for the two faults a recogniser heard in it and how they were cured.


## 9. Drawn with the words (2026-10-12, evening)

What section 8 left undone, and what a reference lecture beside ours made plain (doc 12): the drawing drew itself in
its first five seconds and then held everything the lesson was going to reach. In the lecture on the same proof the
board has only the triangle for 53 seconds; the line through the top corner is drawn when it is spoken of, each equal
angle when it is named, and the sum is written last.

**How.** Three pieces, each of which does one job.

1. *Code says what the THINGS in a drawing are* (`sequence.things_of`): a line with the arrowhead on it and the
   words at it; an angle's arc with its number; the hatching under a mirror with the mirror; a ray that the SVG wrote
   as two pieces with an arrowhead between them. The proof drawing's 23 parts are 8 things; a ray diagram's 48 are 10.
2. *A model that sees the drawing and reads the script says only WHEN each thing is drawn* (`sequence.plan`): the
   drawing with a red tag on every thing, the things as a list, the words beat by beat with every moment a line
   comes up numbered S1, S2, …. It lists first the questions the words leave open and what in the picture would tell
   their answer, then a step for every thing.
3. *Code makes the plan agree with the drawing* (`sequence.settle`): the first big thing the SVG draws is there
   when the drawing arrives; a mark is not drawn before the line it is drawn on; what would tell a question's answer
   waits for the step where the words give it; a card is never empty.

The steps then carry `"draw": [part numbers]`. The renderer holds those parts back (`figures.PictureFigure.hold_back`),
draws each when its step's words come, beside the words and never into the next line's
(`runtime.GuidedChapter._draw_with`), and works out from the whole lesson what earlier chapters have drawn
(`_drawn_later`: a chapter is a render of its own). While parts are held back the figure is its pen-work; when the
last one is there the finished picture takes its place.

**What each rule came from** (five lessons made that day, planned and filmed again from their own audio):

| seen | rule |
|---|---|
| the model read our red numbers 1 to 8 as the drawing's own printed "1" to "5" and planned other things than it described | tags carry a hash sign (`#3`), and the prompt says a bare number is the picture's own |
| asked about 18 parts one by one, it described each in our own list's words ("small black curve") and scattered them | it is asked about THINGS, and for its own name of each ("the angle at B") |
| the small model that judges frames put the proof's line on the board at the start in two of three answers, and held an arc back for twenty steps as "showing the answer" | `PLAN_MODEL`: a stronger model for this one call (about 2 to 4 cents a drawing against 0.3) |
| one plan held the triangle back and showed its labels around nothing | the first big thing is there when the drawing arrives |
| three lines that meet in a point each waited for the last; a whole second panel waited for its last drop of water | only MARKS wait, and only for a line they are drawn ON, away from its ends (`_rests_on`) |
| the reflected ray was drawn under "Which outgoing ray?" | questions and what tells their answer are listed first, and code holds those things back |
| "what tells the answer" came back as every arc at an angle that was asked about | the prompt says a mark that shows WHERE a question is about tells nothing |
| a highlighter marked a label before any step had drawn it; bringing the label in with the mark put a "5" beside a line that was not there, and the next chapter did not have it | a mark on a label that is not drawn yet is not shown; what is on the board is decided by `draw` alone |
| nearness measured between corner points missed a mark that starts on the middle of a long line | nearness is to an outline's segments |

**What it looks like** (frames in `pilot/words/filmed/`): the ray diagram's lesson opens on the mirror alone; the
point, the normal and the incident ray come as each is named; under "Which outgoing ray?" there is no reflected ray,
and it is drawn 81 seconds later (at 90 s) when the voice says "r equals thirty degrees". In the proof, the parallel
line is drawn at "Line through A" (36 s), the two angles beside it at "Left angle equals B" (62 s) and "Right angle
equals C" (71 s), and the arc of the straight angle at "One straight angle" (83 s).

**Where it is not used.** A drawing with more than 30 things or fewer than 3 (drawn at once, as in section 8); a
drawing the words begin with all of (the plan holds back fewer than two things); a poster built up by its arrows and
an anatomy drawing shown by close-ups (they have their own way); a lesson made before today (its steps bring
nothing). `HARNESS_DRAW_WITH_WORDS=0` leaves it out.

**Not done.** The narration does not yet say what is being drawn ("now a line through A"): the writer still writes
about a finished picture, and the plan is fitted to its words afterwards. A plan is one model's answer: it is kept
consistent by code but not checked by a second look.
