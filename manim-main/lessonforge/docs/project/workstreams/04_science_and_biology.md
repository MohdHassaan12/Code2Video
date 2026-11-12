# Science and biology representations

Build diagrams and animations that explain a mechanism and preserve scientific meaning. A moving illustration is useful when the learner can identify what changes, what stays fixed, and why.

## Scope and formal task

Input: subject objective, verified explanation, labeled entities, relationships, and assumptions. Output: reviewed scene contracts, assets, and where appropriate a simulation with state x(t), parameters theta, and explicitly defined update rules.

For a quantitative model, validate constraints g(x, theta) within a declared numerical tolerance. For a qualitative biological model, validate entity identities, containment, sequence, causal claims, and stated simplifications. Avoid presenting an illustrative model as a measurement of actual biological motion.

## Literature implications

[PhyEduVideo](https://arxiv.org/html/2601.00943v1) separates conceptual accuracy from visually smooth output. [PhET's research portal](https://phet.colorado.edu/en/research) is a useful reference for designing guided interactions. [HHMI BioInteractive](https://www.biointeractive.org/classroom-resources) is a candidate biology resource for a later topic review; its individual resources were not evaluated here.

## Proposed first topics

Curriculum placement is provisional pending the school's edition.

| Subject | Candidate | Teaching move | Scientific checks |
| --- | --- | --- | --- |
| Physics | Uniform motion and distance–time graphs | Move a marker while plotting the same state | Distance, elapsed time, speed, axes, and units agree; a stationary interval is represented correctly |
| Biology | Cell structures and functions | Progressively reveal a simplified labeled cell | Boundaries and labels match the selected cell type; a cell wall is not conflated with its membrane; simplifications are stated |
| Science extension | Particle model of changes of state | Track particle arrangement and motion in a bounded schematic | Do not imply that individual particles expand to explain every bulk change; review temperature and phase claims |

## Proposed approach

Create a scientific specification before illustration. Name every entity and relationship and list likely misconceptions. Use approved vector diagrams or original schematics with controlled labels. Separate physical coordinates from screen coordinates, especially when zooming or exaggerating scale.

When dynamics matter, generate them from a model and explain its assumptions. When dynamics are not essential, use a carefully sequenced static diagram. A short interaction should ask the learner to predict a change before adjusting a parameter, then compare the result with the prediction.

For biology, require a subject expert to review both the diagram and the narration together. A correctly labeled still image may become misleading during a transition. Check end states and intermediate frames, including arrow direction, containment, and implied causation.

## Deliverables and acceptance

For the first meeting review: one physics brief and one biology brief, each with script, storyboard, asset requirements, scientific checks, and a reviewer field. For the next milestone: one accepted video per subject and associated practice.

Acceptance requires no false causal claims, correct labels and units, visible model assumptions, and consistency between the visual and explanation. Every animation should serve a named learning objective.

Suggested owners: science and biology authors to be named, working with the video implementers. Dependencies: topic selection, trusted subject sources, and asset availability. Evaluate through teaching-point accuracy and learner explanations; aesthetic scores are secondary. Main risk: a visually plausible process that teaches the wrong mechanism.
