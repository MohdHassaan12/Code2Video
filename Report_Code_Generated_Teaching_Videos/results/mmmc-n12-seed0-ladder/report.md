# Metric ladder: mmmc-n12-seed0

12 topics, 48 distinct videos.

| Rung | Change | Defined | Distinct values | Own − other topic (base) | Reliability | learner−base ties |
|---|---|---|---|---|---|---|
| M0 | TeachQuiz, as in the pilot | 48/48 | 8 | +0.106 [+0.011, +0.222] 4/8/0, p 0.125 | n/a | 7 |
| M1 | + answers matched by order | 47/48 | 9 | +0.106 [+0.022, +0.217] 5/7/0, p 0.0625 | 0.956 (seed 1 vs seeds 2-3) | 7 |
| M2 | + forced choice | 48/48 | 2 | +0.167 [+0.050, +0.333] 6/6/0, p 0.0312 | 1.0 (option order 0 vs 1) | 12 |
| M3 | + normalised gain (NVG) | 0/48 | 0 | n/a | n/a | None |
| M4 | + dense silent video | 0/48 | 0 | n/a | n/a | None |
| M5 | + motion control (D-VGAIN) | 0/48 | 0 | n/a | n/a | None |
| M6 | + continuous scoring | 0/48 | 0 | n/a | n/a | None |
| M7 | + option rotation | 0/48 | 0 | n/a | n/a | None |
| M8 | + prior filter (unknown items only) | 0/48 | 0 | n/a | n/a | None |
| M9 | M7 on 3 frames per section (no dense video) | 0/48 | 0 | n/a | n/a | None |
| R7 | raw: dense video P(right) minus no-video P(right) | 48/48 | 17 | +0.041 [-0.025, +0.147] 9/0/3, p 0.3804 | 0.654 (option order 0 vs 1) | 1 |
| R9 | raw: 3 frames/section P(right) minus no-video P(right) | 48/48 | 21 | +0.130 [+0.042, +0.238] 12/0/0, p 0.0005 | 0.771 (option order 0 vs 1) | 0 |

## Paired condition differences per rung

mean [bootstrap 95% CI] wins/ties/losses, Wilcoxon p

| Rung | learner − base | learner − generic | learner − learner_all | generic − base |
|---|---|---|---|---|
| M0 | +0.017 [-0.017, +0.055] 3/7/2, p 0.5 | -0.022 [-0.105, +0.061] 1/9/2, p 0.75 | -0.044 [-0.111, +0.006] 1/8/3, p 0.25 | +0.039 [-0.050, +0.144] 2/7/3, p 0.75 |
| M1 | +0.072 [-0.011, +0.178] 3/7/2, p 0.3125 | +0.028 [-0.044, +0.122] 2/8/2, p 0.875 | +0.006 [-0.018, +0.036] 1/9/1, p 1.0 | +0.044 [-0.011, +0.122] 3/7/2, p 0.5 |
| M2 | +0.000 [+0.000, +0.000] 0/12/0, p 1.0 | +0.000 [+0.000, +0.000] 0/12/0, p 1.0 | +0.000 [+0.000, +0.000] 0/12/0, p 1.0 | +0.000 [+0.000, +0.000] 0/12/0, p 1.0 |
| M3 | n/a | n/a | n/a | n/a |
| M4 | n/a | n/a | n/a | n/a |
| M5 | n/a | n/a | n/a | n/a |
| M6 | n/a | n/a | n/a | n/a |
| M7 | n/a | n/a | n/a | n/a |
| M8 | n/a | n/a | n/a | n/a |
| M9 | n/a | n/a | n/a | n/a |
| R7 | +0.014 [-0.000, +0.030] 8/1/3, p 0.2783 | -0.001 [-0.004, +0.001] 6/0/6, p 0.9097 | +0.003 [-0.003, +0.012] 9/0/3, p 0.2661 | +0.015 [+0.000, +0.031] 9/0/3, p 0.0923 |
| R9 | +0.001 [-0.001, +0.003] 6/0/6, p 0.5186 | +0.000 [-0.001, +0.002] 7/0/5, p 0.9097 | +0.001 [-0.001, +0.003] 9/0/3, p 0.3013 | +0.001 [-0.001, +0.003] 5/0/7, p 0.9697 |

## What the student knows without the video

```
{
 "s_blind_mean": 1.0,
 "s_blind_p_mean": 1.0,
 "topics_blind_all_right": 12,
 "unknown_items_per_topic": [
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0
 ],
 "s_visual_mean": 0.996,
 "s_static_mean": 0.988,
 "s_frames_mean": 0.983,
 "s_visual_p_mean": 0.994,
 "s_frames_p_mean": 0.983,
 "s_static_p_mean": 0.988,
 "tq_abstained_mean": 85.389
}
```
