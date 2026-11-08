/** The desktop journal: signed hash-chained uploads, 5-minute offline buffer then read-only, nothing lost across restarts. */

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash, createPublicKey, verify } from "node:crypto";
import { Journal, type KeyStore } from "../src/journal.ts";

function fakeServer() {
  const s = {
    up: true,
    pub: "",
    batches: [] as Array<{ batch_seq: number; prev_hash: string; offline_ms: number; events: any[]; hash: string; ok: boolean }>,
    async fetch(path: string, init?: { method?: string; body?: string }) {
      if (!s.up) throw new Error("ECONNREFUSED");
      const res = (status: number, body: unknown) => ({ ok: status < 300, status, json: async () => body });
      if (path === "/api/me") return res(200, { student_id: "S1" });
      if (path === "/api/desktop/config") return res(200, {});
      if (path.startsWith("/api/devices")) { s.pub = JSON.parse(init!.body!).public_key; return res(200, { device_id: "d1" }); }
      const { signed } = JSON.parse(init!.body!);
      const key = createPublicKey({ key: { kty: "OKP", crv: "Ed25519", x: Buffer.from(s.pub, "base64").toString("base64url") }, format: "jwk" });
      const ok = verify(null, Buffer.from(signed.payload), key, Buffer.from(signed.sig, "base64"));
      const p = JSON.parse(signed.payload);
      s.batches.push({ ...p, hash: createHash("sha256").update(signed.payload).digest("hex"), ok });
      return res(200, { inserted: p.events.length });
    },
  };
  return s;
}

const memKeys = (): KeyStore & { der: Buffer | null } => { const k = { der: null as Buffer | null, load: () => k.der, save: (d: Buffer) => { k.der = d; } }; return k; };
const ev = (seq: number) => ({ seq, t: seq, type: "focus", data: { target: "window", state: "in" } });

test("batches are signed and chained, and the files go once a closed session is sent", async () => {
  const srv = fakeServer();
  const dir = mkdtempSync(join(tmpdir(), "jr-"));
  const j = new Journal({ dir, fetch: srv.fetch, keys: memKeys() });
  j.append("abc", [ev(0), ev(1)]);
  await j.tick();
  j.append("abc", [ev(2)]);
  j.close("abc");
  await j.tick();
  assert.equal(srv.batches.length, 2);
  assert.ok(srv.batches.every((b) => b.ok));
  assert.equal(srv.batches[0]!.prev_hash, "");
  assert.equal(srv.batches[1]!.prev_hash, srv.batches[0]!.hash);
  assert.deepEqual(srv.batches.flatMap((b) => b.events.map((e) => e.seq)), [0, 1, 2]);
  assert.equal(j.state().pending, 0);
  await j.stop();
});

test("offline: keeps writing, read-only after 5 minutes, catches up with the outage length", async () => {
  const srv = fakeServer();
  let now = 1_000_000;
  const states: any[] = [];
  const j = new Journal({ dir: mkdtempSync(join(tmpdir(), "jr-")), fetch: srv.fetch, keys: memKeys(), now: () => now, onState: (s) => states.push(s) });
  j.append("s1", [ev(0)]);
  await j.tick();
  srv.up = false;
  j.append("s1", [ev(1)]);
  await j.tick();
  assert.equal(j.state().online, false);
  assert.equal(j.state().readOnly, false);
  now += 4 * 60_000;
  j.append("s1", [ev(2)]);
  await j.tick();
  assert.equal(j.state().readOnly, false);
  assert.equal(j.state().pending, 2);
  now += 61_000;
  await j.tick();
  assert.equal(j.state().readOnly, true);
  srv.up = true;
  await j.tick();
  assert.equal(j.state().online, true);
  assert.equal(j.state().readOnly, false);
  const last = srv.batches.at(-1)!;
  assert.deepEqual(last.events.map((e) => e.seq), [1, 2]);
  assert.ok(last.offline_ms >= 5 * 60_000);
  assert.deepEqual(states.map((s) => [s.online, s.readOnly]), [[true, false], [false, false], [false, true], [true, false]]);
  await j.stop();
});

test("a restart picks up unsent events and keeps the chain", async () => {
  const srv = fakeServer();
  const dir = mkdtempSync(join(tmpdir(), "jr-"));
  const keys = memKeys();
  const a = new Journal({ dir, fetch: srv.fetch, keys });
  a.append("s2", [ev(0)]);
  await a.tick();
  srv.up = false;
  a.append("s2", [ev(1), ev(2)]);
  a.fsync();
  await a.stop(); // quit while offline
  srv.up = true;
  const b = new Journal({ dir, fetch: srv.fetch, keys });
  assert.equal(b.state().pending, 2);
  await b.tick();
  assert.equal(srv.batches.length, 2);
  assert.equal(srv.batches[1]!.prev_hash, srv.batches[0]!.hash);
  assert.equal(srv.batches[1]!.batch_seq, 1);
  await b.stop();
});
