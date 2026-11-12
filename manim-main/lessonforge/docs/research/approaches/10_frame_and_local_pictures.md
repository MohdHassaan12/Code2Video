# 10. The frame, and pictures made on this machine (2026-10-10)

The owner, 2026-10-10: "There is a flaw in current approach of one side image and another side
text this is not giving good look … research for better layouts and work on improving the visual
research on how we can make better and cheaper visuals any open-source to run locally … they are
very bad", and an hour later: "There is still space in gpus use it or for future when it becomes
free use gpustat to get gpu info."

Three things were done: two web surveys (layout; local models), a new frame layout tried on
copies of eleven finished lessons, and a real run of an image model and a vision model that are
already on this machine. The survey of open-licensed diagrams is doc 09 (the other session's).

**State since 2026-10-10, 17:55:** the layout below IS in `src/` and live for new lessons, with no caption band and,
for lessons whose pictures are all prepared drawings, the light page (the owner's "Yes for all" to the five
decisions; `longform/look.py`). What follows was written that morning, before; §6's verdict on repainting was
corrected the same evening (doc 11 §7). **State when this was written:** the new layout is NOT in `src/`. It is ready in
`lessonforge_workspace/pilot/stage_layout/` (the two files as they would stand, their diffs, the
scripts that render a lesson copy with them) and waits for the owner to have seen frames. The
reviewer's note for it is in `src/` already and does nothing until a render records a layout.

## 1. What the frame looked like, measured

One frame from each of six lessons of 9 October (`10_assets/before.jpg`):

- the heading band is 19% of the frame's height, the band kept free for captions 16%; what is
  left for the lesson is 63% (73% once a prepared drawing made the heading small);
- a 3:2 drawing is limited by HEIGHT and stands at 57 to 60% of the frame's width, as a white
  card on a dark page, with a column of 30-point lines beside it: a slide;
- the 30-point lines are 0.38 units of font size (4.7% of the frame's height) with capitals 0.3
  units high. On a phone held upright the video is about 203 CSS px high, so that is a 10 px
  font with 7.5 px capitals;
- a model-written scene is thin lines in a mostly empty stage (the sky lesson: six circles on
  an arrow).

## 2. What the surveys said (sources in the agents' briefs, summarised)

Layout (a research agent, web only; it marks what is its own derivation):

- Words ON or beside the part they name beat words in a separate block: g = 0.63 over 58
  comparisons (2018 meta-analysis), though a 2024 experiment did not replicate it.
- Two or three printed words beside the matching part, on system-paced slides: retention
  d = 0.47 to 0.70, no gain in transfer (2008). Key-term text beats verbatim text.
- Signalling (showing which part is being talked about): g = 0.53 for retention.
- A type floor for an upright phone, derived: font size at least 6% of the frame's height
  (about 65 px at 1080p), body 7 to 8%; one line across the frame holds about 42 characters,
  which is also Netflix's caption limit; a 40% column holds 15 to 20.
- Reading studies favour light backgrounds, more so as text gets small.
- What the good channels do is a full-frame picture with words on it and earlier text leaving
  when the next statement comes; a split screen is for comparisons. No style guide was found
  for any of them: that sentence is the agent's own description.
- Other generators (Code2Video, TheoremExplainAgent, SGA, ALGOGEN): every fix that worked
  took free coordinates away from the model and added a check. None deals with variety or
  with phones. Code2Video's template is the same picture-and-text split.
- "Captions as app text under the player, or a 4:5 render for upright phones, would gain more
  legibility than any 16:9 layout."

Local models (a second agent): no image model draws diagrams reliably and none spells
reliably; no open SVG model draws a labelled school diagram; grounding models locate parts of
school DIAGRAMS badly (9 to 12% IoU for local open models on one 2026 benchmark). Its ranking
for this project: widen the code-drawn tier; take part locations from SVG structure; a local
Manim writer with a render-and-retry loop (Qwen3-Coder 30B: 87% render success on a 2026
benchmark, and it is on this machine); an offline library of permissively licensed art; local
text-free illustration last, "limit it to objects, never diagrams".

## 3. The stage: the layout that was tried

`GuidedChapter` with `LESSONFORGE_FRAME=stage` (the patch; `columns` is the frame as it is):

- **One small line of heading**, no rules: the stage is 73% of the frame for every picture.
- **The picture takes what the frame can give it and the words what is left**, worked out:
  the picture is scaled to the larger of the two sizes it can have with a column of words
  beside it (3.9 units) or a strip of words above it (1.25). A 3:2 drawing is limited by
  height and leaves room at its side; a before-and-after pair or a row of fraction bars is
  limited by width and takes its words above, centred. Picture and words sit together in the
  middle of the frame.
- **One line of words at a time** while a picture is being looked at: 44-point beside, 48
  above (6.9% and 7.5% of the frame's height). The line before leaves when the next comes.
- Not everywhere: working that grows line by line keeps its column (a run of beats on one
  picture is laid out once for all of them, so the picture does not jump when one beat brings
  a formula); a recap beside its picture keeps its list; a beat with no picture stacks its
  lines large in the middle.
- The question card stands where the words stand.
- A model-written scene keeps the size it had (enlarged further, parts of its own that only
  just cleared each other touch, and the layout check counts it).
- `LESSONFORGE_CAPTION_BAND=0`: no band kept free at the foot; the stage is 87% of the frame.
  Only right if the player shows captions outside the frame (it shows the browser's own, on
  by default, over the foot of the picture).
- `LESSONFORGE_THEME=paper`: a light page (trial; `figures.py`'s own colours do not follow
  yet, so it is for lessons whose pictures are prepared drawings). A drawing is made for white
  paper: on the light page it has no card around it and the words beside it are part of the
  same sheet.
- A picture marked `bleed` (an illustration with no print of its own) fills the frame edge to
  edge, lies under the heading and the words, has no card, and a part of it is marked with a
  bright outline; the one line of words stands on a plate of the page's colour.

Tried on copies, from each lesson's own audio (no model, nothing spent), all chapters, with
`build.run_checks` afterwards:

| lesson | pictures | layout faults, first render → stage |
|---|---|---|
| 4aea9f water cycle | drawing built by parts | 0 → 0 |
| c92dd1 animal cell | drawing with pointers | 0 → 0 |
| a27a42 pasted script | typeset drawing, two panels | 0 → 0 |
| 722331 three pictures | drawing, picture | 0 → 0 |
| 65a5b8 three-four-five | right triangle, scene, formulas | 2 → 0 |
| 6744a6 fractions | bars, scenes, formulas | 0 → 0 |
| 0979b9 sky | scenes | 0 → 0 |
| aee9fc motion | scenes, formulas, question cards | 0 → 0 |
| 7f179f square numbers | scenes, rectangle | 0 → 1 * |
| a7e2f5 | scenes, number line | 3 → 6 * |
| sky with local pictures (§4) | full-frame pictures | 0 → 0 |

\* not the layout's: rendered again with `src/` as it stands, the same chapters give the same
findings (a scene's own "2" touching its "9 × 9" by 0.06 units; a scene one of whose parts
ends 27,609 units off the frame). Both lessons were made by older code. The second is a real
fault in today's scene path and is open.

What the frames showed that the checks did not: the stage with the band kept is cleaner but a
3:2 drawing is no larger than before (it was already at the stage's height) and still has its
words at its side. Without the band that drawing is limited by the words' column instead and
gains only 6% in width (8.5 to 9.0 units); a wide picture gains up to 29% in height (4.0 to
5.15). What changes the look most is the light page and a picture that fills the frame.

## 4. Pictures made on this machine

The owner's own ComfyUI (`/workspace/models/ComfyUI`) has Z-Image-Turbo (Apache 2.0) on disk.
Started headless on a free port with its own output, user and database folders
(`lessonforge_workspace/local_models/`), on the GPU `gpustat` showed with most room:

- a 1344 × 768 picture in 10 to 15 seconds (35 the first time), about 15 GB of one 48 GB GPU
  that other jobs kept 96% busy; no money;
- **good**: a flat water-cycle landscape, a prism splitting white light, the Sun with air
  drawn as dots and a child looking up, the Moon's black sky with an astronaut, a sunset, a
  schoolgirl under a blue sky (`10_assets/local_good.jpg`);
- **wrong**: asked for a DIAGRAM of scattering it drew blue arrows pointing back at the Sun
  and no molecules; its circuit has a glowing bulb and an open switch; asked for four labels
  it wrote "Evapration" and "Condenation" (`10_assets/local_wrong.jpg`).

So: a thing or a place, yes; a diagram, or any text, no. Labels are for code to add.

The vision model on the machine's Ollama (`qwen3.6`, Apache 2.0), run on the CPU because the
GPUs had no room for it:

- **where the parts are**: asked for boxes on a 0 to 1000 scale it gave the sun, the dots, the
  child and the ground of the sky picture, and seven parts of the water cycle, all in the
  right places (65 s; 270 s when Ollama split it between a GPU and the CPU);
- **is the picture right**: of the scattering picture it said "the blue arrows originate from
  the sun instead of being scattered by individual air molecules" and "no visible air
  molecules"; of the circuit, "the switch is open but the bulb is lit, which is physically
  inconsistent" (41 s and 27 s). It then called the first one usable all the same: what it
  lists as wrong has to be the decision, in code;
- **spelling**: it read "Evapration" as printed and "Condenation" as "Condensation": one of
  two caught. No help there.

The demonstration (`pilot/stage_layout/make_sky_local.py`, lesson copy `skylocal`): the
owner's sky lesson with its five model-written scenes replaced by four such pictures shown
full frame, the sun and the child outlined as the voice names them from the vision model's
boxes (`PictureFigure`'s existing `points`). All thirteen checks pass. Which picture goes with
which chapter, and which part a step points at, were chosen by hand for it: the pipeline does
not do this yet.

What it would take to be the pipeline's: a `kind` on a picture request that says thing/place
or diagram (the other session's `visuals_for` and `stills_for` already return a kind); a
`draw_locally(ask)` that returns a file or nothing (GPU room by `gpustat`, a queue, nothing
when there is none); the same judge look, with "anything listed as wrong" as a refusal; boxes
handed in as `points`. In the ladder it sits after the checked shelf of open diagrams and the
drawing service, before a model-written scene.

## 5. What is open

- The owner has not seen any of it; nothing above is in a lesson a requester gets.
- Captions: under the video in the app (and the band given to the picture), or as now.
- The light page needs `figures.py`'s colours to follow before a lesson with a code-drawn
  figure can use it.
- A line of words placed AT the part it names (what the evidence favours most) is not built;
  the line stands beside, above or on the picture and the part is outlined.
- The GPUs: at 06:06 on 10 October a system update replaced the NVIDIA library (580.178) under
  a running kernel module (580.173); `gpustat` and `nvidia-smi` answer "driver/library version
  mismatch" until the module is reloaded or the machine restarts. Jobs already on the GPUs
  run on. Nothing here caused it and nothing here can cure it.
- Model-written Manim by the local `qwen3-coder:30b` was not tried.

## 6. The SVG as the skeleton, a diffusion model for the look (the owner's idea, tried 2026-10-10)

The owner, 08:28: "Can we do something like make the skeleton using svg api then use diffusion based
approaches to style it for this". It answers §4's finding from the other side: the drawing service gets the
STRUCTURE right (which arrow goes where, every word spelt) and looks flat; the image model looks good and
gets structure wrong. So each does its half:

- the SCENE of a drawing (`base.png`: the things, no arrow, no label) is handed to Z-Image-Turbo as an image
  to repaint (image to image: `VAEEncode` of the picture, `KSampler` with `denoise` below 1; the prompt is a
  style line plus what the picture is of, and "no text, no arrows");
- every arrow layer and every label is the drawing service's own and is put back by code at the place the SVG
  gave it. The model never draws an arrow or a letter.

`lessonforge_workspace/pilot/local_visuals/stylize.py` (the repaint) and `styled_diagram.py` (a drawing folder
in, a drawing folder out, same manifest, so `DiagramFigure` shows it unchanged). 14 s a picture on one GPU
with 12 GB free (38 s the first time), no money. `10_assets/svg_then_style.jpg` is the photosynthesis drawing
of the first trial lesson, before and after.

What the tries showed (five drawings, looked at):

| drawing | strength | result |
|---|---|---|
| photosynthesis poster (scene + 5 arrow layers) | 0.45 | almost unchanged |
| the same | 0.6, 0.65 | painted plant, soil, clouds; every arrow still lands on its part |
| the same | 0.75 | richest; one leaf has moved under an arrow's end |
| water-cycle poster | 0.65 | sea, hills and trees painted well; the river came out thin and broken, the rain cloud pale |
| animal cell (its art, 11 parts) | 0.55 | WRONG: the Golgi body became a green body with yellow dots, the centrioles a ball, new bodies invented |
| foot and ball (typeset, no layers), lines pasted back | 0.55, 0.7 | WRONG: the model repainted the letters too and they show double; at 0.7 it painted a boot that does not fit the outline |

So:

- **Things and places, yes** (a plant, the Sun, sea, hills, a ball): where they are is kept, how they look
  is new. **A drawing whose inner detail IS the lesson, no** (a cell's organelles, a heart, a circuit): the
  model replaces detail with other detail. This is §4's rule again, now for repainting.
- **It needs the drawing in three layers: things, arrows, words.** The service's posters come apart that way
  already (`diagrams.callouts`). Its typeset drawings do not: letters are glyph outlines among the shapes.
  The cleanest cure is at the service: an SVG that keeps `scene`, `arrows` and `labels` as three groups.
- **Strength is a dial with a cliff**: 0.6 to 0.65 for a scene; above 0.7 things move from under their arrows.
  A look by the vision judge (before against after: "is every thing still there, in its place?") has to be
  the gate, with anything it lists as changed being a refusal, as for every other judge here.
- Two faults of the take-apart showed on the way: a filled arrowhead stays in `base.png` (it was moved into
  its arrow's layer by pixels for the test), and nothing says which KIND of drawing a folder holds.

Where it would sit: after a drawing is fetched, taken apart and judged, for drawings whose kind is a scene:
`style_locally(folder)` returns a styled folder or nothing (no GPU room, a refused look). Not in the lesson path.

## 7. Lessons made end to end in the trial frame (2026-10-10, 08:15 onward)

The owner, 08:08: "Try end to end pipeline to gen few videos you won't interfere the system". Done on a
second server (`127.0.0.1:5055`) running a copy of `src` with the stage layout, with its own lessons,
sessions and visits (`lessonforge_workspace/pilot/e2e_trial/`), the live library and caches by link, and the
owner's ledger. Nothing entered the live history and the live server was not restarted. What the lessons
showed about the frame is in `CLAUDE.md` under the same date; the short version for this document:

- one formula step put a whole seven-chapter lesson into the column of small lines, because the "working"
  layout was chosen per run of beats on one picture and the whole lesson was one run. Now the picture's place
  is one for the run and the way the words are shown is each chapter's own (`GuidedChapter._working`);
- a word equation fitted to the column on one line was a quarter of the size of its neighbours: a long line
  of working is cut before its first arrow or relation (`runtime.relation_rows`);
- beads ran along arrows that were not drawn yet (`focus_animations` was called when a step was prepared,
  not when its words were spoken): the call waits for the cue (`runtime.Later`). Today's `src` has the same fault.
