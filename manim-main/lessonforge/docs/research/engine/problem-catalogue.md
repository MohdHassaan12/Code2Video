# Problem Catalogue — every open problem, how hard it is, and how to approach it

**Written 2026-08-22.** One entry per open problem in the video engine, stated in general
terms, graded for difficulty, and given a way in. This is the *complete* list — the
research-grade problems and the ordinary-but-unfinished ones together — because the two are
routinely confused, and confusing them is expensive in both directions: hard problems get
attacked with a quick fix, and easy problems get deferred as if they were research.

Companions: [`improvement-timeline.md`](improvement-timeline.md) says *when* and *in what
order*; [`pipeline-roadmap.md`](pipeline-roadmap.md) holds the per-stage evidence; the
[research-problems site](research/problems/index.html) holds the long-form treatment of the
unsolved ones; [`problem-decomposition.md`](problem-decomposition.md) maps the problem
space itself — the transformation chain, who owns each hidden decision, the option space
per stage and the representation ladder — and is where "what is the next version" is
argued from.

---

## 1. How difficulty is graded

Two independent axes. Conflating them is the most common planning error here.

**Difficulty — how much is *unknown*:**

| Tier | Meaning | What the work looks like |
|---|---|---|
| **T1** | The answer is known. | Build it and test it. Risk is schedule, not outcome. |
| **T2** | The shape is known; the answer is not. | Experiments, measurement, a prototype that might be thrown away. |
| **T3** | No known reliable solution anywhere. | A research programme. Success is a better measurement, not a finished feature. |

**Effort — how much *changes*:**  **S** = days · **M** = a couple of weeks · **L** = a month or more.

A T1/L problem (long-form video) is fully understood and still the largest thing on this
list. A T3/S problem (a first pedagogy metric) is cheap to start and may never finish.
**Difficulty tells you the risk; effort tells you the cost. Neither tells you the priority.**

---

## 2. The full list at a glance

Grouped by what the problem is *about*, ordered within each group by how much it blocks
other work.

| # | Problem | Group | Difficulty | Effort |
|---|---|---|---|---|
| 1 | The system can't tell a good video from a bad one | Judgement | T2→T3 | L |
| 2 | Machine visual judgement isn't trustworthy enough to block a release | Judgement | T3 | M |
| 3 | Verification only understands geometry, not meaning | Judgement | T2 | M |
| 4 | Every new visual capability costs verification coverage | Judgement | T2 | M |
| 5 | Things the verifier can't see get quietly destroyed by repair | Judgement | T1 | S |
| 6 | Nothing checks the narration against the source | Content | T2 | M |
| 7 | Nothing checks whether the lesson teaches | Content | T3 | L |
| 8 | The most expensive step has no gate in front of it | Content | T1 | S |
| 9 | Composition intent never reaches the layout engine | Composition | T1 | S |
| 10 | The scene has no structure to lay out | Composition | T2 | L |
| 11 | Frames are unbalanced and under-filled | Composition | T1 | S |
| 12 | Animation is timed against the clock, not the words | Motion | T2 | M |
| 13 | Motion points at things; it doesn't explain them | Motion | T2 | M |
| 14 | Drawings are checked for existence, not for resemblance | Visuals | T2 | M |
| 15 | Self-repair has no theory of when it's stuck | Repair | T2 | M |
| 16 | Repair edits the code instead of the plan | Repair | T2 | L |
| 17 | The system doesn't remember its own fixes | Repair | T2 | S |
| 18 | The system can't say what a video cost | Operations | T1 | M |
| 19 | Nothing survives a crash | Operations | T1 | S |
| 20 | Experiments die silently between stages | Operations | T1 | S |
| 21 | The same decision is made in two places | Operations | T1 | S |
| 22 | Videos are capped at about four minutes | Scale | T1 | L |
| 23 | Batch generation has never been graded on real work | Scale | T1 | S |
| 24 | Projects don't outlive the browser | Product | T1 | M |
| 25 | One small edit re-does the whole video | Product | T1 | M |

