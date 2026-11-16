# Noise model

Points are on the 0-100 scale (M9, NVG, D-VGAIN, or raw P(right) x 100).

## Repeat noise (same input twice)

232 questions in 29 identical-input pairs (ours vs autofix (identical frames), repeat r1, repeat r2): 33 moved by more than 0.01, the largest by +46.2 points of P(right).
Repeat noise alone puts 95% of version differences within ±7.2 M9 points on one topic and ±1.9 on the mean of all topics.

## Comparisons

| | Question | n | Mean | 95% CI (topics, questions) | MDE | p (measurement) | p Holm | p (over topics) | > 0 | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| N1 | NOVEL-12: the base video teaches (M9 > 0, 3 frames vs no video) | 10 | +42.4 | [+6.9, +62.2] | 39.4 | 0.0001 | 0.0004 | 0.00781 | 9/10 | real, and holds over topics |
| N2 | NOVEL-12: the gain is specific (own video − another topic's video, M9) | 10 | +64.4 | [+44.2, +104.9] | 42.7 | 0.0001 | 0.0004 | 0.00195 | 10/10 | real, and holds over topics |
| N3 | NOVEL-12: the dense video teaches (NVG, dense vs no video) | 10 | +14.1 | [-10.9, +28.4] | 28.0 | 0.0499 | n/a | 0.0156 | 9/10 | beyond noise for these videos only (not over topics / not after correction) |
| N4 | NOVEL-12: 3 frames teach more than the dense video (M9 − NVG dense) | 10 | +28.4 | [+0.4, +52.7] | 37.7 | 0.0020 | n/a | 0.0137 | 8/10 | real, and holds over topics |
| L1 | Layout study: Claude-fixed − ours (M9, preregistered) | 10 | +5.1 | [-10.0, +22.9] | 24.2 | 0.2661 | 0.445 | 0.619 | 5/10 | within noise |
| L2 | Layout study: autofix − ours (M9) | 10 | -0.0 | [-1.5, +1.5] | 2.0 | 0.9481 | n/a | 1 | 1/10 | within noise |
| L3 | Layout study: Claude-fixed − ours (M7, dense video + motion bonus) | 10 | +1.5 | [-10.7, +11.4] | 15.5 | 0.6432 | n/a | 0.674 | 6/10 | within noise |
| P1 | MMMC pilot, 3B student: learner − base (M9) | 9 | -23.7 | [-186.2, +27.4] | 160.2 | 0.2226 | 0.445 | 0.727 | 5/9 | within noise |
| P2 | MMMC pilot, 3B student: own − other topic (raw P(right), R9) | 12 | +6.4 | [-0.0, +16.8] | 12.5 | 0.0094 | n/a | 0.0283 | 9/12 | beyond noise for these videos only (not over topics / not after correction) |
| P3 | MMMC pilot, gemma: own − other topic (raw P(right), R9; M9 undefined at the ceiling) | 12 | +13.0 | [+3.5, +25.0] | 15.6 | 0.0001 | n/a | 0.000488 | 12/12 | real, and holds over topics |
| P4 | MMMC pilot, gemma: learner − base (raw P(right), R9) | 12 | +0.1 | [-0.1, +0.4] | 0.3 | 0.4143 | n/a | 0.41 | 6/12 | within noise |

Preregistered layout rule (mean >= +5 and >= 70% of topics ahead): fires now = False; it fires on noise alone in 8.2% of randomisations.

## Per topic (value, item-level p, SD from resampling the questions)

**N1** NOVEL-12: the base video teaches (M9 > 0, 3 frames vs no video)

- Tovan sums: +76.4 (p 0.0082, SD 12.4)
- Krell steps on a grid: +25.8 (p 0.148, SD 20.0)
- Vorn sequences: +42.7 (p 0.53, SD 58.3)
- Glint numbers: +79.2 (p 0.0879, SD 31.2)
- Mirthful triangles: +42.0 (p 0.0981, SD 22.6)
- Sorrel counts of lattice rectangles: -27.9 (p 0.322, SD 41.4)
- Quill distance: +26.9 (p 0.169, SD 18.5)
- Dapple numbers: +45.6 (p 0.26, SD 31.3)
- Orbit words: +61.9 (p 0.102, SD 23.3)
- Vells of 2×2 grids: +51.8 (p 0.108, SD 20.9)

**N2** NOVEL-12: the gain is specific (own video − another topic's video, M9)

- Tovan sums: +83.3 (p 0.0073, SD 17.3)
- Krell steps on a grid: +31.7 (p 0.183, SD 19.5)
- Vorn sequences: +90.7 (p 0.0757, SD 66.1)
- Glint numbers: +106.8 (p 0.0081, SD 28.5)
- Mirthful triangles: +73.6 (p 0.0165, SD 37.1)
- Sorrel counts of lattice rectangles: +43.1 (p 0.23, SD 64.0)
- Quill distance: +27.2 (p 0.0388, SD 16.9)
- Dapple numbers: +58.8 (p 0.155, SD 39.2)
- Orbit words: +67.8 (p 0.0392, SD 21.4)
- Vells of 2×2 grids: +61.5 (p 0.0457, SD 34.4)

**N3** NOVEL-12: the dense video teaches (NVG, dense vs no video)

- Tovan sums: +11.5 (p 0.754, SD 15.0)
- Krell steps on a grid: +18.1 (p 0.294, SD 17.1)
- Vorn sequences: +49.7 (p 0.124, SD 26.2)
- Glint numbers: +15.9 (p 0.63, SD 34.5)
- Mirthful triangles: +17.5 (p 0.676, SD 27.1)
- Sorrel counts of lattice rectangles: -16.0 (p 0.471, SD 29.9)
- Quill distance: +11.6 (p 0.525, SD 16.9)
- Dapple numbers: +7.9 (p 0.797, SD 28.0)
- Orbit words: +19.5 (p 0.224, SD 16.7)
- Vells of 2×2 grids: +4.8 (p 0.76, SD 26.2)

**N4** NOVEL-12: 3 frames teach more than the dense video (M9 − NVG dense)

- Tovan sums: +64.9 (p 0.0067, SD 14.2)
- Krell steps on a grid: +7.7 (p 0.786, SD 29.9)
- Vorn sequences: -7.0 (p 1, SD 54.5)
- Glint numbers: +63.3 (p 0.0683, SD 27.6)
- Mirthful triangles: +24.6 (p 0.536, SD 43.5)
- Sorrel counts of lattice rectangles: -11.9 (p 0.44, SD 17.1)
- Quill distance: +15.2 (p 0.55, SD 21.9)
- Dapple numbers: +37.7 (p 0.188, SD 27.3)
- Orbit words: +42.4 (p 0.067, SD 19.4)
- Vells of 2×2 grids: +47.0 (p 0.114, SD 26.7)

**L1** Layout study: Claude-fixed − ours (M9, preregistered)

- Tovan sums: -10.9 (p 0.208, SD 9.6)
- Krell steps on a grid: +24.2 (p 0.0686, SD 16.1)
- Vorn sequences: -3.1 (p 0.248, SD 1.5)
- Glint numbers: -8.0 (p 0.276, SD 10.0)
- Mirthful triangles: -25.9 (p 0.153, SD 15.8)
- Sorrel counts of lattice rectangles: +62.7 (p 0.0141, SD 18.8)
- Quill distance: +9.1 (p 0.323, SD 7.7)
- Dapple numbers: +2.8 (p 0.629, SD 14.1)
- Orbit words: +3.1 (p 0.783, SD 10.5)
- Vells of 2×2 grids: -2.7 (p 0.548, SD 4.7)

**L2** Layout study: autofix − ours (M9)

- Tovan sums: +0.0 (p 1, SD 0.0)
- Krell steps on a grid: +3.6 (p 0.987, SD 3.8)
- Vorn sequences: +0.0 (p 1, SD 0.0)
- Glint numbers: +0.0 (p 1, SD 0.0)
- Mirthful triangles: +0.0 (p 1, SD 0.0)
- Sorrel counts of lattice rectangles: +0.0 (p 1, SD 0.0)
- Quill distance: +0.0 (p 1, SD 0.0)
- Dapple numbers: -0.4 (p 0.75, SD 0.6)
- Orbit words: -2.4 (p 0.558, SD 3.6)
- Vells of 2×2 grids: -1.0 (p 0.526, SD 1.4)

**L3** Layout study: Claude-fixed − ours (M7, dense video + motion bonus)

- Tovan sums: +10.1 (p 0.328, SD 8.8)
- Krell steps on a grid: -6.6 (p 0.761, SD 20.7)
- Vorn sequences: +10.5 (p 0.0145, SD 4.2)
- Glint numbers: +5.3 (p 0.898, SD 8.4)
- Mirthful triangles: +4.2 (p 0.833, SD 7.7)
- Sorrel counts of lattice rectangles: -19.7 (p 0.0541, SD 20.1)
- Quill distance: -2.5 (p 0.255, SD 2.8)
- Dapple numbers: -7.2 (p 0.669, SD 15.8)
- Orbit words: +1.7 (p 0.923, SD 3.4)
- Vells of 2×2 grids: +18.8 (p 0.0848, SD 14.0)

**P1** MMMC pilot, 3B student: learner − base (M9)

- The inscribed square or rectangle proble: +24.6 (p 0.315, SD 44.6)
- Hamming error correction codes: -72.1 (p 0.0605, SD 14.2)
- Space-filling curves and the relationshi: -4.6 (p 0.941, SD 7.1)
- Uncertainty Principle in the Context of : +4.5 (p 0.314, SD 7.5)
- Holomorphic dynamics and iterated comple: n/a (p n/a, SD 6.0)
- Backpropagation calculus: n/a (p n/a, SD 0.9)
- Error correction codes and Hamming codes: +1.8 (p 0.318, SD 1.1)
- Large Language Models and Transformers i: n/a (p n/a, SD 17.4)
- Interconnections in number theory: π, pr: +77.8 (p 0.693, SD 4.4)
- Higher order derivatives: +7.5 (p 0.561, SD 3.7)
- Sum of normal distributions, Gaussian + : -252.7 (p 0.126, SD 284.3)
- The determinant: +0.0 (p 1, SD 0.0)

**P2** MMMC pilot, 3B student: own − other topic (raw P(right), R9)

- The inscribed square or rectangle proble: +7.0 (p 0.566, SD 11.6)
- Hamming error correction codes: +7.6 (p 0.0627, SD 5.3)
- Space-filling curves and the relationshi: -0.3 (p 1, SD 1.5)
- Uncertainty Principle in the Context of : +0.9 (p 0.938, SD 4.7)
- Holomorphic dynamics and iterated comple: +1.9 (p 0.567, SD 1.9)
- Backpropagation calculus: +2.3 (p 0.0609, SD 1.4)
- Error correction codes and Hamming codes: +1.9 (p 0.0629, SD 0.7)
- Large Language Models and Transformers i: +0.1 (p 0.817, SD 0.5)
- Interconnections in number theory: π, pr: +4.0 (p 0.123, SD 1.9)
- Higher order derivatives: -2.9 (p 0.368, SD 2.4)
- Sum of normal distributions, Gaussian + : +53.7 (p 0.126, SD 12.7)
- The determinant: +0.0 (p 1, SD 0.0)

**P3** MMMC pilot, gemma: own − other topic (raw P(right), R9; M9 undefined at the ceiling)

- The inscribed square or rectangle proble: +51.6 (p 0.0575, SD 10.3)
- Hamming error correction codes: +0.2 (p 1, SD 0.2)
- Space-filling curves and the relationshi: +0.3 (p 0.122, SD 0.3)
- Uncertainty Principle in the Context of : +12.9 (p 0.0591, SD 7.8)
- Holomorphic dynamics and iterated comple: +20.0 (p 0.127, SD 17.6)
- Backpropagation calculus: +10.0 (p 0.0659, SD 9.0)
- Error correction codes and Hamming codes: +10.1 (p 0.318, SD 8.3)
- Large Language Models and Transformers i: +47.4 (p 0.0591, SD 8.9)
- Interconnections in number theory: π, pr: +0.8 (p 0.872, SD 0.7)
- Higher order derivatives: +0.0 (p 1, SD 0.0)
- Sum of normal distributions, Gaussian + : +0.1 (p 1, SD 0.1)
- The determinant: +2.0 (p 0.371, SD 1.7)

**P4** MMMC pilot, gemma: learner − base (raw P(right), R9)

- The inscribed square or rectangle proble: +0.8 (p 0.687, SD 0.8)
- Hamming error correction codes: -0.0 (p 1, SD 0.0)
- Space-filling curves and the relationshi: +0.4 (p 0.748, SD 0.3)
- Uncertainty Principle in the Context of : +0.3 (p 0.5, SD 0.3)
- Holomorphic dynamics and iterated comple: +0.0 (p 1, SD 0.0)
- Backpropagation calculus: -0.0 (p 0.507, SD 0.0)
- Error correction codes and Hamming codes: -0.3 (p 0.88, SD 0.3)
- Large Language Models and Transformers i: +0.0 (p 1, SD 0.0)
- Interconnections in number theory: π, pr: -0.1 (p 0.696, SD 0.1)
- Higher order derivatives: -0.0 (p 1, SD 0.0)
- Sum of normal distributions, Gaussian + : +0.0 (p 0.504, SD 0.0)
- The determinant: -0.1 (p 0.258, SD 0.1)
