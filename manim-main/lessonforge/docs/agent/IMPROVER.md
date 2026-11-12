# The improver: Claude Code as the senior guide of the video pipeline

**What it does.** You give it a request ("Class 8, why the area of a circle is πr²"). Claude Code, running
on your Claude subscription, then:

1. makes the video with the pipeline as it is (`lessonforge harness`, the cheap model routing);
2. looks inside every stage: the brief, the teaching card, the script and what the critic said, the
   animations, the drawing plan and the hand's marks, the voice and its timing, the render, the checks,
   and the frames themselves next to what the narrator is saying at that second;
3. finds which stage CAUSES each problem, the line of code it comes from, and whether other lessons
   have it too;
4. changes the system in one place, adds a test, runs the test suites;
5. makes the same video again and compares before and after; keeps the change only if it is better;
6. writes a plain report and leaves the change on a git branch for you to review.

It never pushes, never restarts the live server, never edits `.env`, never changes which models the
pipeline uses (cheap models stay; quality comes from the harness), and works in its own copy of the
code so a lesson a tester is making is never touched. The lessons it makes go into a workspace of its
own, so they never appear in the app's list (where a failed one would carry a "Try again" button that
spends your money).

**Where the money goes.** Two separate bills:
- Claude Code itself (the thinking, the code reading, looking at frames, writing fixes) uses your
  **Claude plan**. Nothing per token; it is limited by the plan's usage limits.
- Each video it makes calls the pipeline's own models through **OpenRouter**, on the same ledger and
  cap as the live server (its own workspace, the live ledger): about 0.10 to 0.15 USD a lesson on the
  cheap routing. One request makes 1 to 3 lessons, capped by `IMPROVER_MAX_USD` (default 1.00 USD).

## Files

| file | what it is |
|---|---|
| `.claude/skills/make-best-video/SKILL.md` | the main loop: `/make-best-video <request>` |
| `.claude/skills/inspect-lesson/SKILL.md` | look only: `/inspect-lesson <job id>` (spends nothing) |
| `.claude/agents/frame-reviewer.md` | looks at every beat's frames beside the words; scores 0 to 3 |
| `.claude/agents/stage-auditor.md` | reads one group of stages and the code; finds the cause and one lever |
| `.claude/settings.json` | what Claude Code may run here without asking, and what it may never run (not a sandbox: see the last section) |
| `scripts/agent/dossier.py` | one lesson's evidence, stage by stage, plus frame sheets (no model, no spend) |
| `scripts/agent/compare.py` | before/after table and a KEEP / REVERT / UNSURE call |
| `scripts/agent/survey.py` | the same numbers across recent lessons: one lesson's fault or the system's? |
| `scripts/agent/preflight.sh` | the checks before anything is spent |
| `scripts/agent/improve.sh` | setup, one request, an inbox queue, or an interactive session |

## Install on the server (once)

These steps assume the live server already runs from a checkout of this repository with its venv
(`lessonforge/.venv`) and its `.env`, as in CLAUDE.md "Environment gotchas".

1. **Get the improver files.** Merge this branch, or `git fetch && git switch <this branch>` in the
   live checkout. (The improver later works in its own copy; this only brings the scripts.)

2. **Install Claude Code** (needs Node 18 or newer):
   ```bash
   npm install -g @anthropic-ai/claude-code
   claude --version
   ```

3. **Log in with your Claude Pro account** (once per server user):
   ```bash
   claude          # then type /login and follow the link; choose your Claude.ai account, not an API key
   ```
   Do not set `ANTHROPIC_API_KEY` in this user's environment: when it is set, Claude Code bills the API
   key instead of your plan.

4. **Tell the improver where things are:**
   ```bash
   cd ~/manim/lessonforge                      # your live checkout
   cp scripts/agent/improver.env.example scripts/agent/improver.env
   nano scripts/agent/improver.env             # set LIVE_REPO, WORKTREE, VENV, LIVE_HOME
   ```
   `LIVE_HOME` is the live server's workspace (the one with `spend.jsonl` and `lessons/`). The improver
   never makes a lesson there: it makes them in its own workspace, `IMPROVER_HOME` (default
   `$LIVE_HOME/improver/home`), whose `library` and `cache` are links to the live ones. So its lessons
   never enter the app's list, while teaching cards, drawings, the concept knowledge base, the speech
   cache and the stage store are shared (nothing is paid twice), and its spending goes on your ledger
   (`OPENROUTER_LEDGER`, default `$LIVE_HOME/spend.jsonl`) and under your cap. An `improver.env` from
   before 2026-10-15 that sets `LESSONFORGE_HOME` to the live workspace still works: it is read as `LIVE_HOME`.

5. **Make its own checkout and workspace:**
   ```bash
   scripts/agent/improve.sh setup
   ```
   This creates a git worktree next to your checkout (default `~/manim-improver`) and the improver's
   workspace with its two links, and runs the preflight. It must end with "setup is fine". No `.env` is
   put in the improver's checkout (a link left by an older setup is removed): each run reads your live
   `.env` into its own environment, so the pipeline has the keys and no key file sits in the folder
   Claude Code works in.

