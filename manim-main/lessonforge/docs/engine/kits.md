# Subject kits

Status (2026-11-09). Stage 1, branch `kits/subject-kit-registry`: the registry, geometry (a `legacy` adapter, phase 9 is not
done) and `motion`. Stage 2, branch `kits/mixed-pipeline` (stacked on it): `chemistry` (kind `chem_reaction`),
`components` (kind `component`, the lesson-visuals library), lessons that mix subjects, kit metadata for routing, the code
router and the pipeline that calls the kits (CLI and MCP). Stage 3, on the same branch: the components kit reads the
number-state contract of lesson-visuals `origin/main` (see "Components"), tests are hermetic, the router weighs a component's
words by where they came from, and two lessons were filmed through the kits (see "Proof videos"). No paid call has been made:
both films are hand-written lessons, checked by the kits and filmed with the free Kokoro voice. Which class and subject each kit can draw:
[kits-coverage.md](kits-coverage.md). The same ideas for the lesson-visuals side:
`/home/mani/lesson-visuals` `docs/lessonforge-kits.md` (branch `docs/lessonforge-kits`, not yet merged).

The rule that holds for every kit: **code, not a model, decides every fact on screen.** A model picks words and which kit
draws a beat; the kit's model works out each number, fills each gap and checks each claim.

## What a kit is

A lesson video was good when four things held, in this order:

1. a pure function (the MODEL) worked out every number;
2. the figure was drawn only from that model;
3. gaps in the words were filled, and claims checked, by code;
4. the writer was told the rules, and tests held all of it.

A kit is that chain as one object. Adding a subject means registering one `KitBase` subclass in
`src/lessonforge/kits/` instead of editing if-chains in `figures.py`, `writer.py`, `workbench.py`, `improver.py` and
`mcp_server.py`. `KitBase` has five abstract methods, and a subclass that cannot supply them cannot be instantiated,
so cannot register:

The chain, and the code that holds each link (`model -> figure -> gaps + claims -> rules -> tests`):

| link | where |
|---|---|
| model | `solve` (pure; `longform/motion_math.py` for motion) |
| figure | `builder = {"kind": "pkg.mod:func"}`, drawn from the model only (`longform/kit_figures.py`), reached through `figures.build` |
| gaps + claims | `fill_gap`, `claims`, `stray_numbers`, run by `KitBase.settle` |
| rules | `rules`, shipped per lesson (never in a built-in prompt) |
| tests | `cases()`, run by the shared conformance test |

| method | the link it forces |
|---|---|
| `solve(figure)` | the pure model (raise `KitError("plain words")` for inputs that are not a situation) |
| `fill_gap(expr, model)` | `{gap}` text in narration, steps, quiz is filled by code |
| `claims(text, model)` | qualitative claims the model denies ("speeds up", "balanced") are faults |
| `stray_numbers(text, model, used)` | a typed value the picture does not show is a fault. `used` holds `Filled` numbers (floats that keep their gap text); a finding may be a `Whole` message template (`{ref}{where}`) instead of "says X". Motion uses both: a number a gap filled but written with another quantity's unit ("{acceleration} metres per second") is reported as "the unit after {acceleration} should be m/s squared (or metres per second squared)", not as a stray number |
| `cases()` | good lessons, at least three refused lessons and exact gap fills; the conformance test runs them |

`KitBase.settle` is the shared per-beat loop (it is the generic form of `harness/shapes.settle`): solve, fill, check
claims, check stray numbers, refuse two quiz options that come out equal, refuse a gap on a beat with no figure of the
kit. `KitBase.expected_fault` recognises a wrong quiz option's typed number as the point of the option, through the
shared `STRAY` / `STRAY_RE` constants so the writer of the message and the matcher cannot drift apart.

## Layout

```
src/lessonforge/kits/
  base.py       Kit protocol, KitBase, KitError, KitCases, GAP, STRAY, STRAY_RE, arithmetic()
  registry.py   register / get / for_kind / serving / kinds / active / builder_for / rules_for / lesson_faults / guarded,
                and the seam helpers mixed / is_expected_fault / settle_active / edit_ops / slim / rules_for_lesson / mcp_note
  geometry.py   legacy adapter over harness/shapes.py (no behaviour of its own)
  motion.py     the proof kit
  reaction.py   the chemistry kit (kind chem_reaction)
  components.py the components kit (kind component): lesson-visuals components, registered only when Node is there
  __init__.py   re-exports; _BUILTIN = ("geometry", "motion", "reaction", "components") imports the kit modules so they register
src/lessonforge/longform/motion_math.py   the motion model, stdlib only
src/lessonforge/longform/reaction_math.py the equation model (a thin layer over figure_math), stdlib only
src/lessonforge/longform/component_lib.py the components, read through Node (catalogue, checks, drawing), stdlib only
src/lessonforge/longform/component_figure.py Manim-side builder of the component figure (SVG parts, labels, reveal)
src/lessonforge/longform/kit_figures.py   Manim-side builders for kit figures (motion -> the graph builder)
src/lessonforge/env.py                    PAID_KEYS and the LESSONFORGE_NO_DOTENV predicate
```

Import rule: `import lessonforge.kits` pulls in no manim, numpy or `lessonforge.harness` (a subprocess test pins it).
Adapters import `harness.shapes` inside methods; a kit's Manim-side builder is a dotted path
(`"pkg.mod:func"`) resolved only by `longform.figures.build`, through `registry.builder_for`.

## The registry and its switch

`serving(kind)` is the only function a seam calls. It answers `None` for an unknown kind, for a `legacy` kit and for
every kind while `LESSONFORGE_KITS=0`. A seam that gets `None` falls through to today's code, so nothing a kit adds can
break an old lesson; `guarded(label, fn, default)` makes a kit's exception cost a log line, never a lesson.

`LESSONFORGE_KITS` is a `Control` in `knobs.py` (default on, read only by `registry.enabled()` through `knobs.get`).
Off, a stored lesson with a kit's figure keeps the previous picture on screen and `writer.discipline` drops the figure.

`register()` raises at import time on a duplicate name, a figure kind another kit owns, or a built-in kind
(`registry.BUILTIN_KINDS`) unless the kit is `legacy`, and on a non-legacy kit with no `builder` (`"pkg.mod:func"`) for each of its kinds, or no rules. `BUILTIN_KINDS` is a static mirror of `figures.KINDS` because
the registry may not import manim; a test keeps the two equal.

How a lesson asks for a kit: by its figures (`uses_figures`), by `brief["kits"]` (adds that kit's `rules` to the
writer's per-lesson system prompt; unknown names are logged and skipped), or through the workbench/MCP. There is no
auto-detection. A built-in prompt (`FIGURE_RULES`, `writer.SYSTEM`, `pack.SYSTEM`, `improver._system()`) is never
edited by a kit: `tests/unit/test_prompts_pinned.py` pins their sha256, and a kit's rules travel in an addendum.

Mixed lessons (`LESSONFORGE_KITS_MIXED`, default on; 2026-11-09 owner decision): a lesson may draw from several
kits. A beat belongs to the kit that serves its figure kind (`registry.owner_of_beat`; geometry owns `shape`); a beat
with no figure, or a figure of a built-in kind no kit owns, belongs to none. Each kit checks only its own beats:
`KitBase.settle` and `harness/shapes.settle` (through a `quiet` flag on `fill_text`, set only when
`registry.multi(lesson)`) leave a gap on another kit's beat as written, without a fault, and that kit reports it.
A gap on a beat no kit owns is reported ONCE, by `registry.orphan_gaps`, as "which subject is this value from?" when
the lesson draws from several kits; with one kit the kit reports it itself ("no motion figure"), as before. A
geometry-only or motion-only lesson takes exactly the old path (`multi` is False). `workbench.faults_of`,
`registry.lesson_faults` and `writer.kit_pass` run each kit over its own beats and merge the faults; `kit_pass` also runs
geometry's settle in a mixed lesson (a repair of one subject can break another's beats) and its repair request adds what
the other subject's figures make. `rules_for` with several kits named (and mixing on) adds an opening line about mixed
lessons and one header per kit; one kit named gives the same addendum as before.

Switch off (`LESSONFORGE_KITS_MIXED=0`): the previous rule, word for word. `registry.mixed` adds "this lesson draws from
two subject kits (geometry, motion); give each lesson one subject" when a served kit and any other kit (legacy geometry
included) both use a lesson, `workbench.faults_of` returns only that fault, and nothing above applies.

## The seams

Each is an appended branch guarded by `serving()`/`active()` and `guarded()`; with the switch off, or for a kind no
served kit owns, the old code runs unchanged.

| seam | what it does for a served kit |
|---|---|
| `figures.build` | `BUILDERS.get(kind) or kits.builder_for(kind)`; `BUILDERS` and `KINDS` are not edited; an unsolvable figure builds nothing ("the previous picture stays") |
| `writer.discipline` | `kit.normalise_figure` (None = no picture), then the kind is allowed through the figure gate |
| `writer.figure_numbers`, `figure_math.figure_issues` | a tail branch: `kit.numbers`, `kit.figure_issues` |
| `writer.write_lesson` | `system += kits.rules_for(brief.get("kits"))` ("" when the brief names no kit; a header per kit when several) |
| `writer.kit_pass` | after `geometry_pass`: settle, up to `KIT_REPAIRS` (2) repairs through `repair_prompt`, keeps the draft with fewest faults; records `lesson["kit_check"] = {"kits", "faults_left"}` |
| `workbench.faults_of` | `kits.lesson_faults` after the usual checks; with mixing off a mixed lesson reports only the one-subject fault |
| `workbench._expected_fault` | `kits.is_expected_fault` first |
| `workbench.add`, `apply_edits` | `kits.settle_active` fills the kit's gaps; ops from `kit.edit_ops` resolve before "unknown op" (the message lists them only when some exist) |
| `improver.improve` | the kit rules go in the USER text (`kits.rules_for_lesson`), never in `_system()`; `_slim` adds `kits.slim` |
| `mcp_server` | `kits.mcp_note()` (one sentence per served kit) is appended to the server instructions |

## Geometry (kit #1, legacy)

`GeometryKit` (`legacy=True`) is an adapter: `settle`, `unfilled`, `repair_prompt` delegate to `harness.shapes`;
`expected_fault` and `merge_declared` repeat the workbench / edit rules verbatim; `uses()` reproduces the divergent
"is this geometry" tests (`workbench.faults_of`, `workbench.apply_edits`, `writer.geometry_pass`, `scripted._finish`).
`tests/unit/test_kits_geometry_parity.py` holds it equal to `shapes` over the fixtures in
`tests/unit/geometry_fixtures.py` (the Phase 0 goldens in `test_geometry_safety_net.py` pin what `shapes` itself
answers). Routing geometry through the registry is a later, separate owner decision.

## Motion (the proof kit)

Straight-line motion at constant acceleration (SI units), drawn as a speed-time graph.

Figure: `{"kind":"motion","start_speed":0,"acceleration":2,"duration":6,"marks":[3,6]}`. Give any three of
`start_speed`, `end_speed`, `acceleration`, `duration`; code works out the fourth. `marks` (at most four) are the
times the figure labels.

Model (`longform/motion_math.py`, stdlib only): `solve(spec) -> Motion(u, a, T, marks)` with `v(t)`, `s(t)`,
`distance(t)` (differs from `|s|` after a reversal), `stop_time()` (only when `u*a < 0` and the stop is within the run),
`phase()` (speeding up, slowing down, steady, reverses), `trends()`, `facts()`, `shown()` and `graph_params()` for the
existing graph builder. Refused: fewer than three inputs, four inputs that disagree (`0 + 2 x 6 = 12, not the 15 you
gave`), duration not in (0, 600], a non-finite or huge value, a mark outside the run.

Gaps: `{speed at T}`, `{distance at T}`, `{acceleration}`, `{start speed}`, `{end speed}`, `{duration}`, `{stop time}`
combined with numbers and `+ - * /`. The time `T` must be `0`, `duration` or a mark (so a filled value is on the
graph and a later re-check of the filled lesson stays clean).

Claims (each skipped after a negation, in a question, or inside an unfilled gap): "speeds up / accelerates" needs the
speed to rise somewhere in the run, "slows down / decelerates / brakes" to fall, "constant / steady / uniform speed"
needs `a == 0`, "comes to rest / stops" needs a stop within the run, "starts from rest" needs `u == 0`, "turns back /
reverses" needs a sign change. A reversing run both slows down and speeds up.

Stray numbers: a number with a unit (`m/s`, `m/s^2` / `m/s2` / `m/s²`, `s` / seconds, `m` / metres) must be one the
picture shows (start and end speed, speeds at marks, acceleration, duration and marks, displacement and distance at the
end and at marks, the stop time, and the difference between two shown values of the same kind) or a filled gap value;
its sign is ignored. Spoken number words are not policed (a known gap).

## Routing metadata (`subjects`, `classes`, `keywords`)

Every kit may declare which school `subjects` it serves, which NCERT `classes` (1 to 12 for maths; the scope setting below) and the lower-case `keywords`
that, found in a brief or a beat, suggest it. `KitBase` defaults all three to `()` and `registry.describe()` reads them
with `getattr`, so a kit that sets none (a toy kit in a test, an older adapter) works unchanged. `registry.describe()`
(also `kits.describe()`) returns one plain-JSON row per kit: `name`, `figure_kinds`, `subjects`, `classes`, `keywords`,
`legacy`, `served`. It is data for a router, not behaviour: only `harness/kit_pipeline.py` (the router) reads it; the writer,
workbench and the other seams do not.

| kit | subjects | classes | figure kind |
|---|---|---|---|
| geometry (legacy) | maths | 1-12 (the scope) | `shape` |
| motion | physics | 7-9 | `motion` |
| chemistry | chemistry | 7-9 | `chem_reaction` |
| components | from `meta.subject` of each component (maths, physics, chemistry, characters, biology, earth, ...) | the classes its files serve, inside the scope (1-12) | `component` |

## Chemistry (the reaction kit)

A chemical equation drawn as molecules with a before/after atom table, for chemical change, balancing and
conservation of atoms.

Figure: `{"kind":"chem_reaction","equation":"2H2 + O2 -> 2H2O"}`, optional `"counts":false` (hide the table),
`"role":"wrong"` with `"wrong":["H2O2"]` (a changed formula). An unknown coefficient is `?`.

**Why the kind is `chem_reaction`, not `reaction`.** `reaction` is a built-in kind: the writer's own prompt names it
(pinned by `test_prompts_pinned`), `figures.BUILDERS` draws it, and `registry.register` lets only a `legacy` adapter own
a built-in kind. A legacy kit is never served, so its gaps and claims would not be checked. Owning `reaction` as a
served kit would put every old reaction lesson under new faults and repair calls. So the served kit owns a NEW kind whose
builder (`kit_figures.chem_reaction`) calls the same `figures.reaction`: `figures.build` and every old lesson are
unchanged, and the figure keeps `kind == "reaction"` so the voice-led hints and the coefficient-change animation work.

