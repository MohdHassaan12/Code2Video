# Deep Storyboard — sources → screens → specialist writers → simulations

**Status:** v1 shipped 2026-08-15, flag-gated (`DEEP_STORYBOARD=1` for the front half,
`SIM_GEN=1`/default-on for simulations). Harnesses: `test_deep_storyboard.py` (67),
`test_simulation.py` (66, includes a real Manim render). Roadmap stages §A, §B, §D.

The request behind it: *"the gen video has less content and not good flow… it should
work similar to NotebookLM — one scene ideator agent, storyboard, input the YouTube
transcript / search, then we make screens (what each screen contains), then define
tasks to multiple agents to generate a full detailed storyboard screen-wise, each
screen can contain static text, images and dynamic simulation-like animation… then an
agent generates pseudocode, and the final agent needs Manim context."*

---

## 1. What was actually wrong

The complaint was two symptoms with two different causes, and it is worth separating
them because only one of them is a prompt problem.

**Thin scenes.** The entire board — narrative spine, every scene, every element, every
cue, in the target language — came out of **one** LLM call. One call has one token
budget; spread across six scenes, a model writes the first scene properly and sketches
the rest. Worse, nothing anywhere *stated* how much a scene was supposed to contain, so
"thin" was unmeasurable. You could only watch the video and feel it.

**No dynamic content.** The transpiler's IR describes a **composition**: things that
appear, sit, move next to each other, and leave. It has no way to say *this system
evolves*. Every projectile, wave, orbit and pendulum therefore became a still picture
of a moving thing. Prompt-tuning cannot fix this — the vocabulary does not exist. (The
2026-08-14 census makes the same point from the other side: across three live boards
the model wrote 92 `show`, 42 `hide`, 6 `highlight` and **zero** transform/move_to.)

---

## 2. The pipeline

```
 brief + sources (YouTube / URLs / pasted notes / optional search)
        │
        ▼
 app/sources.py ─────────► ResearchPack        chunked, tagged [S2#1], content-hashed
        │
        ▼
 pipeline/screens.py ────► ScreenPlan          per screen: role, beat, visual_kind,
        │                                       must_show[], must_say[+cite], carries
        ▼
 pipeline/scene_writers.py                     ONE LLM CALL PER SCREEN, in parallel
        │  ├─ writer 1 ─┐
        │  ├─ writer 2 ─┼──► N StoryboardScenes ──► _discipline() ──┐
        │  └─ writer N ─┘                                            │
        ▼                                                            ▼
 pipeline/deep_storyboard.py ────────────────────────────► one StoryboardResponse board
        │
        ▼
 (unchanged from here down) shape+language gate → cache → agent registry
   (visual_director, motion_director) → transpiler → render → probe → repair
```

Plus, orthogonally, one new element type:

```
 element {type: "simulation", content: "<one sentence describing the system>"}
        │
        ▼
 app/manim_context.py ──► installed-Manim API index + curated build/animate patterns
        │
        ▼
 app/sim_gen.py ────────► LLM writes build(w,h) + animate(group, run_time)
        │                 → safety gate → VERIFY by stepping the animation
        │                 → cache as a module → element content := absolute path
        ▼
 transpiler emits  simulation(path, 6.0, 4.0)  and  sim_play(var, run_time=…)
```

---

## 3. The decisions, and what was rejected

### 3.1 Fan out on the INPUT, never the output

The obvious reading of "multiple agents work on specific tasks" is to give each agent a
slice of *video* and stitch the clips. This repo already rejected that once
(`app/pipeline/registry.py`): splitting the output puts the seams in the artifact,
where they cost the most — mismatched styling, duplicated elements, and a stitcher that
can only cut, never reconcile.

So each writer produces one **scene of IR**, and the deterministic transpiler remains
the sole renderer. The "stitching" is code that cannot disagree with itself.

### 3.2 The screen plan IS the pseudocode

The request asked for a pseudocode stage between the storyboard and the code. That
stage exists — it is just not written in Python, because the thing consuming it is a
deterministic transpiler, not a model.

`must_show` is the pseudocode: one entry per drawable object ("circle labelled 84",
"branch from 84 to 12"), which is the storyboard prompt's rule 4c stated as **data
instead of advice**. Because it is data:

* the scene writer has a contract to satisfy rather than a vibe to match, and
* `screens.coverage()` can compare planned objects against written elements, so "thin"
  becomes a number in the log (`objects planned 22 -> elements written 19`) instead of
  a feeling about a video.

