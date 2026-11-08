/**
 * Desktop sign-in through the system browser (RFC 8252: loopback redirect + PKCE).
 *
 * 1. The shell makes a verifier, its SHA-256 challenge and a state, and listens on
 *    127.0.0.1:<random port>.
 * 2. It opens <server>/#/desktop/signin?challenge&port&state in the system browser,
 *    where the student signs in exactly as on the web and presses Continue.
 * 3. That page asks the server for a one-time code bound to the challenge
 *    (POST /api/auth/desktop/grant) and sends the browser to 127.0.0.1:<port>/callback.
 * 4. The shell trades code + verifier for a session (POST /api/auth/desktop/exchange)
 *    and puts the session cookie into its own cookie jar.
 * A code is useless without the verifier, which never leaves this process.
 */

import { session, shell } from "electron";
import { createHash, randomBytes } from "node:crypto";
import { createServer, type Server } from "node:http";
import type { SignInResult } from "../shared/contract";
import { fail } from "./ipc";

const b64url = (b: Buffer) => b.toString("base64url");
const TIMEOUT_MS = 5 * 60_000;

const PAGE = (title: string, body: string) => `<!doctype html><meta charset="utf-8"><title>${title}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font:15px/1.5 system-ui,sans-serif;display:grid;place-items:center;min-height:90vh;margin:0;background:#f7f7f8;color:#18181b}
@media (prefers-color-scheme:dark){body{background:#111113;color:#ececef}}main{max-width:26rem;padding:2rem;text-align:center}h1{font-size:1.25rem;margin:0 0 .5rem}</style>
<main><h1>${title}</h1><p>${body}</p></main>`;

let pending: { server: Server; reject: (e: unknown) => void } | null = null;

export async function desktopSignIn(origin: string, onBack: () => void): Promise<SignInResult> {
  pending?.reject({ code: "signin_cancelled", title: "Sign-in was started again." });
  const verifier = b64url(randomBytes(32));
  const challenge = b64url(createHash("sha256").update(verifier).digest());
  const state = b64url(randomBytes(16));

  const code = await new Promise<string>((resolve, reject) => {
    const server = createServer((req, res) => {
      const url = new URL(req.url ?? "/", "http://127.0.0.1");
      if (url.pathname !== "/callback" && url.pathname !== "/cancel") { res.writeHead(404).end(); return; }
      if (url.searchParams.get("state") !== state) { res.writeHead(400).end("state mismatch"); return; }
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" });
      if (url.pathname === "/cancel") {
        res.end(PAGE("Sign-in cancelled", "You can close this tab."));
        finish(() => reject({ code: "signin_cancelled", title: "Sign-in was cancelled in the browser." }));
        return;
      }
      res.end(PAGE("You're signed in", "Go back to the Student IDE app. You can close this tab."));
      const c = url.searchParams.get("code");
      finish(() => (c ? resolve(c) : reject({ code: "signin_failed", title: "The browser did not send a sign-in code." })));
    });
    const timer = setTimeout(() => finish(() => reject({
      code: "signin_timeout", title: "Sign-in took too long.", fix: "Press Sign in again and finish in the browser within 5 minutes.",
    })), TIMEOUT_MS);
    const finish = (then: () => void) => {
      clearTimeout(timer);
      server.close();
      if (pending?.server === server) pending = null;
      then();
    };
    pending = { server, reject: (e) => finish(() => reject(e)) };
    server.on("error", (e) => finish(() => reject({ code: "signin_failed", title: "Could not start sign-in.", detail: String(e) })));
    server.listen(0, "127.0.0.1", () => {
      const port = (server.address() as { port: number }).port;
      const q = new URLSearchParams({ challenge, port: String(port), state });
      shell.openExternal(`${origin}/#/desktop/signin?${q}`).catch((e) =>
        finish(() => reject({ code: "signin_failed", title: "Could not open the browser.", detail: String(e) })));
    });
  }).catch((e) => fail(e));

  onBack();
  const r = await session.defaultSession.fetch(`${origin}/api/auth/desktop/exchange`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, verifier }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) fail({ code: "signin_failed", title: "Sign-in did not go through.", detail: body.detail ?? `HTTP ${r.status}`, fix: "Press Sign in again." });
  await session.defaultSession.cookies.set({
    url: origin, name: body.cookie.name, value: body.cookie.value, path: "/",
    httpOnly: true, secure: origin.startsWith("https:"), sameSite: "lax", expirationDate: body.cookie.expires_at,
  });
  await session.defaultSession.cookies.flushStore();
  return { email: body.me.email, role: body.me.role };
}

export async function desktopSignOut(origin: string) {
  await session.defaultSession.fetch(`${origin}/api/auth/logout`, { method: "POST", credentials: "include" }).catch(() => undefined);
  const jar = session.defaultSession.cookies;
  for (const c of await jar.get({ url: origin })) await jar.remove(origin, c.name);
}
