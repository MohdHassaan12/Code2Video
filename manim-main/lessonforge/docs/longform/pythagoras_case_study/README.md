# The geometry of a shortcut

An original **20-minute, 1080p, English narrated lesson** explaining why the Pythagorean theorem works. It follows a single problem through visual area reasoning, a general proof, applications and practice.

**User review, 7 October 2026:** narration quality and coherence are unsatisfactory. This is a technical prototype pending audio redesign, not an accepted production lesson. See the [current handoff and future tasks](../HANDOFF_REPORT.md). Google TTS testing is pending.

## Watch and inspect

- [Full video — 20:00](output/pythagoras_20min.mp4)
- [Player with chapter navigation and captions](review.html)
- [Complete narrative](narrative.md)
- [Timed storyboard and visualization script](storyboard.md)
- [Ten educator explanations compared](research/teacher_comparison.md)
- [Production review and remaining evaluation](REVIEW.md)
- [Actual generation costs](costs.md)
- [Download editable source package](output/editable_lesson_source.zip)

The source comparison includes three primary-site video/classroom transcripts and seven written explanations. It does not claim that ten videos were watched. Teacher phrasing, footage and voices were not copied into the lesson.

## Code and provenance

[Chapters1–4](chapters_first_four.py), [chapters5–10](chapters_rest.py), and the [shared renderer](lesson_runtime.py) are the reviewed implementation. Premium Sonnet generated the narrative and code drafts. The coding assistant corrected the narrative and substantially reconstructed faulty scene code after inspecting renders. The original model outputs are preserved in `generated/`, with prompts in `prompts/` and repairs in [editorial_changes.json](editorial_changes.json).

Do not treat the raw drafts as approved training examples. The reviewed source, the corrected narrative, the original failures and the review evidence together make a useful first reference case. One lesson is not enough to establish a model ranking or train a reliable specialist.

## Rebuild locally

Run these commands from this folder. The renderer uses the already installed Manim Community0.19.0 environment in the neighboring prototype folder. FFmpeg and LaTeX are required. No paid API call is needed to rebuild the reviewed lesson.

```bash
.tts/bin/python build_audio.py
../prototype/.venv/bin/manim -qh --fps 30 --media_dir media chapters_first_four.py C01 C02 C03 C04
../prototype/.venv/bin/manim -qh --fps 30 --media_dir media_rest chapters_rest.py C05 C06 C07 C08 C09 C10
python3 assemble.py
python3 build_review.py
```

Separate media folders prevent simultaneous render processes from racing on Manim's temporary SVG files. The audio builder caches individual sentences; unchanged sentences do not need synthesis again. It measures their lengths, gently adjusts the overall pace and retains explicit thinking time.

For a fresh TTS environment, create a Python environment and install [tts_requirements.lock.txt](tts_requirements.lock.txt). Download the model and voice pack referenced by the [official Kokoro ONNX project](https://github.com/thewh1teagle/kokoro-onnx) into `models/` as `kokoro-v1.0.onnx` and `voices-v1.0.bin`. Kokoro model: Apache2.0; ONNX wrapper: MIT. The stock `af_heart` voice is used without cloning a teacher.

The local HTML player may need to be served through a local HTTP server for captions in browsers that restrict file URLs. The MP4 includes its own English subtitle track and chapter markers.

## Evidence

- [Mathematical checks](output/math_checks.json) and [checks of the actual rendered geometry](output/render_geometry_checks.json)
- [Measured audio report](audio_report.json), [timeline](timeline.json), and [chapter durations](output/chapter_duration_checks.json)
- [Final media checks](output/final_checks.json) and [full media probe](output/media_probe.json)
- Preview and final contact sheets in `output/`, with individual sampled frames in `output/frames/`
- [Build manifest](build_manifest.json) and [API usage ledger](usage.json)

This is a technically reviewed reference candidate. Teacher evaluation, learner testing and a continuous human listening review remain pending.
