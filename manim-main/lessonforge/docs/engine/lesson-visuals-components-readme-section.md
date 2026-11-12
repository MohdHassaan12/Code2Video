# Text for lesson-visuals `components/README.md` (owner to paste; not applied)

Superseded 2026-11-09 by `docs/lessonforge-kits.md` in lesson-visuals (branch `docs/lessonforge-kits`), which also covers
the number-state point this older text predates. Kept for the wording of the sections below.

This is the section lessonforge's docs say lives in BOTH repos. It is kept here because the lesson-visuals repo is the
owner's and the lessonforge branch `kits/mixed-pipeline` was told to change only its own worktree. Paste it at the end of
`/home/mani/lesson-visuals/components/README.md`, as it is or edited, and commit it there.

---

## Used by lessonforge

lessonforge (the lesson-video engine) draws these components as a subject kit. Nothing has to be registered: it reads this
folder directly.

- **Where.** It finds this repo by the environment variable `LESSON_VISUALS_DIR` (default `/home/mani/lesson-visuals`) and
  reads `components/<subject>/<id>.ts`. It runs each file with Node 22.6+ (`--experimental-strip-types`), read-only, one
  short process per batch.
- **New files are picked up on their own.** Add `components/<subject>/<id>.ts` and it is in lessonforge's catalogue and in
  the writer's list of components at its next call: no registration, no edit in lessonforge. A file that fails to load, or
  breaks the contract, is listed as broken with the reason and left out; it never stops a lesson. The folders `tools/` and any
  name starting with `.` or `_` are skipped. Run `check.ts` before you rely on a file: a file that passes it loads.
- **`meta.ncert` must keep the form `"Class N, Ch M Title"`** (one string per chapter, `Title` first, any notes after a `(`),
  or `"Any class 6-10 ..."` for a general figure. lessonforge reads the class from it (it serves Classes 6 to 9; a component
  that names only Class 10 is refused) and the title for the writer. A string in neither form gives a component with an
  unknown class, which is left out of the class-filtered list.
- **Parts are in voice order.** `meta.parts` is the order a teacher names them. The first part is the outline and is there
  from the first frame; each later part is drawn in when the step that names it is said. Use short `snake_case` part names
  (at most 24 characters, `a-z`, `0-9`, `_`): a step's focus is stored in that form, so a longer or differently spelt name
  cannot be pointed at.
- **A part may be `""` in some states** (no bubbles, nothing in the hand). lessonforge keeps its place in the order, draws
  nothing for it, and refuses a step that points at a part that is empty in the chosen state. The first part may not be empty.
- **Text belongs in `labels`, not in parts.** lessonforge writes labels itself, in the lesson's font, at `at` on `side` (right:
  the left edge of the words 6 px right of `at`; left: the right edge 6 px left; above and below: centred). A `<text>` inside a
  part is cut out of the SVG (the SVG reader hangs on it) and written again, but its font and size are then approximate.
  Every number the picture shows should come from `draw()` (a label such as `net force 15 N`): lessonforge lets a lesson
  quote only numbers that are parameters or are written in a label.
- **`validate(params)` is the component's own rule**; lessonforge also checks unknown keys, types, options, min/max and
  state values from `meta` before it asks, and fills missing parameters from their `default` (draw is never called with a
  missing one). Text parameters take words with no digits.
- **Same input, same picture.** The first drawing of a component is made twice and compared; a file that differs is refused.
  Only the tags `check.ts` allows (`path line polyline polygon rect circle ellipse g text tspan`) are accepted.
- **Coordinates** are the component's own pixel box `meta.size`, y pointing down; anchors and labels use the same box.
- **The kit pipeline routes a brief to a component by its words** (`harness/kit_pipeline.py`, no model): the component's
  `title`, its `id` (underscores read as spaces), its part names, and each parameter's name and `say`, plus the `meta.ncert`
  chapter titles. So give a component a plain-words `title` and `say` lines that name the thing the way a teacher would
  ("wooden block", "friction", "test tube"): that is what makes "a block on a rough surface with friction" land on
  `force_block` with no registration. Words that appear in many components' descriptions weigh less; the `subject` word is
  not scored (it is only a filter). A component with no class from 6 to 9 in `meta.ncert` is not routed to.
