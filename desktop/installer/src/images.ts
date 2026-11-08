/**
 * Pull lab images into the engine, skipping ones already present, and the
 * minimal built-in setup check used until desktop/sandbox's doctor is wired in.
 */
import fs from 'node:fs';
import { errors } from './errors';
import { logOf } from './exec';
import type { Host } from './host';
import type { CheckItem, CheckResult, EngineInfo, ImageRef } from './types';

export function engineRun(host: Host, engine: EngineInfo, args: string[], timeoutMs = 120_000) {
  const env = { ...engine.env, ...(engine.dockerHost && engine.kind === 'docker' ? { DOCKER_HOST: engine.dockerHost } : {}) };
  return host.run(engine.cli[0], [...engine.cli.slice(1), ...args], { env, timeoutMs });
}

/** Reads images.json ({ images: [{ ref, subject? }] }); a missing file is an empty list. */
export function loadImageList(file: string): ImageRef[] {
  try {
    const data = JSON.parse(fs.readFileSync(file, 'utf8')) as { images?: ImageRef[] };
    return (data.images ?? []).filter((i) => typeof i.ref === 'string' && i.ref);
  } catch {
    return [];
  }
}

export async function pullImages(
  host: Host,
  engine: EngineInfo,
  images: ImageRef[],
  say: (pct: number, msg: string) => void,
): Promise<void> {
  const unique = [...new Map(images.map((i) => [i.ref, i])).values()];
  for (const [n, img] of unique.entries()) {
    const label = img.subject ? `${img.subject} (${n + 1} of ${unique.length})` : `lab ${n + 1} of ${unique.length}`;
    say(Math.round((n / unique.length) * 100), `Downloading ${label}`);
    if ((await engineRun(host, engine, ['image', 'inspect', img.ref])).code === 0) continue;
    let r = await engineRun(host, engine, ['pull', img.ref], 30 * 60_000);
    if (r.code !== 0) r = await engineRun(host, engine, ['pull', img.ref], 30 * 60_000); // one retry: flaky campus Wi-Fi
    if (r.code !== 0) throw errors.imagePullFailed(img.ref, logOf(r));
  }
  say(100, unique.length ? 'Labs downloaded' : 'No labs to download yet');
}

/** Same signature as desktop/sandbox's setupCheck; a subset of its checks. */
export async function builtinCheck(host: Host, engine: EngineInfo, images: ImageRef[]): Promise<CheckResult> {
  const checks: CheckItem[] = [];
  const add = (id: string, ok: boolean, message: string, fix?: string) => checks.push({ id, ok, message, fix });

  const v = await engineRun(host, engine, ['version']);
  add('engine', v.code === 0, v.code === 0 ? 'Engine answers' : `Engine did not answer: ${logOf(v).slice(0, 200)}`, 'Restart the computer.');

  const vol = `sid-setupcheck-${process.pid}`;
  const c = await engineRun(host, engine, ['volume', 'create', vol]);
  await engineRun(host, engine, ['volume', 'rm', '-f', vol]);
  add('volume', c.code === 0, c.code === 0 ? 'Workspace storage works' : 'Could not create a workspace volume');

  const first = images[0];
  if (first) {
    const r = await engineRun(host, engine, ['run', '--rm', '--network=none', first.ref, 'true'], 300_000);
    add('run', r.code === 0, r.code === 0 ? 'A lab container starts' : `A lab container did not start: ${logOf(r).slice(0, 200)}`);
  }
  return { ok: checks.every((x) => x.ok), checks };
}
