# 14. The annotation harness: what a hand adds to a drawing while the voice speaks (2026-10-12, evening)

The owner, watching "Laws of Reflection": "the visual is not matching audio … we can't able to see the 30 deg 40 deg",
then: "the image is not being annotated; there should be an annotation harness on top of the SVG which will ideate the
annotations, not just stale text", and: "it should be intelligent enough to update and change so it is not giving bad
annotations or overlapping things; … the current image SVG reference and minimal inputs; the starting and ending time
stamps for synchrony; … extendable for any topics; come up with generalized frameworks."

## 1. What was wrong, in numbers

`pilot/values/said_not_shown.py` (no model) on the six lessons made that day: the voice says 39 values; **37 are not in
the picture**, and 11 are not on screen at all during their beat. In the reflection lesson the drawn ray stands at
exactly 45° while the voice says 30°, 40° and 50°, and the one line that showed "30 degrees" in the opening was on
screen for 0.28 s. The cause is the order of work: a drawing is asked for before the script exists, so it cannot hold
the script's numbers. Asking the drawing service for the same diagram WITH the numbers was probed first: of three
requests one failed twice, one came back without the values, one was good. Not reliable enough on its own.

## 2. The framework (`harness/annotate.py`)

Inputs: a drawing's SVG as its sequence of parts (doc 11 §8), and the lesson's words with the moments its lines come
up. Nothing about a topic.

| step | who | what |
|---|---|---|
| ideate | a model that sees the drawing with its things tagged and reads the words | FIRST every value the voice says about the picture, each with the words that say it and the thing that MEASURES it (or the two lines whose angle it is); THEN the hand's gestures, each on a tagged thing with the words it comes with |
| keep it honest | code (`honest`) | a known kind, on things that are on the board by then, a written NUMBER that the voice says in that beat, words that are literally in the narration; a value the voice only asks is not written; one gesture at a step |
| place | code (`KINDS`, `Board.write`) | from the drawing's geometry and from what STANDS ON THE BOARD AT THAT MOMENT: the eight places round a thing, the clearest wins; further off with a leader line when all are taken; an angle's arc in the clearest sector at the clearest radius |
| check | code (`problems`) | writing on other writing, on the drawing's own words, across its lines, outside the picture |
| change | the model looks at its own annotated drawing, mark by mark (`improve`) | "wrong thing" moves the mark to the thing it names, "unreadable" writes it on the side it names, "pointless" drops it; kept only when code finds no more wrong than before |
| time | the renderer (`runtime._marks_due`) | each mark comes with ITS OWN words (not with its step's line), never before what it stands on is drawn; start and end go into the chapter's record |

A mark is data on its step: `{"id", "kind", "slot", "life", "say", "text", "on", "needs", "prims"}`. `prims` are
**paths and pieces of text in shares of the drawing**, so a renderer draws only two primitives and the same marks draw
in the film (`figures.PictureFigure.annotate`) and in the browser player (doc 13). A mark that `stays` (a value, an
angle, a span, a name, an equal-mark) takes a slot: a new value on the same thing replaces the old one, and everything
standing is wiped when the next chapter begins (a teacher wipes one example's numbers before the next). A gesture (a
ring, a line gone over, an arrow, a cross, a tick) is there until the hand's next gesture or the end of its beat.

**A new kind of mark is one entry in `KINDS`**: its line for the model and its function that places it. The prompt is
assembled from the registry; neither renderer changes. Ten kinds today: value, angle, span, label, equal, ring, trace,
arrow, cross, tick.

## 3. What it did on four topics (the lessons' own scripts and audio; frames in `pilot/annot/`)

| lesson | marks | what is on the picture now |
|---|---|---|
| Laws of Reflection (English) | 16: 7 values, 1 angle, 5 traces, ring, cross, equal | "30°" at *i* when it is said, "30°" at *r* with the answer, "40°" / "?" / "35°" for the next cases, the 40° between ray and mirror surface marked where the drawing has no arc, a cross on the wrong reference line, the normal gone over when it is named |
| Angles in a Triangle (English) | 19: 10 values, rings, traces, cross, equal | "= 50°" beside angle 2, "70°" at angle 3, "60°" at angle 1 when the answer is given |
| Why Water Pushes Up (Hinglish) | 8 | "8 units" at the first balance's pointer, "6 units" at the second, "2 units" at the displaced water |
| Three Paths of Heat (Hinglish, no numbers) | 11: label, rings, traces, 3 ticks | "hot end" written at the rod's end; the conduction arrow, the rising air and the radiation arrows gone over as each is named; a tick at each in the beat that sorts them |

Each took two looks by the model (ideas, then the check of its own picture): 6 to 8 cents a drawing in that first trial; about 4 cents a drawing when measured on the nine drawings of the final run (0.39 USD).

**The final code on the five annotated lessons in the app's list** (`pilot/batch/refilm_marks.py`; one frame a second
after each mark begins, every sheet read; `pilot/annot/listed/<run>/`): 67 marks on film (Laws of Reflection 22,
Angles in a Triangle 20, Three Paths of Heat 13, Why Water Pushes Up 9, Magnets Push and Pull 3), all checks pass, no
note from the renderer. The first reading of those sheets found five faults (section 4, the last five rows); they
were cured in code and the two lessons whose IDEAS were affected were ideated again (about 0.21 USD). What I would
still call imperfect on the final sheets: a ring round a printed LABEL where the thing itself was meant (several
times: "stone", "metal rod", "Pencil"), and "hot end" written across the flame's edge.
Each filmed lesson has `output/annotations.json`: every mark with its start and end on the lesson's clock and its
primitives. The heart lesson is not annotated (its drawing is shown in close-ups).

