---
name: make-best-video
description: Make a lesson video from a request, look inside every pipeline stage for why it is not as good as it should be, fix the system (one change at a time, tested), make the video again and keep the change only if it is measurably better. Use when asked to make, improve or debug a video end to end.
argument-hint: "<what the video should teach, for whom>  (or a path to a brief .json or a script .txt)"
---

# Make the best video: run, inspect, fix the system, prove it

You are the senior engineer and guide for lessonforge. A request comes in; you make the video with the
pipeline as it is, find out stage by stage why it is not as good as it should be, change the SYSTEM so
every later lesson is better, and prove it on this lesson. You fix code, not this one video by hand.

Request: $ARGUMENTS

Read `docs/agent/IMPROVER.md` § "Rules" once if you have not this session. The short version:
never push, never restart or touch the live server, never read or edit `.env` or print a key (the keys
are in your environment for the pipeline, not for you), never make or remove a lesson in the app's list
(yours go to your own workspace), never change the model chains (cheap models; quality comes from the
harness), never skip or weaken a test, one lever per experiment, the first video is never lost.

## 0. Preflight (stop on any failure)

```bash
bash scripts/agent/preflight.sh
```

It checks that you are in the improver's own checkout (not the one the live server runs), that
`lessonforge` imports from this checkout, that the workspace is the improver's own (not the app's; its
library and caches linked to the live ones, the ledger the live one), the toolchain and the money left. It prints
`RUN=<folder>` for this request: everything you write goes there. Read the money line: a lesson on the
cheap routing costs about 0.10 to 0.15 USD; the per-request cap is `IMPROVER_MAX_USD` (default 1.00).
If the room left is under 0.50 USD, make the baseline only and say so in the report.

## 1. The request becomes a brief

