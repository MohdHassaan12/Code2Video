# The GyanSetu teaching systems: what each repo is and how they fit

This page is the same in every repo below. If you are new, read it first: it tells you which repo does what,
which one owns which data, and where to look before you build something that already exists next door.

Written 2026-11-02 from each repo's README, docs and commits since September 2026. Keep it short; put details in
each repo's own docs and link them here.

## The picture in one paragraph

A teacher or learner picks an NCERT topic (Classes 6-12, English or Hindi medium). **Lesson Board** plans the
lesson and teaches it live on a whiteboard. Inside the lesson it places three kinds of media made by other services:
a narrated **video** (Image Teacher's Video API, or Lesson Forge for Manim-drawn videos), a hands-on **explorer
screen** (ce-library), and a **simulation** (Prayog). Drawings come from the **diagram service** (image-gen) or are
drawn by code. Textbook text and figures come from **RAG_DB**. Every service uses cheap models through OpenRouter,
and every one follows the same rule: the model writes, code checks and repairs.

```
                         RAG_DB (NCERT text, figures, learning indicators)
                                        │
                                        ▼
  teacher / learner ──▶  LESSON BOARD  (plans the lesson, owns the lesson record, live tutor, quizzes, progress)
                          │      │      │       │
           video ◀────────┘      │      │       └────────▶ simulation: PRAYOG
  IMAGE TEACHER (board video)    │      └────────▶ explorer screen: CE-LIBRARY
  LESSON FORGE  (Manim video)    │
                                 └────────▶ drawings: IMAGE-GEN diagram service
```

## The repos

| Repo | What it is | Main language | Live at (Render) | Start reading at |
|---|---|---|---|---|
| [lesson-board](https://github.com/ManideepDonkena/lesson-board) | The hub. Live AI whiteboard tutor: plans a course, teaches with voice, cards, highlights and diagrams, answers interruptions, quizzes per learning indicator, tracks progress, teacher editor. Owns the **lesson record** that the other parts are made from. | Python + JS | lesson-board-e5s4 | `README.md`, `docs/CODEMAP.md`, `docs/lesson-contract.md` |
| [Image-teacher](https://github.com/ManideepDonkena/Image-teacher) ("image-explain") | Picture lessons and the **Video API**: finds openly licensed pictures (Wikimedia, Unsplash, lesson-board search), checks them with a vision model, explains them step by step, and renders narrated board videos (Node canvas, not Manim). Also the Picture API (labels, parts, marks). | Python + JS | image-explain-8y1u | `README.md`, `docs/video-api.md`, `docs/picture-api.md` |
| [manim](https://github.com/ManideepDonkena/manim) ("Lesson Forge") | Long narrated lesson videos drawn with **Manim CE 0.19**: storyboard, timeline compiler, scene checks, visual-action plans, code-drawn geometry and chemistry, Hindi and Sarvam voices. | Python | lessonforge-zqjk | `lessonforge/docs/README.md`, `lessonforge/docs/engine/visual-teaching-engine.md` |
| [Prayog](https://github.com/ManideepDonkena/Prayog) | Prompt to a runnable **simulation lesson** (Canvas2D draw code, sliders, readouts, practice, explore), PhET-style tools (eye toggle, probe, ruler, game levels). Makes a sim for each lesson-board "try it". | TypeScript | prayog-rpmk | `README.md`, `PIPELINE_WALKTHROUGH.md` |
| [ce-library](https://github.com/ManideepDonkena/ce-library) | One player and catalog for **Concept Explorer** modules (book, chapter, module), classes, Hindi, a lesson generator API and an editor; embeds one screen inside a board lesson. | TypeScript | ce-library-04s5 | `README.md`, `docs/ARCHITECTURE.md`, `docs/CONTENT.md` |
| [image-gen](https://github.com/ManideepDonkena/image-gen) | Fork of the GyanSetu assessment backend that now carries the **diagram service** (`standalone/diagram-service`): text brief to labelled SVG, label and arrow parts, narration-driven animation of parts. | Python | diagram-engine | `standalone/README.md`, `PROJECT_OVERVIEW.md` |
| [RAG_DB](https://github.com/ManideepDonkena/RAG_DB) | Textbook ingestion (OCR, figures, equations) into a Qdrant hybrid index; NCERT curriculum server with learning indicators and "golden" pages per teaching move. | Python | curriculum server | `README.md`, `INTEGRATION.md` |
| [concept_explorer](https://github.com/ManideepDonkena/concept_explorer) | The original Concept Explorer builder (sectioner, concept store, guided canvas, model benchmarks) and the `harness/` lesson player for exported `ui.json` lessons. Mostly superseded by ce-library for playing. | Python | - | `README.md`, `DOCS.md` |
| [Video_Notebook_LM](https://github.com/ManideepDonkena/Video_Notebook_LM) | Chapter to whiteboard explainer via NotebookLM slides, with a hand-drawn reveal kept in sync with the voice by construction. Its whiteboard paint was ported into Image Teacher. | Python | - | `ARCHITECTURE.md` |
| [Interaction_generator](https://github.com/ManideepDonkena/Interaction_generator) | Early virtual chemistry lab engine and simulations (July 2026); ideas moved into Prayog. | JS | - | `APPROACH.md` |
| [education_content_review-](https://github.com/ManideepDonkena/education_content_review-), [Stem_Animation_Manim](https://github.com/ManideepDonkena/Stem_Animation_Manim) | Planning and research notes (meeting minutes, Code2Video review, research agenda) that seeded Lesson Forge. Read-only history. | Markdown | - | `README.md` |

## Shared contracts (read before changing an API)

- **Lesson record** `lesson-board/unified-lesson/1` and **scope** `lesson-board/scope/1`: lesson-board
  `docs/lesson-contract.md`. Every video or explorer request carries the scope (objectives, include, exclude,
  prerequisites, max seconds) and the glossary (term, Hindi-book word, meaning, notation).
- **Video timeline** `video-timeline/1`: Image Teacher `GET /api/v1/videos/{id}/timeline?format=contract`. Each spoken
  line with its picture, highlights, reveals and the objectives each scene teaches.
- **Diagram service**: `POST /v1/diagrams` (brief to SVG), `/v1/diagrams/{id}/animate` (narration lines to steps).
- **Speech text**: lesson-board's shared speech text service says equations and units the same way in every app.
- **Image search**: lesson-board's shared image search is used by Image Teacher and ce-library.

## Rules every repo follows

1. **The model writes, code checks.** Numbers, counts, angles, coordinates and answers are computed or checked by
   code, never trusted from the model. When code finds a fault, the model gets the exact list once or twice, then
   the next model in the chain.
2. **Pictures move with the voice.** Each spoken sentence should change, light or point at something. Measure the
   share of time the picture changes and the longest still stretch.
3. **Cheap models, strong harness.** OpenRouter models by default, ordered fallback lists, every call logged with
   its cost.
4. **NCERT first.** Follow the textbook's words, order and the student's school medium (English or Hindi).
5. **Secrets stay in environment variables**, never in a repo, PR or chat.

## Where to put things

- A new kind of media for lessons: a service with its own repo, called from lesson-board with the scope spec.
- A new check on generated content: in the repo that generates it, with a `scripts/eval_*.py` that measures it.
- A change to a shared contract: update the doc named above in the owning repo, then this page.

When you change what a repo does, update its row in this table in every repo (search for `ECOSYSTEM.md`).
