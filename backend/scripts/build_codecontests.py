"""Build the bundled CodeContests question set (studentide/providers/data/codecontests.jsonl.gz).

CodeContests (DeepMind, 2022) is a dataset of competitive-programming problems
from Codeforces, CodeChef, HackerEarth, AtCoder and Aizu with statements, tags,
difficulty and stdin/stdout tests, released under CC BY 4.0. It is published as
Riegeli files on Google Cloud Storage (gs://dm-code_contests), which no live
API serves problem by problem, so a filtered copy is bundled with the app.

    gsutil -m cp "gs://dm-code_contests/code_contests_*.riegeli*" /tmp/cc/
    pip install zstandard
    python scripts/build_codecontests.py /tmp/cc studentide/providers/data/codecontests.jsonl.gz

Kept: Codeforces problems rated 800 to MAX_RATING with tags (the topic
categories), not interactive, and CodeChef / HackerEarth / AtCoder / Aizu
problems marked easy or medium. Tests: every public test, then up to
MAX_HIDDEN private or generated tests, each small. Problems whose statement
accepts several correct answers keep no tests, since exact comparison would
mark right answers wrong.

The reader below understands only what these files use (simple chunks,
zstd), and the protobuf decoding is done by hand for the fields needed, so
the only dependency is `zstandard`.
"""

from __future__ import annotations

import gzip
import json
import re
import struct
import sys
from pathlib import Path

MAX_RATING = 2000
MAX_HIDDEN = 8
MAX_TEST_BYTES = 4000  # input + output of one test
MAX_STATEMENT = 12_000

SOURCES = {1: "codechef", 2: "codeforces", 3: "hackerearth", 4: "codejam", 6: "atcoder", 7: "aizu"}
DIFFICULTY = {1: "easy", 2: "medium", 3: "hard", 4: "harder", 5: "hardest"}
MANY_ANSWERS = re.compile(r"(multiple|several|many) (possible |correct |valid |optimal )?(answers|solutions)|print any|output any|any of them",
                          re.I)

# --- Riegeli (simple chunks only) --------------------------------------------

BLOCK, BLOCK_HEADER = 1 << 16, 24


def _varint(b: bytes, i: int) -> tuple[int, int]:
    r = s = 0
    while True:
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        s += 7
        if x < 0x80:
            return r, i


def _decompress(kind: int, data: bytes) -> bytes:
    if kind == 0:
        return data
    import zstandard

    if kind != ord("z"):
        raise ValueError(f"unsupported Riegeli compression {chr(kind)!r}")
    size, i = _varint(data, 0)
    return zstandard.ZstdDecompressor().decompress(data[i:], max_output_size=size)


def riegeli_records(path: Path):
    raw = path.read_bytes()
    d = b"".join(raw[s + BLOCK_HEADER:s + BLOCK] for s in range(0, len(raw), BLOCK))  # drop block headers
    pos = 0
    while pos + 40 <= len(d):
        size = struct.unpack("<Q", d[pos + 8:pos + 16])[0]
        kind, n = chr(d[pos + 24]), int.from_bytes(d[pos + 25:pos + 32], "little")
        body = d[pos + 40:pos + 40 + size]
        pos += 40 + size
        if kind != "r" or not n:
            continue  # signature, metadata, padding
        sizes_len, i = _varint(body, 1)
        sizes = _decompress(body[0], body[i:i + sizes_len])
        values = _decompress(body[0], body[i + sizes_len:])
        j = off = 0
        for _ in range(n):
            ln, j = _varint(sizes, j)
            yield values[off:off + ln]
            off += ln


# --- protobuf wire format, just the ContestProblem fields used ---------------

def _fields(b: bytes):
    i = 0
    while i < len(b):
        key, i = _varint(b, i)
        num, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(b, i)
        elif wt == 2:
            ln, i = _varint(b, i)
            v, i = b[i:i + ln], i + ln
        elif wt == 5:
            v, i = b[i:i + 4], i + 4
        elif wt == 1:
            v, i = b[i:i + 8], i + 8
        else:
            raise ValueError(f"wire type {wt}")
        yield num, v


def _tests(blobs: list[bytes]) -> list[tuple[str, str]]:
    out = []
    for blob in blobs:
        t = {n: v.decode("utf-8", "replace") for n, v in _fields(blob)}
        out.append((t.get(1, ""), t.get(2, "")))
    return out


