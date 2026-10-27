"""Function-style questions (LeetCode, MBPP) in every lab language.

Those datasets test a Python function: call it with some arguments, compare
what it returns. Nothing in that is Python-specific, so for C, C++, Java and
JavaScript labs this module turns the same tests into stdin/stdout tests:

- each argument's type comes from the Python signature (LeetCode's type
  hints) or, without hints (MBPP), from the test values themselves, and is
  narrowed by the values (int vs 64-bit long, a string of one character vs
  a string), the way LeetCode's own C++/Java signatures are written;
- stdin is one JSON value per argument, one per line, in parameter order;
- the student gets a LeetCode-style starter in their language (class
  Solution in C++/Java, a plain function in C/JavaScript, with C's
  `int* returnSize` conventions), and the question's harness, appended after
  their code, reads the arguments, calls the function and prints what it
  returns as JSON, exactly as the Python harness does, so the bundled
  expected outputs and the "json" comparison work unchanged.

Types covered: int, long, double, bool, char, string, lists and lists of
lists of those, and LeetCode's ListNode and TreeNode. A problem whose
arguments or answer fall outside them (a dict, a mixed tuple, a list of
trees) stays Python only, and so does a test whose numbers don't fit the
language (beyond 64 bits; beyond 2^53 in JavaScript).
"""

from __future__ import annotations

import ast
import json
import math
from dataclasses import dataclass

LANGUAGES = ("c", "cpp", "java", "javascript")
NODES = ("ListNode", "TreeNode")
INT32 = (-2**31, 2**31 - 1)
INT64 = (-2**63, 2**63 - 1)
JS_SAFE = (-2**53, 2**53)
MAX_DEPTH = 2  # lists of lists at most
RESERVED = {  # names that can't be parameters in one of the languages
    "auto", "bool", "boolean", "break", "byte", "case", "catch", "char", "class", "const", "continue", "default",
    "delete", "do", "double", "else", "enum", "eval", "export", "extends", "extern", "false", "final", "float", "for",
    "function", "goto", "if", "implements", "import", "in", "instanceof", "int", "interface", "let", "long", "new",
    "null", "package", "private", "protected", "public", "register", "return", "short", "signed", "sizeof",
    "static", "struct", "super", "switch", "template", "this", "throw", "true", "try", "typedef", "typeof",
    "union", "unsigned", "var", "void", "volatile", "while", "with", "yield", "arguments", "string", "vector",
}


# C library functions the starter's headers declare, which a C function can't be named after.
C_LIBRARY = {
    "abs", "atoi", "atof", "atol", "calloc", "ceil", "cos", "div", "exit", "exp", "fabs", "floor", "free", "getchar",
    "index", "isalnum", "isalpha", "isdigit", "islower", "isspace", "isupper", "labs", "log", "log10", "log2",
    "malloc", "memcpy", "memset", "pow", "printf", "putchar", "puts", "qsort", "rand", "realloc", "remove", "rename",
    "round", "scanf", "sin", "sqrt", "strcat", "strchr", "strcmp", "strcpy", "strlen", "strstr", "tan", "time",
    "tolower", "toupper", "trunc",
}


def c_name(fn: str) -> str:
    return fn + "_" if fn in C_LIBRARY else fn


@dataclass(frozen=True)
class Signature:
    fn: str
    params: tuple[tuple[str, str], ...]  # (name, type), type like "int", "string[]", "int[][]", "TreeNode"
    ret: str
    any_order: bool = False

    @property
    def nodes(self) -> set[str]:
        return {t for t in [self.ret, *(t for _, t in self.params)] if t in NODES}


def base(t: str) -> str:
    return t.replace("[]", "")


def depth(t: str) -> int:
    return t.count("[]")


# --- types from Python hints and from values --------------------------------

def from_hint(node: ast.AST | None) -> str | None:
    """A Python annotation -> our type name (None: not supported)."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):  # 'TreeNode' as a forward reference
        try:
            node = ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return None
    if isinstance(node, ast.Name):
        return {"int": "int", "float": "double", "bool": "bool", "str": "string",
                "ListNode": "ListNode", "TreeNode": "TreeNode"}.get(node.id)
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        inner = from_hint(node.slice)
        if node.value.id == "Optional":
            return inner if inner in NODES else None
        if node.value.id in ("List", "list") and inner and inner not in NODES and depth(inner) < MAX_DEPTH:
            return inner + "[]"
    return None


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def guess(values: list) -> str | None:
    """A type every value fits, for untyped tests (MBPP)."""
    if not values:
        return "int"  # e.g. always-empty lists: any element type works
    if all(isinstance(v, bool) for v in values):
        return "bool"
    if all(_int(v) for v in values):
        return "int"
    if all((_int(v) or isinstance(v, float)) and math.isfinite(v) for v in values):
        return "double"
    if all(isinstance(v, str) for v in values):
        return "string"
    if all(isinstance(v, (list, tuple)) for v in values):
        inner = guess([x for v in values for x in v])
        return inner + "[]" if inner and depth(inner) < MAX_DEPTH else None
    return None


def fits(v, t: str) -> bool:
    if t in NODES:
        return v is None or (isinstance(v, list) and all(
            (_int(x) and INT32[0] <= x <= INT32[1]) or (x is None and t == "TreeNode") for x in v))
    if t.endswith("[]"):
        return isinstance(v, (list, tuple)) and all(fits(x, t[:-2]) for x in v)
    if t in ("int", "long"):
        return _int(v)
    if t == "double":
        return (_int(v) or isinstance(v, float)) and math.isfinite(v)
    if t == "bool":
        return isinstance(v, bool)
    return isinstance(v, str) and (t == "string" or len(v) == 1)


def narrow(t: str, values: list) -> str:
    """int -> long when a value needs 64 bits; string -> char when every value is one character."""
    if t in NODES:
        return t
    if t.endswith("[]"):
        return narrow(t[:-2], [x for v in values for x in v]) + "[]"
    if t == "int" and any(not INT32[0] <= v <= INT32[1] for v in values):
        return "long"
    if t == "string" and values and all(len(v) == 1 for v in values):
        return "char"
    return t


def in_range(v, language: str) -> bool:
    """Every integer in `v` fits the language's widest integer."""
    lo, hi = JS_SAFE if language == "javascript" else INT64
    if isinstance(v, (list, tuple)):
        return all(in_range(x, language) for x in v)
    return not _int(v) or lo <= v <= hi