Emitting literal Python pseudocode here would add a translation step whose only
consumer is another model — cost with no verification value.

### 3.3 Model-written Manim exists, but is scoped to ONE element

Handing whole-scene codegen back to an LLM is the move this repo removed on purpose:
it would give up layout-by-construction, zone allocation, split-screen, `connects` /
`inside` structure, theming, `sustain`, per-scene isolation, and the overlap probe's
contract — every one of which exists because the LLM path lost them.

But the *gap* the request identifies is real, so the scope is inverted instead. A model
writes **one bounded function pair for one element**:

```python
def build(width, height) -> Mobject       # the system at t=0, inside a w × h box
def animate(group, run_time) -> Animation # how it evolves; nothing else changes
```

This is the exact shape of `asset_gen`'s `def draw(ax)` and it works for the same
reason: **the harness owns the figure, so the model cannot get the figure wrong.**

### 3.4 Manim context: the installed package, not the web

The question was posed as "docs? 3b1b's GitHub? a search model? MCP?". Three candidates,
one right answer here:

| Option | Why not |
|---|---|
| OpenRouter web-search models (`:online`) | Reads *the internet's* Manim — a decade of ManimGL and 0.x posts whose APIs no longer exist. Unmeterable, uncacheable, non-deterministic: a per-call web spend on every element, with a different answer each time. |
| An MCP docs server | A live dependency. A headless bulk run or a cron job with no MCP session silently loses its context and starts guessing. |
| **Introspecting the installed `manim==0.20.1`** | Free, offline, deterministic, and *authoritative* — it is the exact version whose signatures the generated code must satisfy. |

`app/manim_context.py` builds the index in a subprocess (so the API server never pays
the manim import), caches it as JSON, and retrieves with plain keyword scoring — no
vector DB, no embedding call, no new dependency. Alongside it sits a small curated
corpus of **simulation patterns written against this repo's own contract**, which is
the part an API listing cannot teach: how a physical system becomes `build` + `animate`.

**The honest caveat, which is why the design does not lean harder on context:** what
makes model-written Manim safe here is not how well it was briefed. It is that the code
is *executed and verified* before it can reach a video. Context reduces retries; the
verifier is what makes a failure impossible to ship.

### 3.5 Verification is the load-bearing part

`sim_gen.verify` steps the animation by hand — `begin()` / `interpolate(alpha)` /
`finish()` — with **no renderer at all**. About a second, no ffmpeg, no video. That
cheapness is what makes it affordable to reject and retry rather than ship and hope.
It rejects:

