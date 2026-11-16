# Figure prompts

Two sets of images can be generated from prompts and dropped into `paper/figures/`.

- **Part A, paper figures F1–F6.** Method figures in the style of the Code2Video paper's Figures 1, 3 and 4. They
  have panels, short labels, icons and arrows, and they explain how the pipeline and the measure work. These are
  the ones the paper needs.
- **Part B, illustrations P1–P6.** Optional pictures for the long report, with no text.

**Data figures are not generated.** Every chart and table comes from the result files via `paper/make_figures.py`
and `paper/make_tables.py`. The F figures contain no measured numbers, except the two marked in F5, which must
match the report.

**How to use them:**

1. Paste the shared style block, then the figure's prompt, into an image model that can write short labels, for
   example ChatGPT image generation, Gemini image generation or Ideogram.
2. Check every label's spelling against the list in the prompt. Regenerate, or fix it in an editor, if a word is
   wrong.
3. Save the image under the file name given, in `paper/figures/`, and run `paper/build.sh`. It replaces its
   placeholder box in `main.pdf`, `report.pdf` and `long_report.pdf`.

**If the labels come out garbled:** generate it again with "no text" added, then put the labels in yourself (Figma,
PowerPoint, draw.io or Inkscape) from the label list. Paper figures are usually finished this way.

---

# Part A: paper figures

## Shared style block (paste before every F prompt)

