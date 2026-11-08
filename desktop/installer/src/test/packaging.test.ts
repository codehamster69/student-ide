/**
 * Static checks on shipped packaging files that bit a real macOS install
 * (2026-11-08): Lima 1.0.7 refuses a probe script without a '#!' line, and an
 * unsigned arm64 build is killed at launch unless fuses re-sign it ad hoc.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = path.join(__dirname, '..', '..');
const read = (p: string) => fs.readFileSync(path.join(root, p), 'utf8');

test('lima template: every provision and probe script starts with a #! line', () => {
  const lines = read('assets/lima/studentide.yaml').split('\n');
  const scripts = lines.flatMap((l, i) => (/script: \|\s*$/.test(l) ? [lines[i + 1].trim()] : []));
  assert.equal(scripts.length, 3);
  for (const first of scripts) assert.match(first, /^#!/);
});

test('electron-builder: fuses reset the ad-hoc macOS signature', () => {
  assert.match(read('packaging/electron-builder.yml'), /^\s+resetAdHocDarwinSignature: true$/m);
});
