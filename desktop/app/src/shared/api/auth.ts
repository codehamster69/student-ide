/**
 * `studentDesktop.auth`: desktop sign-in (owned by the shell thread).
 *
 * Google blocks its sign-in inside embedded browsers, so the desktop app signs in
 * through the system browser: it opens the site's #/desktop/signin page there, the
 * student signs in as on the web and confirms, the page hands a one-time code to a
 * loopback port, and the shell trades it (with a PKCE verifier) for the normal session
 * cookie. In dev mode (roll numbers) none of this is needed: the web screens work as is.
 */

export interface SignInResult {
  email: string;
  role: "student" | "teacher" | "admin";
}

export interface AuthApi {
  /** Opens the system browser and resolves once the app holds a session. Rejects with code "signin_cancelled" or "signin_timeout". */
  signIn(): Promise<SignInResult>;
  signOut(): Promise<void>;
}

export interface AuthEvents {
  "auth.changed": { signedIn: boolean };
}