**The placer under load** (`pilot/annot/fuzz.py`, no model, all 33 drawings in the library a pen can follow, 583
things): at a lesson's load (four values standing, a gesture at a time) code finds 11 of 294 marks wrong (3.7%: nine
written across a line of the drawing, where its plate keeps it readable; two on the drawing's own words). With a value on
EVERY thing at once, 16%.

## 4. What each rule came from

| seen | rule |
|---|---|
| asked for "annotations", the model gave four | it lists what is HEARD first; every value it heard and found a thing for is written, by construction |
| "30°" written on the incident ray, not at the angle | "measures": the mark that measures it, not a neighbouring line |
| the opening's 30° stood beside the last example's 50° | what is written belongs to its chapter; wiped when the next begins |
| a wiped value three chapters back still pushed new writing away | a place is judged by what stands on the board at THAT step |
| the voice says "thirty degrees" in its first sentence, before the mirror is drawn; the arc and its "30°" hung in the air | a mark drawn early waits for the lines it is drawn on (`sequence._rests_on`), and a mark is never made before the parts it `needs` |
| a value said in a beat's last sentence was written in a jump when the last line arrived, and a ring left six seconds early | the marks' track runs to the beat's true end (found by the filmed test) |
| the record said a ring left at 6.0 s and a value was written at 10.3 s; the frames showed the ring at 6.5 s and no value at 11.5 s | nothing is added to or taken off the picture while a beat runs: a beat's marks are on it unseen before its first frame, and only what is seen changes (`prepare_marks`, `sweep`); the filmed test counts red ink in frames cut at the recorded times |
| a pulled value was refused: "a number the voice does not say in that beat" | the number is checked against the beat that SAYS it, not the beat it is drawn in (found by a unit test) |
| four fair values called "on the drawing's lines" | a line through the writing's middle counts, one that grazes its edge does not |
| "8 units" drawn as a length | "units" is not a length unit |
| a line gone over in solid red hid its dashes and arrowhead | a trace is a broad see-through pass |
| a ring came 1.5 s into a lesson and hung in the empty place where the stone was drawn two seconds later | "drawn" means the pen has finished: a mark waits for the end of the arrival's pen-work, or of the step's that brings the part it stands on (`figure.pen_seconds`, `settled` in `runtime._marks_due`) |
| a ring round the displaced water ran through the "2 units" written beside it at that step; rings round two angles ran through their "30°" | a gesture that would run through what is written is left out (`annotate._through` in `lay_out`); where one stands all the same, `problems` counts it |
| the stroke that means "equal" was put on two parallel lines, for "the two lines stay the same distance apart" | a mark that CLAIMS something comes with a sentence that makes the claim (`Kind.heard`, `Kind.never`): for `equal`, a sentence that compares, and not one about parallel lines |
| "40°" at one angle beside the last part's "30°" at the other for two seconds; then "35°" beside the "40°" it had just replaced | a value of the old case never stands beside one of the new: the wipe at a part's first step stays a wipe when a new value follows at that place, and a "?" that replaces a standing value comes with the new case's value, not with its own later words (`lay_out`) |
| an arrow's words ("motion: right") stayed on the picture after the hand had moved on, and had been up for only a second before that | what the hand is still drawing is finished before anything is hidden (`runtime._start_marks`); a gesture that writes words gets 2.6 s before the next gesture (`_marks_due`). Found on the frame sheet of the first lesson the pipeline made with marks |
| a cross on the picture's (correct) reflected ray, for "would draw the wrong reflected ray" | the cross's line to the model: only a thing the words tell the learner NOT to use; never a right thing of the picture, never a wrong result that is only imagined |

