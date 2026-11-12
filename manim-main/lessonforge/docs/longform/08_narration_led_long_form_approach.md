# Narration-led teaching videos: revised scope and approach

Updated 6 October 2026 following the user's clarification. The target is a complete, teacher-like explanation, potentially 20 minutes, with synchronized graphics that add understanding. The 79-second prototype demonstrates a rendering path; it does not establish the intended teaching quality or product format. This document takes precedence over earlier proposals favoring short videos or treating approved scripts as the only starting point. Historical meeting minutes remain unchanged.

This is an implementation and research specification for the user's team and coding models. No new renderer, dataset, repair service, or trained model is claimed here.

## 1. Product and research questions

A lesson should have a clear explanatory argument, natural spoken delivery, deliberate pauses, worked reasoning, misconceptions, and practice. Duration follows that teaching need. A 20-minute lesson can contain many animation events while remaining one continuous explanation. Internal rendering chunks need not become visible chapter breaks.

Technology should reveal something: move from a real example to a mathematical model, vary a parameter, trace a process, highlight what remains invariant, or compare a misconception with a correct construction. Motion is useful when it explains. A held diagram during reasoning can be intentional; decorative continuous movement is not a quality criterion.

The research has three independently evaluated parts:

1. Learn how to explain from expert teaching evidence and generate a coherent spoken lesson.
2. Translate that explanation into sustained, synchronized visual teaching across a full lesson.
3. Detect and repair correctness, layout, timing, and continuity defects at an affordable cost.

## 2. Expert teaching corpus and script generation

Use teacher-contributed, licensed, or otherwise authorized source material, recording provenance and permitted uses. Preserve teaching episodes in context rather than only isolated transcript sentences. Teacher popularity is not a correctness label.

Each episode record should include source and timestamps; transcript and speech timing; board or diagram states; prerequisite knowledge; learner level; the question being explained; examples; misconception; explanation steps; pauses and emphasis; visual actions; subject review; and the preceding and following lesson context. Preserve whole-lesson sequencing as well as episode annotations. A transcript alone loses gestures, drawings, and timing.

