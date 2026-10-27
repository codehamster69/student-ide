"""Similar submissions in a competition, for a teacher to look at.

This is a pointer for a conversation, never a verdict. Short programs that
solve the same small problem often look alike because there are only so many
ways to write them, and two students can learn the same idiom from the same
teacher. Nothing here changes a score, and the page that shows it says so.

How it works (the MOSS / JPlag family of methods):

1. Each submission is turned into a stream of normalised tokens. Comments,
   whitespace, include/import lines and braces/semicolons are dropped; every
   name that is not a keyword of the language becomes V, every number N and
   every string or character literal S. Renaming variables, reformatting,
   changing comments or string texts therefore changes nothing.
2. Winnowing (Schleimer, Wilkerson and Aiken 2003): hash every K-token
   window and keep the smallest hash of every W consecutive windows. Two
   submissions sharing a run of K + W - 1 tokens are guaranteed to share a
   fingerprint. Shared fingerprints pick the candidate pairs cheaply.
3. Greedy string tiling (Wise 1993, the core of JPlag) on each candidate pair
   finds the maximal common runs of at least MIN_MATCH tokens. Similarity is
   the share of both submissions covered by those runs; the runs map back to
   character ranges so the page can highlight them side by side.

Code the student did not write is never counted: tokens matching the
question's starter code in that language, and runs that a large part of the
class shares (COMMON_SHARE of the submissions, at least COMMON_MIN of them:
the natural way to write it), are masked before tiling.

Languages: C and C++ are compared with each other (C code is C++); Java,
JavaScript and Python each within themselves. A solution translated by hand
from one language into another is not detected by token methods, and this
module does not pretend otherwise.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

K = 8               # tokens per fingerprinted window
W = 4               # winnowing window: any shared run of K + W - 1 tokens is caught
MIN_MATCH = 8       # shortest common run that counts in tiling
MIN_TOKENS = 15     # shorter submissions (after masking) are too small to compare meaningfully
COMMON_SHARE = 0.5  # a run in this share of submissions is "how everyone writes it" ...
COMMON_MIN = 5      # ... once at least this many submissions share it
REPORT_AT = 0.3     # pairs below this similarity are not listed

FAMILY = {"python": "python", "c": "c", "cpp": "c", "java": "java", "javascript": "javascript"}

_C_KEYWORDS = """auto break case char const continue default do double else enum extern float for goto if inline int
long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while
bool true false catch class delete friend namespace new nullptr operator private protected public template this throw
try typename using virtual NULL""".split()
KEYWORDS = {
    "c": set(_C_KEYWORDS),
    "java": set("""abstract assert boolean break byte case catch char class const continue default do double else enum
extends final finally float for if implements import instanceof int interface long native new package private
protected public return short static super switch synchronized this throw throws try void volatile while var
true false null String""".split()),
    "javascript": set("""break case catch class const continue debugger default delete do else export extends finally
for function if import in instanceof let new return super switch this throw try typeof var void while with yield
async await of true false null undefined""".split()),
    "python": set("""False None True and as assert async await break class continue def del elif else except finally
