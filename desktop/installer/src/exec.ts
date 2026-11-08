/**
 * Runs external commands (wsl.exe, limactl, podman, pkexec...). Never throws
 * for a non-zero exit: setup decides what each exit means. Swappable so tests
 * can script the outputs of every tool without a real Windows or Mac.
 */
import { spawn } from 'node:child_process';

export interface RunResult {
  code: number;
  stdout: string;
  stderr: string;
}

export interface RunOptions {
  env?: Record<string, string>;
  timeoutMs?: number;
  /** Called with each chunk of stdout+stderr, for progress. */
  onOutput?: (chunk: string) => void;
}

export type Runner = (cmd: string, args: string[], opts?: RunOptions) => Promise<RunResult>;

export const run: Runner = (cmd, args, opts = {}) =>
  new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    let settled = false;
    const done = (r: RunResult) => {
      if (!settled) {
        settled = true;
        resolve(r);
      }
    };
    let child;
    try {
      child = spawn(cmd, args, {
        env: { ...process.env, ...opts.env },
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (e) {
      return done({ code: 127, stdout: '', stderr: String(e) });
    }
    const timer = opts.timeoutMs
      ? setTimeout(() => {
          child.kill();
          done({ code: 124, stdout, stderr: stderr + `\n(timed out after ${opts.timeoutMs} ms)` });
        }, opts.timeoutMs)
      : undefined;
    // wsl.exe writes UTF-16LE unless WSL_UTF8=1; strip NULs in case an old build ignores it.
    const clean = (b: Buffer) => b.toString('utf8').replace(/\u0000/g, '');
    child.stdout.on('data', (b: Buffer) => {
      const s = clean(b);
      stdout += s;
      opts.onOutput?.(s);
    });
    child.stderr.on('data', (b: Buffer) => {
      const s = clean(b);
      stderr += s;
      opts.onOutput?.(s);
    });
    child.on('error', (e: NodeJS.ErrnoException) =>
      done({ code: e.code === 'ENOENT' ? 127 : 1, stdout, stderr: stderr + String(e) }),
    );
    child.on('close', (code) => {
      if (timer) clearTimeout(timer);
      done({ code: code ?? 1, stdout, stderr });
    });
  });

export const logOf = (r: RunResult) => `${r.stdout}\n${r.stderr}`.trim();
