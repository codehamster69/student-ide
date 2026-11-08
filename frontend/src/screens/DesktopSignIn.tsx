// #/desktop/signin, opened by the desktop app in the system browser (docs/desktop.md).
// The student signs in here as on the web, confirms, and this page hands a one-time
// code to the app's loopback port. The code only works with the app's secret verifier.

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { CheckCircle2, Laptop } from "lucide-react";
import { api } from "../api";
import { authConfig, currentUser, signOut, type AuthConfig, type Me } from "../auth";
import { Button, Card, Logo, Spinner, item, stagger } from "../ui";
import { GoogleSignIn } from "./GoogleSignIn";

type Params = { challenge: string; port: number; state: string };

function params(): Params | null {
  const q = new URLSearchParams(location.hash.split("?")[1] ?? "");
  const challenge = q.get("challenge") ?? "", state = q.get("state") ?? "", port = Number(q.get("port"));
  if (!/^[A-Za-z0-9_-]{43,128}$/.test(challenge) || !/^[A-Za-z0-9_-]{8,64}$/.test(state)) return null;
  if (!Number.isInteger(port) || port < 1024 || port > 65535) return null;
  return { challenge, port, state };
}

const loopback = (p: Params, path: "callback" | "cancel", extra: Record<string, string> = {}) =>
  `http://127.0.0.1:${p.port}/${path}?${new URLSearchParams({ state: p.state, ...extra })}`;

export function DesktopSignIn() {
  const [p] = useState(params);
  const [cfg, setCfg] = useState<AuthConfig | null>(null);
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const [phase, setPhase] = useState<"ask" | "sending" | "done">("ask");
  const [error, setError] = useState("");

  useEffect(() => { authConfig().then(setCfg); currentUser().then(setMe); }, []);

  const go = async () => {
    setPhase("sending");
    setError("");
    try {
      const { code } = await api<{ code: string }>("/api/auth/desktop/grant", { challenge: p!.challenge });
      location.href = loopback(p!, "callback", { code });
      setPhase("done");
    } catch (err) {
      setError((err as Error).message);
      setPhase("ask");
    }
  };

  let body;
  if (!p) {
    body = <p className="text-sm text-muted">This sign-in link is incomplete. Press <b>Sign in with your browser</b> in the Student IDE app again.</p>;
  } else if (!cfg || me === undefined) {
    body = <div className="grid place-items-center py-6"><Spinner /></div>;
  } else if (cfg.mode !== "google") {
    body = <p className="text-sm text-muted">This server uses roll-number sign-in; sign in inside the app itself.</p>;
  } else if (!me) {
    body = (<>
      <p className="mb-6 text-sm text-muted">Sign in with your college Google account (<span className="font-mono text-xs">@{cfg.domain}</span>) to connect the app.</p>
      <GoogleSignIn cfg={cfg} onDone={setMe} />
    </>);
  } else if (phase === "done") {
    body = (
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="grid justify-items-center gap-2 py-2 text-center">
        <CheckCircle2 className="size-8 text-success" />
        <p className="font-medium text-text">Signed in. Go back to the Student IDE app.</p>
        <p className="text-sm text-muted">You can close this tab.</p>
      </motion.div>
    );
  } else {
    body = (<>
      <div className="mb-6 flex items-center gap-3 rounded-xl bg-surface-2 p-3">
        <span className="grid size-9 place-items-center rounded-lg bg-accent-soft text-accent"><Laptop className="size-4" /></span>
        <div className="min-w-0 text-sm">
          <p className="truncate font-medium text-text">{me.name || me.email}</p>
          <p className="truncate text-muted">{me.email}</p>
        </div>
      </div>
      <div className="grid gap-2">
        <Button variant="primary" size="lg" onClick={go} disabled={phase === "sending"} className="w-full">
          {phase === "sending" && <Spinner />} Continue to the app
        </Button>
        <div className="flex justify-between">
          <Button variant="ghost" size="sm" onClick={async () => { await signOut(); setMe(null); }}>Not you?</Button>
          <Button variant="ghost" size="sm" onClick={() => { location.href = loopback(p, "cancel"); }}>Cancel</Button>
        </div>
      </div>
      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{error}</p>}
    </>);
  }

  return (
    <main className="grid min-h-screen place-items-center bg-bg px-4 py-10">
      <motion.div variants={stagger(0.06)} initial="initial" animate="animate" className="grid w-full max-w-md gap-6">
        <motion.div variants={item} className="justify-self-center"><Logo /></motion.div>
        <Card variants={item} className="p-8">
          <h1 className="text-xl font-semibold tracking-tight text-text">Sign in to the Student IDE app</h1>
          <p className="mb-6 mt-1 text-sm text-muted">The desktop app on this computer asked to sign in.</p>
          {body}
        </Card>
      </motion.div>
    </main>
  );
}