---

## 3. Judgement — knowing whether the output is any good

### 1 · The system can't tell a good video from a bad one
**T2→T3 · effort L · this blocks almost everything else**

The engine measures whether text overlaps and whether it fits on screen. It has no measure
of whether the video *works*. So every lever that isn't geometric — how the script is
written, what gets emphasised, how fast it moves, which visual style — is tuned by a person
watching, forming an opinion, and changing something.

**Why it's hard:** a score that correlates with *plausibility* is easy and worse than
nothing, because it will confidently approve a fluent, wrong, boring video. A score that
correlates with *learning* needs learners.

**How to approach it:** don't try to build the real thing. Build the scaffolding first —
decide what a scorecard contains, attach it to every video, and let it be partly empty.
Fill it with the cheap objective parts (geometry, coverage of what was planned, whether the
narration matches the plan) and leave the pedagogical fields explicitly unknown rather than
guessed. Then run the one experiment that matters: does the score move when a human says
quality moved? A metric that disagrees with human judgement on known-good and known-bad
videos is a metric to throw away, and finding that out is the actual deliverable.

---

### 2 · Machine visual judgement isn't trustworthy enough to block a release
**T3 · effort M**

The engine can already look at its own frames with a vision model and describe what's
wrong. It's switched off, because it isn't reliable: in one live run it called every
sampled frame "dead and mostly empty" — and it was sampling at the moments scenes begin,
when frames are legitimately near-empty. That is a sampling bug, not perception, but it
illustrates the real problem: **a reviewer that flags healthy work is worse than no
reviewer**, because everyone learns to ignore it.

**How to approach it:** treat it as a calibration problem, not a capability problem. Fix
the obvious sampling artefacts first, then build a small fixed set of videos with known
faults and known-clean counterparts, and measure the reviewer against it — false alarms
matter more than misses at this stage. Give it a narrow vocabulary of things it's allowed
to report, so its output can be checked. Only after false alarms are rare does it get the
power to reject anything; until then it advises and its findings are recorded, not acted
on.

---

### 3 · Verification only understands geometry, not meaning
**T2 · effort M**

The checker knows where things are. It doesn't know what they mean, so it cannot see that a
diagram is unrelated to the narration, that a label points at the wrong thing, or that the
frame is technically fine and communicates nothing. Its blind spots are also uneven — some
kinds of visual content it skips entirely, which means genuine problems there go
unmeasured.

**How to approach it:** widen coverage before deepening it. The cheapest wins are the
categories currently skipped wholesale — measuring them badly is still better than not at
all, provided the measurement is honest about its own uncertainty. Beyond that, this
problem merges into #1: meaning-level verification is quality scoring under another name.

---

### 4 · Every new visual capability costs verification coverage
**T2 · effort M**

This is the structural version of #3. Camera movement — zooming into a diagram, panning
across a process — is deliberately not implemented, because the checker measures against a
fixed frame and a moving camera would make it report correct content as cut off while
missing genuine clipping. The capability is withheld to keep the verifier honest. The same
trade recurs with every new visual power.

**How to approach it:** make it a rule rather than a case-by-case negotiation — **a new
visual capability ships together with its verifier, or it doesn't ship**. For camera
movement specifically, the way in is to teach the checker the transform and prove it by
planting a known fault and confirming it's still caught. The deeper question — whether
verification can be made independent of what it verifies, by checking pixels rather than
geometry — stays open and is worth a prototype, not a commitment.

---

### 5 · Things the verifier can't see get quietly destroyed by repair
**T1 · effort S · a recurring class, not a one-off**

Whenever the engine improves a video automatically, it accepts the change if the measured
problems went down. Anything the measurement can't see is therefore free to delete: replace
a real photograph with a simple icon, or remove an animation entirely, and the frame is
still perfectly legal and the score improves. This has now happened three separate times
with three different kinds of content, each caught only after a shipped video looked wrong.

