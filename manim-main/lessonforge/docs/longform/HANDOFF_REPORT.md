# Educational video project handoff and future work

Updated 7 October 2026. This handoff covers the completed research, experiments, twenty minute Pythagoras lesson, known defects, and the next production architecture. It is intended for the project team and the next coding assistant after moving to another environment.

**Current decision:** retain the lesson as a reproducible technical prototype. The user has reviewed it and reported that the narration is poor and lacks coherence. It is not an accepted quality benchmark or a release candidate. Improve the teaching performance and synchronization before scaling or distilling models.

## Project objective and constraints

Create substantial, teacher-like lessons for Classes 8 and 9, initially mathematics and then science and biology. Speech should carry a sustained explanation; animation, highlighting, graphics, and simulations should make the reasoning easier to follow. The target is around twenty minutes when the concept warrants it. A duration target must not force unnatural speech or repetitive content.

The user wants quality first, then cost optimization, expert-teacher datasets, comparisons of in-context learning and retrieval, and eventual model distillation. Six Blackwell GPUs are reportedly available to the team; their exact models, memory, topology, and access have not been verified. No specialist model has been trained. The local video was rendered without a working GPU driver.

The original meeting requested scripts first, convincing conceptual explanations, two worked problems and three independent problems, and teacher/student review before launch. Earlier meeting advice about shorter videos is superseded for this prototype by the user's subsequent long-form requirement. The meeting's review date was “the 9th”; its month and year were not established from the transcript.

## Completed work and where to find it

All paths below are relative to this report's folder, `meeting/education_content_review`.

| Deliverable | Current state | Entry point |
| --- | --- | --- |
| Meeting minutes and workstreams | Written from the supplied transcript | [Minutes](01_meeting_minutes.md), [action register](05_action_register.md), `workstreams/` |
| Detailed methods comparison | Forty approaches across eight problems | [Methods](research/04_long_form_method_comparison.md) |
| Paper and code assessment | Four repositories cloned and inspected at pinned commits; full systems not reproduced | [Audit](research/05_paper_and_code_audit.md), [commit manifest](research/repository_manifest.json) |
| Initial narrated prototype | Approximately 79 seconds, like terms; different speech engine from the full lesson | [Prototype](prototype/README.md) |
| Small model comparison | Limited script/code/render/repair experiments; insufficient for a model ranking | [Pilot results](experiments/openrouter_pilot/RESULTS.md) |
| Ten explanations of Pythagoras | Three primary-site transcripts and seven written explanations; not ten watched videos | [Teacher comparison](long_form_pythagoras/research/teacher_comparison.md) |
| Complete lesson | Rendered 1080p English MP4, captions, chapters, worked examples and questions | [Video](long_form_pythagoras/output/pythagoras_20min.mp4), [player](long_form_pythagoras/review.html) |
| Script and visual plan | Original narrative, revised mathematical reasoning, timed storyboard | [Narrative](long_form_pythagoras/narrative.md), [storyboard](long_form_pythagoras/storyboard.md) |
| Editable implementation | Shared Manim renderer and ten chapters; substantial assistant repairs to premium drafts | [Runtime](long_form_pythagoras/lesson_runtime.py), [chapters 1 to 4](long_form_pythagoras/chapters_first_four.py), [chapters 5 to 10](long_form_pythagoras/chapters_rest.py) |
| Scaling and training proposals | Written designs; infrastructure and training not implemented | [Scaling](06_scaling_dataset_and_distillation.md), [framework handoff](07_frameworks_and_implementation_handoff.md) |

The lesson explains Pythagoras as an area relationship that yields a length. It contains ten chapters, forty beats, 2,906 spoken words, two worked examples and three independent questions. The encoded file is 1,200.003 seconds, with 36,000 frames at 30 fps and 1920 by 1080 resolution. It contains 274 caption segments and 173 animation anchors. These are production measurements, not evidence that the explanation succeeds with learners.

## Models and actual costs

