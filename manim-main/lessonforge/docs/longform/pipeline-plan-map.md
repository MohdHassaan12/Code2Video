# LGLG's video pipeline plan, stage by stage, against lessonforge (2026-10-17)

LGLG's plan (relayed 2026-10-17): lesson spec → instructional planner → one shared scene-and-narration storyboard →
audio (TTS, pronunciation, phrase alignment) and visuals → timeline compiler → render and evaluate → quality gate
and repair of only the affected beats → final video with its sources. It recommends TypeScript + Zod + Remotion +
FFmpeg and "make the storyboard and timeline compiler the core".

## What exists, per stage

| Plan stage | Plan artifact | lessonforge today | Where |
|---|---|---|---|
| Lesson spec | lesson.json (spec) | the brief: topic, class, level, length, language, sources; Socratic intake fills it | `harness/intake.py`, `job.json` → `brief` |
| Instructional planner | teaching_plan.json | the teaching card: big idea, objectives with Bloom levels, misconceptions, opening question, route, checks; one stable card per concept | `harness/card.py`, `harness/concepts.py`, `library/packs/<slug>/card.json` |
| Shared storyboard | storyboard.json | `lesson.json`: chapters → beats; each beat has narration, steps (`say` anchor phrase + `show` + `kind` + `focus` + `draw` + `annotate`), figure, quiz, depth | `harness/writer.py`, `longform/contract.py` |
| Narration quality gate | (in plan) | the reviewer (a different model family, claims checked by code) plus code gates: length, language, repetition, settings, questions, coherence | `harness/critic.py`, `harness/questions.py`, `harness/coherence.py` |
| Storyboard gate before audio | (in plan) | `qa.storyboard_findings`, logged before speech; since 2026-10-18 `qa.mend_storyboard` sends the failing beats back for new steps first | `harness/qa.py` |
| Audio | narration.wav + alignment | per-beat synthesis, measured durations, whisper word times, every cue labelled `aligned` or `word-position` | `longform/audio.py`, `longform/align.py`, `longform/speech.py` |
| Visual action library | (in plan) | closed figure inventory drawn by code from numbers; prepared drawings taken apart into parts; pen drawing with the words; annotation kinds (`annotate.KINDS`) | `longform/figures.py`, `harness/diagrams.py`, `harness/sequence.py`, `harness/annotate.py` |
| Timeline compiler | timeline.json | `timeline.json` is the only source of timing; scenes anchor to spoken phrases and wait for them | `longform/audio.py`, `longform/runtime.py` (`GuidedChapter.cue`) |
| Render and evaluate | draft.mp4 | one Manim render per chapter, layout probe after every play, bounds, technical checks; stills preview before any audio is paid for | `longform/build.py`, `layout_probe.py`, `longform/preview.py` |
| Vision review | (in plan) | stills look before speech; frame review of the film after | `harness/vision_review.py`, `harness/compose.py` |
| Quality gate + targeted repair | qa_report.json | repairs exist per beat or chapter (screen rewrite, compact re-lay, picture mend), each kept only if it improves things; **new**: one `output/qa_report.json` per lesson, keyed by beat, each finding naming its stage and the pass that owns its repair | `harness/repairs.py`, `service.chapters_to_relay`, `harness/qa.py` |
| Final + source bundle | final.mp4 + sources | `output/` holds the video, captions, `timeline.json`, `interactions.json`, `annotations.json`, checks, reviews | `results_from_disk` in `harness/service.py` |

## The stack question

Concept Explorer (ManideepDonkena/concept_explorer) uses TypeScript only for its interactive lesson player
(`harness/`: Zod schema package, React web app, Expo app). Its video side is Python and Manim (`ce/` →
`stem_animation_lab`), which is the engine lessonforge grew from. No Remotion anywhere. lessonforge's Expo client is
TypeScript too, and plays the videos. Rewriting the video pipeline in TypeScript + Remotion would rebuild every stage
above, including the layout probe and the phrase-anchored renderer, before getting back to today's quality. So:
the storyboard (`lesson.json`) and `timeline.json` are already the core LGLG asks for; they stay in Python, and the
TypeScript side reads them as JSON (the player already reads `interactions.json` and `annotations.json`).

## Built on 2026-10-17

- `harness/qa.py`:
  - `storyboard_findings(lesson)` checks the storyboard before audio, by code, with no model: an anchor the narration never says; anchors out of order; a beat with nothing on screen; two or more spoken numbers the screen never shows; a figure one beat late; an unknown still "?" after the voice states it.
  - `report(lesson_dir)` merges those with the reviewer's unresolved findings, the stills look, the layout probe, bounds, technical checks, late cues and the frame review. It writes `output/qa_report.json` (`status`, `by_stage`, `beats_to_repair`, each finding's `repair`).
- Both run in `service._run` as advisory steps. They report and change nothing.
- Run on 48 finished lessons (no model, no cost): 10 pass. The storyboard gate found 72 beats where the voice gives numbers the screen never shows, 7 late figures and 5 unknowns left as "?". The paid frame review found several of the same faults only after the render (trigonometry beat 04: "the voice says 6, 7, 8 and the screen never shows them").

## Built on 2026-10-18: the gate repairs before speech

- `qa.mend_storyboard(lesson, llm)` takes beats whose voice says numbers the screen never shows, or whose anchors are
  missing or out of order (worst first, at most 6), and has `repairs.fix_steps` write their steps again. A new set is
  kept only when that beat's findings drop, nothing new appears, and every line that was on screen is still there.
  Then `writer.point_again`. Kept in the stage store, so the same lesson again pays nothing. Switch:
  `HARNESS_STORYBOARD_MEND` (on).
- Tried on five finished lessons (no audio, under 1 cent): 13 of 17 faulted beats fixed, 2 put back.
- `annotate.spoken_numbers` now reads decimals said in words ("zero point zero two" is 0.02), which the storyboard gate
  and the marks share: before, "0.02" on screen was "not shown" against a voice that said it.

## Not built, and why

- The gate does not block a lesson: a beat it cannot mend is rendered as it is and stays in the report.
- No pronunciation check for TTS. The recogniser's match rate per block is the nearest thing, and it already runs.
- No exported JSON Schema of `lesson.json` for a Zod import. Easy to add once the TypeScript side needs it.
