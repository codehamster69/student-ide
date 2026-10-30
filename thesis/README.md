# thesis/

Everything for Rohan's M.Tech thesis, *Who is at the keyboard? Process-Aware
Authorship Continuity in Programming Assessment* (IIIT Surat), lives here.
There are three parts:

| Folder | What it is |
| --- | --- |
| [`brain/`](brain/) | The project's memory: a dated log of events, decisions, results and the reasoning behind them. This is the raw material the report and thesis get written from. |
| [`plans/`](plans/) | Plans for work not built yet (e.g. the desktop client), written before a thread starts coding. |
| [`latex/`](latex/) | The LaTeX thesis project: chapters, front matter, bibliography, and every figure, screenshot, graph, flowchart and ablation result that goes in it. |

## Standing rule for every thread / PR

When a piece of work finishes something meaningful (a feature lands, a design
decision is made, an experiment produces numbers, a plan changes), the **same
PR** must:

1. **Add a brain entry** in `brain/entries/` (see format below).
2. **Add thesis material** to `latex/` if any exists: a screenshot, a graph,
   a flowchart, a results table, an ablation, or a paragraph of draft text in
   the relevant chapter. Rough is fine; it's easier to polish text that exists.
3. **Add citations** you relied on to `latex/bib/references.bib`.

Keep thesis changes inside `thesis/` so they never collide with code PRs.

## Writing a brain entry

One file per entry, so parallel PRs never conflict:

```
thesis/brain/entries/YYYY-MM-DD-NN-short-slug.md   (NN orders same-day entries)
```

Copy [`brain/TEMPLATE.md`](brain/TEMPLATE.md). Each entry has a type
(`event`, `decision`, `result`, `plan`, `issue`), what happened, **why**
(the rationale is the part you can't recover later), evidence (PR links,
commit hashes, file paths, numbers), and which thesis chapter it feeds.
Entries are append-only: if a decision is reversed, write a new entry that
supersedes the old one and link back to it, don't edit history.

`brain/README.md` explains how to read the log; files sort by date.

## Where thesis assets go

All paths are under `latex/`:

| Asset | Folder | Notes |
| --- | --- | --- |
| UI screenshots, dashboard captures | `snapshots/` | PNG. Name `YYYY-MM-DD-what.png`. |
| Plots (ROC, detection delay, CUSUM traces) | `graphs/` | Prefer PDF/SVG from code. Commit the script or notebook path that made it in the brain entry. |
| Flowcharts, architecture diagrams | `flowcharts/` | TikZ `.tex` preferred (see `pipeline.tex`); exported PDF otherwise. |
| Other figures (photos, hand drawings) | `figures/` | |
| Ablation studies | `ablations/` | Raw `.csv` plus a `.tex` table. One subfolder per study. |
| Standalone results tables | `tables/` | `.tex` files `\input` from chapters. |
| Bibliography | `bib/references.bib` | BibLaTeX. Mark unverified entries with `note = {TODO verify}`. |

## Building the PDF

```
cd thesis/latex
latexmk -pdf main.tex      # or: make
```

Needs a TeX Live install with `latexmk`, `biber` and the usual packages
(`texlive-latex-extra`, `texlive-pictures`, `texlive-bibtex-extra`), or open
the `latex/` folder in Overleaf and set `main.tex` as the main document.
