# Concept-explainer story benchmark (2026-11-03)

Why: the owner said our lesson stories "jump" and are hard to follow. This measures how a good explainer's story
moves from sentence to sentence, from real YouTube explainers, and holds our lessons to it. No model calls.

## Data (kept outside git: transcripts belong to their channels)

`/mnt/project-files/explainer-bench/` in the project: `corpus/videos/<id>.json` (title, channel, chapters, timed
creator captions), `uploads/` (the owner's Khan Academy transcript exports), `our_videos_text/` (our videos,
transcribed), `results-2026-11-03/`.

| step | script | notes |
|---|---|---|
| topic search | `collect.py topics.txt corpus` | YouTube search per topic, kept only from channels known for clear explaining, 150-1500 s |
| channel harvest | `harvest.py corpus 8` | latest videos of 26 explainer channels |
| user exports | `md2json.py corpus/videos <file.md>...` | "# Video transcript:" exports; no timings, so times are spread by word position |
| our videos | `asr.py ours <mp4>...` / `vtt2json.py` | faster-whisper small.en on CPU, or our own captions.vtt |
| score | `bench.py corpus ours out` | needs `sentence-transformers`, `scikit-learn` |

Only **creator** captions are kept: YouTube's automatic captions have no punctuation, so sentences cannot be found.
About half the search hits are dropped for that. From a cloud machine only the embedded player answers
(`player_client=web_embedded`), one caption track per request.

## Sets

292 explainers, 29 channels (3Blue1Brown, Khan Academy, Veritasium, Professor Dave, TED-Ed, CrashCourse, Steve Mould,
minutephysics, Kurzgesagt, ...), including 68 Khan Academy middle/high school transcripts the owner gave. Split **by
channel** (hash of the name): practice channels (130 videos) set the ranges and train anything learned; held-out
channels (162 videos, Khan Academy among them) are only used to test. Anything that improves lessonforge is tuned on
practice channels; the scramble test and the held-out ranges are the benchmark.

## Measures (`lessonforge.harness.storyflow`)

Per talk: `jump_rate` (sentences sharing no content word with the two before and opening with no link word),
`tie_rate`, `adjacent_similarity` / `neighbour_gain` (sentence-embedding closeness to the previous sentence, and how
much closer than to a random sentence of the same talk), `new_terms_per_100w`, connectives per 100 words (cause,
contrast, sequence, example, recap), questions, sentence length, numbers, you/we, words per minute.

## Scramble test (held-out channels): does a measure notice a broken story?

Each held-out explainer is broken in a known way and the measure must score the real one better.

| measure | 8 steps left out | two blocks swapped | 4 sentences from another talk | shuffled |
|---|---|---|---|---|
| neighbour_gain | 0.74 | 0.94 | 0.96 | 1.00 |
| adjacent_similarity | 0.73 | 0.94 | 1.00 | 1.00 |
| tie_rate (words only) | 0.64 | 0.85 | 0.98 | 1.00 |
| jump_rate (words only) | 0.66 | 0.70 | 0.82 | 0.95 |

Finding the broken SENTENCE is much harder. A finder learned on practice channels (words + embeddings, logistic
regression): AUC 0.70 overall on held-out channels; 0.86 for a sentence from another talk, 0.67 for swapped blocks,
**0.54 for a left-out step** (chance is 0.5). The word-only rule finds 11-23% of planted breaks and flags 8% of the
sentences of real explainers. So lessonforge does not rewrite on it; jumps are listed for a person. A model judge for
"why does this sentence come now?" is the next candidate and must pass this test first.

## Where our videos fall (25 videos: the 2026-11-03 benchmark set, ice, quadrilaterals, chemistry)

| measure | good explainers p10 / p50 / p90 | Khan middle school p50 | ours (median) |
|---|---|---|---|
| neighbour_gain | 0.065 / 0.117 / 0.160 | 0.111 | **0.049** |
| jump_rate | 0.077 / 0.146 / 0.237 | 0.135 | 0.225 |
| mean sentence words | 13.8 / 19.4 / 26.7 | 13.5 | **10.2** |
| "but / however / instead" per 100 words | 0.48 / 0.77 / 1.20 | 0.94 | **0.0** |
| you / we per 100 words | 1.13 / 3.11 / 5.68 | 4.88 | 1.9 |
| numbers per 100 words | 0.45 / 1.71 / 5.37 | 0.77 | **7.18** |
| questions per 100 words | 0.0 / 0.26 / 0.87 | 1.42 | 1.19 |
| words per minute | 127 / 159 / 184 | 184 | **110** |

And lines that say the lesson's plan aloud ("Pause on that.", "Predict before you look.", "Now, you with help.",
"Say it back", "Start with what you know.", "Now the picture."): about 5 per 1,000 words in ours, **0 in 590,000
words** of explainers. That one is exact, so it is a lessonforge finding (`HARNESS_STORY_GATE=1`).

Score any lesson: `lessonforge storyflow <lesson.json | captions.vtt | text.txt>`.

## Script writing: old frameworks vs the story framework (2026-11-03)

Scripts judged blind on one rubric (0-10) by Claude, 4 held-back Class 8 topics (`script_topics.json`, test split).

| Written by | Score |
|---|---|
| lessonforge's writer, `concrete_first` (the foundation default) | 2.75 |
| lessonforge's writer, `story` (new) | 6.0 |
| A bare prompt with the same story shape (no writer rules) | 8.25 |
| A bare prompt listing the old stage titles | 3.5 |

Same model (Haiku 5.5) throughout; the 8 writer lessons cost $0.08. The story framework more than doubles the score
inside the real writer. The gap to the bare prompt (6.0 vs 8.25) is the writer's own rules: the judge's main fixes were
giving the answer away in the opening, and "experiment shows" in place of a reason. `writer_ab.py` reruns it.

### Story first (2026-11-03, later)

Tightening the story stages inside the writer did not help (4.25 against 4.75-5.0 for two runs of the
unchanged framework, same judging; the bare story prompt scored 7.25 in the same batch). So a story lesson's
words now come from that bare prompt (`harness/story_first.py`, knob `HARNESS_STORY_FIRST`, on) and go the
pasted-script route (`scripted.script_lesson`): the words are kept, the screen is designed for them. One run on
Newton's first law: 330 words written, 337 spoken (numbers said as words), 8 beats each with a figure, $0.009.
