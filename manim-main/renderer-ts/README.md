# renderer-ts: lessonforge chapters drawn in TypeScript

A second renderer for lessonforge, next to the Manim one. It reads what the Python pipeline already writes
(`lesson.json`, `timeline.json`, `audio/narration.wav`) and renders one chapter to mp4 with
[Revideo](https://github.com/redotvideo/revideo) (MIT, a Motion Canvas fork with headless rendering).
Nothing in the Python pipeline changes yet. Plan and sizing: "Moving lessonforge from Manim to TypeScript".

```
cd renderer-ts && npm ci
lessonforge lesson audio ../lessonforge/examples/figures_demo --voice silent   # or any finished lesson folder
node scripts/make-input.mjs <lesson_dir> 1 /tmp/c1.json        # chapter 1 -> render_input.json (version 1)
node scripts/render.mjs /tmp/c1.json /tmp/c1.mp4                # picture + narration cut from the lesson audio
npm run typecheck && npm test
```

## What it draws

- **Figure kinds** (`src/figures.tsx`), from the same figure JSON the writer emits: `right_triangle`
  (labels, unknown side, `squares` with side² = area inside each), `circle` (radius, circumference, `sectors`
  that slide into a near-rectangle when `rearranged`), `rectangle` (`grid`, area counted cell by cell),
  `number_line` (axis, ticks, roles/colors, dots, arrow with label), `bars` (stacked fraction/part bars with
  filled and frame cells), `graph` (axes, functions, curves, points, labels), and `shape` (polygon, segments, vertices).
  Each kind names its parts, so a step's `focus` lights up the part the voice is talking about.
- **Figure continuity across beats** (`src/lesson.tsx`): a figure is kept across beats talking about the same
  picture, and only retired when replaced by a new figure, explicitly turned off (`picture: "off"`), or at chapter end.
- **Steps** (`src/lesson.tsx`): each step card (`math` as LaTeX via MathJax, `key` boxed, `point` plain)
  appears when the narrator says its `say` words (`src/timing.ts`, word position inside the sentence's
  timeline slot); a step whose words are never said is spread through the speech.
- **Captions**: the sentence being spoken, at the bottom.
- **Python pipeline integration**: `LESSONFORGE_RENDERER=ts` (or `lessonforge lesson render --renderer ts` / `build --renderer ts`)
  renders directly via `renderer-ts`.

## Measured here

`examples/figures_demo` (2 chapters, 54 s): about 15 s of render per chapter at 1280x720, 30 fps, in a
4-CPU container. Maths renders with no LaTeX installed (MathJax in the browser).

## Notes

- `scripts/chrome.sh` automatically detects Google Chrome / Chromium and drops `--single-process`, which
  Revideo always adds and which crashes recent Chromium. Set `CHROME=/path/to/chrome` to override.
- Revideo 0.11 sometimes fails at start-up ("The thread is not available in the current context");
  `render.mjs` runs each attempt in a fresh process, 3 tries (`RENDER_TRIES`).
- Python integration: pass `--renderer ts` to `lessonforge lesson render` / `build`, or set `LESSONFORGE_RENDERER=ts`.

