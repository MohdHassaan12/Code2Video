# 12. A reference lecture and our lesson, side by side (2026-10-12)

The owner: "try to compare the narration between the baseline audio which we get from Khan Academy and the narration
which is there in the current pipeline generated audio and also compare the visuals of both."

Two pairs on the same topic, in English, were measured from the videos themselves (their sound, their frames) and
from their words. Nothing was asked of a model. The reference lectures are the ones the library already reads as
sources for these topics; they were fetched at 360p for this comparison only and are kept in the workspace
(`lessonforge_workspace/pilot/khan/media/`, not served, not copied anywhere). Khan Academy's videos are licensed
CC BY-NC-SA.

| pair | reference | ours |
|---|---|---|
| triangle | Khan Academy, "Area of triangles intuition" (5:29) | "Area of a Triangle", 2026-10-10, the owner's voice (3:27) |
| fractions | Khan Academy, "Adding fractions with unlike denominators" (7:23) | "Adding Fractions by Making Equal Parts", 2026-10-09, a paid voice (4:18) |

Tool: `lessonforge_workspace/pilot/khan/compare.py <name> <reference.mp4> <transcript.json> <our lesson folder>`.
Numbers: `pilot/khan/out/<name>.json`; frames at the same moments: `out/<name>_frames.jpg`, `out/<name>_start.jpg`.

## 1. How it is said

| | triangle: reference | ours | fractions: reference | ours |
|---|---|---|---|---|
| words a minute, over the whole video | 189 | 143 | 154 | 154 |
| share of the time nobody speaks | 24% | 42% | 30% | 40% |
| silences of two seconds or more | 0 | 8 | 1 | 12 |
| longest silence | 1.4 s | 6.5 s | 2.0 s | 7.3 s |
| "we", "let's", "our" per 100 words | 3.4 | 0.8 | 4.8 | 0.5 |
| "I", "me", "my" per 100 words | 3.1 | 0.0 | 1.9 | 0.0 |
| "so", "now", "well", "actually", "okay" per 100 words | 4.0 | 1.0 | 6.0 | 1.4 |
| times the words point at the picture, a minute | 5.7 | 0.6 | 1.1 | 0.2 |
| four-word runs said three times or more | 24 | 1 | 26 | 2 |
| sentences over 25 words | 11 of 67 | 2 of 38 | 11 of 88 | 2 of 54 |
| reading grade of the words (Flesch–Kincaid) | 6.2 | 7.3 | 5.5 | 6.2 |
| questions a minute | 1.3 | 2.3 | 2.2 | 1.9 |
| range of the voice's pitch (10th to 90th percentile, semitones) | 16 | 12.5 | 15 | 7.5 |
| variation of loudness while speaking | 0.94 | 0.63 | 0.70 | 0.55 |

The pitch and loudness figures come from a simple estimate (autocorrelation, no speech toolkit on this machine):
read them as "more varied" and "less varied", not as measurements to two digits.

What the numbers are the trace of, in the two narrations themselves:

> **Reference:** "So let's look at some triangles here. So that is a triangle and we're given the base and the
> height. And we're gonna try to think about, well what's, what's this area? … Well, to think about that, let me copy
> and paste this triangle. So let me copy and then let me paste it."

> **Ours:** "This triangle has a base of six centimetres and a perpendicular height of four centimetres, so will it
> cover twenty-four square centimetres, twelve square centimetres, or another amount? Make your guess before we move
> anything. Area means the square units that cover a flat shape, and a right angle is a square corner."

1. **The reference is a person thinking aloud while doing something; ours is a text read out.** "We" and "I" eight to
   nine times in a hundred words against about once; a joining word ("so", "now", "well") every twenty words against
   every eighty. Ours has no "I" at all in either lesson.
2. **The reference says what is being DONE to the picture** ("let me copy and paste this triangle"), six times a
   minute in the geometry lesson. Ours describes a finished picture, or does not refer to it.
3. **The reference says the important thing again, in other words, on purpose**; our pipeline removes repetition
   (a rule that came from lessons that repeated whole scenes). These are two different things, and our gate cannot
   tell them apart: it counts repeated runs of words.
4. **The reference never stops.** It asks itself a question and answers it in the next breath. Ours stops the video
   eight to twelve times for two seconds or more (thinking pauses, and gaps between sections): two fifths of our
   running time is silence.
5. **The reference uses easier words in longer, looser sentences**; ours uses shorter, denser sentences with harder
   words ("perpendicular height", "provided it meets the chosen base").
6. **The reference voice moves more** in pitch and loudness than either of our two voices here.

## 2. How it is shown

| | triangle: reference | ours | fractions: reference | ours |
|---|---|---|---|---|
| share of half-seconds in which something on screen changes | 88% | 33% | 81% | 49% |
| longest stretch with nothing changing | 2.5 s | 13.5 s | 5 s | 13.5 s |
| moments something is added to the picture, a minute | 39 | 19 | 30 | 29 |
| share of the frame that is not background (median) | 3% | 8% | 1% | 10% |
| whole-screen changes | none | none | none | none |