**How to approach it:** it's solved in principle — anything the verifier is blind to needs
an explicit rule that it must survive. What keeps failing is discipline: the rule must be
written in the same change that introduces the content, and in *every* place a rewrite can
happen, not the first one. Treat "what can't be seen here?" as a required question whenever
a new kind of visual content is added.

---

## 4. Content — is what it says true, and does it teach

### 6 · Nothing checks the narration against the source
**T2 · effort M**

The engine can now gather and cite source material, and the script-writing stage records
which source each fact came from. Nothing then verifies that the narrated video kept the
fact. An invented number is indistinguishable from a sourced one — in a system whose entire
purpose is teaching facts.

**Why it isn't simply a checker:** a good teacher invents. A fresh analogy, a made-up
worked example with clean numbers, a simplification that isn't literally in the source — all
of these are correct pedagogy and all look identical to fabrication from a checker's
position. The open question is where the line sits, not how to compare strings.

**How to approach it:** start with the half that has no ambiguity — **specific claims**:
numbers, dates, names, formulas. Sample a handful per video, trace each back to a source
chunk, and report the pass rate. Leave everything else unjudged rather than guessing. A
figure like "8 of 10 sampled facts traced" is immediately actionable and doesn't require
answering the philosophical question first.

---

### 7 · Nothing checks whether the lesson teaches
**T3 · effort L**

The strongest statement of the gap comes from the system's own documentation: *a
pedagogically weak learning plan compiles into a pedagogically weak video, flawlessly*.
Admission gates check that a script is complete, well-formed and in the right language.
None checks that it explains anything. A video that never states the law it's about will
pass every gate — and one did.

**How to approach it:** separate what can be checked mechanically from what can't. A
surprising amount is mechanical: does the video ever state the thing it's named after? Is
every term used after it's introduced, not before? Does the ending answer the question the
opening asked? These are lints, they're cheap, and they would have caught the real failure
above. The genuinely open part — whether a lesson *works* for a learner — needs learners,
and should be scoped as a study rather than a feature.

---

### 8 · The most expensive step has no gate in front of it
**T1 · effort S**

Voice synthesis is the dominant per-video cost, and the script goes into it unreviewed. Any
flaw in the narration — awkward phrasing, a term said twice in two languages, a sentence
that will read badly aloud — is paid for in full, and paid for again on every retry.

**How to approach it:** a review pass immediately before synthesis is the cheapest gate
protecting the costliest spend. It also becomes mandatory rather than optional at longer
video lengths, where this cost scales directly with duration.

---

## 5. Composition — arranging a frame that means something

### 9 · Composition intent never reaches the layout engine
**T1 · effort S · the best return on this list**

For every scene, the script-writing stage already describes the intended composition in
words — *"title banner across the top, coordinate grid centred, derivation stacked in a
right-hand column"*. The renderer reads that description, records it in the log, and places
nothing based on it. The intent exists and is discarded.

**How to approach it:** don't interpret free text — that's a much harder problem in
disguise. Define a small closed vocabulary of composition patterns, recognise those and
nothing else, and map each to an arrangement the renderer already knows how to produce.
Anything unrecognised falls back to today's behaviour, so it cannot regress. The layout
mechanism this plugs into already exists; it just has almost nothing in it.

---

### 10 · The scene has no structure to lay out
**T2 · effort L**

A scene is a flat collection of things with positions. It can now say that one thing
connects two others, or sits inside another — real progress, and enough to draw a tree
correctly. What it still can't express is the frame as a whole: this row, that column, these
two things are a pair, this group balances that one. So arrangement happens by claiming
regions one at a time, which prevents collisions and cannot produce a composition.