for from global if import in is lambda nonlocal not or pass raise return try while with yield""".split()),
}

_OPS = r"\*\*=|//=|>>=|<<=|>>>|===|!==|\.\.\.|->|::|\+\+|--|<<|>>|<=|>=|==|!=|&&|\|\||\+=|-=|\*=|/=|%=|&=|\|=|\^=|\*\*|//|=>|[-+*/%=<>!&|^~?:.,()\[\]@]"
_NUM = r"(?:0[xX][0-9a-fA-F_]+|\d[\d_]*\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)[a-zA-Z]*"
_IDENT = r"[A-Za-z_$][\w$]*"
_C_STR = r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\''

LEXERS = {
    "c": re.compile(rf"""(?P<skip>\s+|//[^\n]*|/\*[\s\S]*?(?:\*/|$)|\#[^\n]*)
        |(?P<drop>[{{}};])|(?P<str>{_C_STR})|(?P<num>{_NUM})|(?P<id>{_IDENT})|(?P<op>{_OPS})|(?P<other>\S)""", re.X),
    "java": re.compile(rf"""(?P<skip>\s+|//[^\n]*|/\*[\s\S]*?(?:\*/|$)|(?:import|package)\s[^;\n]*;?)
        |(?P<drop>[{{}};])|(?P<str>{_C_STR})|(?P<num>{_NUM})|(?P<id>{_IDENT})|(?P<op>{_OPS})|(?P<other>\S)""", re.X),
    "javascript": re.compile(rf"""(?P<skip>\s+|//[^\n]*|/\*[\s\S]*?(?:\*/|$))
        |(?P<drop>[{{}};])|(?P<str>{_C_STR}|`(?:\\.|[^`\\])*`)|(?P<num>{_NUM})|(?P<id>{_IDENT})|(?P<op>{_OPS})|(?P<other>\S)""", re.X),
    "python": re.compile(rf"""(?P<skip>\s+|\#[^\n]*|\\\n)
        |(?P<drop>;)|(?P<str>[rRbBuUfF]{{0,2}}(?:\"\"\"[\s\S]*?(?:\"\"\"|$)|'''[\s\S]*?(?:'''|$)|{_C_STR}))
        |(?P<num>{_NUM})|(?P<id>{_IDENT})|(?P<op>{_OPS})|(?P<other>\S)""", re.X),
}


@dataclass
class Token:
    text: str   # normalised
    start: int  # character range in the original code
    end: int


def tokenize(code: str, language: str) -> list[Token]:
    """Normalised tokens of `code` (see the module docstring)."""
    fam = FAMILY.get(language, "c")
    kw = KEYWORDS[fam]
    out = []
    for m in LEXERS[fam].finditer(code):
        kind = m.lastgroup
        if kind in ("skip", "drop"):
            continue
        s = m.group()
        text = ("S" if kind == "str" else "N" if kind == "num" else
                (s if s in kw else "V") if kind == "id" else s)
        out.append(Token(text, m.start(), m.end()))
    return out


def _hash(texts: list[str]) -> int:
    return int.from_bytes(hashlib.blake2b("\x1f".join(texts).encode(), digest_size=8).digest(), "big")


def kgram_hashes(tokens: list[Token], k: int = K) -> list[int]:
    t = [x.text for x in tokens]
    return [_hash(t[i:i + k]) for i in range(len(t) - k + 1)]


def winnow(hashes: list[int], w: int = W) -> dict[int, int]:
    """Fingerprints: hash -> first k-gram position, the minimum of every window of w hashes
    (rightmost on ties, so a run of equal hashes yields one fingerprint)."""
    fp: dict[int, int] = {}
    if not hashes:
        return fp
    if len(hashes) <= w:
        h = min(hashes)
        return {h: hashes.index(h)}
    for i in range(len(hashes) - w + 1):
        win = hashes[i:i + w]
        lo = min(win)
        j = i + max(p for p, h in enumerate(win) if h == lo)
        fp.setdefault(lo, j)
    return fp


def tile(a: list[str], b: list[str], mask_a: list[bool], mask_b: list[bool],
         mml: int = MIN_MATCH) -> list[tuple[int, int, int]]:
    """Greedy string tiling: maximal non-overlapping common runs (i in a, j in b, length),
    longest first, each at least mml tokens, never over a masked token."""
    used_a, used_b = list(mask_a), list(mask_b)
    tiles = []
    while True:
        # every unmasked mml-gram of b, to find candidate starts without an n*m scan
        index: dict[tuple, list[int]] = {}
        for j in range(len(b) - mml + 1):
            if not any(used_b[j:j + mml]):
                index.setdefault(tuple(b[j:j + mml]), []).append(j)
        best, found = mml, []
        for i in range(len(a) - mml + 1):
            if any(used_a[i:i + mml]):
                continue
            for j in index.get(tuple(a[i:i + mml]), ()):
                n = mml
                while i + n < len(a) and j + n < len(b) and a[i + n] == b[j + n] and not used_a[i + n] and not used_b[j + n]:
                    n += 1
                if n > best:
                    best, found = n, [(i, j, n)]
                elif n == best:
                    found.append((i, j, n))
        if not found:
            return tiles
        for i, j, n in found:
            if any(used_a[i:i + n]) or any(used_b[j:j + n]):
                continue  # overlaps a tile taken in this round
            used_a[i:i + n] = [True] * n
            used_b[j:j + n] = [True] * n
            tiles.append((i, j, n))


@dataclass
class Entry:
    """One submission as compared: the last one a student made in one language."""
    key: str                 # submission id
    student_id: str
    language: str
    code: str
    tokens: list[Token] = field(default_factory=list)
    mask: list[bool] = field(default_factory=list)  # starter code or class-wide common code
    fps: set[int] = field(default_factory=set)

    @property
    def n_own(self) -> int:
        return sum(not m for m in self.mask)


def _cover(mask: list[bool], start: int, n: int) -> None:
    mask[start:start + n] = [True] * n


def prepare(entries: list[Entry], starters: dict[str, str]) -> None:
    """Tokenise, mask starter code and class-wide common runs, and fingerprint what is left.
    `starters`: language -> the question's starter code in it."""
    starter_tokens = {lang: [t.text for t in tokenize(code, lang)] for lang, code in starters.items() if code.strip()}
    for e in entries:
        e.tokens = tokenize(e.code, e.language)
        e.mask = [False] * len(e.tokens)
        st = starter_tokens.get(e.language)
        if st:
            texts = [t.text for t in e.tokens]
            for i, _, n in tile(texts, st, [False] * len(texts), [False] * len(st), min(MIN_MATCH, max(3, len(st)))):
                _cover(e.mask, i, n)
    # runs most of the class shares, per language family
    by_family: dict[str, list[Entry]] = {}
    for e in entries:
        by_family.setdefault(FAMILY[e.language], []).append(e)
    for group in by_family.values():
        grams = [kgram_hashes(e.tokens) for e in group]
        seen: dict[int, int] = {}
        for g in grams:
            for h in set(g):
                seen[h] = seen.get(h, 0) + 1
        common = {h for h, c in seen.items() if c >= max(COMMON_MIN, COMMON_SHARE * len(group))}
        for e, g in zip(group, grams):
            for i, h in enumerate(g):
                if h in common:
                    _cover(e.mask, i, K)
            hashes = [h if not any(e.mask[i:i + K]) else None for i, h in enumerate(g)]
            # winnow each unmasked stretch on its own, so masked code leaves no fingerprints
            run: list[int] = []
            for h in hashes + [None]:
                if h is None:
                    e.fps.update(winnow(run))
                    run = []
                else:
                    run.append(h)


def compare(a: Entry, b: Entry) -> dict:
    """Tile two prepared entries: similarity and the matching character ranges."""
    tiles = tile([t.text for t in a.tokens], [t.text for t in b.tokens], a.mask, b.mask)
    matched = sum(n for _, _, n in tiles)
    na, nb = max(a.n_own, 1), max(b.n_own, 1)
    regions = [{"a": [a.tokens[i].start, a.tokens[i + n - 1].end], "b": [b.tokens[j].start, b.tokens[j + n - 1].end],
                "tokens": n} for i, j, n in sorted(tiles)]
    return {"similarity": round(2 * matched / (na + nb), 4), "share_a": round(matched / na, 4),
            "share_b": round(matched / nb, 4), "matched_tokens": matched,
            "longest_run": max((n for *_, n in tiles), default=0), "regions": regions}


def similar_pairs(entries: list[Entry], starters: dict[str, str], report_at: float = REPORT_AT) -> list[dict]:
    """Every pair of different students' submissions in the same language family whose
    similarity is at least `report_at`, most similar first."""
    prepare(entries, starters)
    usable = [e for e in entries if e.n_own >= MIN_TOKENS]
    holders: dict[int, list[int]] = {}
    for idx, e in enumerate(usable):
        for h in e.fps:
            holders.setdefault(h, []).append(idx)
    shared: dict[tuple[int, int], int] = {}
    for idxs in holders.values():
        for x in range(len(idxs)):
            for y in range(x + 1, len(idxs)):
                p, q = usable[idxs[x]], usable[idxs[y]]
                if p.student_id != q.student_id and FAMILY[p.language] == FAMILY[q.language]:
                    shared[(idxs[x], idxs[y])] = shared.get((idxs[x], idxs[y]), 0) + 1
    out = []
    for (x, y) in shared:
        r = compare(usable[x], usable[y])
        if r["similarity"] >= report_at and r["matched_tokens"] >= MIN_MATCH:
            out.append({"a": usable[x].key, "b": usable[y].key, **r})
    out.sort(key=lambda r: (-r["similarity"], -r["matched_tokens"]))
    return out


def paste_stats(events: list[dict]) -> dict:
    """How the code arrived, from the session's edit events: characters typed vs pasted.
    Facts for the teacher's conversation, not a judgement."""
    typed = pasted = n_pastes = 0
    for e in events:
        if e["type"] == "edit":
            data = e["data"] if isinstance(e["data"], dict) else json.loads(e["data"])
            n = sum(len(text) for _, _, text in data["changes"])
            if data["origin"].startswith("input.paste"):
                pasted += n
                n_pastes += 1
            elif data["origin"].startswith("input"):
                typed += n
    return {"typed_chars": typed, "pasted_chars": pasted, "n_pastes": n_pastes}
