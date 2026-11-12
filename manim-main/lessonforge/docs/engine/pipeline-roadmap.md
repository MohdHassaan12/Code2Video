# Video Pipeline — Structure, Current Level, and Improvement Roadmap

Audited 2026-07-19 by rendering "Distance between two points" through the merged
pipeline and inspecting the actual frames, the generated code, and the render logs —
then comparing each stage against the sibling **Video_Notebook_LM** project
(`/home/manideep/Downloads/Video_Notebook_LM`), whose architecture docs record
lessons we haven't paid for yet. Its rubric language is reused here:
**L0** = missing · **L1** = works sometimes · **L2** = works, rough edges ·
**L3** = production-grade with guardrails.

---

## 0. The pipeline at a glance

```
ce/ (lesson side)                     stem_animation_lab/ (video engine, :5000)
─────────────────                     ──────────────────────────────────────────
videos_build → video_planner    →     /api/generate_storyboard
video_generation → clip_planner            grounding (yt transcript / NCERT)
stem_animation (HTTP client)               planner_agent (PARTS pedagogy)
video_merger (concat + bgm)                storyboard LLM (elements + cues)
        ▲                             /api/generate_code
        │                                  transpiler.py  (deterministic codegen:
        │                                    zones, topo-sort, math_evolution,
        │                                    SVG sanitize, per-scene scripts)
        │                                  Layout QA Critic (LLM rewrite pass)
        │                                  validate_and_repair (syntax+logic)
        │                             /api/compile_video → _run_render_job
        │                                  parallel per-scene render + concat
        │                                  dry-run probe (TTS-stubbed): overlap /
        │                                    clipped / text-over-shape violations
        │                                  LaTeX self-heal (strip MathTex, retry)
        └──────── mp4 ◄──────────          _repair_overlaps (accept-if-better)
                                           sidecar .json → /timeline badges
```

**Engine structure (2026-07-21):** the video engine's former 3995-line `app.py` is now
the stage-aligned **`app/` package** (`config`/`schemas`/`llm`/`rag`/`codegen`/`assets`/
`storyboard`/`codegen_pipeline`/`render`/`jobs`/`api/*`/`pipeline/*`; map in
`app/README.md`, pre-split monolith frozen at `app_legacy.py`). Behavior-preserving —
142 deterministic checks stayed green. `app/pipeline/stages.py` now documents the pipeline
as an explicit stage sequence with a `PipelineStage` protocol; this is the north-star
framing (planner → **visual director** → layout → animation → components → compile →
static-validate → **vision QA** → repair). Since 2026-07-21 the full written form of
that framing is **`docs/architecture/reference-architecture.md`** — the reference
architecture spec (IR ladder, layer contracts + invariants, agent specs, formal
properties, Renderer Backend Contract), with the Storyboard-IR and sidecar contracts
machine-checked by `stem_animation_lab/schemas/*.schema.json` +
`test_ir_contracts.py` (16 checks; `--regen` re-exports after an intentional
`app/schemas.py` change). Architecture/invariant changes land in the spec, the
schema files, and the harness in the same pass. As of 2026-07-21 night ALL ten stages are
implemented: **Visual Director** (§D) and **Vision QA** (§G) shipped as flag-gated
agent stages (`VISUAL_DIRECTOR=1` / `VISION_QA=1`, both `env_overrides`-allowlisted,
default off; harnesses `test_director.py` 24 + `test_vision_qa.py` 19).

---

## 1. Stage-by-stage: what exists, its level, and how to improve it

### A. Content grounding — L2
**Have:** 3-tier context (`storyboard_context.py`): explicit YouTube URL → topic
search transcript → NCERT node text. Reused for both pedagogy and storyboard.
**Gaps:** no citation of which chunk grounded which claim; nothing prevents the
storyboard from inventing numbers/examples not in the source.
**Improve (from NLM project):**
- Adopt **Rule 0: "numbers/names must come from the source, never invent"** as an
  explicit storyboard-prompt rule, and add a *fidelity spot-check* to QA: N facts
  per video traced back to a grounding chunk (their pilot bar: ≥95% pass).
- Their "danger class" applies verbatim to us: *plausible misspellings of technical
  terms inside authoritative-looking visuals* — worth a dedicated critic check.

**Shipped 2026-08-15 — the engine can now gather its own sources (`app/sources.py`).**
Until then grounding was something the engine had to be *given*: `ce/` resolved a
transcript or NCERT chunk and passed `context["grounding_chunks"]`, so anything calling
the lab directly (Studio, `/bulk`, curl) generated from the topic string alone — and a
model asked to explain a topic it was never shown writes the average of everything it
has read about it. Now: YouTube links (transcript), web pages, pasted notes, and an
optional search tier (Tavily/Serper/Brave key, `SOURCE_AUTO_SEARCH=1`) all resolve into
a `ResearchPack` of **numbered, citable chunks** (`[S2#1]`), whose digest is the
cache-freshness signal. Request field `sources: [...]`; inspectable before it is paid
for at `POST /api/research` (no LLM call) and in Studio's brief.
This closes the *first* half of the gap above — chunks are now addressable, so a claim
CAN cite one. `must_say[].cite` (the screen plan, §B-deep) records where each fact came
from. **Still open:** nothing yet audits that the narration kept the cited fact — the
fidelity spot-check (N facts traced back, ≥95% pass) remains unbuilt, and Rule 0 is
stated in the ideator/writer prompts but not enforced. Grade stays L2 until the
spot-check exists.

