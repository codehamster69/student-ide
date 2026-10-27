"""How well the similarity check (studentide/similarity.py) separates a
disguised copy from solutions written independently.

Corpus: backend/tests/fixtures/similarity/<problem>/, six contest-style
problems, each solved independently three times in C/C++ and three times in
Python, in deliberately different styles (written for this evaluation).

For every solution a "copy" is made the way a student hiding a copy might:

    L1  renamed + reformatted: every program-defined name renamed, comments
        stripped and a new one added, indentation and brace placement changed
    L2  L1 + rewritten constructs: i++ -> i += 1, a += b -> a = a + b
    L3  L2 + dead code: a harmless statement inserted after every third statement

Each problem/language family is run as one small class (the three
independent solutions plus one copy of each), exactly as the competition
page runs it, and every pair is scored. Copy pairs should score high,
independent pairs low.

    python backend/scripts/eval_similarity.py

writes thesis/latex/ablations/similarity/{results.csv,table.tex} and, with
matplotlib, thesis/latex/graphs/similarity-separation.pdf.
"""

from __future__ import annotations

import csv
import itertools
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from studentide import similarity  # noqa: E402

CORPUS = ROOT / "backend" / "tests" / "fixtures" / "similarity"
OUT = ROOT / "thesis" / "latex" / "ablations" / "similarity"
GRAPH = ROOT / "thesis" / "latex" / "graphs" / "similarity-separation.pdf"
LANG = {".c": "c", ".cpp": "cpp", ".py": "python"}
THRESHOLDS = (0.4, 0.5, 0.6, 0.7)

# names the program does not define (library calls, members): never renamed
LIBRARY = set("""main printf scanf puts putchar getchar fgets fwrite stdin stdout stderr malloc free strtok strlen isspace
bsearch sizeof EOF NULL std cin cout endl string vector map stack istringstream getline reverse lower_bound to_string
max min ios sync_with_stdio push_back pop top empty count begin end size print input int map split list range len sum
str join sys read readline write deque appendleft enumerate math isqrt bisect bisect_left iter next float setdefault get
replace strip rstrip index append bytearray bool long char void size_t auto deque collections bits stdc iostream sstream
algorithm stdbool stdlib stdio ctype h const_cast""".split())


def rename(code: str, lang: str) -> str:
    """Rename every program-defined identifier consistently (v1, v2, ...)."""
    names: dict[str, str] = {}
    out, last = [], 0
    for t in similarity.tokenize(code, lang):
        word = code[t.start:t.end]
        if t.text != "V" or word in LIBRARY or code[:t.start].rstrip().endswith((".", "->", "#include <", "import", "from")):
            continue
        new = names.setdefault(word, f"{'n' if lang == 'python' else 'v'}{len(names) + 1}x")
        out += [code[last:t.start], new]
        last = t.end
    return "".join(out) + code[last:]


def strip_comments(code: str, lang: str) -> str:
    if lang == "python":
        return re.sub(r'(?m)^\s*""".*?"""\s*\n|#[^\n]*', "", code, flags=re.S)
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", code, flags=re.S)


