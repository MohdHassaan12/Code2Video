# Metric ladder: novel12

10 topics, 10 distinct videos.

| Rung | Change | Defined | Distinct values | Own − other topic (base) | Reliability | learner−base ties |
|---|---|---|---|---|---|---|
| M0 | TeachQuiz, as in the pilot | 7/10 | 7 | n/a | n/a | None |
| M1 | + answers matched by order | 10/10 | 9 | +0.483 [+0.346, +0.625] 10/0/0, p 0.002 | 0.671 (seed 1 vs seeds 2-3) | None |
| M2 | + forced choice | 10/10 | 5 | +0.425 [+0.300, +0.562] 10/0/0, p 0.002 | 0.214 (option order 0 vs 1) | None |
| M3 | + normalised gain (NVG) | 10/10 | 9 | +0.745 [+0.497, +1.012] 10/0/0, p 0.002 | 0.428 (option order 0 vs 1) | None |
| M4 | + dense silent video | 10/10 | 5 | +0.307 [+0.092, +0.515] 7/2/1, p 0.0234 | -0.191 (option order 0 vs 1) | None |
| M5 | + motion control (D-VGAIN) | 10/10 | 7 | +0.325 [+0.073, +0.567] 8/0/2, p 0.0391 | -0.075 (option order 0 vs 1) | None |
| M6 | + continuous scoring | 10/10 | 10 | +0.237 [+0.062, +0.412] 9/0/1, p 0.0195 | 0.103 (option order 0 vs 1) | None |
| M7 | + option rotation | 10/10 | 10 | +0.265 [+0.130, +0.403] 9/0/1, p 0.0059 | n/a | None |
| M8 | + prior filter (unknown items only) | 10/10 | 10 | +0.265 [+0.143, +0.403] 9/0/1, p 0.0039 | n/a | None |
| M9 | M7 on 3 frames per section (no dense video) | 10/10 | 10 | +0.644 [+0.496, +0.795] 10/0/0, p 0.002 | n/a | None |
| R7 | raw: dense video P(right) minus no-video P(right) | 10/10 | 10 | +0.121 [+0.064, +0.172] 9/0/1, p 0.0059 | -0.309 (option order 0 vs 1) | None |
| R9 | raw: 3 frames/section P(right) minus no-video P(right) | 10/10 | 10 | +0.362 [+0.285, +0.442] 10/0/0, p 0.002 | 0.297 (option order 0 vs 1) | None |

## Paired condition differences per rung

mean [bootstrap 95% CI] wins/ties/losses, Wilcoxon p

| Rung | learner − base | learner − generic | learner − learner_all | generic − base |
|---|---|---|---|---|
| M0 | n/a | n/a | n/a | n/a |
| M1 | n/a | n/a | n/a | n/a |
| M2 | n/a | n/a | n/a | n/a |
| M3 | n/a | n/a | n/a | n/a |
| M4 | n/a | n/a | n/a | n/a |
| M5 | n/a | n/a | n/a | n/a |
| M6 | n/a | n/a | n/a | n/a |
| M7 | n/a | n/a | n/a | n/a |
| M8 | n/a | n/a | n/a | n/a |
| M9 | n/a | n/a | n/a | n/a |
| R7 | n/a | n/a | n/a | n/a |
| R9 | n/a | n/a | n/a | n/a |

## What the student knows without the video

```
{
 "s_blind_mean": 0.375,
 "s_blind_p_mean": 0.41,
 "topics_blind_all_right": 0,
 "unknown_items_per_topic": [
  4,
  6,
  4,
  4,
  5,
  3,
  6,
  6,
  6,
  5
 ],
 "s_visual_mean": 0.537,
 "s_static_mean": 0.463,
 "s_frames_mean": 0.637,
 "s_visual_p_mean": 0.502,
 "s_frames_p_mean": 0.675,
 "s_static_p_mean": 0.471,
 "tq_abstained_mean": 41.68
}
```
