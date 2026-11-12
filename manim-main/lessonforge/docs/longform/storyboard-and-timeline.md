# The shared storyboard and the timeline compiler (2026-10-17)

The owner's design note for Concept Explorer asked for a pipeline whose core is a shared storyboard (one record per
teaching beat that the narration and the visuals are both made from) and a timeline compiler (visual events placed on
the spoken audio), with a file and a check for each stage. It assumed a TypeScript, React and Remotion stack; the
video pipeline is lessonforge (Python, Manim), which already worked this way inside its code. This change makes the
intermediate representation explicit and checked, without changing how a lesson is written, narrated or rendered.

## The stages and their files

| Stage | File (in the lesson folder) | Made by | Checked by |
| --- | --- | --- | --- |
| 1 Lesson spec | `output/lesson_spec.json` | `storyboard.lesson_spec` (from the brief) | intake asks for level, goal, language, length |
| 2 Teaching plan | `output/teaching_plan.json` | `storyboard.teaching_plan` (framework roles, example, method, mistake, checkpoints) | `writer.continuity`, `coherence.py` (flow) |
| 3 Shared storyboard | `output/storyboard.json` (+ `lesson.json`, the renderer's copy) | `storyboard.from_lesson` | **`storyboard.validate`**, before any narration is bought; `repair` fixes the failing beats |
| 4A Audio | `audio/narration.wav`, `timeline.json`, `audio_report.json`, `output/captions.vtt` | `audio.build_audio` (speech first, measured; whisper word alignment) | coverage, alignment match rate |
| 4B Visuals | figures, drawings, scenes, steps, marks in `lesson.json`; `chapters_*.py` | writer, `diagrams`, `sequence`, `annotate`, `sim_gen` | `compose` stills preview, `layout_probe` |
| 5 Timeline | `output/sync_timeline.json` | **`timeline_compiler.compile_lesson`**, after speech and before rendering | anchors spoken, beats end to end, crowding, reading time |
| 6 Render | `output/<slug>.mp4` | `build.render_chapters`, `assemble` | `output/final_checks.json`, `vision_review.json` |
| 7 Quality gate | `output/qa_report.json` | **`qa.write_qa`** | one list of checks in six areas, each fault mapped to its beats and the component that fixes it |
| 8 Release | `output/bundle.json` | **`qa.write_bundle`** | every stage file with its sha256 and the code commit; rebuild with `lessonforge lesson build` |

## What a storyboard beat holds

`narration` (exactly what is spoken), `visual_intent`, `figure`, `events` (figure drawn in, a step of words or a formula,
a hand's mark, a question), each event with the `anchor` phrase it waits for, `reasoning` (what the viewer should be
able to do after the beat), `thinking_pause_seconds` and `validation` (the rules the beat is checked against).

## The gate (stage 3)

Code, not a model. Errors: markup in narration; an event anchor that the renderer will not find (it searches inside one
sentence, in order: `phrase_at` is the same search); a question without time to answer. Warnings: symbols a voice cannot
read, a sentence over 45 words, a beat with nothing planned for the screen, anchors out of order, a mark whose words are
not said. `repair` touches only the beats with an error: strips markup (never in an author's own script) and re-anchors
a step on the sentence that holds most of its own words. A lesson built from its folder (`lessonforge lesson build`) is
reported on and not changed.

## The compiler (stage 5)

`timeline_compiler.locate` IS the renderer's search (`runtime.LessonScene.locate` calls it), and `compile_timeline`
follows `GuidedChapter`'s scheduling, so the times in `sync_timeline.json` are the ones the render will use, with their
source: `aligned` (heard words), `word-position/…` (estimated inside a measured sentence), `fallback-spread`
(the words were never found), `lead-in` (a picture drawn before the voice). Any other player can be driven from this
file and `narration.wav` without re-deriving anything.

## The sync repair (2026-10-19, `longform/sync_repair.py`)

The compiler's findings are acted on. Right after `timeline.json` exists (before the render), every beat with an
`anchor spoken`, `events crowded`, `reading time` or `after the voice` issue has its steps given new anchors among the
words actually heard: a step whose own words leave room for the step before keeps them; otherwise it takes the three
spoken words, after the step before and late enough for that step to be read, from the sentence holding most of the
step's own words. The beat is compiled again alone, and the change is kept only when its issues score lower (an error
weighs ten warnings) and it gains no error. Nothing that is spoken is changed. `HARNESS_SYNC_REPAIR=0` leaves it out.

**Thinning (2026-10-19).** Moving anchors cannot make room the narration does not have: a beat whose words give its
lines too little time (a six-word line up 1.7 s at the end of its beat; a line 0.5 s before the next) is thinned when
re-anchoring alone leaves it faulted. Greedy, one cut at a time, each re-anchored and kept only when it lowers the score:
a line that mostly repeats another line of the beat is taken off first; then a line is cut to its first clause ("It must
spin, once per orbit" → "It must spin"); then a plain point the voice says anyway is taken off. Never a line that asks
(the question card is made from it), works something out (`math`), points at the picture (`focus`) or draws part of it
(`draw`), nor the beat's only key line; a hand's mark on a line taken off goes to its neighbour. On the five lessons
with a timeline: 5 reading/crowding warnings → 0, four beats thinned (Moon 02, 05, 07; Monty Hall 11), every frame of
those beats looked at after filming again. `HARNESS_SYNC_THIN=0` leaves it out.

The screen repair (`harness/repairs.repair_screen`) writes steps again AFTER that, so it calls the same repair on its
new steps before it films them (on the Monty Hall lesson four rewritten beats had lines up too briefly to read).

`lessonforge lesson mend <folder>` does it on a finished lesson: only the chapters whose beats changed are filmed again,
from the lesson's own audio, and the first render is put back unless the layout checks are no worse; then the
storyboard, timeline, QA report and bundle are written again. On the heavy-ball lesson it took QA from failed (two
crowded beats, one unanchored step, cues 0.64 s late) to passed with warnings by re-filming two of seven chapters, and
on the Monty Hall lesson reading-time warnings from four beats to one.

## What is not done

- The sync repair acts on the timeline's own checks. A `fail` of another component in `repair_plan` (a claim, an
  overlap inside a model-written scene) is still acted on only by the repairs that already existed before this report.
- The gate and compiler are advisory: they never stop a lesson. A timeline `error` (beats not end to end, a beat with
  no narration) would be a bug in the audio stage, not a content problem.
- Thinning cures a beat after the fact; the writer still writes more lines than some beats have time for. Telling
  the writer a budget of lines per beat (from its words) would prevent it, and is a prompt change for every lesson.
- Reading-time and crowding thresholds (`READ_WORDS_PER_SECOND` 3.0, `MIN_EVENT_GAP` 0.6 s) are first guesses, not
  measured with learners. They were left as they are after five real lessons (2026-10-19): what they flagged the sync repair
  could mostly cure, and nothing measured said another value was better. Frames were looked at per beat, not per step.
