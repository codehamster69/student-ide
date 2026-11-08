/**
 * Files the runtime writes into every instance (as root, on each start).
 *
 * Nothing here has to be baked into an image, so environments built from a
 * raw Dockerfile get the same terminal monitoring. The student has sudo and
 * can remove all of it; that is expected (plan section 4.2): key timing is
 * captured in the app, and silent hooks are themselves visible in the review.
 *
 * Marks: the shell writes OSC 6973 sequences into the terminal stream, which
 * the client parses and strips before xterm.js sees them:
 *   ESC ] 6973 ; start ; <n> ; <b64 command> ; <b64 cwd> BEL   a command line begins
 *   ESC ] 6973 ; end ; <exit code> BEL                         the prompt is back
 */

export const HOOK_DIR = "/etc/studentide";
export const RCFILE = `${HOOK_DIR}/bashrc`;
export const HOOK_VERSION = 1;

export const BASHRC = `# Student IDE terminal hooks v${HOOK_VERSION}. Written by the app on every start.
[ -f /etc/bash.bashrc ] && . /etc/bash.bashrc
[ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"
case $- in *i*) ;; *) return ;; esac
# every command line has to reach history for the start mark
HISTCONTROL=
HISTIGNORE=
[ -n "$SID_TERM" ] && tty > "/tmp/.sid-tty-$SID_TERM" 2>/dev/null
__sid_b64() { printf '%s' "$1" | base64 | tr -d '\\n'; }
__sid_pre() {
  local line n c
  line=$(HISTTIMEFORMAT= builtin history 1)
  n=\${line%%[^0-9 ]*}; n=\${n// /}
  c=\${line#*[0-9]  }
  printf '\\033]6973;start;%s;%s;%s\\007' "$n" "$(__sid_b64 "$c")" "$(__sid_b64 "$PWD")"
}
__sid_post() { printf '\\033]6973;end;%s\\007' "$1"; }
PS0='$(__sid_pre)'"\${PS0-}"
PROMPT_COMMAND='__sid_post $?'"\${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
`;

/** Shell script (run as root) that installs the hooks; idempotent. */
export function installScript(): string {
  const b64 = Buffer.from(BASHRC, "utf8").toString("base64");
  return [
    "set -e",
    `mkdir -p ${HOOK_DIR}`,
    `printf '%s' '${b64}' | base64 -d > ${RCFILE}`,
    `chmod 644 ${RCFILE}`,
    `echo ${HOOK_VERSION} > ${HOOK_DIR}/version`,
  ].join("\n");
}

/** Command that starts the shell of one terminal inside a PTY made in the container. */
export function terminalCommand(termId: string, cols: number, rows: number): string[] {
  const c = Math.max(10, Math.floor(cols));
  const r = Math.max(2, Math.floor(rows));
  // util-linux `script` gives bash a real PTY although our stdin is a pipe
  const inner = `stty rows ${r} cols ${c} 2>/dev/null; exec bash --rcfile ${RCFILE} -i`;
  return ["env", `SID_TERM=${termId}`, "TERM=xterm-256color", "script", "-qfec", inner, "/dev/null"];
}

/** Command that resizes a terminal's PTY (the kernel then sends SIGWINCH). */
export function resizeCommand(termId: string, cols: number, rows: number): string[] {
  const c = Math.max(10, Math.floor(cols));
  const r = Math.max(2, Math.floor(rows));
  return ["sh", "-c", `t=$(cat /tmp/.sid-tty-${termId} 2>/dev/null) && stty -F "$t" rows ${r} cols ${c}`];
}