* `build()` that draws nothing (an empty `VGroup` runs perfectly — "exit code 0 proves
  nothing", the blank-icon lesson from `asset_gen`),
* an animation where **nothing moves** (the moving equivalent of a blank icon),
* geometry that **leaves its box** mid-animation — which would manufacture clipped-text
  violations and send the repair agent chasing ghosts (the same round-trip discipline
  `viz_helpers.sustain` follows), and
* anything that raises (the traceback becomes the repair round's brief).

---

## 4. Traps found while building this

* **A cached module has no imports, so it has no namespace.** The generated module
  contains only the two functions — it is told to import nothing, because the
  verification harness supplies `from manim import *`. The first loader used
  `importlib`, which gives a module *empty globals*: `Axes` was undefined, the loader's
  own except-branch caught it, and every simulation silently became a `Text`
  placeholder that looked exactly like a working fallback. Only a real render found it
  (`test_simulation.py` Part F now pins it). Same family as the `viz_helpers.__all__`
  and selective-import traps: the code *looked* right; the environment contract broke it.
* **The repair agent will trade away what the verifier cannot see** — generalized. The
  probe measures a *still frame*, so deleting a `sim_play(...)` line removes all the
  motion while leaving a perfectly legal frame: the cheapest possible way for a repair
  round to "improve" a video. `_repair_preserves_assets` now guards `simulation(` and
  `sim_play(` alongside `fetch_real_image(`. **Every asset the verifier is blind to
  needs its own deterministic preservation guard.**
* **A security violation and a contract violation are not the same rejection.** The
  first live run resolved 1 of 4 simulations; all three failures were trajectory-tracing
  descriptions that reached for `TracedPath`, which the first cut listed next to
  `open(` — so each died with no repair round. Reaching for `open(` is disobedience;
  reaching for `TracedPath` is the obvious way to trace a path in Manim that happens to
  need a Scene. Two tiers now: `_unsafe_code` (never retried) and `_contract_problem`
  (rejected *with a brief* naming the fix). **1/4 → 3/4** on the same descriptions.
* **A metric that stops at the IR will lie about the video.** `coverage()` reported full
  delivery of 46 elements while the frames showed a clipped placeholder and bare
  circles — every image had degraded (Wikimedia was 429-ing every download for want of a
  contact in the User-Agent) and 3 of 4 simulations with them.
  `_log_element_survival` now prints what *survived codegen*, and shouts when a whole
  type resolves 0/N. Quiet degradation is right for one bad asset and misleading for a
  tier being down.
* **A prompt change is a content change, so it partitions the cache.** The deep path
  carries `DEEP_VERSION` as a cache-key *variant*, appended only when set — so turning
  the feature off returns the exact keys, and therefore the exact cached boards, that
  existed before it.
* **Two stages encoding one rule is a twin.** The language contract used to live inside
  the single-call prompt's f-string. A per-screen writer with its own copy would ship
  half a video in the wrong language on the next persona fix, so it was extracted to
  `storyboard.language_rules()` and both stages call it. Pinned by a source-level check.

---

## 5. Cost

| | Before | Deep path |
|---|---|---|
| Storyboard | 1 call | 1 (ideator) + N (writers, parallel) |
| Simulations | — | 1 call + ~1s verification per *distinct description*, cached forever |
| Cache hit | free | free (source digest + `DEEP_VERSION` in the key) |

`DEEP_STORYBOARD` is therefore **off by default**: turning it on is a billing change.
`SIM_GEN` is on by default but only fires for `simulation` elements, which only exist if
a board asks for one.

---

## 5b. Follow-up: Manim draws the objects too (2026-08-15)

After watching the first live video the user asked to *"remove the svg import and let the
content be generated by manim itself"*, then *"remove this shape calling issue and let the
llm gen the code for the obj rather than using fixed shapes"*. Both were right, and the
board showed why: 14 `svg_icon` elements that were all the same keyword (one clipart
basketball, repeated, for a whole explainer) and 14 of 16 `shape` elements named
`"circle"` / `"point"` / `"arrow pointing right"`.

So `svg_icon` and `shape` now go through the same verified `build(width, height)`
contract as simulations — a drawing is a simulation without motion, so one harness
verifies both. `min_parts` is the load-bearing check: a one-circle "drawing" is exactly
the placeholder being replaced. Never drawn: an **edge** (geometry comes from its
endpoints) and a **bare primitive** (no subject to draw; a model with a floor to meet
would invent parts). The upstream half is `SHAPE_CONTENT_RULE` — name the object, not the
primitive — as one constant shared by both prompts, with a counter so it can be judged.

## 6. What is not done yet

1. **The screen plan is not shown in Studio.** It is the most reviewable artifact the
   pipeline produces (a shot list, before any money is spent on writers) and the editor
   should let the user edit it before the fan-out. Roadmap §J.
2. **Coverage is measured, never enforced.** A screen that under-delivers logs a
   warning; nothing regenerates it. Deliberate for now — the same call `narrative_problems`
   made — but a targeted single-screen rewrite is cheap and is the obvious next step.
3. **Citations are collected but not audited.** `must_say[].cite` records where a fact
   came from; nothing yet checks that the narration kept it. The roadmap's §A
   fidelity spot-check (N facts traced back to a chunk, ≥95% pass) is the missing gate.
4. **Simulations are single-shot.** One system per element, played once during its cue.
   A simulation that should evolve across several cues (a wave whose frequency changes
   as the narration explains frequency) needs a `simulation` + event vocabulary.
5. **The overlap probe measures a simulation's final frame only** — the same blind spot
   images have, one dimension over: a system that overlaps a caption *mid-animation*
   goes unmeasured. The box contract limits the damage; it does not remove it.
6. **A degraded simulation becomes a bare circle.** Failure sets `type: "shape"`, whose
   prose head-noun ("a ball …") resolves to `Circle()` — six of them in the first live
   run, semantically empty. It should route to the asset cascade instead.
7. **Simulations are uncapped per scene.** The single-call storyboard prompt says "at
   most ONE per scene"; the per-screen writer prompt does not. One rule, one place.
8. **`web_search` needs a key** (Tavily / Serper / Brave) and is off by default
   (`SOURCE_AUTO_SEARCH=1`). Without one, sources must be supplied explicitly.