def build(fn: str, names: list[str], hints: list[str | None] | None, ret_hint: str | None,
          cases: list[tuple[list, object]], any_order: bool = False) -> tuple[Signature, list[int]] | None:
    """The signature for these tests and the indices of the tests it covers,
    or None when the problem can't be written in a typed language."""
    if hints is None:  # untyped: from the values
        hints = [guess([args[i] for args, _ in cases]) for i in range(len(names))]
        ret_hint = guess([exp for _, exp in cases])
    if ret_hint is None or any(h is None for h in hints) or not cases:
        return None
    if any_order and base(ret_hint) == "double":  # sorted by Python's float text, which other languages print differently
        return None
    keep = [k for k, (args, exp) in enumerate(cases)
            if len(args) == len(names) and all(fits(a, h) for a, h in zip(args, hints)) and fits(exp, ret_hint)]
    if not keep:
        return None
    params = tuple((safe_name(n), narrow(h, [cases[k][0][i] for k in keep])) for i, (n, h) in enumerate(zip(names, hints)))
    return Signature(fn, params, narrow(ret_hint, [cases[k][1] for k in keep]), any_order), keep


def safe_name(name: str) -> str:
    return name + "_" if name in RESERVED else name


def stdin(args: list) -> str:
    return "".join(json.dumps(a, ensure_ascii=False) + "\n" for a in args)


# --- starter code ------------------------------------------------------------

C_SCALAR = {"int": "int", "long": "long long", "double": "double", "bool": "bool", "char": "char", "string": "char*"}
CPP_SCALAR = {"int": "int", "long": "long long", "double": "double", "bool": "bool", "char": "char", "string": "string"}
JAVA_SCALAR = {"int": "int", "long": "long", "double": "double", "bool": "boolean", "char": "char", "string": "String"}
JAVA_BOXED = {"int": "Integer", "long": "Long", "double": "Double", "bool": "Boolean", "char": "Character", "string": "String"}
JS_SCALAR = {"int": "number", "long": "number", "double": "number", "bool": "boolean", "char": "character", "string": "string"}


def c_type(t: str) -> str:
    if t in NODES:
        return f"struct {t}*"
    return C_SCALAR[base(t)] + "*" * depth(t)


def c_params(sig: Signature) -> list[str]:
    out = []
    for n, t in sig.params:
        out.append(f"{c_type(t)} {n}")
        if depth(t) >= 1:
            out.append(f"int {n}Size")
        if depth(t) == 2:
            out.append(f"int* {n}ColSize")
    if depth(sig.ret) >= 1:
        out.append("int* returnSize")
    if depth(sig.ret) == 2:
        out.append("int** returnColumnSizes")
    return out


def cpp_type(t: str) -> str:
    if t in NODES:
        return t + "*"
    out = CPP_SCALAR[base(t)]
    for _ in range(depth(t)):
        out = f"vector<{out}>"
    return out


def java_type(t: str, returned: bool = False) -> str:
    if t in NODES:
        return t
    if returned and (depth(t) == 2 or (depth(t) == 1 and base(t) == "string")):  # as LeetCode usually returns them
        out = JAVA_BOXED[base(t)]
        for _ in range(depth(t)):
            out = f"List<{out}>"
        return out
    return JAVA_SCALAR[base(t)] + "[]" * depth(t)


def js_type(t: str) -> str:
    return t if t in NODES else JS_SCALAR[base(t)] + "[]" * depth(t)


