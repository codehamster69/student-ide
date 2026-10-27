"""Build the bundled LeetCode question set (studentide/providers/data/leetcode.jsonl.gz).

Source: LeetCodeDataset (Xia et al. 2025, arXiv:2504.14655), Apache 2.0,
https://huggingface.co/datasets/newfacade/LeetCodeDataset. Download the two
JSONL files and point this script at them:

    curl -LO https://huggingface.co/datasets/newfacade/LeetCodeDataset/resolve/main/LeetCodeDataset-train.jsonl
    curl -LO https://huggingface.co/datasets/newfacade/LeetCodeDataset/resolve/main/LeetCodeDataset-test.jsonl
    python scripts/build_leetcode.py LeetCodeDataset-train.jsonl LeetCodeDataset-test.jsonl \\
        studentide/providers/data/leetcode.jsonl.gz [--verify]

Kept per problem: slug, LeetCode number, title (from the slug), difficulty,
tags, starter code, method name, whether answers may come in any order, the
row's position in the dataset (so the browser can load the problem text
live), and up to MAX_TESTS tests. **Not kept: the problem description**,
which is LeetCode's text (see providers/leetcode.py). The "any order" flag
is read from the description at build time; the text itself is dropped.

Tests are the dataset's asserts, `assert candidate(k=v, ...) == expected`
(or is_same_list / is_same_tree), turned into stdin = the keyword arguments
and expected = the JSON the harness prints for the expected value. Only
literals, list_node(...) and tree_node(...) are allowed in either side.
The two smallest become visible examples, the rest are spread over the
remaining asserts (largest included) and hidden.

--verify runs each problem's reference solution (the dataset's `completion`,
which is not bundled) through the real harness on every kept test, drops
tests it fails and problems left with fewer than MIN_TESTS. It runs each
test in a fresh `python3 -I` process, a few minutes in all.
"""

from __future__ import annotations

import ast
import gzip
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studentide.grading import outputs_match  # noqa: E402
from studentide.providers.leetcode import HARNESS, LIST_NODE, PRELUDE, TREE_NODE, harness  # noqa: E402

MAX_TESTS = 10
MIN_TESTS = 3
MAX_TEST_CHARS = 3000  # stdin + expected of one test
ANY_ORDER = re.compile(r"\bin any order\b", re.I)
SMALL_WORDS = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}

_ns: dict = {}
exec(HARNESS.format(fn="_", any_order=False).rsplit("\n_args", 1)[0], _ns)  # the harness's own builders


def title(slug: str) -> str:
    return " ".join(w.upper() if w in SMALL_WORDS else w.capitalize() for w in slug.split("-"))


