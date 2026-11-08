// Sign-in. On a real deployment students and teachers sign in with their
// college Google account (Google Identity Services gives the browser an ID
// token, the server checks it and sets an HttpOnly cookie). Without a Google
// client id the server runs in dev mode: roll number for students, admin
// token for teachers.

export type LiveMode = "off" | "class" | "editor";

export interface AuthConfig {
  mode: "google" | "dev";
  client_id: string | null;
  domain: string;
  /** what teachers may watch live during a lab ($STUDENTIDE_LIVE) */
  live?: LiveMode;
}

export interface Me {
  email: string;
  name: string;
  role: "student" | "teacher" | "admin";
  student_id: string;
  program: string | null;
  year: number | null;
  branch: string | null;
  roll: string | null;
  consented: boolean;
  /** consent v3 (Sandbox Labs: terminal, file changes, offline journal) */
  sandbox_consented?: boolean;
}

let config: Promise<AuthConfig> | null = null;

export function authConfig(): Promise<AuthConfig> {
  config ??= fetch("/api/auth/config")
    .then((r) => (r.ok ? r.json() : { mode: "dev", client_id: null, domain: "" }))
    .catch(() => ({ mode: "dev", client_id: null, domain: "" }));
  return config;
}

/** The signed-in account, or null. */
export async function currentUser(): Promise<Me | null> {
  const r = await fetch("/api/me");
  return r.ok ? r.json() : null;
}

export async function signInWithGoogle(credential: string): Promise<Me> {
  const r = await fetch("/api/auth/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail ?? `sign-in failed (${r.status})`);
  return body;
}

export async function signOut(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined);
  window.google?.accounts.id.disableAutoSelect();
}

// -- Google Identity Services

interface GsiButtonOptions { theme?: string; size?: string; text?: string; shape?: string; width?: number; logo_alignment?: string }

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize(o: { client_id: string; callback: (r: { credential: string }) => void; hd?: string;
            ux_mode?: "popup"; auto_select?: boolean; use_fedcm_for_prompt?: boolean }): void;
          renderButton(el: HTMLElement, o: GsiButtonOptions): void;
          disableAutoSelect(): void;
        };
      };
    };
  }
}

let gsi: Promise<void> | null = null;

export function loadGoogle(): Promise<void> {
  gsi ??= new Promise((resolve, reject) => {
    if (window.google?.accounts) return resolve();
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => { gsi = null; reject(new Error("could not reach Google sign-in; check the network")); };
    document.head.appendChild(s);
  });
  return gsi;
}

/** Draws Google's own button into `el`; `onCredential` gets the ID token. */
export async function renderGoogleButton(el: HTMLElement, cfg: AuthConfig, onCredential: (credential: string) => void) {
  await loadGoogle();
  const id = window.google!.accounts.id;
  // `hd` only pre-selects the college account in Google's chooser; the server enforces the domain.
  id.initialize({ client_id: cfg.client_id!, callback: (r) => onCredential(r.credential), hd: cfg.domain, ux_mode: "popup" });
  el.replaceChildren();
  id.renderButton(el, { theme: "outline", size: "large", text: "signin_with", shape: "pill", width: 320, logo_alignment: "left" });
}