- A path to a `.json` brief: use it as is.
- A path to a `.txt` script (the author's own words): use `lessonforge script <file> -o $RUN/baseline`
  in step 2 instead of `harness`. Their words are never rewritten.
- Plain words: write `$RUN/brief.json` with the intake fields: `topic`, `audience` (e.g. "Class 8
  students"), `grade`, `level` (foundation | core | advanced), `goal` (what they can do afterwards),
  `language` (en-IN | hinglish | hi-IN | te-IN | ta-IN; default en-IN), `duration_minutes` (default 3),
  `card: true` (sources and a teaching card first: better grounded, two more cheap calls). Copy the
  shape of `evals/writer/cases/*.json` → `brief`. Do not invent a story setting; "the example serves
  the idea" (CLAUDE.md).

## 2. Baseline video

```bash
lessonforge harness $RUN/brief.json -q m -o $RUN/baseline 2>&1 | tee $RUN/baseline.log
```

It runs in this process with this checkout's code and writes the lesson into the improver's own
workspace (`$LESSONFORGE_HOME/lessons/<job id>/`), never into the app's list; cards, drawings and stages
come from the shared live library and stage store. The job id is in `$RUN/baseline/results.json`. A run takes
several minutes; let it finish. If it fails, the failure IS the first finding: read the log's last lines
and `job.json` → `error`, then go to step 4.

## 3. Look inside every stage

```bash
python scripts/agent/dossier.py <job id> -o $RUN/baseline/dossier
```

Then, IN PARALLEL (one message, three Agent calls):
- `frame-reviewer` on `$RUN/baseline/dossier` (scores every beat from the frames; writes
  `agent_review.json`)
- `stage-auditor` with stage group **words**, the dossier folder and the lesson folder
- `stage-auditor` with stage group **picture and sync**, the dossier folder and the lesson folder
  (tell it to wait for nothing: if `agent_review.json` is not there yet it works from the dossier)

While they work, read `dossier.md` yourself, especially "log lines that say something was skipped".
Something that fell back silently is often the biggest fault.

## 4. Decide: one lever

Put every finding in one table in `$RUN/findings.md`: symptom (what a learner sees or hears), beat,
stage that CAUSES it, evidence, systemic (N of M lessons, from `survey.py`), already tried (CLAUDE.md /
roadmap), proposed lever. Then choose ONE, in this order of preference:

1. A failure or a silent fallback (a stage skipped, a voice degraded, animations refused).
2. Something a learner would notice that recurs across lessons (`survey.py --grep`).
3. Upstream before downstream: a script that asks for too much before a layout rule.
4. Code before prompt; a prompt change only where a model owns the content.
5. Small: one module, a test can pin it.

Do not pick: a model swap or model-chain edit; anything CLAUDE.md records as tried and left (unless
you can say what changed); a change to the live server, its client, `.env` or the budget; re-timing
speech; editing a lesson's files by hand to make this one video look better.

If the best finding needs the owner's decision (a dearer model, a different kind of video, a design
choice), write it down for the report and choose the next one.

## 5. Change the system (on a branch)

```bash
git switch -c improver/$(date +%Y%m%d-%H%M)-<short-slug>
```

- Read the module, its docstring and the CLAUDE.md section that names it BEFORE editing. The comments
  record why each rule exists; do not undo one.
- Make the change. Add or extend a test that fails without it (real inputs, model stubbed; see
  `tests/unit/` for the house style).
- Run, each as its own command (never piped into `tail`, which hides a failure):
  `python -m pytest tests/unit -q`, then `python -m pytest tests/integration -q`.
  All must pass. If an unrelated test was already red before your change, say so in the report.
- Commit locally with a message that says what a learner will see differently.

## 6. Make the video again and compare

```bash
lessonforge harness $RUN/brief.json -q m -o $RUN/after1 2>&1 | tee $RUN/after1.log
python scripts/agent/dossier.py <new job id> -o $RUN/after1/dossier
```

Earlier stages whose code you did not touch are reused from the stage store (nothing paid twice); a
stage whose module you changed runs again by itself. Then run `frame-reviewer` on the new dossier, and:

```bash
python scripts/agent/compare.py $RUN/baseline/dossier $RUN/after1/dossier | tee $RUN/compare1.md
```

- **KEEP**: nothing got worse, the finding you targeted is gone or smaller. Look at the two sheets of
  the beats you targeted yourself (Read the images) before you believe it.
- **REVERT**: something got worse, or the lesson failed. `git revert --no-edit HEAD` (the branch keeps
  the record). Write in the report what was tried and why it was left.
- **UNSURE**: the change did not show on this lesson. Keep it only if its test shows it working and
  the change is small; say so plainly.

A model's output varies from run to run: a frame score that moves by less than 0.3 is noise. When the
words were made again (an upstream change), compare the beats that carry the targeted fault, not the
whole score.

Repeat steps 4 to 6 for the next finding while all of these hold: rounds done < `IMPROVER_ROUNDS`
(default 2), money left in the per-request cap, and the next finding is worth it.

## 7. Write it down (the owner reads this)

`$RUN/REPORT.md`, in plain, short sentences, for a reader who does not read code:

1. The video: path of the best version (`$LESSONFORGE_HOME/lessons/<job>/output/*.mp4`) and its length.
2. What was wrong, stage by stage, in one line each, worst first (from `findings.md`).
3. What was changed in the system, why, and the before/after table from `compare.py`.
4. What was tried and left, and why.
5. What needs the owner (a decision, money, a server restart to make the change live), with a
   recommendation.
6. Cost of this request (`lessonforge spend`, before and after).

Then fold what was learned into the living docs on the same branch, per CLAUDE.md "Operating
discipline": a new symptom → a row in `docs/engine/pipeline-roadmap.md` §4; a rule that a real failure
taught → a short line in CLAUDE.md WITH what taught it; merge into an existing entry rather than adding
a twin. Commit. Do NOT push and do NOT merge: the owner reviews the branch.

Finish by printing the path of `REPORT.md` and its first section.