C_NODES = {
    "ListNode": "struct ListNode {\n    int val;\n    struct ListNode *next;\n};\n",
    "TreeNode": "struct TreeNode {\n    int val;\n    struct TreeNode *left;\n    struct TreeNode *right;\n};\n",
}
CPP_NODES = {
    "ListNode": ("struct ListNode {\n    int val;\n    ListNode *next;\n    ListNode() : val(0), next(nullptr) {}\n"
                 "    ListNode(int x) : val(x), next(nullptr) {}\n    ListNode(int x, ListNode *next) : val(x), next(next) {}\n};\n"),
    "TreeNode": ("struct TreeNode {\n    int val;\n    TreeNode *left;\n    TreeNode *right;\n"
                 "    TreeNode() : val(0), left(nullptr), right(nullptr) {}\n"
                 "    TreeNode(int x) : val(x), left(nullptr), right(nullptr) {}\n"
                 "    TreeNode(int x, TreeNode *left, TreeNode *right) : val(x), left(left), right(right) {}\n};\n"),
}
JAVA_NODES = {
    "ListNode": ("class ListNode {\n    int val;\n    ListNode next;\n    ListNode() {}\n    ListNode(int val) { this.val = val; }\n"
                 "    ListNode(int val, ListNode next) { this.val = val; this.next = next; }\n}\n"),
    "TreeNode": ("class TreeNode {\n    int val;\n    TreeNode left;\n    TreeNode right;\n    TreeNode() {}\n"
                 "    TreeNode(int val) { this.val = val; }\n    TreeNode(int val, TreeNode left, TreeNode right) {\n"
                 "        this.val = val;\n        this.left = left;\n        this.right = right;\n    }\n}\n"),
}
JS_NODES = {
    "ListNode": ("function ListNode(val, next) {\n    this.val = (val === undefined ? 0 : val);\n"
                 "    this.next = (next === undefined ? null : next);\n}\n"),
    "TreeNode": ("function TreeNode(val, left, right) {\n    this.val = (val === undefined ? 0 : val);\n"
                 "    this.left = (left === undefined ? null : left);\n    this.right = (right === undefined ? null : right);\n}\n"),
}


def _provided(sig: Signature, defs: dict[str, str], comment: str) -> str:
    nodes = [n for n in NODES if n in sig.nodes]
    if not nodes:
        return ""
    return f"{comment} Provided, as on LeetCode: the {' and '.join(nodes)} definition{'s' if len(nodes) > 1 else ''}.\n" + \
        "\n".join(defs[n] for n in nodes) + "\n"


def starter(sig: Signature, language: str) -> str:
    if language == "c":
        head = "#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdbool.h>\n#include <limits.h>\n#include <math.h>\n\n"
        note = ("/**\n * Return an array you malloc (the tests don't free it), and set *returnSize to its length"
                + (";\n * set *returnColumnSizes to a malloc'd array of each row's length" if depth(sig.ret) == 2 else "")
                + ".\n */\n") if depth(sig.ret) else ""
        return (head + _provided(sig, C_NODES, "//") + note
                + f"{c_type(sig.ret)} {c_name(sig.fn)}({', '.join(c_params(sig))}) {{\n    \n}}\n")
    if language == "cpp":
        params = ", ".join(f"{cpp_type(t)}{'&' if depth(t) else ''} {n}" for n, t in sig.params)
        return ("#include <bits/stdc++.h>\nusing namespace std;\n\n" + _provided(sig, CPP_NODES, "//")
                + f"class Solution {{\npublic:\n    {cpp_type(sig.ret)} {sig.fn}({params}) {{\n        \n    }}\n}};\n")
    if language == "java":
        params = ", ".join(f"{java_type(t)} {n}" for n, t in sig.params)
        return ("import java.util.*;\n\n" + _provided(sig, JAVA_NODES, "//")
                + f"class Solution {{\n    public {java_type(sig.ret, True)} {sig.fn}({params}) {{\n        \n    }}\n}}\n")
    if language == "javascript":
        doc = "".join(f" * @param {{{js_type(t)}}} {n}\n" for n, t in sig.params)
        return (_provided(sig, JS_NODES, "//") + f"/**\n{doc} * @return {{{js_type(sig.ret)}}}\n */\n"
                + f"var {sig.fn} = function({', '.join(n for n, _ in sig.params)}) {{\n    \n}};\n")
    raise ValueError(language)


# --- harnesses ---------------------------------------------------------------

HEADER = "Student IDE test driver: reads one JSON value per argument from stdin, calls {call}\nand prints what it returns as JSON{nodes}."


def _header(sig: Signature, call: str, comment: str) -> str:
    nodes = " (linked lists and trees as lists)" if sig.nodes else ""
    return "\n".join(f"{comment} {line}" for line in HEADER.format(call=call, nodes=nodes).splitlines()) + "\n"


def _ord(sig: Signature, language: str) -> str:
    return ("true" if sig.any_order else "false") if language != "c" else ("1" if sig.any_order else "0")


# C ---------------------------------------------------------------------------

