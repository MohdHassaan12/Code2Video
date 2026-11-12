# OpenRouter pilot results for long form lesson production

Total provider-reported cost was **US$0.48565189 across 13 requests**, below the authorized US$5 cap. All requests have completed. The credential was read without terminal echo and kept in process memory; it was not written to the experiment files. No training job was run.

This is a one-topic diagnostic pilot, not a statistically reliable model ranking, a reproduction of Code2Video, or a completed 20-minute video. It compares matched plan and code prompts, preserves failed deliveries, and tests one diagnostic-guided repair. Source prompts, full responses, usage, source code, render logs and videos are retained.

## Tasks and controls

The topic is slope and intercept in y=mx+b for learners aged14–16. Every model received the same verified factual brief and task prompt. The plan request required 8–12 sections totaling1,200 seconds, a 350–450 word opening, two worked problems and three independent problems. The code request required a 60-second continuous Manim 0.19.0scene with a persistent graph, an intercept change, a slope change, equal axis units, clipping, readable labels and reserved caption space.

Three initial plans used a 6,000output-token limit. Sonnet and Gemini hit that limit, producing incomplete JSON. This is an output-budget failure of the pilot setup, not evidence that those models cannot produce valid plans. All three plan prompts were repeated with 12,000 tokens allowed; the original attempts and their cost remain included. Gemini's first code request was rate-limited upstream. Qwen's first code response contained no usable message content despite reported billed tokens. Both were retried once.

The delivered code was inspected before rendering in the existing isolated Manim environment. Only surrounding Markdown fences were stripped; no semantic changes were made to the original code candidates. Preview renders used 480p15 and had no audio, because the coding task intentionally isolated animation production. The full narration request was a separate Sonnet-only task.

## Plan results

| Model | Initial attempt | Follow-up with larger output budget | Observed contract issues |
| --- | --- | --- | --- |
| Sonnet 4.6 | Truncated JSON | Valid JSON;12 sections;1,300 seconds;411opening words | Duration exceeds the required 1,200 seconds |
| Gemini 2.5 Flash | Truncated JSON | Valid JSON;12 sections;1,290 seconds;251opening words | Duration and opening length fail |
| Qwen3-Coder-30B-A3B | Valid JSON;8 sections;960 seconds;137opening words | Empty delivered message content | Initial plan undershoots duration and opening length; follow-up unusable |

These results show that duration totals and completeness need deterministic checks. They do not establish relative teaching effectiveness: no teacher panel or learner trial rated these plans. Provider errors and empty delivered responses are separated from content defects.

## Code and render results

| Candidate | Render outcome | Duration | Specific observations |
| --- | --- | --- | --- |
| Sonnet original | Renders |58.000scheduled;58.067encoded seconds | Late text overlap, stale b=1 text while graph shows b=2, triangle remains on the prior line; unequal axis units; caption boundary crossed |
| Gemini delivered retry | Fails | No completed video;42 seconds of static scheduled calls | Uses an incompatible `axes.get_graph(..., x_range=...)` call under pinned Manim 0.19.0; initial axes also exceed the frame |
| Qwen delivered retry | Renders |30.000scheduled;30.134encoded seconds | Trackers never actually change to requested b=2 or m=−1; at 20 seconds a rising line appears with a slope −1 label; no requested numeric axis labels; unequal units |
| Sonnet diagnostic repair | Renders |58.000scheduled;58.067encoded seconds | Improves right-panel spacing and synchronized b-state; fixes equal units; still fails60 seconds, caption clearance, and some graph-label separation |

No code candidate passed the full requested contract. Therefore this pilot has no defensible finite cost per accepted animation to report. Token price divided by the number of API responses would conceal the failed quality requirements.

