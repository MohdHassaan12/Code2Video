# Scaling educational video production through datasets and distillation

**Scope update:** The [narration-led long-form approach](08_narration_led_long_form_approach.md) adds expert-teacher script research as a first-class workstream and continuity across complete lessons. Its priorities supersede this document's narrower initial training target; the data and evaluation safeguards below still apply.

Build a reusable renderer and an evidence-backed dataset around the production workflow, then fine-tune a smaller model for a narrow, measurable task. The first target should be **approved script to structured scene specification**. Retain a stronger model for unfamiliar concepts and failed cases, and retain independent content and visual checks.

Prepared on 6 October 2026. Data volumes, model sizes, and experimental budgets below are proposed planning ranges, not measured requirements. No training run, production benchmark, or large dataset has been completed. The user has six Blackwell GPUs; exact SKU, memory, host architecture, and connectivity are unconfirmed. Implementation will be delegated by the user to lower-cost models. The [framework and implementation handoff](07_frameworks_and_implementation_handoff.md) specifies that work.

## What the existing prototype teaches us

The [79-second clip](prototype/output/like_terms.mp4) contains nine scenes. Its first render succeeded technically but retained earlier objects over later scenes. Visual inspection found the defect; explicit scene clearing fixed it. Timing rounding and audio padding also needed correction. The [validation record](prototype/output/validation.json) and [visual review](prototype/output/visual_review.json) distinguish automated checks from pending teacher and learner review.

This means the valuable training artifact is not simply a script paired with code. It is a script, scene plan, executable result, observations, correction, and acceptance decision. The present lesson is one candidate source family, not nine independent lessons and not teacher-approved gold data. The original failed source snapshots were not preserved as separate immutable artifacts; do not reconstruct them and label them as observed historical trajectories.

## Separate the scaling problems

| Scaling problem | First intervention | When model training helps |
| --- | --- | --- |
| Many students watch the same lesson | Render approved lessons once; distribute cached video and captions | A smaller generator is not needed for repeated playback |
| Many different lessons must be authored | Reusable representations, structured input, render queue, review tools | Repeated scene-planning and coding tasks become candidates for fine-tuning |
| Multiple languages or accessibility variants | Separate narration and text from mathematical objects; reuse verified scenes | Language adaptation can later be trained and evaluated separately |
| Learners need individual hints | Separate rubric-grounded feedback service | Train on reviewed student attempts and hints, not on animation code |
| New topics require new visual forms | Strong-model or human author creates a reviewed component | Add the new representation to the renderer and dataset after validation |

Scale distribution and authoring independently. Generating an entire video for every student request would repeat expensive work and make quality harder to control. Initially personalize practice, hints, pace, and selection from accepted lesson segments.

## Recommended system

```text
Reviewed subject content and script
                 |
        Retrieve approved examples
                 |
      Small model proposes scene specification
                 |
   Schema checks and mathematical constraints
                 |
        Deterministic Manim compiler
                 |
     Render -> semantic and visual checks
                 |
        Accepted for subject review?
           /                  \
         yes                   no
          |                     |
    Human release review   Bounded repair / stronger model
          |                     |
    Publish and cache      Re-render and re-check
                                |
                     Record failure and correction
                                |
                       Curated training release
```

The small model can be text-only if its inputs are scripts, scene state, and structured diagnostics. A visual critic that inspects frames is a separate vision-language component. Do not assume a text-only coder can see overlaps from a successful runtime log.

## Make the output language smaller

The current scene file mixes mathematical intent, scene construction, layout, captions, and audio timing. Refactor stable behavior into tested components. Candidate primitives include equation steps, identical tile groups, number lines, coordinate plots, labeled diagrams, comparison panels, question cards, and narration cues.

Use a scene specification, also called an intermediate representation, to select components and supply their parameters. For the existing lesson, the model should express: create two and three identical x-squared tiles, preserve their dimensions, regroup them, and reveal the matching equation. The renderer should own screen coordinates, font choices, caption placement, and scene cleanup where possible.

An illustrative target is:

```json
{
  "schema_version": "0.1-proposed",
  "scene_type": "combine_identical_terms",
  "objective": "Explain addition of like terms using equal quantities",
  "coefficients": [2, 3],
  "shared_term": {"symbol": "x", "exponent": 2},
  "representation": "equal_area_tiles",
  "representation_domain": "x > 0",
  "algebra_domain": "x is real",
  "layout": "two_groups_then_one_group",
  "narration": "Two copies and three copies make five copies of x squared."
}
```

This is a proposed interface; no general compiler currently consumes it. The compiler should derive the total 5 and associated equation from structured inputs. Preserve a free-form code route for genuinely new visual forms, with stronger review. A restricted representation trades some expressivity for easier checking; measure where it becomes a bottleneck.

## Dataset tasks and supervision

| Dataset | Input | Target | Evidence needed |
| --- | --- | --- | --- |
| Script planning | Approved concept brief, prerequisites, and source evidence | Scene sequence and original narration | Subject approval and objective coverage |
| Scene generation | Approved scene script, notation, available primitives, preceding scene state | Structured scene specification or code | Render, semantic checks, and visual review |
| Repair | Original input, failing specification/code, actual diagnostics, relevant prior state | Corrected output or patch | Before/after artifacts and repeated checks |
| Preference | Identical input and two candidate outputs | Preferred output plus defect labels | Verified comparison, with correctness taking precedence |
| Visual quality | Rendered frames, scene specification, and objective | Localized defects and severity | Human-reviewed labels; possible future VLM training |
| Pedagogical feedback | Problem, rubric, learner attempt, and observed uncertainty | Diagnosis, clarification, or graduated hint | Subject review and later learner outcomes |

Begin with scene generation and repair. Keep the other tasks as separately labeled datasets even if one model eventually supports several of them. A code generator, a pedagogical planner, and a handwriting evaluator have different evidence requirements.

## Data collection procedure

1. **Define coverage.** Create a matrix of concept families, representations, mathematical operations, prerequisites, language, narration length, and failure modes. Start with algebra and coordinate geometry. Expand to science and biology only after suitable checks and reviewers exist.
2. **Create original seeds.** Propose 25–50 carefully reviewed lesson briefs, yielding roughly 200–400 scene examples depending on lesson structure. Include examples that require different visual reasoning, rather than only changing coefficients.
3. **Freeze evaluation families first.** Reserve entire lesson and concept families before teacher generation, paraphrasing, or augmentation. Maintain a separate test of new combinations of supported primitives.
4. **Generate candidates.** Use a strong teacher model to produce several structured alternatives per training input. Supply actual API documentation, component examples, and reviewed mathematical constraints. Request explicit plans and outputs needed by the task; private internal reasoning traces are not required.
5. **Execute and check.** Compile, render, inspect intermediate and final frames, verify declared mathematics, check timing, and review teaching points. Record failures as first-class outcomes.
6. **Correct and preserve.** Save immutable before/after versions, actual tool observations, patches, and acceptance reasons. Keep human edits attributable and linked to their source attempt.
7. **Curate.** Remove duplicates, ambiguous inputs, incomplete dependencies, and examples that teach an unsupported rule. Limit the weight of prolific source families so coefficient variants do not dominate.
8. **Release a version.** Publish a manifest, task counts, family splits, licenses and permissions, review coverage, model provenance, and checker versions. Keep raw generation output separate from training exports.