C_LIB = r'''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <ctype.h>

typedef struct sid_v { int kind; long long i; double d; char* s; int n; struct sid_v* a; } sid_v; /* 0 null 1 int 2 real 3 bool 4 str 5 list */
static char* sid_in; static size_t sid_p;
static void sid_ws(void) { while (sid_in[sid_p] && isspace((unsigned char) sid_in[sid_p])) sid_p++; }
static void sid_utf8(char* out, int* k, unsigned u) {
    if (u < 0x80) out[(*k)++] = (char) u;
    else if (u < 0x800) { out[(*k)++] = (char) (0xC0 | u >> 6); out[(*k)++] = (char) (0x80 | (u & 63)); }
    else { out[(*k)++] = (char) (0xE0 | u >> 12); out[(*k)++] = (char) (0x80 | (u >> 6 & 63)); out[(*k)++] = (char) (0x80 | (u & 63)); }
}
static sid_v sid_val(void) {
    sid_v v; memset(&v, 0, sizeof v); sid_ws();
    char c = sid_in[sid_p];
    if (c == '[') {
        int cap = 4; v.kind = 5; v.a = malloc(cap * sizeof(sid_v)); sid_p++; sid_ws();
        if (sid_in[sid_p] == ']') { sid_p++; return v; }
        for (;;) {
            if (v.n == cap) { cap *= 2; v.a = realloc(v.a, cap * sizeof(sid_v)); }
            v.a[v.n++] = sid_val(); sid_ws();
            if (sid_in[sid_p++] == ']') return v;
        }
    }
    if (c == '"') {
        size_t q = ++sid_p; while (sid_in[q] && sid_in[q] != '"') q += sid_in[q] == '\\' ? 2 : 1;
        int k = 0; v.kind = 4; v.s = malloc(q - sid_p + 1);
        while (sid_in[sid_p] != '"') {
            char d = sid_in[sid_p++];
            if (d != '\\') { v.s[k++] = d; continue; }
            d = sid_in[sid_p++];
            if (d == 'u') { char h[5] = {0}; memcpy(h, sid_in + sid_p, 4); sid_p += 4; sid_utf8(v.s, &k, (unsigned) strtoul(h, NULL, 16)); }
            else v.s[k++] = d == 'n' ? '\n' : d == 't' ? '\t' : d == 'r' ? '\r' : d == 'b' ? '\b' : d == 'f' ? '\f' : d;
        }
        v.s[k] = 0; sid_p++; return v;
    }
    if (!strncmp(sid_in + sid_p, "null", 4)) { sid_p += 4; return v; }
    if (!strncmp(sid_in + sid_p, "true", 4)) { sid_p += 4; v.kind = 3; v.i = 1; return v; }
    if (!strncmp(sid_in + sid_p, "false", 5)) { sid_p += 5; v.kind = 3; return v; }
    char* end; size_t q = sid_p; int real = 0;
    while (sid_in[q] && strchr("+-.eE0123456789", sid_in[q])) { if (strchr(".eE", sid_in[q])) real = 1; q++; }
    if (real) { v.kind = 2; v.d = strtod(sid_in + sid_p, &end); }
    else { v.kind = 1; v.i = strtoll(sid_in + sid_p, &end, 10); v.d = (double) v.i; }
    sid_p = (size_t) (end - sid_in); return v;
}
static void sid_read(void) {
    size_t cap = 1 << 16, n = 0, got; sid_in = malloc(cap);
    while ((got = fread(sid_in + n, 1, cap - n - 1, stdin)) > 0) { n += got; if (n + 1 >= cap) { cap *= 2; sid_in = realloc(sid_in, cap); } }
    sid_in[n] = 0; sid_p = 0;
}
static char* sid_dup(const char* s) { char* t = malloc(strlen(s) + 1); strcpy(t, s); return t; }
static char* sid_fi(long long x) { char b[32]; snprintf(b, sizeof b, "%lld", x); return sid_dup(b); }
static char* sid_fd(double x) { char b[40]; snprintf(b, sizeof b, "%.17g", x); return sid_dup(b); }
static char* sid_fb(bool x) { return sid_dup(x ? "true" : "false"); }
static char* sid_fs(const char* s) {
    if (!s) return sid_dup("null");
    char* t = malloc(strlen(s) * 6 + 3); int k = 0; t[k++] = '"';
    for (; *s; s++) {
        unsigned char c = (unsigned char) *s;
        if (c == '"' || c == '\\') { t[k++] = '\\'; t[k++] = (char) c; }
        else if (c == '\n') { t[k++] = '\\'; t[k++] = 'n'; }
        else if (c == '\t') { t[k++] = '\\'; t[k++] = 't'; }
        else if (c == '\r') { t[k++] = '\\'; t[k++] = 'r'; }
        else if (c < 0x20) k += sprintf(t + k, "\\u%04x", c);
        else t[k++] = (char) c;
    }
    t[k++] = '"'; t[k] = 0; return t;
}
static char* sid_fc(char c) { char s[2] = {c, 0}; return sid_fs(s); }
static int sid_cmp(const void* a, const void* b) { return strcmp(*(char* const*) a, *(char* const*) b); }
static char* sid_join(char** parts, int n, int ord) {
    size_t len = 3; for (int i = 0; i < n; i++) len += strlen(parts[i]) + 2;
    if (ord && n > 1) qsort(parts, (size_t) n, sizeof(char*), sid_cmp);
    char* t = malloc(len); size_t k = 0; t[k++] = '[';
    for (int i = 0; i < n; i++) { if (i) { t[k++] = ','; t[k++] = ' '; } size_t m = strlen(parts[i]); memcpy(t + k, parts[i], m); k += m; }
    t[k++] = ']'; t[k] = 0; return t;
}
'''
C_LIST = r'''static struct ListNode* sid_list(sid_v v) {
    struct ListNode* head = NULL;
    for (int i = v.n - 1; i >= 0; i--) { struct ListNode* x = calloc(1, sizeof *x); x->val = (int) v.a[i].i; x->next = head; head = x; }
    return head;
}
static char* sid_flist(struct ListNode* h) {
    int n = 0, cap = 16; char** parts = malloc(cap * sizeof(char*));
    for (; h && n < 100000; h = h->next) { if (n == cap) { cap *= 2; parts = realloc(parts, cap * sizeof(char*)); } parts[n++] = sid_fi(h->val); }
    return n ? sid_join(parts, n, 0) : sid_dup("null");
}
'''
C_TREE = r'''static struct TreeNode* sid_tree(sid_v v) {
    if (v.n == 0 || v.a[0].kind == 0) return NULL;
    struct TreeNode** q = malloc(v.n * sizeof(struct TreeNode*)); int head = 0, tail = 0, i = 1;
    struct TreeNode* root = calloc(1, sizeof *root); root->val = (int) v.a[0].i; q[tail++] = root;
    while (head < tail && i < v.n) {
        struct TreeNode* x = q[head++];
        if (v.a[i].kind) { x->left = calloc(1, sizeof *x); x->left->val = (int) v.a[i].i; q[tail++] = x->left; }
        if (++i < v.n && v.a[i].kind) { x->right = calloc(1, sizeof *x); x->right->val = (int) v.a[i].i; q[tail++] = x->right; }
        i++;
    }
    return root;
}
static char* sid_ftree(struct TreeNode* root) {
    if (!root) return sid_dup("null");
    int cap = 64, head = 0, tail = 0, n = 0; struct TreeNode** q = malloc(cap * sizeof(struct TreeNode*)); char** parts = malloc(cap * sizeof(char*));
    q[tail++] = root;
    while (head < tail) {
        struct TreeNode* x = q[head++];
        if (tail + 2 > cap || n + 1 > cap) { cap *= 2; q = realloc(q, cap * sizeof(struct TreeNode*)); parts = realloc(parts, cap * sizeof(char*)); }
        parts[n++] = x ? sid_fi(x->val) : sid_dup("null");
        if (x) { q[tail++] = x->left; q[tail++] = x->right; }
    }
    while (n && !strcmp(parts[n - 1], "null")) n--;
    return sid_join(parts, n, 0);
}
'''
C_SCALAR_IN = {"int": "(int) {v}.i", "long": "{v}.i", "double": "{v}.d", "bool": "(bool) {v}.i", "char": "{v}.s[0]", "string": "{v}.s"}
C_SCALAR_OUT = {"int": "sid_fi({x})", "long": "sid_fi({x})", "double": "sid_fd({x})", "bool": "sid_fb({x})", "char": "sid_fc({x})",
                "string": "sid_fs({x})"}


