# Code2Video assessment and adoption approach

Use Code2Video as a research baseline and architectural reference for script-controlled educational animation. Before adopting its full pipeline, prove a smaller version on one approved lesson and compare it with a manually authored baseline. This assessment is based on the public paper and repository, not a local execution.

## What the research establishes

The paper separates temporal planning, executable animation generation, and visual critique. Its repair mechanism targets code scope, and its critic uses visual anchors to improve layout. TeachQuiz is a model-based metric built around suppressing and recovering target knowledge; it should not be interpreted as a measured improvement in pupils' learning. The published benchmark and experiments support feasibility, with transfer to this school's curriculum still to be tested. [Code2Video paper](https://arxiv.org/html/2510.01174v1).

The repository exposes a single-topic runner, a benchmark runner, API configuration, and evaluation scripts. It lists MIT licensing and describes dependencies on language and vision models and visual-asset services. Its documentation also records an icon-service workaround. These details make environment pinning, asset caching, and recorded configuration relevant to reproduction. [Official repository](https://github.com/showlab/Code2Video).

## Proposed adaptation for this project

The following is a project design, not a claim that upstream implements every feature.

| Stage | Proposed input and output | Acceptance condition |
| --- | --- | --- |
| Approved content | Objective, original script, sources, prerequisites, five-problem plan | Independent teacher review completed |
| Scene planning | Script to ordered scenes with exact objects, narration, and checks | Every objective maps to a scene and assessment item |
| Code generation | One scene contract to renderable code | Restricted build completes; expected objects exist |
| Semantic verification | Equations, units, coordinate relationships, diagram labels | All declared lesson invariants pass |
| Visual inspection | Rendered frames at transitions and steady states | No misleading or unreadable critical content |
| Local correction | Defect tied to scene and reason | Correction passes affected checks without changing approved content |
| Narration and assembly | Approved speech, timestamps, captions, scene clips | Spoken and displayed mathematics agree |
| Final review | Complete lesson and practice set | Teacher accepts package for the next pilot stage |

Freeze the approved script before the comparison. Allow code repair to change layout and timing, but send any proposed factual change back to the subject reviewer. Preserve stable identifiers for symbols and visual objects across scenes. Keep calculations outside free-form narrative generation where possible.

## Adoption options

| Option | Benefit | Cost or limitation | Recommendation |
| --- | --- | --- | --- |
| Manual Manim from approved script | Strong control and clear reference implementation | Authoring effort | Required baseline for the first lesson |
| Direct model-to-Manim from approved script | Small integration surface | May require extensive repairs | Include in comparison |
| Adapted staged pipeline | Explicit plans and localized review | More orchestration and model calls | Main experimental candidate |
| Full upstream reproduction | Closest comparison with reported setup | Dependency, provider, and asset integration work | Separate follow-up; avoid making it a prerequisite for the first demo |
| Pixel-generated technical scenes | Potentially useful contextual imagery | Exact labels, geometry, and dynamics need verification | Optional controlled comparison, outside the initial critical path |

## Reproduction checklist

1. Record repository URL, selected commit, date, license file, and environment specification.
2. Inspect runner arguments and configuration at that commit. Keep credentials outside tracked files and build logs.
3. Use the documented historical environment first. Check provider availability separately; log substitutions because they change the experiment.
4. Confirm asset retrieval or supply a small reviewed local asset set. Track permissions per asset rather than assuming the code license covers videos or icons.
5. Run one short topic and preserve every attempted output, prompt, model identifier, exception, and repair.
6. Render the approved common lesson. If upstream planning changes its content, record that as a different condition rather than silently calling it the same script.
7. Compare the output with the manual reference using the project's semantic and visual rubric.
8. Run broader benchmark work only after the single-lesson environment is stable and the budget is known.

No clone, installation, API request for generation, or benchmark execution is included in this review.

## Proposed comparison

Use three topics: like terms, reading a distance–time graph, and a cell structure/function explanation. Curriculum placement must be confirmed. For each topic, prepare one script and teacher-reviewed reference storyboards.

For the larger engineering comparison, use four conditions: manual reference; direct generation; structured generation with runtime correction; structured generation with runtime correction plus visual and semantic review. Use three generation attempts for each automated condition: 27 automated attempts plus three manual references. If that exceeds capacity, begin with the math topic and three automated attempts per condition, then expand. These are proposed sample counts, not research requirements.

Record final correctness, number and severity of defects, repair count, human minutes, elapsed time, and total cost. Cap automated repair at two rounds per scene for the demonstration; keep unresolved cases in the results. Automated and manual review budgets must be visible, since extra intervention can explain improvements.

## Engineering constraints

- Execute generated scene code in a restricted worker with no production credentials, a bounded output directory, timeouts, and memory limits.
- Pin rendering dependencies, fonts, mathematical typesetting, and output settings. Cache reviewed assets and generated audio.
- Render short scenes independently. Rebuild dependent scenes if notation or shared objects change.
- Check the beginning, middle, and end of transitions. A single final frame can miss a misleading intermediate state.
- Calculate plotted points from the same mathematical object used for the displayed equation.
- Keep question generation and student-feedback services outside the renderer. Their failures and evaluation needs differ.

## Decision rule

Adopt the staged pipeline only if it improves accepted output quality or reduces total production effort relative to the simpler baseline. Render success alone is insufficient. If the manual baseline remains more reliable for the first few lessons, use it while collecting targeted failure cases for later automation work.