## 5. Read for ideas (the owner: "pull and see these repos")

Cloned read-only into `pilot/refs/`; nothing of theirs was run.

| source | what it is | taken | not taken |
|---|---|---|---|
| `alby13/AI-Whiteboard` | a live board a model draws on through tools; 30 semantic element types; hand-drawn canvas renderer | the hand's line: a seeded bow and tapered tremor (`_by_hand`), a ring begun anywhere and run past its start; going over a line as a highlighter pass | absolute pixel coordinates from the model; typed (not stroked) text; it has no clock and no maths |
| `SSHdotCodes/tutori` | a spoken lesson with a canvas board; the model emits steps of `say` + board ops; a layout pass repairs or drops | fuzzing the placer on real drawings with a "realistic" tier (`fuzz.py`); "a value the words name gets a mark, a question gets none" | per-step timing only; its checker grades its own box estimates; hand-written template diagrams by keyword |
| hyperknow.io | a chat study agent with two-minute explainer videos; the site describes no whiteboard or annotation | nothing yet | a marks layer that can be switched off, and replaying a diagram with a mark on the part a learner got wrong, are ideas for the app |

Still to borrow: a mark's drawing time from its length; colour by role (the thing to watch, the result); an ink budget.

## 6. The writer's model

The owner: "this narration or story board model is not good, try better model." The same brief and teaching card
written again (`pilot/values/try_writer.py`, script only):

| | GPT-5.6 Terra (as made) | Sonnet 5.5 | Opus 5.5 |
|---|---|---|---|
| reflection (English), words for "at most 343" | 484 | 367 | 378 |
| "I / me / my" per 100 words | 0.6 | 2.2 | 1.9 |
| "so / now / well" per 100 words | 1.4 | 1.9 | 2.9 |
| magnets (Hinglish), words | 400 | 342 | |
| cost of the script | about 0.19 USD | 0.32 | 0.58 |

Read side by side: Sonnet's lines carry the numbers it speaks ("30°, 60°, or anywhere?"), its English says what is
done ("At O we draw a dashed line at a right angle to the mirror, and that's the normal"), and its Hinglish points into
the picture ("Left mein bar magnet paper sheet ke neeche hai …"). It is the writer's first choice now
(`writer.WRITER_MODELS_DEFAULT`; `HARNESS_WRITER_MODELS` in `.env` puts the order back). Two briefs are a trial, not a
study; the first lessons made with it should be read against these.

## 7. Not done

The drawing's own geometry is not changed: a ray drawn at 45° is still at 45° under a written "30°" (a drawing made for
the script's numbers, or a code-drawn figure, is the cure). The writer does not know the marks exist, so it does not say
"let me mark this angle". Marks are made for drawings shown whole; posters built up by their arrows and anatomy
close-ups are not annotated. A thing is a whole line or shape: "the base from B to C" can only be gone over as the
whole triangle (a stretch of a line between two printed letters is the next kind of place to build). Nobody has watched
an annotated lesson from start to end with its sound.
