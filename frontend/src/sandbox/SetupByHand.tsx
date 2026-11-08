// "Set up by hand" (plan §3.4, §5.2): a fresh instance of the subject's
// environment with a terminal. The teacher installs what the subject needs as on
// any Linux machine; the commands they run become the environment's setup script
// (shown and editable), and saving builds a new version from it, reproducibly.
import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, Check, CircleStop, RefreshCw, Save, Terminal } from "lucide-react";
import { Button, Card, Spinner, TextArea, cn } from "../ui";
import { get, send, token } from "../review/api";
import { go, href } from "../routes";
import { PreviewTerminal } from "./bits";
import type { Environment, Preview, SetupLog } from "./api";

export function SetupByHand({ p, onReload, onAuthLost }: { p: Preview; onReload: () => void; onAuthLost: () => void }) {
  const [log, setLog] = useState<SetupLog | null>(null);
  const [script, setScript] = useState("");
  const [touched, setTouched] = useState(false);
  const [env, setEnv] = useState<Environment | null>(null);
  const [msg, setMsg] = useState("");
  const [saved, setSaved] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const running = p.status === "running";

  const refresh = useCallback(async () => {
    if (!running) return;
    try {
      const l = await get<SetupLog>(`/api/sandbox/previews/${p.id}/setup`);
      setLog(l);
      if (!touched) setScript(l.script);
    } catch (e) { if ((e as Error).message.includes("sign")) onAuthLost(); }
  }, [p.id, running, touched, onAuthLost]);
  useEffect(() => { void refresh(); const t = setInterval(refresh, 4000); return () => clearInterval(t); }, [refresh]);
  useEffect(() => { if (p.environment_id) get<Environment>(`/api/sandbox/environments/${p.environment_id}`).then(setEnv, () => {}); }, [p.environment_id]);

  const latest = env?.versions[env.versions.length - 1];
  const saveVersion = async () => {
    if (!env || !latest) return;
    setBusy(true); setMsg("");
    try {
      const old = latest.recipe.setup.trim();
      const setup = [old, script.trim()].filter(Boolean).join("\n");
      await send("POST", `/api/sandbox/environments/${env.id}/versions`, { recipe: { ...latest.recipe, setup } });
      setSaved(latest.version + 1);
      await send("POST", `/api/sandbox/previews/${p.id}/stop`);
      onReload();
    } catch (e) { setMsg((e as Error).message); }
    finally { setBusy(false); }
  };

  const q = new URLSearchParams(token.get() ? { token: token.get() } : {}).toString();
  const wsUrl = `${location.origin}/api/sandbox/previews/${p.id}/terminal${q ? `?${q}` : ""}`;

  return (
    <div className="mx-auto flex h-[calc(100vh-3.5rem)] max-w-[1600px] flex-col gap-3 px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <button onClick={() => history.back()} className="inline-flex items-center gap-1 text-[13px] text-muted hover:text-text"><ArrowLeft className="size-3.5" /> Back</button>
        <h1 className="text-base font-semibold text-text">{p.lab_title}</h1>
        <span className="flex-1" />
        {running && <Button size="sm" onClick={async () => { await send("POST", `/api/sandbox/previews/${p.id}/stop`); onReload(); }}><CircleStop className="size-3.5" /> Stop without saving</Button>}
      </div>

      {saved !== null ? (
        <Card className="grid flex-1 place-items-center p-10 text-center">
          <motion.div initial={{ scale: 0.96, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="grid max-w-md justify-items-center gap-3">
            <span className="grid size-10 place-items-center rounded-full bg-success-soft text-success"><Check className="size-5" /></span>
            <p className="text-sm font-medium text-text">Saved as version {saved}. It is being built now.</p>
            <p className="text-xs text-muted">Every student's machine gets exactly this setup. Labs already published keep their version until you move them.</p>
            <Button variant="primary" onClick={() => history.back()}>Back to the subject</Button>
          </motion.div>
        </Card>
      ) : p.status === "starting" ? (
        <Card className="grid flex-1 place-items-center p-10 text-center">
          <div className="grid justify-items-center gap-3"><Spinner className="size-6 text-accent" />
            <p className="text-sm text-text">Starting a fresh instance…</p>
            <p className="text-xs text-muted">The first start of an environment can take a few minutes while its image is fetched.</p></div>
        </Card>
      ) : !running ? (
        <Card className="grid flex-1 place-items-center p-10 text-center">
          <div className="grid justify-items-center gap-3">
            <p className="text-sm text-text">{p.status === "failed" ? `The instance could not start: ${p.error}` : `This instance stopped (${p.stop_reason ?? "stopped"}). Nothing was saved.`}</p>
            {p.environment_id && <Button variant="primary" onClick={async () => {
              const n = await send<Preview>("POST", "/api/sandbox/previews", { environment_id: p.environment_id });
              go(href.sbxPreview(n.id));
            }}><RefreshCw className="size-4" /> Start again</Button>}
          </div>
        </Card>
      ) : (
        <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[2fr_minmax(300px,1fr)]">
          <div className="grid min-h-0 grid-rows-[auto_1fr] gap-2">
            <ol className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
              {["Install what the subject needs (sudo works, so does apt, pip, npm)", "Try it here", "Check the recipe on the right, then save"].map((s, i) => (
                <li key={s} className="flex items-center gap-1.5"><span className="grid size-4 place-items-center rounded-full bg-accent text-[10px] text-accent-fg">{i + 1}</span>{s}</li>
              ))}
            </ol>
            <PreviewTerminal url={wsUrl} />
          </div>
          <Card className="flex min-h-0 flex-col gap-3 p-4">
            <div className="flex items-center gap-2">
              <Terminal className="size-4 text-accent" />
              <h2 className="flex-1 text-sm font-semibold text-text">Your recipe</h2>
              <button onClick={() => { setTouched(false); void refresh(); }} className="text-xs text-muted hover:text-text" title="Take the commands from the terminal again">
                <RefreshCw className="inline size-3" /> {touched ? "Reset to terminal" : "Live"}
              </button>
            </div>
            <p className="text-xs text-muted">Commands that change the machine, in order. Look-around commands (ls, cat, --version) are left out; sudo is dropped and apt gets -y, because the build runs as root without questions.</p>
            <TextArea value={script} onChange={(e) => { setScript(e.target.value); setTouched(true); }} rows={10}
              placeholder="Nothing yet. Try: sudo apt install -y postgresql" className="min-h-40 flex-1 font-mono text-xs" />
            <AnimatePresence>
              {log && log.dropped.length > 0 && (
                <motion.details initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-xs text-muted">
                  <summary className="cursor-pointer">{log.dropped.length} command{log.dropped.length === 1 ? "" : "s"} left out</summary>
                  <pre className="mt-1 max-h-28 overflow-auto rounded-md bg-surface-2 p-2 font-mono text-[11px]">{log.dropped.join("\n")}</pre>
                </motion.details>
              )}
            </AnimatePresence>
            <p className="text-xs text-muted">Files edited in vim or nano are not captured: write them with <code className="font-mono">tee</code> or <code className="font-mono">cat &gt; file</code> so they land in the recipe.</p>
            {msg && <p className="text-sm text-danger">{msg}</p>}
            <Button variant="primary" disabled={busy || !script.trim() || !latest} onClick={saveVersion} className={cn(!script.trim() && "opacity-60")}>
              {busy ? <Spinner /> : <Save className="size-4" />} Save as environment{latest ? ` v${latest.version + 1}` : ""}
            </Button>
          </Card>
        </div>
      )}
    </div>
  );
}
