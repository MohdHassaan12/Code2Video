# Paper and code comparison for long form educational video

The strongest starting point is a combination of whole-lesson planning, a shared audiovisual specification, reusable executable graphics, and independent verification. No inspected repository by itself establishes the complete narration-led, consistently correct 20-minute product described in the requirements.

Four repositories were cloned for inspection, with immutable commit IDs in [repository_manifest.json](repository_manifest.json). Their original license files remain in the clones. The audit concerns the paths below; it is not an end-to-end reproduction of their benchmarks. The small OpenRouter experiment uses original prompts and is reported separately.

## Research systems and useful contributions

| System | Useful contribution | Relevance to this project | Evidence boundary |
| --- | --- | --- | --- |
| Code2Video | Outline and storyboard stages, section coding, scope-guided fixes, spatial anchors and visual critique | Main reference for modular code production and targeted layout repair | Its benchmark scores and reference-video lengths do not establish our full-lesson quality |
| Manimator from HyperCluster | Paper/text to scene description to Manim code | Simple ingestion and direct-generation baseline | Lightweight path; not a ready-made teacher-data or temporal-layout validation system |
| TheoremExplainAgent | Scene planning, narration, technical plans, code, optional context examples and RAG | Best inspected starting reference for coordinated narration and code experiments | Reported theorem-video results do not transfer automatically to school curricula |
| TeachMaster | Manuscript expansion/refinement, pagination, separate visual/audio streams, representation routing | Useful long-form planning and production design | Paper/platform examined; executable implementation not located in the inspected sources |
| EduVisAgent | Specialized pedagogical feedback and intermediate teaching plans | Useful script/visual-design critique roles and interactive-content direction | Inspected orchestration ends in UI plans; not evidence of a narrated video compiler |
| LASEV | Separate solution, illustration, and narration with multiple quality gates | Useful structured compilation and production-scale design | Reported costs concern short problem videos; public linked repository inspected as a project site |
| LLM2Manim | Symbol consistency, speech alignment, expert review, learner evaluation | Useful quality protocol and shared notation register | Limited learner study; not a general autonomous-production guarantee |
| PhyEduVideo | Separates physical/conceptual accuracy from visual appearance | Useful science defect taxonomy and evaluation prompts | Benchmark reference, not a long-form generation engine |

### Code2Video

