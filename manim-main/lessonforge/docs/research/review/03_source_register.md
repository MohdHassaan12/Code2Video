# Source register and verification scope

All entries were checked on **6 October 2026**. Dates below distinguish first publication from revisions where observed. Inspection depth describes what supports this review; it does not imply experiments were reproduced. Source numbers provide stable handles for future updates.

| ID | Primary source | Date or version | Inspection and use |
| --- | --- | --- | --- |
| S01 | [Chen, Lin, and Shou, Code2Video](https://arxiv.org/html/2510.01174v1) | 2025, arXiv v1 | Full HTML sections on method, benchmark, and metrics; central video reference |
| S02 | [Show Lab Code2Video repository](https://github.com/showlab/Code2Video) | Live README checked 2026-10-06 | Setup, runners, evaluation entry points, and license label; no code execution or pinned commit audit |
| S03 | [Ku et al., TheoremExplainAgent](https://aclanthology.org/2025.acl-long.332/) | ACL 2025 | Publication record, abstract, and paper opening; long-form feasibility and layout limitations |
| S04 | [Wang et al., TeachMaster](https://arxiv.org/abs/2601.04204v2) | First submitted 2025-12-07; revised 2026-04-25 | Abstract and version record; adjacent production architecture, no cost reproduction |
| S05 | [Joshi et al., LLM2Manim](https://arxiv.org/html/2604.05266v1) | 2026-04-07, preprint v1 | Method, study summary, and limitations; narrated animation and learner evaluation |
| S06 | [K.M. et al., PhyEduVideo](https://arxiv.org/html/2601.00943v1) | 2026-01-02, preprint v1 | Benchmark design and findings; physics teaching-point accuracy |
| S07 | [IES, Organizing Instruction and Study to Improve Student Learning](https://ies.ed.gov/ncee/wwc/PracticeGuide/1) | September 2007 | Official recommendations; learning-design foundation |
| S08 | [Macina et al., MathDial](https://arxiv.org/abs/2305.14536v2) | First submitted May 2023; v2 October 2023 | Abstract and publication status; tutoring moves and answer disclosure |
| S09 | [Baral et al., DrawEduMath](https://arxiv.org/abs/2501.14877) | January 2025; NAACL 2025 | Abstract and dataset description; student-work reading benchmark |
| S10 | [Wang et al., Tutor CoPilot](https://arxiv.org/abs/2410.03017v2) | October 2024; v2 January 2025 | Abstract and trial summary; human tutor assistance |
| S11 | [Bastani et al., Generative AI without guardrails can harm learning](https://hamsabastani.github.io/education_llm.pdf) | PNAS 2025 | Author-hosted manuscript and indexed publication record; assisted versus unassisted outcomes |
| S12 | [Chowdhury et al., GeoDial](https://arxiv.org/abs/2606.12419) | 2026; primary page lists submission 2026-05-08 | Abstract and dataset description; visual feedback. Use the primary page's date, not an inferred date from identifier or search age. |
| S13 | [Manim Community](https://docs.manim.community/en/stable/) | Stable documentation 0.21.0 at access | Official rendering documentation; separate from upstream historical version |
| S14 | [Manim Voiceover](https://voiceover.manim.community/en/stable/) | Documentation 0.3.7 at access | Feature documentation; recording, speech services, and timing |
| S15 | [SymPy equation solving](https://docs.sympy.org/latest/guides/solving/solve-equation-algebraically.html) | Documentation 1.14.0 at access | Official guide; symbolic checking |
| S16 | [PhET research](https://phet.colorado.edu/en/research) | Live research portal | Official research overview; simulation design reference, not a topic-level review |
| S17 | [3Blue1Brown](https://www.3blue1brown.com/) | Live lesson catalogue | Official catalogue inspected; candidate visual teaching reference, no lesson quality ranking |
| S18 | [NCERT textbooks](https://ncert.nic.in/textbook.php) | Current portal, edition unresolved | Official portal located in search; direct fetch failed. No exact chapter or current edition claim relies on it. |
| S19 | [HHMI BioInteractive classroom resources](https://www.biointeractive.org/classroom-resources) | Current resource catalogue | Official resource results located; direct fetch failed. Candidate for later topic-level review only. |

## Evidence handling

Reported numerical results belong to their original study population, setup, and metrics. They are not expected outcomes for this project. Research preprints, published studies, software documentation, and resource catalogues have different evidential roles. The workstream proposals are engineering and instructional judgments informed by these sources, not features automatically provided by them.

## Updating this review

For a newly found paper, record: exact title; authors; version and date; URL; task; learner population; comparison baseline; sample size; evaluation method; human involvement; code/data availability; major limitation; and the concrete project decision it could change. Prefer a source that changes a decision over a longer list of loosely related papers.

Before implementation, inspect the full methods of any paper whose evaluation protocol will be adopted. Before a curriculum claim, verify the school's actual board, year, language, and textbook edition. Before a model comparison, record the model identifier actually available and used.