def c_harness(sig: Signature) -> str:
    lines, args = [], []
    for k, (n, t) in enumerate(sig.params):
        v = f"sid_a{k}"
        lines.append(f"    sid_v {v} = sid_val();")
        if t == "ListNode":
            lines.append(f"    struct ListNode* {n} = sid_list({v});")
        elif t == "TreeNode":
            lines.append(f"    struct TreeNode* {n} = sid_tree({v});")
        elif depth(t) == 0:
            lines.append(f"    {c_type(t)} {n} = {C_SCALAR_IN[t].format(v=v)};")
        elif depth(t) == 1:
            lines += [f"    {c_type(t)} {n} = malloc(({v}.n + 1) * sizeof({c_type(base(t))}));",
                      f"    for (int i = 0; i < {v}.n; i++) {n}[i] = {C_SCALAR_IN[base(t)].format(v=f'{v}.a[i]')};"]
        else:
            row = c_type(base(t) + "[]")
            lines += [f"    {c_type(t)} {n} = malloc(({v}.n + 1) * sizeof({row}));",
                      f"    int* {n}ColSize = malloc(({v}.n + 1) * sizeof(int));",
                      f"    for (int i = 0; i < {v}.n; i++) {{",
                      f"        {n}ColSize[i] = {v}.a[i].n;",
                      f"        {n}[i] = malloc(({v}.a[i].n + 1) * sizeof({c_type(base(t))}));",
                      f"        for (int j = 0; j < {v}.a[i].n; j++) {n}[i][j] = {C_SCALAR_IN[base(t)].format(v=f'{v}.a[i].a[j]')};",
                      "    }"]
        args += [n] + ([f"{v}.n"] if depth(t) >= 1 else []) + ([f"{n}ColSize"] if depth(t) == 2 else [])
    o, r = _ord(sig, "c"), sig.ret
    if depth(r) >= 1:
        lines.append("    int sid_n = 0; int* sid_cols = NULL;")
        args.append("&sid_n")
    if depth(r) == 2:
        args.append("&sid_cols")
    lines.append(f"    {c_type(r)} sid_r = {c_name(sig.fn)}({', '.join(args)});")
    if r == "ListNode":
        lines.append("    puts(sid_flist(sid_r));")
    elif r == "TreeNode":
        lines.append("    puts(sid_ftree(sid_r));")
    elif depth(r) == 0:
        lines.append(f"    puts({C_SCALAR_OUT[r].format(x='sid_r')});")
    elif depth(r) == 1:
        lines += ["    char** sid_s = malloc((sid_n + 1) * sizeof(char*));",
                  f"    for (int i = 0; i < sid_n; i++) sid_s[i] = {C_SCALAR_OUT[base(r)].format(x='sid_r[i]')};",
                  f"    puts(sid_r || !sid_n ? sid_join(sid_s, sid_n, {o}) : \"null\");"]
    else:
        lines += ["    if (sid_n && !sid_cols) { fprintf(stderr, \"set *returnColumnSizes to the length of each row\\n\"); return 1; }",
                  "    char** sid_s = malloc((sid_n + 1) * sizeof(char*));",
                  "    for (int i = 0; i < sid_n; i++) {",
                  "        char** sid_t = malloc((sid_cols[i] + 1) * sizeof(char*));",
                  f"        for (int j = 0; j < sid_cols[i]; j++) sid_t[j] = {C_SCALAR_OUT[base(r)].format(x='sid_r[i][j]')};",
                  f"        sid_s[i] = sid_join(sid_t, sid_cols[i], {o});",
                  "    }",
                  f"    puts(sid_join(sid_s, sid_n, {o}));"]
    return (_header(sig, f"{c_name(sig.fn)}()", "//") + C_LIB + (C_LIST if "ListNode" in sig.nodes else "")
            + (C_TREE if "TreeNode" in sig.nodes else "") + "\nint main(void) {\n    sid_read();\n" + "\n".join(lines)
            + "\n    return 0;\n}\n")


