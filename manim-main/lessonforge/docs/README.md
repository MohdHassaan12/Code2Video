# Documentation map

Status: **live** (describes current code), **record** (correct as of its date, kept
for the reasoning), **reference** (research and evidence).

Documents copied from the source repositories are unmodified, so their internal paths
and some relative links still describe the old layouts. Read them with this table:

| Written in older docs | Means now |
| --- | --- |
| `stem_animation_lab/app/…`, `app/…` | `src/lessonforge/engine/…` |
| `stem_animation_lab/{transpiler,viz_helpers,theme}.py` | `src/lessonforge/…` |
| `_OVERLAP_PROBE_SNIPPET` in `app/render.py` | `src/lessonforge/layout_probe.py` |
| `stem_animation_lab/test_X.py` | `tests/engine/test_X.py` |
| `static/videos/`, `temp_renders/`, `.tts_cache/`, `assets/*_cache/` | under the workspace — `src/lessonforge/paths.py` |
| `uvicorn app:app`, `python -m app` | `lessonforge serve` |
| `long_form_pythagoras/{lesson_runtime,build_audio,assemble}.py` | `src/lessonforge/longform/{runtime,audio,build}.py` |
| `meeting/education_content_review/…` | `docs/longform/`, `docs/project/`, `docs/research/review/` |

## Start here

| Doc | Status | Read it for |
| --- | --- | --- |
| [../README.md](../README.md) | live | What the package does, how to run it, what is not done |
| [../CLAUDE.md](../CLAUDE.md) | live | The hard-won rules, each with the failure that taught it |
| [../PROVENANCE.md](../PROVENANCE.md) | live | Source commits, what moved where, what was pruned |
| [agent/IMPROVER.md](agent/IMPROVER.md) | live | **The improver**: Claude Code on the owner's plan makes a video, inspects every stage, fixes the system one tested change at a time and proves it (`/make-best-video`, `/inspect-lesson`, `scripts/agent/`) |
| [research/RESEARCH_QUESTIONS.md](research/RESEARCH_QUESTIONS.md) | live | **The unified register: 30 open questions from both projects**, evidence from each side, where they disagree, a proposed order, and a crosswalk of every original id |

## Engine — `docs/engine/`

| Doc | Status | Read it for |
| --- | --- | --- |
| [pipeline-roadmap.md](engine/pipeline-roadmap.md) | live | The improvement playbook: per-stage grades from real runs, priorities, symptom routing, §6 long-form design |
| [visual-teaching-engine.md](engine/visual-teaching-engine.md) | live | The owner's Visual Teaching Engine requirement (module 12) and what exists for each part; the chemistry example step by step. Read before changing pictures, timing or questions |
| [USAGE.md](engine/USAGE.md) | live (old paths) | Language settings, single and bulk generation, env knobs |
| [tuning.md](engine/tuning.md) | live | Every tunable by regeneration cost, and the cache-key traps. Read before any A/B |
| [layout_framework.md](engine/layout_framework.md) | live | Layout enforcement v5: the probe, the repair loop, the traps |
| [deep-storyboard-design.md](engine/deep-storyboard-design.md) | record | Sources → screen plan → one writer per screen; generated simulations |
| [studio-editor-design.md](engine/studio-editor-design.md), [studio_proposal.html](engine/studio_proposal.html) | record | The scene-first editor: design and visual pitch |
| [video_pipeline.md](engine/video_pipeline.md), [PIPELINE_WALKTHROUGH.md](engine/PIPELINE_WALKTHROUGH.md), [audio_agent.md](engine/audio_agent.md) | record | Earlier design and walkthrough notes |
| [architecture/](engine/architecture/README.md) | reference | Reference architecture spec and diagrams (the IR ladder, layer contracts) |

## Long-form — `docs/longform/`

| Doc | Status | Read it for |
| --- | --- | --- |
| [storyboard-and-timeline.md](longform/storyboard-and-timeline.md) | live | **The stage files of a lesson**: shared storyboard and its gate, timeline compiler, QA report, bundle (2026-10-17) |
| [lesson-forge-videos.md](longform/lesson-forge-videos.md) | live | **Videos from Lesson Forge plans** (`lessonforge forge`): the two ways to get the words, what the first 14 videos showed |
| [pipeline-plan-map.md](longform/pipeline-plan-map.md) | live | **LGLG's video pipeline plan mapped to the code** (2026-10-17): stage → module → artifact, the stack decision, the storyboard gate and `qa_report.json` |
| [HANDOFF_REPORT.md](longform/HANDOFF_REPORT.md) | record | **What the first 20-minute lesson got wrong** and tasks T01–T14. Several are now addressed in code — see the table below |
| [NEXT_SESSION.md](longform/NEXT_SESSION.md) | record | The continuation brief that preceded this merge |
| [08_narration_led_long_form_approach.md](longform/08_narration_led_long_form_approach.md) | record | Why narration leads; script, continuity, timing, repair |
| [09_combined_architecture_and_tickets.md](longform/09_combined_architecture_and_tickets.md), [03_system_architecture.md](longform/03_system_architecture.md), [07_frameworks_and_implementation_handoff.md](longform/07_frameworks_and_implementation_handoff.md) | record | Proposed architecture, contracts and tickets |
| [06_scaling_dataset_and_distillation.md](longform/06_scaling_dataset_and_distillation.md) | record | Dataset construction and distillation plan |
| [pythagoras_case_study/](longform/pythagoras_case_study/README.md) | reference | The reviewed lesson: narrative, storyboard, review, costs, checks, and `drafts/` — raw model output, prompts and repairs. **Scripts in `drafts/` make paid calls; do not run them** |

