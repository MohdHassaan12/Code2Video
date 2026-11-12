# Measured API cost

These are actual OpenRouter charges for this lesson attempt, including failed and truncated responses. They are not the full economic cost of producing a lesson. Local CPU rendering, local TTS and coding-assistant work are not priced here.

| Request | Model | Completion status | Charge |
|---|---|---|---:|
| narrative | anthropic/claude-opus-5.5 | length | $0.417120 |
| narrative_v2 | anthropic/claude-sonnet-4.6 | stop | $0.223185 |
| part1 | anthropic/claude-sonnet-4.6 | length | $0.311439 |
| chapter5 | anthropic/claude-sonnet-4.6 | stop | $0.070572 |
| chapters678 | anthropic/claude-sonnet-4.6 | stop | $0.151635 |
| chapters910 | anthropic/claude-sonnet-4.6 | stop | $0.124260 |

This lesson: **US$1.298211**. Earlier comparison: US$0.48565189. Combined authorized-budget usage: **US$1.78386289 of US$5**. Remaining: US$3.21613711.

The Opus request returned no visible script after consuming its reasoning/output limit. The long first-half code request returned four complete chapters and part of chapter five. Complete replacements were generated in smaller requests. Premium outputs still needed substantial review and repair; this is not a measured cost for fully autonomous production.

The immutable response files and usage ledger preserve the provider usage fields. The model-price snapshot records the Sonnet listing used by the runner. The runner applies provider price ceilings and reserves maximum request costs before sending requests. No further paid calls are needed for the current build.
