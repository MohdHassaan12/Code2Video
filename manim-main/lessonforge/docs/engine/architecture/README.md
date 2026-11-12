# Architecture diagrams

**The written spec lives at [reference-architecture.md](reference-architecture.md)** —
the full reference architecture for the video engine (IR ladder, layer contracts,
agent specs, formal properties, renderer extensibility). The diagrams below are the
visual companions.

Visual architecture overviews for the Concept Explorer video pipeline — one full-system
map plus one diagram per subsystem. Each diagram exists as an `.html` source (edit this)
and a rendered `.png` (share this).

| # | Diagram | What it explains |
|---|---------|------------------|
| 00 | [System overview](00-system-overview.png) | Full flow: `ce/` client pipeline → `stem_animation_lab` server → outputs, plus LLM providers, quality invariants, env knobs |
| 01 | [ce/ video pipeline](01-ce-pipeline.png) | The client side: lesson nodes → per-node video build → HTTP calls to the lab server → merged lesson videos |
| 02 | [Lab server internals](02-lab-server.png) | `stem_animation_lab/app.py`: endpoints, storyboard generation, codegen, render engine, TTS, sidecars, bulk & timeline |
| 03 | [Layout enforcement v5](03-layout-enforcement.png) | Overlap probe → LLM repair loop: detection classes, accept/reject gate, loser hygiene, split-screen management |
| 04 | [Deterministic transpiler](04-transpiler.png) | `transpiler.py`: storyboard JSON → Manim code with zones, entrance animations, per-scene scripts |
| 05 | [Tooling & testing](05-tooling-testing.png) | Debug sandbox, /timeline UI, debugging discipline, the seven LLM-stubbed test harnesses |

## Re-rendering after an edit

Diagrams are plain HTML styled by the shared [style.css](style.css). After editing an
`.html`, re-render its `.png` with Playwright (already installed on this box):

```bash
cd docs/architecture
npx playwright screenshot --viewport-size "1560,900" --full-page <name>.html <name>.png
# or all of them:
./render.sh
```

Keep diagrams in sync with CLAUDE.md — when a pipeline stage changes, update the
matching diagram in the same pass.