# C++ -------------------------------------------------------------------------

CPP_LIB = r'''#include <bits/stdc++.h>
namespace sidt {
std::string in;
size_t p = 0;
void ws() { while (p < in.size() && isspace((unsigned char) in[p])) p++; }
bool null_() { ws(); if (in.compare(p, 4, "null") == 0) { p += 4; return true; } return false; }
size_t num_end() { size_t q = p; while (q < in.size() && strchr("+-.eE0123456789", in[q])) q++; return q; }
void rd(long long& x) { ws(); size_t q = num_end(); x = std::stoll(in.substr(p, q - p)); p = q; }
void rd(int& x) { long long v; rd(v); x = (int) v; }
void rd(double& x) { ws(); size_t q = num_end(); x = std::stod(in.substr(p, q - p)); p = q; }
void rd(bool& x) { ws(); x = in[p] == 't'; p += x ? 4 : 5; }
void rd(std::string& s) {
    ws(); s.clear(); p++;
    while (in[p] != '"') {
        char c = in[p++];
        if (c != '\\') { s += c; continue; }
        c = in[p++];
        if (c == 'u') {
            unsigned u = std::stoul(in.substr(p, 4), nullptr, 16); p += 4;
            if (u < 0x80) s += (char) u;
            else if (u < 0x800) { s += (char) (0xC0 | u >> 6); s += (char) (0x80 | (u & 63)); }
            else { s += (char) (0xE0 | u >> 12); s += (char) (0x80 | (u >> 6 & 63)); s += (char) (0x80 | (u & 63)); }
        } else s += c == 'n' ? '\n' : c == 't' ? '\t' : c == 'r' ? '\r' : c == 'b' ? '\b' : c == 'f' ? '\f' : c;
    }
    p++;
}
void rd(char& c) { std::string s; rd(s); c = s.empty() ? 0 : s[0]; }
template <class T> void rd(std::vector<T>& v) {
    ws(); v.clear(); p++; ws();
    if (in[p] == ']') { p++; return; }
    for (;;) { T x; rd(x); v.push_back(x); ws(); if (in[p++] == ']') return; }
}
std::string sh(long long x, bool) { return std::to_string(x); }
std::string sh(int x, bool) { return std::to_string(x); }
std::string sh(double x, bool) { char b[40]; snprintf(b, sizeof b, "%.17g", x); return b; }
std::string sh(bool x, bool) { return x ? "true" : "false"; }
std::string sh(const std::string& s, bool) {
    std::string t = "\"";
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') { t += '\\'; t += (char) c; }
        else if (c == '\n') t += "\\n";
        else if (c == '\t') t += "\\t";
        else if (c == '\r') t += "\\r";
        else if (c < 0x20) { char b[8]; snprintf(b, sizeof b, "\\u%04x", c); t += b; }
        else t += (char) c;
    }
    return t + "\"";
}
std::string sh(char c, bool o) { return sh(std::string(1, c), o); }
std::string join(std::vector<std::string> a, bool o) {
    if (o) std::sort(a.begin(), a.end());
    std::string s = "[";
    for (size_t i = 0; i < a.size(); i++) { if (i) s += ", "; s += a[i]; }
    return s + "]";
}
'''
CPP_LIST = r'''ListNode* rd_list() {
    if (null_()) return nullptr;
    std::vector<int> v; rd(v); ListNode* head = nullptr;
    for (size_t i = v.size(); i-- > 0;) { ListNode* x = new ListNode(v[i]); x->next = head; head = x; }
    return head;
}
std::string sh(ListNode* h, bool) {
    if (!h) return "null";
    std::vector<std::string> a;
    for (; h && a.size() < 100000; h = h->next) a.push_back(std::to_string(h->val));
    return join(a, false);
}
'''
CPP_TREE = r'''TreeNode* rd_tree() {
    if (null_()) return nullptr;
    std::vector<TreeNode*> a; ws(); p++; ws();
    if (in[p] == ']') p++;
    else for (;;) { if (null_()) a.push_back(nullptr); else { int x; rd(x); a.push_back(new TreeNode(x)); } ws(); if (in[p++] == ']') break; }
    if (a.empty() || !a[0]) return nullptr;
    std::deque<TreeNode*> q{a[0]}; size_t i = 1;
    while (!q.empty() && i < a.size()) {
        TreeNode* x = q.front(); q.pop_front();
        x->left = a[i++]; if (x->left) q.push_back(x->left);
        if (i < a.size()) { x->right = a[i++]; if (x->right) q.push_back(x->right); }
    }
    return a[0];
}
std::string sh(TreeNode* root, bool) {
    if (!root) return "null";
    std::vector<std::string> a; std::deque<TreeNode*> q{root};
    while (!q.empty()) {
        TreeNode* x = q.front(); q.pop_front();
        a.push_back(x ? std::to_string(x->val) : "null");
        if (x) { q.push_back(x->left); q.push_back(x->right); }
    }
    while (!a.empty() && a.back() == "null") a.pop_back();
    return join(a, false);
}
'''
CPP_VECTOR = r'''template <class T> std::string sh(const std::vector<T>& v, bool o) {
    std::vector<std::string> a;
    for (const auto& x : v) a.push_back(sh(x, o));
    return join(a, o);
}
}  // namespace sidt
'''


