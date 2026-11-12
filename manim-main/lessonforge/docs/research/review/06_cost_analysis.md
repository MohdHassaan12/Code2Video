# Cost analysis for twenty minute teaching lessons

Separate the cost of generating candidate material from the cost of an accepted teaching lesson. Current API token prices can make drafting surprisingly inexpensive, while expert review, repairs, and production engineering remain substantial. A cheaper model is economical only if its extra failures do not erase the token savings.

The [live pilot ledger](../experiments/openrouter_pilot/usage.json) records provider-reported usage for this session under the authorized US$5 cap. The scenarios below are estimates, not measurements of a completed 20-minute production pipeline. The [calculator](../scaling/cost_model.py) reproduces them from the saved [model-price snapshot](../experiments/openrouter_pilot/model_prices.json), writing [scenario details](../scaling/cost_scenarios.json).

## Prices and accounting

The public [OpenRouter model endpoint](https://openrouter.ai/api/v1/models) was retrieved during this session. The following are the snapshot's advertised token rates, without assuming caching discounts:

| Model | Input per million tokens | Output per million tokens | Pilot role |
| --- | ---: | ---: | --- |
| Claude Sonnet 4.6 | $3.00 | $15.00 | Strong-model plans, code, script, repair |
| Gemini 2.5 Flash | $0.30 | $2.50 | Lower-cost plan/code comparison; possible visual critic |
| Qwen3-Coder-30B-A3B Instruct | $0.07 | $0.28 | Smaller coding-model baseline |

These are comparison candidates, not claims about the best current models. Actual provider routing and rates can vary; the recorded API response cost is authoritative for the pilot. Input image/video tokens, reasoning tokens, cache writes, and any paid tools must be accounted for where used. The pilot enabled no web-search or image-generation tools. [OpenRouter usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)

For a text request:

`C_request = T_input * P_input / 1,000,000 + T_output * P_output / 1,000,000`

For production, sum all drafts, critiques, repairs, rejected attempts, speech, rendering, review, and storage. If a cost component is already included in provider-reported completion usage, do not add it a second time. The request runner uses provider price ceilings and an output-token reserve before every call. It does not automatically retry uncertain request outcomes.

## Illustrative workload for one lesson

Assume 10explanatory sections rendered through 20chunks. Chunk count is an engineering choice, not a target number of visible cuts. The assumed total includes six local repair calls; vary that assumption in the calculator rather than treating it as a measured failure rate.

| Stage | Calls | Input tokens per call | Output tokens per call |
| --- | ---: | ---: | ---: |
| Planning and revision | 4 | 8,000 | 2,000 |
| Narration and visual-intent drafting | 10 | 6,000 | 900 |
| Code generation | 20 | 6,000 | 1,800 |
| Visual review | 20 | 4,000 | 400 |
| Local repairs | 6 | 5,000 | 1,600 |
| Whole-lesson continuity review | 2 | 12,000 | 1,200 |
| Total | 62 | 346,000 total | 73,000 total |

The visual-review input is a hypothetical combined text/image token allowance. It must be replaced by actual provider accounting after testing frame count and resolution. The script output includes visual instructions as well as spoken words. The full-script pilot is a separate direct-generation measurement with a much smaller input and should not be confused with this multi-stage workload.

## Model routing comparisons

| Scenario | Routing | Estimated LLM cost per attempt |
| --- | --- | ---: |
| Premium | Sonnet for every stage | $2.1330 |
| Hybrid | Sonnet for planning, script, repairs, continuity; Qwen for code; Gemini for visual review | $0.9355 |
| Economy experiment | Qwen for text/code stages; Gemini for visual review | $0.0808 |

The economy scenario is a price floor experiment, not an accepted-quality recommendation. The live pilot found substantive defects in low-cost generated code as well as strong-model code. A quality-equivalent comparison has not been established.

This table also reveals the limited initial financial case for distilling only code generation: under these assumptions,20 Sonnet code calls cost $0.90, while the Qwen code calls cost about $0.0185. The maximum direct saving on that stage is about $0.8815 per lesson before accounting for different repair and review rates. A training project should not assume large savings simply because output tokens are cheaper.

## Non model costs and accepted output

Use these explicitly hypothetical operating assumptions to see the order of magnitude; they are not vendor quotations:

| Component | Assumption | Cost |
| --- | --- | ---: |
| Speech | 24,000 characters at $15 per million characters | $0.36 |
| Rendering | 2 CPU worker-hours at $0.50 per worker-hour | $1.00 |
| Human review and correction | 1.5 hours at $20 per hour | $30.00 |
| Storage allowance | Per-lesson allowance; delivery bandwidth excluded | $0.10 |

With those inputs, attempt costs are $33.593 premium,$32.3955 hybrid,and$31.5408 economy. These equal review-time assumptions isolate the token effect; real review time will differ by output quality. They exclude amortized software development, paid visual assets, support, taxes, and distribution bandwidth. Add those for a business budget.

At$20 per reviewer-hour, an extra five minutes costs $1.67. That exceeds the$1.20LLM saving between the premium and hybrid scenario. Therefore reducing overlap, semantic mismatch, and review effort can matter more economically than selecting the lowest token price.

Estimate accepted-output cost as total cost across all attempted lessons divided by the number accepted. If every attempt costs $32.40 and only 80% are accepted, the illustrative ratio is $40.50 per accepted lesson; at 95% it is $34.11. The ratio is only valid when the assumed cost includes rejected attempts consistently. Do not quietly remove expensive failures from the denominator or numerator.

## Why historical paper prices are not directly comparable

| Reference | Reported quantity | Appropriate use |
| --- | --- | --- |
| Code2Video | Token usage and elapsed time per topic, varying by configuration | Compare stage efficiency after reproducing matching tasks; no direct current-dollar estimate from aggregate tokens alone |
| TheoremExplainAgent | Historical table reports$0.10–$4.67 per video across older model/RAG configurations | Shows that retrieval and repeated context can materially alter cost; not today's price list |
| TeachMaster | Approximately$83.70 for a 45-hour course in its reported deployment | Author-reported operating result with a different infrastructure and accounting boundary |
| LASEV | Less than $0.07 for a roughly two-minute problem video | Useful short-form production reference; does not establish20-minute lesson costs or teacher-like quality |

Sources: [Code2Video](https://arxiv.org/html/2510.01174v1), [TheoremExplainAgent appendix](https://arxiv.org/html/2502.19400v1), [TeachMaster deployment](https://arxiv.org/html/2601.04204v2), [LASEV cost analysis](https://arxiv.org/html/2602.11790v1).

For perspective only, TeachMaster's arithmetic ratio is about $0.031 per video minute. That ratio leaves unresolved which development, quality review, hardware utilization, and rejected outputs were allocated to the number. It is not a quote for our product. Similarly, ten short independent problem videos do not constitute a continuous long explanation merely because their durations add to20 minutes.

## Training and self hosting economics

A deliberately explicit setup scenario is:

- 5,000 teacher examples, each 1,000 input and800 output tokens at Sonnet snapshot prices:$75.
- One minute of review per example at $20 per hour:$1,666.67. This may be too little for complex scenes and is only a sensitivity input.
- 40 engineering hours at $30 per hour:$1,200.
- 6 GPUs for8 hours at an assumed$3 per GPU-hour:$144. This is an accounting scenario, not a cloud quote or a training-time prediction.
- Total:$3,085.67, before additional experiments, corpus acquisition, and maintenance.

If the net saving after equal-quality review and fallback is $0.25 per lesson, break-even is about12,343 lessons. At$1 saving it is3,086; at $5 it is618; at $10 it is309. If the student costs more after repairs, there is no positive break-even.

`N_break_even = C_setup / (C_baseline_accepted - C_student_accepted)`

The denominator must compare the same quality standard. Use production measurements rather than substituting token-price ratios.

The six Blackwell GPUs can support profiling, teacher/student inference, speech, and training experiments, but the exact feasible configuration depends on SKU, VRAM, host topology, and model. For self hosting:

`C_gpu_per_accepted_lesson = allocated_GPU_hours * effective_cost_per_GPU_hour / accepted_lessons`

Include idle allocation when machines are reserved for the service, plus CPU rendering and human review. Measure throughput at the actual context and output lengths. A model fitting in memory does not establish throughput or economic advantage. Train only after the dataset and held-out evaluation reveal a repeatable task worth specializing.

## Production savings to test first

1. Approve the full script before expensive visuals, reducing late conceptual rework.
2. Reuse verified components and common assets; keep fresh narration and instructional choices where needed.
3. Regenerate only affected chunks, with explicit downstream invalidation and boundary checks.
4. Use cheap geometry checks before expensive multimodal critique, and reserve dense critique for flagged intervals.
5. Render approved videos once and distribute them repeatedly. Personalize practice, hints, or selection before generating a unique full video for every viewer.

Track script approval minutes, visual correction minutes, retry count, final accepted minutes, queue latency, and complete production cost. These measurements determine whether better retrieval, a stronger model, a compiler improvement, or distillation is the next worthwhile investment.
