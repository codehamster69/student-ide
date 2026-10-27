"""The similarity check behind "similar submissions worth a look"."""

from pathlib import Path

from studentide import similarity
from studentide.similarity import Entry, similar_pairs, tokenize

from test_compete import ADMIN, client, app, enter  # noqa: F401  (fixtures)

CORPUS = Path(__file__).parent / "fixtures" / "similarity"
KADANE_C = (CORPUS / "kadane" / "a.c").read_text()
KADANE_PY = (CORPUS / "kadane" / "a.py").read_text()

RENAMED_C = """#include <stdio.h>
// totally my own work
int main(void)
{
  int count; scanf("%d", &count);
  long long top = -1000000000000LL, run = 0;
  for (int k = 0; k < count; k++)
  {
    long long val; scanf("%lld", &val);
    run = run + val > val ? run + val : val;   /* extend or restart */
    if (run > top) { top = run; }
  }
  printf("%lld\\n", top);
  return 0;
}
"""


def texts(code, lang):
    return [t.text for t in tokenize(code, lang)]


def test_names_layout_comments_and_literals_do_not_matter():
    assert texts(KADANE_C, "c") == texts(RENAMED_C, "c")
    assert texts("x = 'a'  # hi\nprint(x)\n", "python") == texts('total = "zzz"\nprint(total)', "python")
    assert texts("let a = `x${1}`; // c\nconsole.log(a)", "javascript") == texts("let b = 'y'\nconsole.log(b);", "javascript")
    java = "import java.util.*;\npublic class Main { public static void main(String[] a) { int n = 3; } }"
    assert texts(java, "java") == texts("public class Main{public static void main(String[] args){int k=7;}}", "java")
    # keywords and structure survive normalisation
    assert texts("for i in range(3): pass", "python")[:3] == ["for", "V", "in"]


def test_tokens_keep_their_place_in_the_code():
    t = tokenize("int  total = 0;", "c")
    assert [("int  total = 0;"[x.start:x.end]) for x in t] == ["int", "total", "=", "0"]


def test_copy_is_found_and_regions_point_at_the_code():
    pairs = similar_pairs([Entry("a", "S1", "c", KADANE_C), Entry("b", "S2", "c", RENAMED_C)], {})
    assert len(pairs) == 1 and pairs[0]["similarity"] == 1.0
    r = pairs[0]["regions"][0]
    assert KADANE_C[r["a"][0]:r["a"][1]].startswith("int main") and RENAMED_C[r["b"][0]:r["b"][1]].startswith("int main")


def test_same_student_and_other_languages_are_never_paired():
    cpp = KADANE_C.replace("#include <stdio.h>", "#include <cstdio>")
    entries = [Entry("a", "S1", "c", KADANE_C), Entry("b", "S1", "cpp", cpp),  # one student, two languages
               Entry("c", "S2", "cpp", cpp), Entry("d", "S3", "python", KADANE_PY)]
    pairs = similar_pairs(entries, {})
    assert {frozenset((p["a"], p["b"])) for p in pairs} == {frozenset("ac"), frozenset("bc")}  # C and C++ compare


def test_starter_code_is_not_counted():
    starter = "#include <stdio.h>\n\nint main(void) {\n    int n;\n    scanf(\"%d\", &n);\n    long long best = -1000000000000LL, cur = 0;\n    return 0;\n}\n"
    other = KADANE_C.replace("cur = cur + x > x ? cur + x : x;", "if (cur < 0) cur = 0;\n        cur += x;")
    with_starter = similar_pairs([Entry("a", "S1", "c", KADANE_C), Entry("b", "S2", "c", other)], {"c": starter}, report_at=0)
    without = similar_pairs([Entry("a", "S1", "c", KADANE_C), Entry("b", "S2", "c", other)], {}, report_at=0)
    assert with_starter[0]["similarity"] < without[0]["similarity"]


def test_code_most_of_the_class_shares_is_masked():
    base = "n = int(input())\ntotal = 0\nfor i in range(n):\n    total += int(input())\nprint(total)\n"
    own = ["x = sorted(set(map(int, input().split())))\nprint(len(x), x[0], x[-1], sum(x) // len(x))\n",
           "q = [w.upper() for w in input().split() if w]\nprint(' '.join(reversed(q)), len(q) * 2 - 1)\n"]
    entries = [Entry(str(i), f"S{i}", "python", base + own[i % 2]) for i in range(6)]
    similarity.prepare(entries, {})
    assert all(any(e.mask) for e in entries)  # the shared reading loop is everyone's, not evidence