6. **Trust the folder once** (Claude Code ignores the project's permission list until you do):
   ```bash
   scripts/agent/improve.sh shell              # answer "Yes, I trust this folder", then type /exit
   ```

## Use it

**One request, hands off:**
```bash
scripts/agent/improve.sh run "Class 8 students, Hinglish, 3 minutes: why friction slows a rolling ball"
```
It prints where to follow along (`tail -f …/improver/logs/<time>-run.log`). When it ends, read
`$LIVE_HOME/improver/<time>/REPORT.md`; the lessons it made are in `$IMPROVER_HOME/lessons/`, not in the
app. The improved code is on a branch named
`improver/<date>-<topic>` in the improver checkout: review it with `git log -p` there, and merge it
yourself when you agree. The live server uses a change only after you merge it and restart it (CLAUDE.md:
never while a lesson is being made).

A brief file or your own script works too:
```bash
scripts/agent/improve.sh run /path/to/brief.json
scripts/agent/improve.sh run /path/to/my_script.txt      # your words are kept as written
```

**Talk to it while it works** (recommended the first few times):
```bash
scripts/agent/improve.sh shell
> /make-best-video Class 10, how a convex lens forms an image
> /inspect-lesson 20261012-191635-3ac7d0
> why is beat 04 so empty? look at the drawing plan
```

**Look only, spend nothing** (a job id is looked up in the improver's workspace, then in the app's list):
```bash
scripts/agent/improve.sh inspect 20261012-191635-3ac7d0 20261014-101500-abc123
```

**A queue, e.g. overnight.** Put one request per file in `$LIVE_HOME/improver/inbox/`
(`.txt` with the request in words, a `.json` brief, or a `.txt` script starting with `#`), then:
```bash
crontab -e
# every night at 1:00
0 1 * * *  /home/you/manim/lessonforge/scripts/agent/improve.sh queue >> /home/you/improver-cron.log 2>&1
```
Finished requests move to `inbox/done/`, failed ones to `inbox/failed/`. When the plan's usage limit is
reached the queue stops and the rest wait for the next night.

## Settings (`scripts/agent/improver.env`)

| setting | default | meaning |
|---|---|---|
| `LIVE_HOME` | `$LIVE_REPO/lessonforge/lessonforge_workspace` | the live server's workspace: the app's list, the ledger, the library, the caches; reports, logs and the inbox go under its `improver/` |
| `IMPROVER_HOME` | `$LIVE_HOME/improver/home` | the improver's own workspace, where its lessons go; `library` and `cache` link to the live ones |
| `IMPROVER_MAX_USD` | 1.00 | most OpenRouter money one request may spend on lessons |
| `IMPROVER_ROUNDS` | 2 | most fix-and-remake rounds per request |
| `CLAUDE_MODEL` | sonnet | the model Claude Code itself uses. `sonnet` stretches the Pro limits further; `opus` reasons better on hard bugs but uses the limit faster |
| `MAX_TURNS` | 200 | safety stop for one headless run |
| `BASE_BRANCH` | main | each request starts from the latest of this branch |

## Rules (the skill reads these)

- **Its own checkout only.** `preflight.sh` refuses the main checkout and checks that `lessonforge` is
  imported from the improver's copy. Render code is read live by a running job; an edit in the live
  checkout would reach a tester's lesson mid-render.
- **Its own workspace, the live ledger.** Lessons are made in the improver's workspace, never in the app's
  list (the owner's rule: test lessons never enter it). Its `library` and `cache` are links to the live
  ones, so cards, drawings, the concept base, speech and the stage store are shared and nothing is paid
  twice; `OPENROUTER_LEDGER` is the live ledger, so the spending is on the owner's ledger and under the
  live cap (CLAUDE.md 2026-10-10, "How to run the whole pipeline without touching the live server").
  `preflight.sh` refuses the live workspace, a workspace whose `library` or `cache` is not a link to the
  live one, and a ledger inside the improver's workspace. A lesson in the app's list may be inspected
  (`dossier.py` and `survey.py` read both), never made or removed there.
- **Never:** `git push`, merge, restart or stop the server, `scripts/public_link.sh`, `lessonforge budget`,
  read, print or edit `.env` or a key, kill processes, delete lessons. `.claude/settings.json` denies the
  plain commands for these (and has no `find`, whose `-exec` runs anything).
- **Models stay as they are.** No model swaps, no model-chain edits, no "use a better model" fixes. The
  owner's rule (CLAUDE.md, 2026-10-12): quality comes from the harness on cheap models.
- **One lever per experiment**, a test that pins it, both test suites green, and the first video kept.
  A change is kept only when `compare.py` and a look at the targeted beats agree it is better.
- **Upstream first**: script → visuals → layout/render → repair. Fix where the fault is caused.
- **Write down what was tried and left**, in the report and, when general, in CLAUDE.md or the roadmap.

## What it cannot do (yet)

- **Its permission list is not a sandbox.** The keys are in the environment of every command it runs
  (the pipeline needs them), and it may write files and run `python -m pytest` and `scripts/agent/*`:
  a test file or a script it writes can run any Python, read any file this user can read and print any
  variable. `.claude/settings.json` stops the plain commands (`cat .env`, `grep … .env`, `find -exec`, `git
  push`, `kill`), and a `grep` whose pattern contains `.env` (such as `os.environ`) is refused with them
  (Claude Code's own search tool still works). What keeps it safe is its own checkout, its own workspace,
  the rules above and a person reviewing the branch: run it only as a user whose files you would let it read.
- It does not listen to the audio. The frame reviewer reads what is said from the timeline, not the
  sound; voice quality still needs a person.
- A model's output varies run to run, so one before/after pair is weak evidence for a change upstream
  of the script. For those, run the writer's eval (`scripts/eval_writer.py`, about 2 USD) before merging.
- `CLAUDE.md` is about 275 KB and Claude Code loads it at the start of every session. That is a large
  share of a Pro plan's usage on every run. Splitting the dated history into `docs/` and keeping
  CLAUDE.md to the map and the standing rules would make each run several times lighter.
