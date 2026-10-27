"""Build the bundled Codeforces question set (studentide/providers/data/codeforces.jsonl.gz).

Source: open-r1/codeforces (Penedo et al., Hugging Face 2025), CC BY 4.0 on
the dataset card (ODC-By in its licence section): 10,000+ Codeforces problems
up to 2025 with statements, tags, ratings, the official tests that Codeforces
shows in full, extra tests generated and validated against human solutions,
and, for the ~30% of problems that accept several right answers, a Python
checker validated against accepted human solutions.

    pip install pyarrow
    huggingface-cli download open-r1/codeforces --repo-type=dataset --include='data/*.parquet' --local-dir cf
    python scripts/build_codeforces.py cf/data studentide/providers/data/codeforces.jsonl.gz [generated.jsonl]

generated.jsonl (optional) tops up problems that have fewer than three small
tests: one line per contest, {"contest": id, "tests": {problem_id: [[in, out], ...]}},
already cut down from the dataset's generated_tests/*.parquet (110 GB in all,
so only the contests needed are fetched and only small tests kept).

Kept: every problem our runner can run, i.e. marked executable by the
dataset, not interactive, reading standard input. Tests: the statement's
examples (visible), then small official and generated tests (hidden), at
most MAX_HIDDEN. Problems with a checker keep it; their tests are judged by
it instead of by comparing text.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_codecontests import clean  # noqa: E402  (same $$$ LaTeX clean-up)

MAX_HIDDEN = 10
MAX_TEST_BYTES = 4000  # input + output of one test
MAX_STATEMENT = 14_000
COLUMNS = ["id", "contest_id", "index", "title", "description", "input_format", "output_format", "note", "examples",
           "rating", "tags", "official_tests", "input_mode", "generated_checker", "executable", "interaction_format",
           "contest_start_year"]


def small(i: str, o: str) -> bool:
    return len(i) + len(o) <= MAX_TEST_BYTES


def statement(p: dict) -> str:
    parts = [p["description"] or ""]
    for head, key in (("Input", "input_format"), ("Output", "output_format"), ("Note", "note")):
        if (p.get(key) or "").strip():
            parts.append(f"{head}\n{p[key].strip()}")
    return clean("\n\n".join(parts))[:MAX_STATEMENT]


def entry(p: dict, generated: list[list[str]]) -> dict:
    examples = [(t["input"], t["output"]) for t in p["examples"] or [] if small(t["input"], t["output"])]
    seen = {i for i, _ in examples}
    tests = [{"stdin": i, "expected": o, "hidden": False} for i, o in examples]
    for i, o in [(t["input"], t["output"]) for t in p["official_tests"] or []] + [tuple(x) for x in generated]:
        if small(i, o) and i not in seen and sum(t["hidden"] for t in tests) < MAX_HIDDEN:
            seen.add(i)
            tests.append({"stdin": i, "expected": o, "hidden": True})
    contest, index = p["contest_id"], p["index"]
    return {"ref": f"cf-{contest}{index}", "title": p["title"], "source": "codeforces", "level": p["rating"] or 0,
            "tags": sorted(p["tags"] or []), "year": p["contest_start_year"],
            "url": f"https://codeforces.com/problemset/problem/{contest}/{index}", "prompt": statement(p),
            "sample_input": examples[0][0] if examples else "", "tests": tests, "checker": p["generated_checker"] or ""}


def main(src_dir: str, out: str, generated_path: str | None = None) -> None:
    generated: dict[str, list] = {}
    if generated_path:
        for line in open(generated_path, encoding="utf-8"):
            generated.update(json.loads(line)["tests"])
    rows, seen, skipped = [], set(), {"not executable": 0, "interactive": 0, "file input": 0, "no statement": 0}
    for f in sorted(Path(src_dir).glob("*.parquet")):
        for p in pq.read_table(f, columns=COLUMNS).to_pylist():
            why = ("not executable" if not p["executable"] else "interactive" if p["interaction_format"] or "interactive" in (p["tags"] or [])
                   else "file input" if p["input_mode"] != "stdio" else "no statement" if not p["description"] else None)
            if why:
                skipped[why] += 1
                continue
            e = entry(p, generated.get(p["id"], []))
            if e["ref"] not in seen:
                seen.add(e["ref"])
                rows.append(e)
    rows.sort(key=lambda e: (e["level"], e["ref"]))
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as g:
        for e in rows:
            g.write(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n")
    n_tests = [len(e["tests"]) for e in rows]
    print(f"wrote {len(rows)} problems to {out}; skipped {skipped}; tests: "
          f"{sum(n >= 3 for n in n_tests)} with 3+, {sum(n == 0 for n in n_tests)} with none, "
          f"{sum(bool(e['checker']) for e in rows)} judged by a checker", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    main(*sys.argv[1:])
