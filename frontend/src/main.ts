import { basicSetup } from "codemirror";
import { python } from "@codemirror/lang-python";
import { EditorView, keymap } from "@codemirror/view";
import { Prec } from "@codemirror/state";
import { indentUnit } from "@codemirror/language";
import { indentWithTab } from "@codemirror/commands";
import { Recorder, SCHEMA_VERSION } from "./recorder";
import { captureExtension, captureWindow, SNAPSHOT_EVERY_MS } from "./capture";
import "./style.css";

interface Task {
  id: string;
  title: string;
  prompt: string;
  starter_code: string;
  sample_input: string;
}

const app = document.getElementById("app")!;

async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, body === undefined ? undefined : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `request failed (${res.status})`);
  }
  return res.json();
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, props: Record<string, unknown> = {}, ...kids: (Node | string)[]): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  Object.assign(node, props);
  node.append(...kids);
  return node;
}

function show(...kids: Node[]) {
  app.replaceChildren(el("main", { className: "card" }, ...kids));
}

// --- login ----------------------------------------------------------------

function showLogin(error = "") {
  const input = el("input", { placeholder: "e.g. PG25CS07", autocomplete: "off", required: true, maxLength: 32 });
  const form = el("form", {},
    el("label", {}, "Roll number", input),
    el("button", { type: "submit" }, "Continue"),
    el("p", { className: "error" }, error),
  );
  form.onsubmit = async (e) => {
    e.preventDefault();
    try {
      const r = await api<{ student_id: string; consented: boolean }>("/api/login", { student_id: input.value });
      r.consented ? showTasks(r.student_id) : showConsent(r.student_id);
    } catch (err) {
      showLogin((err as Error).message);
    }
  };
  show(el("h1", {}, "Student IDE"), el("p", { className: "muted" }, "Lab code editor"), form);
  input.focus();
}

// --- consent --------------------------------------------------------------

function showConsent(studentId: string) {
  const box = el("input", { type: "checkbox" });
  const go = el("button", { disabled: true }, "Start");
  box.onchange = () => (go.disabled = !box.checked);
  go.onclick = async () => {
    await api("/api/consent", { student_id: studentId });
    showTasks(studentId);
  };
  show(
    el("h1", {}, "Before you start"),
    el("p", {}, "This editor is part of a research study on how people write code. While you work it records:"),
    el("ul", {},
      el("li", {}, "when each key is pressed and released (timing, and which key)"),
      el("li", {}, "every edit to your code, and anything you paste, copy or cut in the editor"),
      el("li", {}, "each time you run your program, with its output"),
      el("li", {}, "when you switch away from the editor or this tab"),
    ),
    el("p", {}, "It does not use your webcam or microphone and does not record your screen or other apps."),
    el("p", {}, "Your typing patterns are compared only with your own earlier sessions. If something looks unusual, the only consequence is a conversation with your instructor, never an automatic penalty. Raw keystroke data is deleted once summary statistics have been computed."),
    el("label", { className: "check" }, box, "I have read this and agree to take part."),
    go,
  );
}

// --- task picker ----------------------------------------------------------

async function showTasks(studentId: string) {
  const tasks = await api<Task[]>("/api/tasks");
  const list = el("div", { className: "tasks" });
  for (const t of tasks) {
    const b = el("button", { className: "task" }, el("strong", {}, t.title), el("span", {}, t.prompt));
    b.onclick = () => void startSession(studentId, t);
    list.append(b);
  }
  show(el("h1", {}, "Choose a task"), el("p", { className: "muted" }, `Signed in as ${studentId}`), list);
}

// --- editor session -------------------------------------------------------