(The reference's pointer moves on screen and counts as change: it is how the speaker points.)

Looked at frame by frame (`out/triangle_frames.jpg`, `out/fractions_frames.jpg`):

1. **The reference's screen is being written on nearly all the time**, in thin bright strokes on one dark board that
   is never cleared; ours shows a finished drawing and changes the line of words beside it.
2. **The reference builds the idea by acting on the picture**: it draws a triangle, copies it, turns the copy and
   fits it on, shades one half, and only then writes the formula. Ours showed "Area of Triangle = ½ × b × h" printed
   in the drawing from the tenth second, before a word of the reason (an older drawing; requests now ask for no
   conclusion in the picture).
3. **The reference draws every case it speaks of**: an acute triangle, then an obtuse one with its height outside.
   Ours spoke of the obtuse triangle over the same acute one.
4. **The whole frame is the lesson** in the reference. In ours the drawing had a quarter to a half of the frame, with
   a heading and a column or a line of words.
5. In the fractions pair the reference shows NO picture of a fraction at all: three worked sums written out step by
   step. Ours has more pictures there (bars cut into parts), and a question card every half minute.

## 3. What this says about the pipeline, and what already answers it

| gap | state on 2026-10-12 |
|---|---|
| a drawing stands finished and still | a drawing shown whole is drawn part by part (doc 11 §8) and, since the evening of the 12th, WITH the words: each thing in it when the voice reaches it (doc 11 §9) |
| the words do not say what is done to the picture | not addressed: the writer writes about a finished drawing. It needs the sequence of the drawing's parts at writing time, and steps that name a part to draw |
| a case that is spoken of is not drawn | a section about something else now gets a drawing of its own from the service (doc 11 §6), when the service can draw it |
| the conclusion printed in the picture from the start | requests ask for no formula or result in the picture (`diagrams.VISUAL_RULE`); older drawings in the library still carry it |
| impersonal, written-sounding narration | not addressed. `skills/teaching-script/voice.md` counts orders and screen-talk; it does not ask for "we", for joining words, or for saying what is being done |
| long silences | by design (thinking pauses the player can answer); 40% of the running time is more than the reference's 24 to 30% and is worth measuring per lesson |
| a flatter voice | the owner's voice and the local fallback are what they are; not a script matter |

Two pairs are not a study, and the two of ours were made on 9 and 10 October, before the changes of the 11th and
12th. Section 4 is the same comparison on a lesson made on the 12th.

## 4. A third pair, on a lesson made by the pipeline as it stands (2026-10-12)

Reference: Khan Academy, "Proof: Sum of measures of angles in a triangle are 180" (4:28). Ours: "Angles in a
Triangle", made on 12 October by the pipeline alone (3:33): the drawing is drawn part by part when it arrives, the
voice is the one on this machine (Kokoro), the pause card shows the screen's own line.
Numbers: `out/angles.json`; frames: `out/angles_frames.jpg`, `out/angles_start.jpg`.

| | reference | ours, 12 October | ours, 10 October (the triangle pair) |
|---|---|---|---|
| words a minute, over the whole video | 177 | 115 | 143 |
| words a minute while speaking | 230 | 193 | 246 |
| share of the time nobody speaks | 23% | 40% | 42% |
| silences of two seconds or more | 0 | 11 | 8 |
| longest silence | 1.7 s | 7.3 s | 6.5 s |
| "we", "let's", "our" per 100 words | 2.9 | 0.0 | 0.8 |
| "I", "me", "my" per 100 words | 2.3 | 0.0 | 0.0 |
| "so", "now", "well", "actually", "okay" per 100 words | 3.9 | 1.2 | 1.0 |
| times the words point at the picture, a minute | 4.9 | 0.3 | 0.6 |
| four-word runs said three times or more | 9 | 1 | 1 |
| range of the voice's pitch (semitones) | 14.7 | 7.3 | 12.5 |
| share of half-seconds in which something on screen changes | 92% | 48% | 33% |
| longest stretch with nothing changing | 2.5 s | 8.5 s | 13.5 s |
| moments something is added to the picture, a minute | 33 | 29 | 19 |

What moved, and what did not:

1. **The picture is less still**: something changes in 48% of half-seconds against 33%, and the longest still
   stretch is 8.5 s against 13.5 s. The drawing is drawn in its first five seconds and a highlighter then moves from
   label to label. It is still half of what the reference does.
2. **The drawing is finished five seconds in, and it holds the whole proof.** The parallel line through the top
   corner and the angles 4 and 5 beside it are on screen from second five; the words reach "Line through A" at
   0:40. The reference has only the triangle until 0:53, extends a side, adds the parallel line at 1:33, marks one
   equal angle at 2:13, the next at 2:54, and writes the sum only at 4:01. Nothing is on its screen before it is
   spoken of. Ours draws the parts in the order of the SVG, in one go, not in the order and at the moments of the
   words.
3. **The narration did not move at all**: no "we", no "I", the picture pointed at once in three minutes, and two
   fifths of the running time silent. Nothing built on the 11th or 12th was about how the script is worded.
4. **The local voice is flatter** than the two voices of the earlier pairs (7.3 semitones against 12.5 and 7.5) and
   than the reference (14.7). Nobody has listened to it yet.

Where our silent time is (the lesson's own `timeline.json`, 213 s): the six thinking pauses are 27 s (13% of the
running time), the lead-in before each section's first word and the hold after its last are 21 s (10%: 0.5 s, or 1.5 s
when the section brings a new picture, and 0.6 s after, twelve times), and what is left, about 17%, is the voice's own
pauses between phrases, which is LESS than the reference's 23%. So the voice does not pause more than a person does:
the extra silence is the stops for the learner and two seconds at every section's edge. The reference has neither:
it asks, and answers in the next breath.

So the two changes this comparison asks for are the same two as before, now with a number each to move:
the drawing's parts brought in WITH the words that name them, and a narration written as someone doing the thing
("we", joining words, saying what is being drawn).

The first of the two was built the same evening (doc 11 §9): filmed again from its own audio, this lesson's drawing
has only the triangle and the angles it starts from until the line through A is spoken of at 36 seconds. The
second is not started.
