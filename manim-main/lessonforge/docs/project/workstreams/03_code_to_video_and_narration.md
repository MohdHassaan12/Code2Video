# Code to video and narration

Convert approved scripts into accurate, editable, short videos with synchronized audio. The first goal is one complete, inspectable lesson from each implementer, with a shared reference script for comparison.

## Scope and formal task

Given scene contracts S, verified assets V, narration A, and locked environment E, produce executable code C and video Y = Render(C, V, A, E). For each declared semantic invariant I, check I(C, Y); a successful process exit is only one required condition.

Examples of invariants are a plotted point satisfying its equation, an unchanged exponent during addition of like terms, and the same symbol representing the same quantity throughout.

## Literature implications

See the [Code2Video assessment](../research/02_code2video_assessment.md) for the central baseline. [TheoremExplainAgent](https://aclanthology.org/2025.acl-long.332/) is evidence that multi-minute generation is feasible while layout defects remain relevant. [Manim Voiceover](https://voiceover.manim.community/en/stable/) documents narration timing support; it does not validate the correctness of spoken content.

## Proposed approach

Start with approved templates for equation transformations, coordinate plots, grouped algebra tiles, and labeled diagrams. Generate scene parameters before free-form code. Use explicit object identifiers and stable layout regions. Keep mathematical values as structured data shared by equations, figures, and answer checks.

Render low-resolution drafts per scene, run numerical or symbolic checks, then inspect frames and transitions. Allow two automatic correction rounds before manual intervention for the demonstration. Preserve the failing output and defect reason. Once content and layout pass, produce final audio, align motion with its actual timing, and render the final lesson.

For y = 2x + 3, calculate points from that expression, check intercept (0,3), and verify that a unit change in x increases y by 2. Distinguish coordinate slope from apparent screen angle when axis scales differ. This is a proposed regression scene, not a claim about the chosen curriculum.

## Narration and packaging

Use a teacher recording if speech generation delays the prototype. Include a pronunciation table for exponents, fractions, units, and Hindi terms. Captions should match narration while displayed mathematics retains standard notation. Avoid cutting a scene before the explanation or reading pause completes.

Package MP4, captions, script version, scene code, assets, environment lock, checks, and review log. Preserve the ability to replace a scene without regenerating unrelated content.

## Acceptance and measurements

Zero unresolved critical mathematical errors; no clipped essential content; consistent notation; equations and audio agree; all key objects readable at the intended display size; final duration at most 15 minutes. Time the finished video, not only the script estimate.

Track first-pass render rate, final accepted rate, correction rounds, human repair minutes, generation cost, render time, and cost per accepted video minute. Include failed attempts in cost.

Owners: Manideep and Durgesh, as directed in the meeting. A proposed split is Manideep for geometry and rendering, Durgesh for assembly and narration, but both should show an attributable demonstration. Main dependency: approved script. Main risks: content drift, layout overlap, provider changes, and unbounded correction loops.
