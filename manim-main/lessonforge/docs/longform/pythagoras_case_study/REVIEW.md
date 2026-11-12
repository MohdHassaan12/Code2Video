# Production review

**Updated user feedback, 7 October 2026:** the narration is poor and lacks coherence. Technical checks below remain valid within their stated scope, but the lesson has not passed audio acceptance. The next iteration must address connected speech, Google TTS evaluation, alignment and purposeful highlighting. See the [handoff report](../HANDOFF_REPORT.md).

This is an original reference lesson for further teacher review, not a demonstrated learning-outcome improvement or a launch approval. The concept is the Pythagorean theorem as an area relationship that yields a length.

## What was built

- Ten coherent chapters, forty narration beats, 2,906 spoken words, two worked problems and three learner questions.
- Measured neural narration and thinking time totaling exactly1,200 seconds; 274 synthesized sentences.
- Deterministic geometry, 173 spoken animation anchors, English captions and chapter navigation.
- Ten source explanations: three primary-site video/classroom transcripts and seven written educator explanations. Public video metadata is separately labeled and was not treated as a watched explanation.

## Review findings and repairs

The premium script needed corrections to the central-angle argument, translated coordinates, premature answer disclosure and the distinction between bounds on a leg versus a hypotenuse. Repetition was reduced from3,627 to2,906 words.

The premium animation drafts were useful as implementation drafts but were not acceptable unchanged. They contained invalid central-square coordinates, non-square polygons described as squares, content outside the frame, overlapping equation layers, nonexistent spoken cues and a truncated final class. The coding assistant substantially reconstructed the final scene code using shared geometry and panel transitions. Raw premium drafts remain available for comparison. This distinction matters when using this lesson as a future distillation example: the reviewed code is the target, not the unfiltered model responses.

The reviewed preview was inspected at three positions in every beat:120 sampled frames. An overlap occurring during simultaneous equation crossfades was fixed by removing old writing before revealing the new writing. Final-resolution inspection and media verification are recorded in `output/final_checks.json` after export.

## Mathematical checks

`output/math_checks.json` verifies the symbolic area identity and all example answers. `output/render_geometry_checks.json` independently checks the vertices used by the actual renderer: equal central-square sides, perpendicular adjacent edges, congruent triangle areas, complete outer-area partition, and correctly proportioned outward squares whose areas add. Finite angle-sweep animations preserve leg lengths. The coordinate axes use the same scale in both directions.

## Timing and visibility

Narration timing comes from synthesized sentence lengths, not estimated reading speed. Actions inside a sentence are positioned using word-count interpolation, so synchronization is sentence-based rather than phoneme-perfect. Each chapter checks that its animations finish within the measured narration beat. End-state bounds checks protect the main frame and caption region; sampled visual inspection complements these checks. This is not an exhaustive proof that no collision occurs in any video frame.

The three independent-question beats include eight seconds each after speech ends. Answers appear in the next beat. Captions are optional tracks, not burned into the picture. A local HTML player supplies the WebVTT track; the MP4 also contains a subtitle track.

## Remaining evaluation

A mathematics teacher should assess whether the explanation, pace and vocabulary suit the intended students. A learner study and a continuous human listening review have not been performed. Neural narration is a stock Kokoro voice; no teacher voice was cloned. The script, sources and code are reviewable, and the reference can be revised before comparing cheaper models or training a smaller model.

Actual API costs, including failed calls, are in [costs.md](costs.md). This does not price local compute or the coding assistant's review work.