async function startSession(studentId: string, task: Task) {
  const meta = {
    user_agent: navigator.userAgent,
    language: navigator.language,
    platform: (navigator as any).userAgentData?.platform ?? navigator.platform,
    screen: { w: window.screen.width, h: window.screen.height, dpr: devicePixelRatio },
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    client_schema_version: SCHEMA_VERSION,
  };
  const { session_id } = await api<{ session_id: string }>("/api/sessions", {
    student_id: studentId, task_id: task.id, client_meta: meta,
  });
  const rec = new Recorder(session_id);
  (window as any).__studentide = { rec, sessionId: session_id }; // for end-to-end tests
  rec.log("session_start", { wall_clock_ms: Date.now() });

  const status = el("span", { className: "status" }, "● recording");
  rec.onStatus = (pending, ok) => {
    status.textContent = ok ? "● recording" : `● offline, ${pending} events waiting`;
    status.classList.toggle("warn", !ok);
  };
  const runBtn = el("button", { className: "primary" }, "Run ▶");
  const doneBtn = el("button", {}, "Finish");
  const stdin = el("textarea", { value: task.sample_input, rows: 3, spellcheck: false });
  const output = el("pre", { className: "output" });
  const editorHost = el("div", { className: "editor" });

  app.replaceChildren(
    el("div", { className: "ide" },
      el("header", {}, el("strong", {}, task.title), el("span", { className: "muted" }, studentId), status, runBtn, doneBtn),
      el("aside", {}, el("h2", {}, "Task"), el("p", {}, task.prompt)),
      editorHost,
      el("section", { className: "io" },
        el("label", {}, "Input", stdin),
        el("div", {}, el("span", { className: "label" }, "Output"), output),
      ),
    ),
  );

  let running = false;
  let lastSnapshot = task.starter_code;
  const runCode = async () => {
    if (running) return;
    running = true;
    runBtn.disabled = true;
    const code = view.state.doc.toString();
    rec.log("snapshot", { reason: "run", text: code });
    lastSnapshot = code;
    output.textContent = "Running…";
    output.className = "output";
    try {
      const r = await api<any>(`/api/sessions/${session_id}/run`, { code, stdin: stdin.value });
      rec.log("run", {
        run_id: r.run_id, code_sha256: r.code_sha256, exit_code: r.exit_code,
        duration_ms: r.duration_ms, error_type: r.error_type,
      });
      output.textContent = r.stdout + (r.stderr ? (r.stdout ? "\n" : "") + r.stderr : "") || "(no output)";
      output.classList.toggle("failed", r.error_type !== null);
    } catch (err) {
      output.textContent = `Could not run: ${(err as Error).message}`;
      output.classList.add("failed");
    } finally {
      running = false;
      runBtn.disabled = false;
    }
  };

  const view = new EditorView({
    doc: task.starter_code,
    parent: editorHost,
    extensions: [
      basicSetup,
      python(),
      indentUnit.of("    "),
      keymap.of([indentWithTab]),
      captureExtension(rec),
      Prec.highest(keymap.of([{ key: "Mod-Enter", run: () => (void runCode(), true) }])),
    ],
  });
  rec.log("snapshot", { reason: "start", text: view.state.doc.toString() });
  const snapTimer = window.setInterval(() => {
    const text = view.state.doc.toString();
    if (text !== lastSnapshot) {
      rec.log("snapshot", { reason: "periodic", text });
      lastSnapshot = text;
    }
  }, SNAPSHOT_EVERY_MS);
  const stopWindow = captureWindow(rec);

  const finish = (reason: string) => {
    window.clearInterval(snapTimer);
    stopWindow();
    rec.log("snapshot", { reason: "end", text: view.state.doc.toString() });
    rec.log("session_end", { wall_clock_ms: Date.now(), reason });
  };
  const onHide = () => { finish("pagehide"); rec.beacon(); };
  window.addEventListener("pagehide", onHide, { once: true });

  runBtn.onclick = () => void runCode();
  doneBtn.onclick = async () => {
    if (!confirm("Finish this session? You will not be able to edit it afterwards.")) return;
    window.removeEventListener("pagehide", onHide);
    finish("submit");
    doneBtn.disabled = runBtn.disabled = true;
    await rec.close();
    view.destroy();
    show(el("h1", {}, "Session saved"), el("p", {}, "Thank you. You can close this tab or start another task."),
      Object.assign(el("button", {}, "Another task"), { onclick: () => showTasks(studentId) }));
  };
  view.focus();
}

showLogin();