def test_independent_solutions_stay_apart_and_disguised_copies_do_not():
    """A small version of backend/scripts/eval_similarity.py (the full run is in the thesis)."""
    import sys
    sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
    import eval_similarity
    rows = eval_similarity.run()
    indep = [r["similarity"] for r in rows if r["level"] == "independent"]
    copies = [r["similarity"] for r in rows if r["level"] != "independent"]
    assert max(indep) < 0.5 <= min(copies)


def test_paste_stats():
    ev = [{"type": "edit", "data": {"origin": "input.type", "changes": [[0, 0, "ab"]]}},
          {"type": "edit", "data": '{"origin": "input.paste", "changes": [[2, 2, "hello"]]}'},
          {"type": "edit", "data": {"origin": "delete.backward", "changes": [[0, 1, ""]]}}]
    assert similarity.paste_stats(ev) == {"typed_chars": 2, "pasted_chars": 5, "n_pastes": 1}


def test_teacher_sees_similar_pairs(client, app):
    c = client.post("/api/teach/competitions", headers=ADMIN, json={"title": "Any", "language": "any"}).json()
    lab_id = c["lab_id"]
    lab = client.post(f"/api/teach/labs/{lab_id}/questions", headers=ADMIN, json={
        "title": "Max subarray", "tests": [{"name": "t", "stdin": "3\n1 -2 3", "expected": "3"}]}).json()
    qid = lab["questions"][0]["id"]
    client.put(f"/api/teach/labs/{lab_id}/roster", headers=ADMIN, json={"student_ids": ["S1", "S2", "S3"], "everyone": False})
    for s in ("S1", "S2", "S3"):
        enter(client, s)
    client.post(f"/api/teach/competitions/{lab_id}/start", headers=ADMIN)
    assert client.post(f"/api/competitions/{lab_id}/join", json={"student_id": "S2", "handle": "Bo"}).status_code == 200
    code = {"S1": ("c", KADANE_C), "S2": ("c", RENAMED_C), "S3": ("python", KADANE_PY)}
    sess = {}
    for s, (lang, src) in code.items():
        sess[s] = client.post("/api/sessions", json={"student_id": s, "question_id": qid, "client_meta": {}, "language": lang}).json()["session_id"]
        client.post(f"/api/sessions/{sess[s]}/events", json={"schema_version": 1, "events": [
            {"seq": 0, "t": 0.0, "type": "edit", "data": {"changes": [[0, 0, src]], "origin": "input.paste" if s == "S2" else "input.type",
                                                       "len_before": 0, "len_after": len(src)}}]})
        assert client.post(f"/api/sessions/{sess[s]}/submit", json={"code": src}).status_code == 200

    assert client.get(f"/api/teach/competitions/{lab_id}/similarity").status_code in (401, 403)  # staff only
    rep = client.get(f"/api/teach/competitions/{lab_id}/similarity", headers=ADMIN).json()
    q = rep["questions"][0]
    assert q["n_compared"] == 3 and len(q["pairs"]) == 1
    p = q["pairs"][0]
    assert {p["a"]["student_id"], p["b"]["student_id"]} == {"S1", "S2"} and p["similarity"] == 1.0
    assert "regions" not in p and {p["a"]["handle"], p["b"]["handle"]} == {"S1", "Bo"}

    a, b = (p["a"], p["b"]) if p["a"]["student_id"] == "S2" else (p["b"], p["a"])
    d = client.get(f"/api/teach/competitions/{lab_id}/similarity/{a['submission_id']}/{b['submission_id']}", headers=ADMIN).json()
    assert d["a"]["student_id"] == "S2" and d["a"]["pasted_chars"] == len(RENAMED_C) and d["b"]["typed_chars"] == len(KADANE_C)
    r = d["regions"][0]
    assert d["a"]["code"][r["a"][0]:r["a"][1]].startswith("int main") and d["b"]["code"][r["b"][0]:r["b"][1]].startswith("int main")
    assert client.get(f"/api/teach/competitions/{lab_id}/similarity/{a['submission_id']}/nope", headers=ADMIN).status_code == 404
