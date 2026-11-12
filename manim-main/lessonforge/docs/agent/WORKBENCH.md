# The workbench, the MCP server and the improver

The quadrilateral videos of 2026-10-20 were made by Claude in a chat. It wrote every lesson by hand, looked at
stills, changed the lesson and filmed it again, while lessonforge drew, voiced and assembled the video. The
workbench turns that loop into calls that a program can make.

| Piece | File | Cost |
|---|---|---|
| Workbench: add or draft, check, preview, edit, revert, film, review | `harness/workbench.py` | Only drafting is paid |
| MCP server over the workbench | `mcp_server.py`, `lessonforge mcp [--http]` | Free |
| Improver: Claude over the API makes small, checked edits inside a dollar cap | `harness/improver.py`, `lessonforge improve` | About 0.2 to 0.5 cents a round on Haiku, 4 to 5 cents on Sonnet |
| Frame judge: a vision model judges one frame per spoken sentence, 6 frames per call | `harness/frame_judge.py`, `lessonforge judge-frames` | About 0.65 cents for a 6-minute lesson |
| Loop: film, judge the frames, edit, film again, keep the better film | `harness/loop.py`, `lessonforge loop --cap 0.05 --batch-cap 1` | About 2 cents a lesson |

## Use it from Claude Code

```
pip install -e ".[kokoro,mcp]"          # plus the Kokoro model files in $LESSONFORGE_HOME/models/
claude mcp add lessonforge -- lessonforge mcp
```

Tools: `list_lessons`, `pack_units`, `draft_unit` (paid), `add_lesson`, `get_lesson`, `check_lesson`, `preview`
(returns the contact sheet as an image), `edit_lesson`, `revert`, `lesson_history`, `film`, `review_video`,
`judge_frames` (paid, under a cent).

Filming is free by default: `workbench.film` hides the OpenRouter key from the service, so it pays for no word
alignment and no per-beat vision review. The frame judge does that job per sentence.

## Use it over the API

```
export ANTHROPIC_API_KEY=...            # or OPENROUTER_API_KEY: the same models through OpenRouter
lessonforge improve <lesson-id or lesson.json> --cap 0.10 --rounds 3 [--film]
```

How it keeps cost down:

- Code checks, craft numbers and stills come first, and they are free. A lesson with nothing to fix costs nothing.
- The model answers with a few edits, never the whole lesson. Its fixed instructions are cached by the provider.
- Haiku goes first. It moves to Sonnet only after two rounds with no gain, and only if the cap still allows it.
- Before every call, the next call's cost is estimated from the last one. The run stops when the next call would
  pass `--cap`. Every call goes into the spend ledger.
- The run stops early when a round brings no gain. The best version is kept as the newest.
- Nothing runs on a schedule.

## Edits

```
{"op":"set_beat","beat":"04","fields":{"narration":..,"steps":[..],"figure":{..},"quiz":{..}}}
{"op":"insert_beat","after":"04","beat":{"narration":..,"steps":[..],"figure":{..}}}
{"op":"delete_beat","beat":"04"}
{"op":"set_shape","name":"tri","shape":{"points":{..},"polygon":"ABC","is":["convex"]}}
```

After every edit, the lesson goes through the same checks as a fresh pack draft (`shapes.settle`, then
`pack.structure_issues`). Gaps like `{angle D}` are filled from the points. An edit that brings in a fault is not kept, and
the reply lists the fault.

## What "craft" measures (free, from the script)

- `screen_changes_per_sentence`: steps divided by sentences. The hand-made units score 0.67 to 0.93.
- `beats_with_held_sentences`: beats where 2 or more sentences in a row start no new step, so the screen holds still.
- `beats_same_picture_as_before`: a beat that opens on exactly the picture before it.
- `long_screen_words`: on-screen lines longer than 9 words.

`review` measures the film the same way the 2026-10-21 review measured the hand-made videos: the share of
half-seconds in which the screen changes, the longest still stretch, the share of silence, and words per minute.

## Pilot, 2026-11-07

Unit 3 of the quadrilaterals pack, vision pass share (sentences whose frame goes with the words):

- Pack draft alone: 81.5%.
- One loop pass with Haiku: 90.8%, for 2.1 cents.
- The hand-made lesson, filmed again: 92.3%.

The share of moving time did not rise (43% against 52.5% for the hand-made lesson). Making the picture move with the
voice is engine work, not something edits can fix. The full tables are in the project's
`lessonforge-videos/2026-11-07-workbench-pilot/results.md`.
