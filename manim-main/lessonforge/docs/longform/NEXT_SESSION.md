# Continuation brief for the next environment

Read `HANDOFF_REPORT.md` first. The user wants a coherent, teacher-like, approximately twenty minute educational video with dynamic mathematics and purposeful highlights. Quality comes before scaling. They rejected the current narration and prefer Google TTS, potentially Gemini 2.5 TTS; Neural2 is a different possible interpretation.

## Current state

- A complete Pythagoras video exists at `long_form_pythagoras/output/pythagoras_20min.mp4`, 1080p30, 1200.003 seconds.
- Its narration is local Kokoro-82M ONNX, `af_heart`, synthesized as 274 individual sentences, then retimed. This likely contributes to disconnected delivery. There has been no new Google synthesis.
- The corrected renderer is `lesson_runtime.py`, `chapters_first_four.py`, and `chapters_rest.py` in that folder. Other generated chapter files are drafts, not the final implementation.
- Technical checks pass, but the user's narration feedback means this is not an accepted reference lesson. Do not describe it as ready to launch.
- Premium drafts required extensive repairs. Preserve original drafts, corrections and provenance. Do not train on raw responses as if they were approved examples.
- Total OpenRouter spend is $1.78386289 against the user's $5 cap; remaining $3.21613711. No keys are included. Any new spend must be recorded and remain within the applicable authorization.
- Six Blackwell GPUs are reported available, but hardware details and access are unverified. No training has occurred.

## Next action

Audit a connected two to three minute explanation from the narrative. Improve its argumentative flow and spoken mathematical language. Test Google speech in semantic blocks, with consistent voice direction, initially English and Hindi. Verify the intended Google product and usable authentication. Compare listening quality before rebuilding the full lesson. Do not generate sentences independently or force speech to exactly twenty minutes.

Implement audio alignment and stable semantic anchors, then a separate highlight scheduler referring to scene object IDs. Preserve exact mathematical geometry and expand checks from beat-end bounds to motion overlaps, subtitle clearance and highlight occlusion. Let each language have its own timing.

Read task IDs T01–T14 in the report. Complete a reviewed full lesson before expanding the dataset or distilling a model. Do not claim model quality rankings from the small existing pilot.

## Files to read

1. `HANDOFF_REPORT.md`
2. `long_form_pythagoras/REVIEW.md`, `audio_report.json`, `output/final_checks.json`
3. `long_form_pythagoras/narrative.md`, `storyboard.md`, `lesson.json`
4. `long_form_pythagoras/build_audio.py`, `lesson_runtime.py`, `assemble.py`
5. `research/04_long_form_method_comparison.md`, `research/05_paper_and_code_audit.md`
6. `06_scaling_dataset_and_distillation.md`, `07_frameworks_and_implementation_handoff.md`

The full meeting archive includes environments, weights, repositories and caches. Recreate environments on the destination instead of assuming copied environments are portable; reuse weights and repositories where compatible. Use `research/repository_manifest.json` to restore exact inspected commits. Do not run paid generation scripts merely to preview the existing video.