Inspect the [original Sonnet contact sheet](sonnet_original_contact_sheet.jpg), [repaired contact sheet](sonnet_repaired_contact_sheet.jpg), and [Qwen frame at 20 seconds](frames/qwen_20.png). Original and repaired videos are available at [Sonnet original](renders/sonnet_original/videos/sonnet_original/480p15/SlopeInterceptDemo.mp4), [Sonnet repaired](renders/sonnet_repaired/videos/sonnet_repaired/480p15/SlopeInterceptDemo.mp4), and [Qwen original](renders/qwen_original/videos/qwen_original/480p15/SlopeInterceptDemo.mp4).

## Repair evidence and limits

The repair prompt supplied the original source and concrete findings from source inspection and sampled rendered frames. It cost $0.094278. The model produced a revised program; that program was rendered and checked again. The repair was partially effective but did not meet acceptance.

The [geometry checks](initial_geometry_checks.json) measured Sonnet's x/y unit sizes changing from approximately 0.933/0.800 to 0.800/0.800. The repaired axes' bottom was −2.62854, which still crosses the specified −2.6 caption boundary. Both original and repaired code schedule58 seconds despite comments suggesting60 seconds.

This illustrates why repairs require independent checks and why measuring rendered object extents is stronger than reasoning only from nominal axis lengths. The sampled visual review does not certify every frame; it identified residual graph-label crowding. Detection in this pilot was partly manual, so it is not a benchmark of an autonomous visual critic.

## Full narration draft

The separate full-script call cost $0.089835 and returned ten sections with roughly 2,400 spoken words under the documented counting heuristic. Its marked thinking pauses total 150 seconds rather than the approximately90 seconds requested. It includes worked examples and independent problems, but initially used an overbroad statement about all straight lines and language suggesting a line starts at its intercept.

The raw [model output](anthropic__claude-sonnet-4.6__full_script.txt) is preserved. The [edited teaching draft](../../examples/long_form_slope_script_draft.md) corrects several clarity issues, with remaining work listed in [production notes](../../examples/long_form_slope_production_notes.md). No audio was synthesized for this manuscript, and exact duration is unmeasured.

## Actual spend by task

| Model | Plan attempts combined | Code attempts combined | Additional task |
| --- | ---: | ---: | --- |
| Sonnet 4.6 |$0.20190600|$0.05749200| Full script$0.08983500;repair$0.09427800 |
| Gemini 2.5 Flash |$0.03289050|$0.00713530| None |
| Qwen3-Coder-30B-A3B |$0.00116707|$0.00094802| None |
| Total | | | **$0.48565189** |

Costs include truncated, empty, and retried requests. They exclude local rendering and this assistant's analysis time. They measure specific short requests, not the hypothetical complete workflow in the [cost analysis](../../research/06_cost_analysis.md).

## Reproduction and artifacts

The [usage ledger](usage.json) contains provider response IDs and reported token costs. The [price snapshot](model_prices.json) contains the public model metadata retrieved for this comparison. [Prompts](prompts.json), the [repair prompt](repair_prompt.txt), and original response JSON are retained. The price snapshot covers the models as advertised at retrieval; actual billed provider rates appear in response usage.

Run deterministic artifact checks without an API key:

```bash
python3 meeting/education_content_review/experiments/openrouter_pilot/check_artifacts.py
```

For the initial geometry check, run `check_initial_geometry.py` with the prototype's Manim virtual environment from this experiment directory. It constructs the inspected candidates only until their first animation call and measures axes; it does not validate complete motion or labels. The saved [artifact checks](artifact_checks.json) distinguish parsing, schedule, and render results.

The API scripts are research runners, not production services. An intentional rerun incurs new charges. Preserve or copy the experiment directory before a new run so original observations remain immutable. Keep credentials out of files and use a separately scoped budget for any new comparison.

## Implications for the implementation

Use deterministic arithmetic to validate section budgets; common parameter sources to synchronize diagrams and text; actual geometry to enforce layout; pinned API examples to reduce engine mismatches; and acceptance checks after every repair. Broaden the benchmark before selecting a model or investing in distillation. The useful training records are the prompt, exact candidate, observed defect, repair, and post-repair results—not merely a code block labeled successful because it rendered.