def decode(rec: bytes) -> dict:
    p: dict = {"tags": [], "public": [], "private": [], "generated": []}
    for n, v in _fields(rec):
        if n == 1:
            p["name"] = v.decode()
        elif n == 2:
            p["description"] = v.decode("utf-8", "replace")
        elif n in (4, 5, 18):
            p[{4: "public", 5: "private", 18: "generated"}[n]].append(v)
        elif n == 6:
            p["source"] = v
        elif n == 7:
            p["difficulty"] = v
        elif n == 10:
            p["cf_contest_id"] = v
        elif n == 12:
            p["cf_index"] = v.decode()
        elif n == 14:
            p["cf_rating"] = v
        elif n == 15:
            p["tags"].append(v.decode())
        elif n == 20:
            p["translated"] = bool(v)
    for k in ("public", "private", "generated"):
        p[k] = _tests(p[k])
    return p


# --- selection and clean-up ---------------------------------------------------

TEX = [(r"\le", "≤"), (r"\leq", "≤"), (r"\ge", "≥"), (r"\geq", "≥"), (r"\ne", "≠"), (r"\neq", "≠"), (r"\cdot", "·"),
       (r"\times", "×"), (r"\ldots", "…"), (r"\dots", "…"), (r"\cdots", "…"), (r"\lt", "<"), (r"\gt", ">"), (r"\oplus", "⊕"),
       (r"\infty", "∞"), (r"\to", "→"), (r"\rightarrow", "→"), (r"\%", "%"), (r"\,", " ")]


def clean(text: str) -> str:
    """Codeforces writes maths as $$$...$$$ LaTeX; make it readable as plain text."""
    text = text.replace("$$$$$$", "").replace("$$$", "")
    for a, b in sorted(TEX, key=lambda ab: -len(ab[0])):
        text = re.sub(re.escape(a) + r"(?![A-Za-z])", b, text)
    text = re.sub(r"\\(?:mathit|mathrm|text|textbf|texttt|operatorname)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\^\{([^{}]*)\}", r"^\1", text)
    text = re.sub(r"_\{([^{}]*)\}", r"_\1", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def keep(p: dict) -> bool:
    src = SOURCES.get(p.get("source", 0))
    if not p.get("description") or not p["public"] or p.get("translated"):
        return False
    if src == "codeforces":
        r = p.get("cf_rating", 0)
        return bool(p["tags"]) and 800 <= r <= MAX_RATING and "interactive" not in p["tags"] and "*special" not in p["tags"]
    return src in ("codechef", "hackerearth", "atcoder", "aizu") and DIFFICULTY.get(p.get("difficulty", 0)) in ("easy", "medium")


def small(t: tuple[str, str]) -> bool:
    return len(t[0]) + len(t[1]) <= MAX_TEST_BYTES


def entry(p: dict) -> dict:
    src = SOURCES[p["source"]]
    if src == "codeforces":
        ref = f"cf-{p['cf_contest_id']}{p['cf_index']}"
        title = re.sub(r"^\d+_[A-Z]\d?\. ", "", p["name"])
        url = f"https://codeforces.com/problemset/problem/{p['cf_contest_id']}/{p['cf_index']}"
        level = p["cf_rating"]
    else:
        ref = f"{src[:2]}-{re.sub(r'[^A-Za-z0-9]+', '-', p['name']).strip('-').lower()[:60]}"
        title, url, level = p["name"], "", DIFFICULTY[p["difficulty"]]
    statement = clean(p["description"])[:MAX_STATEMENT]
    tests = []
    if not MANY_ANSWERS.search(p["description"]):
        tests = [{"stdin": i, "expected": o, "hidden": False} for i, o in p["public"] if small((i, o))]
        extra = [t for t in p["private"] + p["generated"] if small(t) and t not in p["public"]]
        tests += [{"stdin": i, "expected": o, "hidden": True} for i, o in extra[:MAX_HIDDEN]]
    sample = p["public"][0][0] if small(p["public"][0]) else ""
    return {"ref": ref, "title": title, "source": src, "level": level, "tags": sorted(p["tags"]),
            "url": url, "prompt": statement, "sample_input": sample, "tests": tests}


def main(src_dir: str, out: str) -> None:
    files = sorted(Path(src_dir).glob("code_contests_*.riegeli*"))
    seen, rows = set(), []
    for f in files:
        for rec in riegeli_records(f):
            p = decode(rec)
            if keep(p):
                e = entry(p)
                if e["ref"] not in seen:
                    seen.add(e["ref"])
                    rows.append(e)
        print(f"{f.name}: {len(rows)} kept so far", file=sys.stderr)
    rows.sort(key=lambda e: (e["source"], str(e["level"]), e["ref"]))
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as g:
        for e in rows:
            g.write(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"wrote {len(rows)} problems to {out}", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:3])
