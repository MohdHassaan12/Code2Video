# Detailed approaches to producing long form teaching videos

The production target is an approximately 20-minute teacher-like explanation with accurate, expressive, synchronized visuals. The system must preserve a line of reasoning across the lesson and support economical revision. Optimizing for the number of generated scenes or for code that merely runs will miss this target.

This comparison develops five approaches for each of eight problems. The approaches within a problem are alternatives or incremental extensions, not forty services that should all be deployed. The proposed starting combination is A2/A3 for teacher evidence, B2/B3 for scripts, C3 for continuity, D3/D4 for graphics, E2/E3 for narration, F2/F3/F4 for layout, G2/G3 for repair, and H1 before H2/H3 for scaling. The sections explain the tradeoffs and experiments behind that choice.

Use this alongside the [paper and code audit](05_paper_and_code_audit.md), [cost analysis](06_cost_analysis.md), and [live pilot results](../experiments/openrouter_pilot/RESULTS.md). These distinguish inspected implementations, reported research results, measured calls, and proposed experiments.

## A Acquiring useful evidence from expert teachers

### A1 Transcript corpus with topic and prerequisite labels

Transcribe complete lessons, correct equations and terminology, and label topic, learner level, prerequisites, example boundaries, and misconception discussions. Preserve source timestamps and lesson identity. This is the least expensive entry point and is suitable for searching what a teacher said or adapting an explanation into original wording.

Its weakness is that speech is often incomplete without the board: “this term” and “move this here” lose their meaning. Treat transcript-only examples as language evidence, not as faithful audiovisual supervision. Test the defect rate by having reviewers reconstruct explanations from transcripts and then compare with the video. Use that measured rate to decide which topics need richer annotation.

### A2 Multimodal teaching episodes with aligned board states

For each meaningful episode, retain transcript, audio interval, board snapshots, diagram changes, gestures where relevant, and the concept being established. Annotate correspondences: a spoken reference points to an object; a drawing illustrates an inference; a pause invites a prediction. Keep the preceding explanation attached so the episode does not become a fragment without context.

This supports audiovisual planning and is a better fit for the desired product. Annotation is more expensive, particularly when handwriting and formulas are unclear. Begin with a deliberately diverse reviewed subset rather than automatically labeling every frame. Evaluate reference resolution, equation transcription, and whether another teacher can reconstruct the instructional move. Store observed actions separately from an annotator's interpretation of why they work.

### A3 Teaching move library built from multiple teachers

Extract reusable instructional patterns: contrast two cases, vary one parameter, expose a common error, move from concrete quantities to symbols, or ask for a prediction before a reveal. Each pattern includes the conditions under which it applies, the prerequisite knowledge it assumes, a successful example, and a known limitation.

For example, area tiles clarify addition of like terms but need an explicit domain discussion when literal side lengths no longer represent the algebra. Retrieve the pattern by its instructional role and concept structure, not only vocabulary. This may transfer better to unseen topics than memorizing complete lessons, but overgeneralization is a risk. Evaluate on held-out concepts where the system must decide that a familiar analogy is inappropriate.

### A4 Expert correction and preference dataset

Give teachers two anonymous candidate explanations for the same brief, or one draft to edit. Record the chosen version, exact changed spans, defect category, and short observable rationale: a missing prerequisite, incorrect analogy, abrupt transition, or answer revealed too early. Preserve disagreements rather than turning every preference into an objective truth.

This creates high-value data for supervised revision and later preference optimization. It targets the difference between fluent prose and effective teaching more directly than raw transcripts. Costs depend on reviewer time and rubric reliability. Begin with a calibration set reviewed by two teachers; measure agreement before buying thousands of labels. Keep narration style preferences separate from conceptual correctness and learner outcomes.

### A5 Synthetic expansion constrained by reviewed exemplars

A stronger model can create variants of an accepted explanation: another prerequisite profile, a different misconception, a new problem structure, or a different visual representation. Require explicit invariants and independent subject checks. Preserve the original parent lesson and transformation type in every record.

