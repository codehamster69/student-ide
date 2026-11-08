#!/usr/bin/env node
/**
 * studentide-setup: the same setup from a terminal, for IT and for CI smoke
 * runs. Prints progress lines (or JSON lines with --json); exit 0 = ready,
 * 2 = restart needed, 3 = admin needed, 1 = any other failure.
 *
 *   studentide-setup --data-dir DIR [--assets DIR] [--images images.json] [--silent] [--existing] [--json]
 */
import path from 'node:path';
import os from 'node:os';
import { runSetup } from './setup';
import { SetupError } from './errors';
import { loadImageList } from './images';

function arg(name: string): string | undefined {
  const i = process.argv.indexOf(name);
  return i > 0 ? process.argv[i + 1] : undefined;
}
const flag = (name: string) => process.argv.includes(name);

async function main() {
  const json = flag('--json');
  const dataDir = arg('--data-dir') ?? path.join(os.homedir(), '.studentide');
  const images = arg('--images') ? loadImageList(arg('--images')!) : [];
  try {
    const res = await runSetup({
      dataDir,
      assetsDir: arg('--assets') ?? path.join(__dirname, '..', 'assets'),
      images,
      silent: flag('--silent'),
      prefer: flag('--existing') ? 'existing' : 'bundled',
      onProgress: (p) => console.log(json ? JSON.stringify({ progress: p }) : `[${p.step}] ${p.percent}% ${p.message}`),
    });
    console.log(json ? JSON.stringify({ ok: true, ...res }) : `Ready: ${res.engine.kind} ${res.engine.version}\n${res.warnings.join('\n')}`);
    return 0;
  } catch (e) {
    if (!(e instanceof SetupError)) throw e;
    console.log(json ? JSON.stringify({ ok: false, error: e.toJSON() }) : `${e.title}\n${e.detail}\nWhat to do: ${e.fix}`);
    if (!json && e.log) console.error(`\nDetails:\n${e.log}`);
    return e.needsReboot ? 2 : e.needsAdmin ? 3 : 1;
  }
}

main().then((code) => process.exit(code));
