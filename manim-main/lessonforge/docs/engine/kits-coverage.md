# Which kit can draw which chapter (Classes 8 and 9)

> **Update 2026-11-09 (maths, classes 1 to 12).** The tables below were assessed before the lesson-visuals repo got its 46 maths
> components. Its chapter sheet now lists every maths chapter of classes 1 to 12 (161 of 161) as drawable by a library component
> (`docs/maths-components.md` there; the `components` kit draws them). Read the class 8 and 9 maths rows below as older: most "gap"
> rows have a component now (coordinates: `coordinate_plane`; probability: `probability_tree`; solids: `solid_shapes`, `solid_nets`;
> circles: `circle_parts`; sequences: `dot_patterns`, `pascal_triangle`; data: `tally_marks` and the `graph` kind). Science rows are unchanged.

Status 2026-11-09. This is an assessment made by reading the chapter titles and the kits' code, not a record of lessons
made. Chapter ids and titles are from `ncert_concepts.json` in the adhyay repo (`server/sources/`, ids `C8-MAT-01` ...); no
Class 6 or 7 list exists in this repo or that file, so those classes are covered only by topic in
[kits.md](kits.md#class-and-subject-to-kit). The router does not read chapter ids yet (words, class, subject only).

Names: `shape` = kit `geometry`; `motion`, `chemistry` (`chem_reaction`), `components` are the other registered kits.
Built-in figure kinds (no registered kit checks them): `right_triangle`, `number_line`, `bars`, `circle`, `rectangle`,
`graph` (draws `y = f(x)`; a point is always put ON the curve, so a free point cannot be plotted), `float` (density and
flotation only). "gap" = nothing in the repo draws it with code-decided facts.

## Class 8 Mathematics

| id | chapter | drawn by |
|---|---|---|
| 01 | A Square and A Cube | `rectangle` (grid, w = h), `number_line` |
| 02 | Power Play | gap |
| 03 | A Story of Numbers | gap |
| 04 | Quadrilaterals | `shape` |
| 05 | Number Play | gap |
| 06 | We Distribute, Yet Things Multiply | `rectangle` (area model; the algebra is not checked) |
| 07 | Proportional Reasoning-1 | `graph` (linear), `bars` |
| 08 | Fractions in Disguise | `bars`, `number_line` |
| 09 | The Baudhayana-Pythagoras Theorem | `right_triangle` |
| 10 | Proportional Reasoning-2 | `graph` |
| 11 | Exploring Some Geometric Themes | `shape` |
| 12 | Tales by Dots and Lines | gap (needs a data-chart kind: plotted points) |
| 13 | Algebra Play | `graph` (partly), `number_line` |
| 14 | Area | `rectangle`, `circle`, `shape` |

## Class 8 Science

| id | chapter | drawn by |
|---|---|---|
| 01 | Exploring the Investigative World of Science | `components` characters only |
| 02 | The Invisible Living World | `components` biology (none in the default checkout) |
| 03 | Health: The Ultimate Treasure | `components` biology (none) |
| 04 | Electricity: Magnetic and Heating Effects | gap (no circuit kit) |
| 05 | Exploring Forces | `components` `force_block`, `inclined_plane` (picture; a force-balance kit would add claims) |
| 06 | Pressure, Winds, Storms, and Cyclones | gap (`float` is density only) |
| 07 | Particulate Nature of Matter | gap (`scene` only: no particle-state kit) |
| 08 | Nature of Matter: Elements, Compounds, and Mixtures | `chemistry` (formulas, atoms of an element or compound), partly |
| 09 | The Amazing World of Solutes, Solvents, and Solutions | `components` `test_tube` only |
| 10 | Light: Mirrors and Lenses | gap (no ray kit in lessonforge; lesson-visuals has `visuals/figures/rays.py`) |
| 11 | Keeping Time with the Skies | `components` earth (none) |
| 12 | How Nature Works in Harmony | `components` biology (none) |
| 13 | Our Home: Earth, a Unique Life Sustaining Planet | `components` earth (none) |

## Class 9 Mathematics

| id | chapter | drawn by |
|---|---|---|
| 01 | Orienting Yourself: The Use of Coordinates | gap (plot points, distance, midpoint) |
| 02 | Introduction to Linear Polynomials | `graph` |
| 03 | The World of Numbers | `number_line` |
| 04 | Exploring Algebraic Identities | `rectangle` (area model, partly) |
| 05 | I'm Up and Down, and Round and Round | gap (`shape` is polygon-only: no chords, arcs, circle angles) |
| 06 | Measuring Space: Perimeter and Area | `rectangle`, `circle`, `shape` |
| 07 | The Mathematics of Maybe: Introduction to Probability | gap |
| 08 | Predicting What Comes Next: Sequences and Progressions | gap |
| 09 | Propositions and their Converses | gap (words only) |
| 10 | How Quantities Combine: Understanding Data | gap (no chart kind) |
| 11 | The World of Algorithms | gap |
| 12 | Quadrilaterals | `shape` |
| 13 | Two Variables, One Line | `graph` |
| 14 | Math of Space: Surface Area and Volume | gap (no 3D solids) |

## Class 9 Science

| id | chapter | drawn by |
|---|---|---|
| 01 | Exploration: Entering the World of Secondary Science | gap (introductory) |
| 02 | Cell: The Building Block of Life | `components` biology (none) |
| 03 | Tissues in Action | `components` biology (none) |
| 04 | Describing Motion Around Us | `motion` (speed-time); distance-time is a gap |
| 05 | Exploring Mixtures and their Separation | `components` chemistry (separation apparatus missing) |
| 06 | How Forces Affect Motion | `motion`; `components` `force_block`, `inclined_plane`, `gravitation_fall` |
| 07 | Work, Energy, and Simple Machines | `components` `inclined_plane` (pulley and energy bars missing) |
| 08 | Journey Inside the Atom | gap (no shell or electron-configuration kit) |
| 09 | Atomic Foundations of Matter | `chemistry` (conservation of mass, formulae) |
| 10 | Sound Waves: Characteristics and Applications | `graph` (sin), partly, no claims |
| 11 | Reproduction: How Life Continues | `components` biology (none) |
| 12 | Patterns in Life: Diversity and Classification | `components` biology (none) |
| 13 | Earth as a System: Energy, Matter, and Life | `components` earth (none) |

## What is missing, in the order it blocks lessons

1. Biology and earth components in the checkout the kit reads (the owner adds them in lesson-visuals; the loader now
   accepts the newer contract, number states and situations, so the newer library is drawn when `LESSON_VISUALS_DIR`
   points at it): see "Components" in [kits.md](kits.md).
2. A chapter-aware router, and the Class 6 and 7 chapter lists (get a source first).
3. Kits for: plotted points and data charts, circle geometry, electric circuits, rays, particle states, 3D solids, a
   distance-time graph, a substance-name table for the chemistry kit.