> Academic paper method figure, in the clean style of ICLR/CVPR system diagrams. Pure white background. Content
> sits in large rounded-rectangle panels with very light pastel fills and thin coloured borders: light grey
> (#F3F4F6), mint green (#E9F6EE, border #6CC08B), lavender (#F2ECFA, border #A98BD6), peach (#FDEEE6, border
> #EE9A75), pale yellow (#FFF8E0, border #E8C547) and pale blue (#EAF2FC, border #6FA3E0). Each panel has a short bold
> title at the top centre in a serif font, for example "(i) Planner". Secondary labels are small italic serif text.
> Icons are flat, colourful and friendly, in a consistent Flaticon-like style: a student at a laptop, a small
> robot head, a teacher, a database cylinder, a code window marked "</>", a gear, a magnifying glass, a wrench, a
> clipboard quiz sheet. Video frames are small dark rectangles (near-black) with simple coloured mathematical
> shapes on them (dots, arrows, a parallelogram, a curve), like Manim animation frames. Status badges are small
> filled circles: green with a white check mark, red with a white cross. Arrows are thin and grey with small
> heads; important flows are dashed red. Code and JSON snippets are tiny monospace text on light-grey cards and only
> need to look like code. Generous spacing, no clutter, no gradients, no 3-D, no shadows except a very soft one
> under panels. Landscape. All text in English and spelled exactly as given.

## F1, overview (like Code2Video's Figure 1): `fig_overview.png`

Aspect 2:1. Where it goes: the start of the paper and of the long report.

> Two rows of panels.
>
> **Top row, two panels side by side, joined by a thick hollow green arrow pointing right.**
>
> Left panel, light grey, title "TeachQuiz (Code2Video)":
> - a speech bubble with the italic words "learning topic" and inside it "Determinant";
> - an arrow to a small robot head wearing a sleep mask, with a caption bubble "forget this topic";
> - an arrow to a quiz sheet whose answer boxes all read "NULL";
> - below, three red cross badges with bold italic labels: "refuses", "already knows", "grading bug".
>
> Right panel, mint green, title "Our measurement":
> - the same speech bubble, but inside it "Tovan sum (invented)";
> - an arrow to the same robot without the mask, holding a pencil over a sheet with circles A B C D, one filled;
> - an arrow to a small bar of four segments labelled "no video", "3 frames", "start/end", "dense video";
> - below, three green check badges with labels: "must choose", "prior measured", "cannot be known".
>
> **Bottom row, two panels side by side.**
>
> Left panel, pale blue border, title "How to repair — Learner feedback". Three small rounded boxes in a row:
> - "(i) Practice quiz", subtitle "student answers DEV";
> - "(ii) Find weak section", subtitle "debugger-style";
> - "(iii) Small edit", subtitle "rewrite only that part".
>
> Under them a mini flow: a film strip of 4 frames, one frame glowing orange under a magnifying glass, an arrow to
> a code window with one line highlighted, and a circular arrow back to the film strip.
>
> Right panel, peach border, title "How to evaluate — D-VGAIN + NOVEL-12". Three small rounded boxes:
> - "(i) Gain over prior", subtitle "what it did not know";
> - "(ii) Frames vs. video", subtitle "is motion needed?";
> - "(iii) Invented concepts", subtitle "no model has seen them".
>
> Under them a mini flow:
> - a clipboard labelled "TEST";
> - a lock icon, with the italic caption "never seen by the pipeline";
> - a robot answering;
> - a small upward arrow labelled "gain".
>
> **Labels to check:** TeachQuiz (Code2Video), learning topic, Determinant, forget this topic, NULL, refuses, already
> knows, grading bug, Our measurement, Tovan sum (invented), no video, 3 frames, start/end, dense video, must choose,
> prior measured, cannot be known, How to repair — Learner feedback, (i) Practice quiz, student answers DEV,
> (ii) Find weak section, debugger-style, (iii) Small edit, rewrite only that part, How to evaluate — D-VGAIN +
> NOVEL-12, (i) Gain over prior, what it did not know, (ii) Frames vs. video, is motion needed?, (iii) Invented
> concepts, no model has seen them, TEST, never seen by the pipeline, gain.

## F2, the pipeline in detail (like Code2Video's Figure 4): `fig_pipeline.png`

Aspect 2:1. Where it goes: the pipeline section of the paper, and Step 3 of the long report.

> **A wide light-grey top band**, reading left to right:
>
> 1. Italic heading "Input: topic". A student-at-desk icon with a speech bubble "What is a tovan sum?". Under it, a
>    small card icon with the italic caption "definition card (invented concepts)".
> 2. A dashed red rounded frame titled in red italic "Generation", holding three boxes joined by arrows:
>    - "(i) Planner": a storyboard icon; text "lesson plan: 4 sections".
>    - "(ii) Coder": a code-window icon; text "one Manim scene per section".
>    - "(iii) Checks": a gear and a checklist icon; text "code check · render · layout (SGA)".
> 3. An arrow labelled "render" to a dark video thumbnail with a play button. Heading "Base video".
>
> **Below the band, a second dashed red rounded frame** titled in red italic "Learner feedback (ours)". Four
> columns, left to right, joined by arrows:
>
> - **Column 1**, lavender panel "Practice quiz (DEV)". A robot looks at 3 small dark frames per section. To its
>   right, a list of five questions "q1"–"q5" with badges: q1 green check, q2 red cross, q3 red cross, q4 green
>   check, q5 red cross. Caption: "forced choice, read confidence".
> - **Column 2**, pale yellow panel "Find the weak section". A small grid, rows "q1"–"q5" and columns "s1" "s2"
>   "s3" "s4", with one dot per row showing which section should teach that question. Under the grid, a row of
>   four score chips "s1", "s2", "s3", "s4"; the "s2" chip is filled orange and larger, with a magnifying glass over
>   it. Caption: "Ochiai score, like a debugger".
> - **Column 3**, peach panel "Small edit". A code card with two lines struck through in red and two new lines in
>   green. Above it, a note card "missing idea: one general principle". A small shield icon with a red cross over a
>   copied answer, captioned "no copying the practice answer".
> - **Column 4**, mint panel "Gate". A dark video thumbnail where only the second segment of its timeline is
>   orange. Two check badges: "practice score not lower" and "layout not worse". Heading "Repaired video".
>
> **Bottom strip, separated by a thick red dashed horizontal line labelled "wall"**: a clipboard "TEST (written by
> others)" with a lock icon, and the italic caption "used only for the final score".
>
> **Labels to check:** Input: topic, What is a tovan sum?, definition card (invented concepts), Generation,
> (i) Planner, lesson plan: 4 sections, (ii) Coder, one Manim scene per section, (iii) Checks, code check · render ·
> layout (SGA), render, Base video, Learner feedback (ours), Practice quiz (DEV), q1–q5, forced choice, read
> confidence, Find the weak section, s1–s4, Ochiai score, like a debugger, Small edit, missing idea: one general
> principle, no copying the practice answer, Gate, practice score not lower, layout not worse, Repaired video, wall,
> TEST (written by others), used only for the final score.

## F3, why TeachQuiz cannot see teaching (three failures and their fixes): `fig_failures.png`

Aspect 3:1. Where it goes: Step 0 of the long report (the three breaks), and the paper's audit section.