Create two related retrieval collections: verified subject evidence, and examples of teaching moves. Retrieve a useful analogy or counterexample by its instructional purpose and learner prerequisite, as well as topic similarity. Keep each retrieved passage attached to its surrounding explanation. Context-enriched chunk retrieval is an established technique, but its benefit for this teaching corpus must be measured locally. [Anthropic contextual retrieval](https://www.anthropic.com/engineering/contextual-retrieval)

Compare the following on the same held-out lesson briefs:

| Experiment | Inputs | Question |
| --- | --- | --- |
| Strong-model baseline | Verified curriculum facts, learner brief, explicit teaching requirements | What can good prompting already achieve? |
| In-context examples | Same inputs plus a fixed, small set of reviewed teaching examples | Does demonstrating explanation structure help? |
| Retrieved examples | Same inputs plus relevant subject evidence and teaching episodes | Does topic-specific example selection improve the lesson? |
| Fine-tuned script model, with and without retrieval | Reviewed brief-to-script examples and optional retrieved evidence | Can learned teaching behavior improve quality or reduce accepted-output cost? |

RAG selects information; in-context learning uses supplied examples; fine-tuning changes weights. They can be combined. Do not assume one wins before evaluating them. Keep the underlying model and output budget fixed when testing retrieval effects; report model-size changes separately. Separate teacher/source families and near-duplicate lessons across splits, with an additional unseen-concept evaluation.

Have subject reviewers compare scripts without knowing their generation method. Score missing reasoning steps, conceptual accuracy, use of prerequisites, examples, misconceptions, spoken naturalness, and unnecessary repetition. Render only a subset initially so script experiments are not dominated by video costs. Script scores are intermediate measures; learner comprehension and transfer remain outcome measures.

The deliverable is a teaching script with coordinated tracks: exact spoken words, intended learner inference, visual action, and pause/emphasis cues. Read or listen to it as a whole before approving it. Where a diagram is essential, narration should explicitly refer to its meaning and changes.

## 3. Plan globally and render locally

Use the hierarchy `lesson -> explanatory section -> teaching beat -> visual event`. A beat might pose a prediction, reveal a construction, work a step, or address an error. It is not automatically a separate video or a fixed number of seconds.

The lesson plan holds objectives, concept dependencies, notation, running examples, visual conventions, and deliberate recaps. Each beat references what has already been established and what new inference it must add. A global review distinguishes intentional reinforcement from redundant reintroduction.

Rendering contracts hold:

- Required starting state: object IDs, geometry, labels, camera, axes scale, colors, and visible equations.
- Narration segment and word or phrase anchors.
- Visual events and their intended meaning.
- Objects created, changed, retained, and removed.
- Required final state and facts established by the explanation.

Generate these boundary states globally. A chunk renderer reconstructs its declared starting state without replaying earlier animations, executes its events, and validates its final state. Neighboring chunks must agree on the shared state. Keep boundaries at natural holds where possible; ongoing motion needs explicit trajectory and timing state or should remain inside one render unit. Independently generated chunks can otherwise produce abrupt camera changes, repeated introductions, or disappearing objects.

For a line lesson, retain the same axes and line while the teacher first varies the intercept and then the slope. Preserve colors and refer to the earlier observation. The code can be modular even though students experience a continuous demonstration.

Reusable components should support operations such as plotting, transforming, annotating, zooming, revealing derivation steps, and simulating a process. Avoid limiting the whole product to a few slide layouts. Allow reviewed custom code for representations the component library cannot yet express, then consider promoting useful implementations into the library.

Cache chunks with keys covering the script, audio, assets, code, renderer version, and starting state. A local layout repair should usually require a local render and boundary checks. Changes to shared notation, audio timing, or boundary state invalidate dependent chunks. Reassemble and check the complete lesson after local repairs.

## 4. Audio drives the timeline

Write narration and visual intentions together, approve the explanation, produce section-level audio with consistent voice settings and pronunciation, and derive animation timing from measured audio. Avoid synthesizing every sentence in isolation if that damages prosody. Review joins, volume, pauses, and pronunciation across the whole lesson.

Use spoken anchors such as “notice the intercept” to cue the corresponding highlight. Word alignment requires validation, especially for equations, Hindi-English switching, and technical terms. If an animation needs more reasoning time, revise the narration or pause rather than speeding through the explanation to fill a slot.

Manim Voiceover provides duration tracking and word bookmarks for synchronizing animations with speech. Those are useful implementation mechanisms, not evidence that synthetic delivery sounds like an expert teacher. [Manim Voiceover quickstart](https://voiceover.manim.community/en/stable/quickstart.html)

Keep captions separate from the teaching board. Use graphics, equations, and short labels on screen; evaluate whether large transcript blocks compete with the diagram. Provide an initial human-recorded reference section for comparison with synthetic narration.

## 5. Overlap prevention and repair

Successful execution only means the program ran. Layout errors can arise from long formula widths, stale objects, independently chosen coordinates, changed camera scale, transformed objects entering occupied space, or captions intruding into the teaching area. The existing prototype had a stale-object defect: removing a wrapper did not remove individually introduced children. It was found by visual inspection and corrected in source. Its current endpoint boundary assertions are not a complete overlap detector.

Build prevention into the layout system:

1. Measure text and equation geometry with the actual fonts and renderer before placement.
2. Declare safe regions, readable minimum text size, margins, and caption space. Express label placement relative to its associated object.
3. Track actual visible object identities, lifetimes, layering, and camera transforms.
4. Declare intentional intersections: labels inside shapes, curves crossing axes, braces beside expressions, and explicit occlusion. Avoid exempting arbitrary object pairs to silence failures.
5. When content cannot fit, reflow, stage its reveal, move a derivation to another board region, or revisit the beat. Repeatedly shrinking everything is not an acceptable default repair.

Check layouts over time in screen coordinates. Cheap bounding-box intersections can identify candidate conflicts, but nested objects and empty space inside bounds create false positives. Refine important candidates using visible geometry or object masks, ownership, and allowed-overlap rules. Check safe bounds, occlusion, readability, captions, and object lifecycle separately.

Inspect animation boundaries and intermediate frames; use denser sampling around transforms and camera movement. For release validation, instrument all output frames where practical, while applying expensive pixel/multimodal analysis selectively. Sparse screenshots cannot certify an entire video, and full-frame geometry checks still do not prove pedagogical clarity.

Use a repair loop with concrete evidence:

`render -> diagnostic -> bounded patch -> rerender affected interval -> regression and boundary checks`

Diagnostics should identify the lesson and beat, time interval, object IDs, violated rule, measured geometry, representative frames, narration, and relevant code. Fix a violated layout parameter or object lifecycle rule first. Ask a coding model for a scoped patch when a deterministic fix is insufficient. A vision model can help identify confusing composition, but its judgment is one signal and must not manufacture acceptance.

Cap attempts and escalate unresolved defects. Record initial code, observed failure, patch, and new results immutably. A patch passes only if it resolves the target issue without breaking mathematics, timing, readability, or adjacent state. Regressions should include moving labels, long formulas, stale objects, changing cameras, caption collisions, and legitimate diagram intersections.

Code2Video's planner/coder/critic design and scope-guided fixes are useful references. Its reported evaluation does not establish that this proposed system will produce coherent, teacher-quality 20-minute lessons. [Code2Video paper](https://arxiv.org/html/2510.01174v1)

## 6. Coding models and distillation

Compare a strong coding model, a smaller model with retrieved component examples, and a fine-tuned smaller model using the same approved script, visual plan, renderer, and evaluation. Include unfamiliar compositions as well as routine cases. Judge first-pass correctness, final acceptance, repair cycles, human review time, and total cost per accepted lesson.

Maintain distinct dataset tasks, even if adapters eventually share a base model:

- Teaching: learner brief plus evidence to coherent narration and visual intentions.
- Production: beat contract plus boundary states to executable visual events or code.
- Repair: failing program plus observed diagnostics to a verified patch.

Preserve whole-lesson plans in production examples; isolated scene pairs cannot teach cross-section continuity by themselves. Fine-tune on reviewed successful outputs and verified repairs. Include student-model failures corrected by a stronger model or expert. Synthetic volume is not a substitute for correctness and teaching review.

The six Blackwell GPUs support future experiments, subject to actual SKU, VRAM, and topology. Select distributed training and inference arrangements after profiling. Training a model to generate code does not eliminate rendering, visual verification, or subject review. The existing [framework handoff](07_frameworks_and_implementation_handoff.md) remains the infrastructure reference with the revised product scope above.

## 7. Bounded implementation assignments and acceptance

| Assignment | Reviewable deliverable | Acceptance evidence |
| --- | --- | --- |
| Expert corpus and script comparison | Episode schema, reviewed examples, fixed held-out briefs, prompt/retrieval baselines | Provenance, split audit, blind script ratings, actual cost records |
| Whole-lesson planner | One complete roughly 20-minute script and state-linked beat plan | No missing prerequisite or accidental repeated introduction; teacher approval pending until performed |
| Narration and timing | Natural audio, pronunciation guide, measured anchors and captions | Listening review and actual speech/visual synchronization |
| Renderer and layout | Dynamic components, state restoration, geometric checks | Purpose-built defect fixtures including motion and valid overlap |
| Repair workflow | Diagnostic records, bounded patches, before/after render evidence | Defect resolved, adjacent states preserved, no new semantic error |
| Model comparison and training | Baseline report, curated exports, later training configuration | Unseen-lesson quality and accepted-output cost, with no fabricated results |

First build one full lesson to expose continuity and pacing problems, plus a small suite of deliberately difficult rendering cases. Use inexpensive previews during iteration and render the final reviewed lesson at delivery quality. That lesson is an integration milestone, not proof of generalization. Broaden to unseen math and science lessons and learner evaluation before claiming scale or learning gains.