def reformat(code: str, lang: str) -> str:
    lines = [l.rstrip() for l in code.split("\n") if l.strip()]
    if lang == "python":
        lines = [re.sub(r"^((?:    )+)", lambda m: "  " * (len(m.group(1)) // 4), l) for l in lines]
        return "# my answer\n" + "\n".join(lines) + "\n"
    out = []
    for l in lines:
        ind = re.match(r"\s*", l).group()
        body = l.strip()
        if body.endswith("{") and body != "{":  # Allman braces, 2-space indent
            out += [ind[: len(ind) // 2] + body[:-1].rstrip(), ind[: len(ind) // 2] + "{"]
        else:
            out.append(ind[: len(ind) // 2] + body)
    return "/* solution */\n" + "\n".join(out) + "\n"


def rewrite(code: str, lang: str) -> str:
    code = re.sub(r"\b(\w+)\+\+(?=\s*[;)])", r"\1 += 1", code)
    code = re.sub(r"\+\+(\w+)\b", r"\1 += 1", code)
    end = "" if lang == "python" else ";"
    return re.sub(rf"(?m)^(\s*)(\w+) \+= ([^;\n]+){re.escape(end)}$", rf"\1\2 = \2 + \3{end}", code)


def dead_code(code: str, lang: str) -> str:
    out, n = [], 0
    for l in code.split("\n"):
        out.append(l)
        body = l.strip()
        simple = (body and not body.endswith(":") and not body.startswith(("#", "def ", "return", "elif", "else", "@", "import", "from"))
                  if lang == "python" else body.endswith(";") and l.startswith((" ", "\t")) and not body.startswith("return"))
        if simple:
            n += 1
            if n % 3 == 0:
                ind = re.match(r"\s*", l).group()
                out.append(f"{ind}unused{n} = {n}" if lang == "python" else f"{ind}int unused{n} = {n};")
    return "\n".join(out)


LEVELS = {
    "L1": lambda c, l: reformat(rename(strip_comments(c, l), l), l),
    "L2": lambda c, l: rewrite(reformat(rename(strip_comments(c, l), l), l), l),
    "L3": lambda c, l: dead_code(rewrite(reformat(rename(strip_comments(c, l), l), l), l), l),
}


def run() -> list[dict]:
    rows = []
    for problem in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
        files = sorted(problem.iterdir())
        for family in ("c", "python"):
            originals = [(f.stem + f.suffix, LANG[f.suffix], f.read_text()) for f in files
                         if similarity.FAMILY[LANG[f.suffix]] == family]
            for level, disguise in LEVELS.items():
                entries = [similarity.Entry(name, f"s-{name}", lang, code) for name, lang, code in originals]
                entries += [similarity.Entry(f"copy-{name}", f"c-{name}", lang, disguise(code, lang)) for name, lang, code in originals]
                scored = {frozenset((p["a"], p["b"])): p for p in similarity.similar_pairs(entries, {}, report_at=0.0)}
                for x, y in itertools.combinations([e.key for e in entries], 2):
                    is_copy = y == f"copy-{x}" or x == f"copy-{y}"
                    if not is_copy and (x.startswith("copy-") or y.startswith("copy-")):
                        continue  # a copy against another student's original is just another independent pair
                    if is_copy or (not x.startswith("copy-") and level == "L1"):  # independent pairs once
                        p = scored.get(frozenset((x, y)), {})
                        rows.append({"problem": problem.name, "family": family, "level": level if is_copy else "independent",
                                     "a": x, "b": y, "similarity": p.get("similarity", 0.0),
                                     "longest_run": p.get("longest_run", 0)})
    return rows


def summarise(rows: list[dict]) -> list[dict]:
    out = []
    for kind in ("independent", *LEVELS):
        s = [r["similarity"] for r in rows if r["level"] == kind]
        d = {"pairs": kind, "n": len(s), "median": statistics.median(s), "min": min(s), "max": max(s)}
        for t in THRESHOLDS:
            d[f"at_{t}"] = sum(v >= t for v in s) / len(s)
        out.append(d)
    return out


LABELS = {"independent": "Independent solutions", "L1": "Copy: renamed + reformatted",
          "L2": "Copy: + rewritten constructs", "L3": "Copy: + dead code every 3rd line"}


def write(rows: list[dict], summary: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    body = "\n".join(
        f"    {LABELS[s['pairs']]} & {s['n']} & {s['median']:.2f} & {s['min']:.2f}--{s['max']:.2f} & "
        + " & ".join(f"{100 * s[f'at_{t}']:.0f}\\%" for t in THRESHOLDS) + r" \\"
        for s in summary)
    heads = " & ".join(f"$\\ge {t}$" for t in THRESHOLDS)
    (OUT / "table.tex").write_text(rf"""% Generated by backend/scripts/eval_similarity.py. Do not edit by hand.
\begin{{table}}[ht]
  \centering\small
  \caption{{Similarity check on six contest problems, each solved independently three times in C/C++ and
    three times in Python. Each solution was also copied with increasing disguise. Columns on the right:
    share of pairs at or above each similarity (the page lists pairs from 0.3 and highlights from 0.5).}}
  \label{{tab:similarity-separation}}
  \begin{{tabular}}{{@{{}}lrcc{"c" * len(THRESHOLDS)}@{{}}}}
    \toprule
    Pairs & $n$ & Median & Range & {heads} \\
    \midrule
{body}
    \bottomrule
  \end{{tabular}}
\end{{table}}
""")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: no graph")
        return
    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    kinds = ["independent", *LEVELS]
    for i, k in enumerate(kinds):
        ys = [r["similarity"] for r in rows if r["level"] == k]
        xs = [i + (j % 7 - 3) * 0.04 for j in range(len(ys))]
        ax.scatter(ys, [i] * len(ys), s=14, alpha=0.55, color="#1f6feb" if k != "independent" else "#8b949e")
    ax.axvline(0.5, color="#d29922", lw=1, ls="--")
    ax.set_yticks(range(len(kinds)), [LABELS[k] for k in kinds], fontsize=8)
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel("similarity (share of both programs in common runs)", fontsize=8)
    ax.tick_params(axis="x", labelsize=8)
    ax.invert_yaxis()
    fig.tight_layout()
    GRAPH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(GRAPH)


if __name__ == "__main__":
    rows = run()
    summary = summarise(rows)
    for s in summary:
        print(f"{LABELS[s['pairs']]:36s} n={s['n']:3d} median={s['median']:.2f} range={s['min']:.2f}-{s['max']:.2f} "
              + " ".join(f">={t}: {100 * s[f'at_{t}']:.0f}%" for t in THRESHOLDS))
    if "--no-write" not in sys.argv:
        write(rows, summary)
