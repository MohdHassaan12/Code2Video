# Compiling the paper and the reports

This folder compiles on its own. Every table and number is already generated in `tables/`. The data figures are
already drawn in `figures/`. You only add the illustrations and run LaTeX.

| File | What it is |
|---|---|
| `main.tex` | the paper (two columns) |
| `report.tex` | the technical report |
| `long_report.tex` | the long report, written for newcomers |
| `pdf/` | the three PDFs as built when this zip was made |
| `results/` | the result files behind the numbers (side study, ladders, noise model, frozen pilot numbers), as they were when this zip was made |

## 1. Add the images

Generate each image from its prompt in `figures/IMAGE_PROMPTS.md`, then save it in `figures/` under exactly this
name. Until a file is present, its place shows a box naming the prompt, so the documents always compile.

**Method figures.** These appear in all three documents, in the style of Code2Video's figures.

| Prompt | File | Where it appears |
|---|---|---|
| F1 | `figures/fig_overview.png` | introduction, start of the long report |
| F2 | `figures/fig_pipeline.png` | pipeline section, Step 3 |
| F3 | `figures/fig_failures.png` | TeachQuiz audit, Step 0 |
| F4 | `figures/fig_measure.png` | measure section, Step 1 |
| F5 | `figures/fig_novel.png` | NOVEL-12 section, Step 2 |
| F6 | `figures/fig_localise.png` | Step 3 of the long report |

**Illustrations.** These appear in the long report only, and are optional.

| Prompt | File |
|---|---|
| P1 | `figures/cover.png` |
| P2 | `figures/forget.png` |
| P3 | `figures/refuse.png` |
| P4 | `figures/knows.png` |
| P5 | `figures/invented.png` |
| P6 | `figures/debugger.png` |

PNG or JPG both work; keep the file names. Method figures are placed at full text width, so a landscape image works
best: 2:1 or 3:1, as each prompt says.

## 2. Compile

**Locally**, with TeX Live and its packages `tcolorbox`, `pgfplots`, `tikz`, `natbib` and `placeins`:

    for d in main report long_report; do
      pdflatex $d && bibtex $d && pdflatex $d && pdflatex $d
    done

**On Overleaf:**
1. Choose New Project, then Upload Project, and pick this zip.
2. In the menu, set the Compiler to pdfLaTeX and the Main document to `main.tex`.
3. Recompile. Switch the main document to `report.tex` or `long_report.tex` to build those.

## 3. Before submitting

- In `refs.bib`, check the entries marked `CHECK`: SGA, PIVOT, ManimCode, EduPanel, and the CounterVQA authors.
- Confirm the author line in each `.tex` file.
- Do not edit `tables/numbers.tex` or other files in `tables/` by hand. They are generated from the result files by
  `paper/make_tables.py` in the repository, so a new run updates them consistently.
- A `[pending]` mark means that result had not finished when the zip was made.