def _safe(node: ast.AST) -> bool:
    """Only literals and list_node(...) / tree_node(...) of literals."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            if not (isinstance(n.func, ast.Name) and n.func.id in ("list_node", "tree_node") and len(n.args) == 1 and not n.keywords):
                return False
        elif isinstance(n, ast.Name):
            if n.id not in ("list_node", "tree_node", "inf"):
                return False
        elif not isinstance(n, (ast.Constant, ast.List, ast.Tuple, ast.UnaryOp, ast.USub, ast.UAdd, ast.Load, ast.keyword)):
            return False
    return True


def _value(node: ast.AST):
    env = {"__builtins__": {}, "list_node": _ns["_list_node"], "tree_node": _ns["_tree_node"], "inf": float("inf")}
    return eval(compile(ast.Expression(node), "<expected>", "eval"), env)


def convert(row: dict, any_order: bool) -> tuple[list[dict], int]:
    """(tests, asserts skipped)."""
    fn_def = ast.parse(row["test"]).body[0]
    tests, skipped, seen = [], 0, set()
    for st in fn_def.body:
        t = st.test if isinstance(st, ast.Assert) else None
        if isinstance(t, ast.Compare) and len(t.ops) == 1 and isinstance(t.ops[0], ast.Eq):
            call, exp = t.left, t.comparators[0]
        elif isinstance(t, ast.Call) and getattr(t.func, "id", "") in ("is_same_list", "is_same_tree") and len(t.args) == 2:
            call, exp = t.args
        else:
            skipped += 1
            continue
        if not (isinstance(call, ast.Call) and getattr(call.func, "id", "") == "candidate" and not call.args
                and all(k.arg for k in call.keywords) and all(_safe(k.value) for k in call.keywords) and _safe(exp)):
            skipped += 1
            continue
        stdin = ", ".join(f"{k.arg}={ast.unparse(k.value)}" for k in call.keywords)
        try:
            expected = json.dumps(_ns["_show"](_value(exp), any_order))
        except Exception:
            skipped += 1
            continue
        if len(stdin) + len(expected) > MAX_TEST_CHARS or stdin in seen:
            skipped += 1
            continue
        seen.add(stdin)
        tests.append({"stdin": stdin, "expected": expected})
    return tests, skipped


def pick(tests: list[dict]) -> list[dict]:
    """Two smallest first (shown as examples), then spread over the rest, the largest included."""
    by_size = sorted(tests, key=lambda t: len(t["stdin"]) + len(t["expected"]))
    head, rest = by_size[:2], by_size[2:]
    n = MAX_TESTS - len(head)
    if len(rest) > n:
        rest = [rest[round(i * (len(rest) - 1) / (n - 1))] for i in range(n)]
    return head + rest


def _run(program: Path, test: dict) -> bool:
    try:
        p = subprocess.run([sys.executable, "-I", str(program)], input=test["stdin"], capture_output=True, text=True,
                           timeout=10, cwd=program.parent)
    except subprocess.TimeoutExpired:
        return False
    return p.returncode == 0 and outputs_match(p.stdout, test["expected"], "json")


def verify(rows: list[dict], solutions: dict[str, str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        jobs = []
        for r in rows:
            nodes = "".join(src for n, src in (("ListNode", LIST_NODE), ("TreeNode", TREE_NODE)) if n in r["starter_code"])
            prog = Path(tmp) / f"{r['ref']}.py"
            prog.write_text(PRELUDE.format(nodes="") + nodes + "\n" + solutions[r["ref"]] + "\n\n"
                            + harness(r["fn"], r["any_order"]), encoding="utf-8")
            jobs += [(r, prog, t) for t in r["tests"]]
        with ThreadPoolExecutor(max_workers=16) as pool:
            ok = list(pool.map(lambda j: _run(j[1], j[2]), jobs))
    failed: dict[str, set[int]] = {}
    for (r, _, t), good in zip(jobs, ok):
        if not good:
            failed.setdefault(r["ref"], set()).add(id(t))
    for r in rows:
        r["tests"] = [t for t in r["tests"] if id(t) not in failed.get(r["ref"], set())]
    print(f"verify: {sum(ok)} of {len(ok)} tests pass the reference solution; "
          f"{sum(1 for r in rows if r['ref'] in failed)} problems lost at least one", file=sys.stderr)


def main(train: str, test: str, out: str, check: bool) -> None:
    rows, solutions, dropped = [], {}, {"in place (returns None)": 0, "too few usable tests": 0, "not Solution().method": 0}
    for split, path in (("train", train), ("test", test)):
        with open(path, encoding="utf-8") as f:
            for offset, line in enumerate(f):
                d = json.loads(line)
                if not d["entry_point"].startswith("Solution()."):
                    dropped["not Solution().method"] += 1
                    continue
                any_order = bool(ANY_ORDER.search(d["problem_description"]))
                tests, _ = convert(d, any_order)
                if tests and all(t["expected"] == "null" for t in tests):
                    dropped["in place (returns None)"] += 1
                    continue
                rows.append({"ref": d["task_id"], "id": d["question_id"], "title": title(d["task_id"]),
                             "difficulty": d["difficulty"].lower(), "tags": d["tags"], "starter_code": d["starter_code"],
                             "fn": d["entry_point"].split(".", 1)[1], "any_order": any_order,
                             "split": split, "offset": offset, "tests": pick(tests)})
                solutions[d["task_id"]] = d["completion"]
    if check:
        verify(rows, solutions)
    kept = []
    for r in rows:
        if len(r["tests"]) < MIN_TESTS:
            dropped["too few usable tests"] += 1
        else:
            kept.append(r)
    kept.sort(key=lambda r: r["id"])
    with gzip.open(out, "wt", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    n_tests = sum(len(r["tests"]) for r in kept)
    print(f"kept {len(kept)} problems with {n_tests} tests; dropped {dropped}", file=sys.stderr)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--verify"]
    if len(args) != 3:
        sys.exit(__doc__)
    main(*args, check="--verify" in sys.argv)