This expands coverage cheaply once the seed data are good. Number substitution alone adds little instructional diversity, while unconstrained generation can amplify a teacher model's errors. Split source families before augmentation; otherwise near-duplicate variants inflate evaluation. Measure unique teaching moves and failure coverage, not record count. Only export reviewed or reliably verified targets to training, and retain rejected generations for diagnosis rather than silently discarding them.

### Selection and corpus contract

Start with A2 for the most valuable demonstrations and A3 for retrieval; use A1 to broaden discovery and A4 to learn what requires correction. Apply A5 after the review process works. Record provenance and permitted uses for source material. Teacher popularity is not a quality label. Keep whole lessons, episodes, teaching moves, and corrections linked rather than flattening everything into unrelated text chunks.

## B Generating a script that teaches for twenty minutes

### B1 Strong model with a whole lesson brief

Provide verified facts, learner prerequisites, objectives, required examples, misconceptions, and approximate duration. Ask for a complete lesson and review it as one artifact. This minimizes orchestration and establishes how much good instruction alone can achieve. It is the proper control condition for more complex methods.

Typical failures are superficial expansion, nominal timestamps unsupported by actual speech length, missing reasoning, and repetitive summaries. Validate spoken word count separately from stage directions. A 20-minute label is not timing evidence. Compare teacher ratings, factual defect counts, and measured audio duration. Keep output limits large enough for the requested narration so truncation is not mistaken for a model's inability to teach.

### B2 Fixed in context examples of good explanation

Supply a small, curated set of original or authorized examples showing different teaching moves. Include what makes each example useful, the learner assumptions, and situations where it should not be copied. Ask the model to select and adapt a teaching strategy before drafting the lesson.

This gives tighter control over style and reasoning structure without training. The same examples can bias every lesson toward the same analogy or pacing. Use examples from different concept families and include a counterexample where the tempting analogy fails. Compare B1 and B2 using the same model, facts, output budget, and evaluation briefs. Otherwise model size or extra output length could explain the apparent gain.

### B3 Retrieval of subject evidence and teaching episodes

Maintain separate retrieval indexes for factual evidence and instructional examples. Filter by prerequisite level and subject, retrieve with both lexical and semantic signals, rerank, and supply a compact set of episodes with surrounding context. Retrieve explanations of the specific misconception rather than every passage containing the topic name.