The paper describes a planner/coder/critic architecture, increasingly broad repair scopes, and a 6-by-6 visual anchor scheme. Its MMMC source corpus contains complete videos and shorter segments; the mean complete reference length is about 16.9 minutes. That is a property of reference data, not proof that every generated result has the same duration or teaching depth. The reported table uses token consumption and generation time per topic, which cannot be converted into a current dollar quote without input/output splits, model prices, and attempt accounting. [Paper](https://arxiv.org/html/2510.01174v1)

The useful lesson is to separate planning, executable generation, and rendered-output critique. The gap for our design is stronger audio control, explicit cross-section state, geometry-based checks, and verified repair acceptance.

### Manimator

The paper presents scene-description generation followed by Manim code generation and rendering from text or research papers. Use it as the minimal staged baseline for testing whether richer planning and verification justify their cost. [Paper](https://arxiv.org/html/2507.14306v1)

There are several unrelated projects named Manimator. The cloned repository is [HyperCluster-Tech/manimator](https://github.com/HyperCluster-Tech/manimator), the paper-associated project identified during this review. Features from other same-name repositories must not be attributed to it.

### TheoremExplainAgent

The paper targets multimodal theorem explanations and acknowledges layout inaccuracies. Its appendix reports substantial prompt growth with RAG and historical per-video costs across older models. These are useful warnings about repeated context, not current quotations. [Paper and runtime table](https://arxiv.org/html/2502.19400v1)

The local code exposes separate scene-plan, visual-storyboard, technical-implementation, narration, and code example collections, plus optional RAG. That makes it useful for controlled ablations instead of introducing every mechanism at once. Its corpus and task differ from the proposed expert school-teacher dataset.

### TeachMaster

TeachMaster describes manuscript skeletonization, expansion, duration refinement, pagination, and separate visual and audio streams. Its routing mechanism distinguishes code-native graphics from scenes using generated image assets. It reports an 8×A800 deployment, more than 30,000 minutes generated, and approximately $83.70 for a 45-hour course. These are author-reported deployment claims with a different workflow and cost boundary from ours; they are not an all-in quotation including our expert review and development. [Paper](https://arxiv.org/html/2601.04204v2)

Borrow the manuscript and dual-stream organization. Add explicit object-state continuity because pagination alone does not specify what persists between chunks. The inspected paper linked [the platform](https://www.teachmaster.cn/); a reproducible source implementation was not located in those inspected materials.

### EduVisAgent

The project structures teaching plans and gathers feedback from specialized roles before producing presentation plans. The benchmark targets reasoning-driven pedagogical visualization. [Paper](https://arxiv.org/abs/2505.16832), [repository](https://github.com/aiming-lab/EduVisAgent)

Use its critique decomposition as an experimental script/design pass: visual representation, information expression, cognitive strategy, and overall learning strategy. Do not confuse a well-reviewed web UI plan with a synchronized audiovisual lesson. Additional narration, rendering, state, and playback contracts are required.

### LASEV

The HTML paper uses the name LASEV, while some abstract/search records use LAVES. The system separates solution reasoning, illustration, and narration, then assembles an executable specification with semantic, tool, and rule checks. It reports less than $0.07 for a roughly two-minute problem video and very high deployment throughput. Those figures concern its reported production setup, not six local GPUs or rich 20-minute lessons. [Paper](https://arxiv.org/html/2602.11790v1)

The linked [public repository](https://github.com/RobitsG/LASEV) exposed a project page, assets, and example videos in the inspected listing, rather than the production generation engine. Borrow the quality-gate design; do not schedule a reproduction assuming the implementation is available there.

### LLM2Manim and PhyEduVideo

LLM2Manim combines narration alignment, symbol consistency, local regeneration, and human review. It reports a 100-undergraduate study with two STEM topics and better immediate results than its slide condition. This supports studying learner outcomes, while leaving school-age transfer, long-term retention, and broad production reliability unresolved. [Paper](https://arxiv.org/html/2604.05266v1)

PhyEduVideo evaluates generated physics explanations and distinguishes conceptual correctness from perceptual quality. Use its subject-specific framing to add checks for conservation, forces, direction, scale, and causal explanation where applicable. It is not evidence that attractive generated motion obeys the governing physics. [Paper](https://arxiv.org/abs/2601.00943)

## Findings from the cloned code

### Code2Video layout and repair behavior

The inspected [base class](repositories/Code2Video/prompts/base_class.py) creates a title, left lecture-text block, and right-side anchors. Its `place_in_area` computes a center and applies a supplied scale. It does not measure an object's extent and enforce containment in the declared area. Therefore an area assignment is placement guidance, not a fit guarantee. Our compiler needs measured geometry and a separate acceptance check.

The inspected [repair implementation](repositories/Code2Video/src/scope_refine.py) includes a quick validation helper that alters the scene body to return early, then imports and instantiates the scene. It does not run the full original animation. The main [agent](repositories/Code2Video/src/agent.py) subsequently invokes actual Manim rendering in its debug loop. Keep both facts: the quick helper is limited, but the pipeline does have later rendering.

`GridCodeModifier.parse_feedback_and_modify` recognizes a restricted textual format containing line numbers and placement calls. It can return unchanged code when no edit is parsed. In the inspected `generate_section_code` feedback path, a returned unchanged string is not an exception, so it can bypass the model-based fallback. The subsequent successful render alone cannot show that the visual issue was fixed.

A small isolated check of this inspected helper confirmed that unstructured feedback returned unchanged code, whereas a correctly formatted line replacement changed it. Results are saved in [code_audit_checks.json](code_audit_checks.json). This is a helper-level finding, not a measured failure rate for the full repository.

No `add_sound`, voiceover, TTS, or audio matches were found in the inspected `src` and `prompts` trees. The base class displays lecture text. Our narration-led pipeline therefore requires an explicit audio and synchronization stage rather than assuming that those release paths already provide it.

### Manimator generation and endpoint behavior

The [animation generator](repositories/Manimator/manimator/api/animation_generation.py) requests code through LiteLLM and includes overlap/cleanup instructions in the prompt. Its `num_retries=2` argument is an API-call retry setting, not evidence of a rendered-layout correction loop.

The inspected [animation endpoint](repositories/Manimator/manimator/main.py) generates code, extracts a scene class, renders, and returns a video or error. This path is a useful simple baseline. It does not itself establish an iterative visual-quality controller, full-lesson continuity, or expert-teacher scripting. The corresponding [scene-description code](repositories/Manimator/manimator/api/scene_description.py) is useful for the preceding text/PDF interpretation stage.

### TheoremExplainAgent and EduVisAgent interfaces

TheoremExplainAgent's [VideoPlanner](repositories/TheoremExplainAgent/src/core/video_planner.py) separately loads context examples for scene plans, visual storyboards, technical implementations, narration, and code. Its [CodeGenerator](repositories/TheoremExplainAgent/src/core/code_generator.py) includes generation, error-fix, and retrieval paths. Its [VideoRenderer](repositories/TheoremExplainAgent/src/core/video_renderer.py) includes optional visual reflection and scene assembly. These are useful boundaries for experiments, but runtime behavior was not reproduced in this audit.

EduVisAgent's inspected [intermediate system](repositories/EduVisAgent/agents/teach_agents_intermediate_system.py) collects specialist feedback for each teaching-plan part, synthesizes a revision, and generates UI plans referencing Shadcn/UI components. The path ends by saving plans. Treat it as a planning reference; do not count those artifacts as executable video output.

## Proposed combination of methods

Use one shared specification rather than chaining independent agents that repeatedly rewrite each other's outputs:

```text
Expert teaching episodes + verified subject evidence
                         |
            Whole lesson manuscript and concept graph
                         |
        Narration anchors + visual state and event contracts
                 /                           \
        Speech generation              Component/code generation
                 \                           /
                  Measured timeline and preview render
                               |
        Subject checks + temporal geometry + selective visual critique
                               |
               Scoped repair or specification revision
                               |
        Boundary checks + whole lesson review + final render
```

The design borrows modular generation and scoped repair from Code2Video, narration/planning interfaces from TheoremExplainAgent, whole-manuscript organization from TeachMaster, quality-gate separation from LASEV, and pedagogical critique ideas from EduVisAgent. It adds explicit state contracts, a common parameter source for equations and graphics, measured audio timing, and independent temporal layout checks. This combination is a proposed architecture, not a previously validated research result.

Use Manimator-style staged generation as the simple baseline. Compare the combination component by component before claiming an advantage. Avoid copying every agent role: repeated critiques increase cost and can introduce contradictory edits. Each stage must own a defined artifact, report an observable defect, or enforce a testable requirement.