**How to approach it:** this is where a real design decision is owed, and the options
differ enough to be worth prototyping rather than debating — richer layout primitives
(rows, columns, groups) versus a constraint solver that's given goals and finds an
arrangement. Prototype behind a switch, on a fixed set of scenes, and judge it on the
measurements from #11 rather than on a screenshot. Expect to throw one away.

---

### 11 · Frames are unbalanced and under-filled
**T1 · effort S**

Content collects in the upper portion of the frame; scenes with little content leave the
bottom half empty rather than centring what they have. It's visible in shipped videos and
is currently an opinion rather than a number.

**How to approach it:** make it a number first — a simple measure of where the visual weight
sits in each frame, logged for every render. Then the fix is mechanical and the metric says
whether it worked. This measurement is also the yardstick for #10, which is why it comes
first despite being smaller.

---

## 6. Motion — making things move meaningfully and in time

### 12 · Animation is timed against the clock, not the words
**T2 · effort M**

Things appear at fixed fractions of the way through a narration beat, rather than at the
moment the narrator names them. The mismatch is small per event and constant throughout,
and it's the difference between a video that feels explained and one that feels
accompanied.

**How to approach it:** a middle path already exists in the toolchain and is unused —
marking positions inside the narration text and having animation wait for them. It gives
element-level timing without splitting the audio, so nothing about cost or caching changes.
The genuinely hard remainder is word-level alignment for **Hinglish** narration that
switches language mid-sentence, where the tooling that works for English doesn't; that part
stays research.

---

### 13 · Motion points at things; it doesn't explain them
**T2 · effort M**

Idle time in a beat is now filled with gestures — a nudge, a pulse, a lift — so the frame
is never frozen. But the gesture vocabulary is deliberately small and content-blind: it
points at things, it doesn't demonstrate them. Real explanatory motion — a vector actually
sweeping, a graph tracing along its curve, a quantity counting up — requires the script to
say *what should move and why*, and in practice scripts almost never do.

**How to approach it:** this is partly solved from an unexpected direction — the engine can
now generate genuinely animated systems as first-class visual elements, so "a projectile
flying" is a real animation rather than a picture of one. What remains is the ordinary case:
existing elements moving to make a point. That needs the intent to be produced reliably
upstream, which is a prompting-and-measurement problem, not a rendering one. Measure how
often expressive motion is requested at all before trying to render it better.

---

## 7. Visuals — the drawings themselves

### 14 · Drawings are checked for existence, not for resemblance
**T2 · effort M**

The engine now draws its own objects rather than fetching clipart, which was a large jump in
quality. Each drawing is verified to actually draw something, to have enough parts to be
more than a placeholder, and to stay inside its allotted space. Nothing checks that it looks
like the thing it's supposed to be. This is the same blind spot the previous clipart system
had — a library that always returns its closest match never says "no", so a request for a
grandfather clock quietly becomes a clock face.