def cpp_harness(sig: Signature) -> str:
    lines = []
    for n, t in sig.params:
        if t == "ListNode":
            lines.append(f"    ListNode* {n} = sidt::rd_list();")
        elif t == "TreeNode":
            lines.append(f"    TreeNode* {n} = sidt::rd_tree();")
        else:
            lines.append(f"    {cpp_type(t).replace('vector<', 'std::vector<').replace('string', 'std::string')} {n}; sidt::rd({n});")
    lines.append(f"    auto sid_r = Solution().{sig.fn}({', '.join(n for n, _ in sig.params)});")
    lines.append(f"    std::cout << sidt::sh(sid_r, {_ord(sig, 'cpp')}) << std::endl;")
    return (_header(sig, f"Solution().{sig.fn}()", "//") + CPP_LIB + (CPP_LIST if "ListNode" in sig.nodes else "")
            + (CPP_TREE if "TreeNode" in sig.nodes else "") + CPP_VECTOR
            + "\nint main() {\n    sidt::in.assign(std::istreambuf_iterator<char>(std::cin), {});\n" + "\n".join(lines) + "\n    return 0;\n}\n")


# Java ------------------------------------------------------------------------

JAVA_LIB = r'''public class Main {
    static String in;
    static int p;

    static void ws() { while (p < in.length() && Character.isWhitespace(in.charAt(p))) p++; }

    static Object val() {
        ws();
        char c = in.charAt(p);
        if (c == '[') {
            java.util.ArrayList<Object> a = new java.util.ArrayList<>();
            p++; ws();
            if (in.charAt(p) == ']') { p++; return a; }
            while (true) { a.add(val()); ws(); if (in.charAt(p++) == ']') return a; }
        }
        if (c == '"') {
            StringBuilder s = new StringBuilder();
            p++;
            while (in.charAt(p) != '"') {
                char d = in.charAt(p++);
                if (d != '\\') { s.append(d); continue; }
                d = in.charAt(p++);
                if (d == 'u') { s.append((char) Integer.parseInt(in.substring(p, p + 4), 16)); p += 4; }
                else s.append(d == 'n' ? '\n' : d == 't' ? '\t' : d == 'r' ? '\r' : d == 'b' ? '\b' : d == 'f' ? '\f' : d);
            }
            p++;
            return s.toString();
        }
        if (in.startsWith("null", p)) { p += 4; return null; }
        if (in.startsWith("true", p)) { p += 4; return true; }
        if (in.startsWith("false", p)) { p += 5; return false; }
        int q = p;
        while (p < in.length() && "+-.eE0123456789".indexOf(in.charAt(p)) >= 0) p++;
        String t = in.substring(q, p);
        return t.matches("-?\\d+") ? (Object) Long.valueOf(t) : (Object) Double.valueOf(t);
    }

    static Object conv(Object o, Class<?> c) {
        if (c.isArray()) {
            java.util.List<?> l = (java.util.List<?>) o;
            Object a = java.lang.reflect.Array.newInstance(c.getComponentType(), l.size());
            for (int i = 0; i < l.size(); i++) java.lang.reflect.Array.set(a, i, conv(l.get(i), c.getComponentType()));
            return a;
        }
        if (c == int.class) return ((Number) o).intValue();
        if (c == long.class) return ((Number) o).longValue();
        if (c == double.class) return ((Number) o).doubleValue();
        if (c == char.class) return ((String) o).charAt(0);
        return o;
    }

    static String q(String s) {
        StringBuilder t = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            if (c == '"' || c == '\\') t.append('\\').append(c);
            else if (c == '\n') t.append("\\n");
            else if (c == '\t') t.append("\\t");
            else if (c == '\r') t.append("\\r");
            else if (c < 0x20) t.append(String.format("\\u%04x", (int) c));
            else t.append(c);
        }
        return t.append('"').toString();
    }

    static String join(java.util.List<String> a, boolean o) {
        if (o) java.util.Collections.sort(a);
        return "[" + String.join(", ", a) + "]";
    }

    static String sh(Object x, boolean o) {
        if (x == null) return "null";
        if (x instanceof String) return q((String) x);
        if (x instanceof Character) return q(String.valueOf(x));
        if (x instanceof Number || x instanceof Boolean) return x.toString();
        java.util.List<String> a = new java.util.ArrayList<>();
'''
JAVA_LIST = r'''        if (x instanceof ListNode) {
            for (ListNode h = (ListNode) x; h != null && a.size() < 100000; h = h.next) a.add(String.valueOf(h.val));
            return join(a, false);
        }
'''
JAVA_TREE = r'''        if (x instanceof TreeNode) {
            java.util.ArrayDeque<java.util.Optional<TreeNode>> q = new java.util.ArrayDeque<>();
            q.add(java.util.Optional.of((TreeNode) x));
            while (!q.isEmpty()) {
                TreeNode t = q.poll().orElse(null);
                a.add(t == null ? "null" : String.valueOf(t.val));
                if (t != null) { q.add(java.util.Optional.ofNullable(t.left)); q.add(java.util.Optional.ofNullable(t.right)); }
            }
            while (!a.isEmpty() && a.get(a.size() - 1).equals("null")) a.remove(a.size() - 1);
            return join(a, false);
        }
'''
JAVA_REST = r'''        if (x.getClass().isArray()) {
            for (int i = 0; i < java.lang.reflect.Array.getLength(x); i++) a.add(sh(java.lang.reflect.Array.get(x, i), o));
        } else if (x instanceof Iterable) {
            for (Object y : (Iterable<?>) x) a.add(sh(y, o));
        } else return q(x.toString());
        return join(a, o);
    }
'''
JAVA_LIST_IN = r'''
    static ListNode list(Object o) {
        if (o == null) return null;
        java.util.List<?> v = (java.util.List<?>) o;
        ListNode head = null;
        for (int i = v.size() - 1; i >= 0; i--) { ListNode x = new ListNode(((Number) v.get(i)).intValue()); x.next = head; head = x; }
        return head;
    }
'''
JAVA_TREE_IN = r'''
    static TreeNode tree(Object o) {
        if (o == null) return null;
        java.util.List<?> v = (java.util.List<?>) o;
        if (v.isEmpty() || v.get(0) == null) return null;
        TreeNode root = new TreeNode(((Number) v.get(0)).intValue());
        java.util.ArrayDeque<TreeNode> q = new java.util.ArrayDeque<>();
        q.add(root);
        int i = 1;
        while (!q.isEmpty() && i < v.size()) {
            TreeNode x = q.poll();
            if (v.get(i) != null) { x.left = new TreeNode(((Number) v.get(i)).intValue()); q.add(x.left); }
            i++;
            if (i < v.size() && v.get(i) != null) { x.right = new TreeNode(((Number) v.get(i)).intValue()); q.add(x.right); }
            i++;
        }
        return root;
    }
'''


