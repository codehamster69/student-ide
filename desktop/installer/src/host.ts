/**
 * Everything setup needs to know about the machine, gathered in one object so
 * the per-OS steps stay pure and tests can fake a Windows, Mac or Linux PC.
 */
import os from 'node:os';
import fs from 'node:fs';
import path from 'node:path';
import { run as realRun, Runner } from './exec';

export interface Host {
  platform: NodeJS.Platform;
  /** os.release(): "10.0.22631" on Windows, Darwin kernel on macOS. */
  release: string;
  arch: string;
  totalMemBytes: number;
  /** Free bytes on the disk holding dataDir. */
  freeDiskBytes: () => Promise<number>;
  run: Runner;
  /** App's userData folder; engine.json and the engine's disk live under it. */
  dataDir: string;
  /** Folder with bundled assets (Lima, WSL rootfs, podman-static); process.resourcesPath/installer when packaged. */
  assetsDir: string;
  /** Path of the app executable, used to resume setup after a reboot. */
  appExe: string;
  env: NodeJS.ProcessEnv;
  exists: (p: string) => boolean;
  writeFile: (p: string, data: string) => void;
  readFile: (p: string) => string | undefined;
}

export function realHost(dataDir: string, assetsDir: string, appExe = process.execPath): Host {
  return {
    platform: process.platform,
    release: os.release(),
    arch: process.arch,
    totalMemBytes: os.totalmem(),
    freeDiskBytes: async () => {
      fs.mkdirSync(dataDir, { recursive: true });
      const s = await fs.promises.statfs(dataDir);
      return s.bavail * s.bsize;
    },
    run: realRun,
    dataDir,
    assetsDir,
    appExe,
    env: process.env,
    exists: (p) => fs.existsSync(p),
    writeFile: (p, data) => {
      fs.mkdirSync(path.dirname(p), { recursive: true });
      fs.writeFileSync(p, data);
    },
    readFile: (p) => {
      try {
        return fs.readFileSync(p, 'utf8');
      } catch {
        return undefined;
      }
    },
  };
}