**How to approach it:** resemblance judgement is the same capability as #2 pointed at a
smaller target, and it inherits the same calibration problem — with one advantage: a
drawing has a known intended subject, so the question is narrow and checkable ("is this a
grandfather clock?") rather than open-ended. That makes it a good first testbed for machine
visual judgement generally, and worth doing *before* trusting that judgement on whole
frames.

---

## 8. Repair — improving without breaking

### 15 · Self-repair has no theory of when it's stuck
**T2 · effort M**

When the engine finds problems in a rendered video it asks a model to fix them, re-renders,
and keeps whichever version is better. This is safe — nothing gets worse — but it's blind
descent: there's no notion of whether another round would help. Some videos ship with
problems that survived four rounds of attention.

**How to approach it:** before theorising, classify. Take the videos that shipped with
unresolved problems and sort what remained by kind. Almost certainly they cluster, and
almost certainly some kinds are not fixable by the mechanism being used — which converts an
open-ended loop into a small set of named cases, some of which belong upstream entirely. It
costs nothing but reading.

---

### 16 · Repair edits the code instead of the plan
**T2 · effort L**

The repair step is the one place in the system where a model edits the rendering code
directly — against this system's own organising principle that structure belongs to code
and content belongs to models. It patches the symptom in the output rather than fixing the
arrangement that produced it.

**How to approach it:** repairing the *plan* and re-deriving the output is the version
consistent with the rest of the design, and it composes with #9 and #10 — a layout that can
be described can be re-solved. It's a large change and should follow the classification in
#15, which will say how much of the repair traffic it would actually cover.

---

### 17 · The system doesn't remember its own fixes
**T2 · effort S to start**

A store of past errors and their fixes is fully built, on both the writing and reading side,
and switched off. Every fix is re-derived from scratch, every time, at full cost. Meanwhile
a substantial archive of past failures sits unused on disk.

**How to approach it:** the first move is nearly free — switch it on in isolation and
measure whether remembered fixes actually apply. The open part is safety: a memory of fixes
propagates a wrong fix silently and permanently, so only fixes that *stayed* verified may be
remembered. Design that rule before switching it on anywhere real, not after.

---

## 9. Operations — knowing what happened and what it cost

### 18 · The system can't say what a video cost
**T1 · effort M · blocks more decisions than it looks like**

There is no cost tracking. Not partial — none. This is why several of the engine's best
capabilities are switched off by default: nobody can price them, so nobody can justify
turning them on. It also means "is this experiment worth running twice?" is unanswerable.

**How to approach it:** the lesson-side of the product already has a working cost ledger; the
video engine simply doesn't report anything back into it. This is plumbing, not design. Two
rules from prior art are worth adopting verbatim: a re-run that hits a cache is **not free**
— record what it would have cost — and unknown cost must display as *unknown*, never as
zero.

---

### 19 · Nothing survives a crash
**T1 · effort S**

What's currently running lives in memory and dies with the process. Work products scatter
across several directories with no per-video home. A model call with no time limit can leave
a job apparently running forever.

**How to approach it:** persist the job list, define one vocabulary for what a job's state
can be, mark long-running jobs as stale rather than silently retrying them, and give every
run a single folder holding everything it produced. That folder is also what makes
resumption possible, and it's the same folder that saved projects and chapterised long-form
videos both need — one piece of plumbing, three capabilities.

---

### 20 · Experiments die silently between stages
**T1 · effort S · the reason other work gets misjudged**

Several settings that change output can't be reached from the tools people actually use —
they require restarting the server with different configuration, which means A/B comparisons
mostly don't happen. Worse, some settings that change what gets generated aren't part of
what identifies a cached result, so changing one and re-running quietly serves the *old*
output. A fix then appears not to work, and gets blamed.

**How to approach it:** make every setting that changes output reachable per job, and make
every setting that changes output part of the cache's identity. Both are small. This has
already caused at least one multi-hour misdiagnosis, and it silently degrades the quality of
every conclusion drawn about every other problem on this list.

---

### 21 · The same decision is made in two places
**T1 · effort S · a discipline, not a task**

Recurring failure shape: two parts of the system both decide the same quantity — how long a
video should be, how many things can be on screen, what the language rules are — and the
upstream one silently wins. Tuning the visible one does nothing. This has happened with
video length, with layout rules, and with per-scene limits.

**How to approach it:** it isn't a project, it's a habit: before tuning anything, look for
the twin. When one is found, merge rather than align them — two things that agree today
drift tomorrow. Worth stating explicitly because it keeps recurring after being fixed each
time.

---

## 10. Scale

### 22 · Videos are capped at about four minutes
**T1 · effort L · fully understood, still the biggest item here**

The engine is a ninety-second-to-two-minute machine by construction, with roughly four
minutes as the hard ceiling. A full lesson is ten to fifteen. This is a tenfold scale-up.

**Why the difficulty is T1 anyway:** the design is settled — don't stretch, chapterise. A
long video becomes a sequence of chapters, each a properly-structured short video with its
own arc, threaded by a running summary so terminology and examples stay consistent. Every
existing quality gate then applies per chapter unchanged, and a fault in chapter five
re-makes chapter five.

**How to approach it:** treat the prerequisites as part of the work, not as blockers — cost
accounting (#18), durable per-run artifacts (#19), a gate before voice synthesis (#8), and
parallel repair (#15) are all things that become mandatory rather than nice at ten times the
length. Then do one full lesson end to end and grade where it actually breaks, rather than
predicting.

---

### 23 · Batch generation has never been graded on real work
**T1 · effort S**

Generating many videos from a list works, is resumable, and re-costs nothing on resume — and
has been verified almost entirely against a stubbed system. One real run exists on disk. The
repeated lesson in this project is that composition faults only appear on real runs.

**How to approach it:** run it for real on a meaningful list and grade it the way earlier
audits were graded — one run, watched end to end, with what broke written down. Cheap, and
it either confirms the capability or finds the thing that would have embarrassed it later.

---

## 11. Product

### 24 · Projects don't outlive the browser
**T1 · effort M**

The editor covers the whole loop — brief, script, per-scene editing, render, progress — and
saves projects in browser storage. Close the tab on the wrong day and the work is gone. It
also can't be handed to anyone or opened on another machine.

**How to approach it:** server-side projects, built on the same per-run folder as #19 rather
than as a separate store. There's also a safety gap worth closing at the same time: scripts
edited by hand currently skip the validation that generated scripts pass, so a person can
produce something the generator wouldn't be allowed to.

---

### 25 · One small edit re-does the whole video
**T1 · effort M**

Changing one sentence in one scene currently re-renders everything. Voice synthesis is
cached so unchanged narration isn't re-paid, but every scene is re-drawn. It makes iteration
feel expensive even when it mostly isn't, which discourages exactly the fine-tuning the
editor exists to enable.

**How to approach it:** re-render the changed scene and re-join, keeping the individual
scene pieces instead of discarding them after assembly. The machinery to render scenes
independently already exists and is used; what's missing is keeping the results and
reassembling.

---

## 12. How to approach any of them — the house method

These aren't preferences; each was learned by getting it wrong here.

1. **Measure before fixing.** Nearly every problem above was invisible until something
   counted it. If a problem can't be stated as a number, the first deliverable is the
   number — not the fix.
2. **Attribute upstream first.** Follow the chain — script, then code, then render, then
   repair — and fix it at the earliest stage that could have prevented it. Fixing a
   downstream symptom guarantees the upstream cause returns wearing a different hat.
3. **One lever per experiment.** Two changes at once produce an unattributable result, which
   is the same as no result at a higher cost.
4. **Structure belongs to code; content belongs to models.** Any fix that solves a layout or
   timing problem by rewording an instruction to a model is temporary. The prompt is advice;
   code is a contract.
5. **An automated improvement pass improves or stands aside — it never destroys.** Every
   automatic change is a candidate, accepted only if measurably better, with the previous
   version kept until it is.
6. **A health measure must read zero on a healthy run.** A signal that always fires is not a
   signal. Check every new measure against a known-good run before trusting it.
7. **Verify by watching, not by reading the plan.** The recent failures all looked correct
   in the data and wrong on screen.
8. **Pin every real failure as a test.** The failures worth the most are the ones that
   already happened; the only way to bank them is to make them permanently detectable.

---

## 13. What is *not* on this list

Kept deliberately empty of: bugs with known fixes and no interesting content (they're fixed
as found, not tracked here); features with a build plan and no open question (those are
milestones in [`improvement-timeline.md`](improvement-timeline.md)); and paused workstreams
outside the video engine. If a problem here becomes merely a build task, it moves to the
timeline. If it turns out to be harder than graded, its tier moves up and the reason gets
written down — the grades are earned from real runs, never assumed.