Model (`longform/reaction_math.py`): `solve(spec) -> Reaction` over `figure_math.parse_equation / atom_counts /
is_balanced / balance` (nothing is parsed or counted twice). Refused in plain words: an equation `parse_equation`
cannot read (no arrow, state symbols, charges, coefficient above 6), a symbol that is not an element (`Zz2` parses as a
formula, the kit checks the 118 symbols), a `wrong` formula that is not in the equation.

Gaps: `{atoms of O left}` / `{atoms of oxygen after}` (sides: left, right, before, after, reactants, products),
`{total atoms right}`, `{coefficient of H2}` (as written; refused while the figure still shows `?`),
`{balanced coefficient of H2O}` (the smallest whole numbers that balance it; add `left` or `right` for a formula on
both sides), combined with numbers and `+ - * /`. Atom gaps are refused when the figure hides its counts.

Claims (skipped after a hedge or negation, in a question, and for a general "a balanced equation has ..."):
"balanced / balances" needs every count equal and no `?`; "not balanced / unbalanced / does not balance" needs a count
that differs or a `?`; "the same number of atoms on both sides" and "conserved here / now / on both sides" need the
counts to agree (for the elements the sentence names, else all); "more / fewer X atoms on the left / right" is compared
with the counts. "Mass is conserved in every reaction" is a law, not a claim about the picture, and is not policed.

Stray numbers: "N atoms", "N hydrogen atoms", "N atoms of H" must be a count on a side the sentence names (both when it
names none), a subscript or coefficient of a species on that side, atoms in one molecule, or a filled gap value. Spoken
number words up to ten are read; the other number words are not (a known gap).

Known limits: no state symbols, ions, reversible arrows, conditions over the arrow or word equations; coefficients 1 to
6; `balance()` is tried for at most five species. A lesson with such an equation is refused until the model grows.
Not built yet (each one a separate step):

* A table from substance names to formulas, so a lesson could write "magnesium + oxygen -> magnesium oxide" and code
  would map the names (`reaction_hints.NAMES` maps element names and `COMMON` five compounds, but only for voice hints;
  `reaction_math.solve` reads formulas only). Classes 6-8 chemistry speak in names, so this is the next step for them.
* `{balanced coefficient of X}` on a beat that still shows `?` is filled wherever it is written, narration included; it is
  not limited to quiz text, so a writer can reveal the answer early.
* `longform/visual_actions.py` keys on `spec["kind"] == "reaction"`, so its advisory plan and hints do not yet cover
  `chem_reaction` figures (the figure itself still gets the voice-led hints, which key on the built figure).

## Components (the lesson-visuals kit)

Drawings from the owner's component library in the lesson-visuals repo (`components/<subject>/<id>.ts`, contract in that
repo's `components/README.md`, checker `components/tools/check.ts`): a test tube, a force block, a child, a leaf. The kit
makes them a subject like any other, so a lesson may mix them with motion, chemistry and geometry beats.

**Where it reads them.** `LESSON_VISUALS_DIR` (default `/home/mani/lesson-visuals`; a folder that holds the subject
folders itself is also accepted). Node 22.6+ is needed (`--experimental-strip-types`); it is found by `LESSONFORGE_NODE`,
then `PATH`, then `~/.local/bin/node`. If Node or the folder is missing the kit is **not registered**: one warning line
from the logger `lessonforge.kits`, no exception, `serving("component")` is `None` and every other kit, old lesson and
test is unchanged. The kit does not call lesson-visuals over HTTP: it reads the files and runs Node itself (the checkout
at `origin/main` of lesson-visuals has `/v1/components` routes, `GET` / `draw` / `plan`, which return one SVG per step;
the kit uses none of them).

