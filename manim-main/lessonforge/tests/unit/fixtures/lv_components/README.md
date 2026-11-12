# A pinned snapshot of six lesson-visuals components

These six files are the owner's own, copied unchanged from `components/` of the lesson-visuals repo (`origin/main`, at
`ffcb242` when copied on 2026-11-09, read through a read-only extract). They are here so the components kit's tests do not
depend on the owner's checkout, which is moving: the owner adds components there every day.

| file | why it is here |
|---|---|
| `chemistry/test_tube.ts` | named states and a number state (`bubble_rate`) together, three situations, `layer` and `ground` |
| `physics/force_block.ts` | the older shape: named states only, no number state |
| `physics/simple_pendulum.ts` | a number-only state (`time_s`), no `layer` or `ground`, numbers in its situation lines |
| `biology/leaf_section.ts` | named presets and number states that must agree (`stoma`/`opening`, `time`/`light`), a text-free outline |
| `maths/number_line.ts` | a maths component, `hops_done` against its named `progress`, a situation that moves one number |
| `characters/child.ts` | a person: `layer: actor`, drawn head up |

Do not edit them. To move the snapshot, copy the newer files over and run `tests/unit/test_kits_components.py`; the
fixed numbers in those tests come from these files. `tests/unit/conftest.py` points `LESSON_VISUALS_DIR` here for every
unit test; a real tree can be checked with `LESSON_VISUALS_DIR=<tree> pytest tests/unit/test_kits_components.py -k real_tree`.