Teacher generation followed by filtering is supported as a general data strategy by [Self-Instruct](https://arxiv.org/abs/2212.10560). Its results do not establish how many examples this animation task needs.

## Record structure

Each collected record should contain:

- Stable record, task, lesson, scene, and source-family identifiers.
- Parent record IDs and all paraphrase, translation, correction, or parameter-variant relationships.
- Original input, task-visible context, notation and units, and preceding scene state where required.
- Target output, representation/compiler version, dependency lock, and asset references.
- Teacher model/provider/version, generation settings, prompt version, and generation date.
- Actual render logs, hashes of code and media, sampled frames, and independently maintained checks.
- Review status for executability, mathematical validity, visuals, narration, and pedagogy separately.
- Actual correction history, timing, model usage, review effort, and outcome.
- Source and asset rights, training eligibility, retention, and release restrictions.
- Dataset split and a reason for inclusion or rejection.

Split the record into immutable input, output, evidence, and provenance sections. Do not place an answer key, future reviewer verdict, or post-repair result in a model's input unless that information will exist at inference time. A repair task can include actual current error reports; ordinary generation cannot see its future errors.

The accompanying [dataset specification](scaling/dataset_specification.md) defines the initial labels and split policy. The present prototype supplies one source family for a future inventory; its teacher review remains pending.

## Quality gates before training

**Executability:** a clean environment completes within resource limits. Require the intended nonempty output; a blank video is not a pass.

**Semantic correctness:** use trusted mathematical checks, explicit assumptions, unit checks, and subject review. Tests invented by the generator can supplement a maintained test suite but should not be the sole judge of its answer.

**Visual correctness:** inspect frames at transitions and stable states; check stale objects, clipping, label collisions, and geometry. The prototype's initial boundary checks did not detect stale prior-scene objects. Add active-object identity and lifecycle checks at scene transitions.

**Instructional usefulness:** verify that each scene advances the objective and that narration matches it. A polished or executable scene can still be a weak explanation.

**Data suitability:** ensure enough context to reproduce the target, genuine review provenance, permitted training use, and family-level split isolation. Keep failed outputs in repair or preference datasets; do not train them as successful generation targets.

Initially review every seed and first instance of a new representation. For familiar parameter variants, use automated checks plus stratified human audits. Increase audit coverage when a family produces errors. An LLM judge's confidence is not a substitute for these gates.

## Distillation sequence

### First establish an untuned baseline

Evaluate a code-capable open-weight model using the component library, structured outputs, and retrieved examples before training. Compare it with a stronger teacher using the same inputs, renderer, checking budget, and repair allowance. Model choice should follow the task's held-out results, available memory, and model license, rather than a generic leaderboard.

### Supervised distillation

Fine-tune an existing model on accepted teacher outputs. This is sequence-level distillation: the student learns to predict the teacher's validated scene specification or corrected code. It does not require teacher token probabilities or identical tokenizers. The DeepSeek-R1 project documents smaller models trained on teacher-curated samples, illustrating this general approach. [Official DeepSeek-R1 repository](https://github.com/deepseek-ai/DeepSeek-R1).

Start by comparing a 7–8B class code-capable model with a smaller model if resources permit; consider 14B when the smaller candidate's held-out reasoning or repair performance is inadequate. These are experiment sizes, not a claim that a particular memory capacity will fit the workload.

Use LoRA or QLoRA as an economical first adaptation method. QLoRA trains adapters through a frozen quantized base; it is a training-memory technique, distinct from the teacher-to-student supervision strategy. [QLoRA paper](https://arxiv.org/abs/2305.14314), [PEFT quantization guidance](https://huggingface.co/docs/peft/developer_guides/quantization).

Mask loss on prompts and tool observations where appropriate, training on the assistant outputs required by the task. Preserve complete examples and record truncation; silently dropping the end of a program creates misleading targets. The current [TRL supervised trainer documentation](https://huggingface.co/docs/trl/sft_trainer) describes supported training formats and loss options. Pin the actual training stack before implementation.

Proposed learning curve: compare 250, 1,000, and 5,000 accepted scene/repair examples while tracking the number of independent source families. Run a small set of learning rates and adapter configurations against validation only. These counts are checkpoints for deciding whether more data helps, not a promised path to a target success rate.

### Train from the student's actual failures

After the first model, run it on training-pool prompts and collect the states it actually reaches. Have the teacher correct those exact failed states, re-run the checks, and add accepted repairs. Do not attach a patch from a teacher's different code state to the student's trajectory.

This preserves tools in the workflow. Research on [agent distillation with retrieval and code tools](https://arxiv.org/abs/2505.17612) studies transferring tool-using behavior to smaller models. It does not demonstrate a ready-made Manim model, but it is closer to this task than copying polished answers alone.

### Add preference optimization only when useful

Once supervised training reliably produces viable outputs, collect comparisons under the same input. Prefer correct and clear over correct but confusing; clearly label wrong mathematics as a hard failure. DPO is a possible method for learning from preferred/rejected pairs. [DPO paper](https://arxiv.org/abs/2305.18290).

Keep prompt conditions identical across a preference pair. If the repaired candidate was given an error message and the original was not, that is naturally a repair training example rather than a clean preference pair. Human edits may yield a pair only when both targets answer the same original input.

### Consider advanced distillation or reinforcement learning later

Student-generated rollouts with teacher/evaluator supervision can address distribution mismatch; [EasyOPD, July 2026](https://arxiv.org/abs/2607.11012) is recent infrastructure for several on-policy distillation settings. Some methods need teacher logits and tokenizer alignment, while correction-based supervised training does not. Inspect the chosen method's access requirements before adopting it.

Execution rewards could later encourage valid outputs, but “code ran” is an inadequate reward. A system can exploit a weak checker by omitting the difficult content. Retain hard correctness and coverage gates, and test deliberately misleading outputs against the evaluator. Do not start with an expensive RL pipeline before establishing a useful supervised baseline.

## Evaluate the whole system

Report schema validity, first-pass render rate, semantic acceptance, visual acceptance, lesson coherence, first-pass acceptance without human repair, acceptance after a fixed repair budget, fallback rate, human minutes, and total cost per accepted lesson. Use the same budget for teacher and student comparisons and count all attempts.

Hold out concept families, not just random scenes. Keep all derived versions of a source example in one split. Also test longer compositions: nine correct independent scenes can still fail when combined. Recheck performance after inference quantization.

Compare: untuned student with retrieval, supervised student, student with repair training, student with preference training if available, and the teacher. Report what each added stage contributes. Use a locked final test set only after choosing the model and settings.

Teacher review remains distinct from model evaluation. Evidence that a small model imitates accepted scene outputs is not evidence that schoolchildren learn equally well from every resulting lesson.

## Production cost and routing

Route supported familiar representations to the student. Route unfamiliar primitives and repeated failures to the stronger model or author. Base routing on supported schema, verified constraints, and observed failure rates; do not rely only on self-reported confidence. All routes pass the same acceptance process.

Use content-addressed caches for specifications, generated code, assets, narration, and rendered segments. Include script, renderer, font, model, voice, and dependency versions in the appropriate cache keys. Run independent scenes in worker processes and assemble only after checking cross-scene state and notation.

Let C_setup be collection plus training plus evaluation cost. Let C_teacher and C_student be measured total cost per accepted lesson, including failed attempts, review, repair, fallback, and compute. Training breaks even after approximately:

`N > C_setup / (C_teacher - C_student)`

This only makes sense when C_teacher exceeds C_student and both systems meet the same quality bar. If narration, rendering, or review dominates cost, a smaller model may offer little overall saving. Measure the cost breakdown before expanding training.

## Proposed milestones

| Milestone | Concrete deliverable | Gate to continue |
| --- | --- | --- |
| 1 Production foundation | Refactor the prototype into a scene specification and 6–8 reusable primitives; log every attempt | Replay the existing clip from structured input with regression checks |
| 2 Data foundation | 25–50 reviewed briefs; initial scene/repair corpus; frozen family splits | Reproducible artifacts and trustworthy labels |
| 3 First model experiment | Untuned baseline versus supervised adapter; learning-curve results | Better accepted output or lower accepted-production cost |
| 4 Failure-driven improvement | Verified repairs from actual student failures; optional preference pairs | Improvement on held-out families without content regression |
| 5 Scaled production | Batch generation, cache, fallback, reviewed release workflow | Measured quality, throughput, review load, and cost |

The next engineering action is milestone 1: transform `like_terms.py` from a one-off scene script into a compiler for a small, explicit scene format. That gives us stable model targets and makes every subsequent authored lesson a reproducible candidate for the dataset.