> **Three equal panels in a row**, each split horizontally: the top half is light red (#FDECEC) and shows the
> problem; the bottom half is mint and shows the fix. A small down arrow joins the halves.
>
> **Panel 1, title "(i) Grading".**
> - Top: a prompt card showing `{"id": "q1", ...}` with "q1" highlighted. Next to it, a robot reply card "q1: B,
>   q2: C, ...". Next to that, a grader icon looking for "t1 … t5", with a red cross and the caption "answers lost".
> - Bottom: the same reply with a green check and the caption "matched in order".
>
> **Panel 2, title "(ii) Refusal".**
> - Top: the robot holds up a grey card reading "NULL" like a shield. A thought bubble behind its head shows a
>   right triangle with squares on its sides (it knows). Red cross, caption "refusing is not forgetting".
> - Bottom: the robot fills one circle of A B C D. Green check, caption "must choose".
>
> **Panel 3, title "(iii) Prior knowledge".**
> - Top: the robot sits on a stack of books and fills every circle correctly before a video thumbnail has started
>   (play button). Red cross, caption "already knows the answer".
> - Bottom: a sealed envelope with a card of strange symbols (a circle with a plus inside, dots on a grid). Green
>   check, caption "invented concepts + measure what it knew".
>
> **Labels to check:** (i) Grading, {"id": "q1", ...}, q1: B, q2: C, t1 … t5, answers lost, matched in order,
> (ii) Refusal, NULL, refusing is not forgetting, must choose, (iii) Prior knowledge, already knows the answer,
> invented concepts + measure what it knew.

## F4, how we measure (like Code2Video's Figure 3): `fig_measure.png`

Aspect 3:1. Where it goes: the metric section of the paper, and Step 1 of the long report.

> **Top-left:** a question card with a green border:
> - "Q: What is 1 ⊕ 4?"
> - options "A: 5", "B: 9", "C: 4", "D: 10", with B in green.
>
> **Right of it, four panels in a row**, each with the same robot (no mask) and a small A B C D bar chart above its
> head showing how confident it is in each letter:
>
> 1. Grey panel, heading "No video". The robot has an empty thought bubble. Its bar chart is flat, all four bars
>    similar. Italic label "S_blind".
> 2. Pale blue panel, heading "3 frames per section". Three small dark frames in front of the robot. Bar B is
>    tall. Label "S_frames".
> 3. Pale yellow panel, heading "First + last frame". Two frames. Bar B is medium. Label "S_static".
> 4. Lavender panel, heading "Dense silent video". A film strip of many small frames with a muted speaker icon.
>    Bar B is tall. Label "S_visual".
>
> **A thin bracket under all four panels** leads to a formula card on the right:
> - "Gain = (S − B) / (1 − B)";
> - below it, smaller: "B = max(0.25, S_blind)";
> - below that, small italic: "two option orders; undefined if 1 − B < 0.05".
>
> **Labels to check:** Q: What is 1 ⊕ 4?, A: 5, B: 9, C: 4, D: 10, No video, S_blind, 3 frames per section,
> S_frames, First + last frame, S_static, Dense silent video, S_visual, Gain = (S − B) / (1 − B), B = max(0.25,
> S_blind), two option orders; undefined if 1 − B < 0.05.

## F5, the NOVEL-12 benchmark (like Code2Video's Figure 2): `fig_novel.png`

Aspect 2:1. Where it goes: the NOVEL-12 section of the paper, and Step 2 of the long report.

> **Left half, peach panel, title "A definition card".** A card with a thin border showing:
> - bold "Tovan sum";
> - "a ⊕ b = a + b + a × b";
> - three bullet lines: "order does not matter", "0 is neutral", "−1 swallows everything";
> - an italic example line "2 ⊕ 3 = 2 + 3 + 6 = 11".
>
> Around the card, a ring of 12 small round badges, each with a different simple abstract symbol (circle-plus, a
> staircase of dots, a 2×2 grid, a clock face, a triangle, a folded list, a lattice rectangle, a word in a circle,
> a quill, a dappled dot, a grid path, a spiral). Caption under it: "12 invented concepts · 96 TEST questions".
>
> **Right half, mint panel, title "Room to learn".** Three horizontal bars stacked vertically, each with an icon at
> its left:
> - a robot with an empty thought bubble, bar "untaught", filled to about 41% and labelled "41%";
> - a robot reading a dark video thumbnail, bar "after the video", striped with a question mark and no number;
> - a robot reading the card, bar "given the card", filled to about 85% and labelled "85%".
>
> A dotted vertical line at 25% is labelled "chance". Under the bars, a small note: "keys computed by code; letters
> balanced".
>
> **Labels to check:** A definition card, Tovan sum, a ⊕ b = a + b + a × b, order does not matter, 0 is neutral, −1
> swallows everything, 2 ⊕ 3 = 2 + 3 + 6 = 11, 12 invented concepts · 96 TEST questions, Room to learn, untaught,
> 41%, after the video, given the card, 85%, chance, keys computed by code; letters balanced.
>
> **The two numbers must match the report:** 41% is `\novelpriorGemmaAcc` (41.1) and 85% is `\novelcardGemmaAcc`
> (84.9). If those change, edit the image.

## F6, finding the weak section like a debugger: `fig_localise.png`

Aspect 16:9. Where it goes: Step 3 of the long report, next to the worked example table.

> **Top:** a horizontal film strip of four dark Manim frames labelled "s1", "s2", "s3", "s4". Above each frame is a
> tiny italic topic word: "definition", "worked example", "rules", "summary".
>
> **Middle:** a clean grid table. Rows "q1"–"q5" (practice questions). Columns "s1"–"s4". One filled dot per row:
> - q1 under s1;
> - q2 and q3 and q4 under s2;
> - q5 under s3.
>
> A right-hand column "student" shows: q1 green check, q2 red cross, q3 red cross, q4 green check, q5 red cross.
>
> **Bottom:** a row of four score bars, one under each frame:
> - s1 empty, "0";
> - s2 tall and orange, "0.67";
> - s3 medium, "0.58";
> - s4 empty, "0".
>
> A large magnifying glass sits over s2's frame, which glows orange. A small wrench icon points from s2 to a code
> card captioned "edit s2 first, then s3 if the budget allows".
>
> A side note card on the right reads "suspicious = fails here, passes elsewhere".
>
> **Labels to check:** s1, s2, s3, s4, definition, worked example, rules, summary, q1–q5, student, 0, 0.67, 0.58,
> edit s2 first, then s3 if the budget allows, suspicious = fails here, passes elsewhere.
>
> These are the illustrative numbers from the report's Table on spectrum-based localisation, not results.

---

# Part B: illustrations (optional, long report only)

Style for every image, so they look like one set:
- flat vector illustration with soft shading
- white background
- a restrained palette of blue `#2a78d6`, orange `#eb6834` and warm greys
- the same friendly, round, simple robot character in every image
- **no text, letters or numbers inside the image**: image models garble them, and the report's captions carry the words
- landscape, 16:9

## P1, the cover: `cover.png`

> Flat vector illustration, white background, palette of blue #2a78d6, orange #eb6834 and warm greys. A friendly,
> round, simple robot sits at a desk and watches a large screen. On the screen, an abstract mathematical animation:
> a square stretching into a parallelogram, arrows, a curve. The robot holds a pencil above a multiple-choice answer
> sheet with four empty circles per row. Calm, clean, educational mood. No text, no letters, no numbers anywhere.
> 16:9.

## P2, how TeachQuiz is meant to work: `forget.png`

> Flat vector illustration, white background, same palette and the same round robot character. The robot wears a
> soft blindfold made of a folded book page: it has been told to forget a topic. In front of it, a screen shows a
> simple geometric animation. A thought bubble above the robot is empty, with a small question mark shape (drawn as
> a shape, not a letter). Gentle, slightly humorous. No text, letters or numbers. 16:9.

## P3, the refusing student: `refuse.png`

> Flat vector illustration, white background, same palette and the same round robot character. The robot holds up
> a blank grey card in front of it like a shield, refusing to answer, while a thought bubble behind its head clearly
> shows a bright, complete diagram (a right triangle with squares on its sides), showing it secretly knows the
> answer. A teacher's hand points at an answer sheet. Humorous, clear contrast between "refusing" and "knowing". No
> text, letters or numbers. 16:9.

## P4, the student who already knows: `knows.png`

> Flat vector illustration, white background, same palette and the same round robot character. The robot sits on a
> huge stack of closed books and glowing tablets, the whole internet it has read, and confidently fills in every
> circle of a multiple-choice sheet before a video on a nearby screen has even started (the screen shows a
> play-button shape). Light-hearted. No text, letters or numbers. 16:9.

## P5, invented concepts: `invented.png`

> Flat vector illustration, white background, same palette and the same round robot character. On a table lies a
> sealed envelope with a wax seal, and beside it a card with unfamiliar abstract symbols (circles with crosses,
> arrows on a small grid, a staircase of dots), clearly new mathematics nobody has seen. The robot looks at the card
> with curiosity; its thought bubble is empty. A screen behind shows the same symbols being animated. No text,
> letters or numbers. 16:9.

## P6, a debugger for lessons: `debugger.png`

> Flat vector illustration, white background, same palette and the same round robot character. A horizontal film
> strip of four panels, each a small mathematical animation frame. A large magnifying glass hovers over the second
> panel, which glows orange as the suspicious one; the others are calm blue. Below the strip, a row of small check
> marks and cross marks (drawn as shapes), with the crosses clustered under the second panel. A tiny wrench rests
> beside the strip. No text, letters or numbers. 16:9.
