# Literature review for educational scripts videos and feedback

The strongest implementation direction is a reviewed instructional script followed by controlled rendering, verified practice, and carefully evaluated feedback. The research below motivates that direction but does not establish that an automated pipeline is ready for this team's Classes 8 and 9 population. In particular, generation quality, human learning, and operational cost need separate measurements.

## Scope and search method

Checked on **6 October 2026**. Searches covered Code2Video, educational Manim generation, physics-video correctness, instructional design, worked examples, mathematical tutoring, and handwritten-work interpretation. Primary papers, author repositories, official documentation, and an evidence-based instructional guide were prioritized. Recent work from 2025–2026 was combined with foundational instructional and tutoring sources where useful.

This is a targeted review for implementation decisions. It is not a reproducible systematic review of every database, and it does not establish a current global model ranking. Full-paper sections were inspected for the central video studies; several adjacent tutoring papers were assessed at abstract level. The [source register](03_source_register.md) records that difference. Repository inspection is documentary, not an executed reproduction.

## Research findings by task

| Work | Contribution and evidence | Limitation relevant here | Proposed use |
| --- | --- | --- | --- |
| [Code2Video, Chen et al., 2025](https://arxiv.org/html/2510.01174v1) | Planner, Coder, and Critic generate and refine Manim videos. MMMC includes 117 full videos and 339 segments across 13 domains. TeachQuiz tests knowledge recovery in a model. | Model-based teaching scores are not Class 8–9 learning gains; curated reference content differs from this curriculum. | Compare staged generation with direct generation under equal budgets. |
| [TheoremExplainAgent, Ku et al., ACL 2025](https://aclanthology.org/2025.acl-long.332/) | Produces theorem-explanation videos longer than five minutes; evaluates 240 theorems using five automated metrics. Authors report 93.8% success for their strongest reported agent, while noting layout issues. | A reported generation-success rate does not establish classroom comprehension or error-free explanations. | Use long-form planning as a feasibility reference and inspect intermediate frames. |
| [TeachMaster, Wang et al., revised April 2026](https://arxiv.org/abs/2601.04204v2) | Educators specify pedagogical intent while coordinated planning, design, and rendering components create editable videos through code. The abstract reports large production-cost reductions. | The cost comparison is setup-dependent; this review does not reproduce it. | Maintain editable scripts and scene plans; measure local costs including human review. |
| [LLM2Manim, Joshi et al., April 2026](https://arxiv.org/html/2604.05266v1) | Uses constrained planning, a symbol ledger, narration alignment, and human review. A within-subject study with 100 undergraduates reports post-tests of 83% versus 78% for animations and slides. | Two topics at one institution, immediate outcomes, and a different age group; effects cannot be assumed for school learners. | Test synchronized narration and controlled notation, with delayed assessment. |
| [PhyEduVideo, K.M. et al., January 2026](https://arxiv.org/html/2601.00943v1) | Evaluates 205 prompts across 60 physics concepts. Finds visually coherent motion can coexist with unreliable conceptual accuracy. | Results concern the evaluated models and prompts, not every future video model. | Score individual teaching points and scientific invariants independently of aesthetics. |
| [IES practice guide, 2007](https://ies.ed.gov/ncee/wwc/PracticeGuide/1) | Recommends combining graphics and verbal descriptions, integrating concrete and abstract representations, and interleaving worked examples with problems. | It is broad instructional guidance, not a trial of this product or an exact five-question recipe. | Connect a concrete model to notation and sequence examples with practice. |
| [MathDial, Macina et al., 2023](https://arxiv.org/abs/2305.14536) | Provides about 3,000 teacher–simulated-student tutoring dialogues and a taxonomy of teaching moves. Highlights incorrect feedback and premature answer disclosure. | Simulated students and dialogue benchmarks do not replace observation of real pupils. | Define hint actions and measure whether the system reveals answers too soon. |
| [DrawEduMath, Baral et al., NAACL 2025](https://arxiv.org/abs/2501.14877) | Contains 2,030 handwritten student-work images and 11,661 teacher-authored question–answer pairs. Evaluated vision-language models leave substantial room for improvement. | English-language work and image QA are not the same as dependable Hindi or English step diagnosis. | Build a separate image-reading evaluation before enabling automatic feedback. |
| [Tutor CoPilot, Wang et al., revised January 2025](https://arxiv.org/abs/2410.03017v2) | A randomized study with 900 tutors and 1,800 pupils reports a four-percentage-point increase in topic mastery with tutor assistance. Tutors also reported grade-level mismatches. | The system supports human tutors; it does not validate replacing them with an autonomous tutor. | Give teachers a review and override path; test grade appropriateness. |
| [Bastani et al., PNAS 2025](https://hamsabastani.github.io/education_llm.pdf) | A high-school mathematics field experiment distinguishes supported practice performance from unassisted learning and finds harm from unrestricted assistance in the studied setting. | Different students and tutor design; it is not proof that every AI intervention is harmful. | Measure unassisted transfer and delayed retention, not only assisted answer completion. |
| [GeoDial, Chowdhury et al., 2026](https://arxiv.org/abs/2606.12419) | Offers over 1,300 teacher–student geometry dialogues grounded in visual highlights. Fine-tuning improves dialogue more readily than precise diagram highlighting. | A research dataset and model evaluation, not evidence that arbitrary uploaded figures can be annotated reliably. | Treat correct text feedback and correct visual localization as separate outputs. |

## Engineering resources

| Resource | Verified capability | Project implication |
| --- | --- | --- |
| [Manim Community documentation](https://docs.manim.community/en/stable/) | Programmatic mathematical animation; the stable documentation inspected identifies version 0.21.0. | Lock the renderer and dependencies used for each lesson; test compatibility before upgrading. |
| [Manim Voiceover documentation](https://voiceover.manim.community/en/stable/) | Recorded and generated speech, with timing hooks for matching animation to narration. | Use actual audio timing; independently check pronunciation of equations and Hindi text. |
| [SymPy equation-solving guide](https://docs.sympy.org/latest/guides/solving/solve-equation-algebraically.html) | Symbolic equation solving with explicit symbols and solution handling. | Verify answer keys and transformations with assumptions; symbolic equivalence alone cannot judge teaching quality. |
| [PhET research](https://phet.colorado.edu/en/research) | Documents research on interactive simulations and their educational design. | Use guided manipulation as a candidate approach when a changing variable is central to the concept. |

The [Code2Video repository](https://github.com/showlab/Code2Video) documents Manim 0.19.0, while the current Manim documentation differs. Reproduction and development should therefore use separate pinned environments until compatibility is checked. Historical provider and model choices in a repository are reproduction details, not a present-day recommendation.

## Evidence gaps and implications

**Teacher selection.** No source here establishes a worldwide best teacher for every topic. Evaluate an actual explanation, its assumptions, its examples, and its fit to the intended learners. Subscriber counts and regional identity are unsuitable quality measures.

**Video generation.** A successful render establishes executability. It does not establish that a proof is valid, a graph matches its equation, or a biological process is represented faithfully. Design a lesson-specific set of semantic checks before generating it.

**Narrative quality.** Motion is useful only when it clarifies the reasoning. The proposed comparison should include an equally well-scripted static lesson to isolate whether animation adds value beyond a better explanation.

**Question generation.** The reviewed literature does not establish an automatic generator guaranteed to produce exactly five valid, grade-appropriate problems. Constrained templates and independent solutions are therefore the recommended starting point. Free-form generation can later be compared against that baseline.

**Feedback.** Reading an image, locating a mathematical error, choosing a helpful teaching move, and placing a highlight are distinct tasks. Evaluate them separately; otherwise an incorrect transcription can be mistaken for poor student reasoning.

**Three learner levels.** The meeting's priority is a strong common lesson. Later variants should respond to prerequisite evidence and demonstrated needs. They should preserve conceptual truth and allow learners to change routes.

**Classroom validation.** Teacher and strong-student approval can identify quality problems, but broader usability requires pupils with varied prior knowledge. A small local trial can guide revision; it should not be represented as proof of population-wide learning gains.

## Testable project hypotheses

| Hypothesis | Comparison | Primary outcome |
| --- | --- | --- |
| Reviewed scripts improve generated lessons | Topic-only generation versus approved-script generation | Critical conceptual defects per lesson |
| Explicit scene contracts reduce inconsistency | Free-form scene prompt versus structured script, notation, and invariants | Scene errors and human repair minutes |
| Visual review catches additional defects | Runtime checks alone versus runtime plus frame and teacher review | Confirmed missed visual errors |
| Animation improves learning for selected concepts | Matched narrated static lesson versus animated lesson | Unassisted transfer performance |
| Targeted hints support learning | Answer-first assistance versus staged hints, where appropriate to the study | Independent correction and delayed performance |
| Reusable components reduce accepted-production cost | Free-form scenes versus approved templates | Total cost per accepted lesson |

These are proposed experiments. No local measurements or outcomes are asserted.
