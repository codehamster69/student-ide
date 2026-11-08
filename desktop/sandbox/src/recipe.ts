/**
 * The student's setup recipe: every package command that succeeded, in order.
 *
 * Installed packages are too big to sync between machines, so the app keeps
 * the commands that installed (or removed) them and replays them on a new
 * machine or after "Reset instance" (plan section 3.5). The student can see
 * and edit the list. Commands are stored as typed, so replay does exactly
 * what the student did, including flags like --break-system-packages.
 */

export interface PkgCommand {
  manager: string;
  action: "install" | "remove";
  packages: string[];
}

export interface RecipeStep extends PkgCommand {
  command: string;
  cwd: string;
  at: number; // unix ms
}

export interface Recipe {
  version: 1;
  steps: RecipeStep[];
}

export const emptyRecipe = (): Recipe => ({ version: 1, steps: [] });

const strip = (words: string[]): string[] => {
  let i = 0;
  while (i < words.length && (words[i] === "sudo" || /^[A-Za-z_]+=/.test(words[i]!) || words[i] === "-E")) i++;
  return words.slice(i);
};

const pkgs = (args: string[]): string[] => args.filter((a) => !a.startsWith("-") && a !== "&&");

/** Parse one simple command (no pipes); null when it is not a package command. */
export function parsePkgCommand(command: string): PkgCommand | null {
  // only the first command of a chain like "apt update && apt install x" is not enough; take each part
  const words = strip(command.trim().split(/\s+/));
  const [tool, sub, ...rest] = words;
  if (!tool) return null;
  const name = tool.split("/").pop()!;
  const act = (s: string | undefined, inst: string[], rem: string[]): "install" | "remove" | null =>
    s && inst.includes(s) ? "install" : s && rem.includes(s) ? "remove" : null;

  if (name === "apt" || name === "apt-get" || name === "aptitude") {
    const a = act(sub, ["install"], ["remove", "purge", "autoremove"]);
    const p = pkgs(rest);
    return a && (p.length || a === "remove") ? { manager: "apt", action: a, packages: p } : null;
  }
  if (/^pip(3(\.\d+)?)?$/.test(name) || ((name === "python3" || name === "python") && sub === "-m" && /^pip/.test(rest[0] ?? ""))) {
    const args = name.startsWith("pip") ? [sub, ...rest] : rest.slice(1);
    const a = act(args[0], ["install"], ["uninstall"]);
    if (!a) return null;
    const rest2 = args.slice(1) as string[];
    const p = pkgs(rest2.filter((_, i) => !["-r", "--requirement", "-c", "--constraint"].includes(rest2[i - 1] ?? "")));
    // "pip install -r requirements.txt" depends on a lab file: keep it as a step, packages unknown
    return { manager: "pip", action: a, packages: p };
  }
  if (name === "npm" || name === "pnpm" || name === "yarn") {
    const a = act(sub, ["install", "i", "add"], ["uninstall", "remove", "rm"]);
    // only global installs change the instance; local ones live in the lab folder (synced)
    if (!a || !rest.some((x) => x === "-g" || x === "--global" || x === "global")) return null;
    return { manager: "npm", action: a, packages: pkgs(rest).filter((x) => x !== "global") };
  }
  if (name === "cargo" && sub === "install") return { manager: "cargo", action: "install", packages: pkgs(rest) };
  if (name === "go" && sub === "install") return { manager: "go", action: "install", packages: pkgs(rest) };
  if ((name === "conda" || name === "mamba") && (sub === "install" || sub === "remove")) {
    return { manager: "conda", action: sub === "install" ? "install" : "remove", packages: pkgs(rest) };
  }
  if (name === "gem" && (sub === "install" || sub === "uninstall")) {
    return { manager: "gem", action: sub === "install" ? "install" : "remove", packages: pkgs(rest) };
  }
  return null;
}

/** All package commands in a command line ("apt update && apt install -y gcc; pip install x"). */
export function parseCommandLine(line: string): PkgCommand[] {
  return line
    .split(/&&|\|\||;/)
    .map((part) => parsePkgCommand(part))
    .filter((p): p is PkgCommand => p !== null);
}

/** Add a successful command line to the recipe; returns the parsed package commands. */
export function record(recipe: Recipe, command: string, cwd: string, at = Date.now()): PkgCommand[] {
  const found = parseCommandLine(command);
  if (found.length) {
    const first = found[0]!;
    recipe.steps.push({ ...first, packages: found.flatMap((f) => f.packages), command, cwd, at });
    if (recipe.steps.length > 500) recipe.steps.splice(0, recipe.steps.length - 500);
  }
  return found;
}

/** Shell script that replays the recipe, non-interactively, stopping at nothing. */
export function replayScript(recipe: Recipe): string {
  const lines = ["export DEBIAN_FRONTEND=noninteractive", "n=0; ok=0"];
  for (const s of recipe.steps) {
    // apt prompts; answer yes the way the student did
    let cmd = s.command;
    if (s.manager === "apt" && !/\s-y\b|--yes|--assume-yes/.test(cmd)) cmd = cmd.replace(/\b(apt(-get)?)\s+(install|remove|purge)\b/g, "$1 $3 -y");
    lines.push(`n=$((n+1)); echo "[setup] $n: ${s.manager} ${s.action} ${s.packages.join(" ").replace(/["`$\\]/g, "")}"`);
    lines.push(`(cd ${shq(s.cwd)} 2>/dev/null || cd ~; ${cmd}) </dev/null && ok=$((ok+1))`);
  }
  lines.push('echo "[setup] done $ok/$n"');
  return lines.join("\n");
}

export const shq = (s: string): string => `'${s.replace(/'/g, `'\\''`)}'`;
