// End-to-end check of any-language competitions and the similar-submissions
// page, with screenshots for the thesis: a teacher creates an "Any language"
// competition; a student opens a question in Python, switches to C, solves it
// and submits; classmates (driven through the API) answer in Python, C++ and
// Java, one of them with a renamed and reformatted copy of the student's C;
// the board shows each row's languages and the teacher opens the pair side by side.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/anylang.mjs [screenshot-dir] [light|dark]
//
// The server needs STUDENTIDE_ADMIN_TOKEN=$TOKEN and gcc, g++ and javac for the
// classmates' answers. Any database works.

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
const TAG = Date.now().toString(36).toUpperCase();
const STUDENT = `E2E${TAG}`;
const CLASS = ["Grace", "Linus", "Guido", "Ken"].map((h, i) => ({ id: `C${TAG}${i}`, handle: `${h} ${TAG.slice(-2)}` }));

const api = async (method, path, body, admin = false) => {
  const r = await fetch(BASE + path, {
    method,
    headers: { "Content-Type": "application/json", ...(admin ? { "X-Admin-Token": TOKEN } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  assert.ok(r.ok, `${method} ${path}: ${r.status} ${JSON.stringify(data)}`);
  return data;
};

const browser = await chromium.launch();
const errors = [];
const open = async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
  page.on("pageerror", (e) => errors.push(e.message));
  return page;
};
const shot = async (page, name, full = false) => {
  if (!OUT) return;
  await page.waitForTimeout(1200);
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await page.screenshot({ path: `${OUT}/anylang-${SCHEME}-${name}.png`, fullPage: full });
};

const C_SOLUTION = `#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    long long best = -1000000000000LL, cur = 0;
    for (int i = 0; i < n; i++) {
        long long x;
        scanf("%lld", &x);
        cur = cur + x > x ? cur + x : x;
        if (cur > best) best = cur;
    }
    printf("%lld\\n", best);
    return 0;
}
`;
// a classmate's renamed, reformatted copy of the same program
const C_COPY = `#include<stdio.h>
// max subarray
int main(void)
{
  int count; scanf("%d", &count);
  long long top = -1000000000000LL, run = 0;
  for (int k = 0; k < count; k++)
  {
    long long val; scanf("%lld", &val);
    run = run + val > val ? run + val : val;
    if (run > top) { top = run; }
  }
  printf("%lld\\n", top);
  return 0;
}
`;
const PY = "n = int(input())\na = list(map(int, input().split()))\nbest = a[0]\ncur = 0\nfor x in a:\n    cur = max(x, cur + x)\n    best = max(best, cur)\nprint(best)\n";
const CPP = `#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    cin >> n;
    vector<long long> a(n);
    for (auto &x : a) cin >> x;
    long long result = a[0], running = a[0];
    for (int i = 1; i < n; ++i) {
        running = max(a[i], running + a[i]);
        result = max(result, running);
    }
    cout << result << "\\n";
}
`;
const JAVA = `import java.util.*;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        int n = in.nextInt();
        long[] pre = new long[n + 1];
        for (int i = 1; i <= n; i++) pre[i] = pre[i - 1] + in.nextLong();
        long low = 0, ans = Long.MIN_VALUE;
        for (int r = 1; r <= n; r++) {
            ans = Math.max(ans, pre[r] - low);
            low = Math.min(low, pre[r]);
        }
        System.out.println(ans);
    }
}
`;

// --- teacher creates an any-language competition ---------------------------------
const t = await open();
await t.goto(`${BASE}/#/teach`);
await t.fill("input[type=password]", TOKEN);
await t.click("button[type=submit]");
await t.waitForSelector("text=A lab is one sitting");
await t.click("button:has-text('New competition')");
await t.fill("input[placeholder^='Friday sprint']", `College contest ${TAG}`);
await t.fill("textarea", "Solve in any language you like: C, C++, Java, JavaScript or Python.");
await t.fill("input[type=number]", "45");
await t.selectOption("select[aria-label='Programming language']", "any");
await t.waitForSelector("text=Each student picks C, C++, Java, JavaScript or Python per question");
await shot(t, "01-new-competition");
await t.click("button:has-text('Create and add questions')");
await t.waitForSelector("text=Add the first question");
const labId = (await t.evaluate(() => location.hash)).split("/").at(-1);

await api("POST", `/api/teach/labs/${labId}/questions`, {
  title: "Best streak", prompt: "Read N and then N integers. Print the largest sum of a run of consecutive numbers (at least one).",
  sample_input: "5\n-2 3 -1 4 -9", tests: [
    { name: "sample", stdin: "5\n-2 3 -1 4 -9", expected: "6" }, { name: "all negative", stdin: "3\n-5 -2 -7", expected: "-2" },
    { name: "large", stdin: "4\n1000000000 1000000000 -1 1000000000", expected: "2999999999", hidden: true }],
  variants: {
    python: { starter_code: "n = int(input())\nnums = list(map(int, input().split()))\n", harness: "" },
    c: { starter_code: "#include <stdio.h>\n\nint main(void) {\n    \n    return 0;\n}\n", harness: "" },
    java: { starter_code: "import java.util.*;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner in = new Scanner(System.in);\n    }\n}\n", harness: "" },
  } }, true);
await api("POST", `/api/teach/labs/${labId}/questions`, {
  title: "Echo twice", prompt: "Read a word and print it twice, separated by a space.", sample_input: "hi",
  tests: [{ name: "word", stdin: "hi", expected: "hi hi" }] }, true);
await api("PUT", `/api/teach/labs/${labId}/roster`, { student_ids: [STUDENT, ...CLASS.map((c) => c.id)], everyone: false }, true);
await t.reload();
await t.waitForSelector("text=Best streak");
await t.click("li:has-text('Best streak') button:has-text('Edit')");
await t.click("[role=tab]:has-text('Java')");
await t.waitForSelector("text=Scanner in");
await shot(t, "02-starter-per-language", true);
await t.click("button:has-text('Cancel')");
await api("PATCH", `/api/teach/labs/${labId}`, { status: "open" }, true);
await api("POST", `/api/teach/competitions/${labId}/start`, undefined, true);

// --- the student opens Q1 in Python, switches to C and solves it ---------------------
const s = await open();
await s.goto(BASE);
await s.fill("input", STUDENT);
await s.click("button[type=submit]");
await s.waitForSelector("text=Before you start");
await s.check("input[type=checkbox]");
await s.click("button:text-is(\"Start\")");
await s.click(`button:has-text('College contest ${TAG}')`);
await s.waitForSelector("text=Best streak");
await shot(s, "03-arena");
await s.click("button:has-text('Best streak')");
await s.waitForSelector(".cm-content");
const sel = "select[aria-label='Language for this question']";
assert.equal(await s.inputValue(sel), "python");
await s.waitForSelector("text=nums = list");
await s.selectOption(sel, "c");
await s.waitForSelector("text=main.c");
await s.waitForSelector(".cm-content:has-text('#include')");
await s.click(".cm-content");
await s.keyboard.press("Control+A");
await s.keyboard.insertText(C_SOLUTION);
await s.click("button:has-text('Run')");
await s.waitForSelector("text=Exit 0");
await shot(s, "04-editor-in-c");
await s.selectOption(sel, "python");                    // the Python code is still there ...
await s.waitForSelector(".cm-content:has-text('nums = list')");
await s.selectOption(sel, "c");                         // ... and so is the C
await s.waitForSelector(".cm-content:has-text('long long best')");
await s.click("button:has-text('Submit')");
await s.waitForSelector("text=All tests passed!");
await shot(s, "05-submit-solved");

// --- classmates answer in other languages; one copies the student's C --------------
const submitAs = async (c, lang, code) => {
  await api("POST", "/api/consent", { student_id: c.id });
  await api("POST", `/api/competitions/${labId}/join`, { student_id: c.id, handle: c.handle });
  const q = (await api("GET", `/api/competitions/${labId}?student_id=${c.id}`)).questions[0];
  const { session_id } = await api("POST", "/api/sessions", { student_id: c.id, question_id: q.id, language: lang, client_meta: { synthetic: true } });
  // the copy arrives as one paste, the others are typed
  await api("POST", `/api/sessions/${session_id}/events`, { schema_version: 1, events: [
    { seq: 0, t: 0, type: "edit", data: { changes: [[0, 0, code]], origin: c === CLASS[0] ? "input.paste" : "input.type", len_before: 0, len_after: code.length } }] });
  return api("POST", `/api/sessions/${session_id}/submit`, { code });
};
assert.equal((await submitAs(CLASS[0], "cpp", C_COPY)).passed, 3);
assert.equal((await submitAs(CLASS[1], "python", PY)).passed, 3);
assert.equal((await submitAs(CLASS[2], "cpp", CPP)).passed, 3);
assert.equal((await submitAs(CLASS[3], "java", JAVA)).passed, 3);

// --- teacher: the board with languages, then the similar pair ----------------------
await t.goto(`${BASE}/#/teach/labs/${labId}/board`);
await t.waitForSelector(`text=${CLASS[3].handle}`);
await shot(t, "06-board-languages", true);
await t.goto(`${BASE}/#/teach/labs/${labId}`);
await t.click("a:has-text('Similar submissions')");
await t.waitForSelector("text=Similar submissions worth a look");
await t.waitForSelector(`button:has-text('${CLASS[0].handle}')`);
const pairs = await api("GET", `/api/teach/competitions/${labId}/similarity`, undefined, true);
const q1 = pairs.questions[0].pairs;
assert.equal(q1.length, 1, "only the copy stands out");
assert.deepEqual(new Set([q1[0].a.student_id, q1[0].b.student_id]), new Set([STUDENT, CLASS[0].id]));
await shot(t, "07-similar-list", true);
await t.click(`button:has-text('${CLASS[0].handle}')`);
await t.waitForSelector("text=pasted in 1 paste");
await t.hover("[role=dialog] mark >> nth=0");
await shot(t, "08-similar-pair");

assert.deepEqual(errors, [], "no page errors");
await browser.close();
console.log("any-language e2e ok:", q1.map((p) => [p.a.handle, p.b.handle, p.similarity]));
