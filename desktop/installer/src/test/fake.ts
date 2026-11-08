/**
 * A scripted fake machine for tests: each rule matches a command line by
 * regex and returns an exit code and output. Records every call.
 */
import type { Host } from '../host';
import type { RunResult } from '../exec';

export type Rule = [RegExp, Partial<RunResult> | ((line: string) => Partial<RunResult>)];

export function fakeHost(over: Partial<Host> & { rules: Rule[]; files?: Record<string, string> }) {
  const calls: string[] = [];
  const files: Record<string, string> = { ...(over.files ?? {}) };
  const host: Host = {
    platform: 'linux',
    release: '6.8.0',
    arch: 'x64',
    totalMemBytes: 16 * 1024 ** 3,
    freeDiskBytes: async () => 100 * 1024 ** 3,
    dataDir: '/data',
    assetsDir: '/assets',
    appExe: 'C:\\Program Files\\Student IDE\\Student IDE.exe',
    env: { XDG_RUNTIME_DIR: '/run/user/1000' },
    exists: (p) => p in files || p.startsWith('/assets/'),
    writeFile: (p, d) => {
      files[p] = d;
    },
    readFile: (p) => files[p],
    ...over,
    run: async (cmd, args) => {
      const line = [cmd, ...args].join(' ');
      calls.push(line);
      for (const [re, res] of over.rules) {
        if (re.test(line)) {
          const r = typeof res === 'function' ? res(line) : res;
          return { code: 0, stdout: '', stderr: '', ...r };
        }
      }
      return { code: 127, stdout: '', stderr: `not scripted: ${line}` };
    },
  };
  return { host, calls, files };
}
