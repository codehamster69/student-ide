"""Check the generated C, C++, Java and JavaScript test drivers (providers/polyglot.py).

    python scripts/check_polyglot.py [--compile-all] [--mbpp mbpp.jsonl]

1. Round trip: for every argument/return type the LeetCode set uses, a
   solution that returns its argument unchanged is run on up to 40 real
   values of that type from the bundled tests, in order and "any order", in
   every language (Python through the JSON-lines harness too). Its output must equal what the Python harness prints for
   the same value, so reading arguments and printing answers agree with the
   expected outputs everywhere.
2. Compile: one problem per distinct signature shape (all problems in C,
   where a function name can clash with the C library, with --compile-all)
   is compiled with a do-nothing body, so every generated starter and
   harness compiles together. --mbpp adds MBPP's typed problems (download
   mbpp.jsonl from the URL in providers/mbpp.py), compiled the same way.

Needs gcc, g++, javac and node. Runs our own code only (no dataset solutions).
"""

from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studentide import runner  # noqa: E402
from studentide.grading import outputs_match  # noqa: E402
from studentide.providers import leetcode, mbpp, polyglot  # noqa: E402
from studentide.providers.polyglot import Signature, base, depth  # noqa: E402

PER_TYPE = 40


def py_show(v, t: str, o: bool):
    """What the Python harness prints for value v of type t."""
    if t in polyglot.NODES:
        if not v:
            return None
        if t == "TreeNode":
            while v and v[-1] is None:
                v = v[:-1]
        return v
    if isinstance(v, (list, tuple)):
        out = [py_show(x, t[:-2], o) for x in v]
        return sorted(out, key=json.dumps) if o else out
    return v


def body(sig: Signature, language: str, echo: bool) -> str:
    """Code for the function body: return the (only) argument, or a do-nothing default."""
    x, r = (sig.params[0][0] if sig.params else ""), sig.ret
    if language == "c":
        if echo:
            sizes = (f"*returnSize = {x}Size; " if depth(r) >= 1 else "") + (f"*returnColumnSizes = {x}ColSize; " if depth(r) == 2 else "")
            return f"{sizes}return {x};"
        return ("*returnSize = 0; " if depth(r) >= 1 else "") + ("return NULL;" if depth(r) or r in polyglot.NODES or r == "string" else "return 0;")
    if language == "cpp":
        return f"return {x};" if echo else "return {};"
    if language == "java":
        if echo:
            return f"return {x};"
        return "return null;" if depth(r) or r in polyglot.NODES or r == "string" else \
            {"bool": "return false;", "char": "return 'a';"}.get(r, "return 0;")
    return f"return {x};" if echo else "return null;"


def program(sig: Signature, language: str, echo: bool) -> str:
    if language == "python":
        return (leetcode.PRELUDE.format(nodes="") + leetcode.LIST_NODE + leetcode.TREE_NODE
                + f"\nclass Solution:\n    def {sig.fn}(self, x):\n        return x\n\n" + leetcode.json_harness(sig))
    code = polyglot.starter(sig, language)
    if echo and language == "java":  # arrays come back as they went in, whatever LeetCode's return type
        code = re.sub(r"public .+? " + sig.fn + r"\(", f"public Object {sig.fn}(", code)
    code = re.sub(r"\{\n( *)\n( *)\}", lambda m: "{\n" + m.group(1) + body(sig, language, echo) + "\n" + m.group(2) + "}", code, count=1)
    return code.rstrip("\n") + "\n\n" + polyglot.harness(sig, language)


def values_by_type() -> dict[str, list]:
    out: dict[str, list] = {}
    for sig, tests in leetcode._converted().values():
        for t in tests:
            args, exp = t["values"]
            for (_, ty), v in [*zip(sig.params, args), ((None, sig.ret), exp)]:
                bucket = out.setdefault(ty, [])
                if len(bucket) < PER_TYPE and v not in bucket and len(json.dumps(v)) < 2000:
                    bucket.append(v)
    return out


def round_trip() -> int:
    failures = 0
    jobs = []
    for ty, vals in sorted(values_by_type().items()):
        for o in (False, True):
            if o and base(ty) == "double":  # never generated: see polyglot.build
                continue
            sig = Signature("echo", (("x", ty),), ty, o)
            for lang in ("python", *polyglot.LANGUAGES):
                vs = [v for v in vals if polyglot.in_range(v, lang)]
                jobs.append((ty, o, lang, sig, vs))

    def run(job):
        ty, o, lang, sig, vs = job
        failed, outs, _ = runner.run_many(program(sig, lang, True), lang, [polyglot.stdin([v]) for v in vs])
        if failed:
            return job, [f"compile: {failed.stderr[:400]}"]
        bad = [f"{json.dumps(v)[:80]} -> {r.stdout.strip()[:80]!r} {r.stderr.strip()[:200]}"
               for v, r in zip(vs, outs) if not outputs_match(r.stdout, json.dumps(py_show(v, ty, o)), "json")]
        return job, bad

    with ThreadPoolExecutor(max_workers=4) as pool:
        for (ty, o, lang, _, vs), bad in pool.map(run, jobs):
            status = "ok" if not bad else f"{len(bad)} FAILED"
            print(f"round trip {lang:10} {ty:12} {'any order' if o else 'in order':9} {len(vs):3} values: {status}")
            for b in bad[:3]:
                print("   ", b)
            failures += bool(bad)
    return failures


def compile_all(everything: bool, sigs: list[Signature]) -> int:
    shapes: dict[tuple, Signature] = {}
    c_all = []
    for sig in sigs:
        shapes.setdefault((tuple(t for _, t in sig.params), sig.ret), sig)
        c_all.append(sig)
    jobs = [(lang, sig) for lang in polyglot.LANGUAGES for sig in (c_all if lang == "c" and everything else shapes.values())]

    def run(job):
        lang, sig = job
        with runner.Program(program(sig, lang, False), lang) as p:
            return job, p.failed
    failures = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for (lang, sig), failed in pool.map(run, jobs):
            if failed:
                failures += 1
                print(f"compile {lang} {sig}: {failed.stderr[:600]}")
    print(f"compiled {len(jobs)} programs ({len(shapes)} signature shapes): {failures} failed")
    return failures


def mbpp_signatures(path: str) -> list[Signature]:
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    sigs = [got[0] for r in rows if (got := mbpp.typed(r, "c"))]
    print(f"MBPP: {len(sigs)} of {len(rows)} problems have types in C, C++ and Java")
    return sigs


if __name__ == "__main__":
    sigs = [sig for sig, _ in leetcode._converted().values()]
    if "--mbpp" in sys.argv:
        sigs += mbpp_signatures(sys.argv[sys.argv.index("--mbpp") + 1])
    bad = round_trip() + compile_all("--compile-all" in sys.argv, sigs)
    sys.exit(1 if bad else 0)