Handoff tasks against the merged code:

| Task | State |
| --- | --- |
| T02 speech adapter | Partly: `longform/speech.py` routes to the engine's provider chain (Sarvam, Gemini TTS). No cost ledger; not run with a key |
| T04 versioned contracts, stable ids | Partly: `longform/contract.py` validates the lesson; ids are per beat, not per visual object |
| T05 alignment and anchors | Partly: sentence starts located on real pauses and labelled; inside a sentence still estimated. No forced aligner |
| T07 attention scheduler | First cut: `GuidedChapter` steps and highlights, for generated chapters only |
| T08 layout and motion checks | Partly: the engine's per-play probe now runs on long-form scenes. Not per frame |
| T12 resumable builds | Partly: speech clips are content-addressed; chapters re-render whole |
| T01, T03, T06, T09–T11, T13, T14 | Not started (human review, typed geometry components, localisation, evaluation, dataset, distillation) |

## Research — `docs/research/`

| Doc | Status | Read it for |
| --- | --- | --- |
| [RESEARCH_QUESTIONS.md](research/RESEARCH_QUESTIONS.md) | live | The merged register (start here) |
| [engine/research-agenda.md](research/engine/research-agenda.md) | reference | R1–R18 with who is working on each, and the v1.1 → v3.0 plan |
| [engine/problem-catalogue.md](research/engine/problem-catalogue.md) | reference | 25 open problems graded by difficulty and effort |
| [engine/problem-decomposition.md](research/engine/problem-decomposition.md) | reference | The 19-link chain and the representation ladder |
| [engine/improvement-timeline.md](research/engine/improvement-timeline.md) | reference | Milestones M1–M7 as capabilities |
| [engine/research-papers.csv](research/engine/research-papers.csv) | reference | 116 papers, tools and APIs behind the agenda |
| [engine/problems/](research/engine/problems/index.html) | reference | Deep-dive pages P01–P11 |
| [engine/chapter-4-architecture.md](research/engine/chapter-4-architecture.md) | reference | The architecture as a research contribution |
| [review/01–06](research/review/) | reference | Literature review, Code2Video assessment, source register, forty approaches across eight problems, paper and code audit, cost analysis |
| [approaches/02_layout_and_composition.md](research/approaches/02_layout_and_composition.md) | reference | How others solve overlap, off-frame and composition in generated Manim (SGA, Code2Video, OmniManim, manimkit, slide agents, VLM critics): comparison table, the three to adopt first with design sketches, what did not work |
| [experiments/openrouter_pilot/](research/experiments/openrouter_pilot/RESULTS.md) | reference | A small three-model pilot with real renders and one repair. Not a ranking |
| [scaling/](research/scaling/) | reference | Dataset specification and cost scenarios |

## Project — `docs/project/`

Meeting minutes, scope and delivery plan, evaluation protocol, action register, the
seven workstreams, lesson and review templates, and example lesson packages — the
delivery context the research review was written for.

## Added 2026-10-08 — real-model run and approach research