**The twenty minute lesson uses Kokoro-82M through `kokoro-onnx` 0.6.1, with the stock `af_heart` voice, English US pronunciation, and synthesis speed 0.85.** It runs locally and has no per-request API charge. CPU/GPU time, storage and maintenance still have costs. The ONNX wrapper is MIT licensed; the model is Apache 2.0. See the [official project](https://github.com/thewh1teagle/kokoro-onnx) and the local [audio report](long_form_pythagoras/audio_report.json). The earlier short prototype used FFmpeg Flite `slt`; do not confuse the two.

Premium narrative and animation drafts were generated through OpenRouter. The successful substantial drafts used `anthropic/claude-sonnet-4.6`. A call to `anthropic/claude-opus-5.5` exhausted its output allowance on reasoning and returned no visible narrative. That failed call is included in costs. Final source code was substantially reconstructed and corrected by the coding assistant; it is not untouched premium-model output.

| Recorded expenditure | USD |
| --- | ---: |
| Earlier comparison pilot | 0.48565189 |
| Full lesson generation, including failed/truncated calls | 1.29821100 |
| Total recorded OpenRouter spend | 1.78386289 |
| User authorized cap | 5.00000000 |
| Remaining under that cap | 3.21613711 |

The ledgers are [pilot usage](experiments/openrouter_pilot/usage.json) and [lesson usage](long_form_pythagoras/usage.json). These totals exclude local compute, assistant work and human review. They are not the total cost of producing an accepted lesson.

**No Google audio has been generated in this handoff update.** The user authorized testing Google speech, but the latest request shifted the immediate deliverable to a migration report. Google access, endpoint choice, and actual pricing for the selected route still need verification before a paid test. No credentials are included in the handoff. Provision them in the destination's secret store or environment; never put them in source, reports, or training data.

## What passed and what remains unacceptable

The [technical check record](long_form_pythagoras/output/final_checks.json) reports successful full-file decoding, mathematical checks, actual polygon-geometry checks, chapter timing, and forty beat-end bounds checks with zero recorded violations. Review covered 120 preview frames and 120 final-resolution frames, plus an angle-motion repair sample.

These checks do not establish continuous audio quality, all-frame collision freedom, teacher approval, or learning improvement. In particular, the user's negative narration assessment supersedes any implication that a complete render was sufficient acceptance.

| Problem | Evidence or likely cause | Required response |
| --- | --- | --- |
| Disconnected delivery | Each of 274 sentences was synthesized independently; the model received no preceding sentence context | Generate complete teaching blocks and review joins |
| Artificial pacing | Speech was globally retimed with FFmpeg `atempo` 0.95515665, then padded to exactly twenty minutes | Let approved speech determine timing; revise prose for duration |
| Weak teacher performance | No explicit evaluated voice direction, pronunciation guide, or continuous listening gate | Add a performance script and blind listening review |
| Approximate synchronization | Within-sentence cue times are estimated by word position | Align actual speech and resolve semantic cue anchors |
| Ad hoc highlighting | Highlights are embedded in individual scene code | Make attention events an independent semantic layer |
| Residual overlap risk | Bounds are checked at beat ends; sampled frames miss intermediate collisions | Inspect layout and motion intervals, including captions and highlights |
| Long-form continuity | Scenes share helpers, but no formal state contract governs every chapter boundary | Carry forward object identity, terminology and unresolved questions |
| Raw code reliability | Premium drafts had invalid squares, wrong coordinates, overlaps, missing cues and truncation | Keep deterministic geometry and scoped repair; do not train on unreviewed drafts |

Sentence fragmentation and retiming are plausible contributors, not isolated experimentally proven causes. Script coherence, pronunciation and voice suitability must be evaluated separately from synthesis artifacts.

## Proposed full system

The following design is future work. The existing renderer implements only portions of it.

```text
Teacher evidence and curriculum
  -> concept graph and misconception map
  -> lesson argument and original teaching script
  -> semantic beats, persistent objects and attention events
  -> localized speech blocks and pronunciation rules
  -> speech synthesis -> transcript verification -> alignment
  -> locale-specific event timeline
  -> geometry, text, highlight and caption composition
  -> automated checks and teacher listening/viewing review
  -> accepted lesson and curated training records
```

Use a shared intermediate representation so models propose instructional intent while tested code implements geometry, layout and rendering. Rendering chunks can be short for reliability without turning the explanation into unrelated mini-lessons. Each chunk receives the lesson plan, its entry state, its teaching goal and its required exit state.

### Teaching and narrative layer

Maintain a lesson-level argument: motivating question, needed ideas, proof or explanation, application, misconception check and transfer. Each block must identify what the learner already knows, what changes in this block, and why the next block follows. Store reminders already delivered so different chapter generators do not repeat introductions.

Compare four script approaches on the same concept: a strong model with a curated few-shot teaching example; retrieval of reviewed concept-specific evidence; a planner followed by a writer and mathematical reviewer; and later a fine-tuned script model. Start with the first three. Retrieval supplies evidence and strategies; it does not automatically create a coherent lesson. Fine-tuning should wait for multiple accepted lessons and meaningful evaluation data.

Keep source-derived teaching observations separate from reusable licensed text. Public availability alone does not establish permission to train on complete teacher transcripts or reproduce their voice.

### Visual and geometry layer

Give every mathematical object a stable ID, meaning, coordinate system, lifecycle and invariants. For example, `triangle.main`, `side.hypotenuse`, and `square.hypotenuse` remain identifiable across explanation, proof and application. A highlight refers to one of these objects instead of guessed pixel coordinates.

Four implementation approaches are useful: reusable Manim components for exact mathematical animations; a scene-description language compiled to Manim; constrained generated Python for genuinely new visual behavior; and an interactive companion using the same mathematical parameters. Begin with reusable components and a small scene contract. Allow custom code only when those cannot express the required explanation.

For Pythagoras, preserve a triangle while constructing outward squares, rearranging congruent pieces, connecting area to side length, and varying the angle to demonstrate the right-angle condition. Each transformation should reveal a relationship the speech is explaining. More movement alone is not an improvement.

Validate the model of the scene before rendering: equal scales on axes, correct units, side lengths and areas, angle constraints, and consistent variable colors. Generate geometry from parameters; never rely on a raster image generator to make a diagram mathematically exact.

### Text and layout layer

Reserve separate regions for title, main diagram, explanation/equations and captions. Measure text after shaping and font selection, including Hindi and other local scripts. A bounding box from an English layout cannot be reused for every translation.

Support responsive templates, constraint-based positioning, semantic equation groups, and controlled overflow fallback. The fallback order is reflow, relocate secondary content, split a reveal, then editorially shorten text. Shrinking all text until it fits can make a technically valid but unreadable lesson.

Overlap checking must distinguish intentional containment, such as a side label near a triangle, from obscuring content. Track bounding boxes, object families, z-order and allowed-overlap relations. Check animation start/end, transition midpoints and intervals where paths intersect. Dense motion may need frame-level checks. Caption regions participate in the same layout checks.

### Highlight and attention layer

Create explicit events with `target_id`, `purpose`, `spoken_anchor`, `effect`, `onset`, `offset`, `priority` and `accessibility_style`. Purposes include identify, compare, follow a transformation, emphasize a condition and reveal an error. Effects include outline, underline, dim surroundings, pointer, temporary color or a moving trace.

Compare four attention strategies: static emphasis when the teacher names an object; progressive tracing while deriving a relation; synchronized comparison of two regions; and misconception-focused emphasis on the exact failing condition. Choose the effect from the instructional purpose. Do not add pulses to every noun.

A scheduler should prevent simultaneous unrelated focal points, stale pointers after objects move, highlights behind opaque objects, and emphasis that hides a number. Do not use color as the only signal. At a chapter boundary, clear completed attention events while retaining relevant mathematical objects.

### Speech performance and multilingual audio

Treat narration as a performance of a coherent argument. Store spoken text separately from delivery instructions, pronunciation forms, mathematical notation and visual directions. A direction such as “pause while the square fills” must not accidentally become spoken text.

The working interpretation of “Google TTS 2” is **Gemini 2.5 TTS**. Google also sells a separate **Neural2** product; confirm that distinction before final model selection. Gemini 2.5 Flash and Pro offer prompt-controlled speech. English India, Hindi, Tamil and Telugu are among documented supported languages. The model limits are 8,192 input and 16,384 output tokens. Use the endpoint's own supported features rather than assuming SSML or word timepoints work identically across products. [Google model documentation](https://docs.cloud.google.com/text-to-speech/docs/gemini-tts)

Run a small controlled comparison before regenerating the whole lesson:

1. Same script and voice family with complete 45 to 90 second teaching blocks.
2. Longer 90 to 180 second blocks to test whether additional context improves delivery or introduces drift.
3. Gemini Flash versus Pro with identical content and directions.
4. English and independently adapted Hindi versions, reviewed by fluent listeners.
5. The current Kokoro output as a baseline, with identities hidden during rating where practical.

These block sizes are experimental choices, not provider limits. Do not request the entire twenty minutes in one response. Natural transitions should determine block boundaries. Use a consistent voice and delivery profile; include enough context for the provider to understand the argument without asking it to speak the context again. Preserve silence where the learner needs to think.

After synthesis, check for omitted or duplicated words, incorrect numbers, lost negations, wrong mathematical pronunciation and audible discontinuities. Re-synthesize a complete affected block when necessary. Do not splice phonemes casually or crossfade voiced syllables across a join. Match level and room tone conservatively; avoid heavy processing that changes speech character.

Each language gets its own text, audio, alignment, captions and timing. Share the concept graph and scene meanings. Do not stretch Hindi speech onto the English timeline. Decide deliberately whether terminology is Hindi, English or a consistent bilingual convention, with a pronunciation lexicon for symbols and units.

### Alignment and timeline layer

Generate speech before final animation timing. Use forced alignment against the intended transcript where language support is adequate; use ASR to detect text differences, not as proof of mathematical correctness. Resolve semantic anchors to aligned spans. Numbers, formulas, punctuation and code-switching need normalization rules and review.

Compare provider timestamps if available, language-compatible forced alignment, ASR followed by transcript matching, and manual anchor correction for difficult passages. All must retain confidence and unresolved-anchor records. Keep sentence timing as a fallback requiring review, not silently as word accuracy.

Store speech time and pedagogical pause time separately. An animation may start slightly before the named object to orient attention, but such offsets must be explicit and reviewed. Never allow a fallback to fire every unresolved highlight at the start of a scene.

### Rendering and automatic repair

Use cached chapter renders with entry/exit state contracts and deterministic geometry. Start with one tested Manim renderer; a multi-renderer abstraction can follow actual need. Keep independent Manim jobs in separate media directories because shared temporary LaTeX/SVG files caused races in this work.

Repair in stages: schema and missing-object errors; compile/runtime errors; geometry violations; layout and collision defects; timing and narration mismatch; then explanatory quality. Attach a bounded failing scene, object IDs, relevant screenshots and the specific failed invariant to a repair request. Recheck neighboring transitions after a repair.

Compare deterministic layout repair, template substitution, a constrained code patch and a broader scene regeneration. Prefer the narrowest change that can resolve the actual failure. Set retry and spend limits; preserve failed attempts for analysis. A successful process exit or plausible screenshot is not acceptance.

## Google audio cost planning

Google Cloud lists Gemini 2.5 Flash TTS at $0.50 per million input text tokens and $10 per million output audio tokens. Pro is $1 and $20 respectively. Audio is billed at 25 tokens per second; these Cloud SKUs list no free usage allowance. Neural2 separately lists one million free characters and $16 per million beyond that allowance. These are direct Cloud prices checked on 7 October 2026, not a quote for OpenRouter or another Google API route. [Official pricing](https://cloud.google.com/text-to-speech/pricing)

For twenty minutes of generated speech, 1,200 × 25 = 30,000 audio tokens. Assuming 5,000 total input tokens including repeated directions:

| Scenario | Flash estimate | Pro estimate |
| --- | ---: | ---: |
| One language, one synthesis pass | $0.3025 | $0.6050 |
| One language, two complete candidate passes | $0.6050 | $1.2100 |
| Three languages, one pass each at the same duration | $0.9075 | $1.8150 |

Actual durations, tokenization, retries and route prices change these estimates. Externally inserted thinking silence is not synthesized speech. Alignment, rendering, storage, taxes and review are excluded. Record billed usage for every real request. Do not equate a low audio API price with a low cost per accepted lesson.

## Prioritized implementation tasks

Roles below are suggested assignments, not confirmed commitments. Dependencies define order; these are work packages, not promised dates.

| ID | Priority and owner role | Deliverable | Dependency and acceptance |
| --- | --- | --- | --- |
| T01 | P0, teaching lead | Review the existing script and mark broken transitions, repetition and unclear references | First; each block has one clear explanatory purpose and a connection to its neighbors |
| T02 | P0, audio engineer | Google speech adapter with secret handling, explicit model/voice/locale, cost ledger and bounded retries | Verify account/route first; save actual model and usage with every clip |
| T03 | P0, teaching lead and audio engineer | English/Hindi comparison clips, including one worked explanation and one transition | T01–T02; fluent listeners rate coherence, pronunciation and pacing; zero critical math-speech errors |
| T04 | P0, platform engineer | Versioned lesson/scene/audio/highlight contracts and stable IDs | T01; reject dangling IDs, missing entry states and unsupported locales |
| T05 | P0, audio engineer | Alignment and anchor resolver | T03–T04; all critical equation/highlight anchors resolved or manually reviewed; assess a proposed 200 ms timing tolerance |
| T06 | P0, animation engineer | Persistent geometry and typed scene components | T04; existing geometric checks pass and object identities survive transitions |
| T07 | P0, animation engineer | Independent attention scheduler | T05–T06; each highlight has a teaching purpose, a valid target and a checked interval |
| T08 | P0, rendering engineer | Layout and motion collision checks | T06–T07; captions remain clear, text meets agreed readability size, no unexplained occlusion in reviewed motion intervals |
| T09 | P1, editor and teaching lead | Revised full English lesson | T03–T08; continuous listening/viewing review, no repeated sentence joins, no unresolved critical defects |
| T10 | P1, localization lead | Full Hindi adaptation and locale-specific timeline | T09 architecture; native-language review, same mathematics and learning objectives |
| T11 | P1, evaluation lead | Teacher rubric and small learner pilot | T09; record comprehension, misconceptions and transfer, alongside preference ratings |
| T12 | P1, platform engineer | Queue, content hashes, retry budgets, cost accounting and resumable builds | Stable contracts; rerun only affected artifacts after a local edit |
| T13 | P2, data lead | Rights-aware accepted/failure dataset | T09–T11; provenance, review status and held-out split for every record |
| T14 | P2, ML engineer | Retrieval and distillation benchmark | T13; compare against unchanged premium baseline on unseen concepts and teachers |

For T03, review the same excerpt under controlled settings before choosing a voice. Then test at least one continuous chapter, because isolated attractive sentences can conceal long-form problems. A full lesson is accepted only after someone listens through it and inspects critical visuals in context.

## Scaling and dataset strategy

Scale the production pipeline before training a large replacement model. Cache by semantic scene, script, locale, model/voice, pronunciation profile and renderer version. A narration edit invalidates alignment and dependent animation timing; a palette edit usually does not require new speech. Store those dependencies explicitly.

Use the six GPUs only after measuring the actual bottleneck. CPU rendering, layout review, external TTS latency and teacher evaluation may dominate. Inventory GPU type/VRAM/interconnect, compatible drivers and training framework support before selecting a model size or promising throughput.

Dataset records should connect source provenance, concept, prerequisite, misconception, original teaching block, visual intent, stable object IDs, localized speech, verified alignment, accepted code, defects, repairs and reviewer judgments. Use separate datasets for script writing, scene planning, code repair and localization. Do not collapse the entire task into a transcript-to-Python pair.

Distillation sequence: establish accepted reference lessons; compare prompt-only and retrieval baselines; collect reviewed examples and failure/correction pairs; train the smallest useful component; evaluate on held-out concepts and source teachers; deploy only if it meets the same quality gate with lower total cost. Split by lesson/concept/source rather than random neighboring blocks to reduce leakage. One Pythagoras lesson is insufficient evidence for reliable distillation.

Measure critical defects per accepted minute, repair attempts, teacher review time, audio acceptance rate, learner outcomes and cost per accepted lesson. Token cost and rendering throughput alone are inadequate targets.

## Reusing the research repositories

The [pinned repository manifest](research/repository_manifest.json) records the exact inspected versions. Use the local audit before selecting code to adopt.

- **Code2Video:** useful planning/render/feedback ideas; inspected layout helpers do not guarantee non-overlap, and the reviewed path did not establish a complete narrated long-form pipeline.
- **Manimator:** useful animation-generation reference; its existence does not establish the quality of twenty minute teacher-like lessons.
- **TheoremExplainAgent:** relevant planner/generator/renderer separation and Kokoro voiceover integration. It does not remove the need for coherent speech and alignment review.
- **EduVisAgent:** useful visualization planning ideas; inspected material did not constitute this complete narrated production system.

Combine clear interfaces and tested components rather than copying four autonomous repair loops into one system. Keep one canonical lesson representation, one cost ledger and one acceptance policy. The repositories were inspected, not independently benchmarked end to end.

## Moving to another environment

Use the complete `meeting_full_backup_2026-10-07.tar.gz` archive and [continuation brief](NEXT_SESSION.md). At the user's request, the archive contains the entire meeting folder: reports, scripts, prompts, model responses, ledgers, checks, final reference videos, virtual environments, downloaded model weights, cloned repositories, raw audio and intermediate render caches. The final MP4 preserves the existing narration for comparison. Environments are included as a snapshot, but should be recreated on the destination machine because their paths and system libraries may differ. Extract with `tar -xzf meeting_full_backup_2026-10-07.tar.gz` from the desired destination directory.

The existing [build instructions](long_form_pythagoras/README.md) describe the local setup. Recreate environments instead of copying virtual environments across machines. Pin Manim Community 0.19.0 for the old lesson; use its existing [TTS lockfile](long_form_pythagoras/tts_requirements.lock.txt) to reproduce the old voice. Install FFmpeg/ffprobe, LaTeX/dvisvgm, Cairo/Pango, and the fonts used by the renderer. Separate media directories remain necessary for concurrent jobs.

Some historical JSON fields and logs contain absolute paths from this machine. Treat those as provenance. Rebuild `timeline.json`, concat lists and media metadata with the local scripts where necessary. Audit paths before invoking old helpers. Existing generation scripts make paid calls; do not run them as part of a routine rebuild.

The first task in the next environment is T01–T03: revise a representative connected explanation and test coherent Google narration. Keep the existing twenty minute file intact as the baseline. Select the speech approach using listening evidence, then rebuild timing and highlights around it. Preserve the mathematical checks and corrected geometry throughout.

## Open decisions

- Whether “Google TTS 2” means Gemini 2.5 TTS or Neural2, and which authenticated provider route will be used.
- Preferred teacher voice and accent; English and Hindi are proposed first languages, additional priorities remain open.
- Acceptable duration range around twenty minutes and expected learner prerequisite level.
- Who will perform continuous listening, mathematics review and language review.
- Hardware details and rights to use expert-teacher materials in any training corpus.

No new Google speech, multilingual final video, automated alignment service, independent highlight scheduler, training run or learner study is claimed complete in this handoff.