This adapts examples to a growing curriculum while avoiding huge prompts. Retrieval can select a semantically similar but pedagogically inappropriate example. Measure whether the needed explanation was retrieved before blaming generation. Compare retrieved examples with fixed examples under an equal context budget, and include an oracle condition where a teacher selects the evidence. The oracle shows the headroom available from improving retrieval. Contextual retrieval is a relevant implementation reference, not proof of teaching quality. [Reference](https://www.anthropic.com/engineering/contextual-retrieval)

### B4 Hierarchical manuscript with explicit dependency review

Draft a concept graph and complete lesson outline first. Allocate a purpose and approximate speech budget to each section. Expand sections using the same notation register, running example, established facts, and next-section obligations. Then run a whole-manuscript editing pass to repair missing bridges and unnecessary repetition.

This makes long-form generation manageable and supports local edits. Its risk is that each section becomes a polished but disconnected essay. Require each section to identify its new inference and its dependency on earlier material. A recap must have an explicit retrieval or consolidation purpose. Evaluate continuity at boundaries and whether every required reasoning step is actually explained. The final manuscript, not the outline, is the teacher-review artifact.

### B5 Fine tuned teaching and revision model

Train on learner briefs, approved evidence, lesson plans, accepted scripts, and expert corrections. Include tasks for expanding an explanation, fixing a misconception, and repairing a transition. A model trained only on transcripts learns to continue transcripts; it does not automatically learn brief-to-lesson authoring.

This can reduce repeated prompting and standardize teaching behavior, but requires enough diverse reviewed targets. Begin with supervised fine-tuning and compare against the untuned model plus the same retrieved evidence. Add preference optimization only when reliable preferences exist. Hold out teachers, source families, and concepts. Use retention and transfer questions with actual learners to validate teaching gains; model judges and script ratings remain intermediate signals.

### Selection and experiment

Start with B2 plus B4, then add B3 when the corpus is large enough to make selection useful. Treat B5 as an experiment with a quality and cost threshold. A first comparison might use 12 diverse lesson briefs and two generation seeds per condition, with a smaller blind teacher-rated subset; these are proposed pilot sizes, not statistical power claims. Predefine failures and count every generation, including rejected outputs.

## C Preserving continuity across long videos

### C1 One monolithic program and timeline

Generate a single program containing the entire lesson. All objects and variables exist in one execution context, so reusing a graph is straightforward. It is a useful reference implementation for one carefully authored lesson and can reveal what a seamless result should look like.

As duration grows, code becomes costly to inspect and repair. Regeneration may disturb already-correct sections, and a late exception can waste a long render. Keep this baseline for comparison but measure change amplification: how much code and video must be regenerated for a one-line narration or layout edit? A long context window increases capacity; it does not provide modular correctness or stable state management.

### C2 Independently generated clips under a shared outline

Give each renderer a section brief, common visual style, and asset library, then concatenate the resulting clips. This is easy to parallelize and failures are local. It suits genuine chapter boundaries, unrelated worked examples, or comparisons where a deliberate visual reset is acceptable.

Shared colors and assets do not preserve the student's mental context by themselves. The same axes can return at a different scale; a running example can disappear; each clip may repeat the definition. Use this as a speed baseline and quantify discontinuities and redundant reintroductions. Avoid treating it as the final long-form design simply because the clips concatenate successfully.

### C3 Explicit visual state at chunk boundaries

Define the starting and ending state of every rendering chunk: object IDs, geometry, parameters, labels, camera, layers, visible equations, and established conceptual facts. A renderer restores the starting state without replaying its introduction, performs its events, and verifies the ending state. Adjacent chunks must agree on their shared state.

This preserves a continuous graph or derivation while permitting parallel work after contracts are settled. Serialization is the hard part: custom updaters, random simulations, and ongoing motion may carry hidden state. Prefer boundaries at natural holds; otherwise serialize time and trajectory state too. Compare semantic state equality and boundary-frame geometry rather than relying on identical pixel hashes that may differ through antialiasing.

### C4 Event timeline compiled into a persistent scene

Represent the lesson as typed events such as create axes, set parameter, reveal equation step, highlight term, and retire object. Compile those events into one persistent scene, with optional render checkpoints. The same event specification can later drive a video or interactive player.

This reduces arbitrary code and makes object ownership and timing inspectable. The cost is building an expressive event language: an overly small vocabulary produces formulaic visuals. Include a reviewed custom-component mechanism and a way to declare its state and bounds. Test compositional generalization by combining known primitives in unfamiliar teaching sequences. Do not claim that valid event syntax implies mathematical or educational correctness.

### C5 Dependency graph with selective regeneration

Track dependencies between facts, scripts, audio, visual objects, assets, code, and rendered chunks. A changed pronunciation invalidates audio and timing; a changed equation invalidates its visual and downstream explanations; a color change may affect every later reference to that object. Schedule only the affected computations, then recheck joins and whole-lesson consistency.

This is the production extension to C3/C4, not a substitute for planning. Incomplete dependency tracking can reuse stale artifacts and conceal errors. Test with controlled edits and compare incremental outputs against a clean rebuild. Cache keys must include renderer version, fonts, assets, state, and randomness, not just prompt text. Report both compute saved and stale-cache defects.

### Selection and long horizon reliability

Use C3 first and evolve toward C4/C5 where repetition justifies engineering. Even if each of 40 chunks independently has a 98% chance of passing, the illustrative all-pass probability is 0.98^40, about 45%. Real failures are correlated, so this is not a forecast; it explains why section-level pass rates alone are insufficient. Evaluate complete lessons and cross-section errors explicitly.

## D Producing expressive and correct visual code

### D1 Direct generation with the strongest suitable coding model

Send an approved narration and visual plan to a strong model and request Manim code. This maximizes flexibility for unusual constructions and gives a reference for the quality ceiling of the current prompt. Use pinned engine versions and small executable examples of required APIs.

The model must simultaneously solve geometry, layout, object lifecycle, timing, and API usage. Fluent code can encode a false diagram. Measure first-pass render success and semantic correctness separately, and keep failed attempts. Use this route for novel components or difficult cases; its low engineering overhead may beat training economically when lesson volume is modest.

### D2 Code retrieval with adaptation

Retrieve tested components or examples indexed by behavior: clipped dynamic line, signed rise/run triangle, equation transformation, particle simulation, or process diagram. Give the model the component contract, supported parameters, known limits, and engine version. Ask it to adapt only what the lesson needs.

This reduces invented API calls and duplicated implementation. Retrieved snippets may have hidden assumptions or introduce incompatible coordinate systems. Store executable fixtures alongside examples and test the adapted behavior, not just syntax. Prefer small reusable functions to whole unrelated videos. Compare retrieval with an equal-length generic Manim reference so improvements can be attributed to example relevance.

### D3 Typed scene specification and deterministic compiler

Let the model select components and specify semantic parameters, layout relationships, and timed events. The compiler constructs geometry and enforces structural rules. For y=mx+b, the equation, plotted line, intercept marker, and slope triangle should derive from the same parameter values rather than separate generated strings.

This removes many opportunities for disagreement and makes regression tests reusable. It does not remove the need to choose the right representation. A compiler that supports only a few slide types limits teaching. Begin with a small but composable algebra/graphing vocabulary and add reviewed custom components for new needs. Evaluate correctness and expressiveness on held-out combinations.

### D4 Route each representation to an appropriate renderer

Use deterministic vectors for equations and graphs, numerical simulation for changing systems, diagrams or reviewed image assets for biological structures, and footage where observing a real experiment matters. A common timeline and coordinate/layout interface should govern composition. The teaching plan explains why each modality adds information.

This broadens explanation beyond text and simple shapes. Mixing engines adds synchronization, color, resolution, and asset-management costs. Do not use a generated photorealistic image as authoritative evidence for fine anatomy or physical law. A representation contract should specify what must be exact and what is illustrative. Start with two renderers only when a lesson demonstrates the need; avoid a large framework before that evidence exists.

### D5 Distilled code model with escalation

Train a smaller model on verified specification-to-code pairs and observed repairs. Route routine supported cases to it and escalate unfamiliar components or failed checks to the stronger model. Keep the same renderer and validators for both so an apparent speed gain does not come from weaker checking.

This can lower repeated authoring cost, but API code generation may already be a small part of the total. A cheap model that adds review work can cost more per accepted lesson. Learn escalation thresholds from held-out failure data, not self-reported confidence alone. Compare total attempts, human minutes, and accepted-output cost against D1/D2 before deploying it broadly.

## E Natural narration and audiovisual synchronization

### E1 Human narration reference

Have a good teacher record the approved explanation, including natural pauses and emphasis. Align animations to that recording. This provides an explicit quality target and reveals where a written script does not sound natural when spoken. A small reference set is valuable even if most production later uses TTS.

Human recording is harder to revise and scale across languages. Keep section boundaries at complete thoughts and retain pronunciation notes. Evaluate the reference and synthetic versions using the same visuals so reviewers judge voice and delivery rather than different lessons. Treat teacher recording time and editing time as real costs in the comparison.

### E2 Section level TTS with consistent prosody

Synthesize complete thought groups rather than every sentence separately. Use consistent voice settings, a pronunciation dictionary, and explicit pause/emphasis markup where supported. Review transitions between generated sections for changed speed, tone, or volume.

This balances natural phrasing with local regeneration. Longer audio units can make small edits more expensive; very short units can sound disjointed. Compare several section lengths using listening tests and actual regeneration cost. Do not assume voice cloning improves explanation: vocal identity and instructional delivery are different variables. Use voice references only with the appropriate permission.

### E3 Measured speech anchors and forced alignment

After generating audio, align words or phrases and attach visual events to anchors. “The intercept stays here” should coincide with the relevant marker, while a result appears after the intended question pause. The schedule may include minimum visual durations independent of speech.

Equation pronunciation and Hindi-English switching can make automatic alignment unreliable. Validate a sampled set of anchors and high-risk terms; prefer stable phrase boundaries when word timestamps are noisy. Keep the visible math notation and spoken form linked but separate. Manim Voiceover supplies duration tracking and word bookmarks as implementation building blocks. [Documentation](https://voiceover.manim.community/en/stable/quickstart.html)

### E4 Joint constrained scheduling of speech and animation

Represent temporal rules explicitly: a label must exist before it is referenced; a transformation must finish before its consequence is discussed; a prediction pause precedes the answer. Find a schedule satisfying those constraints within a section's available duration. If constraints are infeasible, request a script or animation revision.

This is stronger than stretching every animation to match TTS. It adds solver and authoring complexity, but can catch pedagogically harmful ordering. Start with simple precedence constraints and minimum durations; add optimization for idle time later. Validate whether repaired timing actually improves comprehension. A numerically valid schedule can still speak too quickly for a new concept.

### E5 Audio and interaction variants over one semantic lesson

Maintain language-specific narration, captions, and alignment over a common concept and visual specification. Let a player offer pause-and-predict moments, optional prerequisite explanations, or a manipulable version of the same simulation. Render a linear version for ordinary playback.

This scales reuse and adds technology that supports learner action. Translation changes speech length and text width, so recheck timing and layout for every language. Alternate paths also need prerequisite and state contracts; a learner returning from a remedial branch must rejoin correctly. Evaluate the interactive layer separately so it does not mask a weak base explanation.

## F Detecting and preventing overlap and formatting defects

### F1 Prompt rules and fixed screen regions

Reserve title, diagram, equation, and caption regions. Specify minimum font sizes, margins, and a small set of placements. Provide examples of good and bad layouts. This is inexpensive and useful as a baseline; the Manimator code audit shows an instance of prompt-level overlap instructions.

Prompt compliance does not measure actual glyph bounds or motion. A long expression can overflow its region despite a plausible coordinate. Use this layer to constrain initial output but never treat it as a checker. Measure false acceptance on a defect suite containing long formulas, stale objects, camera shifts, and moving labels.

### F2 Constraint based layout using measured geometry

Render or measure text and formulas before layout. Model relations such as left-of, attached-to, inside-region, aligned-baseline, and minimum-gap. Solve positions subject to bounds and minimum readable size. Reflow or split a reveal if constraints cannot be satisfied.

Constraints can overconstrain a dense diagram and may need discrete choices such as placing a label above or below a curve. Use a small candidate search rather than assuming every problem is a continuous optimization. Declare intentional overlaps and nesting explicitly. Validate output at target resolution because units in a scene do not directly guarantee legibility on a student's device.

### F3 Temporal geometry and object lifecycle checks

Track all visible objects, their screen-space bounds, opacity, layer, owner, creation, and removal through time. Check candidate intersections at every relevant frame or event interval. Apply exemptions only to declared semantic relationships, such as a label inside its node.

Axis-aligned boxes are fast but can flag empty space around rotated or curved shapes. Use them as a broad phase, followed by tighter geometry or masks for important candidates. Camera transforms and transient animations must be included. A scene endpoint may be clean while an equation sweeps over another label halfway through. Measure detection precision and recall against manually labeled intervals.

### F4 Raster inspection and multimodal critique

Inspect rendered images using text recognition, visible masks, contrast/readability measures, and a vision model supplied with the intended layout and object IDs. This catches discrepancies between abstract geometry and actual output, including font rendering, cropping, and confusing composition.

A vision model is not a reliable collision oracle and may overlook small errors or suggest damaging changes. Ground its reports in times, regions, and objects; verify proposed changes with deterministic checks. Use denser sampling around motion and selected high-risk sections. Calibrate on defect fixtures, including legitimate graph intersections, and report missed defects rather than only attractive examples.

### F5 Search over layout alternatives and controlled repair

Generate several constrained placements for a dense beat, render inexpensive previews, and choose among candidates satisfying hard correctness/readability rules. Use a softer composition score only after hard gates pass. Search over meaningful choices such as graph-left versus graph-top, label positions, or progressive reveal.

This can outperform one-shot coordinate guessing but multiplies rendering and evaluation cost. Limit search to detected difficult cases and cache unchanged elements. Do not optimize aesthetics at the expense of the explanatory correspondence. Track repair success, newly introduced errors, and human preference. If none of the candidates fit, revise the visual plan rather than forcing a smaller font.

## G Repairing failures without breaking the lesson

### G1 Whole section regeneration

Send the failing section, error, and requirements back to a strong model and request a replacement. It is easy to implement and suitable when the underlying visual plan is wrong. It is also a necessary baseline against which more elaborate repair systems should be measured.

Regeneration can change correct mathematics, notation, and timing while fixing one issue. Preserve the original artifact and compare all hard requirements after the change. Limit retries and record every rejected attempt. Use this as the last local option for major structural failures, not the default response to a small spacing defect.

### G2 Diagnostic driven scoped patches

Classify the failure as API/runtime, layout, semantic, timing, or continuity. Supply the smallest relevant code region plus sufficient context, a precise diagnostic, and the invariants the patch must preserve. Expand the scope only when a local repair cannot work.

Code2Video's scope-guided repair is a useful precedent; the inspected implementation also illustrates why patch application needs verification. A parser can return unchanged code when feedback does not match its expected format. Require evidence that the intended edit occurred, then rerender and rerun the violated check. Syntax or a successful process exit is insufficient proof that a visual defect was fixed.

### G3 Repair the specification and recompile

When a layout, timing, or parameter error originates in the structured specification, change that source of truth and regenerate code deterministically. For example, move a label through an attachment rule rather than editing one hard-coded coordinate while leaving its future positions unchanged.

This produces maintainable repairs and a cleaner training target. It depends on the compiler representing the faulty behavior; custom code can escape those contracts. Map render diagnostics back to specification IDs and preserve the compiler version. Test that a subsequent rebuild retains the repair. Use code patches for compiler defects, and specification patches for lesson choices.

### G4 Candidate repair search with regression gates

Generate a few independent patches, evaluate each against the original failure and neighboring state, and keep the best passing candidate. Use separate semantic and visual checks to reduce self-confirmation by the generating model. A patch can be smaller yet still wrong, so edit distance is a cost signal rather than the acceptance criterion.

The search cost can exceed simply asking a stronger model once. Compare both under the same budget. Stop when candidates repeat the same failure and escalate to redesign or human review. Preserve failed repairs because they are useful examples for training a repair policy and for identifying missing compiler features.

### G5 Failure experience library and learned repair policy

Store observed failure signatures, context, attempted fixes, actual outcomes, and applicability conditions. Retrieve analogous cases before generating a patch, and later train a model on verified trajectories. Include cases where a tempting repair made the result worse.

This can reduce recurring API and lifecycle mistakes. A superficial match can apply an outdated fix to a different engine version. Version the environment and require current checks. Synthetic fault injection is useful for coverage but must be labeled separately from naturally occurring failures; a policy good at injected errors may not repair real planning mistakes. Evaluate on new defect families and report fallback rate.

## H Training and scaling economically

### H1 Strong teacher and cheap generalist routing without training

Use the strong model for lesson planning, difficult explanations, novel components, and unresolved repairs. Use a cheaper model for routine structured transformations and supported components. Route using task type and observed validator outcomes; collect the resulting traces.

This establishes the real opportunity for distillation without paying training setup costs first. It may already be economical because videos are authored once and replayed many times. Measure cost per accepted lesson, including retries and human review. Model price alone is not the objective: a slightly more expensive draft that saves ten minutes of teacher correction can be the cheaper workflow.

### H2 Supervised distillation on reviewed outputs

Train a smaller model to reproduce accepted scripts, scene plans, code, or repairs under the same input contracts. Keep task labels and use separate adapters when output styles conflict. Start with a representative subset and learning curves rather than selecting a large dataset target arbitrarily.

Synthetic teacher outputs require filtering; fluent mistakes are still mistakes after distillation. Use permitted teacher-model outputs and authorized expert data. The first useful targets may be narrow transformations with strong checks. Compare the tuned student against its untuned version plus the same retrieval context. Log training, evaluation, reviewer time, and unsuccessful runs as setup cost.

### H3 Student failure driven dataset aggregation

Run the current student on fresh lesson specifications, render its outputs, and classify failures. Ask the teacher model or expert to correct the student's actual errors. Add verified corrections and retrain. This addresses the gap between pristine teacher examples and the states the deployed student actually encounters.

It is particularly useful for repairs and unfamiliar component combinations. Selection can become dominated by frequent easy errors, leaving rare serious failures underrepresented. Sample by severity, novelty, and concept family; reserve a fresh untouched evaluation set for each iteration. Measure whether failures decrease on new lessons, not just on replayed corrections.

### H4 Preference optimization or execution based reinforcement

Use reviewed preference pairs for explanation quality and executable checks for code behavior. Prefer pairs with the same brief and comparable completeness. In reinforcement experiments, rewards can include semantic checks, layout violations, timing, and patch cost.

Reward hacking is a substantial technical risk: empty scenes have few overlaps, short scripts avoid some errors, and tiny text can fit everything. Enforce required content and minimum readability before awarding quality scores. Start only after supervised baselines and validators are credible. A scalar aesthetic score alone is not an adequate reward for educational production.

### H5 Self hosted specialists and production scheduling

On six Blackwell GPUs, profile the actual hardware and model before choosing replicas or tensor/model sharding. Assign GPU resources to inference, speech, or training based on measured demand; CPU-based Manim rendering may remain a separate bottleneck. Queue jobs by stage and cache accepted assets, audio, and renders.

Owning GPUs does not make their use free: include power, maintenance, opportunity cost, and allocated capital cost where relevant. Compare self-hosted dollars per accepted lesson at actual utilization with hosted APIs. Low utilization can erase savings. Keep training jobs from starving production inference, and use explicit resource reservations rather than assuming six GPUs form one pooled memory device.

## Combined system and experiment order

The proposed common representation has five linked parts: verified subject claims; the learner's prerequisite and concept progression; spoken narration with anchors; an evolving visual state with events; and validation requirements. Connect them through stable IDs. A visual event should identify the claim it illustrates and the narration it supports. A repair then has a precise place to act.

Implement in this order:

1. Establish a full narration and visual-intent reference for one lesson. Review it as teaching, independent of rendering.
2. Compare B1/B2/B3 on held-out briefs. Keep the strongest practical script route.
3. Compare C2 with C3 while using identical scripts and render components. Measure continuity, repeated introductions, and edit cost.
4. Compare D1/D2/D3 on the same difficult beats. Measure correctness and expressiveness as well as executable success.
5. Add F2/F3 and evaluate on deliberately labeled overlap cases; use F4 for residual perceptual problems.
6. Compare G1/G2/G3 with preserved before/after artifacts and fixed retry budgets.
7. Distill only after H1 provides a cost and failure baseline. Scale dataset volume when learning curves and production economics justify it.

Avoid a full Cartesian product of all methods. Stage the experiments, then run selected end-to-end combinations. Report the number of lessons, attempts, rejected outputs, actual durations, reviewer minutes, and confidence intervals where the sample supports them. One lesson is an integration test, not a model ranking or evidence of classroom effectiveness.