**How it runs them.** `component_lib.py` globs `components/*/*.ts` at call time (not `tools/`, not names starting with `_`
or `.`), so a file the owner adds is found on the next call with no registration, and a file that passed `check.ts` loads
by construction. One short Node process per batch (about 0.1 s), `--permission` with read access to the components folder
only (no writes, no child processes, no workers), a clean environment (no keys) and a 20 s timeout. Results are cached in
the process by sha256 of (the file's content, merged parameters, state), so an edited component is never served from an
old drawing; the catalogue is also cached on disk under `$LESSONFORGE_HOME/cache/components` by file content (only when
`LESSONFORGE_HOME` is set, so importing the package never creates a folder). The first drawing of each component is made
twice and compared: a component that draws differently for the same input is refused.

**The catalogue.** `catalogue(subjects=None, classes=(6, 7, 8, 9))` lists `id, title, subject, size, classes, chapters,
params (name, type, min, max, options, default, say), parts, states, anchors, example, keywords, path, sha, warnings`.
Classes are read from `meta.ncert`: `"Class 8, Ch 11 Force and Pressure"` is class 8 (chapter 11, title up to the first
`(`), `"Any class 6-10 ..."` is 6 to 10; a component is in scope when any string is a class inside the scope (1 to 12; 6 to 9 before 2026-11-09). A string in neither form gives
no class and a warning (the component is then listed only with `classes=None`). `broken()` lists files that did not load or
break the contract (`meta.id` is the file name, `meta.subject` the folder, parts, size, `validate` and `draw` exported),
with the reason; they are never raised. `kits.describe()` reads `subjects`, `classes` and `keywords` from the catalogue, so a
biology folder appears there with its first file.

**Parameter checks.** `validate(id, params, state)` checks in Python what the component's own `validate` leaves open
(an unknown key, a boolean or a string where a number belongs, NaN, an option not listed, outside min/max, a state key or
value the component does not have, digits typed into a text parameter), fills the defaults (`draw` does not), and only then
asks the component's own `validate`. `draw(id, params, state)` returns the parts as `[(name, svg)]` in `meta.parts` order
(an empty string is kept: a part may draw nothing in some states), the anchors, the labels, the numbers the picture shows
and `facts`; it checks the shape of what came back (every part, finite anchors, labels on real parts with a legal side, only
the SVG tags `check.ts` allows, no NaN or `undefined`).

**Figure.** `{"kind":"component","params":{"id":"force_block","params":{"applied_force":30},"state":{"motion":"sliding_right"}}}`.
The nested form is the canonical one, because `figures.build` hands a builder only `figure["params"]`; the flat form
(`id`, `params`, `state` beside `kind`) is accepted and rewritten by `normalise_figure` and `settle`. The writer picks only
the id, the parameters (each from the component's closed list or range), the state and a step's `focus`; every word and
number on the picture comes from `draw()`. A figure whose parameters fail is refused with the component's own problem
list (`KitError`); a component that serves only other classes (Class 10 only) is refused; no component that fits is
answered by having no component figure.

**Gaps, claims, numbers.** `{param applied_force}` fills a number parameter (defaults included) and nothing else (no
arithmetic: a derived number is the component's own label, such as `net force 15 N`). There are no claims: the component
cannot back a claim about what its picture does, and none is invented. A typed number on a component beat must be a number
parameter, a number in the component's labels, or a filled gap; any other is stray, except ordinals, "Class 8", "step 2",
fractions and exponents. Spoken number words are not policed (a known gap). A wrong quiz option is still the point of the
option (`expected_fault`).

**Parts under the voice.** A step's `focus` must name a part of the component (spelling as the writer stores it: lower
case, `a-z0-9_`, cut at 24 characters, so keep part names short snake_case) and the part must draw something in this
state. `settle` then rewrites the figure to its canonical form and adds `reveal`, the parts steps name in `meta.parts`
order, and a `manifest` (id plus the parameters that differ from the defaults, hashed) that `runtime._pointed_at_before`
already uses to carry earlier focuses into the next chapter. `reveal` is the union over the lesson for one `manifest`, so
repeating the figure on the next beat keeps it on screen. On the stage (`component_figure.py`) the outline (the first part)
and every part no step names are there from the first frame; a named part waits at zero opacity and is drawn in when its
step is said (`focus_animations`, `resume` for earlier beats); a part already on screen pulses once. Nothing is dimmed or
ringed. The drawing stands on a paper card (`#F7F3EA`): components are drawn for paper (ink `#1B2033`) and the lesson's stage
can be dark, where the first film showed outlines and labels vanishing. SVG is loaded per part with `should_center=False, height=None`; Manim still turns each file upside down about the
middle of its own contents, which is undone, and points are placed as `((x - w/2) k, (h/2 - y) k)` (the same for anchors and
labels). `<text>` inside a part is taken out of the SVG (Manim's parser hangs on it) and written again with `Text`.

**Rules for the writer.** `rules` is generated from the catalogue: every component in scope with its full sheet (up to 12
components, a one-line index above that). `kits.rules_for(["components:force_block,test_tube"])` (a `kit:argument` name,
a small additive hook in `registry.rules_for`) gives the full sheet of just the components a brief or a router names;
`rules_for_lesson` does the same for the components a lesson uses. A new component appears in the writer's prompt with no
edit.

Known limits: only drawings (no motion of their own); string parameters take words without digits; numbers in spoken words
and in a quiz's `answer_index` are not read; a part longer than 24 characters in its name cannot be a focus (reported as a
catalogue warning); the first catalogue call after a component changes costs one Node run (about 0.1 s). The checkout the
kit reads by default (`/home/mani/lesson-visuals`) was behind `origin/main` when checked (2026-11-09) and had no biology or
maths component (only characters, chemistry and physics), so a lesson on them there gets "no component fits" and no
picture; with the newer library (`LESSON_VISUALS_DIR`) they are drawn. No earth component exists in either.

**Contract the kit reads (2026-11-09: the number-state contract of lesson-visuals `origin/main`, `components/README.md`
and `tools/check.ts` there).** Read: `meta.id`, `title`, `subject`, `ncert`, `size`, `params`, `parts`, `states`, `anchors`,
`example`, `layer`, `ground`, `situations`, and the exports `validate` and `draw`. Anything else in `meta` is carried in the
entry's `extra`, never refused. Not read: `meta.keywords` and `meta.classes` (keywords are derived from the title, id,
subject, parameter names and `say` lines and the `ncert` chapter titles; classes only from `ncert`), the scenes folder and
`compose.ts` (a scene is the owner's own composer; the kit draws one component per figure).

* **States.** A value of `meta.states` is a list of names (a preset) or a number slider
  `{type: "number", min, max, default, say}`. `check_params` / `validate(id, params, state)` refuse a name not in the list, a
  number outside `[min, max]` (or NaN, or a boolean, or a preset name where a number belongs) and a key the component does
  not have; several keys may be given at once and all reach `draw`. Where a number state and a preset both speak, the number
  wins (README); that is the component's own `draw`, the kit only passes both. Missing number states are filled with their
  `default` (`filled_state`) when the state names at least one number and no preset; an empty state stays empty (the
  component draws its own default picture: filling every default changed four components of the 2026-11 library, for
  instance `number_line`, whose unset picture is the finished hops while `hops_done` defaults to 0) and a state that names a
  preset is not filled either, so `{stoma: "closed"}` still closes the stoma. A slider with `min >= max`, a default outside
  its range or a value that is neither a list nor a slider makes the component unloadable (`broken()` says which); a slider
  with no `say` line is a warning.
* **Canvas fields.** `layer` (`background`, `actor`, `prop`, `overlay`) and `ground` (a y inside the size) are shown in
  `catalogue()` as `layer` and `ground` (`None` when absent or outside the contract, with a warning). The kit does not
  compose scenes, so it does not place or stack by them.
* **Load report.** Run against an extract of lesson-visuals `origin/main` (`ffcb242`, 2026-11-09), `broken()` is empty:
  all 39 components load (the owner's own `check.ts` also accepts all 39); before this change it listed 26 (the number
  states were refused as "meta.states must map each name to a list of values"), so the earlier caveat that number states
  do not load no longer holds. `catalogue()` (Classes 6 to 9) lists 28 of the 39; the other 11 name no class from 6 to 9
  (`nephron`, `reflex_arc`, `burette`, `displacement_reaction`, `hydrogen_pop_test`, `clock`, `counters`, `money`,
  `glass_slab_refraction`, `lens`, `prism`: classes 1 to 5, or 10 to 12) and appear with `classes=None`. `classes_of`
  reads `"Class 8 Science: Light (reflection)"` (no `Ch N`) as class 8 (`chapters_of` still lists only `Class N, Ch M Title`
  strings). 39 of 39 declare `situations`; 25 declare `layer`.
* **Situations.** `catalogue(id)["situations"]` is `[{name, title, ncert, params, steps: [{state, show, say}]}]`: `state` is
  what the step sets (it keeps what earlier steps set), `show` the parts on screen (the step before's when it lists none,
  every part at the first step), `say` the owners' own line, and `params` appears only on a step that moves a number param.
  `kits.components.situation_to_beats(component_id, situation_name, speaker=None)` makes lesson beats from one
  (`longform/component_lib.situation_plan` checks every step first: params and states inside their min and max, shown parts
  exist, a `say` line, then the component's own `validate` and a drawing; a fault is a `KitError` naming the step):
  the narration is the situation's `say` lines in order and each beat step is one of them (`say`: its first five words,
  `show`: its first sentence or clause, `focus`: the part it brings in), the figure is the component with the situation's
  params (over the component's `example`, as `check.ts` draws it) and the states set so far. No model touches a word, and
  the numbers in those lines are not stray (the figure carries `situation`, and the kit allows the numbers of that
  situation's own lines). Added figure keys, all written by code: `hold` (parts kept out of this drawing until a step names
  them: the ones the set-up has not shown yet), `with` (`{part: [parts]}` that come in together with the part), `situation`.
  The writer's rules do not mention them. `speaker` is carried on each beat as `speaker`.
* **Numbers that change.** A lesson beat has one figure, and runtime `GuidedChapter` draws one figure per beat: a step has
  `say`, `show`, `kind`, `focus`, `highlight`, nothing that changes the figure's numbers. So a number that moves is a new
  figure on a new beat: `situation_to_beats` starts a new beat when a step changes a state or a param, and a run of more than
  four steps with the same numbers is cut into beats of four on the same figure (the figure carries over, its drawn parts
  stay). `override_figure(figure, params, state)` builds such a new figure and refuses a value outside min and max, an
  unknown name or an unlisted option. A step that carries `params` or `state` in a lesson is a fault in `settle` (the
  renderer would ignore it and the words would describe a picture that is not there), with the range message when the value is also
  out of range. Limit: a part a set-up stops showing stays on screen (a beat cannot take a part away), and the stage
  does not tween between two figures' numbers by default (`LESSONFORGE_COMPONENT_TWEEN`, "A number that moves is a tween").
* **Tests.** Hermetic (they no longer read the owner's moving checkout): `tests/unit/conftest.py` points `LESSON_VISUALS_DIR` at `tests/unit/fixtures/lv_components` (six of the
  owner's files, pinned; its README says where from) and keeps the shell's value in `LF_TEST_REAL_LV`; the optional test
  `test_every_component_the_owners_checker_accepts_also_loads_in_the_kit_real_tree` runs `check.ts` of a real tree and compares
  (`LESSON_VISUALS_DIR=<tree> pytest tests/unit/test_kits_components_contract.py -k real_tree`).

## The pipeline that calls the kits (`harness/kit_pipeline.py`)

A brief goes in; a checked lesson on the workbench comes out, with a trace. The order is the repo's cost rule: code first
and free, a model last and capped.

```
route -> plan_to_brief -> write -> settle + check every kit -> repair (bounded) -> workbench.add -> preview -> film
 code      code           model     code                        model, capped      code            free       free
```

* **`route(brief_text, classes=None, subjects=None, beats=None)`** gives each part of the brief (paragraphs, list items,
  or the sentences of a one-paragraph brief; a heading is context for the next part) to a kit BY CODE. The words are
  stemmed and scored against what each kit declares in `kits.describe()` (`subjects`, `classes`, `keywords`); the
  components kit is scored one component at a time, from the catalogue, so a new `components/<subject>/<id>.ts` is
  routable at once. A keyword listed by many targets weighs less (1/sqrt(targets)); a multi-word phrase weighs more.
  Router-only extras (`EXTRAS`: element and substance names, vehicles; `PATTERNS`: an equation, a formula, a speed with
  its unit) are data in `kit_pipeline.py`, not kit metadata, so no kit changed. The class filter keeps a kit whose classes
  meet the filter (motion starts at 7, so `--classes 6` drops it); with none given, "Class 8" in the brief is used, else
  every class in scope (1-12). Ties within 0.05 go by `PRIORITY` (`PRIORITY = {"chemistry": 3, "motion": 3, "geometry": 2, "components": 1}`). A part scoring under 0.5 gets
  `kit=None`: the existing scene/diagram figure kinds, never a failure. Each item is
  `{beat, text, kit, kind, component, subject, class_band, score, why, by, alternatives}`.
* **Optional model router.** An injected callable decides only parts scoring under 1.5 (and of 4+ words), is asked once
  with the list of kits, and its answer is validated: the kit must be registered and inside the class/subject filter, and
  a component id must be in the catalogue. Anything invalid is ignored and noted in `plan.notes`; a null never overrides a
  code choice. Facts are never its job: it picks which kit draws, the kit's code decides every number.
* **`plan_to_brief(plan, brief)`** fills `brief["kits"]` (kits the plan uses; components as `components:id1,id2` so the
  writer gets those components' sheets; several kits get the mixed-lesson addendum) and `brief["kit_hints"]`, one line per
  part, which `writer._brief_block` shows only when present (no older prompt changes; `test_prompts_pinned` holds).
* **`run(brief_text, llm=None, cap_usd=0.0, film=False, rounds=2, *, lesson=None, ...)`** writes with
  `writer.write_lesson` (its own `kit_pass` runs first), settles and checks every kit's beats with
  `workbench._settled` + `faults_of`, then asks the model to repair at most `rounds` times
  (`kits.repair_prompt`, or `shapes.repair_prompt`, or a generic prompt), accepting a round only if it lowers the fault
  count and stopping at the first that does not. It puts the best draft on the workbench (faults left are reported, not
  hidden), optionally makes the stills, and films (free Kokoro voice) only when no fault is left. It returns a `Report`
  `{plan, lesson_id, faults, craft, spend, steps[], brief, preview, film}`; each step is `{n, step, ok, what, seconds}`.
* **Money.** `llm=None` is free only: nothing here calls a model. `llm` is a callable `(prompt, system) -> JSON`, wrapped
  in `Meter`, which refuses a call BEFORE making it when `spent + last call's cost x 1.3` (or the estimate before any
  call) would pass `cap_usd`. A callable that does not declare `spent_usd` is assumed to cost `DEFAULT_CALL_USD` = $0.05 a call (conservative on purpose: a
  library caller who hands over a raw paid callable is over-counted, never under-metered), so `cap_usd=0`
  refuses it at once, and a refusal before the first call counts in `spend.refused`; a stub declares `spent_usd = 0` and `call_estimate_usd = 0` and runs free. `ledger_llm()` meters a
  real model by how much `spend.spent()` grew. A cap reached while the writer is mid-lesson loses that draft: size the
  cap for a whole lesson (the improver's default is $0.10; a 6-minute chapter-by-chapter lesson is several calls).
* **Tools** (`TOOLS`: `list_kits`, `describe_kit`, `route`, `check_lesson`) are plain functions of plain JSON, free, for a
  Claude session or an agent loop to call one by one. `check_lesson` takes lesson JSON, a file or a workbench id and saves
  nothing.
* **CLI**: `lessonforge kits list|describe NAME|route "text" [--classes 7,8] [--subjects physics] [--json]|run BRIEF.md
  [--lesson L.json] [--cap USD] [--rounds N] [--preview] [--film]`. `run` without `--lesson` needs `--cap > 0` (exit 2
  otherwise, and no model is looked for); with `--lesson` and no `--cap` it is free; exit 1 when faults remain.
* **MCP**: `list_kits`, `describe_kit`, `route_kits`, `run_kit_pipeline` (check only: no model, no film; film is the
  existing `film` tool).

What it does not do: it does not write a lesson without a model (a placeholder outline is not a lesson); it does not
decide that a kit is right for a beat the code scored low unless a model was given (and then only validates it); it does
not turn a beat with no kit into a picture, and a `scene` figure (model-written animation) is not code-decided, so the
hints tell the writer to type no number the kit did not work out. Tests: `tests/unit/test_kit_pipeline.py` (stubs only).

Limits of the router today (seen by running it on 2026-11-09):

* Its targets are the registered kits and the components. The built-in figure kinds `bars`, `number_line`, `circle`,
  `rectangle`, `graph`, `float` and `right_triangle` are not kits, so "three fourths as bars" and "plot y = 2x + 1" route to
  `kit=None`, while "area of a rectangle" and "hypotenuse of a right triangle" go to `geometry` (its keywords). A part with
  `kit=None` is not an error: the writer uses the usual figure kinds.
* It keys on words, class and subject only. It does not use a chapter id or title (the Class 8 and 9 titles are in
  `adhyay/server/sources/ncert_concepts.json`, in the adhyay repo; no Class 6 or 7 list exists in either repo).
* A weak word match used to win ("negative integers on a number line" scored 1.0 for `components:splinter` because a
  splinter parameter's say line says "negative"; "The angle is 40 degrees." went to `inclined_plane`). Fixed 2026-11-09: a
  component keyword now has a tier by where it came from (`TIER_NAME` 1.0 for the id and title, `TIER_SITUATION` 0.6 for a
  situation title, `TIER_CHAPTER` 0.5 for the NCERT strings, `TIER_PARAM` 0.25 for a parameter's name and `say` line, the
  parts and the named states). What only the parameter tier matched adds at most `WEAK_CAP` (1.0), under `SURE_SCORE`, so it
  can never decide alone; a single word in `GENERIC` (negative, number, value, angle, line, time, ...) is not a component
  keyword on its own (the phrase "number line" is). `why` shows the tier of a weak match, e.g. `friction (chapter)`.
  All of it is built from the catalogue (`_component_doc`), so a new component, with its situation titles and NCERT strings,
  is routable with no code change. Class strings are read as "Class 8", "Class 6-10", "Class 1 to 12", "Any class 6-10" and
  "Any class ..." (every class); the catalogue cache key moved to `v3` with that.
* A biology part gets `kit=None` with score 0 only with a library that has no biology folder (the old default checkout). With the
  `origin/main` library (`LESSON_VISUALS_DIR`) it routes to a component: "An animal cell in strong salt water loses water and
  shrinks." goes to `cell` (score 5.9, `why`: animal cell, salt water (situation), shrink (situation)) and a pendulum sentence to
  `simple_pendulum` (4.6); measured 2026-11-09 for the third proof. With no components kit at all the cell sentence goes to
  `chemistry` at 1.0 on the word "water". An earth part still gets no kit anywhere (no earth component exists), and no note says so.

## Proof videos (2026-11-09, free)

Two hand-written lessons (no model wrote a word) were put on the workbench, checked by every kit, filmed with the free Kokoro
voice (`cost_usd` 0.0 in both film results; `LESSONFORGE_NO_DOTENV=1` and the paid keys emptied) and reviewed. They are
session output (about 7.5 MB each), not files of this repo; the lesson JSON is the thing to rerun.

| name | length | what it shows |
|---|---|---|
| `mixed_kits_lesson.mp4`, title "What Moves a Cart: Ramp, Speed, Friction and Fuel" (workbench id `mixed-kits-proof-55c12c`) | 174 s, 8 beats, 3 chapters | four kits in one lesson: a right triangle ramp (`shape`, geometry), a cart's speed-time graph (`motion`, with `{speed at 2}`-style gaps filled by code), a block sliding on a floor (`component` `force_block`, 30 N against 15 N, state `sliding_right`) and `2H2 + O2 -> 2H2O` balanced (`chem_reaction`, `{balanced coefficient of H2}` filled by code). |
| `mixed_kits_lesson_2.mp4`, title "Balance and change" (workbench id `balance-and-change-ffdb1a`) | 148.6 s, 8 beats, 3 chapters | components with the new contract, in `LESSON_VISUALS_DIR` = an `origin/main` library: `cell` (biology; an animal cell, then the same cell in salty water with the number state `water_balance` -0.5), `force_block` twice (30 N balanced, then 35 N against 15 N), `number_line` (a frog hopping 4 jumps of 3 to 12, after a `motion` speed-time graph beat). Run through `kit_pipeline.run(..., llm=None, lesson=...)`: 0 faults after settling, 37 preview stills with 0 findings, then filmed. It found that a part with only a label (`number_line`'s `result`, "0 + 3 + 3 = 6") counted as empty, so a step could not focus on it and the sum showed from the first frame; fixed in `697eca5` (`component_lib.empty_parts`). |

`workbench.film` refuses a lesson that still has faults, and both were filmed without `force`. Both reviews also list craft
numbers outside the band of good explainers (for instance `numbers_per_100w` 7.16 and 8.36, high), and the second lists three
steps with long on-screen words; those are style findings, not kit faults. `cell` and `number_line` are not in the default checkout, so the second film
needs the newer library.

### Third proof (video-quality plan step S13, 2026-11-09, free: Kokoro, quality l, no model, `LESSONFORGE_COMPONENT_TWEEN=1` and `LESSONFORGE_COMPONENT_TIGHT=1`)

Three short lessons written by hand to avoid the plan's "Lesson-writing defects" (one idea each, the quiz answer neither said nor
drawn before it is asked, values printed on the word that says them, step words that add a term or a formula, a closing line that
shows the rule). Session output, in `/home/mani/adhyay/proof_videos/` (`v3_triangle.mp4`, `v3_osmosis.mp4`, `v3_pendulum.mp4`);
the lesson JSON is the thing to rerun (hand-written builders in the session's scratchpad, `v3/tri_lesson.py`,
`osmosis_lesson.py`, `pendulum_lesson.py`). Each went through `workbench.add` (0 faults), `quiz_leaks.find` (0), `preview`, a film
with `cost_usd` 0.0, and a frame read at the start of every sentence. The pendulum also went through `kit_pipeline.run(lesson=)`.

| | triangle (geometry, Class 7) | osmosis (`cell`, Class 9) | pendulum (`simple_pendulum` + `graph`, Class 7) |
|---|---|---|---|
| beats, length, words | 7, 89.2 s, 153 | 5, 69.4 s, 130 | 8, 79.7 s, 152 |
| what moves | a corner dragged across the sentence (`pace: voice`), an angle copied by a half turn twice (`transfer`), a drag on the quiz triangle to close | the cell shrinks 0 to -1 across the sentence (voice tween) and grows back -1 to 0 | the bob swings across three sentences (voice tween through stations), the angle-time graph is drawn, the period label arrives at its number |
| moving share, medium (the script) / pauses forced still (`--pauses`) | **51.3%** / **49.9%** | **52.9%** / **51.6%** | **48.0%** / **46.9%** |
| same lesson done the old way | triangle film 253 s: 34.2% | `mixed_kits_lesson_2` 148.6 s: 26.1% | none |
| gain over it | +17.1 / +15.7 points | +26.8 / +25.5 points | - |
| loose / strict (pauses) | 58.8% / 31.1% | 55.2% / 18.9% | 50.1% / 35.7% |
| longest still outside the quiz pause | **2.4 s** (old 5.7 s) | 4.5 s (old 7.0 s) | 3.2 s |
| time in stills of 3 s or more | **5.8%** (old 19.9%) | 15.8% (old 58.2%) | 10.4% |
| silence (runs of 0.3 s) | 33.3% (old 26.9%) | 32.4% (old 23.8%) | 38.5% |
| step numbers printed early / max lead | 0 / 0.27 s | 0 / 0 | 0 / 0 |
| words per minute (speech only) | 137 | 147 | 161 |
| smallest label in the card (pt) | 32.5 to 37.4 (shapes) | 25.1 | 30.0 (graph: 22.5) |

Acceptance bar of the plan, criterion by criterion (met / not met, with the number):

1. Moving share at least 50% and 15 points over the same lesson done the old way: triangle **met by the script's definition (51.3%),
   not met by 0.1 point when the pause is forced still (49.9%)**; osmosis **met** (52.9% / 51.6%, +25 points); pendulum **not met**
   (48.0% / 46.9%, no old film to compare). The 15 points are met by both lessons that have an old film.
2. Longest still outside a pause at most 3.0 s and stills of 3 s or more at most 15%: triangle **met** (2.4 s, 5.8%); osmosis not met
   (4.5 s: the closing hold after the last step is 3.0 s plus a 0.35 s tail by design, and the quiz beat's speech; 15.8% by 0.8 point);
   pendulum not met on the longest (3.2 s), met on the share (10.4%).
3. Picture: **not met** in two points. The card (preview `picture.share`) is 41.6% to 52.6% (triangle), 44.96% (osmosis), 41.1% to
   51.6% (pendulum): under 50% in some beats of every lesson, which the plan called "already 41 to 58%, no regression"; the ink box of
   the figure is not measured by the script for a dark-stage shape (no paper card). Smallest label at least 26 pt: triangle yes,
   osmosis 25.1 pt and the graph's 22.5 pt no; the graph's axis numbers are still tiny (S11 (c) is not done). Steps at least 42 pt:
   many beats use 44 to 46 pt, the beats with a pinned second line (the proof beats of the triangle) use 28 to 42 pt.
4. Zero faults: `workbench.faults_of` 0 and `chapter_NN_audit.json` `bounds_violations` empty in all three (met). The layout audit
   still lists counted `overlap` entries after each voice-tween beat (the old picture and the new one stand on each other while the
   old one is moved; the new words are now hidden until it goes and the old words leave in the first 30% of the run, the frames at
   every sentence start and the middle of the move show no two numbers on each other, but the audit probe reads positions, not
   opacity). **Not met** for the crossfade between two beats: the 0.4 s crossfade shows both triangles (the quiz question to its answer, the
   line figure to the quiz triangle). The preview lists `small_label` for the graph beats of the pendulum (22.5 pt, a note).
5. Zero premature reveals: step numbers printed more than 0.5 s before they are said: **0** in all three (max lead 0.27 s). Numbers
   drawn inside a figure, read by eye on the frame at each sentence start: the triangle's answer beat (the drag figure shows 55
   degrees and the sum from its first frame, about 1.3 s before "It is 55") is the one left; the pendulum's labels arrive at
   "gram bob", "centimetres long", "it is 1.8 seconds" and the answer's point at "1.8 seconds". No quiz answer on screen or said
   before its beat (the lint finds none; the quiz frames show "?" and a `graph` with no point), the options are shown as words.
6. Number states: the pendulum has **three** voice-driven tweens and the bob is checked in the middle of each (met); the osmosis has
   **two** (the cell cannot cross 0, so a swell to pure water is not tweened) (not met); the 0.02-unit check is the S8 one (0.014 for a
   0.4 s step); the 1.8 s to 3.6 s step of the last beat (a whole swing, 3 legs) was not measured.
7. Title card 2 s and closing hold 3 s: present in all three (first lead 3.5 s, tail 3.01 s). Silence under 16%: **not met**
   (32% to 38%): the title card, the hold and a 5 s pause are 10.3 s, and every beat that brings a new picture has a 1.3 s lead and a
   0.35 s tail (`audio._joined_leads`), which for lessons of 70 to 90 s is already a third. Words per minute: 137, 147 and 161, over the 120
   to 130 aimed at, the two beats over 180 have no new number.
8. Unchanged: the three engine changes below are gated (the old function is pinned by a test over 1600 moments, the voice tween only
   runs for a step a kit flagged, the word timing only through `change_from`), the 783 tests of the baseline set and the files
   touched pass; **the sha256 of the old stills was not recomputed in this step**. Local commits only, nothing pushed.

What limited the moving share: the metric counts a step of 0.1 s as moving only above 0.15% of the frame (86 px of 57,600), so a small
label, an arc or a slow shrink of a small cell never counts, and a text step moves for 0.5 to 0.7 s. The only continuous motion the
engine has is a dragged corner, a turning wedge and a swinging bob or shrinking cell driven across the sentence; each lesson has
one quiz (the question and a 5 s pause, about 18 s in which only the card moves) and a 3 s hold. Three engine defects came out of
filming and are fixed with tests: `pace: voice` (a drag moved 40% of its beat), a `Succession` of stations that could not be stepped by
hand (the pendulum's voice tween silently fell back to the lead-in), and two numbers printed over each other while a number moved.
`scripts/video_metrics.py --pauses` is the fourth change (the bar alone masked 2.6 s of a 5 s pause).

## Video metrics (`scripts/video_metrics.py`, video-quality plan step S0)

One free, deterministic yardstick for a finished mp4, so a video-quality change is judged by the same numbers before and
after. `python scripts/video_metrics.py VIDEO [--json]`; add `--lesson-dir <lessons/ID>` (finds `output/sync_timeline.json`,
`output/captions.vtt`, `preview/*/preview.json`) for the reveal check and the per-beat sizes, or `--sync`, `--captions`,
`--preview` one by one, or `--seen seen.json` (`[{"value": "12", "seen": 31.4}]`) to compare numbers drawn inside a figure that
were read off the video by eye. Needs `ffmpeg` and `numpy` only; nothing is written, no model or network is used. It is a
measuring tool: no render, lesson or prompt is touched. Test: `tests/unit/test_video_metrics.py` (synthetic lossless clips:
still, fade, sliding box, countdown bar; skipped without ffmpeg).

`--pauses` (added with the third proof, plan S13; needs `--lesson-dir`): the thinking pauses that `timeline.json` wrote (the
beat's last `thinking_pause_seconds`) are counted as quiz spans and as still, as well as the spans found from the bar. A crafted
pause (the options as words, the "Time to think" line) changes pixels besides the bar now and then (a few steps of 50 to 115
changed pixels against the medium threshold of 86), so the bar alone masked 2.6 s of a 5 s pause in the new triangle film. Off by
default, so every earlier baseline is the number it was.

Fixed definitions (the earlier 35% / 27% / 24% "moving" disagreement came from each critic using another):

* Read at 10 fps, 320x180; a pixel changed when its grey moved by more than 10 levels (`PIXEL_STEP`). A step between two
  frames is moving when more than 0.03% (`loose`), 0.15% (`medium`) or 0.5% (`strict`) of the pixels changed. `medium` is
  THE moving share. Longest still run, time in still runs of 3 s or more (`still_3s_s`, share) are reported for all three.
* The quiz countdown bar (a thin gold line, at most 3 rows high at 180, that shrinks) is masked, only inside a stretch of at
  least 1 s of bar steps (a quiz span). So a thinking pause counts as still; `longest_still_outside_quiz_s` cuts the quiz spans
  out of every still run. `moving_share_bar_unmasked` is printed beside it: at this size the bar's change per 0.1 s is under
  the medium threshold, so the two agree on all three baselines (the bar is not what makes "moving" high).
* Picture share, every 2 s on a 640x360 frame: `card` = bounding box of the paper (`#F7F3EA`/white, below the header band) as a
  share of the frame (it matches `preview.json` `picture.share`, 0.4255 for the first beat of the balance film); `ink` = the
  bounding box of everything inside that card that is not paper, labels INCLUDED (so it is not "the drawing"); `content` = for
  a dark-stage frame with no card, the bounding box of everything that is not the stage colour below the top 12%, words
  included (so it over-states a figure; call it content).
* Silence = runs of at least 0.3 s under -45 dBFS in 50 ms windows, over the video's length.
* Premature reveals: the number in each step's `show` text, from `sync_timeline.json` (when the step is printed), against the
  caption cue that says it (the position inside the cue is proportional to characters: the voice's word times are not stored).
  `lead_s` > 0 is printed before spoken; flagged beyond 0.5 s; a number first said more than 15 s after it is shown, or said
  in words, is "never spoken". Not checked: numbers drawn inside a figure (no OCR is installed); use `--seen`.

### Baselines (2026-11-09, measured with the script as committed; the three proof videos before any quality step)

| | triangle angle sum (geometry) | mixed_kits_lesson (motion, reaction, shapes) | mixed_kits_lesson_2 (balance and change, components) |
|---|---|---|---|
| length | 253.1 s | 174.0 s | 148.6 s |
| moving share loose / **medium** / strict | 44.9% / **34.2%** / 16.6% | 32.1% / **27.0%** / 14.7% | 28.5% / **26.1%** / 21.3% |
| longest still (medium), where | 5.7 s at 215 s | 8.7 s at 84 s | 7.0 s at 141 s (the closing hold) |
| longest still loose / strict | 5.7 s / 7.5 s | 8.7 s / 8.8 s | 6.7 s / 7.4 s |
| same, quiz pause cut out (medium) | 5.7 s | 8.7 s | 7.0 s |
| time in stills of 3 s or more (loose / medium / strict) | 29.7 s (11.7%) / 50.3 s (19.9%) / 123.7 s (48.9%) | 91.3 s (52.5%) / 91.9 s (52.8%) / 114.8 s (66.0%) | 82.2 s (55.4%) / 86.5 s (58.2%) / 96.9 s (65.2%) |
| quiz span (bar moving) | 8.5 s in 2 spans | 5.7 s in 1 | 4.6 s in 1 (121.5 to 126.1 s) |
| card (paper bbox) of frame | none (dark-stage figures) | 41.7% in 11 of 87 frames | median 54.9%, 40.7% to 57.4% (57 of 74 frames) |
| content, no-card frames | median 50.3%, 18.6% to 68.3% | median 56.5%, 24.7% to 72.2% | median 56.6%, 41.3% to 60.5% (14 frames) |
| silence (runs of 0.3 s or more under -45 dBFS) | 26.9% | 23.4% | 23.8% |
| step numbers (shown / printed early / late / never spoken within 15 s) | 31 / 18 / 3 / 8 | 18 / 13 / 1 / 0 | 20 / 16 / 2 / 0 |
| largest lead (printed before said) | 11.6 s | 6.9 s | 4.2 s |
| label size in preview.json (pt) | 28.3 to 40.5 | 22.0 to 38.9 | 22.4 to 32.2 |
| smallest words in preview.json (pt) | 28.0 | 44.0 | 42.4 |

How this compares with the plan's quoted baselines (24% / 26.6% / 27.3% moving, from the critics' own scripts): the mixed films
agree within about one point (27.0 and 26.1 against 26.6 and 27.3), the triangle film reads 34.2% here (the owner's "35%"), not 24%. The share depends on the pixel step:
at 25 grey levels the triangle reads 22.7%, mixed_kits_lesson 21.3%, mixed_kits_lesson_2 20.5%; at 6 levels 38.7%, 29.7%,
27.2%. The critics' mixed numbers are not reproducible by one pixel step with their triangle number, so this script's single
definition (10 levels) is the yardstick from now on; compare only numbers made by it. "Premature" step leads of 0.5 to 1.5 s
are mostly a step printed when its phrase starts while the number comes later in the same phrase; the large leads are the
real defects (a number 4 to 12 s before it is said). The triangle film's `preview.json` rows are the film's own (the geometry
film is in the stage frame too: card share 36% to 52%, steps 28 to 52.8 pt, shape labels 28.3 to 40.5 pt), but its picture is a
dark-stage shape, not a paper card, so the pixel `card` row is empty for it and `content` is the figure to compare.

## The workbench preview shows the film's layout (video-quality plan step S1)

`workbench.preview` (MCP `preview`, `improver.improve`, `kit_pipeline`) used to render the lesson with no `look`, which is the
old `columns` frame (picture in a left column). The film does not look like that: `service` writes `look.for_new` for a new
job (stage frame, `pictures` chosen by `compose.settle`), so the preview showed a card of 19 to 28% of the frame, labels of
18 to 19.5 pt and 30 pt steps where the film has a card of 41 to 58% (mean about 51%), labels 22 to 32 pt and steps 42 to
48 pt, every figure already at its room limit. Corrected numbers, measured on the proof lessons before and after:

| beat (balance and change film) | preview before (columns) | preview now = the film's own `preview.json` |
|---|---|---|
| card share | 0.19 to 0.28 | 0.4137 to 0.576 (identical, beat by beat) |
| steps | 29 to 34 pt | 42.4 to 48 pt (identical) |
| smallest label in the card | 18.3 to 19.5 pt | 22.4 to 32.2 pt (identical) |
| layout mode | side every beat | top, side, top, top, side, top, top, top (identical) |

`workbench.film_layout(lesson)` makes a throw-away copy with `look = look.for_new(lesson, environ=knobs.environ())`, ALWAYS
(a stored look is ignored, as the film ignores it) and `pictures = fill` when the lesson is in the stage frame, `compose.enabled()`
and `compose.drawn_by_code(lesson)`, else `kept`. The copy goes to `longform.preview.stills` only: it is never saved (no `look`
key appears in `workbench.load`), `compose.settle` is not called (it runs a vision judge), and `HARNESS_FRAME=columns` still
previews the old frame. Say "card", not "figure": the card is 41 to 58%, the drawing inside it is smaller (see `ink` in
`scripts/video_metrics.py`). The geometry proof film previews identically to its own `preview.json` (card 36% to 52%, steps
28 to 52.8 pt). A preview takes 13 to 31 s for these lessons (silent timing, one Manim still per step), so "under a minute" is
true for them but not promised. The improver has no threshold of its own on these findings (it passes the first 12 to the model as text, `improver.py`), and
kit_pipeline only counts them, so nothing was tuned on columns-frame findings; in the stage frame there are fewer (no
thumbnail or enlarge ones that only the columns frame produced), which is the point.

## Small writing inside a figure is measured (video-quality plan step S2)

`longform/preview.measure` has a new finding kind, `small_label`: the end-of-beat still's `picture.type_points` (the smallest
writing inside the picture, which the renderer already measured and nothing read) under `SMALL_POINTS` (28). Severity
`medium` from `UNREADABLE_POINTS` (22) up, `high` below; text "smallest label 22.4 points (7.2 on a phone) in the component
picture"; `fix` is empty (nothing a program can try yet; the figure-text step is S12). It is reported only: `preview.faults()`
does not read findings, so `compose.settle`'s fill-or-kept choice cannot change, and it is not added to `faults()`. New kind,
so the exact-kind assertions on the old kinds hold. Findings are logged and stored under `job["composition"]["measured"]`
(`service`), so that list is no longer empty for a lesson with 22 to 28 pt labels: on the balance film it names beats 01, 02,
05 and 06 (24.6, 23.6, 22.4 and 24.0 pt). The workbench preview carries them too, so `improver.improve` (first 12 findings, as
text) and the MCP `preview` tool now see these four lines; no prompt, threshold or lesson changes.

## Numbers beside an angle appear when the voice says them (video-quality plan step S3)

A geometry picture drew an angle's arc AND its number the moment the voice named the angle ("angle DAB"), and a sum line
under the picture the moment a verdict word came ("sum", "total"), however many seconds before the number was said (the
triangle film: 50 degrees on screen 16 s before it was spoken, 120 degrees 15 s, a quiz's check line 8 s, the sums of the
other triangles 5 to 10 s). New look key `values` (`longform/look.py`): `named` is every lesson made before 2026-11-09 and
is the old plan event for event; `spoken` is what `look.for_new` writes now (`HARNESS_VALUES=named` turns it off for new
lessons, `LESSONFORGE_VALUES` overrides one render; control "Numbers beside an angle" in the app).

* `shape_hints.plan_one(..., spoken=True)`: "angle DAB" lights the arc and its letters (event kind `angle`, parts `[arc]`);
  the number (`angle_DAB_value`) gets its own event (kind `value`) at the first word after the name that is that whole number
  (`info["angle_deg"]`, set by `shape_figure.draw` from the same rounded degrees as the label), looked for in the rest of
  that sentence and the next one (`VALUE_REACH` 25 words). No such word in reach: the number comes with the name, as before,
  so nothing is left unseen. Another angle's number is never taken for it (the search starts after the name).
* The sum line (`band`) of a shape with `angle_sum` or `readout` and no verdict waits for the first equation word
  (`EQ_WORDS`: makes, equals, gives, total, altogether, check, adds), else the first time the total is said as a number, else
  the old verdict words ("sum", "total", "360"). A band that carries a verdict ("convex") is not held for its equation.
* `runtime.GuidedChapter` reads `LOOK["values"]` (`VALUES_SPOKEN`) and sets `figure.values_spoken` on each figure it builds;
  `ShapeFigure.hint_plan` passes it on. `_hold_back_named` (unchanged) holds each part until its first event, so the number
  stays hidden until its word. In stills (the preview) nothing waits, as before.
* Tests: `tests/unit/test_shape_values_spoken.py` (named is the old plan, the number at its word, a number out of reach, no
  number word, the sum line at "makes", the runtime hold times) and `test_look.py`.

## A quiz's answer is not on the screen before it is asked (video-quality plan step S4)

The proof films showed two leaks: a motion graph labels every mark with its value ("2 s, 8 m/s"), so on the beat that asks
"what is the cart's speed after 2 seconds?" the answer stood on the screen for the whole question (19.4 s), and a geometry
quiz asked for an angle the voice had said 15 s earlier. `harness/quiz_leaks.py` (pure; no Manim, model or network):

* `hold(lesson)` is the writer pass `writer.quiz_leaks` (last in `figures_and_words`, so it runs for every lesson that goes
  through the service, the workbench film included). On a beat with a `quiz` whose figure is a `motion` figure, the marks
  whose label shows the correct option's number go into the figure's `hold_marks` (`[2]`). `kit_figures.motion` passes those
  points to `figures.graph` with `"hold": true`: the dot and its label are not drawn, but the point keeps its index (so
  `point2` is still the last mark, a step's `focus` still lands) and the label places and the y range are the answer
  beat's, so the graph does not rescale when the answer comes. The next beat (a figure without `hold_marks` is a new
  figure) is where the marks appear. The model is untouched: the kit still checks every number against all the marks.
  A `shape` figure (with its own `points`) is held the same way: the angle whose arc would write the answer's whole degrees
  (the figure's own rounding, `geometry.round_to_total`) gets `"value": false` in its `angles` entry, so the arc stays and its
  number waits for the next beat; an author's own `value` text is kept.
  A speed answer holds the mark with that speed, a time answer ("2 s") the mark at that time; a number the question gives
  ("after 2 seconds") is not an answer; a bare 0, 1 or 2 with no unit is not looked for. An author's own `hold_marks` is kept.
  Idempotent (running it twice changes nothing); a beat with no quiz and any other figure kind are untouched.
* `find(lesson)` is the lint: the answer's number (digits, or in words) in the narration or screen words of an earlier
  beat, in a motion label of an earlier beat, or in the question beat's own narration (before the question) or screen words.
  The writer pass logs each and keeps them as `lesson["quiz_leaks"]` (a note; the words are not rewritten);
  `kit_pipeline.settled_faults` returns them as faults ("quiz leak: beat 07: the answer 8 is already in view in ..."), so
  `lessonforge kits run` refuses to film such a lesson. A quiz may say `"allow_seen": true` when the earlier mention is a
  deliberate set-up. `HARNESS_QUIZ_LEAKS=0` (control "Keep a quiz's answer off the screen until it is asked") turns the pass
  and the lint off.
* NOT done (plan S4 part c): showing the question frame of a component in a neutral state (`rest`, not `sliding_right`).
  The state is lesson-visuals' vocabulary and `force_block`'s `rest` state would draw 35 N against 15 N standing still, which
  contradicts the numbers; it needs an owner's "prediction" state in the component. Other figure kinds (a `graph` with
  `points`, a `right_triangle` side label, a component's labels) are not held: `graph_reveals` already covers a graph's meeting
  point. A `shape` that says `use` (a named shape of the lesson) rather than carrying its points is not held either.
* Tests: `tests/unit/test_quiz_leaks.py`. Stored `lesson.json` files are not read again by any of this, and a lesson with no
  `hold_marks` draws as it always did.

## A finished graph, table or verdict is drawn as it is talked about (video-quality plan step S5)

A motion graph arrived with every point, its value ("2 s, 6 m/s") and the curve's equation ("v = 3t") 13 to 17 s before the
voice said "after 2 seconds" (the curve never climbed), and a reaction arrived with its atom table and its verdict ("not
balanced yet") before the voice counted anything; at a reaction to reaction change the old counts and verdict stood among the
moving molecules (a ghost "4" and "1" on 120.0 to 121.8 s). New look key `staging` (`longform/look.py`): `whole` is every
lesson made before 2026-11-09 and draws as it did; `steps` is what `look.for_new` writes now (`HARNESS_STAGING=whole` turns it
off for new lessons, `LESSONFORGE_STAGING` overrides one render; control "Graphs and tables").

* `runtime._hold_back_steps` (called beside `_hold_back_named` for a fresh picture, only when the figure carries
  `staged_steps`, which the runtime sets from the look) puts parts into the same `figure._late` list the geometry hold-back
  uses, so `_show_late` draws them in (a curve is drawn along from its start, a dot, label or table fades in over
  `DRAW_IN`), a clock runs (`_start_hints` for a picture with voice-led lights, `_start_staging` for the rest) and the
  beat always ends with every part shown. A part named as the picture arrives (its step is the first) arrives with it.
  * Graph and `motion` figures: the parts a step's `focus` names (`point0` with `point0_label`, `meet0`, `curve0` with its
    equation `curve0_label` unless a step names the equation, `asym`, `hole`) wait for that step's due time. `axes`, `x_label`
    and `y_label` are never held. A part no step names is shown with the picture, so nothing is hidden for good.
    `figures.graph` marks each curve piece `grows_in` so `_hide` grows it. In stills (the preview) a held part is shown at the
    step that names it (`_reveal_to_step`), so the preview stills of a staged graph show the axes and curve first and each
    mark at its step; the beat's last still has everything.
  * Reaction (`chem_reaction`) figures: the count table (`count_heads`, `left_count`, `right_count`) waits for the first word
    that counts (`reaction_hints.stage_times`: "count", or an element and a side: "oxygen on the left") and the verdict for the
    word that says it ("balanced", "unbalanced"; never "balance" as a verb, never before the table). A word never said: the
    part is drawn as the first step comes. Stills show reactions whole, as before.
  * `figures.reaction_change` with `staged_steps`: the old table, rows and verdict FadeOut first (one group), then the
    molecules change; no recount roll-over, because the new numbers come at their words.
* `writer.stage_graphs` (a pass in `figures_and_words`; off with `HARNESS_STAGING=whole`): a motion beat's step with no `focus`
  gets one when its words clearly name a part ("After 3 seconds" is the point at 3 s; "the line climbs steadily" the curve).
  A step with a focus, a point a quiz holds (`hold_marks`) and any other figure kind are left alone; idempotent.
* Same speed-time graph with and without `hold_marks` on the next beat (a quiz and its answer) is swapped in place, not morphed
  (`runtime._only_a_hold_differs`): the morph smeared every label for a second.
* The audit record of each beat (`output/chapter_NN_audit.json`, `layout`) now carries `held_until` (part -> seconds into the
  beat when it is drawn) and `staged` (the parts held by this step); that is how the premature-reveal numbers below were
  measured on a film, not from stills.
* Tests: `tests/unit/test_staging.py` (hold times, grown curve, equation with its curve, gating, writer pass, reaction
  stage times, the reaction change's first group).

## S3 to S5 measured (2026-11-09, free films, Kokoro, quality l)

Four hand-written lessons filmed twice each through `workbench.film`: BEFORE with `HARNESS_VALUES=named HARNESS_STAGING=whole
HARNESS_QUIZ_LEAKS=0`, AFTER with the defaults. Lead = when the voice says the number minus when the label is on screen (seconds
into the beat; the film's own `held_until`, the spoken time estimated inside its sentence by characters, as `video_metrics.py`
does; a number said in an earlier beat is not new). Positive is printed early.

| lesson | labels checked | printed > 0.5 s early before -> after | largest lead before -> after |
|---|---|---|---|
| geometry, 4 beats (angles, sum, quiz on the exterior angle) | 5 | 4 -> 1 (0.5 s: "makes" comes half a second before "180") | 6.1 s (sum line) -> 0.5 s |
| triangle angle sum, 14 beats (`build_tri`) | 9 | 9 -> 2 | 14.2 s -> 13.6 s (see below); sum of leads 49.5 -> 17.7 s |
| motion with a quiz, 3 beats | 4 | 4 -> 0 | 15.7 s -> 0.4 s |
| reaction, 2 beats (not balanced, then balanced) | 4 (count table and verdict, twice) | 4 -> 0 | 17.7 s -> 0.5 s |

* Quiz answer: the 2 s, 8 m/s mark stood on screen for the whole 16.5 s question beat; now 0.0 s (it is drawn at "It is" in the
  next beat, its label when the 8 is said). The triangle lesson's exterior-angle quiz lead is NOT fixed (below).
* `video_metrics.py --lesson-dir ... --seen` with the figure numbers (from the film's `held_until`): premature numbers 8 -> 4
  (geometry), 27 -> 20 (triangle), 11 -> 8 (motion); the rest are step captions printed at the start of their phrase, which none
  of S3 to S5 changes. Without `--seen` the check reads only step text, so it is identical before and after.
* Reaction transition (beat 1 to 2, frames every 0.4 s): before, the old "1" and "4" overlapped, "O2" ran into the legend and
  "not balanced yet" stood under "balanced"; after, the table and verdict fade out, the molecules change, the new table comes at
  "oxygen on the left" and "balanced".
* Unchanged for stored lessons: stills of the proof lesson 1 (chapters 1 and 3, 26 stills, a stored look with no new key) are
  byte-identical (sha256) between the commit before this work and now; the four films with the three switches off are frame-identical
  (md5 of every frame at 5 fps: 325, 200, 255 and 1174 frames) to films made by the commit before this work.
* Not fixed: a number shown in one beat and first said in a later one (triangle beat 10 shows ACF = 120 at "angle ACF", the voice
  says it in beat 11: 13.6 s); a panel's sum line; a value said before its name shows at the name (2.5 s late, never early);
  "Check it" brings the sum line 4 s before "180" in a beat that says "check" first.

## One card for a run of beats on one component (video-quality plan step S6)

Beats that show one library component in different states (a cell at `water_balance` 0, then -1; a number line at 0, 1 and 3
hops) each had a card of their own size, because the card is the box of that state's drawing. The stage scales a picture to
fit its room, so the picture changed size and place at every state change (measured on the real library: number_line card
height 3.396 against 3.927, the cell 7.438 x 4.333 against 6.547 x 3.785; the film of an animal cell at 0 then -1 stood
centred under a heading in beat 1 and jumped to a left-hand card in beat 2).

* **`span`** (a figure key written by code, like `hold` and `with`): `ComponentsKit._focus` collects the distinct `{params, state}`
  of every figure in a run of consecutive beats on one component id and writes the same list (in a fixed order) on every
  figure of the run. A run is broken by another component, by another kit's picture or by an unsolvable figure; a beat with no
  figure of its own or `picture: off` does not break it; a run holds at most `SPAN_LIMIT` (12) distinct drawings, the 13th starts
  a new run. A run of one drawing gets no span. `normalise_figure` and `override_figure` do not carry a span (it is recomputed on
  every settle, so a stale one is rewritten or dropped), `manifest_of` ignores it (the drawing's name is unchanged), and
  `figure_extras` refuses a malformed one in plain words. The writer's rules do not mention it.
* **The card.** `component_figure.component` asks for every drawing of the span in ONE `prefetch` (one Node process), measures
  each (`extent_of`: the content box, labels and anchors, cached per process by the drawing's digest) and gives the figure a card
  that is the union of those boxes, anchors included, plus the figure's own drawing. Two figures of one span therefore have
  the same card (width, height, centre) and the same box, so the stage's `_staged` scale and place are equal. If any drawing of
  the span cannot be drawn, the figure has its own card as before (`fig.span` is then `None`). A figure with no span is built
  exactly as before (card = its content + pad).
* **The runtime.** `GuidedChapter._run_key` makes figures that share a span one run for `_run_board` and `_working` (a formula
  in any beat of the run makes the picture's place a board for all of them), so the picture and the column of words are in the
  same place in every state. Figures with no span use `json.dumps(figure)` as before.
* **Gate.** Control `LESSONFORGE_COMPONENT_FRAME` (default on, group "Pictures"): read when a lesson is settled; off writes no
  span. A lesson.json that was settled before this has no span and renders exactly as before (a re-settle, as the workbench does
  on every edit, writes one while the control is on). Not a look key: nothing is read at render time.
* **Measured** (real `cell` component, two-beat animal cell lesson, Kokoro, quality l, `workbench.film`): with the control off,
  the card is 6.547 x 3.448 at 0 and 6.547 x 4.294 at -1 and the beat-1 picture sits centred under the heading while beat 2's sits
  in a card on the left; with it on, both cards are 6.547 x 4.294 and the two beats put the picture in the same place.
* Tests: `tests/unit/test_kits_components_frame.py` (the span written, run breaks, cap, stale span, gate, validation, equal
  cards, anchors inside, own drawing always inside, fall-back, one batch, `_run_key` and `_run_board`).

## A number that moves is a tween, not a fade (video-quality plan step S7)

Two beats on one component with a different number (the cell at `water_balance` 0, then -1) used to cut: the first drawing
faded out and the second was drawn again. `ComponentFigure.change_from(old)` (`longform/component_figure.py`) uses the hook the
runtime already plays for a reaction (`GuidedChapter`, "the picture CHANGES part by part"), so **`runtime.py` is not edited**: the
runtime plays the returned animation in the beat's lead-in (0.45 to 1.4 s), removes the old figure and adds the new one.

* **Gate.** Control `LESSONFORGE_COMPONENT_TWEEN` (default OFF, group "Pictures", `render=True` so a render subprocess is told;
  read at render time with `knobs.get`). Off, `change_from` is `[]` and the old fade runs exactly as before; the knob stays off
  until the owner has seen a film.
* **When it answers `[]` (the fade is kept).** The old figure is not a `ComponentFigure`, another component, no `span` or a
  different one (S6), the two cards not placed alike (1e-4), the change is anything but number knobs listed in
  `component_lib.TWEEN_KNOBS` (a preset, an integer or structural parameter, a text, a number set on one side only, a knob not
  listed, a part that appears), the library refuses the change (`morph_plan` is `None`), or anything raises (a
  `LESSON_NOTE` line, never a failed chapter).
* **The allow-list is a safety belt, the measurement decides.** `component_lib.morph_plan(id, a, b)` draws the component at 9
  values from a to b in ONE Node batch and compares, for every part whose markup keeps the same shape (`svg_numbers`: the
  markup with its numbers cut out), each number of a probe against the same number interpolated between the ends
  (`deviation_px`, svg pixels). Within 1.0 px (about 0.015 scene units) everywhere: the straight morph is the truth and the
  plan has no stations. Otherwise the plan lists stations (plan step S8, next section) and the art goes through them.
  Measured on the owner's library (`origin/main` extract of 2026-11-09; every number knob of every component probed at three intervals):

  | knob (listed) | change | straight morph off by | verdict |
  |---|---|---|---|
  | `cell.water_balance` (plant and animal) | 0 to -1, 0 to 1, -0.5 to -1, 0.3 to 0.9 | 0 (within 1 px) | straight |
  | `cell.water_balance` | -1 to 1, -0.5 to 0.5 | 25 and 12.5 px | piecewise: it kinks at 0 (water in and water out are separate branches of `draw`) |
  | `nephron.extra_water`, `clamp_stand.jaw_open`, `leaf_section.opening` | full range | 0 to 0.2 px | straight |
  | `food_chain.energy_kept` | 0.05 to 0.2 / 0.1 to 0.2 | 1.4 / 0.25 px | borderline: the wide one needs a station |
  | `burette.added_ml` | 0 to 50 / 20 to 50 | 65 / 0 px | piecewise |
  | `simple_pendulum.time_s` | any | 63 to 143 px | a curve (stations, S8) |
  | `sound_wave.time_ms` (in the plan's list) | any | 27 to 47 px | NOT straight: a polyline wave that translates; removed from the list |
  | `clock.minutes_later` | any | 110 to 154 px | a rotation: not listed |

  So **the plan's allow-list was wrong in three places**, found only by measuring: `sound_wave.time_ms` is not geometry-stable
  (two shifted waves averaged are mush, not the wave in between); `cell.water_balance` is exact only on one side of 0; and
  `burette.added_ml` is piecewise. All three are handled by the measurement, and `sound_wave` is left out of the list.
* **What moves.** For every part: a part the new drawing keeps back (`reveal`, `hold`, `with`) fades out; a part kept back before
  and shown now fades in; otherwise the part's SVG art is `Transform`ed (never the part VGroup, never an invisible anchor)
  when its markup has the same shape on both sides, and cross-faded (old out, a copy of the new in) when it does not; words
  inside a part and the part's labels cross-fade whenever they differ (a "20" never glyph-morphs). The card is equal (checked)
  and is left alone. Every animation works on the OLD figure's own mobjects (the new art is copied in at zero opacity), so
  nothing is added to or removed from the scene while it runs and no ghost can be left. One `AnimationGroup` is returned, so the runtime's 0.45 s per stage floor is met.
* **The flip.** Manim turns each SVG file upside down about its own contents and the figure undoes it per part when it builds
  (`ComponentFigure.__init__`); `Transform` interpolates points that are already in scene coordinates, so the flip holds at every
  alpha (`test_the_manim_flip_holds_under_the_transform...`: the upper layer stays above the lower one at 0, .25, .5, .75 and 1).
* **Measured** (real cell, animal, `water_balance` 0 to -1, `LESSONFORGE_COMPONENT_TWEEN=1`, free Kokoro film, frames at 0.3 s):
  the membrane goes from 7 soft lobes to 20 crenations while the cell shrinks, the nucleus, vacuoles and mitochondria move with it,
  "shrinks" fades in and the card never leaves; with the control off the card fades out and the figure is redrawn. The moving share
  of the 23 s film (`scripts/video_metrics.py`, medium) is 33.5% before and 33.9% after: **S7 alone does not lift it** (the plan
  said so: about 1.4 s of motion per transition; the voice-driven tween, S9, is the lever).
* Tests: `tests/unit/test_component_tween.py` (gate, listing, measurement, pixels at start, middle and end against the old and
  new drawing, the flip, hidden parts, label cross-fade, the fallback) and `tests/integration/test_component_tween.py` (a real
  silent render, in one chapter and across a chapter join, with a negative control).

## A knob that moves along a curve goes through stations (video-quality plan step S8)

The straight morph of a swinging bob from 0 s to 2.4 s is a chord: the bob would slide through the pivot's side of the arc.
`component_lib.morph_plan` (also `keyframes(id, a, b)`, which returns just the stations) draws the component at `t = j / 8`,
j = 0..8, in ONE `prefetch` (at most 9 draws; a batch of 64 draws takes about 0.1 s here, `RUN_TIMEOUT` is untouched at 20 s)
and cuts the grid with the recursive test of S7: a leg between two kept stations stays only if EVERY grid point between them is
within `KEY_TOL_PX` (1.0 svg px) of the straight morph. The probes are several, not the midpoint: a bob released at the side is
back at the side after one period, so the chord between equal ends passes through the midpoint exactly (test with a temporary
component, `a dot on a swing`: midpoint deviation 0, quarter point 60 px, stations cut at 0.25, 0.5 and 0.75).

* **What is interpolated.** Only the number knobs of the change, and only when the change is nothing else (a preset, an
  integer or structural parameter, a text or an unlisted knob in the same change refuse the whole thing: nothing is half-moved
  and nothing is drawn). `_station` writes the value at `t` into a copy of `a`; an integer knob stays an integer.
* **Parts.** A part whose markup keeps one shape at every grid point and draws something (the string, the bob) is `stable`:
  `ComponentFigure._along` makes a `Succession` of `Transform(old art, station art)` legs, each as long as its step of the knob,
  at a steady pace (the group's own smooth easing is outside it). A closed curve (ends equal, the way not) still gets its legs.
  A part that is empty at some station (the speed arrow, the angle arc) is not measured and not morphed: it cross-fades between
  the two ends like a label (so it is absent in between when both ends have none). The stations are built by the same
  constructor in the same frame and put where the stage put the figure (`_placed`: scaled about the card's native centre by the
  card's own factor, lines thickened as the figure's were), which is why they need the S6 card.
* **Measured** (real `simple_pendulum`, scene units at 1:1, the bob against the component drawn at the same knob value, every
  1/100 of the change): 0.4 s to 0.8 s (a step of the library's "one swing" situation, 3 stations) worst 0.014 to 0.015, which
  meets the plan's 0.02; 0 to 2.4 s (a swing and a half in one change, 7 stations) worst 0.118 between two stations and 0.000 at a
  station, against a chord that is off by more than 0.3; 0 to 6 s (four swings) 0.64 (a nonsense request). **The plan's
  "0.019 at k=7" does not hold between stations for a 2.4 s change**; it does for a step of 0.4 s, which is what a
  lesson shows. Finer grids were not adopted (the depth is `KEY_DEPTH = 3`; a depth of 4 draws 17 and could have up to 15 legs).
* Film (free Kokoro, `time_s` 0 then 0.4, `LESSONFORGE_COMPONENT_TWEEN=1`): over the 1.3 s lead-in the string swings from 20
  degrees to vertical with the bob on the arc, the speed arrow fades in, the labels ("time 0 s", "angle 20 deg", "speed 0 m/s")
  cross-fade to the new ones, and the card never changes.
* Not done: `sound_wave.time_ms` (a travelling wave needs far more stations than a batch of 9 gives) and `clock.minutes_later`
  (a rotation) are not listed; a number_line `hops_done` change adds arcs (structural) and is not listed. The voice-timed
  driver (S9) is not built.
* Tests: `tests/unit/test_component_keyframes.py`.

## A number moves across the sentence that says it (video-quality plan step S9)

S7 and S8 move a number in the beat's lead-in (0.45 to 1.4 s, before the words). The step cue caps every animation at 0.9 s
(`run_time=min(.9, ...)`), so nothing longer can be played from a step. S9 drives the same animation by the voice's clock, for
the whole sentence that says the change ("the cell shrinks"), modelled on `_start_motion`.

* **The flag.** `tween: "voice"` on a step (a key only code writes, like `span`). `ComponentsKit._focus` writes it, only when
  `LESSONFORGE_COMPONENT_TWEEN` is on when the lesson is SETTLED, on the first step of a beat whose drawing differs from the
  last beat's (same run, S6) only by a listed number knob (`component_lib.tweenable`: the same allow-list as S7); a step a hand
  flagged on such a beat keeps the flag (the first step is often a lead-in sentence and the shrink is said in the second),
  and a flag anywhere else (a beat that moves nothing, the control off, a run broken by another picture) is dropped at every
  settle, so a stale flag never survives. It is written at settle, not at `situation_to_beats` (the plan's place): every lesson
  goes through `_focus`, the writer's and the library's alike. `COMPONENT_RULES` does not mention it.
* **The driver.** `GuidedChapter._voice_window(steps, due, located)` gives `(start, end)`: the flagged step's words (`due`, the
  moment found in the speech) to the next later step's words, else the end of the speech. `None` (the S7 lead-in plays) when no
  step is flagged, when the flagged step's moment was a guess (`located` is false: an even spread), when an earlier step has a
  `focus` (it would act on a picture that is under the old one), or when the window is under `VOICE_TWEEN_MIN` (1 s).
  `_start_tween(ghost, animation, start, end)` steps the animation `ComponentFigure.change_from` returned by hand (`begin`,
  `interpolate(p)`) from a driver mobject sent behind everything, at `tween_progress(now, start, end)`: **linear** from the first
  word to 0.4 s (at most a sixth of the window) before the end, so the new state is the one on screen when the sentence is
  over. (`stage_progress` is not used: it plays a stage "soon and then waits", about a fifth of a long sentence.) The scene's
  own clock `renderer.time` moves only between plays, so the driver adds its frames' `dt` to it.
* **"Swap at once", by a ghost.** The new figure is added under the old one at once and the old one is brought to the front
  and morphed: it is the picture on screen while the voice speaks, and when it reaches its end it is made invisible (it equals
  the picture below) and removed. This is the plan's "swap `carried` for `figure` at once", with one change that makes its
  "do not let a focus pulse fight the driver" true by construction: the beat's steps (a pulse, a reveal) act on the NEW figure
  under the ghost and never on the mobjects the driver is moving, so there is no pulse to skip. The cost: a step that reveals a part
  during the window shows it when the ghost goes (not at its word), which is why an earlier step with a `focus` refuses the window.
  The last step's entrance used to end the beat's loop, so the driver is run to the window's end (`self.until`) before `_stop_tween`.
* **What stays as it was.** Steps without the flag, the control off (`change_from` answers `[]`), a render of stills (`STILLS`:
  no clock, the end still shows the new figure) and every other kind of figure take the S7 branches unchanged; a stored
  lesson.json has no flag. A driver that cannot start (`_start_tween` returns `None`, nothing changed in the scene) or a frame
  that raises (the ghost goes, the new picture shows, one `LESSON_NOTE`) falls back, never ends the chapter.
* **Measured** (free Kokoro films, quality l, real `cell`, animal, `water_balance` 0 to -1, `LESSONFORGE_COMPONENT_TWEEN=1`;
  frames every 1 s over the window): the membrane goes from soft lobes to crenations and the cell shrinks continuously from
  the word "Water" (18.1 s) to the end of "wrinkles up" (25.4 s) while the voice speaks, labels cross-fading with it; see "S9 measured" below
  for the moving share. Without the flag the same lesson moves in the 1.3 s before the words.
* Tests: `tests/unit/test_component_voice_tween.py` (the clock, the window, the kit's flag, the driver on a fake scene
  with real figures: pixels at several times, the ghost gone at the end, no pulse effect, a failing driver, a long wait) and
  `tests/integration/test_voice_tween_render.py` (a real silent render: the picture changes at every half second of a
  12 s sentence with the flag, and not with it).

* **Bug found filming the pendulum (plan S13, fixed).** A knob that moves along a curve (S8) returns a `Succession` of stations
  inside the group; stepped by hand it had no `scene` (`Succession.begin` reads `self.scene`), `begin()` raised `AttributeError`,
  `_start_tween` caught it ("a number's move was not driven by the voice") and the bob swung in the 1.3 s lead-in, finished
  before the first word. Every level of the animation now gets the scene as a name before `begin`. Test:
  `test_a_knob_that_moves_along_a_curve_is_driven_by_the_voice_too_...` (fails without the fix).

* **Second bug found filming the pendulum (plan S13, fixed): two numbers printed over each other.** The new picture stands under
  the ghost from the first frame with its words at full strength, while the ghost cross-fades its own words into them, so "time
  1.8 s" faded out over "time 3.6 s" and "at the end: speed zero" over "swinging" for the whole sentence (the layout audit lists
  these as counted `overlap` findings after each tween beat). `_start_tween(..., figure=)` now takes the new picture's words away
  (opacity 0, remembered) until the move is over and gives them back when the ghost goes, or at `_stop_tween`, or if the driver
  fails. The ghost carries its own copies of the new words coming in, so no word is missing. Test:
  `test_the_new_pictures_words_wait_under_the_old_one_...`.
  Hiding the new words was not enough: the ghost's OWN cross-fade (old words out, new words in, linear over the whole run) still
  printed two different numbers over each other at half strength at its middle. Words now go out in the first 30% of the run and
  come in in the last 30% (`component_figure.WORDS_OUT`, `WORDS_IN`; art parts that cross-fade keep the whole run); this is only
  reached through `change_from`, so it is behind `LESSONFORGE_COMPONENT_TWEEN` like the rest. `test_component_tween.py`'s
  cross-fade test now asserts the three moments (going out at 0.15, neither there at 0.5, coming in at 0.85).

### S9 measured (2026-11-09, free films, Kokoro, quality l, `LESSONFORGE_COMPONENT_TWEEN=1` where noted)

One lesson, two beats on the real `cell` (animal, `water_balance` 0 then -1; beat 2: "Now put the same cell into strong salt water.
Water leaves the cell through its membrane, so the cell slowly shrinks and the membrane wrinkles up. The cell has lost water.",
three steps), filmed three ways; 28.3 s each. `scripts/video_metrics.py` (medium) over the whole film, and the same definition
(10 fps, 320x180, a step is moving above 0.15% of pixels changed) over the sentence window 18.1 to 25.4 s (the second sentence):

| film | moving share, whole film | the sentence window: moving / longest still | longest still, whole film |
|---|---|---|---|
| control off (the fade and a redraw) | 27.8% | 21% / 5.4 s | 5.5 s at 19.9 s |
| S7 lead-in tween, kit's flag on step 1 (a 3.75 s window) | 33.8% | 21% / 5.4 s | 5.5 s at 19.9 s |
| S9, hand flag on step 2 (the shrink's own sentence, 7.3 s) | **43.8%** | **97% / 0.2 s** | 4.4 s at 2.2 s (the opening beat) |

The acceptance bar of the plan for the window (moving at least 80%, longest still under 1 s) is met; the whole film is +16 points
over the control, for one 7 s change in a 28 s film. The kit's own flag (the first step) is on a short lead-in sentence; the
window then covers the sentence that is spoken first, which is why the third film hand-flags the sentence that says the shrink.

## Craft: a title card, a closing hold, cross-fading pictures and a clean thinking pause (video-quality plan step S11)

New look key **`craft`** (`look.CRAFT`): `plain` for `BEFORE` and any stored lesson.json without the key, `crafted` from
`look.for_new` (control `HARNESS_CRAFT`, group "Look"; `LESSONFORGE_CRAFT` overrides one render; `HARNESS_FRAME=columns` and
`LESSONFORGE_FRAME=columns` give `plain`). Stored lessons render as they did; `test_look.py` and the harness-job test now list the key.

* **Title card, 2 s, and closing hold, 3 s.** `audio.build_audio` makes the room in the timeline (silence the build owns, like every
  lead and tail): the lesson's first beat's `lead` grows by `TITLE_CARD_SECONDS` (2.0) and its last beat's `tail` is at least
  `CLOSING_HOLD_SECONDS` (3.0, from 0.6). `GuidedChapter._title_card` draws the lesson's title (and its `thesis` when short) over
  the page in the first chapter's first beat, in 0.4 s, held, out in 0.4 s, 2 s in all; it plays only when the timeline carries
  the seconds (`lead` of 2.3 or more), so a re-render of an old timeline under a `crafted` look gets no card, and never in a
  render of stills. The closing hold is the last picture held (its steps come back to full strength as they always did).
* **A picture is drawn while the old one fades.** In the branch where a new picture replaces a different one (`fresh`, not a morph,
  not a swap, not `bleeds`), the 0.3 s fade-out that came first (and the blank card it left for the rest of the lead-in) now runs
  in the same play as the new picture's drawing (`FadeOut(..., run_time=.4)` beside `construct_animation`, or beside the card's
  fade-in for a painted drawing). The step text still leaves before its successor arrives (`Succession`): two lines of words
  cross-faded are unreadable at the middle.
* **A thinking pause (`_pause`) leaves nothing stale.** Plain: the card fades in while the steps fade out (the question drawn over
  the words it hid: "Speeds up" under "What is the cart's speed ...") and at the end the steps fade back IN, for the next beat to
  take them away again (the stale words at the end of the pause). Crafted: the steps go first (0.3 s, taken from the countdown),
  then the card comes, and at the end only the card goes; the beat's steps are not restored and the next beat has nothing to fade.
  The plan said to fix this for every lesson; it is gated here because its acceptance bar 8 asks for stored lessons to render
  identically and the task's rule is gating (one line, `crafted = self.CRAFTED` in `_pause`, would ungate it).
* **Options and what the bar counts.** Crafted: the question's options are shown as words (`A.  4 m/s`, no boxes, nothing lights
  up; the answer is the next beat's), so a question that asks for one of them is asking about something shown; in the strip
  above a wide picture they are one line plus "Time to think" above the countdown bar. (`LESSONFORGE_QUIZ_IN_VIDEO=options`, the
  old button-like boxes, is unchanged.)
* **The graph starts at 0.** `motion_math.graph_params(m, zero_floor=True)` (a figure key `zero_floor`, set by `figures.build(spec,
  crafted=True)` for kind `motion` only, the lesson's spec untouched): when no speed is negative the y axis starts at 0, not 2
  below it (the empty band under every speed-time graph). A velocity that goes negative keeps its room.
* **Measured** (`mot` lesson of the S3 to S5 films: 3 beats, a motion graph, a quiz with three options and a 6 s pause; free Kokoro,
  quality l; `HARNESS_CRAFT=plain` against the default): length 52.1 s against 56.5 s (+2.0 s card, +2.4 s hold); at 1.0 s the card
  stands alone on the page; the y axis runs 0 to 14 against -2 to 14; in the pause the card no longer overlaps "Speeds up" (frame 0.4 s
  after the pause begins) and no step text stands over the answer beat's first frames (plain: "Speeds up" is back 0.1 s before the
  next beat). Crossfade: two different component pictures, plain goes to under half of its picture pixels between them and
  crafted stays above a third (`tests/integration/test_craft_render.py`).
* **Unchanged for stored lessons**: the `mot` lesson filmed with `HARNESS_CRAFT=plain` is frame-identical (md5 of the whole decoded stream
  at 5 fps, 2703 frames) to the same lesson filmed by the commit before S9 and S11 (`9f7d451`, from a temporary worktree).
* **Not done** (listed in the plan's S11 (c), skipped because each needs a figure-by-figure look at pixels that this step did not
  have time for, and none can be done blind): axis ticks and header at 24 px or more with fewer ticks; the end-point label offset
  up and left of the axis title; the `?` on the quiz's exterior arc as large as the other labels and in a high-contrast
  colour. They are still open. The 5 s of card and hold are silence in the S0 metric, not motion.
* Tests: `tests/unit/test_craft.py` (the key, the control, the timeline's lead and tail for crafted, plain and no look, the graph's
  floor, the flag reaching the builder only for crafted motion) and `tests/integration/test_craft_render.py` (title card over the
  heading, the closing hold, a pause with no stale steps, a picture always there between two pictures).

## Geometry that moves: drag a corner, copy an angle (video-quality plan step S10)

Two figure keys on a geometry `shape`, both off unless a beat writes them. A figure with neither is built, expanded, hinted and
drawn exactly as before (`tests/unit/test_shape_motion_s10.py` pins that). What the plan assumed and what the code does:

* **The move path already existed and is the way in.** `shape_figure._with_motion` turns a figure with a `move` into ONE group that
  `runtime._start_motion` replays frame by frame (`_Travel`, `at_alpha`): every frame is `draw` on the spec with the corner at its
  place, so angles, arcs, values and the sum line are recomputed each frame, and the motion is cut into stages at the beat's steps
  (nothing moves before the first step). A moving picture has no hint plan (`ShapeFigure.hint_plan` returns `[]`: nothing of it
  stays to light) and it cross-fades in and out of its neighbours (`change_from`). So the plan's "new hint events" were not
  needed and not used; a motion beat is a different kind of beat from a lit one.
* **`drag`** (`"drag": "A"` on a triangle). Code writes the `move`: `geometry.drag_path` takes the triangle's other two corners as
  the base and sends the corner A through `DRAG_TOUR` (a wide triangle leaning left, a right angle at the first base corner, a tall
  narrow one, a wide one leaning right, then home), on A's own side of the base, in straight legs. Every point along every leg is
  a triangle whose smallest angle is at least `DRAG_MIN` (15 degrees; the test samples 401 moments for each corner and either
  side). Without `angles` the three interior angles are shown and `angle_sum` is on, so the line under the picture reads
  `83° + 62° + 35° = 180°` at every frame (the rounding to a whole-degree total is the figure's `round_to_total`, the same rule as a
  still). What the beat wrote wins: a `move` of its own is kept, `angles` and `angle_sum` too; a figure expanded a second time is
  unchanged. A `drag` that is not a corner of a three-point polygon (or whose corner lies on the base) is a plain fault. `settle`
  puts the tour into the shape's frame (`shapes[name].frame`), so every beat of that shape keeps one size; with no `drag` the
  frame is what it was. The narration of a drag beat must not quote the numbers the gaps fill (`{angle A}` is the corner's FIRST
  place): say the sum, which is a fact (`180` may be typed).
* **`transfer`** (`"transfer": {"from": "B", "to": {"at": "A", "from": "D", "to": "B"}}`, both angles also in `angles`). A copy of
  the first angle's wedge makes a HALF TURN about the middle of the line between the two corners and lands on the second angle.
  The plan said "slides along DE"; a slide lands on the corresponding angle (vertically opposite the one wanted), the half turn
  lands on the alternate angle, so that is what is drawn. `geometry.transfer_fault` checks it from the points: the half turn
  reverses each side's direction, so the copy lands only when the two corners' sides are opposite pair by pair, which for
  alternate angles between parallel lines is exactly "DE is parallel to BC". A transfer that does not land is a fault in
  `check_figure` ("the copy of angle B does not land on angle DAB ..."), as is one whose angles are not listed. Drawing: while the
  figure replays a moment (`_t`, set by `at_alpha`), `shape_figure._transfer_ghost` adds a translucent wedge turned by `pi * p`
  with `p = transfer_progress(alpha)` (waits to 0.15 of the beat, turns, rests from 0.80), and until it has landed the
  target's own arc and number are hidden: the number appears where the copy arrives. The built (still) picture that cross-fades
  in hides the landing too (`_hide_landing`); the end of the beat is the ordinary picture, both arcs and both numbers.
* **Measured** (free Kokoro films, quality l, the proof lesson's beats): a two-beat lesson, beat 2 `"drag": "A"` with three steps,
  31.8 s; frames every 1.5 s show the corner moving through the tour with `73° + 55° + 52° = 180°`, `45° + 110° + 25° = 180°`,
  `51° + 99° + 30° = 180°`, `47° + 42° + 91° = 180°` and back to `70° + 50° + 60° = 180°`. A transfer film (beat 1 draws DE, beat 2
  copies angle B): the wedge sits on angle B, goes through the middle of the triangle and lands on angle DAB (about 9 s across the beat's four steps; frames read at
  0.9 s), then `50°` appears at A. The first try failed with `figure 'shape' could not be built (... got multiple values for
  keyword argument 'outer_radius')` and showed no arcs at all (the old picture stayed, as designed): this Manim's `Sector` takes
  `radius`.
* **`pace: "voice"`** (S13, found while filming the third proof: a drag beat of 13.6 s moved only about 40% of the time).
  `runtime.stage_progress` plays a stage "soon and then waits" (`stage_seconds`: 40% of the gap to the next step, at least
  1.2 s), which is right for a block that appears and wrong for a corner that is dragged or a copy of an angle that turns. A
  shape figure that has `move`, `drag` or `transfer` and `"pace": "voice"` sets `fig.voice_paced`, and `_start_motion` calls
  `stage_progress(..., across=True)`: each stage takes the whole gap to the next step (the last one: to the end of the speech),
  evenly, resting a hair before the boundary as before. Off (no key, every stored lesson) the numbers are the old function's, a
  test compares the two over 1600 moments. Nothing moves before the first step, so put the first step on the sentence that
  starts the motion. (The attribute is `voice_paced`: `Figure.sweep()` is already a method.) Test: `tests/unit/test_shape_pace.py`.
* **Not done, and why.** (a) "Three arcs swing onto a straight line" (angles on a line): needs a second and third ghost and a
  landing place that is not one of the drawn angles; the same machinery (`transfer` as a list) would do it, but nothing on screen
  has been checked for it, so it is left. (b) "Make the two-triangle beat full width" and the narrow-corner values inside the arc
  or on a leader line: a drag replaces the two-triangle beat in a new lesson, but `panels` itself is unchanged, and a corner under
  45 degrees keeps its number just outside the corner as before (the film shows `25°` and `30°` close to C and the letter C beside
  them). Moving that for every shape changes every stored shape lesson; it would need its own gate and a measured look. (c) The
  writer is not told about either key: the writer's prompt is pinned (`test_prompts_pinned.py`), so they are for a lesson written
  by hand or by a Claude session through the workbench/MCP (`drag` and `transfer` are in the figure the workbench stores).
* Tests: `tests/unit/test_shape_motion_s10.py` (the tour is pure and every moment is a real triangle, either side and any corner, a
  bad corner is a fault, the keys write what they should and nothing else, the frame holds the tour only with the key, the sum line
  is `180°` while the corner and angles move, the transfer lands only for parallel lines, the copy starts on angle B, leaves it,
  lands within the arc's box and the number waits for it, no key means no motion).

## Larger writing in the card (video-quality plan step S12)

**Measured first** (`ComponentFigure` on the library's 28 components at their default state, free, no render; scratch script, the
stage scale taken from the larger of `look.picture_boxes`): the plan's "crop the card to the union of states actually used plus the
revealed parts" has nothing to crop. The card is already the box of ALL the drawing's parts and labels plus `CARD_PAD`, and every
part a beat holds back is shown by the end of that beat or a later beat of the run, so a smaller card would change size when a
part reveals (the docstring's rule, and what the S6 span exists to keep). The measured slack is elsewhere:

| what | measured on the 28 components |
|---|---|
| paper margin (`CARD_PAD` 0.18 each side) | 13% to 28% of the card's area (most 14% to 19%; the tall narrow `adult` and `child` 26% to 28%) |
| smallest label (14 px, stage scale of the larger picture box) | 18.1 pt (`clamp_stand`) to 52.8 pt (`splinter`); 21 of 28 under 28 pt, 12 under 25 pt; the balance film's `force_block` 24.4 pt (film: 24.6, 23.6, 22.4, 24.0 per S2) |
| drawing's own box against its card | 18% (`simple_pendulum`), 26% (`test_tube`), 34% (`cell`) to 85% (`food_chain`): the empty room is inside the library's own drawing, which is not ours to edit here |

So the two levers in this repo are the margin and the label size, and a larger label can widen the card (so shrink the drawing).
`LESSONFORGE_COMPONENT_TIGHT` (default OFF, group "Pictures", `render=True` so a render subprocess is told, read at render time like
the tween) does both, with a guard instead of a blind change:

* **Label size, `component_figure.tight_px`.** For a run of beats (the figure's `span`, S6) it takes the largest of
  `TIGHT_PX` (18, 17, 16, 15 px) at which (1) no drawing has more pairs of labels on each other than it has at 14 px, by
  `check.ts`'s own boxes (8 px a letter, scaled with the size, the check the library runs at 14) AND by the words as Manim sets
  them (`label_collisions`), and (2) the drawing put on the thinner card is still at least `TIGHT_KEEP` (97%) of the size it
  was on the old card (`_fit`, over the stage's two picture boxes); otherwise 14. One size for the whole run, so a label does
  not change size between states of one card and `extent_of` (cached per size) gives every state the same span frame.
* **Margin.** `TIGHT_PAD` 0.10 instead of 0.18 (`ComponentFigure(pad=)`).
* **Gate.** Off, `ComponentFigure` is built with `label_px=14`, `pad=0.18`: the same card, the same label places and sizes (a test
  compares both for six components). `place_labels` is the old loop moved into a function so the check and the figure use one
  placement. `ComponentFigure.change_from` stations use the figure's own size. Nothing in a lesson.json says anything; turning it
  on for new lessons is a default the owner can choose (a look key would be the other way, and was not needed to be safe).
* **Measured, 28 components** (before, tight; label pt, drawing scale = the stage scale of the card): smallest label under 28 pt
  in 21 components before, 2 after (`clamp_stand` 18.1 to 24.1 pt because its 14 px drawing is small, `leaf_section` 24.2 to 27.3);
  the smallest label of the whole set went from 18.1 to 24.1 pt (12 components under 25 pt before, 1 after); the drawing's scale median x1.028 (0.968 to 1.040), because the thinner margin
  pays for the larger words. The unguarded version (always 18 px) shrank `splinter`, `gravitation_fall` and `inclined_plane` by 8%
  to 9% and `plane_mirror_reflection` by 4%; the 97% rule makes those take 15 to 17 px.
* **Measured, the balance film** (8 beats, the workbench preview, `type_points`; free): smallest label per beat before to after
  23.6 to 25.1, 23.6 to 25.1, 32.0 to 38.6, 32.0 to 38.6, 22.4 to 22.4 (a motion picture, not a component), 24.0 to 24.8, 32.2 to
  41.1, 32.2 to 41.1 pt; card share of the frame 0.469 to 0.450, 0.596 to 0.547, 0.442 to 0.442, 0.427 to 0.432, 0.562 to 0.576.
  Free Kokoro films, quality l: `scripts/video_metrics.py` card median 0.555 to 0.543 (min 0.423 to 0.427, max 0.591 to 0.574),
  content unchanged (0.606). Looking at the frames: the force block is the same size and the words are larger, nothing lands on
  anything. The plan's "ink share of the force block from 18% to 30%" is not reachable from here: the block is a small part of
  the library's own canvas (`force_block.ts`), and the card already hugs the labels.
* **Not done.** The plan's check of `check.ts` was done in Python with its own boxes, not by running `check.ts` (read-only,
  out of this repo); a label sitting on another part's ART (not on another label) is not looked for, as the library does not
  look either. No default change.
* Tests: `tests/unit/test_component_tight.py` (off is built as before, label for label; on never makes a label smaller, the
  picture at most 3% smaller, no new pair of labels on each other; a crowded drawing keeps 14 px; one size and one card for a run
  of beats; the control is off by default and reaches a render subprocess).

## A Kokoro model that is a git-lfs pointer

A clone made without `git lfs pull` leaves a text file of about 130 bytes where `kokoro-v1.0.onnx` (or the voice pack
`voices-v1.0.bin`) should be, and a free film then ended with only "no speech backend produced audio". Now
`KokoroBackend._paths` (`longform/speech.py`) calls `check_not_lfs_pointer(label, path)` for `KOKORO_MODEL` and
`KOKORO_VOICES`: a file under 1024 bytes, or one that starts with `version https://git-lfs`, raises `KokoroModelError`
(a `RuntimeError`) saying that `<label> points at <path>, which is a git-lfs pointer (<n> bytes), not the Kokoro file`, that
the real file is hundreds of MB (the voice pack tens of MB), to run `git lfs pull` where it was cloned or to point the
variable at the real file, "usually in `/workspace/models/ComfyUI/models_local/tts/kokoro/`". `synthesize` resolves the
paths before importing `kokoro_onnx`, so this message comes first; an unreadable or missing file keeps its own
`FileNotFoundError`. When no voice produces audio, `harness/service.py` now appends each refused voice's reason (first 400
characters) to "no speech backend produced audio". Tests: `tests/unit/test_kokoro_lfs_pointer.py`.

## Maths for classes 1 to 12 (2026-11-09)

**Scope.** `component_lib.SCOPE_CLASSES` is now 1 to 12 (`scope_classes()`; `LESSONFORGE_SCOPE_CLASSES=6-9` or `6,7,8,9` brings
the old scope back, junk is ignored). `kit_pipeline`, the geometry kit (plane geometry is checked the same for every class) and
the components kit read it; motion and chemistry keep their own classes (7-9). A class outside 1-12 is a `PipelineError`
("class 13 is outside classes 1 to 12"). A component whose `ncert` strings name only a class outside the scope is refused as before.

**Components.** The lesson-visuals repo got 46 maths components (branch `maths/classes-1-12`, `docs/maths-components.md` there):
with them its chapter sheet reports all 161 maths chapters of classes 1 to 12 as drawable. They are plain library components: no
kit code was added for them; the kit reads their files like any other, and a new file needs no registration.

**Free test of any component (`scripts/components_suite.py`).** Loads each component through the kit, turns every situation into
lesson beats (`situation_to_beats`, no model), settles the lesson and prints an issue per failing situation; `--out DIR` writes the
lessons for `workbench.add` and `film`. Results on the pinned maths tree: 195 situations over the 47 maths components, 189 of them
the 46 new ones, 0 issues; over all 92 components 315 situations and 1 issue, the owner's `counters` situation
`deal_round_by_round` (step 4: its first part `items` draws nothing and the kit requires the outline). 1477 unit tests pass.

**Films (free: Kokoro, quality m, `LESSONFORGE_COMPONENT_TWEEN=1`, `LESSONFORGE_COMPONENT_TIGHT=1`, no paid key).** One situation per
family, taken straight from the component with no model and no editing, measured with `scripts/video_metrics.py` (medium
threshold, countdown bar masked):

| video (classes the component serves) | seconds | moving | longest still | card (median) | silence |
|---|---|---|---|---|---|
| ten_frame make 10 then add (1-2) | 25.8 | 31.2% | 8.1 s | 50.8% | 46.3% |
| flat_shapes trace a face (2-5) | 25.6 | 27.6% | 6.8 s | 47.9% | 47.1% |
| balance_scale find the unknown (1-7) | 34.0 | 18.6% | 10.5 s | 46.5% | 33.9% |
| solid_nets cube net (3-10) | 34.7 | 20.8% | 11.1 s | 43.9% | 38.9% |
| parallel_transversal corresponding (7) | 46.6 | 20.6% | 10.0 s | 50.0% | 33.4% |
| algebra_tiles (x+2)(x+3) (7-9) | 48.9 | 19.5% | 10.8 s | 46.8% | 33.8% |
| right_triangle_trig sin cos tan (9-10) | 37.2 | 22.4% | 7.4 s | 52.9% | 40.3% |
| probability_tree two coins (9-12) | 44.3 | 19.0% | 9.9 s | 44.1% | 34.4% |
| conic changing eccentricity (11) | 46.8 | 20.1% | 10.1 s | 50.0% | 34.6% |

What they show: every picture is right (numbers computed, the net folds, the tiles regroup, PF/PD = e at each eccentricity), and
the sentences are the components' own `say` lines. They are **not** at the hand-made triangle lesson's level (51.3% moving, longest
still 2.4 s, 89 s): a situation is a handful of sentences, one beat per change of numbers, and where only parts appear a picture is
held while the voice speaks (7 to 11 s). Closing that gap is lesson writing, not components: more beats that change a number with
the voice (the S9 tween), a title and a closing hold, and a written pace. The proofs here are the floor, not the target.

Found while filming: the film drops `transform` on `<text>` (a rotated side label landed on a tile in `algebra_tiles`; fixed there),
and a dashed circle drawn as a progressive trace (`flat_shapes`) appears whole.

## Using it

```
lessonforge kits list                                   # kits and components, free
lessonforge kits describe chemistry                     # metadata, the writer's rules, example figures
lessonforge kits route "Class 8: a car speeds up from rest at 2 m/s2 for 6 s." --subjects physics
lessonforge kits route brief.md --classes 7,8 --json    # a plan as JSON; text or a file
lessonforge kits run brief.md --lesson lesson.json --preview   # check a ready lesson: no model, no cost
lessonforge kits run brief.md --cap 0.50 --film         # writes with the model (<= $0.50), repairs, films when clean
```

`route` printed, for "Class 8: A car speeds up from rest at 2 m/s2 for 6 s. Balance 2H2 + O2 -> 2H2O to show atoms are
conserved. Find the hypotenuse of a right triangle with sides 3 and 4.", the kits `motion`, `chemistry`, `geometry`
(mixed), classes 8. The same through MCP (`lessonforge mcp`; all four are free, none calls a model):

```
list_kits()
describe_kit(name="components")
route_kits(text="A block on a rough table: friction.", classes="8", subjects="physics")   # -> components:force_block
run_kit_pipeline(brief_text="...", lesson_json="{...}", preview=false)     # check only; film with the film tool
```

`run` exits 2 without `--lesson` and `--cap` (it will not look for a model), 1 when faults remain, 0 when clean. Money: see
the `Meter` rules above; every number a lesson shows still comes from a kit's model, whoever wrote the words.

## Class and subject to kit

Owner's scope (2026-11-09): four subjects (maths/geometry, physics, chemistry, biology and earth through components),
Classes 1 to 12 (NCERT; `LESSONFORGE_SCOPE_CLASSES`), lessons may mix subjects. "Kit" = a registered kit whose code checks the facts; "figure kind" = a
built-in kind drawn from its own numbers (`bars`, `number_line`, `circle`, `rectangle`, `graph`, `float`, `right_triangle`:
`figure_math` checks some, but no registered kit does, and the router does not target them); `scene` is a model-written
animation, which breaks "code decides every fact", so use it only for pictures that carry no number. Per chapter (Class 8
and 9 titles from `ncert_concepts.json`) and the chapters nothing can draw: [kits-coverage.md](kits-coverage.md).

| Class / subject | Drawn today by | Not drawn |
|---|---|---|
| 6 Maths | figure kinds `number_line`, `bars`, `rectangle`; kit `geometry` (polygons) | (the Class 6 and 7 chapter lists are not in the repo, so no chapter is named; this row is the scout's reading of the topics) |
| 6 Science | kit `components` (`child`, `adult` only) | all of it: the biology and earth components are not in the default checkout |
| 7 Maths | figure kinds `number_line`, `bars`, `graph`, `rectangle`, `circle`; kit `geometry` | expressions |
| 7 Science | kits `chemistry` (formula equations only: no word equations yet), `motion`; component `test_tube` | heat, electricity, light (no component in the default checkout); no pH kit |
| 8 Maths | kit `geometry`; figure kinds `rectangle`, `circle`, `right_triangle`, `bars`, `number_line`, `graph` | 4 of 14 chapters (02, 03, 05, 12) |
| 8 Science | kit `chemistry` (08, partly); components `force_block`, `inclined_plane` (05, picture only) | 04, 06, 07, 10; biology and earth (02, 03, 11, 12, 13) until components exist |
| 9 Maths | kit `geometry`; figure kinds `graph`, `number_line`, `rectangle`, `circle` | 01, 05, 07, 08, 09, 10, 11, 14 |
| 9 Science | kits `motion` (04, 06), `chemistry` (09); components `force_block`, `inclined_plane`, `gravitation_fall` | 01, 08, 10 (claims), biology and earth (02, 03, 11, 12, 13) |

A table in `kit_pipeline.py` keyed by chapter id is not built: the router uses words, class and subject
(see "Limits of the router today").

## Adding a subject

1. Write the pure model (no manim, no numpy at import time).
2. Subclass `KitBase` in `kits/<subject>.py`: `name`, `figure_kinds`, `rules` (the writer's section), `solve`,
   `fill_gap`, `claims`, `stray_numbers`, `cases`; set `builder = {"<kind>": "pkg.mod:func"}` if a Manim figure is
   needed; call `register(Kit())` at module end.
3. Set `subjects`, `classes` (a subset of 1 to 12) and `keywords` (lower case; words a brief or a beat would use, phrases allowed): the
   router (`kit_pipeline.route`) and `kits list|describe` read them from `kits.describe()`, so a kit that declares no keywords scores only from `EXTRAS` and `PATTERNS`.
   Optional, in `kit_pipeline.py` (data, not kit code): `EXTRAS` (more router words) and `PRIORITY` (a tie-break, default 2).
4. Add the module name to `_BUILTIN` in `kits/__init__.py`. Use a NEW figure kind: `register()` refuses a non-legacy kit on a
   built-in kind (`registry.BUILTIN_KINDS`), which is why chemistry owns `chem_reaction` and not `reaction`.
5. `tests/unit/test_kits_registry.py::test_every_registered_kit_meets_the_protocol` runs the kit's cases through its
   own `settle`; write the kit's own test file beside `test_kits_motion.py` (`test_kits_reaction.py` is the second example).
   A built-in prompt is not edited: its sha256 is pinned (`test_prompts_pinned.py`), the kit's `rules` travel in the addendum.
6. A new component in lesson-visuals needs none of this: add `components/<subject>/<id>.ts` there (see its
   `docs/lessonforge-kits.md`).

## Phases

| phase | what | state |
|---|---|---|
| 0 | prompt pins + geometry goldens (tests only) | done |
| 1 | `kits/base.py`, `registry.py`, `LESSONFORGE_KITS` | done |
| 2 | `longform/motion_math.py` | done |
| 3 | `kits/geometry.py` legacy adapter + parity tests | done |
| 4 | `kits/motion.py` | done |
| 5 | `longform/kit_figures.py` + the additive branch in `figures.build` (manim side) | done |
| 6 | writer and `figure_math` seams (discipline gate, `figure_numbers`, `brief["kits"]` rules, `kit_pass`) | done |
| 7 | workbench, improver and MCP seams (`faults_of`, `_expected_fault`, `apply_edits` ops, addendum, MCP note) | done |
| 8 | this document and the CLAUDE.md bullet | done |
| - | one real low-quality render of a motion lesson through the workbench | needs the owner's agreement to spend |
| 9 | route geometry through the registry behind `LESSONFORGE_KITS_GEOMETRY` (default off) | later, owner's call |
| 10 | ReactionKit (done, as the served kind `chem_reaction`; substance-name table and `visual_actions` cover not done); FloatKit adapter and float claims | float later |
| - | mixed-subject lessons (`LESSONFORGE_KITS_MIXED`), branch `kits/mixed-pipeline` | done |
| - | components kit (`kits/components.py`, `longform/component_lib.py`, `longform/component_figure.py`) | done; reads the number-state contract, situations, layer and ground (see Components); filmed in both proof videos |
| - | the pipeline that calls the kits (`harness/kit_pipeline.py`, `lessonforge kits ...`, MCP tools) | done; no paid call made |

## Deviations from the first design

* `motion_math` raises its own `MotionError(ValueError)`; `MotionKit.solve` turns it into `KitError`. Importing
  `kits.base` from `motion_math` would be circular (`kits/__init__` imports `kits.motion`, which imports `motion_math`).
* A motion gap's time must be a mark, 0 or `duration` (the design allowed any number). Otherwise the filled value would
  read as a typed number on the next check of the lesson.
* The y-axis label is "velocity (m/s)" when the run goes below zero, otherwise "speed (m/s)".
* Stray-number tolerance includes differences between two shown values of the same kind, so `{speed at 6 - speed at 3}`
  survives a re-check.
* Geometry's `set_shape` op and `workbench.set_shape` share `kits.geometry.declare_shape`, which re-points the beats that
  show the shape at the new one (a bug the 2026-11-07 video run found); `workbench.add` now settles shape lessons first.

* `kit_pass` settles with every active kit in turn and asks for repairs with the first kit's `repair_prompt`; the lesson's
  record is `kit_check = {"kits": [...], "faults_left": [...]}` (the design said `"kit": name`).
* With `LESSONFORGE_KITS_MIXED=0`, `workbench.faults_of` returns only the one-subject fault for a mixed lesson; each
  checker alone would add false faults for the other subject's gaps (with mixing on, the ownership filter removes them).
* `figures.build` also guards the loading of a kit's builder (an import error keeps the previous picture).
* New registry helpers beyond the design's list (`mixed`, `is_expected_fault`, `settle_active`, `slim`,
  `rules_for_lesson`, `mcp_note`) and an optional `KitBase.mcp_note` attribute.
* The `mcp` package is not installed in the dev venv, so the MCP test builds the server against a stand-in `FastMCP`.
* The optional runtime guard in `_start_hints` was not added.
* The components kit splits as the motion kit does: the Node plumbing and the catalogue are `longform/component_lib.py`
  (stdlib only), the kit class is `kits/components.py`, and `kits/components.py` re-exports `catalogue`, `draw`, `validate`,
  `available`, `broken`, `classes_of`, `ComponentError`. Its `rules`, `subjects`, `classes`, `keywords` and `focus_parts` are
  properties computed from the catalogue, not constants.
* `registry.rules_for` and `rules_for_lesson` understand a `kit:argument` name (`components:id1,id2`) through an optional
  `Kit.rules_with(argument)` / `Kit.rules_name(lesson)`; a kit without them behaves as before.
* `test_kits_workbench.py::test_the_mcp_instructions_carry_one_sentence_per_served_kit` counted at most two full stops for
  the two served kits it knew; it now allows one per served kit with an MCP note.

## Env switches added with this work

* `LESSONFORGE_KITS` (default `1`): the kit registry on or off.
* `LESSONFORGE_KITS_MIXED` (default `1`): lessons may draw from several kits, each checking its own beats. `0` restores the
  one-subject fault. No effect while `LESSONFORGE_KITS=0`.
* `LESSON_VISUALS_DIR` (default `/home/mani/lesson-visuals`): the lesson-visuals checkout whose `components/` the components
  kit reads. `LESSONFORGE_NODE`: the Node binary (default: `node` on `PATH`, then `~/.local/bin/node`). Without a usable
  Node 22.6+ and that folder the components kit is not registered (one log line).
* `LESSONFORGE_COMPONENT_FRAME` (default `1`, control in "Pictures"): at settle time, a run of beats on one component shares one
  card (`span`, "One card for a run of beats on one component"). `0` writes no span.
* `LESSONFORGE_COMPONENT_TWEEN` (default `0`, control in "Pictures", read at render time): a number that moves between two beats
  of one run on one component is morphed in the lead-in instead of fading out and being redrawn ("A number that moves is a
  tween"). `0` is the old fade.
* `LESSONFORGE_COMPONENT_TIGHT` (default `0`, control in "Pictures", read at render time): larger labels (15 to 18 px where none lands
  on another label and the drawing loses at most 3%) and a 0.10 margin on a library component's card ("Larger writing in the card").
  Geometry `drag` and `transfer` are figure keys, not switches ("Geometry that moves").
* `LESSONFORGE_NO_DOTENV=1`: skip the `load_dotenv()` calls in `engine/__init__.py` and `cli.py` (default: load).
* `workbench.film()` hides every key in `lessonforge.env.PAID_KEYS` for a free film (a paid voice needs
  `paid_checks=True`).
