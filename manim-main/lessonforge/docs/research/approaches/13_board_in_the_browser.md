# 13. The board drawn in the browser (2026-10-12, a prototype)

The owner pasted a description of "the best stack for an AI-generated Khan Academy-style real-time blackboard tutor"
with the words "see this". Its four layers, beside what this repository has:

| layer in the pasted stack | here today | what is new in it |
|---|---|---|
| 1. An LLM writes voice segments and drawing commands together, in one pass (it names Llama-3.1-8B on vLLM) | The writer writes narration and on-screen steps anchored to spoken phrases; since 2026-10-12 each step also names the parts of the drawing it brings (`step["draw"]`, doc 11 §9) | Script and drawing are still written separately and fitted afterwards. One pass that says what is drawn while it is said is the right aim. Not taken: positions chosen by the model (code owns geometry here, for reasons CLAUDE.md records), and an 8B model as the lesson's writer |
| 2. Low-latency TTS with word timings (Kokoro-82M, CosyVoice 2) | Kokoro is the voice on this machine for English and Hindi; word times come from a recogniser afterwards (`longform/align.py`) | A more expressive voice is worth a trial on the owner's GPUs (doc 12: our pitch range is half the lecturer's). Streaming matters only for a live tutor |
| 3. Strokes as coordinate paths, not pixels (Graves RNN handwriting, MathJax to SVG paths, CROHME) | Every drawing's SVG is taken apart into parts with outlines (`sequence.json`) and drawn stroke by stroke | Handwriting synthesis is English cursive only, with no Hindi and no maths: not taken. A hand-drawn look for shapes is still open |
| 4. The browser draws the board from the audio clock (Excalidraw, Paper.js, canvas) | Nothing: a lesson is filmed to an mp4 by Manim, about twelve minutes | **This is the real difference**, and the data it needs already exists for today's lessons |

## The prototype

`lessonforge_workspace/pilot/board/`: `make_board.py <lesson folder> <out>` turns a finished lesson into
`board.json` (the drawing's own SVG with every element tagged, which elements each part is, when each part is drawn,
the lines of words and when they come, the labels they mark, the sentences as spoken) and `narration.mp3`;
`player.html` is one page of plain JavaScript that draws it. No model is asked and nothing is rendered.

- What is on the board is a FUNCTION OF THE TIME (`audio.currentTime`): a part's progress is
  (now − its start) / its duration, a line is drawn by its dash offset, a dashed line dash by dash, a fill fades in
  under its edge, a label fades in. So it can be paused, dragged to any second and played at 2× with no render.
- It draws the SVG's OWN elements, clip paths and all, so it is exactly the service's drawing at any size: none of
  the differences between pen-work and picture that the filmed version has to manage (doc 11 §9).
- "Blackboard" turns the ink to chalk on slate (an inversion blended onto the board), "Paper" is the drawing as made.
- Tried on "Laws of Reflection" (made 2026-10-12): 48 parts in 6 moments of drawing, 42 lines, 231 seconds;
  `board.json` is 48 kB and the narration 1.6 MB, against a 9 MB video that took a minute to film at low quality.
  Screens at seven moments: `pilot/board/shots/`. Published privately for the owner as an artifact.

## What it does not do

It plays ONE drawing shown whole. Not there: code-drawn figures and model-written scenes (they are Manim objects, not
SVG), formulas typeset as maths (lines are plain text), the question cards and their answers, a second drawing in the
same lesson, captions as a track, an mp4 to download. None of the checks that guard the filmed lesson (bounds, the
layout probe, the frame review) looks at it.

## The decision this leaves with the owner

Whether the browser board should become a second way to play a lesson (for lessons whose pictures are prepared
drawings) or stay a prototype. As a second player it would need: its own page in the app fed by a route that serves
`board.json`, maths set with a browser typesetter, the question cards, more than one drawing a lesson, and a check
that looks at it. The filmed video would stay for everything else and for download.
