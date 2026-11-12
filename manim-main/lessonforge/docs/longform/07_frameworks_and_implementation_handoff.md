# Framework selection and implementation handoff for six Blackwell GPUs

**Scope update:** Use the [narration-led long-form approach](08_narration_led_long_form_approach.md) for current product requirements and assignments: expert-teacher script generation, complete lessons, continuous visual state, audio timing, and temporal overlap repair. This document supplies the infrastructure baseline.

Use this specification to assign bounded implementation tasks to lower-cost coding models. The target system converts approved teaching scripts into verified educational animations and collects the evidence needed to fine-tune a smaller model. This handoff adds no training implementation and starts no GPU jobs.

Hardware provided by the user: six Blackwell GPUs. Exact models, VRAM, topology, CPU architecture, and whether they share one host remain to be inventoried. Framework documentation was checked on 6 October 2026. Pin tested versions during environment setup; the links below identify capabilities rather than an already validated combined installation.

## Selected framework stack

| Component | Recommended framework | Responsibility |
| --- | --- | --- |
| Model loading and tokenization | Hugging Face Transformers | Load pinned student revisions and their native chat templates |
| Supervised and preference training | [TRL](https://huggingface.co/docs/trl/index) | SFT first, optional DPO, with explicit target-loss masking |
| Adapter training | [PEFT](https://huggingface.co/docs/peft/developer_guides/quantization) | LoRA first; QLoRA if memory profiling justifies it |
| Distributed launch | [Accelerate](https://huggingface.co/docs/accelerate/usage_guides/fsdp) with PyTorch DDP or FSDP | Launch training; shard only when memory requires it |
| Batched generation and serving | [vLLM](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/) | Teacher/student inference, bounded outputs, model revision logging |
| Scene schema | [Pydantic](https://docs.pydantic.dev/latest/) | Strict typed validation and an exported JSON Schema |
| Rendering | Manim plus FFmpeg | Compile accepted scene specifications, render, align narration, export media |
| Mathematical verification | SymPy plus maintained subject-specific checks | Validate identities and domains without treating execution as correctness |
| Training data | [Hugging Face Datasets](https://huggingface.co/docs/datasets/index) and Parquet | Versioned records and reproducible training exports |
| Batch workflow | Python worker processes initially; [Ray Data](https://docs.ray.io/en/latest/data/data.html) when scale warrants | Schedule generation, rendering, and verification with resource limits |
| Experiment tracking | [MLflow](https://mlflow.org/docs/latest/ml/tracking/) | Parameters, dataset hashes, checkpoints, measurements, and acceptance reports |
| Artifact storage | Existing shared storage or object store | Immutable code, frames, audio, video, and logs addressed by hash |

Keep training, inference, and rendering in separate environments or containers. This prevents a rendering dependency change from silently replacing the training CUDA stack. Prefer a small number of explicit Python stages over introducing an agent orchestration framework into the first version.

**Alternative:** [LlamaFactory](https://github.com/hiyouga/LlamaFactory) provides configurable fine-tuning and serving integrations and is a reasonable choice for a quick standard baseline. Use TRL for the primary research pipeline because this project needs custom exports, task-specific loss handling, repair data, and controlled ablations. Select one primary trainer; avoid maintaining duplicate training logic in both.

## Blackwell environment gate

The environment task must first record GPU model, per-device memory, compute capability, driver, host architecture, GPU topology, CPU/RAM, local storage, and network layout. Six GPUs are not automatically one pooled memory space. Data parallelism replicates model state; sharding changes the memory arrangement and communication cost.

PyTorch introduced Blackwell support with its 2.7 release and CUDA 12.8 wheels. Current vLLM guidance states B200/GB200 require CUDA 12.8 or newer; that is a compatibility floor for those devices, not a complete environment prescription for every Blackwell product. [PyTorch release](https://pytorch.org/blog/pytorch-2-7/), [vLLM GPU installation](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/).

Select a maintained, mutually compatible container or wheel set for the actual GPU and host. Require one forward/backward pass, checkpoint save/reload, and a multi-GPU collective test. Establish a BF16 baseline first. Enable optional attention kernels, quantization libraries, compilation, or FP8 only after each passes its own compatibility and quality checks. Record container digest and all package versions.

## How to use the six GPUs

| Stage | Proposed scheduling |
| --- | --- |
| Initial baseline | One GPU if the chosen model, sequence length, and batch fit; profile before distributing |
| SFT experiments | Six-device data parallel training if a full replica fits, or sharded training if needed; alternatively run independent small sweeps concurrently |
| Synthetic collection | Replicated generation workers when each model fits; tensor-parallel groups only for models that need them |
| Teacher plus critic | Example conditional layout: four devices for a teacher and two for a visual critic, only if model shapes, memory, and interconnect support it |
| Rendering | CPU worker pool for the current Cairo-based renderer; profile CPU, RAM, and disk throughput separately |

Six is a valid data-parallel world size. Do not assume tensor parallel size six is supported for a selected model; attention-head and architecture constraints may favor one, two, or another compatible group size. Do not keep training and large-model inference resident on the same devices by default.

The system should accept an external teacher endpoint as well as a local vLLM endpoint. This lets the team choose the teacher by accepted-output quality without rebuilding the data pipeline. A small locally served teacher is useful only if its outputs meet the same checks.

## Initial model and training experiments

Use an existing code-capable instruct checkpoint. As reproducible candidates, the official [Qwen2.5-Coder-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) and [14B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct) cards provide concrete baselines. These are established candidates, not a claim that they are the latest or best models. Compare any newer shortlisted model on the same held-out scene tasks before committing.

Start with a 7B baseline and an adapter run. Select sequence length from the actual scene-record length distribution. A provisional 4K-token configuration is reasonable for a smoke experiment if every selected example fits; retain or split long records deliberately instead of silently truncating code. Try a small validation-only sweep, such as LoRA rank 16 versus 32 and two learning rates, with fixed data and token budgets. The final settings must come from measured validation results.

Use BF16 LoRA if memory permits. Use QLoRA to address memory pressure, not because six GPUs automatically require it. Record effective batch size as devices times per-device batch times gradient accumulation. Resume checkpoints must preserve optimizer, scheduler, random state, and data position as supported by the pinned stack.

Train in this order:

1. Accepted script-to-scene-specification examples using SFT.
2. Verified repairs from the student's own failures, mixed with successful generation examples to retain initial generation quality.
3. Optional DPO on reliable, same-input preference pairs.
4. Optional on-policy distillation after offline training and failure collection are effective.

Current TRL exposes a [DistillationTrainer](https://huggingface.co/docs/trl/distillation_trainer); [EasyOPD](https://arxiv.org/abs/2607.11012) is another research option for on-policy methods. Their supervision and teacher-access requirements must be checked against the selected method. Sequence-level SFT from accepted outputs remains the simplest first distillation experiment. Quantization is a separate inference/training optimization, not a replacement for task learning.

## Module contracts

The following names are proposed interfaces for the implementing models. They do not exist yet.

| Module | Input | Output |
| --- | --- | --- |
| `schemas` | Lesson and scene JSON | Validated `LessonSpec`, `SceneSpec`, and validation errors |
| `compiler` | Scene specification and renderer version | Code bundle, asset manifest, semantic checks |
| `render_worker` | Code bundle and measured narration | Video, frames, object/timing trace, runtime logs |
| `verifier` | Specification and rendered artifacts | Independent statuses and defect records |
| `teacher_client` | Reviewed brief, permitted context, and task type | Candidate output with full provenance |
| `collector` | Candidate, artifacts, reviews, and correction history | Immutable raw attempt record |
| `curator` | Raw records and family split map | Eligible training records and rejected records with reasons |
| `trainer` | Dataset manifest and pinned model configuration | Adapter/checkpoint, training log, data hashes |
| `evaluator` | Checkpoint, locked tasks, and budget | Acceptance, error, latency, fallback, and cost report |
| `router` | Production request and known capabilities | Student result, bounded repair, or teacher escalation |

Use an explicit state machine: requested, generated, schema_valid, compiled, rendered, checked, human_reviewed, accepted or rejected. Retries create child attempts. Repeated delivery of a completed job must not silently generate duplicate records or charge another model call.

## Implementation tickets for lower-cost coding models

Assign these in dependency order. Each ticket should return changed files, runnable commands, measured checks, and remaining limitations. A code model must not mark human reviews complete.

### Ticket 0 Environment and hardware report

**Scope:** Inventory the actual six-GPU host or cluster, select compatible training/inference containers, and create immutable environment records. Do not assume x86 or a particular GPU memory size.

**Acceptance:** One-device forward/backward check; multi-device collective; checkpoint reload; a short inference request; exact revisions and logs. Training or inference outside a small smoke budget needs a configured job budget.

### Ticket 1 Scene schema and renderer refactor

**Scope:** Implement Pydantic schemas and a deterministic compiler. Refactor the existing like-terms prototype into supported primitives: equation sequence, equal tile groups, comparison panel, narration cue, and practice card. Add other primitives after these work.

**Acceptance:** Reproduce all nine scenes from JSON; preserve tile dimensions and equations; no stale scene objects; identical input produces the same scene plan and deterministic mathematical geometry. Compare sampled frames and decoded media rather than requiring byte-identical encoded MP4 files.

### Ticket 2 Render verification and regression corpus

**Scope:** Build a verifier that checks lifecycle, geometry, equations, layout, timing, and media. Keep a small corpus of valid scenes and explicitly injected faults.

**Acceptance:** Detect the prototype's known stale-object, timing, and audio-length failures. Detect a wrong exponent and a clipped label. Maintain independent expected outcomes; a test that merely repeats generator assertions is insufficient. Run generated code in a restricted worker with time and memory limits.

### Ticket 3 Dataset collection and review export

**Scope:** Implement the [dataset specification](scaling/dataset_specification.md), immutable attempts, correction links, task labels, content hashes, and source-family splits. Import the existing prototype as pending teacher review.

**Acceptance:** No family leakage; no unapproved target exported as gold; unknown metadata stays null; failed attempts remain recoverable; every curated record traces to actual artifacts. Preserve reviewed code and media outside JSONL while referencing them by hash.

### Ticket 4 Teacher generation and bounded repair

**Scope:** Implement interchangeable endpoint clients, candidate generation, compiler/render execution, independent checks, bounded repair, and logging. Collect explicit scene plans and actionable corrections rather than relying on private reasoning traces.

**Acceptance:** Run a small configured set of real tasks; retain every failed and successful attempt; preserve actual diagnostic context; retries terminate at the budget; report accepted fraction and review effort. Generated plans must not alter approved mathematical content without review.

### Ticket 5 Untuned baseline and SFT

**Scope:** Export task-specific prompt/target examples, load the chosen model with its chat template, and implement a TRL plus PEFT training entry point. Include Accelerate configuration selected from Ticket 0.

**Acceptance:** Inspect actual token masks; no training on padding or unintended prompt tokens; no unreported truncation; a tiny-batch sanity run; resumable checkpoint; comparison against the untuned model with identical inference and repair budgets. Do not interpret falling training loss as video quality.

### Ticket 6 Held-out evaluation and student failure collection

**Scope:** Implement per-family reporting and complete-lesson composition checks. Generate student failures only from the training/development pool for subsequent repair training.

**Acceptance:** Report first-pass and post-repair results separately, plus semantic defects, visual defects, human time, fallback, and accepted-production cost. Keep the final test locked. Store teacher repairs matched to the student's exact failing state.

### Ticket 7 Optional preference and on-policy training

**Scope:** Add DPO only after reliable pairs exist. Add one on-policy method only after documenting its teacher access, tokenizer assumptions, and runtime cost.

**Acceptance:** Measured incremental improvement over SFT plus repairs on the same held-out families. Preserve correctness gates; reject reward schemes that accept a blank video or omitted teaching point simply because rendering succeeds.

## Copy-ready task preamble

> Implement only the assigned ticket. Read the scaling plan, dataset specification, current prototype, and this handoff. Preserve the existing playable prototype. Treat named future interfaces as requirements to implement, not as existing code. Use primary documentation matching pinned dependency versions. Keep human approval statuses pending until supplied. Do not invent dataset rows, metrics, GPU capabilities, or training results. Keep implementation inside the assigned module boundaries, expose explicit inputs and outputs, and finish with commands, evidence, and limitations. Before an expensive run, use the configured budget and complete the small acceptance checks.

## First data and model milestone

Target 25–50 reviewed briefs, roughly 200–400 scene candidates, plus recorded failures and verified repairs. These are initial collection targets. Freeze family splits before expansion. Run a first baseline and adapter experiment, then expand toward 1,000 and 5,000 accepted examples only if the learning curve and accepted-production cost justify it.

The scarce resource may become subject review and rendering throughput before GPU compute. Track that explicitly. Success means a lower cost per accepted, teachable lesson with equal or better correctness—not simply a model that generates syntactically valid Manim code.
