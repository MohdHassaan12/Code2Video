# Layout side study: the decision rule, written before any result

Written on 2026-11-13, while bench/layout_study.py was still running, before any of its scores were read.

**Question.** Does fixing layout and timing change what the student learns from the video?

**Set.** The 10 approved NOVEL-12 concepts (bench/admission/approved.json), three versions each: ours, ours + timing fixes, and Claude-fixed.

**Primary measure.** M9: the gain on 3 frames per section. This is the share of what the student did not know that it learned, on a 0–100 scale.
- For each concept, take Claude-fixed minus ours.
- M7 (the dense video) is reported beside it.

**Rule.**

- *Layout changes learning* if both hold:
  - the mean M9 difference (Claude-fixed − ours) is at least +5 points;
  - Claude-fixed ≥ ours on at least 7 of the 10 concepts.
  - Then the layout-fixer comparison runs on the 40 base sections, judged on renders, MVQS, timing faults and broken attachments:
    1. the fixing method (raw shift, attachment-safe rules, rewrite);
    2. what the fixer sees (code + reports, or code + frames);
    3. the model.
- *Layout is mostly cosmetic for this student* otherwise.
  - Then only the attachment-safe layout fix and a short side table go into the report, and the effort stays on F0–F5.
- A concept whose M9 is undefined for either version is left out of both counts. The number left out is reported.

**Also reported, with no decision attached.**
- The same comparison for ours + timing fixes against ours. Only 3 of the 10 videos changed, so a difference near 0 is expected.
- Layout score, timing faults and broken attachments for every version.