| Document | What it is |
|---|---|
| `research/experiments/2026-10-08_openrouter_run/REPORT.md` | The first end-to-end build with real models: measured costs, the problem list from one video, what was adopted from the research below. Start here. |
| `research/approaches/01_consistency_and_correctness.md` | How others keep long scripts coherent and catch wrong maths (typed chapter contracts, ledger diffs, cross-family claim verification). |
| `research/approaches/02_layout_and_composition.md` | Render-free layout verifiers, anchor grids, why frame-level VLM judges are weak. |
| `research/approaches/03_sync_and_highlighting.md` | Forced alignment benchmarks, the 250 ms picture-first rule, cueing evidence. |
| `research/approaches/04_frameworks_evaluation_selfhosting.md` | Evidence behind the three revised frameworks, evaluation at scale, open-weight options per stage. |
| `research/approaches/05_personalization_interactivity_readability_palette.md` | Level/age adaptation, in-video interactivity formats, readability thresholds per class band, teaching colour palettes. |
| `research/approaches/06_teaching_script_plan.html` | **Plan, 2026-10-09.** Its steps 2 and 3 were built the same day (`harness/library.py`, `card.py`, `skill.py`, `skills/teaching-script/`, the writer's `card=`); no video made from a card has been watched yet. Why the generated scripts are dull (read from two real scripts), and the change: sources for the topic → a teaching card (the why, the one picture, known mistakes, a try-it-yourself task), a script skill folder that holds the teaching craft, the harness path annotated stage by stage, build order, and a reading list with every DOI checked. An HTML page; also published as an artifact. |
| `research/approaches/06_plan_checks_and_additions.md` | Companion to the plan above, 2026-10-09: what three narrowed literature searches add to it or correct (licences of the sources, no search key needed, the limits of "draw while saying", conditions for the opening question and the try-it task, Google's own pages on NotebookLM and LearnLM), with what was and was not re-checked, and the papers that could not be opened. |
| `research/approaches/07_composition_and_pictures.md` | 2026-10-09. Two documents the owner supplied on overlap handling and a constraint-aware composition framework, digested and set against what lessonforge already does; what the six pilot videos say the real problem is (25 of 45 frame findings are picture-and-words mismatch, 7 are overlap or clipping); what to adopt in which order (typed code-drawn elements, the board takes the frame, imported pictures, findings that become repairs, seven hard test scenes); and a probe of finding and importing SVG pictures (flat ones import well into Manim, shaded ones turn black with no error; search returns wrong things), the owner's diagram service, and the `diagram` figure built from it the same day (section 5c: exact picture layers drawn by a browser, parts named from the diagram's own labels, a part lit when it is named). Sections 4 and 5 are still plans. |
| `research/approaches/08_voice_blueprints_and_posters.md` | 2026-10-09. Why the first card lessons did not sound natural, counted on five lessons, and what was built for it (`harness/voice.py`, `skills/teaching-script/voice.md`); what was taken from the owner's two prompts (a lesson plan worked out for each source, objectives with levels on the card, a table-driven source cleaner); the diagram service's new call and the flat-poster kind of drawing. One real script compared with two earlier ones; no video and no audio yet. Section 5: asking the service for the picture a topic is KNOWN BY (`diagrams.visuals_for`, `for_brief`, `showable`), what it drew for eight topics, and the four topics' chosen pictures. Sections 6 and 7: a demo made with no model call and the owner's own speech service; a drawing's pieces USED (a poster built up with beads on its arrows, an anatomy drawing zoomed, a picture's panels in turn) and what the drawing service could return to make the splitting exact. Read before changing how a script is worded, what the card maker is given, or `diagrams.py`. Live. |
| `research/approaches/09_open_diagrams.md` | 2026-10-10. Survey: free, open-licensed labelled diagrams (Wikimedia Commons) as a first place to look before the drawing service; 228 files over ten topics, licences read by program, 49 looked at, what the current reader does with them. Read before adding any outside picture source. | live (survey; nothing built) |
| `research/approaches/10_frame_and_local_pictures.md` | 2026-10-10. The owner's note that picture-left, text-right "is not giving good look": what the frame measured, two web surveys (layout evidence; local open models), the "stage" layout tried on copies of eleven lessons (one line of words at a time, picture sized by arithmetic, full-frame pictures, a light page), and a real run of the image and vision models already on the machine (Z-Image-Turbo in the owner's ComfyUI, qwen3.6 in Ollama). Read before changing `GuidedChapter`'s layout or adding a picture source. §6 (same day): the owner's idea of the SVG as skeleton and a diffusion model for the look, tried on five drawings (right for scenes, wrong for anatomy and for typeset drawings). §7: what three lessons made end to end in the stage frame changed in it. | live; the layout is in `lessonforge_workspace/pilot/stage_layout/`, not in `src/` |
| `research/approaches/11_composition_previews.md` | 2026-10-10 evening. The owner's note on composition ("render previews, detect problems, apply localized fixes … vision-based assessment … split scenes"): a lesson previewed as stills in seconds before its narration is bought, a regression test over 43 lessons, what the numbers said (290 of 605 beats were a column of 30-point lines) and the two changes they led to, a vision look at each beat's still that finds words about things the drawing does not show (since 2026-10-11 it quotes and code checks the quote), and acting on that look (2026-10-11): a picture taken off the beat it has nothing to do with (live), rewriting words (tried on three lessons, four of thirteen rewrites worse, off), the writer told what its drawing holds (live); 2026-10-12: a drawing of its own for a beat about another situation, and the look of paint on paper for posters (both live); the same afternoon: a drawing as a JSON sequence of its SVG's parts, drawn part by part when it arrives (§8). Also the correction to doc 10 §6 on repainting. | §9 (2026-10-12 evening): a drawing is drawn WITH the words: code says what the things in it are, one look says when each is drawn, code keeps the plan consistent with the drawing.
| `research/approaches/12_reference_lecture_compared.md` | 2026-10-12. A Khan Academy lecture and our lesson on the same topic, measured side by side from the videos themselves (three pairs, the third on a lesson made that day): how each is said (pace, silence, "we" and "I", pointing at the picture, repetition, pitch) and how each is shown (how much of the time something on screen changes, what is drawn when), and which gaps the pipeline has closed or not. Read it before changing the writer's voice rules or how a drawing is animated. | live |
| `research/approaches/13_board_in_the_browser.md` | 2026-10-12 evening. A stack for a real-time blackboard tutor the owner pasted, layer by layer beside what exists here; and a prototype that draws a finished lesson in the browser from its own data, in step with the audio clock (no video): what it does, what it does not, and the decision it leaves. Read it before proposing a new way to play a lesson or building on `pilot/board/`. | live |
| `research/approaches/14_annotation_harness.md` | 2026-10-12 evening. The annotation harness on top of a drawing's SVG: a model ideates what a teacher's hand adds while the voice speaks (a value where it belongs, a ring, an arrow, a line gone over), code keeps the ideas honest, places them from the drawing's geometry, checks them and lets the model correct its own annotated picture; each mark has a start and an end. What it did on four topics, the placer under load, the three sources read for ideas, and the writer-model trial. Read it before adding a kind of mark, touching `harness/annotate.py`, or changing the writer's model. | live |
| `research/approaches/15_cheap_models_strong_harness.md` | 2026-10-12 late night. Where a lesson's 0.69 USD went (by job and model), what four cheap models did on the same real inputs, the five contracts added to the harness so the small model can do the writer's, the card's, the plan's and the marks' jobs, prompt caching as measured, and what a lesson costs now. Read before changing a model route or adding a paid call. | live |
| `research/approaches/16_model_choice_writer.md` | 2026-10-14 to 15. The owner's Model Choice Protocol applied to the lesson writer: twelve frozen briefs, code checks, a judge, seven candidate models with thinking off; Qwen 3.8 Flash (thinking off) scored with Haiku 5.5 after review at a seventh of the cost; thinking remembered per model (`engine.llm.THINKING_BY_MODEL`); the writer's fallback order. Read before changing a model route or adding a model to a job's choices. | live |
| `DEV_SETUP.md` | 2026-10-15. Setting up a developer machine: system packages, Python, `.env` (what each key is for and who gives it), running the server and the app, the lesson API in one table, tests, ways to try a change without making a lesson. Read it first. | live |
| `DEPLOY_RENDER.md` | 2026-10-15. Which of the two ways to be on Render (a table), then running the server on Render as one Docker service with a disk (`../render.yaml`, `Dockerfile`): the setup steps, the cost, and what does not fit (the improver, changing tunnel addresses). | live |
| `DEPLOY_RENDER_VIEWER.md` | 2026-10-15. The finished lessons at a fixed address on Render while they are made on the GPU machine: a Cloudflare R2 bucket and a D1 database step by step (with the CORS rule the video needs), `lessonforge publish`, the Render Blueprint (`deploy/render.yaml`, entered as Render's Blueprint Path; `deploy/Dockerfile`), costs as read on the providers' pages, what does not happen on Render, a trial with no Cloudflare (`LESSONFORGE_CLOUD_DIR`). Read before touching `cloud.py`, `harness/publish.py` or `viewer.py`. | live |
| `FIXED_LINK.md` | 2026-10-15. A link that keeps its address: a named Cloudflare tunnel to this machine (`scripts/fixed_link_setup.sh` once, then `public_link.sh` as before). The free alternative to Render. | live |
| `research/experiments/2026-10-08_openrouter_run/REPORT.md` §9 | Student review and tester feedback sheets: what each question informs, where answers are stored, what the review-only link may reach. |
| `research/experiments/2026-10-08_openrouter_run/REPORT.md` §10 | The dashboard: what is counted and from when, how a visitor is identified, what the first hour of real traffic showed, and the reboot that moved the helpers into the repo. |
| `research/experiments/2026-10-08_openrouter_run/REPORT.md` §11 | One bad lesson taken apart: nine defects, each with its evidence, its cause in the generator and the change made. Read before touching the writer, the critic or the scene path. |
| `research/experiments/2026-10-08_openrouter_run/REPORT.md` §12 | Fifteen lessons' records read together: eleven things that recur, how often, the cause and the change. Start here when a lesson looks wrong: it is probably not only that lesson. |