def java_harness(sig: Signature) -> str:
    lines = []
    for n, t in sig.params:
        if t == "ListNode":
            lines.append(f"        ListNode {n} = list(val());")
        elif t == "TreeNode":
            lines.append(f"        TreeNode {n} = tree(val());")
        else:
            jt = java_type(t)
            lines.append(f"        {jt} {n} = ({jt}) conv(val(), {jt}.class);")
    lines.append(f"        Object sid_r = new Solution().{sig.fn}({', '.join(n for n, _ in sig.params)});")
    lines.append(f"        System.out.println(sh(sid_r, {_ord(sig, 'java')}));")
    return (_header(sig, f"new Solution().{sig.fn}()", "//") + JAVA_LIB + (JAVA_LIST if "ListNode" in sig.nodes else "")
            + (JAVA_TREE if "TreeNode" in sig.nodes else "") + JAVA_REST
            + (JAVA_LIST_IN if "ListNode" in sig.nodes else "") + (JAVA_TREE_IN if "TreeNode" in sig.nodes else "")
            + "\n    public static void main(String[] sid_args) throws Exception {\n"
            + "        in = new String(System.in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);\n"
            + "\n".join(lines) + "\n    }\n}\n")


# JavaScript ------------------------------------------------------------------

JS_LIB = r''';(async () => {
  const _sidFs = typeof require === "function" ? require("fs") : await import("fs");
  const _sidArgs = _sidFs.readFileSync(0, "utf8").split("\n").filter((l) => l.trim() !== "").map((l) => JSON.parse(l));
  const _sidList = (v) => {
    let head = null;
    for (let i = (v || []).length - 1; i >= 0; i--) { const x = new ListNode(v[i]); x.next = head; head = x; }
    return head;
  };
  const _sidTree = (v) => {
    if (!v || !v.length || v[0] === null) return null;
    const root = new TreeNode(v[0]), q = [root];
    let i = 1, h = 0;
    while (h < q.length && i < v.length) {
      const x = q[h++];
      if (v[i] !== null) { x.left = new TreeNode(v[i]); q.push(x.left); }
      i++;
      if (i < v.length && v[i] !== null) { x.right = new TreeNode(v[i]); q.push(x.right); }
      i++;
    }
    return root;
  };
  const _sidJoin = (a, o) => "[" + (o ? a.sort() : a).join(", ") + "]";
  const _sidShow = (x, o) => {
    if (x === null || x === undefined) return "null";
    if (typeof ListNode !== "undefined" && x instanceof ListNode) {
      const a = [];
      for (let h = x; h && a.length < 100000; h = h.next) a.push(String(h.val));
      return _sidJoin(a, false);
    }
    if (typeof TreeNode !== "undefined" && x instanceof TreeNode) {
      const a = [], q = [x];
      for (let h = 0; h < q.length; h++) {
        a.push(q[h] ? String(q[h].val) : "null");
        if (q[h]) q.push(q[h].left ?? null, q[h].right ?? null);
      }
      while (a.length && a[a.length - 1] === "null") a.pop();
      return _sidJoin(a, false);
    }
    if (ArrayBuffer.isView(x) || x instanceof Set) x = Array.from(x);
    if (Array.isArray(x)) return _sidJoin(x.map((y) => _sidShow(y, o)), o);
    if (typeof x === "number" && !Number.isFinite(x)) return "null";
    return JSON.stringify(x);
  };
'''


def js_harness(sig: Signature) -> str:
    conv = {"ListNode": "_sidList({})", "TreeNode": "_sidTree({})"}
    call = ", ".join(conv.get(t, "{}").format(f"_sidArgs[{k}]") for k, (_, t) in enumerate(sig.params))
    return (_header(sig, f"{sig.fn}()", "//") + JS_LIB
            + f"  console.log(_sidShow(await {sig.fn}({call}), {_ord(sig, 'javascript')}));\n}})();\n")


HARNESSES = {"c": c_harness, "cpp": cpp_harness, "java": java_harness, "javascript": js_harness}


def harness(sig: Signature, language: str) -> str:
    return HARNESSES[language](sig)