### B. Pedagogy & storyboard — L2 (07-20: length + truncation fixed; 07-21: language-contract gate added — see §3c; still no full review gate, so not L2.5)
**Have:** PARTS-framework plan (`planner_agent`), storyboard with scenes/elements/
narration cues, visual-richness + accuracy prompt rules (layout_framework v4),
scene-count and cue-density guidance.
**Gaps:** one LLM call, no review gate; no whole-video coherence thread (each scene
stands alone); storyboard is regenerated (re-billed) on every run of the same topic.
**Length under-production — root-caused 2026-07-20 (Dalton's law run), now fixed:**
Asked for a Dalton's-law explainer, the pipeline produced a **23.7s, 1-scene** video
that never stated the law. Attributed upstream-first, and the cause was NOT the
storyboard stage:
- `planner_agent.determine_scene_count` sized the lesson off the **source text's**
  length as if the source were a script to read aloud: a 45-word definition scored
  `45/150*60 = 18s` → `ceil(18/25)` = **1 scene**. The planner returned one 40-word
  scene; the storyboard (1 scene, 2 cues) and the render faithfully followed.
- Meanwhile the storyboard prompt asks for "**4–6 scenes** for a 60–90 second video".
  Two stages of one pipeline gave contradictory length guidance and the upstream one
  silently won. **Lesson worth generalizing: when two stages both encode the same
  quantity, the upstream one is the one that decides — grep for the twin before
  tuning the stage you happened to be looking at.**
- **Fixed** with `MIN_LESSON_SCENES = 4` (aligns the planner with the storyboard
  stage's own stated target): a concept always gets enough beats for hook →
  statement → example → recap however tersely the source is written. Length still
  scales above the floor for longer sources.
- **Incidental bug found and fixed in the same measurement:** the young-learner pace
  check was substring-based, and `"grade 1" in "grade 11"` is True — Grades 10–12
  were narrated at an early-primary 90 wpm. Now `planner_agent.narration_wpm()`
  matches on the grade *number*, and `ce/stem_animation.py` calls it instead of
  carrying its own copy of the same buggy list.
**Truncation is invisible — partly fixed 2026-07-20:** nothing anywhere checked
`finish_reason`, and `loads_json_lenient` runs `json_repair`, which closes a
truncated model response into structurally-valid JSON. A cut-off storyboard
therefore became a *gutted but well-formed* storyboard (scene with zero cues; a cue
ending mid-tag: `"Hey there! [SPEED: SPRINT"`), got cached for 48 h, and rendered as
a 2.9s video with no error in any log. Note the trap: installing the missing
`json_repair` dependency **converted a loud 500 into a silent bad video** — a
lenient parser is a failure-*hiding* device unless something else checks completeness.
Now: `_call_openai_compatible` rejects `finish_reason == "length"` (falls through to
the next model, logging tokens used), and `storyboard_shape_problems()` gates the
cache write so a degenerate storyboard raises instead of poisoning the topic for 48 h.
**Third occurrence of the same class, found + fixed 2026-07-21 night:** the provider
completeness check rejected only `finish_reason == "length"`. A live storyboard call
returned **`finish=error, completion_tokens=0`** and was *accepted* as a success —
partial content that parsed fine and was only caught two stages later by the shape
gate ("scene 3 has no narration cues", hard 500). `_call_openai_compatible` now also
rejects `error` / `content_filter`, so the request falls through to the NEXT model in
the chain instead of burning the whole call. **Generalized rule: any terminal reason
that isn't `stop` means the model didn't finish, however well-formed the JSON looks.**
Pinned in `test_ir_contracts.py` §E.
**Still open:** the same lenient-parse-then-trust pattern applies to every other
`loads_json_lenient` caller (codegen, transliteration) — only the storyboard has a
shape gate. The transliteration length guard checks list *length* but not per-string
integrity, so a truncated single cue passes.
**Improve:**
- **Deck brief + running summary** (their `region_narrator`): generate a one-time
  video brief, update a running summary after each scene, and thread both into every
  scene's generation — kills re-introductions and terminology drift.
- ~~**Storyboard cache** keyed on `sha256(topic+persona+language+style+grade)`~~ —
  **already implemented** (found in the 2026-07-20 code audit, this doc just
  didn't know): `_storyboard_cache_path` app.py:2369-2465 keys on
  topic+persona+language+style+grade+subject+node_type (48 h TTL), or on the
  grounding-chunk sha256 with no TTL when chunks are present; write-back at
  app.py:2727, dir `.storyboard_cache/` (2026-07-22: `tech_terms` joined the key —
  a deliberate one-time invalidation, since the narration-terms policy changes the
  prompt). Still missing from the original idea: a `SCOPE_VERSION` field so a
  prompt fix can selectively invalidate old entries — until then, invalidate by
  hand-bumping the key. **2026-07-30 tuning audit found two more key blind
  spots:** `SCREEN_TEXT_LANG` and `learning_objective` shape the prompt but are
  NOT keyed — flipping either on a cached topic silently serves a board
  generated under the old setting; and the *pedagogical plan* (which carries the
  scene count) isn't keyed either, so planner/prompt tuning is invisible until
  `.storyboard_cache/` is purged. Full post-gen tuning map: `docs/tuning.md`.
- **Narration term double-speak — knob shipped 2026-07-22 (user-reported):** hybrid
  narration said technical terms twice, English then the native translation
  ("point... yaani bindu", "coordinate plane... nirdeshank samtal") — the hybrid
  prompt said "STEM terms stay in Latin script" but never forbade *also*
  translating them. Now a `tech_terms` policy (request field / `VIDEO_TECH_TERMS` /
  videoSpec / dropdowns in lab + bulk + sandbox UIs; default `english`):
  `english` = term spoken in English only, restating FORBIDDEN in the prompt and a
  dedup rule added to the Devanagari→Hinglish transliteration pass; `bilingual` =
  native equivalent once at first mention (deliberate teaching aid); `native` =
  translated throughout. Built as `narration_tech_terms_rule` in `app/storyboard.py`,
  pinned in `test_storyboard_gate.py` (34 checks). **Residual gap:** both layers are
  prompt-side — a model that writes romanized Hinglish directly (skipping the
  transliteration pass) and still double-speaks has no deterministic backstop; if
  that shows up in listens, fold a duplicate-term check into the script-critic gate
  idea in §C rather than adding a new pass.
- **Title-is-a-takeaway** rule: scene headings should state the conclusion
  ("दूरी = कर्ण की लंबाई"), not the topic ("दूरी").
- **Duration contract, code-owned (2026-08-15, from the NLM-pipeline cross-audit;
  user: "vid length issue").** Nothing in the pipeline states a target length:
  screen count is a bare env clamp (`SCREENS_MIN=5`/`SCREENS_MAX=8`,
  `app/pipeline/screens.py:41`), actual length is whatever narration the model
  wrote × TTS, and `ce/stem_animation.py:69` *estimates* duration post-hoc from
  word count — the Dalton lesson above showed what happens when length guidance
  is implicit and split across stages. Proposal (same shape as `must_show`):
  a `target_duration_s` request field → the screen ideator derives screen count
  AND a per-screen narration **word budget** from it (code disposes:
  `words ≈ wpm × seconds-share`, wpm from `planner_agent.narration_wpm`);
  the storyboard gate warns/trims when total narration words land outside ±20%
  of budget (cheapest gate protecting the costliest spend — same argument as
  the script-critic row); the sidecar records `rendered_duration_s` vs target
  and the pipeline logs one `[DURATION]` line per video so drift is a number.
  The NLM pipeline's level-knob lesson applies verbatim: thread it end-to-end
  and verify with an A/B that VARIES the knob, or it will die between stages
  invisibly. **Measured 2026-08-15: the knob already dies at the HTTP
  boundary.** `ce/stem_animation.py:69` computes `spec["duration"]`
  (word count ÷ wpm) but `_generate_storyboard`'s payload sends only
  topic/style/persona/language/tech_terms/context — no duration field — and
  the lab has ZERO duration handling (grep of `app/storyboard.py`,
  `app/schemas.py`, `app/api/generation.py` all empty). Step 1 is plumbing:
  add the field to the request model and thread it to the ideator/prompt.
  Ceiling today is ≈4 min by construction (`ce/planner_agent.py` caps at
  10 scenes × 25s); §6's chapterized design is the path past it.
  **Shipped 2026-08-15** — see priority row 26 for what landed and what remains.
- **Composition as a FIELD, not prose (2026-08-15 cross-audit; user: composition
  issues).** `StoryboardScene.composition` is 1–2 free sentences and the prompt
  *claims* the transpiler consumes it (`app/storyboard.py:595`) — but the
  transpiler only LOGS it (`transpiler.py:1445-1448`); it steers zero layout
  decisions. A documented-but-dead knob, the exact class the NLM level-knob
  audit warns about. Port their `SLIDE_LAYOUT_ARCHETYPES` idea under this
  repo's own "structure is a FIELD, never prose" rule — and the vehicle
  ALREADY EXISTS: `layout_template` is a real enum the transpiler honors via
  `_apply_template_zones` (transpiler.py:1455, both paths), it just has only
  three entries (TitleStageCaption / SplitScreen / FullCanvas), none keyed to
  pedagogical role. Extend THAT vocabulary with role-shaped archetypes
  (hook / mechanism / worked-example / comparison / relationship-graph /
  anatomy / before-after — overlaps `role` + `visual_kind`, reconcile rather
  than triplicate), give each a zone template, and enforce their **variety
  rule** (no archetype >2 consecutive scenes) in code at the screen-plan
  clamp. Extending an honored field is far cheaper than birthing a new one —
  and avoids the twin the merge rule warns about.
  **Shipped 2026-08-15 (first slice)** — ProcessFlow + BeforeAfter + the variety
  rule; see priority row 27 for the remainder. Keep the prose descriptor as human-readable
  intent; the enum is what code acts on. Schema change ⇒
  `test_ir_contracts.py --regen` + commit together.

### C. Narration & TTS — L2 (upgraded 2026-07-19: shared TTS cache shipped)
**Have:** per-cue voiceover blocks; `[SPEED]/[PAUSE]` pacing tags (stripped
correctly for both Sarvam and Gemini paths); provider failover Sarvam → Gemini TTS
via OpenRouter; per-render manim-voiceover cache; **shared content-addressed TTS
cache across renders** (`.tts_cache/` at repo root, gate in
`UniversalTTSService.generate_from_text` — covers Sarvam, the Gemini delegate AND
the fallback; keyed on request intent so a fallback-synthesized clip still
satisfies identical future requests; atomic writes, safe under parallel per-scene
renders; knobs `TTS_SHARED_CACHE` / `TTS_SHARED_CACHE_DISABLE`; pinned by
`test_tts_shared_cache.py`, 16 checks: a repair re-render bills ZERO TTS calls);
**`TTS_MUTE=1` for visuals-only iteration** (2026-08-15, user: "when testing it should
not gen llm based audio as we are working on visuals to save money") — short-circuits the
whole chain to word-count-sized silence, so a layout/visual re-render of the same board
costs **zero** TTS. Measured on the standing "Projectile motion" board: same 6 scenes,
73.9s vs 83.7s (silence at 150 wpm tracks real narration closely enough that beat pacing,
and therefore `sustain` and the layout probe, behave as in production), audio track
present at −91 dB, `voice_muted: true` in the sidecar. **The design constraint worth
remembering: it neither reads nor writes the shared cache.** That cache is keyed on
request intent and does not record which tier answered, so writing silence into it would
make the next REAL render silent — a cost-saving flag turned into a poisoned cache with
no trail back. Pinned explicitly (a real service asking for the same text afterwards must
still synthesize).
**Gaps found in audit:**
1. **No script gate before TTS spend.** Narration goes straight to synthesis; TTS
   is the dominant metered cost (their measurement: ~85% of deck cost).
2. ~~**TTS cache is per-render**~~ — **fixed 2026-07-19** (shared cache above);
   repair rounds no longer re-bill audio.
3. Sync is approximate: entrances play against whole-cue audio. The flat `0.6×`
   was replaced 2026-07-19 by the content-aware `_TIMING` map
   (transpiler.py:122-141, per-el_type fraction + floor, capped at the beat) —
   but the rest of each beat is still dead air until per-element beats land.
   A stale docstring at transpiler.py:698 still advertises the old 0.6 heuristic.
4. **TTS language param describes the persona, not the actual script** (2026-07-21
   Dalton review, §3c): `language="hi-IN"` while the cues were plain English —
   audible pronunciation degradation. Root fix is the stage-B language gate;
   if cues can legitimately be English (persona `en`), the codegen should pass
   the language the script is actually in.
**Failure class observed live 2026-07-21 22:29 — ALL THREE FOLLOW-UPS SHIPPED the
same night.** The OpenRouter audio endpoint went unhealthy (direct probe: HTTP 500;
render path: **HTTP 200 with empty audio content**), one cue's synthesis failed, that
scene died, and the whole parallel render fell back to sequential — double render
time for a seconds-long blip. Shipped:
1. **Retry before failover** — `_tts_post_with_retry` (viz_helpers) retries
   5xx/429/transport-timeouts **and the 200-with-empty-body shape** with linear
   backoff (`TTS_RETRY_ATTEMPTS`=3, `TTS_RETRY_BACKOFF`=1.5), while a 401/400 fails
   fast — retrying a bad key is pure latency.
2. **Keyless last-resort voice** — the chain is now primary → Gemini (keyed) →
   **gTTS (no key)** → silence. gTTS is a different vendor on a different network
   path, so a keyed-provider outage can't take it down too. Silence is
   `TTS_SILENT_FALLBACK=1`, **default OFF**: a failed render gets retried, a silent
   video gets published — failing loudly is the better default. *Trap recorded:*
   import the real `gtts` package, NOT `manim_voiceover.services.gtts` — viz_helpers
   monkeypatches that class back into `UniversalTTSService`, so the "fallback" would
   recurse into the failing chain.
3. **Degradation is visible** — each fallback tier prints `TTS_DEGRADED: <tier>` from
   the manim subprocess; `render._tts_degraded_lines` counts them into the sidecar
   (`voice_degraded`) and the job. Same stdout-marker pattern as `LAYOUT_VIOLATION:`.
   A video that shipped on a degraded voice can no longer look clean.
Pinned by `test_tts_resilience.py` (16 checks, httpx stubbed, no keys).
**Correction caught by the very next live run (2026-07-22):** the first cut marked the
Sarvam→Gemini hop as degradation, and this box has **no SARVAM key by design**, so
every cue of every render printed `TTS_DEGRADED: gemini-fallback` and `voice_degraded`
would have been nonzero on 100% of videos. **A metric that is always red is a metric
nobody reads** — the signal would have been dead on arrival. Now `_tts_config_absent`
separates *never configured* (expected routing, logged at INFO) from *failed at
runtime* (real degradation). Generalizable: when adding a health metric, check what it
reads on a HEALTHY run before trusting it — a degradation counter must be zero in the
normal configuration. **The sidecar of the 2026-07-22 optical-fibre video still shows
`voice_degraded: 24`** — that render's TTS calls happened before the fix landed, so
that number is the false positive itself, preserved as evidence. Expect 0 on the next
render.
**Improve:**
- **Script critic gate** (port of `script_critic.py`): a cheap LLM pass over all
  cue texts *before* synthesis checking (1) invented content, (2) language policy
  (Hinglish stays romanized; Devanagari only in on-screen Text), (3) banned filler
  phrases, (4) beat↔element mismatch. Non-fatal: on any failure return the original
  (their rule: *a QC gate improves or stands aside, it never blocks*). Repairs may
  change text only — never beat count/order (their `_shape_ok` contract).
- **Per-element beats** (longer term): split each cue's narration per element and
  give each its own clip, so element k draws over beat k's real seconds — *sync by
  construction* instead of the 0.6 heuristic.

### B-story. Storyboard narrative — scenes were a syllabus, not a story (2026-08-14)
**Evidence (user report + the board that caused it):** "there is no story in the video
being narrated, all the scenes are disconnected". Read back from
`.storyboard_cache`, the projectile-motion board is a *correct* syllabus whose every
scene cold-starts by restating the topic — scene 2 "Projectile Motion ko samajhne ke
liye…", scene 3 "Projectile Motion ki sabse important baat…", scene 4 "Ab dekhte hain
Projectile Motion ke equations" — and the ball thrown in scene 1 never returns. The
prompt's PARTS framework (Hook → Core → Misconception → Recall → Summary) asks for
*sections*, and sections are what it got.
**Shipped:** `narrative` in the IR (`through_line` + a concrete `anchor` example) and
per-scene `role` (hook/build/turn/payoff/recap); prompt rules requiring the anchor in
every scene, connective openings, and a final scene that answers the hook;
`narrative_problems()` measuring cold opens + anchor recurrence, attached to the board
as `narrative_warnings` and logged `[NARRATIVE]`. Deliberately **measured, not
enforced** — a weak story still renders, so rejecting would spend a regeneration on a
soft metric, but unmeasured prompt changes can't be judged. `PROMPT_VERSION` now
partitions the storyboard cache (a prompt change is a content change; without it the
48 h cache serves old-prompt boards and the fix looks like a no-op). Pinned by
`test_story_continuity.py` (16 checks).
**Open:** continuity is only *narration-side*. Visually the scenes are still islands —
each per-scene script starts from a blank canvas, so the anchor is re-drawn from
nothing every scene instead of persisting/transforming across the cut. A real fix
carries one mobject across scenes (or a match-cut transition on the parallel path),
which needs the concat-level transition work in §D's cross-scene variety item.
Also unmeasured: whether the model actually fills `narrative` well — re-read
`narrative_warnings` across the next batch before grading this above L2.

### B-deep. One call became one call per SCREEN (2026-08-15)

User report: *"the gen video has less content and not good flow"*, with an explicit ask
for a NotebookLM shape (sources in → screen plan → specialist agents → precise
storyboard). Design: `docs/deep-storyboard-design.md`. Flag `DEEP_STORYBOARD=1`,
**default off** (1 + N calls instead of 1 — turning it on is a billing change).

**Root cause, and why it is not a prompt bug.** The entire board — narrative spine,
every scene, every element, every cue, in the target language — came out of ONE call.
One call has one token budget; spread over six scenes a model writes the first scene
properly and sketches the rest. Compounding it: *nothing anywhere stated how much a
scene was supposed to contain*, so "thin" was unmeasurable — you could only watch the
video and feel it. Both halves are addressed:

- **`app/pipeline/screens.py` — the Screen Ideator** emits a plan, not prose: per screen
  a role/beat/visual_kind/carries plus two **countable** contracts, `must_show` (one
  entry per drawable object — the storyboard prompt's rule 4c stated as DATA instead of
  advice) and `must_say` (facts, each citing a source chunk). `coverage()` grades the
  written scene against the plan, so under-delivery is a log line
  (`objects planned 22 -> elements written 19`) rather than a feeling.
- **`app/pipeline/scene_writers.py` — one call per screen, in parallel**, each with the
  anchor, the previous screen's leftovers and the next screen's need, and each forbidden
  to re-introduce the topic. Continuity is still judged by `narrative_problems`.
- Everything downstream is unchanged: the same gate, the same heal, the same cache, the
  same agent registry, the same transpiler. The stage produces a *better-filled* board,
  not a different contract — which is why it is one env var and why every failure path
  falls back to the single call.

**The pseudocode stage the request asked for is the screen plan.** Emitting literal
Python between the board and a *deterministic* transpiler would add a translation step
whose only consumer is another model: cost with no verification value.

**One rule, one place.** The language contract was extracted to
`storyboard.language_rules()` because two stages encoding it is exactly the twin this
doc warns about — a persona fix applied to one prompt and not the other ships a video
half in the wrong language, and the gate then rejects the whole board for it.

**Open / not done:** coverage is measured, never enforced (a thin screen logs a warning;
nothing regenerates it — a targeted single-screen rewrite is the cheap next step); the
screen plan is not shown in Studio, though it is the most reviewable artifact the
pipeline produces and comes *before* the expensive fan-out (§J); and citations are
recorded but unaudited (§A). **Vividness floor (2026-08-15 cross-audit, user:
"components setting"):** `must_show` counts objects but not their *quality* — the NLM
pipeline hit exactly this (anchor+budget rules satisfied in the sparsest way: one
small emblem + two labels per slide) and answered with a floor: the anchor visual
must show the idea HAPPENING (object + action + outcome), carry ≥3 labelled parts,
use the source's REAL values (the `must_say[].cite` chunks already hold them), and
accent the acting element. Fold the floor into `coverage()`/the plan clamp so
"sparse but technically compliant" is countable, like thinness already is.
**Shipped 2026-08-15** (prompt floor + `sparse` metric, `DEEP_VERSION` bumped —
see priority row 28). A
cumulative **running summary** (their `extend_running_summary`) is also still
missing — writers see only the previous screen's leftovers; thread a plan-level
story-so-far through the ideator instead of serializing the parallel writers. Grade deferred until a batch has been run through it —
this doc's rule is that grades are earned from evidence.

### D. Codegen (transpiler + critic) — L2.5 (layout-by-construction complete 2026-07-19 night)
**Motion, not just layout (2026-08-14 — user: "there are no dynamic motion in the
gen video").** Measured, not guessed: a `with self.voiceover(...)` beat plays its
entrances for `tracker.duration * 0.35–0.9` plus a few 0.4s event animations, then
the block ends and manim_voiceover **holds the last frame** for the remaining audio
— 2–3s of animation inside an 8–12s beat. The storyboard can't rescue it: across
three live boards the model emitted **92 `show`, 42 `hide`, 6 `highlight`, and ZERO
`transform`/`move_to`/`focus`** — i.e. the expressive half of the event vocabulary is
dead in production, so prompt-tuning motion would be pushing on a rope. Fix follows
the house rule (code owns structure): `viz_helpers.sustain(scene, mobs, tracker,
accent)` spends the leftover beat gesturing at what the cue just introduced (a beat
that introduces nothing gestures the last few things on screen), and both codegen
paths emit one call per cue via `_sustain_call`. **Every gesture is round-trip** —
Indicate/lift-and-settle/scale-and-return all end on the starting geometry — because
the layout probe measures after every `self.play`, and a gesture that displaced
something would manufacture violations and send the repair agent chasing ghosts.
Pinned by `test_sustained_motion.py` (12 checks; Part B is a REAL manim render that
asserts round-trip geometry to 1e-3 and that removed mobjects are skipped).
**Open:** the gesture vocabulary is deliberately small and content-blind — it points,
it doesn't *explain*. Real semantic motion (a vector actually sweeping, a graph
tracing along its curve, a counter counting) needs the director to emit
`transform`/`move_to` from the IR, which is the same gap as the zero-events finding.
**Shipped since the audit (`42dee5cc` + axes-aware zones):** gaps 1–4 below are
fixed by construction — `c2p()` data-space coords for shapes on axes, `Dot()`
points, minimize-diagram-to-left + right-column derivation once math starts
(screen management), content-aware entrance timing (`_TIMING`: axes ≥1.5s, math
≥1.0s, capped at the narration beat) replacing the flat `0.6×`, **axes-aware
zone claiming** (`_seed_axes_zones`: the axes' estimated screen bbox pre-claims
every safe zone whose footprint it overlaps, so the existing fallback chains
route text AROUND the axes — plus zone stacking now shifts toward frame centre,
a BOTTOM-zone stack used to walk off-screen), and **code-computed label slots**
(`_fix_label_slots`: a label whose reference shape sits on the axes near a tick
strip flips its `next_to` direction away from the strip; the critic's midpoint
rule 8 says the same for the LLM path). Verified: the axes+derivation fixture
that measured 11 violations now dry-runs at **zero**, and the raised-axes A/B
(old transpiler vs new, same fixture, real dry-run probe) measured **4 → 0**
violations — the y-axis-through-title and label-on-tick-number failures exactly.
Pinned by `test_axes_zones.py` (14 checks, no manim needed).
`SCREEN_TEXT_LANG` (match|en) now pins on-screen text language separately from
narration persona. ~~Known issue: free-text `event` strings are emitted as
raw code by the legacy event path and can break a scene~~ — **fixed 2026-07-20**
(`_sanitize_anim_calls`): every legacy-path fragment is now AST-parsed and kept
only if it is a whitelisted animation call or an `.animate` chain. Measured
before the fix — prose (`"the ball falls and bounces"`, and the Devanagari case)
became `self.play(the mobj_scene1_ball falls…)`, a SyntaxError that killed the
whole scene; a **bare element id compiled but raised at render time**
(`self.play()` needs an Animation, not a Mobject) — the worse half of the bug,
which the syntax validator could never have caught. Degrades partially rather
than all-or-nothing: `"FadeOut(ball), and the scene ends"` keeps the `FadeOut`.
Dropped fragments log `[TRANSPILER] dropped …` to stderr — **watch that line**,
it is the storyboard telling us it writes prose where it should write calls
(fix upstream in the storyboard prompt if it turns out to be frequent, per the
attribute-upstream-first rule). Pinned by `test_event_sanitize.py` (14 checks).
**Have:** deterministic transpiler (zones + fallback chains, topo-sorted elements,
`math_evolution` transforms, SVG sanitize + keyword normalization, per-scene
scripts); Layout QA Critic LLM pass; syntax/logic validate-and-repair.
**Gaps found in audit (frame evidence, "Distance between two points" run):**
1. **Scene-vs-data coordinates** — points/lines on an `Axes` are emitted with raw
   scene coords (`.move_to([-3, 2, 0])`), but the axes' unit ≠ 1 scene unit, so
   point A labeled (x₁,y₁)=(−3,2) *renders at ≈(−2.5, 2.4)* — visibly off-grid,
   lines don't touch gridlines. Mathematically wrong output.
   **Fix:** when a scene contains a `coordinate_system` element, the transpiler
   must emit `<axes_var>.c2p(x, y)` for every point/line/label positioned on it
   (data-space contract), never `.move_to([x,y,0])`.
2. **Points are `Circle().scale(0.1)`** — stroke-only rings; should be `Dot()`.
3. ~~**Line labels collide with tick numbers**~~ (`|x₂−x₁|` rendered through the "3"
   tick; midpoint+0.3 shift ignores what else lives there) — **fixed 2026-07-19**
   (`_fix_label_slots` + critic rule 8 rewrite; A/B above).
4. ~~**Zone system is blind to the axes' real extent**~~ (scene 4 shifted axes up but
   kept text bands fixed: the y-axis ran straight through the question text) —
   **fixed 2026-07-19** (`_seed_axes_zones`; A/B above measured this exact
   failure at 4 violations old → 0 new).
5. ~~**Unknown shapes fall back to `Circle()`**~~ — **FIXED 2026-08-01**, together
   with three worse bugs in the same branch, found by inspecting a real
   "Prime Factorization" render where **16 of 17 shape elements drew as the wrong
   object**. Root cause: `content` for a shape is prose *by schema* ("For shape, a
   description"), and the branch substring-matched that prose. Four distinct faults:
   (a) **substring matching** — `"arrow" in "…with curved motion arrows"` made a row
   of tiles an `Arrow()`; the same class as the `"grade 1" in "grade 11"` planner bug.
   Now word-START matching (`\bkw`), so "narrow" no longer hits `arrow`.
   (b) **contents matched instead of the object** — "two chalk **branches** from 84 to
   **circles** containing 12 and 7" hit `circle` and drew ONE circle instead of the
   branches. Now `_shape_head()` cuts the description at the first clause word
   (`containing`/`with`/`from`/`ending`/…) so the head noun decides.
   (c) **contained values dropped** — "circle containing **84**" drew an empty ring, so
   an entire factor-tree video rendered with **no numbers in it**. Now
   `_shape_value_label()` extracts a single value and `viz_helpers.value_in()` centres
   it inside the shape, scaled to fit. Deliberately conservative: a list
   ("containing 2, 2, 3 and 5") or prose ("containing twelve evenly spaced slots")
   labels nothing, because one shape carrying the first of several values would state
   something false.
   (d) **unknown → generic `Circle()`** — the original gap; "chalk starburst" and
   "check mark" drew meaningless rings. Now the vocabulary covers real diagram nouns
   (node/panel/tray/tile/block/frame/branch/connector/star/cross/ellipse) and anything
   still unmatched routes to `fetch_smart_svg` with a cleaned keyword (colour/size
   adjectives stripped); `get_smart_asset`'s own native fallback means it can never
   fail to return a mobject.
   **One table now drives both the object and its entrance** (`_SHAPE_KINDS`), so the
   pair can no longer drift — the hazard the old parallel `_SHAPE_ENTRANCES` list
   carried. Pinned by `test_shape_resolution.py` (33 checks, no manim/keys); full
   deterministic suite 135/135 green.
   **Render-verified on the same board:** the ✗ mark is a `Cross`, both comparison
   panels are `Rectangle`s, the starburst is a `Star`, splits are `Line`s, and
   **"84" is now visible inside its circle** — every one of those was an identical
   empty ring before.
   *Related contrast backstop shipped the same pass:* the Layout-QA critic writes
   `Text('84', color=BLACK)` for a value inside a stroke-only shape — correct on
   paper, **invisible on this pipeline's dark canvas**. `viz_helpers._contrast_safe_text_color`
   now flips near-black text (luminance < 0.16, any colour form) to a light tint on
   dark canvases only; `IS_WHITE_BACKGROUND` still owns the light path. A drawn-but-
   unreadable value is the same failure as a dropped one.
5b. ~~**A single element that describes a MULTI-PART sub-diagram (D8).**~~ —
   **STRUCTURAL IR SHIPPED 2026-08-01.** Two optional fields close it, both with ALL
   geometry owned by code:
   - **`VisualElement.connects: [id_a, id_b]`** — the element IS an edge.
     `viz_helpers.connector()` computes endpoints from the two mobjects' facing
     boundaries, so an edge can never drift off what it links; it is emitted with NO
     position of its own (a zone/absolute placement would tear it off its nodes).
     `"arrow"` in the content gives it an arrowhead. Malformed edges (one id,
     self-loop, id not in this scene) emit nothing rather than crash — the per-scene
     isolation lesson.
   - **`RelativePosition.relation: "inside"`** — containment as a placement primitive
     (the old D7). `viz_helpers.place_inside()` distributes siblings across the
     container in a grid and shrinks them to fit, so a container is never drawn empty
     and contents never spill. Slot indices are assigned **scene-wide**
     (`_mark_containment`), because siblings of one container may enter on different
     cues and each still needs its own cell.
   `_topo_sort_elements` now orders on BOTH dependency kinds (anchor + both edge
   endpoints), so an edge is always emitted after the shapes it joins. Wired into both
   codegen paths. Schema re-exported (`--regen`); contract gate green.
   **Render-verified end-to-end:** a factor-tree board now draws five labelled nodes
   joined by four real edges (previously: one circle, three floating line stubs), and a
   tray board draws six sweets distributed inside the box (previously: an empty
   rectangle). Pinned by `test_ir_structure.py` (36 checks).
   **Found while verifying — and the more important half:** see the critic-guard entry
   below. The prompt now also carries rule **4c ONE ELEMENT PER DRAWABLE OBJECT**, so
   models stop smuggling sub-diagrams into prose.
   *Still open:* nothing consumes `composition` yet (P05), and no layout **solver**
   exists — these primitives express structure but do not yet balance or align a frame.

5b-i. **The Layout QA Critic could silently delete elements — FIXED 2026-08-01, and it
   is the root of "codegen has too little control".** Acceptance for the critic's
   rewrite checked only *does it parse*, *has `def construct`*, *has the scene class*.
   Nothing checked that it preserved the objects. Measured: asked to tidy a tray of six
   sweets it collapsed all six into ONE mobject and replaced `place_inside()` with a
   hand-rolled `arrange_in_grid` — **five elements silently deleted from the video**,
   after the deterministic transpiler had them correct. This is the exact inversion of
   the house rule: an LLM pass was rewriting *structure*.
   Now `review_and_fix_layout` rejects a rewrite that drops any `mobj_scene*_*` element
   variable (`_element_vars`) or dissolves a structural helper
   (`_structure_losses`: `connector` / `place_inside` / `value_in` call counts may rise,
   never fall), keeping the deterministic code and logging what was lost. **The QC pass
   improves or stands aside — it can no longer destroy.** Verified live: the same board
   that lost six candies now logs `Layout QA Critic dropped 6 element(s) … keeping
   deterministic code` and ships all six. Pinned in `test_ir_structure.py` §G.

5b-iv. **Graph auto-layout — code computes node positions from the structure
   (2026-08-01).** With `connects` in the IR, node coordinates no longer come from the
   model guessing. `_apply_graph_layout` finds connected components of the declared
   node/edge graph (≥3 nodes — a 2-node link is not a diagram), assigns BFS depth from
   the first-declared node (storyboards declare a tree root-first), and lays out
   layered top-down: depth → row, evenly distributed within each row, scaled into the
   band between a title and a caption (`_GRAPH_TOP_Y`/`_GRAPH_BOTTOM_Y`). It
   **overrides** any `absolute_position`/`safe_zone_alignment` the model wrote for those
   nodes — this is D1's rule ("the LLM never emits geometry") applied to whole diagrams
   — while leaving edges and `inside` children alone, since both derive their position
   from something else. Emits `[TRANSPILER] graph layout placed N node(s)`.
   **Render-verified from a deliberately terrible board:** six nodes all piled within
   0.1u of (-5.5, 3.4) rendered as a correct, balanced factor tree of 180 (root, two
   children, three leaves), 0 text violations, 0 shape overlaps.
   *Open:* only tree/DAG layering is implemented. Radial, force-directed and
   left-to-right flow layouts are the obvious next kinds — see P11's framework survey
   (Graphviz/ELK are drop-in for exactly this once a second layout kind is wanted).

5b-v. **The critic also un-anchored zone-placed elements — caught by looking at a
   frame, not a test.** After the element/structure guards landed, a render still put a
   BOTTOM_CENTER caption through the middle of the factor tree. Cause: the critic
   rewrote `.to_edge(DOWN, buff=0.3)` into `.move_to([0, BODY_Y, 0])`, and
   `BODY_Y = -0.5` is the frame's MIDDLE. Nothing was deleted and no helper dissolved,
   so both existing guards passed it. Safe-zone placement is code-owned (zone claiming,
   axes-aware routing, stacking toward frame centre), so `_anchor_losses` now rejects a
   rewrite that lowers the `.to_edge(`/`.to_corner(` count. Verified: the same board now
   logs `un-anchored zone-placed elements (zone anchors 2->0) — keeping deterministic
   code` and the caption returns to the bottom edge.
   **Generalizable:** each of these three guards was found by a *different* failure of
   the same kind — the critic has broad freedom over code the transpiler owns. Prefer
   adding an invariant over tightening the critic prompt; the prompt is advice, the
   invariant is a contract.

5b-ii. **Shape-on-shape overlap is now measured (was invisible).** The probe's overlap
   check iterated **text only** — `_shapes` fed the text-over-shape check and nothing
   else — so two diagrams could sit on top of each other and the run graded clean at
   `violations_remaining: 0`, which is why users reported overlap the sidecar denied.
   `_ovl_shape_pair_check` adds it under its OWN class name `shape-overlap`, exempting
   structurally legitimate contact (same-root groups, any edge touching what it links,
   full containment). **Deliberately NOT counted by `_overlap_violations`** — following
   the `vision-*` precedent, a new metric is reported into the sidecar
   (`shape_overlaps`) and graded on real runs before it is ever allowed to trigger a
   repair round. (Note the substring `"LAYOUT_VIOLATION: overlap"` does not match
   `"…: shape-overlap"`, so the counted set is genuinely unaffected.)

5b-iii. **Original D8 statement, kept for the record.** A single element that describes
   a MULTI-PART sub-diagram: Same 2026-08-01 render: after (a)–(d),
   shape *types* are right but frames are still thin, because the storyboard packs a
   whole sub-diagram into one element's prose — "Two diagonal chalk branches from 84
   **to circles containing 12 and 7**" is 2 lines + 2 labelled nodes, and
   "coral chalk **frame with** a short factor branch ending at circles 2 and 6" is a
   frame plus its contents. The transpiler correctly emits ONE primitive, so the child
   nodes never exist: the factor tree renders as a labelled root, disconnected line
   stubs, and empty panels. This is the same lesson as D1/D7 one level up — **the model
   is expressing STRUCTURE (containment, connection) in prose, where code should own
   it.** Keyword work cannot close this; it needs a representation.
   **Approach (schema-level, needs `--regen`):** give `VisualElement` an optional
   `connects: [id_a, id_b]` (transpiler draws a real edge between two resolved
   mobjects' boundaries, killing the floating stubs) and an optional
   `children: [id, …]` or `relative_positioning.relation: "inside"` so a container's
   contents are laid out within its bbox. Then tighten the storyboard prompt to emit
   one element per drawable object. Until then, prefer boards that name each node as
   its own element.

5c. **Unknown shapes fall back to `Circle()`** *(historical note — see 5 above for the
   fix; the original wording is kept because the ranking table still points at it)*
   (`transpiler.py:425`, the `else`
   of `_build_obj_expr`'s shape branch): "angle diagram" → circle. Handled
   keywords are only point/dot→`Dot`, circle, square, rect, triangle, arrow,
   line (transpiler.py:418-424). Note `svg_icon` elements ALREADY route to
   `fetch_smart_svg` (line 406) and molecules to `fetch_molecule_svg` (413) —
   the gap is solely the unknown-`shape`-keyword case.
   **Detailed approach (small, ready to land):** replace the line-425 fallback
   with the same emission the svg_icon branch uses:
   `fetch_smart_svg(<keyword>, color=<el color>, height=<scale>)`. No
   pre-normalization needed — `get_smart_asset` already runs
   `_normalize_svg_keyword` internally (viz_helpers.py:607; the map has 106
   entries, viz_helpers.py:259-302, not "70+"). Reuse the existing
   `failed_assets` preflight guard so a keyword the asset cascade can't resolve
   still degrades to `Circle()` instead of a broken render. Pin with a
   no-manim check (`test_axes_zones.py` style): unknown keyword emits
   `fetch_smart_svg`; preflight-failed keyword emits `Circle()`.
6. ~~**Entrance-animation vocabulary is monotone**~~ — **closed 2026-07-20 night.**
   The 07-20 morning census (76 `self.play` calls, one `Write`, all rate_funcs
   elastic) was taken over temp_renders scripts that predate `_ENTRANCE_CONFIG`
   (transpiler.py:13) — by audit time the per-type map (text→elastic FadeIn,
   math→`Write`, shape→`GrowFromCenter`, axes→`Create`) already existed, so
   most of this gap had silently shipped with the elastic-entrances work.
   **A census over old artifacts measures the old code — check the emitter
   before grading the gap.** The genuinely missing piece landed 2026-07-20
   night: shape entrances refined by content keyword (`_SHAPE_ENTRANCES`:
   arrow→`GrowArrow`, line→`Create`, point/dot→`GrowFromCenter`,
   circle/square/rect/triangle→`DrawBorderThenFill`), with keyword precedence
   deliberately mirroring `_build_obj_expr`'s shape branch so the animation
   always matches the object actually emitted ("arrow pointing at X" builds a
   Dot via the "point" match and must not `GrowArrow`). rate_func variety was
   already right by construction (elastic only on FadeIn targets; Write/Create
   default smooth). Pinned by `test_entrance_map.py` (14 checks, no manim):
   the mixed-type fixture emits 5 distinct entrance classes; both codegen
   paths agree. Note the census result for *text-heavy* storyboards will still
   look FadeIn-dominated — that is the content mix, not the map.
**Improve:**
- **Visual Director stage — v1 SHIPPED 2026-07-21 night** (`app/pipeline/director.py`,
  flag `VISUAL_DIRECTOR=1`, allowlisted for `env_overrides`). Of the four planned
  decision families, three landed: (a) **visual hierarchy** — LLM ranks
  primary/secondary/tertiary, code applies scale tiers ×1.2/×1.0/×0.8 clamped
  [0.4, 1.15], axes/graphs exempt (their footprint seeds zone claims);
  (b) **object lifetime** — LLM proposes "finished after cue k", code appends a
  standard `hide` event ONLY when provably safe (never final cue, never at/before
  birth, never while later events reference it, never an anchor whose label still
  lives — each rule pinned in `test_director.py`, 24 checks); (d) **semantic
  highlighting** — standard `highlight` events, 1/cue, ≤3/scene. All application is
  deterministic (`_apply_directives`, pure) and expressed as ordinary DSL constructs,
  so the transpiler needed ZERO changes and strip-invariance is trivial; the LLM never
  emits geometry. (c) **camera language** remains open — it needs transpiler camera
  support first. First live run (refraction, 6 scenes, gemini-2.5-flash directives):
  `[DIRECTOR] applied: 40 rescaled, 0 hides, 14 highlights (3 proposals rejected)`.
  Watch item: the model proposed 0 hides on its first board — if that repeats, the
  prompt undersells lifetime; tune the prompt, not the safety gates.
  `_maybe_minimize_diagram` and `layout_template` remain absorbed-later pieces.
  **(c) camera language — SHIPPED 2026-07-21 night, deliberately narrow.** A `focus`
  action (semantic spotlight: dim every other mobject, hold, restore — emitted by BOTH
  transpiler paths as `spotlight_on/off`, implemented in `viz_helpers`) with one
  spotlight per scene, never sharing a beat with a `highlight`. **Zoom/pan are NOT
  implemented and should not be added casually:** the overlap probe's clipped-text
  check measures against a fixed `config.frame_width/height`, so a `MovingCameraScene`
  would make it flag legitimately off-frame content and miss real clipping — camera
  motion breaks the verifier. Opacity changes no geometry, so every probe invariant
  survives. Implement camera moves only together with a frame-aware probe.
- **Dead-frame at the source — SHIPPED 2026-07-21 night (the other half of §G's live
  finding).** Two coordinated changes, since the vision reviewer flagged 6/6 frames:
  (i) **storyboard richness** — a new prompt section *4b. FRAME OCCUPANCY* requires a
  substantial central visual, 3–6 elements per scene, `scale` 1.0–1.5 for the scene's
  main visual, and drawing the whole process (a glass slab with no ray, a spring with
  no mass, an axis with no curve are named as dead frames); (ii) **enlarge-to-fill** —
  `director._enlarge_sparse_scenes`, a DETERMINISTIC pass (≤4 elements and no axes ⇒
  boost every scale ×1.3, clamped at 1.4) that runs even when the LLM half stands
  aside, because pure code cannot fail. Conservative on purpose: over-enlarging trades
  a dead frame for clipped text, which the probe would then have to pay for.
  **Measured on the next live board (optical fibre, 2026-07-22) — partial success,
  reported honestly:** element density rose to [4,8,6,7,5] per scene (avg 6.0, inside
  the rule's 3–6 target) and enlarge-to-fill boosted 3 elements, but Vision QA still
  reported 3 `dead-frame` findings. Reading the actual findings changes the diagnosis:
  *"mostly empty with only a title at the top"* at t=29.6s / 69.07s / 88.8s — these are
  **scene-boundary moments**, where the title has entered and the scene's visuals have
  not yet. The 6 evenly-spaced sample frames are landing on scene starts, so this is
  substantially a **sampler artifact, not a composition defect**.
  **Next move (precise):** `_extract_frames` samples the concat blind; pass the clip
  boundaries in (the caller already computes them for attribution) and sample at the
  *midpoint of each scene* instead of evenly across the whole video. That removes the
  false-positive class AND gives one frame per scene, which is what the rubric wants
  anyway. Only after that is the residual `dead-frame` count a trustworthy metric for
  grading the richness/enlarge work.
- ~~The governing principle from their DIRECT_GEN doc — **"the LLM never emits
  geometry"** — finish it: data-space coords via `c2p`, `Dot` for points, label
  slots computed by code, axes-aware zone claiming~~ — **done 2026-07-19**; the
  transpiler now owns coords, slots, and zone routing end-to-end.
- Add an **`_assert_contract()`-style check inside the transpiler** (margins,
  band non-overlap, axes-vs-band separation) so violations are impossible by
  construction; keep the probe as the independent auditor.
- Route unknown shapes through `fetch_smart_svg` before the Circle fallback
  (detailed in gap 5) and widen the entrance map (gap 6).
- **Visual theming (v1) — SHIPPED 2026-07-27.** The style-profile dropdown had
  been dead on the deterministic path for its whole life: the transpiler never
  read it, so every video rendered on Manim's pure-black canvas with flat-white
  shapes and a hard-coded YELLOW `Indicate` accent, whatever style the user
  picked (the profile only reached the *LLM* codegen path as prose). New
  `stem_animation_lab/theme.py` (pure data, no manim — the "no-manim" harnesses
  load it) maps each of the five UI profiles to a concrete `Theme`: a dark
  canvas background painted via `camera.background_color`, an `accent` that
  replaces the YELLOW default, and an ordered `palette` cycled onto **uncoloured
  shapes** so diagrams read as designed instead of a wash of white strokes.
  Model-authored colour is never overridden; text/math keep their high-contrast
  defaults. Traps recorded (both are why the design is shaped as it is): the
  themed background is painted **only for dark themes on a `default` background**
  — a light canvas is reached solely via `white_canvas`, where `viz_helpers`
  owns the light-mode text recolour; painting a light `camera.background_color`
  directly would leave white text invisible. And both codegen paths
  (`parse_schema_to_base_scene` + `parse_schema_to_scene_scripts`) resolve the
  same theme so the single-script render and the concatenated parallel clips
  share one look. Font family left at Montserrat deliberately — swapping it
  shifts text metrics and needs a fresh overlap-probe pass, a separate lever.
  Render-verified (3blue1brown / mono / powerpoint before/after frames) and
  pinned by `test_theme.py` (28 checks, no manim/keys). **Open (v2):** themed
  axes colour (transpiler emits plain white `Axes`; `viz_helpers` YELLOW plot
  defaults are import-time, so a runtime theme handle is needed), cross-scene
  transition variety (parallel path hard-cuts at ffmpeg concat — needs an
  `xfade` in `render.py`), and the font-family lever.
- **Composition descriptor — SHIPPED 2026-07-22.** Every `StoryboardScene` now
  carries a `composition` field — a 1–2 sentence layout gestalt ("Title banner
  top, coordinate grid centre, derivation stacked right column") populated by the
  LLM at storyboard time. The transpiler logs it per scene as `[COMPOSITION]`
  lines. Bridges model intent to code: the LLM's layout intent is captured in a
  structured field before the transpiler makes zone/split decisions, so a new
  zone heuristic first checks whether the descriptor already conveys that intent.
  Schema re-exported: `schemas/storyboard-ir.schema.json`. Pinned by the drift
  gate in `test_ir_contracts.py`.
- **Surface `[TRANSPILER] dropped` lines.** Today they go only to the server
  process stderr (transpiler.py:241/247) and are lost — not in job logs, not in
  the sidecar, nowhere queryable — even though this doc says "watch that line".
  **Approach:** `_sanitize_anim_calls` appends each drop to a module-level
  list; `generate_code_impl` drains it after transpiling and (a) logs via
  `logger.warning` so it reaches the log files, (b) returns a `dropped_events`
  count in the `/api/generate_code` response, (c) threads it through
  CompileRequest into the sidecar so /timeline can badge
  "storyboard wrote prose ×N" and the attribute-upstream-first rule has data.

### D-sim. The IR could not say "this system evolves" (2026-08-15)

The `sustain` filler (§D, 08-14) fixed *dead air*; the Motion Director fixed *nothing
moves*. Both work inside a vocabulary that describes a **composition** — things appear,
sit, move beside each other, and leave. Neither can express a system evolving over time,
so every projectile, wave, orbit and pendulum still rendered as a still picture of a
moving thing. That is not a prompt gap: the vocabulary did not exist.

**Shipped: `type: "simulation"` + `app/sim_gen.py`** (schema change, `--regen` run).
A model writes ONE bounded pair for ONE element — `build(width, height) -> Mobject`,
`animate(group, run_time) -> Animation` — and the transpiler still owns the scene. This
is deliberately *not* a return to LLM whole-scene codegen (that would give back
layout-by-construction, zones, split-screen, structure, theming and the probe contract);
it is `asset_gen`'s `def draw(ax)` applied one layer up, and it works for the same
reason: the harness owns the figure, so the model cannot get the figure wrong.

**What actually makes it safe is the verifier, not the context.** `verify()` steps the
animation by hand (`begin`/`interpolate(alpha)`/`finish`) with **no renderer at all** —
~1s, no ffmpeg, no video — which is what makes reject-and-retry affordable. It rejects a
`build()` that draws nothing (an empty VGroup runs perfectly: "exit code 0 proves
nothing"), an animation where **nothing moves** (the moving equivalent of the blank
icon), geometry that **leaves its 6x4 box mid-animation** (it would manufacture
clipped-text violations and send repair chasing ghosts), and anything that raises.

**Manim context (`app/manim_context.py`) is the installed package**, introspected in a
subprocess and cached as JSON, plus curated build/animate patterns — *not* a web-search
model (reads a decade of dead ManimGL/0.x APIs; unmeterable, uncacheable,
non-deterministic) and *not* MCP (a live dependency a headless/cron run silently loses).
Keyword scoring, no vector DB, no new dependency.

**Two traps, both worth generalizing.** (1) The cached module has no imports — it is
told to import nothing because the harness supplies them — so an `importlib` load gave
it *empty globals* and **every simulation silently became a Text placeholder that looked
like a working fallback**. Only a real render found it (`test_simulation.py` Part F).
Same family as the `viz_helpers.__all__` and selective-import traps: the code looked
right, the environment contract broke it. (2) The probe measures a *still frame*, so
deleting a `sim_play(...)` line removes all the motion and leaves a perfectly legal
frame — the cheapest way for a repair round to "improve" a video.
`_repair_preserves_assets` now guards it, restating the image lesson as a general rule:
**every asset the verifier is blind to needs its own deterministic preservation guard.**

**Open:** a simulation plays once, during the cue that introduces it — a system that
should evolve across several cues (a wave whose frequency changes as the narration
explains frequency) needs a `simulation` + event vocabulary. And the probe still only
sees the final frame, so a mid-animation collision with a caption is unmeasured; the box
contract limits the damage rather than removing it.

**2026-10-09 — three things the verifier got wrong, found on the long-form path**
(`longform/runtime.GuidedChapter` steps the same modules; rules in `CLAUDE.md`, section
"composition and sync"). (1) "Something moved" was judged on point positions only, so
parts that APPEAR one after another ("first one block, then a stack of two, then of
three") were refused as *nothing moved*: `_fingerprint` now also counts opacity, stroke and
colour. (2) The prompt recommended `Succession`, which cannot be stepped without a scene
(it reads `self.scene`; patched, its later parts stand in full view until their turn). It
had therefore never once passed: 0 of 192 cached modules use it. Now a contract problem
whose brief names `AnimationGroup(a, b, c, lag_ratio=1.0)`, and out of the context list.
(3) A module with nothing visible at alpha 0 is refused (`seen_at_start`): the long-form
renderer holds a scene at its start until the first words about it. Measured on one
script made twice through the app: before, two scenes took 5 attempts and one was given
up on and redone small; after, three scenes took 3 attempts. One run each, so a
direction, not a rate. `test_simulation.py` B15–B20.
**Still open from the same reading:** a cached module is never re-verified, so a checker
improvement does not reach scenes already in the cache; and the engine path's
`sim_play` has the same redraw-order question the long-form driver had (an updater-driven
mobject added AFTER the thing it moves leaves that thing in Manim's still background) —
not checked there.

### D-agents. The pipeline is now a registry of IR agents (2026-08-14)
**Ask:** "make the system modular so we can delegate to separate AI agents ... a agent
gen a dynamics part and then the other ... finally an agent stitch them."
**Shipped:** `app/pipeline/registry.py` — an ordered registry of IR-enrichment agents
(`visual_director` → `motion_director`), each `enabled()`-gated, failure-isolated, and
traced into `board["agent_trace"]` (events before → after, seconds, errors). Plus the
agent the ask was really about: **`MotionDirectorStage`**, which authors
`move_to`/`transform`/`focus`/`highlight` events the storyboard model never emits
(measured: 92 show / 42 hide / 6 highlight / **0** motion across three boards).
Verified end to end: agent directives become `arrow.animate.next_to(ball, LEFT)` and
`TransformMatchingTex(eq, eq2)` in the emitted script.
**Design note worth keeping:** the agents split the INPUT (one IR, many specialists),
not the OUTPUT (one clip each, stitched). Output-splitting puts the seams in the
artifact — mismatched styling, duplicated elements, a stitcher that can only cut —
while input-splitting keeps the deterministic transpiler as the sole renderer, so the
"stitch" cannot disagree with itself. Any future agent (narration polish, assets,
pedagogy) joins the same way.
**Open:** (a) agents are sequential and each costs an LLM call — parallelising the
independent ones (motion vs assets) is free latency; (b) no agent yet *reviews*
another's work (a "did this actually add motion" critic could reuse the Vision-QA
seam); (c) the motion vocabulary is still the transpiler's four verbs — a curve trace,
a counter counting, or a camera-free pan need new transpiler support first, and each
needs the overlap probe checked against it.

### D-colour. Theming reached the canvas but not the content (2026-08-14)
**Evidence:** user — "the style profile and the background are not matching and the
gen content is stale". Counted over the six most recent cached boards: **190/198
elements (96%) carry a model-authored `color`**, dominated by raw primaries
(`#FF00FF` ×24, `#00FFCC` ×20, `#FFFF00` ×15, `#00FFFF` ×10). Since the theme only
coloured *uncoloured* shapes, the style profile touched ~4% of the frame — v1 theming
was nearly dead code in production, the same shape as the math-only split-screen
trigger (§D) and "production never used the parallel path" (§F4).
**Shipped:** `theme.harmonize` — keep a model colour when it clears WCAG 3.0 against
the resolved canvas and isn't a raw primary, else snap to the nearest palette colour
BY HUE (distinctness survives, cohesion is gained); text/math never hue-snap, they
fall back to `theme.text` when unreadable; unchanged colours are emitted verbatim so
the diff shows only real changes. Plus `resolve_theme` now adapts a LIGHT theme whose
background isn't `white_canvas` (powerpoint + default painted nothing and put dark
navy on Manim black), and `GET /api/theme` serves the resolved theme so the Studio
blueprint stops hard-coding its own canvas. Pinned by `test_theme.py` Part F.
**Open:** harmonization is per-element and canvas-blind to NEIGHBOURS — two adjacent
shapes can still snap to the same palette entry and lose their distinction; a
scene-level assignment (distinct hues per scene, like the palette cursor does for
uncoloured shapes) is the next step. Also unmeasured: whether pushing the storyboard
prompt to stop emitting colours at all would beat harmonizing them after the fact.

**Emphasis left the colour system entirely (2026-08-15, user: "remove the object
highlight").** `highlight` emitted `Indicate(target, color=theme.accent)` — a half-second
flat repaint. Two problems, one of which harmonization had just made worse: on a themed
frame a temporary accent repaint reads as the object *changing meaning*, and on a raster
photo it painted the whole bitmap (the reason images carried a `Circumscribe` special
case). Replaced by `viz_helpers.emphasize` — `ScaleInPlace(mob, 1.08,
rate_func=there_and_back)`, i.e. what Indicate does internally minus `set_color`. One
treatment for every element type, so the image special case is gone; `sustain`'s colour
gesture became a sideways nudge, which also retires its "ImageMobject has no colour API"
branch. The colour-flash class names left `_VALID_ANIM_NAMES` too — the legacy free-text
`event` path was the back door. **This shrinks what the theme's `accent` is FOR**: it no
longer reaches generated code at all, so `test_theme.py` had to re-observe the
style-profile fallback through the palette instead. Worth knowing before treating
`accent` as a live lever. **Trap:** a round-trip pulse built as two chained `.animate`
legs is not round-trip — `.animate` snapshots its target at CONSTRUCTION, so the return
leg is computed from the original geometry and the pulse settles at 0.926× (measured
drift 0.028, enough to trip the probe it exists to respect).

### E. Assets — L2.5 (2026-07-31: real raster images shipped — Wikimedia `image` elements)
**Have:** Iconify fetch + sanitize (gradients/filters stripped), 70+ STEM keyword
normalizations, RDKit molecules, preflight probe with LLM substitution notes.
**New (2026-08-14): the cascade no longer bottoms out in a generic circle.**
`app/asset_gen.py` adds a final tier — an LLM writes matplotlib drawing code, we
execute it sandboxed, and the SVG is spliced into the board as an absolute path
(`resolve_generated_assets`, called right after the image pass; `get_smart_asset`
step 0 loads a pre-resolved path). Triggered by exactly the elements the preflight
already reports as `status: fallback, provider: native_shape` — the user's live
example was `svg_icon "grandfather clock"` rendering as a ring. Contract: the model
writes ONE `def draw(ax)` (harness owns figure/aspect/transparency/savefig); code is
statically gated for IO/imports/dynamic-exec and run under `python -I` with a scrubbed
env and a 45s timeout; acceptance counts only VISIBLE primitives (matplotlib's
`fill:none; opacity:0` background path made an empty drawing look successful);
cached per keyword in `assets/generated_cache/` so a repeat icon costs 0; one repair
round on a crash; any failure degrades to the old native-shape fallback. Verified live
the same day — attempt 1 hit a model em-dash typo, the repair round fixed it, and the
rasterized icon reads as a grandfather clock. Pinned by `test_asset_gen.py` (30
checks, real matplotlib subprocess).
**A resolved icon can still be the wrong icon (2026-08-14, same report).** Iconify
never answers "no" — it returns its CLOSEST match, so "grandfather clock" comes back
as a plain clock face with `status: resolved`, and nothing downstream ever knew. A
wrong hit is worse than a miss: a miss at least reaches a fallback. `probe_asset`
now scores every hit with `icon_match_strength` (every significant keyword word must
appear in the icon id, 5-char prefix so inflections count) → `strong|partial|weak`,
and `ASSET_GEN_MODE` (`fallback` | **`weak`, default** | `always`) decides which get
drawn instead. Measured: `grandfather clock`→`mdi:clock-time-four` partial,
`water molecule`→`mdi:water` partial (a droplet is not a molecule), `test tube`→
`mdi:test-tube` strong, `clock`→`mdi:clock` strong. Replacing a *resolved* icon adds
no asset warning — it was never a miss. **Open:** `shape`-type elements that route to the
asset cascade aren't generated (their `content` is prose the transpiler still parses,
so the path rewrite would break shape resolution) — needs a name-keyed cache hop
instead; and generated icons are never re-reviewed for quality (no vision check).
**New (2026-07-31):** `type:"image"` storyboard elements → real photos/paintings/maps
from Wikimedia Commons, resolved SERVER-SIDE at codegen time (`resolve_image_elements`
in `app/assets.py`: search → licensed bitmap ≥400×300, aspect 0.4–2.6 → ≤1024px thumb
cached in `assets/wikimedia_cache/` with a JSON attribution sidecar → element content
rewritten to the abs local path, so renders are network-free and dimensions known).
Render loader + fallback: `viz_helpers.fetch_real_image` (aspect-true, clamped
≤7.0w/≤5.5h). Built for narrative Social Science topics; sol storyboards adopted it
immediately (one primary image/scene, specific queries, correct height scales).
Pinned by `test_image_elements.py` (19 checks). Measured on the first live batch:
~80% query hit rate ("Paris bread market 1789" and a route-map query missed → clean
Text degradation); Commons 429s parallel thumb pulls (now 3 workers + one 3s retry).
**Improve:** content-address the asset cache (currently keyword-named files in a
shared dir); record per-asset provenance in the sidecar for the R1-style
traceability their rubric scores. Image-specific: (1) probe currently SKIPS
ImageMobject wholesale — genuine text-over-image collisions are unmeasured; a
center-inside-bbox check (not the stroke-crossing one) would restore coverage
without the false-positive storm. (2) Query misses could retry with an
LLM-simplified query (metered) before degrading to text. (3) On-screen photo
attribution line (license requires it for CC-BY images; sidecar already has the data).

### E-draw. Manim draws the objects — clipart and the primitive table are gone (2026-08-15)

Two user reports, one day apart, after watching live videos: *"remove the svg import and
let the content be generated by manim itself"* and *"remove this shape calling issue and
let the llm gen the code for the obj rather than using fixed shapes"*. The frames and the
board agreed:

- **14 `svg_icon` elements, ALL the same keyword.** A 105-second projectile explainer's
  entire visual vocabulary was one flat clipart basketball, repeated, floating on black.
- **14 of 16 `shape` elements were content-free** — `"circle"`, `"small circle"`,
  `"point"`, `"arrow pointing right"`, `"rectangle"`. The renderer drew exactly what was
  asked for; the ask meant nothing.

**Shipped:** `sim_gen.resolve_drawn_elements` draws BOTH types with the same verified
`build(width, height) -> Mobject` contract the simulations already use — a drawing is a
simulation without motion, so one harness verifies both and they cannot drift. One call
per *distinct* description, in parallel, cached forever (that 14-icon board = ONE call).
`DRAW_WITH_MANIM=0` restores the old paths exactly.

Design points that are load-bearing, not incidental:
- **It runs before the icon preflight.** A resolved element must never be probed:
  probing a filename fails, a failed probe becomes an asset warning, and a warned
  element degrades to a Text placeholder — the probe would have *deleted the drawing it
  was reporting on*.
- **`min_parts` is the real check.** Iconify's failure mode was answering every query
  with its nearest match; a one-circle "drawing" is the same failure wearing a different
  hat. Floors: 3 for an icon, 2 for a shape.
- **Two things are never drawn.** An **edge** (`connects`) takes its geometry from the
  mobjects it joins, so drawing it tears it off the nodes. A **bare primitive** names no
  subject, so a model with a floor to meet invents parts nobody asked for — the fix for
  those is upstream, not here.
- **A drawn element is never recoloured or rescaled**; it sizes itself via `height=` and
  its colours carry meaning. `_drawn_shape_height` converts a shape's `scale`
  (a multiplier on a ~2-unit primitive) into a height so relative sizing survives.
- **A simulation that cannot be ANIMATED is DRAWN as a still** before it degrades — the
  old path set `type: "shape"` and got a bare circle.

**Upstream half:** `SHAPE_CONTENT_RULE` (one shared constant, both prompts) says name the
OBJECT not the primitive, and `_content_free_shapes` counts violations into `[ELEMENTS]`
so the prompt change is judged by a number. Both cache versions bumped — without that the
cached board keeps its `"circle"` elements and the fix silently doesn't apply.

**Open:** cost is now 1 call per distinct object (cached), so a board of 16 distinct
objects is 16 calls on first sight of that topic — measure it over a batch before
deciding whether a cap is needed. And the drawings are judged only by the verifier
(parts, containment, it runs); nothing checks that the drawing *looks like the subject*,
which is the same blind spot `icon_match_strength` exists for on the icon side.

### F. Render & repair loop — L3 (2026-07-20: repair now covers the production path)
*Grade earned, not assumed:* repair reaches the default multi-scene path scene-scoped,
losers are never left on disk, and the whole thing was exercised end-to-end on a real
lesson video (§3b run 6: 4 scenes, 84s, 0 violations) — not just in the harness. It is
**not L3+** while the error-fingerprint/resolution index (gap 3) is still missing.
**Have:** parallel per-scene renders + ffmpeg concat with sequential fallback;
dry-run probe with TTS stub (fast, free) measuring overlap / clipped text /
text-over-shape; LaTeX error markers → deterministic MathTex→Text retry;
`_repair_overlaps` accept-only-if-better with original-video fallback; render
timeout; artifact sweeps.
**Gaps (re-audited 2026-07-20, code-verified):**
0. ~~**The default parallel path never repairs.**~~ — **fixed 2026-07-20 evening**,
   together with gap 1, by scene-scoped repair (below). The parallel fast-path now
   runs the repair pass and reports real `repair_rounds` / `scenes_repaired` in the
   sidecar instead of a hardcoded `repair_rounds=0`.
1. ~~Repair re-renders the **whole** video even when violations are in one scene.~~
   — **fixed 2026-07-20 evening.** `_run_parallel_render` was split into
   `_render_scenes_parallel` (render only, clips left on disk) +
   `_concat_scene_clips` (ffmpeg concat, reusable) + `_repair_scenes_parallel`
   (scene-scoped accept-if-better). `_run_render_job` now does
   render → concat → repair offending scenes → re-concat only if a scene actually
   improved, keeping the pre-repair concat until a better one exists.
   **Design note — better than this doc's original plan:** the plan was to parse
   the `[Scene N]` log prefixes to attribute violations. Unnecessary:
   `_render_scenes_parallel` returns `per_scene_logs` index-aligned with
   `scene_scripts`, so attribution is structural rather than string-parsed. The
   `[Scene N]` prefix is now built at the *end* (for the job log / sidecar) from
   post-repair logs, so `violations_remaining` reflects the shipped video.
   `_repair_overlaps`' whole-video body stays as the sequential/batch path, and
   both paths now share one `_overlap_error_report(violations)` brief.
2. ~~**Repair-candidate mp4s leak**~~ — **fixed 2026-07-20 evening** via
   `_discard_video(url, keep=…)`: after every round the loser is deleted
   (rejected → the candidate; accepted → the superseded previous file), never the
   currently accepted path, tolerating missing files, and dropping the `.json`
   sidecar with it. **A third leak site was found while fixing this and is also
   closed:** when a parallel render *partially* failed, the scenes that DID render
   were left in `static/videos` forever as the caller fell back to sequential —
   `_render_scenes_parallel` now discards them. Correction to this doc's original
   test spec ("static/videos must contain exactly one new mp4"): the right contract
   after a *rejected* round is **zero** net new mp4s, since the candidate rendered
   and must then be deleted — that is what the harness now asserts.
   **Evidence:** the 8 sidecar-less mp4s (Jul 19–20, latest 19:51) all predate the
   fix; the post-fix harness run at 20:00–20:09 produced 14 renders and left zero
   leaked files behind. The 8 historical ones are still on disk — junk to sweep,
   not live failures.
3. The remote's error-fingerprint/resolution index (learn-from-past-failures) was
   dropped in the July 19 merge except the LaTeX path — worth restoring as designed:
   fingerprint → known fix → pre-patch before first render. **Now the only
   substantive gap left in stage F.**
4. ~~**The parallel path was unreachable from production, and broken when reached.**~~
   — **both fixed 2026-07-20 evening**, found by actually running a lesson video
   end-to-end rather than by reading code. Two independent faults stacked:
   - `ce/stem_animation.py::_generate_code` **discarded `scene_scripts`** from the
     `/api/generate_code` response, so the lesson pipeline — the real production
     caller — never sent them and every video took the sequential single-script
     path. The parallel path (and therefore the whole of gap F0/F1's scene-scoped
     repair) had been dead code for production. Now forwarded through
     `_compile_video`.
   - Forwarding it immediately exposed the second fault: **3 of 4 scenes failed to
     render.** Per-scene scripts hold only their own scene's `id→var` map, and both
     emitters fall back to the *raw storyboard id* on a miss — so a cue saying
     "fade out the previous scene's props" emitted `FadeOut(container)`, a
     NameError. The master script never showed it because all scenes share one
     `construct()` namespace. Fixed by `_drop_cross_scene_events` (structured
     `animation_events`) and `_drop_foreign_id_calls` (legacy free-text `event`):
     in an isolated per-scene render an element from another scene isn't on the
     canvas, so the event is dropped, loudly, to stderr. The Dalton storyboard
     dropped 29 such events across scenes 2–4. Pinned by 6 new checks in
     `test_event_sanitize.py` (20 total), including one asserting the master path
     still KEEPS the cross-scene hide — it is legitimate there.
   - **Payoff, measured on the same storyboard:** 406s sequential → **84s** total
     (4 scenes merged in 7.1s), and **4 layout violations → 0** — per-scene renders
     start from a blank canvas, so the stale-text-from-a-previous-scene overlap
     class cannot occur by construction. The repair loop had failed to fix those
     same 4 violations in the sequential run.
   - **Generalizable lesson: a fallback that works is how a broken fast path hides.**
     The parallel path failed 3/4 scenes and the sequential fallback silently
     produced a fine video every time, so nothing ever surfaced. Worth an explicit
     counter/log whenever a fallback fires (see stage H's cost/ops work).
**Improve:** restore the resolution index (gap 3); attribute errors per their
`error_attrib` pattern (*name the failing system, say the fix* — "Sarvam quota"
vs "LaTeX" vs "layout" in the job error).
**Render errors need CLASSIFICATION before repair — SHIPPED 2026-07-21 night.**
Observed during the Vision-QA live test: the audio outage killed a scene, and the
runtime self-heal then fed the TTS traceback to the LLM repair agent, which rewrote
code that was never broken and re-rendered into the same outage.
`_classify_render_failure(logs)` now returns **`infra` | `latex` | `code`** and only
`code` reaches `repair_code_with_gemini`; `infra` (TTS/HTTP/transport/quota markers)
fails loudly, names the failing system in the job error, and tells the operator to
retry once the provider recovers (the shared TTS cache makes that retry cheap).
`infra` deliberately wins over a co-occurring LaTeX marker — outages cascade, and the
LaTeX heal can't fix a dead endpoint either. Pinned in `test_vision_qa.py` §E.
**Still open (the generalization):** attribute *within* `code` too, per the
`error_attrib` pattern — name the failing subsystem in the job error rather than
handing the agent a raw traceback.
**Related gap noticed 2026-07-22 while diagnosing a slow repair phase — no wall-clock
guard on the LLM edge.** `_call_openai_compatible` passes `timeout=120.0`, but
`call_gemini_with_fallback` uses the google-genai SDK with **no timeout configured**,
so if the provider order ever reaches Gemini and that socket stalls, the render job
thread waits indefinitely with nothing in the logs (the job stays `running` forever —
there is no stale-job detection either, roadmap §H). Two cheap fixes: pass an
`http_options` timeout to `genai.Client`, and give `_run_render_job`'s repair phases a
deadline so a wedged provider degrades to "keep the incumbent" instead of hanging.
*Note on method:* this looked exactly like a hang (0% CPU, thread blocked on a Google
TLS socket, no new log lines for minutes) but was actually just slow — sequential scene
re-renders. **A thread dump distinguishes "slow" from "hung"; log silence does not.**

### G. Measurement & QA — L2.5
**Have:** per-beat probe (3 violation classes, false-positive-safe by design),
19-check acceptance harness with real renders + repair state machine,
`test_layout_safety.py` for the deterministic layer, sidecar verification metadata.
**Gaps:** no *visual* QA — everything asserts geometry, nothing looks at pixels;
no narration QA at all; no fidelity-to-source QA.
**Improve:**
- **Adopt their scoring rubric** (R1–R8 / figure principles): per-video scorecard
  in the sidecar — layout violations (have), text-render errors, fidelity
  spot-checks, contrast violations (their `contrast_violations` check is directly
  portable — the dim `a²+b²=c²` frame we captured would have failed it).
- **Frame audit as a tool (Vision QA, "Agent 9") — SHIPPED 2026-07-21 night**
  (`app/pipeline/vision_qa.py` + `render._run_vision_qa`, flag `VISION_QA=1`,
  allowlisted; knobs `VISION_QA_FRAMES`=6, `VISION_QA_REPAIR`=1,
  `VISION_QA_REPAIR_ROUNDS`=1, `VISION_QA_MODELS`): ffmpeg extracts evenly-spaced
  640px frames → ONE multimodal call (`app.llm.call_vision_llm`, OpenRouter,
  gemini-2.5-flash chain) against a seven-class whitelist (clipped/colliding/
  unreadable text, crowding, dead-frame, low-contrast, broken-hierarchy) → findings
  lenient-parsed then shape+whitelist gated, timestamps snapped to frames actually
  sent, emitted as `LAYOUT_VIOLATION: vision-<class> t=<s>s …` lines — a distinct
  class namespace, so `_overlap_violations` (geometric) NEVER counts them and
  `violations_remaining` stays honest. Repair: sequential path runs accept-if-better
  (candidate must render, must NOT raise the geometric count, and must strictly
  reduce vision findings on a metered re-critique); parallel path is
  measurement-only in v1 — findings land in the sidecar as `vision_findings` and
  the job's `vision_report` (scene-scoped vision repair via timestamp→clip
  attribution is the v1.1 follow-up). Non-fatal at every step (no key / ffmpeg
  error / refusal / bad JSON ⇒ zero findings). Pinned by `test_vision_qa.py`
  (19 checks, real ffmpeg on a synthetic clip, all seams stubbed).
  **First live run (2026-07-21 night, refraction, 6 scenes, parallel path):**
  sidecar `{repair_rounds: 4, violations_remaining: 3, scenes_repaired: 1,
  vision_findings: 6}` — the vision call flagged all 6 sampled frames
  `vision-dead-frame` ("mostly empty space with minimal text and a simple
  rectangle"), and a manual frame pull at t=46s CONFIRMED it: one small glass-slab
  box + three labels in ~85% black dead space, no ray drawn. Precision verified;
  and the finding routes UPSTREAM — sparse frames are a stage-B/D composition gap
  (storyboard richness / director enlarge-to-fill), not something the code-repair
  agent can conjure content for. That is the §3c "sparse frames" class, now
  measured automatically instead of by hand.
  **Scene-scoped vision repair SHIPPED 2026-07-21 night** (was listed here as the
  v1.1 follow-up): `_attribute_vision_findings` maps each finding's concat timestamp
  back to the clip whose window contains it (ffprobe durations, timestamps rebased to
  scene-local time so the repair brief matches the script being edited), and
  `_repair_scenes_vision` rewrites ONLY those scenes. Note the asymmetry with the
  geometric loop: probe measurement is free, so overlap repair accepts per scene;
  a vision critique is **metered**, so vision repair accepts at the **concat** level —
  re-concat once, re-critique once, accept only if total findings strictly drop.
  Each scene candidate must additionally not raise that scene's geometric count.
  Unattributable findings (missing clips/durations) stay report-only rather than
  guessing a scene to rewrite. Pinned in `test_vision_qa.py` §G/§H.
  **First live exercise of the full loop (optical fibre, 2026-07-22):** Vision QA found
  4 findings on the concat, attributed them to 4/5 scenes, and repaired scene-scoped —
  scene 2's candidate was **rejected by the geometric non-regression guard** ("vision
  repair added geometric violations"), the re-concat critique returned 4 findings again
  (no improvement), so the whole vision round was rejected and the ORIGINAL concat
  shipped. Sidecar: `{repair_rounds: 1, violations_remaining: 0, scenes_repaired: 1,
  vision_findings: 4, voice_degraded: 24}`; the rejected candidate concat was deleted
  and the run left **zero net new artifacts** (23 mp4s after, vs 28 mid-run; the 8
  sidecar-less ones are the documented Jul 19–20 historical set). Both safety
  properties — never lose the incumbent, never leak a loser — held on a real render.
  *Cost note:* this vision round spent 4 LLM rewrites + 4 scene re-renders + 1
  re-critique and bought nothing on this board. The serial-repair fix above and the
  frame-sampling fix in §D are both prerequisites to enabling `VISION_QA` by default.
  **Ordering trap found while wiring it:** the parallel path discarded its clips
  *before* the vision stage, so attribution would have silently returned None forever
  and scene-scoped repair would have been dead code — the P6 "a working fallback hides
  a broken fast path" shape, caught in review this time rather than in production.
  The clip discard now happens after the vision stage.
  **Known cost (v1, measured on the optical-fibre run):** flagged scenes are repaired
  *sequentially* — 4 flagged scenes meant 4 LLM calls + 4 full scene re-renders back to
  back, which dominated wall-clock. `_repair_scenes_parallel` has the same shape, so
  the fix serves both: rewrite all flagged scenes first (LLM calls are independent),
  then re-render the candidates through `_render_scenes_parallel` instead of one at a
  time. Worth doing before Vision QA is enabled by default.

### H. State, ops & cost — L1  ⟵ biggest operational gap
**Have:** in-memory `RENDER_JOBS` (dies with the process), sidecars per video,
`/timeline` gallery with verification badges, WebSocket job status. Since
2026-07-20 night also: **per-job `env_overrides`** on `/api/compile_video` and
`/api/batch_render_and_merge` (allowlisted repair/render knobs, process-global
last-writer-wins — a single-user debug/bulk affordance, not job isolation), and
the debugger's compile path now defaults through the real server pipeline
(`compile_mode="server"` in `trace_logger.py`) instead of its in-process
compile that bypassed repair — the sandbox also stopped hardcoding
quality="h"/widescreen. The bulk runner's `bulk_runs/<run_id>/` dirs are a
first cut of the per-run-folder idea below (storyboard + code per topic,
resumable), though renders still land in the shared `static/videos/`.
**Gaps:** no durable job registry (a crash loses "what was running"); no *stale*
detection; **no cost tracking at all** — we cannot answer "what did this video cost
in LLM + TTS calls"; no per-run folder (artifacts scatter across temp_renders/,
static/videos/, media_*).
**Tuning-surface gap (2026-07-30 audit, map in `docs/tuning.md`):** the tuning
levers exist but the production paths can't reach them — `ce/stem_animation.py`
hardcodes `quality:"l"`/widescreen and sends **no `env_overrides`** (every
lesson video renders at server defaults, 480p15), and the sandbox UI exposes
only 4 of the 11 allowlisted knobs (no `VISION_QA*`, `VISUAL_DIRECTOR`,
`LAYOUT_REVIEW`, `PARALLEL_RENDER_WORKERS`). Closing both is small and makes
every A/B experiment reachable from the tools people actually use.
**Improve (their state model, nearly verbatim):**
- Persist jobs to disk (`jobs.json`), one status vocabulary
  (`queued/running/done/failed/stale`), stale = `running` older than N minutes,
  surfaced in `/timeline`'s active-jobs banner but **never auto-re-run**.
- **Cost ledger**: route every metered call (storyboard LLM, critic, codegen,
  repair rounds, TTS) through one tracker writing cumulative `cost.json` per video;
  record cache hits at would-have-cost; unknown cost renders as unknown, never $0.
  Their tests to copy: *cached re-render is not free* and *unknown ≠ $0*.
  **Cheapest path (2026-08-15 audit): don't build the ledger — wire the lab
  into the one that exists.** `ce/usage.py` is already a real per-build
  token+USD/INR ledger (record/total/merge, `modelcfg.PRICING`) wired into
  `ce/agents.py`/`imagegen`/`builder` — but the lab server reports no usage
  back over HTTP, so `ce/videos_build.py:102`'s `usage.total()` reads ~0 for
  every video. Have each lab response (and the sidecar) carry per-call usage;
  ce merges it, the lab writes `cost.json` beside the mp4, `/timeline` grows a
  cost badge. Uncached call sites to cover: codegen, Layout-QA critic, repair
  rounds, screen ideator, scene writers (none of these is cached today —
  every repair round is fresh spend).
- **Per-run folder** `runs/<topic-hash>/` holding storyboard.json, code.py,
  scene scripts, violations, frames, cost.json, final.mp4 — local-first, never
  deleted by sweeps, resumable (only missing artifacts regenerate).

### I. Batch & review — L2 (2026-07-20 night: manifest-driven bulk runner shipped)
**Have:** `/timeline` (review), ce/ loop over lesson nodes (sequential, no resume),
and — new 2026-07-20 night — **`stem_animation_lab/bulk_runner.py` + the `/bulk`
page**, ported from the NLM `bulk_orchestrator` pattern: atomic
`bulk_runs/<run_id>/manifest.json` as the source of truth (one row per topic,
status `pending/storyboard/codegen/render/done/failed`), per-topic stage caches
(storyboard.json / code.json) so resume re-bills **zero** LLM calls, topic-level
thread pool (`parallel`, default 2; the server's RENDER_EXECUTOR throttles
renders), dry-run that persists and spends nothing, retry-failed that reuses
stage caches, CLI (`plan.json` / `.txt` / `--resume` / `--force`) and web form
with per-run settings incl. allowlisted `env_overrides`. Renders go through
`/api/compile_video` (scene_scripts forwarded), so repair/sidecars//timeline all
apply and no new `compile_manim_code` caller exists.
*Grade evidence:* stubbed-server engine harness (fresh run 2/2, resume with zero
extra calls, cache-first retry of a failed row, error rows don't kill the run) +
live TestClient route checks. **Not yet exercised on a real multi-topic render
end-to-end** — do that before trusting it at L2.5 (the 3b lesson: composition
faults only show up on real runs).
**Improve:** retry only rate-limit-shaped errors with exponential backoff + abort
signal; provider failover; surface bulk manifests on `/timeline`; a real-run
grade audit.

### J. Editor UX (Studio) — L2 (2026-07-31: first cut of the editor SHIPPED; was L1)
**Design doc:** `docs/studio-editor-design.md` (+ visual pitch `studio_proposal.html`,
repo root, also published as a claude.ai artifact). Original grade evidence:
2026-07-30 code audit of every UI surface (`static/*.html`, `app.js`, `app/api/*`,
sandbox, ce/ Streamlit) — L1 because the UI worked but was a one-shot black box
with capabilities scattered across four disconnected surfaces.
**Shipped 2026-07-31 (grade → L2, verified by a live parallel-path render through
the new flow):** `/studio` (`static/studio.{html,css,js}` + `app/api/voices.py` +
route in `api/pages.py`) — brief → storyboard → scene rail (blueprint SVG thumbs
drawn from the IR, drag-reorder, add/duplicate/delete) → per-scene inspector
(Content: description/composition/elements; Motion: entrance/exit pickers matching
`_ENTRANCE_ANIMS`/`_EXIT_ANIMS` + per-cue `animation_events` chips with targets
scoped to the scene's own element ids; Audio: per-cue text edit + ▶ audition +
voice/persona/language; Style: layout_template, wait_time, style/background/
quality/aspect) → render via `generate_code` + `compile_video` **with
`scene_scripts`** (parallel path + scene-scoped repair) → WS progress with poll
fallback → Advanced drawer (verification report / storyboard JSON / code / logs).
Dirty-scene tracking is signature-based (scene JSON + settings) so the render
button says what changed; a failed render keeps the previous video (never-lose
carried into the UI). Projects persist in **browser localStorage** (cap 20) and an
in-flight render is resumable on reopen via the stored job id. P0 wiring debt from
the list below: (a) scene_scripts now forwarded by BOTH UIs, (b) `err.detail` read
everywhere, (c) `/api/voices` is the source of truth (Studio uses it; the classic
`app.js` mirror still exists — remove on next classic-UI touch), (e) the WS
endpoint has its first real consumer. `/api/tts/preview` (a P2 item) landed early:
disk-cached, strips pacing tags, honest `note` when Sarvam is absent and the
preview falls back to Gemini — verified live (fresh synth + cache hit).
**Follow-up shipped 2026-08-01 — long LLM stages are polled, not held open.**
First real use surfaced the failure this design had not accounted for: the browser
showed `NetworkError when attempting to fetch resource` while the server was *still
working and eventually succeeding*. Root cause was not the network — `/api/generate_code`
is synchronous, the codegen chain took minutes (see the new §4 routing row on reasoning
models burning the token ceiling), and the browser abandoned the open fetch. Uvicorn
logs a request only on completion, so the diagnostic signature is **pipeline work in
the logs with no matching `POST … 200 OK` line**. Shipped `app/api/tasks.py`:
`POST /api/tasks/storyboard` / `POST /api/tasks/codegen` return a task id immediately
and `GET /api/tasks/{id}` is polled (own `TASK_EXECUTOR`, so a codegen never occupies
one of the 2 render workers). A thread-id→task-id log handler attaches `app.llm` /
codegen / transpiler records to the task, so the UI shows *which model is being tried
and why it fell through* instead of a frozen spinner — the "long runs show progress"
rule, applied to the stage that most needed it. Poll misses are tolerated (8
consecutive) so a blip doesn't kill a live task. The sync routes are untouched; the
classic UI and `ce/` still use them, and are still exposed to the same timeout.
**Verified live:** a codegen task ran 74s through polling and returned 5 scene scripts,
with the model-attempt trail visible throughout.
**Still open (the L3 gap):** server-side project store (§H per-run folder) so
projects outlive the browser; per-scene re-render + concat route (today an edit
re-renders the whole video — TTS cache keeps unchanged cues ₹0 but scene renders
re-run); **edited storyboards bypass the storyboard gate** (they go straight to
codegen — the shape/language gate runs only at generation; a PATCH-style
server-side validation is the fix); AI edit box; full sandbox absorption (the
drawer covers report/JSON/code/logs but not repair-round diffs or cost).
**Have:** lab page = 13-knob sidebar + one Generate that runs storyboard → preflight
→ codegen → compile unattended (`app.js:330-492`); storyboard read-only in the
browser — the ONLY editable intermediate is the Manim Python textarea (backwards for
the audience); `/timeline` read-only; `/bulk`; Streamlit sandbox is the sole home of
voice audition, repair history, cost readouts, env knobs; ce/'s `_video_view` has the
only per-unit regenerate.
**Wiring debt, measured (= the P0 list — each a bug independent of any redesign):**
(a) the browser never forwards `scene_scripts` (`app.js:506-510`), so **every web
render takes the sequential path and never gets scene-scoped repair** — the parallel
path is dead code for browser users, the same class as §F4's "production never used
the fast path"; (b) client reads `err.error` but FastAPI sends `detail` — server
errors are silently swallowed; (c) voice lists hardcoded in `app.js:282-313` as a
manual mirror of the sandbox's table; (d) asset "Re-test" fixes patch the storyboard
in browser memory only (no storyboard GET/PUT — corrections die with the tab);
(e) the WS job-status endpoint (`render_routes.py:106`) is used by NO page.
**North star:** scene-first **Studio** (scene rail / preview canvas / inspector with
Content·Motion·Audio·Style tabs mapped 1:1 to `StoryboardScene` fields), **Library**
grown out of /timeline (cards open in Studio; bulk runs as grouped rows), sandbox
absorbed as an **Advanced drawer**. Edit loop: PATCH storyboard IR → existing gates
(shape + language heal) → dirty-scene hash → per-scene candidate render →
accept-if-better → re-concat; the shared TTS cache makes unchanged cues free, so an
edit costs ~one cue + one scene render. AI edits are prompt→IR-patch, never code.
Depends on the §H per-run folder (generalize `bulk_runs/<id>/` into a project
folder; keep per-scene clips instead of discarding them post-concat).
**Phases:** P0 wiring debt (day) → P1 glass box + project persistence (week) →
P2 audio editing + `/api/tts/preview` (week) → P3 content/motion editing + scene
reorder (1–2 wk) → P4 AI edits + Advanced drawer. Full detail incl. proposed API
surface in the design doc.
**Invariants carried over:** never lose a verified artifact (edits are candidates);
code owns structure, models own content; metered edges visible in the UI (₹0-cached
chips); validation before spend; per-scene progress over the WS endpoint.

---

## 2. Priority order (impact ÷ effort)

> **Product view:** [`docs/improvement-timeline.md`](improvement-timeline.md) (2026-08-22)
> groups the open rows below into seven capability milestones (M1–M7) stated in product
> language — what a person can newly do or trust at each step, and why the order is a ladder
> rather than a menu. Its §5 maps each milestone back to the rows here. This table stays the
> source of truth for grades and evidence; when the two disagree, this one wins.
> **Problem-space view:** [`docs/problem-decomposition.md`](problem-decomposition.md)
> (2026-08-22) decomposes the problem independent of the code — 19 links, the owner of each
> hidden decision, the option space per stage, and the representation ladder. Its register
> names three rows as deciding the next version: the per-run record + cost (§H rows 5/7),
> composition + sync (§D/§C rows 11/27 + the balance pass), and the screen plan on by
> default (§B-deep). Measured there and not yet here: `relation: "inside"` is used by
> **0/876** cached elements and `connects` by 23/876; `ProcessFlow`/`BeforeAfter` appear on
> **0/148** cached scenes; the shared TTS cache directory holds **0 files** (unattributed —
> check before assuming repair re-renders bill zero audio); 23/46 sidecars ship with ≥1
> residual violation.

| # | Improvement | Stage | Why first |
|---|---|---|---|
| 1 | ~~**Data-space coordinates (`c2p`) + `Dot` points in transpiler**~~ | D | **Shipped 2026-07-19** (verified in code 2026-07-20: `_mark_c2p`/`c2p` emission transpiler.py:487-518, `Dot(radius=0.1)` line 418). §D recorded it; this row was just never struck. |
| 1a | ~~**Overlap repair on the parallel path (scene-scoped)**~~ | F | **Shipped 2026-07-20 evening.** `_render_scenes_parallel` + `_concat_scene_clips` + `_repair_scenes_parallel`; closed F0+F1 together. Only flagged scenes re-render, accept-if-better per scene. Pinned by 8 new checks in `test_overlap_probe.py`. |
| 1b | ~~**Repair-candidate mp4 cleanup**~~ | F | **Shipped 2026-07-20 evening** (`_discard_video`). Also closed a third leak site (clips orphaned by a partially-failed parallel render). Post-fix harness run: 14 renders, 0 leaked. |
| 2 | ~~**Shared content-addressed TTS cache**~~ | C | **Shipped 2026-07-19** (`viz_helpers` shared gate + `test_tts_shared_cache.py`). Repair rounds re-billed the most expensive stage; now ₹0. |
| 3 | ~~**Axes-aware zones + label slots**~~ | D | **Shipped 2026-07-19** (`_seed_axes_zones`/`_fix_label_slots` + `test_axes_zones.py`; probe A/B 4 → 0). Prevented by construction the collisions the probe had to catch and the LLM had to repair. |
| 3a | ~~**Screen management: split-screen instead of pile-up**~~ | D | **Shipped 2026-07-20** (`_maybe_minimize_diagram` widened + `test_minimize_split.py`, 14 checks). Trigger was math-only and fired on ZERO scenes of live job `bpipueek6` — real storyboards carry derivation steps as `text`. Now: any math, or ≥2 free-standing text-ish elements; never cue 0, never diagram-anchored labels. |
| 3b | ~~**viz_helpers import guard (NameError at render)**~~ | E | **Shipped 2026-07-20.** `sanitize_generated_code`'s `"from viz_helpers import" not in code` check was satisfied by the prompt-requested selective `import UniversalTTSService`, so `auto_fit_scene` was undefined AND `config.font` was never injected. Every such render burned an LLM repair round on a defect codegen created. Now regex-normalized to the star import. |
| 4 | **Script critic before TTS** | C | Cheapest gate protecting the costliest spend; direct port. |
| 5 | **Cost ledger + durable job store** | H | Can't optimize what isn't measured; small, self-contained. |
| 6 | ~~**Scene-scoped repair re-render**~~ | F | **Shipped 2026-07-20 evening** — same change as 1a (this row was the duplicate the merge rule warns about; kept for ranking history). |
| 7 | Per-run folders + resume | H | Foundation for batch. |
| 8 | ~~Vision-LLM frame audit + contrast check ("Agent 9")~~ | G | **Shipped 2026-07-21 night** (`vision_qa.py` + `_run_vision_qa`, 19-check harness; details in §G). Parallel path measures into the sidecar; sequential path repairs accept-if-better with a geometric non-regression guard. Remaining: scene-scoped vision repair on the parallel path (v1.1). |
| — | ~~Modularize the video engine (`app.py` → `app/` package) + agent scaffold~~ | 0 | **Shipped 2026-07-21.** 3995-line monolith → stage-aligned package (frozen at `app_legacy.py`); pragmatic classes (`JobStore`, `StoryboardCache`); `pipeline/` stage protocol + Visual-Director/Vision-QA stubs. Behavior-preserving: 142 deterministic checks green. Enables 8 + the Director work without grafting into a monolith. |
| 9 | Smart-shape routing (svg/builders before Circle fallback) | D | Visual richness. |
| 10 | ~~Batch manifest runner~~ | I | **Shipped 2026-07-20 night** (`bulk_runner.py` + `/bulk`, stub-harness verified) — landed before 5+7 because the user asked for it directly; the ranking's "after 5+7" reasoning still applies to what remains (cost ledger integration, backoff/failover, real-run audit). |
| 11 | Per-element narration beats (sync by construction) | C | Biggest UX win, biggest change — do after 2+4. **Middle path found 2026-08-15:** manim-voiceover **bookmarks** (`<bookmark mark='e3'/>` in the cue text + `tracker.time_until_bookmark`) give element-level sync WITHOUT splitting TTS per element — one clip per cue stays (shared TTS cache keys unchanged, so nothing re-bills), but each element's entrance fires at the word that names it instead of at `_TIMING`-table fractions. `remove_bookmarks` is already imported in the transpiler and unused — the plumbing half-exists. Full per-beat clips (the NLM region-wise shape) stay the endgame; bookmarks are the 20%-effort/80%-value step. |
| 12 | ~~TTS resilience: retry-before-failover + keyless voice + visible degradation~~ | C | **Shipped 2026-07-21 night** after a live outage cost a full sequential re-render. `test_tts_resilience.py` (14). |
| 13 | ~~Render-failure classification (infra / latex / code)~~ | F | **Shipped 2026-07-21 night.** Stops the repair agent rewriting correct code during a provider outage. |
| 14 | ~~Scene-scoped vision repair (parallel path)~~ | G | **Shipped 2026-07-21 night.** Work per scene, acceptance per artifact (a critique is metered). |
| 15 | ~~Dead-frame at source (storyboard richness rule 4b + enlarge-to-fill)~~ | B/D | **Shipped 2026-07-21 night.** First board after the change: 5 scenes at [4,8,6,7,5] elements (avg 6.0) vs the sparse board that produced 6/6 dead frames. |
| 16 | ~~Camera language: `focus` spotlight~~ | D | **Shipped 2026-07-21 night**, render-verified. Zoom/pan deliberately excluded until the probe is frame-aware (see §D). |
| 17 | Frame-aware probe (unblocks camera zoom/pan) | G | The probe measures against a fixed `config.frame_width/height`; make it read the live camera frame, then `MovingCameraScene` becomes safe to adopt. |
| 18 | ~~**Visual theming: style-profile → concrete canvas/palette/accent**~~ | D | **Shipped 2026-07-27.** The UI's style dropdown was dead on the deterministic path (pure-black canvas, flat-white shapes, YELLOW accent for every profile). `theme.py` maps the five profiles to a themed dark canvas + cohesive shape palette + accent, wired into both transpiler paths; render-verified + `test_theme.py` (28). Open v2: themed axes, cross-scene transitions, font family (see §D). |
| 19 | **Post-gen tuning surface** (`docs/tuning.md` shipped 2026-07-30; close the gaps: ce sends no `env_overrides` + hardcoded quality `l`, sandbox exposes 4/11 knobs, `SCOPE_VERSION` + cache-key blind spots) | H | Cheap; makes every later experiment reachable, measurable, and ₹0-repeatable against cached boards. |
| 20 | **Chapterized long-form (10–15 min)** — chapter outline → per-chapter storyboards threaded with brief + running summary → bulk-style chapter manifest → concat | B/H/I | Design in §6. Depends on 4 (script critic — 10× TTS spend), 5 (cost ledger), 7 (per-run folders), and §G's parallel scene repair; ship 19 first so chapter tuning is cheap. |
| 21 | ~~**Editor P0 wiring debt: browser forwards `scene_scripts` + read `err.detail` + nav header + `/api/voices`**~~ | J | **Shipped 2026-07-31** with the Studio first cut. Classic UI now takes the parallel path + scene-scoped repair; server errors surface verbatim. Residual: `app.js` still carries its local voice table (Studio uses `/api/voices`). |
| 23 | ~~**Deep storyboard: source intake + screen ideator + one writer per screen**~~ | A/B | **Shipped 2026-08-15** (`DEEP_STORYBOARD=1`, default off) after "less content and not good flow". Splits the INPUT, never the output; the screen plan's `must_show`/`must_say` make thinness *countable*. `test_deep_storyboard.py` (67). Next: enforce coverage with a targeted single-screen rewrite, and surface the plan in Studio before the fan-out. |
| 24 | ~~**Generated simulations (`type: "simulation"`)**~~ | D | **Shipped 2026-08-15.** The one place an LLM writes Manim — a bounded `build`/`animate` pair per element, verified by stepping the animation with no renderer (~1s). Closes the "a static picture of a moving thing" class that `sustain` and the Motion Director could not reach. `test_simulation.py` (66, real manim). |
| 25 | **Fidelity spot-check (cited facts survive to narration)** | A/G | Sources are now citable and `must_say[].cite` records provenance (row 23), but nothing audits that the narration kept the fact. The NLM pilot bar is ≥95% of N sampled facts traced back to a chunk. Cheap: it reads artifacts that already exist. |
| 26 | ~~**Duration contract**~~ (`target_duration_s` → scene count + narration word budget, `[DURATION]` log + `rendered_duration_s` sidecar field) | B/C | **Shipped 2026-08-15** (measured, not enforced). `target_duration_s` on `StoryboardRequest` → `duration_directive`/`duration_scene_budget` in `app/storyboard.py` (ONE helper, used by the single-call prompt AND the deep ideator via `plan_screens(target_seconds=…)`); ce/ now sends its computed `spec["duration"]` (the knob used to die at the HTTP boundary). Cache: `dur:<s>` joins the key variant ONLY when set — unset requests keep their exact prior keys, pinned by `test_duration_contract.py` A9. `[DURATION]` logs target vs word-count estimate (warns past ±20%); `_write_video_sidecar` ffprobes `rendered_duration_s` to close the loop. Remaining: enforcement (trim/regenerate an off-budget board) once a few live runs show how far the drift actually runs. |
| 27 | ~~**Composition archetypes on `layout_template`**~~ + variety rule | B/D | **Shipped 2026-08-15** (first slice). `ProcessFlow` (mechanism left→right; first/last unpositioned elements pinned LEFT/RIGHT, middle stays with the allocator) and `BeforeAfter` (halves grouped left/right — states read as pictures, unlike SplitScreen's alternation) joined the Literal + `_apply_template_zones`; schema re-exported (`--regen`). `enforce_template_variety` (app/storyboard.py) RESETS the 3rd+ consecutive same-template scene to None — clearing, not swapping: code never invents a layout the model didn't ask for. Pinned by `test_duration_contract.py` B/C. Remaining: role-keyed archetypes for the other NLM kinds (relationship/graph, anatomy) and reconciling with `role`/`visual_kind` so there aren't three vocabularies. |
| 28 | ~~**Vividness floor**~~ (prompt floor + `sparse` metric) | B | **Shipped 2026-08-15** (measured, not enforced). The ideator's must_show block gained the floor (idea HAPPENING — object + action + outcome, source's REAL values; a lone emblem satisfies the count and still fails this) — a deep-prompt change, so `DEEP_VERSION` bumped (billing note; deep is default OFF). `coverage()` now reports `sparse` (<3 elements). Remaining: enforce via the targeted single-screen rewrite (§B-deep's open item). |
| 29 | ~~**TTS account-state failover**~~ | C | **Verified correct 2026-08-15, no change needed.** The NLM bug (a 402 aborting the whole chain) can't occur here: `_synthesize`'s per-tier `except Exception` hops the chain on ANY tier failure, and `_tts_post_with_retry`'s 402 fail-fast only skips same-provider retries — which is right, an empty balance is permanent for that vendor. |
| 22 | Studio P1+ (brief→review→render glass box, project folders, per-scene editing) | J | **Partially shipped 2026-07-31**: `/studio` covers brief→review→edit→render with per-scene *editing* (Content/Motion/Audio/Style), blueprint thumbs, WS progress, TTS audition, advanced drawer. Remaining for the full row: server-side project folders (do together with 5+7 — the project folder IS §H's per-run folder), per-scene *re-render* route, gate-validated storyboard PATCH, AI edits. |

---

## 3. Audit artifacts (2026-07-19 run)

- Generated code: transpiler+critic output showing scene-coord bug — every
  `move_to([x, y, 0])` on axes content.
- Frame evidence: point A labeled (−3,2) rendered off-grid; `|x₂−x₁|` label through
  the "3" tick; scene 4's y-axis through question + solution text; dim corner
  formula; stray detached points.
- The probe correctly models all of these as its three violation classes — the
  finding is that stage D should stop *producing* them, with the probe as auditor
  rather than primary defense.

---

## 3a. Audit artifacts (2026-07-20 re-audit — animation scope)

- Full deterministic suite green: **63/63** across five harnesses (overlap
  probe 19, axes zones 14, event sanitize 14, TTS cache 10, layout safety 6) —
  the code-owned layers hold; no regressions.
- app.py:1985-1997 read directly: the parallel fast-path returns before
  `_repair_overlaps` (new gap F0). Sidecars `user_vid` / `full_pipe_distance`
  show `violations_remaining: 0` with `repair_rounds: 0` — clean by
  construction, but any nonzero measurement on this path ships as-is.
- static/videos: 8 sidecar-less mp4s (Jul 19–20), two created during one
  harness run that day — gap F2's leak observed live.
- Animation census over 14 real generated scene scripts (temp_renders), 76
  `self.play` calls: FadeOut ×28, FadeIn ×34, Create ≈20, Indicate ×4 — only
  one `Write` / one `GrowFromCenter` / one `TransformMatchingTex`; every
  rate_func is `ease_out_elastic` (×85) → gap D6.
- The `audit_run` (11 violations) and `proof3` (14) sidecars both predate the
  07-19 21:06 axes-zones commit — historical evidence, not live failures.

## 3b. Audit artifacts (2026-07-20 evening — "explain Dalton's law" end-to-end)

The whole evening's findings came from one instruction: *make a video explaining
Dalton's law*. Every fault below was invisible to the test suite (63/63 green
before and after) and surfaced only by running the real pipeline and looking at
the output. **Rendering one real video is worth more than another round of code
reading** — the deterministic harnesses cover the layers they were written for
and say nothing about whether the stages compose.

Progression of the same request, each fix revealing the next fault:

| Run | Result | Fault found |
|---|---|---|
| 1 | HTTP 500 | `json_repair` missing from requirements |
| 2 | **2.9s**, 1 scene, cue cut mid-tag | truncation invisible: no `finish_reason` check; `json_repair` closed a truncated storyboard into valid JSON and cached it 48 h |
| 3 | **23.7s**, 1 scene, never states the law | `determine_scene_count` sized the lesson off source-text length → 1 scene, contradicting the storyboard stage's own "4–6 scenes" |
| 4 | **94.2s**, 4 scenes ✓ but sequential, 4 violations unrepaired | `ce/` discarded `scene_scripts`; production never used the parallel path |
| 5 | 4 scenes, 3 failed → fell back | per-scene scripts emitted bare cross-scene ids (`FadeOut(container)`) |
| 6 | **92.7s, 4 scenes, 0 violations, 84s total** | — shipped |

- Storyboard call went **800 → 6107 completion tokens** once the scene floor landed;
  at 8000 `LLM_MAX_TOKENS` a richer topic could now legitimately hit the ceiling —
  the new `finish_reason` check will say so out loud instead of truncating silently.
  **This materialized 2026-07-21:** `gemini-2.5-flash` produced `completion_tokens=8000
  of 8000` on a live topic (reasoning_tokens=0, so pure content) → discarded as
  truncated → fell back to `deepseek/deepseek-v4-pro`, which returned a clean but
  degenerate `finish=stop, 902-token` board with **no scenes** → the §3c shape gate
  500'd it. The very next retry of the same topic fit under the ceiling (6335 tokens)
  and shipped — a marginal boundary flake, not a hard break. **Fixed:** raised the
  `LLM_MAX_TOKENS` default **8000 → 16000** (`_call_openai_compatible`); good boards
  run ~6.3k, so this restores real headroom. Two residual weaknesses left as follow-ups:
  (i) the storyboard fallback (`deepseek`) has poor structured-JSON compliance and
  produces the degenerate board — a known trade-off noted at `app.py` OPENROUTER_STORYBOARD_MODELS;
  (ii) the shape gate runs **outside** `call_llm_with_fallback`, so a clean-but-empty
  response is not retried with the next model — it just 500s. Moving the gate inside
  the fallback loop (or reordering the storyboard chain off deepseek) would make the
  fallback actually protective.
- Sidecar for the shipped video: `repair_rounds: 0, violations_remaining: 0,
  animation_beats: 8, scenes_repaired: 0` — clean by construction, nothing to repair.
- Leak check: the 8 historical sidecar-less mp4s (Jul 19–20) are unchanged across
  every run above; the 4 scene clips of the final render were discarded on schedule.
- Full deterministic suite after all changes: **82/82** (overlap probe 32, axes zones
  14, event sanitize 20, TTS cache 10, layout safety 6).

## 3c. Audit artifacts (2026-07-21 — user review of the shipped Dalton video: "audio and composition issues")

Frame-extraction review (ffmpeg stills at 5–85s) plus the surviving per-scene
scripts in temp_renders. The probe/sidecar said `violations_remaining: 0` and it
was *right* — every defect below is a class the probe does not measure. What was
found, attributed upstream-first:

- **Language inversion (stage B — gate shipped 2026-07-21).** The cached storyboard
  had **8/8 cues in English and 7 on-screen element contents in Devanagari** — the
  exact opposite of the hybrid contract (Hinglish narration, English screen). The
  narration side had NO code-owned guard (the Devanagari→Hinglish transliteration
  stage passes English cues through untouched), and the on-screen side's guard was
  dead (next bullet). Audio symptom: `UniversalTTSService(language="hi-IN")`
  reading English sentences degrades pronunciation — the TTS language param
  describes the persona, not the actual script. **Shipped:**
  `storyboard_shape_problems(storyboard, persona=…)` now rejects, before the cache
  write (same pattern as the truncation gate): (a) Indic content in text/math
  elements under hybrid/en — unambiguous; and (b) hybrid narration where NO cue
  contains Devanagari or any romanized-Hindi function word (`hai/ke/mein/hum/…`)
  — deliberately conservative, since the gate runs post-transliteration where
  valid Hinglish is Latin-script; a single Hinglish cue passes the whole board.
  Pinned by `test_storyboard_gate.py` (26 checks, incl. the exact Dalton shape
  reporting both violations). **Update 2026-07-21 (later):** the gate's *on-screen*
  half now **self-heals** instead of only 500ing. A live hybrid run (`Refraction
  through a glass slab`) had the model emit **9 Devanagari on-screen labels** — the
  gate rejected all 9, hard-500. Root problem: the narration side is healed (cue
  transliteration) but on-screen element content had no equivalent pass. Shipped
  `normalize_onscreen_language(storyboard, persona, translate_fn)` — the mirror of
  the cue pass for `text`/`math` elements: it batches the Indic labels to one
  storyboard-tier LLM call that translates them to concise English (math notation
  preserved), and accepts a heal **only if it actually removed the Indic script** —
  a failed/bad heal leaves the original for the gate to reject, so we never trade a
  loud failure for a silent one. Verified end-to-end: the 9-label run now translates
  (`Glass Slab`, `Incident Ray`, `Normal`, …) and ships 200. The narration-inversion
  half (all-English cues under hybrid) still fails loudly — no code-owned romanizer
  exists for that direction, and inventing Hinglish from English is a content
  decision, not a normalization. The poisoned Dalton cache entry was deleted by hand
  2026-07-21.
- **Indic strip was quote-style blind (stage D backstop, fixed 2026-07-21).**
  `sanitize_generated_code` matched only `Text("…")`; the transpiler emits
  `Text({repr(content)})` and repr() single-quotes Devanagari — so the strip never
  ran on transpiled titles. Proof in one frame: a content string WITH an
  apostrophe got double-quoted by repr, matched, and rendered as `'-' ?` shrapnel.
  Now both quote styles match and punctuation-only leftovers strip to empty
  (blank beats junk). Pinned in `test_minimize_split.py` (20 checks). Note the
  consequence: on a contract-violating storyboard the backstop now yields
  *blank* headings — the real fix is the stage-B gate above.
- **Containment is not a placement primitive (stage D, open — call it D7).** Gas
  particles rendered ON and OUTSIDE their container box: the storyboard placed
  them with absolute coords near the container's absolute coords, and nothing
  ties a "particle" to the inside of its box. Weaker cousin of the D1 c2p lesson:
  *the LLM is still emitting geometry* for containment relationships. Approach:
  a `relative_positioning: {relative_to: X, relation: "inside"}` form the
  transpiler resolves to a position clamped within X's bbox (minus margin) —
  deterministic, no LLM.
- **Sparse frames** (t=25s: one tiny box top-left, rest of the frame empty while
  narration runs) — no measurement class for dead space yet; fold into the G
  frame-audit idea (a vision check would flag "90% empty frame mid-scene").
- The reviewed 1:34 file was the 20:45 **sequential-fallback** render; its scene
  scripts still contain the pre-fix cross-scene `FadeOut(container)` — historical
  confirmation of F4, not a live failure (the 20:52 concat render followed).

## 3d. Audit artifacts (2026-08-15 — first live run of the deep path, "Projectile motion")

One end-to-end run with `DEEP_STORYBOARD=1`, persona `en`, no supplied sources.
**510s total: storyboard 28s (1 ideator + 6 writers, parallel), codegen 190s, render
292s.** Output: `STEMAnimation_ced168c4.mp4`, 104.9s, 854x480, audio present, 26
animation beats, 2 repair rounds, 2 violations remaining, `voice_degraded: 0`.

**What the front half did well — this is the part the user asked for:**
- 6 scenes, **46 elements** (avg 7.7/scene) against a plan of 22 objects: `must_show`
  behaves as a **floor, not a ceiling** (screens planned 3-5, writers delivered 5-9).
- A real arc — `hook → build → build → turn → payoff → recap` — and `narrative_problems`
  clean: no cold opens, the anchor ("a basketball thrown at a hoop") present in all six.
- Zero degraded screens; every writer returned usable IR on the first try.

**What the frames actually showed — three defects, all found by LOOKING at the video:**

1. **The IR was rich; the frame was not, and no number said so.** `[DEEP] objects
   planned -> elements written` stops at the IR. Emitted-code census: 14
   `fetch_smart_svg`, **0 `fetch_real_image`**, **1 of 4** `simulation(`, 6 bare
   `Circle()`. Scene 1 rendered a clipped Text placeholder reading "ketball player
   shooting"; scene 6 was a title over three dimmed icons. **Fixed:**
   `_log_element_survival` (codegen_pipeline) now prints one honest line per render —
   `[ELEMENTS] 46 declared, 5 degraded to placeholders — image 0/2, simulation 1/4, …` —
   and shouts when an entire type resolves 0/N, because a whole tier failing is a
   provider problem, not a bad query.
2. **Wikimedia was returning 429 to every download.** The *search* API answered
   correctly and returned the right files; `upload.wikimedia.org` then rejected each
   fetch with `Your request does not comply with our robot policy`. Cause: their
   User-Agent policy requires a **contact URL or email**, and ours carried only a
   product name. One-line fix (contact URL added, `WIKIMEDIA_USER_AGENT` override) took
   the same two queries from **0/2 to 2/2**. Pre-existing §E bug; the deep path only
   made it visible by asking for images on a topic that has them.
3. **The simulation gate was misclassifying an ordinary mistake as a security event.**
   Only 1 of 4 simulations survived, and all three failures were *trajectory-tracing*
   descriptions that had reached for `TracedPath` — listed in the first cut alongside
   `open(`, so each was killed with **no repair round**. Split into two tiers (security:
   never retried; contract: rejected *with a brief*). Re-running the same four real
   descriptions: **1/4 → 3/4**, two of them now passing on attempt 1. The one that still
   fails does so honestly (`NameError: name 'height' is not defined` — `build`'s
   parameters used inside `animate`; a prompt line now pre-empts it) and degrades to a
   static visual with a warning, as designed.

**Open, with the measurement attached:**
- `SIM_GEN_REPAIR_ROUNDS` stays at **1**. The one remaining failure produced two
  *different* fixable errors in two attempts, so a third round would plausibly land and
  the result caches forever — but n=4 is too thin to move a default on a metered edge.
  Re-measure over a batch before changing it.
- **Simulations are uncapped per scene.** Scene 4 got two (a ball rolling off a table vs
  one dropped straight down) — legitimate for a comparison beat, but the single-call
  storyboard prompt says "at most ONE simulation per scene" and the per-screen writer
  prompt does not. That is a twin; one rule, one place.
- A degraded simulation becomes `type: "shape"`, whose prose head-noun ("a ball …")
  resolves to a bare `Circle()` — six of them in this run. Semantically empty, and worse
  than routing to the asset cascade. Fix belongs with §E's shape-resolution work.

## 3e. Audit artifacts (2026-08-15 evening — same topic re-run after the drawn-object work)

Same brief ("Projectile motion", `DEEP_STORYBOARD=1`, persona `en`), storyboard served
from cache, so this isolates **codegen → render**. Two runs, and the difference between
them is the whole lesson.

| | run A (14:20) | run B (15:00) |
|---|---|---|
| video | `STEMAnimation_b41ca919.mp4` | `STEMAnimation_concat_aff17cf3.mp4` |
| render path | whole-video | parallel concat |
| render time | 313s | **69s** |
| basketball as rendered | flat disc, **0.63u** | textured ball, **1.90u** (= emitted `height=`) |
| repair rounds / violations left | 3 / 1 | 2 / 3 |
| `[ELEMENTS]` | 38 declared, 0 degraded | 38 declared, 0 degraded |

**Why run A shipped 0.63u basketballs even though its scripts on disk all said
`height=1.9`.** Not a stale server — the harness runs in-process and had loaded the fixed
guards. Scene 2's isolated render **crashed** (`GrowArrow` on a `Dot`, defect 2 below;
reproduced by re-rendering `scene_453d0ea7.py` with TTS stubbed). Per the documented
behaviour, one dead scene drags the whole video off the parallel path onto the sequential
whole-video render — visible in the artifacts: run A is `STEMAnimation_*.mp4` at 313s,
run B is `STEMAnimation_concat_*.mp4` at 69s. The sequential path then self-healed the
crash and shipped drawings scaled to a third of their emitted height, and because the
video *looked* complete nothing flagged it. **Same disease as 2026-07-20** ("3 of 4 scenes
died, the sequential fallback quietly shipped a fine video, which is why nobody noticed"):
a crashing scene silently changes which renderer produced the artifact you are grading.
Read the output FILENAME before comparing two runs' frames.

**Three real defects the forensics surfaced, all now fixed and pinned:**

1. **`drawing(` had no preservation guard** — a repair round swapped four drawings for
   fallback icons in one scene (`drawing=10, native_fallback=4` vs siblings' `14/0`) and
   was *accepted*, because an icon in a drawing's place leaves a legal frame and the
   violation count fell. Third instance of the same rule; `_repair_preserves_assets`
   **and** `_STRUCTURE_HELPERS` now both list it. **Two lists, one rule.**
2. **`GrowArrow` on a `Dot` killed a scene at render.** `TypeError: VMobject.scale() got
   an unexpected keyword argument 'scale_tips'`. `_SHAPE_KINDS` correctly built a Dot for
   "velocity arrow pointing right" (the `point` match) and the schema override then
   reinstated `GrowArrow` one line later — the table exists precisely to stop that drift.
   `_entrance_supported` gates the override on the object actually emitted.
3. **The master script emitted forward references.** The global id→var map was
   last-writer-wins, so with 5 element ids repeated across scenes, scene 2's
   `basketball_start` resolved to `mobj_scene3_basketball_start` — used before it is
   bound, i.e. a NameError that takes the whole video, not one scene. Duplicate ids are
   now normal: each screen is written by its own LLM call and `_discipline` only
   de-duplicates *within* a scene. Resolution is per-scene and backward-only.

**Still open after run B** (composition, not asset resolution — the assets are fixed):
- **Frames are top-heavy.** Content occupies roughly the upper two-thirds; scenes 5 and 6
  leave the bottom half empty. The zone allocator fills from the top and nothing pulls
  the group back to centre when a scene under-fills. Next measurement: mean vertical
  centroid of non-background ink per scene.
- **A recap scene of 2 elements is a nearly empty frame.** Screen-plan `must_show` is a
  floor everywhere except the last screen, where it is 2. Cheapest fix is upstream (a
  floor on the recap), not a layout hack.
- `violations_remaining: 3`, `shape_overlaps: 5` — up from run A's 1/2, on a different
  render path. Not yet attributed; the parallel path repairs per scene and reported
  `scenes_repaired: 0`, which deserves a look before reading anything into the counts.

## 4. Symptom → stage → first move (routing table — extend as failures happen)

| Symptom | Inspect FIRST | First move |
|---|---|---|
| Points/labels off the grid; math visually wrong | D | Transpiler data-space coords (`c2p`) — never patch the LLM prompt for a geometry bug |
| Text-on-text overlap, clipped text, text through a shape | F, then D | Check the `.mp4.json` sidecar (`violations_remaining`, `repair_rounds`); recurring class ⇒ D should stop producing it (zones/slots) |
| Wrong facts/values in narration | B | Storyboard grounding — upstream of voice |
| Narration robotic / wrong language / TTS re-billed on repair rounds | C | Shared content-addressed TTS cache; script critic before TTS |
| Scene code crashes at render | D | Critic gate; the crash class becomes a critic rule |
| `TypeError: … unexpected keyword argument 'scale_tips'` | D | `GrowArrow` on a non-Arrow. The object↔entrance agreement broke — check `_entrance_supported` and what `el["_obj_expr"]` actually emitted, not the element's prose |
| `NameError: mobj_sceneN_… is not defined` in the MASTER script | D | A forward reference: two scenes reuse an element id and the event resolved to the later one. Ids are only unique WITHIN a scene by design — resolution must stay backward-only (`_visible_id_to_var`) |
| A generated asset silently reverts to a fallback between rounds | F | The repair agent traded away something the probe cannot see. Add the call to BOTH `_repair_preserves_assets` (render) and `_STRUCTURE_HELPERS` (critic) — one list is half a guard |
| "Choppy", "not continuous": the frame empties at every chapter start | render | Check the lesson's `look.joins`: `cut` (every lesson before 2026-10-15) starts each chapter on an empty stage with 2 s of silence. `carried` opens on the last frame; a `LESSON_NOTE: … not carried over` in `logs/C0n.log` says why one join fell back to a cut |
| Two lessons on one topic explain it two different ways | B | Is the topic in the concept knowledge base (`harness/concepts.py`; log line `[card] the knowledge base's card`)? If not, the first passing lesson's card becomes its entry |
| Server behaves like old code | ops | Restart uvicorn (CLAUDE.md env gotcha) — before debugging anything |
| A fix "doesn't work" on a live run but its harness passes | ops | Identify which PROCESS ran it. uvicorn snapshots modules at startup; an in-process harness (`import app` + `_run_render_job`) snapshots at its own import and never touches the server. Compare that process's start time to the edited files' mtimes before debugging (2026-08-15, §3e) |
| Two runs of the same board render differently for no visible reason | F | Compare output FILENAMES first: `STEMAnimation_concat_*` is the parallel path, `STEMAnimation_*` is the sequential fallback. A single crashing scene switches paths silently, and the fallback's self-heal can ship a degraded video that looks complete (§3e) |
| Cost unknown or spiked | H | Cost ledger; per-task model routing |
| Batch/long run dies with nothing resumable | H/I | Per-run folders + resume |
| Sidecar shows `violations_remaining > 0` with `repair_rounds: 0` | F | Since 07-20 the parallel path DOES repair, so this now means the repair agent was unavailable (no LLM key) or every candidate was rejected — check the job logs for "no LLM available to repair" vs "did not reduce violations" |
| static/videos fills with sidecar-less "Raw" mp4s | F | Repair-candidate leak — fixed 07-20 (`_discard_video`); if it recurs, look for a NEW `compile_manim_code` caller that doesn't discard its loser |
| Storyboard 500s on a JSON decode error | ops | `json_repair` missing from the venv — `loads_json_lenient` silently degrades to plain `json.loads` (added to requirements 07-20) |
| Storyboard 500s with "incomplete storyboard … no scenes" / "truncated model response" | B, then ops | Primary model hit `finish_reason=length` and the `deepseek` fallback returned a degenerate no-scenes board. **Since 07-31 the storyboard task sends NO request-level cap** (`_max_tokens_for_task`, `app/llm.py` — `LLM_MAX_TOKENS`/12000-16000 history no longer applies to storyboards; `LLM_MAX_TOKENS_STORYBOARD` restores one). If seen on a NEW run: confirm the server was restarted after 07-31, then the error text says which limit bound — "no request cap — the MODEL's own output window" means the board outgrew the model itself: pick a larger-output model or chapterize (§6). A one-off usually clears on retry |
| Video is far too short / never states the concept | B, planner FIRST | `determine_scene_count` (`ce/planner_agent.py`) — check the plan's scene count before touching the storyboard prompt; a terse source used to yield 1 scene |
| Video has the right scenes but feels rushed/slow for the grade | B | `narration_wpm()` — one shared implementation; don't re-add a substring grade check |
| Render is slow and `repair_rounds` is high on a multi-scene video | F | It went sequential: confirm the caller forwards `scene_scripts` (`ce/` dropped them until 07-20), then check for `Parallel render: N/M scene(s) failed` |
| `NameError: name '<element id>' is not defined` in a scene render | D | Cross-scene reference in a per-scene script — the id belongs to another scene; `_drop_cross_scene_events` / `_drop_foreign_id_calls` should have dropped it |
| A stage "works" but its fast path never runs | F/ops | Fallbacks hide broken fast paths — grep the logs for the fallback's own warning line before trusting that the fast path ran |
| Generic circle where a named diagram/shape belongs | D | Fixed 2026-08-01 (§D5): prose shape descriptions now match on the HEAD noun with word-START boundaries, cover real diagram nouns, and fall through to `fetch_smart_svg`. If it recurs, add the noun to `_SHAPE_KINDS` (`transpiler.py`) and pin it in `test_shape_resolution.py` |
| A shape described as "containing 84" renders empty / a diagram has no numbers | D | Fixed 2026-08-01 (§D5c): `_shape_value_label` + `viz_helpers.value_in`. A LIST ("containing 2, 2, 3 and 5") labels nothing **on purpose** — one shape holding the first of several values would lie. If the value is drawn but unreadable, it is the contrast backstop, not this |
| Diagram nodes/edges missing: a tree renders as one node, floating line stubs and empty frames | B, not D | The IR can express this since 2026-08-01 (§D5b): edges are `connects:[a,b]`, container contents are `relation:"inside"` children. So a board still showing this is a **storyboard** fault — one element describing several objects in prose. Count elements vs drawable objects; the fix is prompt rule 4c, not transpiler code |
| An element the storyboard declared is missing from the video | D | Check the job log for `Layout QA Critic dropped N element(s)`. Since 2026-08-01 the critic's rewrite is rejected when it deletes elements or dissolves `connector`/`place_inside`/`value_in`, so the deterministic code ships instead — a recurring warning means the critic prompt needs tightening, not the guard |
| Viewer reports overlap but the sidecar says `violations_remaining: 0` | G | Expected before 2026-08-01: the probe measured **text only**. Now read `shape_overlaps` in the sidecar (shape×shape, reported but not repaired by design). If that is 0 too, the collision is either mid-transition (the probe samples at beat boundaries) or under the 15%-of-smaller-bbox threshold |
| Text is drawn but invisible on the dark canvas | D backstop | The critic (or model-authored code) chose a near-black colour. `viz_helpers._contrast_safe_text_color` flips it on dark canvases; if it recurs, the colour arrived somewhere other than `Text`/`MathTex` kwargs |
| Devanagari (or `'-' ?` shrapnel) on screen in a hybrid/en video | D backstop, then B | Indic strip fixed 07-21 (both quote styles, `test_minimize_split.py`); if headings come out BLANK, the storyboard violated the language contract — see the §3c stage-B gate |
| Audio speaks English while the screen is Hindi (or vice versa) | B | Storyboard language inversion (§3c) — since 07-21 the gate rejects this before caching (`test_storyboard_gate.py`); if seen on a NEW video, check whether the server predates the gate, then cue vs element language in the cached storyboard JSON |
| Storyboard 500s with "language-contract violation" | B | The 07-21 gate fired. **On-screen** Devanagari now self-heals (`normalize_onscreen_language` translates labels to English before the gate) — so a 500 naming `native-script … on-screen content` means the heal ALSO failed (LLM error / label list mismatch): check the log for `Failed to translate on-screen labels`. A 500 naming `all narration cues are plain English` is the un-healed narration-inversion half: re-run (a retry usually obeys); recurring ⇒ tighten the storyboard prompt's language rules, not the gate |
| Elements sit on/outside the container they belong in | D | Containment gap D7 (§3c) — storyboard emitted absolute geometry; no code-owned "inside" placement yet |
| Video feels static; every element fades in identically | D | Entrance map shipped 07-20 (`_ENTRANCE_CONFIG` + `_SHAPE_ENTRANCES`, pinned by `test_entrance_map.py`) — if it recurs, check the element `type`/`content` the storyboard emitted, not the transpiler first |
| Video feels SHAKY — text bounces/wobbles on every beat | D | The elastic scale-pop default (`scale=0.1` + `ease_out_elastic`) was retired 07-31 after user review of the social-science batch: with 4-7 elements/scene EVERYTHING bounced. Default is now `_CALM_FADE` (shift-up + ease_out_cubic). Don't reintroduce elastic as a default — gate any "pop" to one hero element per scene |
| Photos parked in corner zones, stage centre empty | D | Hero-image rule (07-31, `_hero_image_place`): the scene's first free-standing image is centred even over a model-chosen zone; second images and axes-scenes keep zones. Pinned in `test_image_elements.py` B7-B9 |
| Whole video speaks in the robotic gTTS voice | C/ops | `voice_degraded` high + `TTS_DEGRADED: gtts-keyless` in logs — BOTH keyed voice tiers failed (no SARVAM key on this box by design; Gemini TTS rides the OpenRouter account, which 402s when credits run dry). Top up OpenRouter credits or add `SARVAM_AI_KEY`, then re-render: the shared TTS cache won't serve the degraded clips for the restored provider config |
| Bulk run died / topics stuck at `storyboard`/`render` | I | `python3 stem_animation_lab/bulk_runner.py --resume <run_id>` — done rows and cached stages are never re-billed; check the row's `error` in `bulk_runs/<run_id>/manifest.json` |
| One scene fails, render goes sequential, job may fail with "All TTS services failed" | ops/C | Provider audio outage (observed live 2026-07-21: OpenRouter `audio/speech` 500 / 200-with-empty-audio). Probe the endpoint with curl FIRST; a retry after recovery usually ships (TTS cache makes it cheap). Do NOT tune repair — the self-heal can't fix a provider outage (see §F error-classification note) |
| Sidecar shows `vision_findings > 0` | G, then B/D | Read the job's `vision_report` lines. `dead-frame`/`broken-hierarchy` ⇒ composition gap upstream (storyboard richness §B rule 4b, director enlarge-to-fill §D); `clipped-text`/`colliding-text` the geometry probe missed ⇒ check probe classes. Both paths now repair (sequential whole-video, parallel scene-scoped) — a surviving finding means every candidate was rejected or findings were unattributable |
| Sidecar shows `voice_degraded > 0` | C/ops | The video shipped on a FALLBACK voice. Grep the job logs for `TTS_DEGRADED:` — `gtts-keyless` means both keyed providers were down (check provider health, then re-render: the shared TTS cache will NOT serve the degraded clip for a different provider config); `silence` means the video has NO narration and should be re-rendered, not published |
| Render fails and the job error names external infrastructure | ops, NOT D | `_classify_render_failure` returned `infra` — the code was never the problem, so no repair round ran (by design). Probe the provider (`curl` the audio/chat endpoint), then re-render |
| Browser shows "NetworkError when attempting to fetch resource" / a UI request just dies | ops/J, NOT the network | The request didn't fail — it's still running. `/api/generate_storyboard` and `/api/generate_code` are **synchronous** and can take minutes when the model chain falls through; the browser abandons the open fetch first. Confirm by grepping the access log: work in the logs with **no matching `POST … 200 OK` line** = still in flight (uvicorn logs on completion). Fix shipped 2026-08-01: `/studio` uses the polled task routes (`POST /api/tasks/{storyboard,codegen}` + `GET /api/tasks/{id}`). The classic UI still holds the connection open — port it if this recurs there |
| Codegen/storyboard takes minutes and repeatedly retries models | B/D config, NOT the pipeline | A **reasoning** model is spending the whole token ceiling on reasoning and returning `finish_reason=length`, so every attempt is discarded and the chain walks to the next model. Observed 2026-08-01: `z-ai/glm-5.2` at 10727 reasoning tokens of `LLM_MAX_TOKENS=12000`, `moonshotai/kimi-k3` at 12000 of 12000 — the same board later succeeded at 5581 tokens, so it is a **coin flip on how much the model reasons**, not a hard break. Check the `WARNING:app.llm:… hit the token ceiling` lines first. **Fixed 2026-08-01 by moving all three chains to non-reasoning models** (see §5a); if it recurs, the added model has reasoning on by default |
| Every OpenRouter model fails in turn with `HTTP 402 … requires more credits` | ops config, NOT the models | The account balance is below OpenRouter's **pre-authorized worst-case cost**, which for the uncapped storyboard task is the model's whole 65535-token output window ("you requested up to 65535 tokens, but can only afford 11190"). It fails identically on every model, so it reads as a total outage. Fix: top up, or run on Gemini (`LLM_PROVIDER_ORDER=gemini,…` — the default since 2026-08-02, switchable live in the Model routing panel), or shrink the estimate with `LLM_MAX_TOKENS_STORYBOARD=16000` (re-imposes a video-length ceiling, §5a) |
| Codegen suddenly takes minutes / bulk 600s read-timeouts | D, via the F/ops fallback rule | The transpiler threw and EVERY board silently fell back to LLM codegen — grep for `Transpiler pipeline failed:` and fix the exception it names. Observed live 07-31: an undefined `logger` NameError'd the transpiler on any board carrying a `composition` descriptor (i.e. 100% of production boards) while all harness boards, composition-less, stayed green — pinned as `test_image_elements.py` A8b |
| OpenRouter model discarded with `finish_reason=length` and huge `reasoning_tokens` | ops | A reasoning-heavy model (GLM-5.2 measured 14–16k reasoning tokens on codegen) burned the whole `LLM_MAX_TOKENS` budget before emitting code. Raise `LLM_MAX_TOKENS` (32000 set 07-31) or move the model down the chain — do NOT treat as a truncation flake, it reproduces at 100% |
| Photo/painting missing from a scene that storyboarded an `image` element | E, then F | (1) Codegen log: `Wikimedia: no suitable bitmap for <query>` (clean Text degradation, ~20% of queries) vs `429` (Commons rate limit — resolver retries once; recurring ⇒ lower resolver parallelism). Cached files + attribution sidecars: `assets/wikimedia_cache/`. (2) If the CODE had the image but the VIDEO doesn't: the repair agent swapped it for an icon — the probe is image-blind so the swap always "reduced" violations. Guarded since 07-31 by `_repair_preserves_assets` (all three repair sites); if it recurs, check for a NEW repair path without the guard |

## 5a. Model selection: no reasoning models in the chains (2026-08-01)

**Rule: every model in `OPENROUTER_*_MODELS` must have reasoning OFF by default.**
A reasoning model spends the completion budget thinking, hits `finish_reason=length`
with little or no content, and `_call_openai_compatible` correctly discards it as
truncated — so the whole chain walks, model by model, taking minutes and producing
nothing. It is not a hard failure (a model that reasons less on a given prompt
succeeds), which is exactly why it reads as a flaky "network error" rather than a
config bug.

**Check before adding a model** — from `https://openrouter.ai/api/v1/models`, the
entry's `.reasoning` must satisfy: `mandatory` false AND `default_enabled` absent or
false. Measured examples of what to avoid:
`z-ai/glm-5.2` → `{mandatory:false, default_enabled:true, default_effort:"high"}`;
`moonshotai/kimi-k3` → `default_effort:"max"`. Both were chain leads before this fix.

Chains as of 2026-08-01 (vendor-diverse on purpose — one provider's outage must not
take a whole chain down):

| Chain | Models | Why |
|---|---|---|
| `OPENROUTER_STORYBOARD_MODELS` | `google/gemini-2.5-flash` → `openai/gpt-4.1` → `qwen/qwen3-235b-a22b-2507` | Structured-JSON compliance decides this stage (a degenerate board fails the shape gate). **deepseek is deliberately excluded** — poor structured-output compliance, the §3b degenerate-board source. |
| `OPENROUTER_CODE_MODELS` | `deepseek/deepseek-v3.2` → `qwen/qwen3-coder` → `google/gemini-2.5-flash` | Codegen / Layout-QA critic / repair agent: code quality with cheap output tokens ($0.40/M). |
| `OPENROUTER_MODELS` | `google/gemini-2.5-flash` → `deepseek/deepseek-v3.2` → `mistralai/mistral-small-3.2-24b-instruct` | General: transliteration, label translation. |

`LLM_MAX_TOKENS` restored to the code default **16000** (was pinned to 12000 locally).
Also removed `openai/gpt-oss-120b:free`, which had silently disappeared from the
OpenRouter catalogue — a dead fallback is an invisible one-model chain.
**Verified live, first model in both chains, no fallback walking:** codegen 54s
(`deepseek-v3.2`, 4221 tokens, 5 scene scripts, valid); a fresh uncached storyboard
40.5s (`gemini-2.5-flash`, 7327 tokens, 7 scenes at [4,7,10,5,5,5,5] elements).

*Housekeeping caught in the same pass:* `.gitignore` matched only the bare name
`.env`, so a `.env.bak-*` copy — same API keys — was untracked-but-visible to git.
Now `.env.*` with a `!.env.example` exception.

### 5a-ii. The block is code now, and the provider order leads with Gemini (2026-08-02)

Two follow-ups, both taught by the same live failure — a storyboard run where every
OpenRouter model answered **HTTP 402** (`"requires more credits ... you requested up
to 65535 tokens, but can only afford 11190"`) and the chain walked the whole list:

- **OpenRouter pre-authorizes the worst case, so an uncapped task costs its whole
  output window.** Since 2026-07-31 the storyboard task sends no `max_tokens`, so
  OpenRouter prices the request at the model's full 65535-token window and refuses it
  the moment the balance falls below that estimate — *before generating anything*. A
  402 therefore looks exactly like a model outage (every model fails in turn) but is
  purely a balance/estimate interaction. Two exits: top up, or set
  `LLM_MAX_TOKENS_STORYBOARD=16000` to shrink the estimate (which re-imposes a
  video-length ceiling — see §5a's note on why the cap was dropped).
- **`LLM_PROVIDER_ORDER` now leads with `gemini`** (`.env` + the built-in default in
  `app/model_routing.py`). The Gemini key is a separate free-tier quota and the genai
  path sends no request-level cap at all, so it is unaffected by both failure modes
  that killed OpenRouter here (credit exhaustion, cost pre-authorization). OpenRouter
  stays as the second hop.
- **Reasoning models are blocked in code, not by comment.** The `.env` warning did not
  prevent a re-add. `model_routing.blocked_reason()` matches `kimi-k3`, `glm-5.2`,
  `deepseek-r1`, `qwq`, `thinking`, `-sol` as case-insensitive substrings; blocked ids
  are stripped from any chain (env or default, logged as `MODEL_BLOCKED:`) and
  rejected with a 400 at `/api/models`. Stripping never empties a chain — it falls
  back to the built-in default. Same house rule as the layout critic's invariants:
  **prefer a contract over advice.**

**Model selection is now a UI panel, not an .env edit** (`/api/models` +
`static/model-panel.js`, mounted on both `/` and `/studio`): provider order (reorder,
disable) and the per-task chains for storyboard / code / general / vision, with the
resolved chain, its source (`default` / `env` / `runtime`) and the built-in default
shown per row. Writes are process-global env, same single-user caveat as
`env_overrides`, effective on the next LLM call and lost on restart; `.env` stays the
durable configuration and `POST /api/models/reset` returns to it. Pinned by
`test_model_routing.py` (37 checks). The chain tables live in `app/model_routing.py`
(no heavy imports) and are re-exported by `app/llm.py`, so the table has one home.

### 5a-iii. The chains were measured on the scene writer, and three fallbacks were dead (2026-10-15)

The code's default chains had drifted from §5a: `deepseek/deepseek-v4-pro` first in the code and general chains
(and second in storyboards, which §5a keeps deepseek out of), then `openai/gpt-oss-120b:free` and
`meta-llama/llama-3.3-70b-instruct:free`, both gone from the catalogue, and `google/gemini-2.0-flash-001` (gone) as
the vision fallback. Every chain was one model in practice. `scripts/check_models.py` now reads the live catalogue
(free, no key) and fails on a dead model anywhere or a thinking model in an engine chain; run it before editing one.

`scripts/eval_scenes.py` (cases `evals/scenes/cases.json`, scorecard `evals/scenes/scorecard.csv`) runs the model
behind `sim_gen` end to end: prompt with the installed-Manim context, security gate, `verify` in a real manim
subprocess, one repair round. Verified / first try / USD a scene / s a scene:

| Model | Verified | First try | $/scene | s/scene |
|---|---|---|---|---|
| `anthropic/claude-haiku-5.5`, thinking off | 8/8 | 8/8 | 0.0008 | 6 |
| `anthropic/claude-haiku-5.5`, thinking on (two runs) | 16/16 | 16/16 | 0.0022 | 19 |
| `deepseek/deepseek-v4-flash`, thinking off | 7/8 | 7/8 | 0.0003 | 22 |
| `qwen/qwen3-coder-next` (two runs) | 12/16 | 11/16 | 0.0011 | 20-27 |
| `deepseek/deepseek-v4-pro` (the old default) | 5/8 | 4/8 | 0.0286 | 147 |
| `google/gemini-2.5-flash` (the Gemini-first default) | 4/8 | 3/8 | 0.0047 | 12 |
| `openai/gpt-5.4-nano`, `z-ai/glm-4.7-flash`, thinking off | 4/8 each | | | |

Frames looked at (first and last of every verified scene, `--stills`): Haiku's are the clearest; DeepSeek V4
Flash's are plainer (a near-black grid for square numbers, no jump arcs). So: code chain Haiku (thinking off for
this task, `llm.THINKING_BY_TASK`) → DeepSeek V4 Flash (off) → Qwen3 Coder Next, and the code task asks OpenRouter
before Gemini when no order was chosen (`LLM_PROVIDER_ORDER_CODE`). A real `generate_simulation` through the new
defaults: Haiku, 0 reasoning tokens, 0.00065 USD, verified on the first try.

What the docs said and the runs showed about switching thinking off: OpenRouter's `reasoning: {"enabled": false}`
reaches models whose effort list has no "none" (DeepSeek V4: 0 reasoning tokens in 11 calls, against 6,650 a call
without it); `deepseek/deepseek-v3.2` ignored both `effort: none` and `enabled: false` on 2 of 3 first calls
(7,912 and 9,462 reasoning tokens), by provider, so it left the general chain. `verify` is not a judge: it says a
scene draws, moves and fits, not that it teaches; the stills are the check on that.

## 5. Maintenance (this doc is THE playbook — see CLAUDE.md → Operating discipline)

- Every task that surfaces an improvement idea, failure mode, measurement, or
  tried-and-reverted decision folds it in here in the same pass. Ideas repeat
  across sessions: **merge into the existing stage entry, don't add a twin**.
- Grades change only with evidence (a run, a test, a benchmark) — cite it in the
  stage section, like §3 does.
- When a priority-order item ships, mark it (strikethrough + commit/date) rather
  than deleting the row — the ranking's history is part of the record.

---

## 5c. Lesson Forge plans as input (2026-10-16)
Evidence: 14 videos, docs/longform/lesson-forge-videos.md. Grade for the Forge-direct path: scripts correct in
arithmetic, weak in teaching (critic pedagogy 1-2), pictures mostly text and flow charts. Next, in order:
1. ~~Tell the writer about the `graph` figure~~ DONE 2026-10-20 (`FIGURE_RULES`, `settle_graph`, `graph_reveals`;
   six of the 11 remakes drew on it). Survey of the remakes: said-not-shown 21 → 3, failed checks 10/20 → 1/10.
   Still open from that survey: words pointing at things the drawing lacks (21 "missing", mostly the lens lesson),
   a figure kept over a beat that has moved to a new case (crossing-point beat 11 spoke x + y = 7 over x + y = 5:
   `figures_follow_words` has no numbers for a graph, and the writer gave no new one).
2. A critic check for false statements on cards ("Sine = Cosecant" passed), not only numeric claims.
3. Make `--words writer` the default if a second batch confirms the four-topic comparison.

## 5d. A storyboard and a timeline that can be read and checked (2026-10-17)
The long-form path's intermediate representation is now explicit (docs/longform/storyboard-and-timeline.md): stage
files 1 to 3 and a code gate before speech, `sync_timeline.json` compiled from the measured narration before the
render, one `qa_report.json` that maps every open fault to its beats and component, and `bundle.json`.

**2026-10-19, five hard-question lessons made through `service._run` (heavy ball, 0.999… = 1, Monty Hall, ice,
the Moon's face; about 0.10 USD each on the cheap routing, local Kokoro voice).** Grade for the timeline stage: B
(its findings were real and the new repair cures most of them; nothing measured with learners). What they showed and
what changed:
- Timeline faults are now repaired, not only reported (`longform/sync_repair.py`, in `_run` after the compiler and in
  the screen repair after its rewrite; `lessonforge lesson mend` for a finished lesson). Heavy ball: QA failed → passed
  with warnings, two of seven chapters filmed again. Monty Hall: reading-time warnings 4 → 1. Left open: a beat with
  more lines than its words give time to read (Moon 02, 05, 07) cannot be cured by moving anchors.
- Numbers on screen: the number line put "1" under the tick at 0.9 and stacked its labels (14 overlaps) →
  `figures.tick_step`, `_unstack`. Units read as letters ("m/s²") → `writer._spoken_units`. Two formulas on one line
  cut at "=" → `runtime.math_rows` prefers ";".
- Correctness: true probability claims failed on float equality (`2/3 == 1 - 1/3`) → `critic._exact` with fractions;
  a true claim the reviewer checked with a wrong expression (`0 - 1 == 1`) → checked again alone
  (`critic._check_again`; a check that cannot be false, `360 == 360`, is not believed).
- Sources: "work" in a probability goal sent the search to the Class 10 science book → `library.school_subject`.
- Scenes: four door scenes were refused as unsafe; the `open(` rule also matched a METHOD call (`.open(`), which
  is now allowed (that `door.open(` was the cause is inferred: refused code is not kept); a staged scene left two labels on each
  other through a whole stage → `sim_gen` checks labels at every stage boundary where both stand still; two scene
  descriptions that began alike shared one cache file → the key carries a hash of the whole description.
- Tried and left off: drawing a model-written scene again when the stills look says it lacks what its words name
  (`compose._redraw_scenes`, `HARNESS_COMPOSE_SCENES=1`): of four kept, two better, one mixed, one worse (the word
  "spin" written under the Earth). The second look asks whether each fault is cured, not what else got worse.

**2026-10-19 (later), the two open items.**
- Too many lines for the time: the sync repair now THINS a beat re-anchoring cannot cure (a repeated line off, a line
  cut to its first clause, a plain point off; never a question, working, a focus or a draw; `HARNESS_SYNC_THIN`).
  Moon: 4 warnings → 0; Monty Hall: 1 → 0; Moon and Monty Hall filmed again with `lesson mend`, layout no worse.
- Scenes that miss their words, first cause found by measuring, not by looking: the scene writer scales text by a
  factor meant for font size. 13 labels in 7 of the 43 cached scenes were under 0.1 units tall in a 4-unit box (a "?"
  0.005, "water" 0.012): drawn, invisible, and so "missing" to every look. `sim_gen.verify` now refuses text under
  2.5% of the box height (`MIN_TEXT_SHARE`), the prompt says so, and a cached scene verified before the check is
  verified again on its next use and drawn again when it fails (`_verify_again`, `VERIFY_REV`; the first file kept as
  `.first.py`, and in use if no redraw passes). Five such scenes redrawn on three lessons: all five better by eye.
- A look at each scene's stills against its description (`harness/scene_look.py`, `HARNESS_SCENE_LOOK`, default off):
  stills where the lesson waits (start, end of each stage) on one sheet; a vision model lists what the description
  asks to be seen, thing by thing; a fault counts only when a second look by number confirms it; a redraw is kept only
  when it has fewer faults AND nothing it showed before is lost AND no new stray words (the "what got worse" check
  `compose._redraw_scenes` lacked). On 30 scenes of three lessons the look found real faults (ice: blocks never
  grow, no molecules) and a few false ones (a blocks' "m" called the wrong label); nine redraws by the cheap code
  model were all refused by the keep rule (four cured nothing, three lost something, one wrote "panel"). So it stays
  off: the look works, the redraw does not yet. Cost about 0.4 cents a look.

**2026-10-20, plain narration ("very complex and cryptic").** Measured first, against 15 lectures found on YouTube for
the five topics (captions fetched through the embedded player; the transcript API is IP-blocked from cloud boxes).
Lecturers: 0.1 to 1.0 questions per 100 words, colons about 0.4, 16 to 22 words a sentence. Ours: 1.7 to 2.7, 1.4 to
3.2, 10 to 14, and 4 to 9 stops in three minutes, plus the framework's stage names read aloud. Levers, in the order they
were found to matter: (1) a lesson-level stop plan in code (`writer.stop_plan`, `keep_planned_stops`), because every
stage job of `why_it_works` asked for a question; (2) the reviser held to plain talk (`critic.apply_edits` with
`voice.unnoted`/`chopped`/`plan_talk_in`), because the writer's plain draft was being cut into notes; (3) lecturer
passages as manner examples (`voice.lecturer_examples`); (4) plain-talk findings for the polish and reviewer; (5)
softer `why_it_works` stage jobs. Same five briefs, script and review only (about 0.2 USD a round): questions per 100 words
1.7-2.7 → 1.4-1.7, colons 1.4-3.2 → 0, stops 4-9 → 3 each, plan said aloud 2-5 → 0-1, "we/you" and joining words
about the same or higher. Round by round: the stop plan alone halved the stops; the plain writer's DRAFT was then cut
back into notes by the reviser until it was held to plain talk.
Still open: sentences stay shorter than a lecturer's (about 11 words against 16 to 22); the try-it beat is still
written as instructions; nobody has listened to the new scripts.

**2026-10-20 (later), the owner's teaching notes (Walter Lewin-inspired: voice, PPDFAR order, a weighted evaluator).**
Mapped before building: the PPDFAR order (Hook, Predict, Discover, Formalize, Apply, Transfer, Reflect) is already the
frameworks' stage lists (`why_it_works`: problem, claim, conflict, proof, limits, transfer, recap; `concrete_first`:
activate, concrete, explore with predict-pause-reveal, name, model, practice, recap), so no new framework. Built: the
delivery rules in the writer (`_SYSTEM_WRITING`, "SOUND LIKE A TEACHER": thinking aloud, 12 to 22 words a sentence,
one plain "this surprises almost everyone" at the turn with no "here is the" (that is `_PLAN_TALK`), assumptions said,
units, the idea before its name, the key idea said again and a closing line, no stock phrases); the try-it beat as an
imagined prediction, not a list of orders (`card_notes`); stock phrases and exclamations as voice findings; the
weighted rubric (`harness/rubric.py`, 8 criteria, weights 20/15/15/15/15/10/5/5, `HARNESS_TEACHING_RUBRIC`, off): a
3 or 4 counts only with a quote code finds in the narration (headings earn nothing), a 0 or 1 with a quoted defect
is a major `teach:` finding for the reviser. Left out: humour (a cheap model's jokes are a risk to a lesson, and the
notes' "don't imitate a real lecturer" rules out the obvious source), the React/JSON lesson schema and its interactive
widgets (the video's stops and the player's question ladder are the interaction), hint ladders beyond the player's.
Measured on the five lessons (script and review, rubric on, 0.26 USD on the ledger): colons stay 0, stops 3, stock
phrases 0, "we/you" and joining words about the same or higher, length on budget. But questions per 100 words rose to
1.7-2.3 (round C 1.4-1.7) and sentences stayed at 10-12 words. Read draft against final: the WRITER's drafts ask 4-7
times (allowed 4) and keep 11-13 words a sentence; the REVIEW raises questions to 6-8 and cuts sentences by about 1.5
words, in round C as well as D. Two causes found and fixed the same hour, not yet re-measured (the cap refused the next
round): a rewrite may not ask more questions than its beat did (`critic.apply_edits`, `voice.asks_in`), and the try-it
note asked for a prediction AND a second question (the card's `question` is now said as a statement); the rubric is
told the try-it task is left unanswered on purpose and that a repair never adds a question (`rubric.VERSION` 2).
Re-measured the same day (round E, three of the lessons, rubric on, 0.35 USD): questions per 100 words 2.2-2.3 -> 0.8-1.2,
words a sentence 10-11 -> 11.5-13.7, colons 0, stock phrases 0, stops 3, length 346-356 for 343. The rubric scored 71-75
of 100; its low scores were real (the heavy-ball lesson's line of working says F = 2mg for the 2 kg ball, and nothing is
shown falling; the ice lesson never says the melt fills exactly the displaced space), and no high score was capped.
Still open: the reviser shortens sentences mildly (above `voice.chopped`'s threshold), so sentences stay under a
lecturer's 16-22 words; and a correctness fault the rubric quotes (F = 2mg) reached the final script, so its findings
are not yet strong enough to make the reviser fix a wrong line of working.

Next, in order:
1. A redraw that cures what the look finds: the brief names the faults, but the cheap code model draws the same
   scene again. Try passing the stills themselves to a model that can see, or a stronger code model for the redraw
   only (a billing decision for the owner).
2. Send the other components' `fail`s in `repair_plan` to their repairs (a claim → the reviser; an overlap inside a
   scene → the scene writer).
3. Drive a second player (the browser board in `pilot/board/`) from `storyboard.json` + `sync_timeline.json`.
Frame review of the three v3 remakes (2026-10-17, LGLG: "the visuals are not good"), one frame per sentence:
- FIXED, by code: the figure changed one beat after the voice gave the new numbers (`writer.figures_follow_words`);
  the hypotenuse kept its "?" for five beats after the voice said 5 (`writer.found_unknowns`); "double every side"
  relabelled a same-size triangle (`writer.scaled_copies` + `ghost` in `figures.right_triangle`); formulas in a small
  serif face beside large sans words (look key `math: sans`); units set as italic variables, "13m"
  (`writer.units_upright`); a scene label resting on another between stages passed `sim_gen.verify` (it checked only
  start and end).
- OPEN: a scene's ghost of its own earlier frame (pressure chapter 6) is an animation caught mid-stage, not yet
  traced; the pressure scenes are cached, so the overlap check only helps when they are drawn again (a few cents);
  a step anchored on a beat's last words appears in its last second; a long line of working still wraps at its
  relation ("= 4/3 doubled" alone on a row); emphasis is a thin gold outline.
- Scene check, 2026-10-18/19: refuses letter-on-letter labels, filled open arcs, a line running through a label at
  rest, labels under 0.1 units tall and top-level parts never seen. Lesson: a check that sees only what is visible
  is passed by invisibility (the redrawn chapter-5 scene had zero-size text and a block faded in from opacity 0 and
  passed every check; caught only by looking at frames of the filmed lesson). On 32 kept scenes the last two refuse
  5, all real. DONE 2026-10-19: value pairing by code (`value_pairs`), a tighter grazing margin, arrows through
  filled shapes. OPEN: redraws fix the checked fault and break unchecked ones (dent depth against pressure, an arrow
  not on its object), so a redraw needs a still looked at. DONE 2026-10-20: the code nudge (`scene_tidy.py`, run by
  the checker AND the lesson's loader): a label a line grazes moves by the smallest step that leaves a 0.05 gap,
  at most half its height, onto no other label; a line through a label's middle stays refused. On 29 cached
  scenes it cured 2 of 5 line-on-label refusals (both in the filmed pressure lesson); the other 3 are lines through
  the middle and stay for a redraw. Still refused and not code-fixable: 3 parts never seen (animate() picks the
  wrong part), 2 "arrows through a block" that are pressure arrows drawn on the contact patch (a fix that moves
  them to the top face would be wrong physics, so none was built).
- Survey of the 20 filmed lessons, 2026-10-20 (`final_checks.json`, `vision_review.json`, `qa_report.json`): the
  commonest failed check was cue lateness (10 of 20): two steps on the same opening words entered one after the
  other at 0.9 s each, so the second came 0.65 s after its words. Fixed in `runtime` (steps sharing a cue enter in
  0.35 s); copies of the older lessons filmed again from their own audio pass it. Next most common: text overlap
  in 5 lessons (scene labels and code-drawn graph labels mid-animation), then frame-review mismatches (51) and
  said-not-shown (21), which need script or picture work, not layout.

Quality report and storyboard gate (2026-10-17, LGLG's pipeline plan; map in docs/longform/pipeline-plan-map.md):
`harness/qa.py` writes `output/qa_report.json` per lesson (every finding by beat, stage and owning repair pass) and
checks the storyboard before speech. On 48 finished lessons: 10 pass; the gate finds 72 beats whose spoken numbers
the screen never shows. DONE 2026-10-18: said_not_shown and anchor faults are sent back for new steps before audio
(`qa.mend_storyboard`; 13 of 17 beats fixed on five lessons; a mend that drops an old line is refused). NEXT: the
gate on new lessons made with it; unknown_left and late_figure have no mend yet.

## 6. Long-form scaling (10–15 min) — constraint ledger + chapterized design (2026-07-30)

Today's system is a **~90–140s machine by construction** (measured: modal band
89–140s over `static/videos/` + `generated_videos/`; cached boards carry 203–430
narration words ≈ 81–172s at 150 wpm). The architectural ceiling is ≈4 min:
`determine_scene_count` caps at 10 scenes × 25s target (`ce/planner_agent.py:78`).
10–15 min is a ~10× scale-up, and **stretching the single-call design is the
wrong move**:

- 10–15 min at ~25s/scene = **24–36 scenes**. A 5–6-scene board already runs
  ~6.3k of the 16k `LLM_MAX_TOKENS` ceiling, so a 30-scene board (~30k+ tokens)
  truncates and the `finish_reason` gate rejects it — loudly, by design (§3b).
- One giant board also concentrates blast radius: one bad LLM call, one gate
  rejection, one sequential-fallback render against the whole-video 600s
  `RENDER_TIMEOUT_SECONDS` budget loses *everything*.

### Design: chapterize, don't stretch

1. **Chapter outline as the new upstream length decider.** The planner emits a
   4–8-chapter outline (each 90–150s, each a hook → statement → example → recap
   arc). Per the §B lesson — *when two stages encode the same quantity, the
   upstream one decides* — total duration is decided HERE and nowhere else.
2. **One storyboard call per chapter, unchanged.** Each chapter uses the
   existing "4–6 scenes / 60–90s" prompt envelope — no prompt surgery, boards
   stay in the proven ~6k-token range, and every existing gate (shape,
   truncation, language contract, tech-terms) applies per chapter unchanged.
3. **Coherence thread.** This is where §B's **deck brief + running summary**
   idea stops being optional: a one-time video brief plus a running summary
   updated after each chapter, threaded into every chapter's storyboard call —
   kills re-introductions and terminology drift across 8 boards. (Merge note:
   that idea already lives in §B Improve; long-form is its forcing function.)
4. **Orchestration = the bulk_runner pattern, rows are chapters.** A chapter
   manifest (`pending/storyboard/codegen/render/done` per chapter, per-chapter
   stage caches, resumable) — the machinery already exists for topics.
   Payoff for tuning: **fixing chapter 5 post-gen re-renders ONE chapter and
   re-concats** — zero re-billing of chapters 1–4. Regeneration is scoped to
   the artifact that changed, which is the whole point of `docs/tuning.md`.
5. **Assembly.** `ce/video_merger.py` already concats N clips + BGM — today it
   is a vestigial 1-clip concat (`clip_planner.py` hardcodes 1); chapters make
   it real again. Cross-chapter transitions are hard cuts until §D theming v2's
   `xfade` lands.
   **Long-form lessons (2026-10-15):** no `xfade` was needed. With look key
   `joins: carried` each chapter's render opens on the frame the last one ended
   on (`runtime.GuidedChapter._carry_over`), so the hard cut joins two identical
   frames; the heading cross-fades and the picture changes from there. Measured
   on a 3-chapter test render: under 2% of the stage differs across each join
   (`tests/integration/test_joins.py`). Seam silence 2.1 s → about 1.1 s, beat
   gaps 1.1 s → 0.65 s (`audio._joined_leads`). Not yet measured on a real
   lesson against doc 12's 40% silent time.

### Constraint ledger — what breaks at 10×, and the fix

| Constraint (today) | At 10–15 min | Fix |
|---|---|---|
| Planner cap 10 scenes (`planner_agent.py:78`) | Can't express 24–36 scenes | Chapter outline decides; per-chapter counts stay 4–6 |
| ~~`LLM_MAX_TOKENS` request cap, board ≈6.3k~~ | ~~30-scene board truncates~~ **Request-level cap REMOVED for the storyboard task 2026-07-31** (user decision; `_max_tokens_for_task` in `app/llm.py`, restore with `LLM_MAX_TOKENS_STORYBOARD`; pinned `test_ir_contracts.py` E3). The binding limit is now the MODEL's own output window | A very large single board still truncates at the model window (finish_reason gate rejects it loudly) — chapterization remains the design; uncapping just stops the ~10–13-scene env ceiling from being the first wall |
| `RENDER_TIMEOUT_SECONDS=600` applies whole-video on the **sequential fallback** | A 10-min sequential render blows it | Chapters bound blast radius (≤2.5 min each); parallel path is per-scene already |
| 1-scene board disables parallel render (`transpiler.py:1181`) | — | Chapters are always multi-scene |
| `_OVL_MAX_REPORTS=12` per render | A long single render silently under-reports late scenes → repair under-covers | Per-chapter renders reset the cap |
| `VISION_QA_FRAMES=6` fixed | 1 frame per 2 min — blind | Run per chapter + the §D per-scene-midpoint sampler fix |
| Vision/overlap repair of flagged scenes runs **sequentially** (§G cost note) | Dominates wall-clock at 30+ scenes | The §G rewrite-all-then-render-parallel fix is a prerequisite |
| TTS spend scales ~10× | Dominant metered cost | #4 script critic graduates to **prerequisite**; shared TTS cache keeps chapter re-renders ₹0 |
| No cost ledger (§H) | 10× spend, unmetered | #5 prerequisite |
| 24 h sweep, no per-run folder | A long run's chapters scatter/vanish | #7 per-run folders prerequisite |
| `RENDER_WORKERS=2` (boot-read) | 8 chapters serialize 4-deep | Raise for the run, or accept wall-clock; chapters are embarrassingly parallel |
| Client seams (`ce/stem_animation.py`) | — | Fine: compile is 202+WebSocket; 300s storyboard timeout is per chapter |

### Cost & sequencing

A 12-min video ≈ 8 chapters ≈ **8× today's per-video cost** (~50k storyboard
tokens total, ~1800 narration words of TTS, 8 renders) — linear, not
super-linear, and chapters parallelize. Sequencing: ship #19 (tuning surface)
first so chapter experiments are cheap, then #4/#5/#7 + §G parallel repair as
the prerequisites above, then #20 itself. Grade the first real long-form run
the §3b way: one topic end-to-end, watch where it actually breaks.


**2026-10-20 (evening), a chemical equation drawn by code.** The owner's balancing-equations script filmed as written
(482 words, 3 min 48 s, slow Kokoro voice): its pictures were model-written scenes and got the chemistry wrong (two
waters labelled "H2O2", counts not updated after balancing, a line cut at the edge; 11 frame-review findings). New
figure kind `reaction` (`figures.reaction`, `figure_math.parse_equation`): code draws the molecules, formulas and atom
counts from the equation alone. Remade: 1 finding, every beat on the new figure, technical checks passed. Still open:
a beat whose words walk through two equations (Mg + O2 -> 2MgO, then 2Mg + O2 -> 2MgO) shows only its last one. Then, after "the video is stale": voice-led hints on the reaction picture (atoms named, counted, a side's count,
a formula read out) took the share of half-seconds in which the picture changes from 10% to 52% (Khan Academy: 81 to
92%). Next lever for the rest: atoms that regroup when a coefficient changes, instead of a whole-figure morph. Then, after "this is not good screen" (snapshot sheets of every sentence): the reaction is drawn on one
line with a before/after count table and a verdict under it, so it fills the picture box (was a narrow column using a
third of its width), the "+" signs are drawn (they had never been in a stage), and chemical equations in the words
column are upright (`writer.chemistry_upright`). Open: the words column often repeats the equation the picture shows
(writer content); the magnesium beat still skips its middle equation. Then the owner's Visual Teaching Engine module (docs/engine/visual-teaching-engine.md): a
typed action vocabulary and a per-scene visual plan with code checks (`longform/visual_actions.py`,
`output/visual_plan.json`), a reaction that changes part by part (new molecules grow, counts roll over), and a
transfer question made by code for any balancing task. Open from that module: the writer choosing actions by purpose,
a student model choosing a different visual after an error, and any measurement of learning.