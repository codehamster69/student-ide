"""The "appeared without typing" check: typed editor code, vim saves with typing, starter files and
terminal pastes are seen; a vim save without typing, cat > file and files dropped in from outside are not."""

from studentide import evidence

W = "/home/student/labs/l1/a1"


def ev(seq, typ, **data):
    return {"seq": seq, "t": float(seq), "type": typ, "data": data}


def typed(seq0, path, text, start_len=0):
    """editor edits that type `text` one character at a time"""
    out, n = [], start_len
    for i, ch in enumerate(text):
        out.append(ev(seq0 + i, "edit", origin="input.type", changes=[[n, n, ch]], len_before=n, len_after=n + 1, path=path))
        n += 1
    return out


def vim_keys(seq0, path, n):
    return [ev(seq0 + i, "key", action="down", code="KeyA", cls="letter", surface="terminal-editor", path=path) for i in range(n)]


def fs(seq, path, added, origin="terminal-editor", command="vim main.c"):
    return ev(seq, "fs_change", path=path, size=len(added), sha256="a" * 64, origin=origin, command=command,
              added=added, added_lines=added.count("\n") + 1, removed_lines=0, diff="")


def test_typed_in_the_editor_is_seen():
    code = 'printf("hello world");\nreturn 0;\n'
    events = [ev(0, "snapshot", reason="start", text="", path=f"{W}/main.c")] + typed(1, f"{W}/main.c", code)
    assert evidence.check_files({"main.c": code}, events, W) == []


def test_a_vim_save_needs_typing_behind_it():
    line = "int add(int a, int b) { return a + b; }"
    with_keys = vim_keys(0, f"{W}/main.c", 45) + [fs(100, f"{W}/main.c", line)]
    s = evidence.saves(with_keys, W)
    assert s[0]["explained"] and s[0]["typed_keys"] == 45
    assert evidence.check_files({"main.c": line}, with_keys, W) == []
    no_keys = vim_keys(0, f"{W}/main.c", 3) + [fs(100, f"{W}/main.c", line * 3)]
    assert not evidence.saves(no_keys, W)[0]["explained"]


def test_cat_and_outside_writes_are_unseen():
    solution = "def solve(n):\n    return sum(range(n + 1))\nprint(solve(int(input())))\n"
    events = [fs(5, f"{W}/sol.py", solution, origin="terminal", command="cat > sol.py"),
              fs(6, f"{W}/other.py", solution, origin="outside", command=None)]
    saves = evidence.saves(events, W)
    assert [s["explained"] for s in saves] == [False, False]
    flagged = evidence.check_files({"sol.py": solution}, events, W)
    assert flagged[0]["path"] == "sol.py" and flagged[0]["unseen_lines"] == 3


def test_starter_files_and_terminal_pastes_are_seen_but_reloads_are_not():
    starter = {"main.c": "#include <stdio.h>\nint main(void) {\n"}
    pasted = "for (int i = 0; i < 10; i++) printf(\"%d\", i);"
    events = [ev(0, "term_paste", term_id="t", length=len(pasted), lines=1, text=pasted, sha256="b" * 64)]
    assert evidence.check_files({"main.c": starter["main.c"] + pasted}, events, W, starter) == []
    # the editor reloading a file changed on disk is not evidence of the new text
    new = "while (scanf(\"%d\", &x) == 1) total += x * x;\nprintf(\"%lld\\n\", total);\n"
    reload = [ev(0, "snapshot", reason="start", text="", path=f"{W}/main.c"),
              ev(1, "edit", origin="reload", changes=[[0, 0, new]], len_before=0, len_after=len(new), path=f"{W}/main.c")]
    assert evidence.check_files({"main.c": new}, reload, W)[0]["unseen_lines"] == 2
