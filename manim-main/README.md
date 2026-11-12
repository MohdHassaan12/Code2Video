# manim

Narrated STEM lesson videos, made by a pipeline instead of by hand. The working project is **[`lessonforge/`](lessonforge/)**.

| folder | what it is |
|---|---|
| [`lessonforge/`](lessonforge/) | the project: a lesson server and pipeline (topic or pasted script → script → narration → Manim video with captions, question stops and checks), and the app for web, Android and iOS (`lessonforge/clients/lessonforge-app`) |
| `concept_explorer/`, `Stem_Animation_Manim/`, `education_content_review/` | git submodules: the three original repositories lessonforge was merged from (see `lessonforge/PROVENANCE.md`); nothing needs them |

## Start here

- **Set it up:** [`lessonforge/docs/DEV_SETUP.md`](lessonforge/docs/DEV_SETUP.md) covers system packages, Python,
  settings, the server, the app, the API and tests.
- **What it does and how a video is made:** [`lessonforge/README.md`](lessonforge/README.md).
- **Rules learned from real failures (read before changing a part):** [`lessonforge/CLAUDE.md`](lessonforge/CLAUDE.md).
- **Every document, and whether it is current:** [`lessonforge/docs/README.md`](lessonforge/docs/README.md).

## Branches

`main` is the line everyone builds on. Work goes on a branch and comes in through a pull request.
