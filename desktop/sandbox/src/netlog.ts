/**
 * net_conn events from the proxy sidecar's log ("registries only" labs).
 *
 * tinyproxy logs each request, then either "Established connection to host"
 * or "Proxying refused on filtered domain". Each host is reported once per
 * watch and decision (the plan's "reaches a new host"), never the contents.
 */

import { netConn, type SandboxEvent } from "./events.ts";
import type { Instance } from "./instance.ts";

export class ProxyLogParser {
  private port = new Map<string, number>();
  private seen = new Set<string>();

  /** One log line in, zero or one event out. */
  line(l: string): SandboxEvent | null {
    const req = /Request \(file descriptor \d+\): (?:CONNECT ([^\s:]+):(\d+)|[A-Z]+ https?:\/\/([^/\s:]+)(?::(\d+))?)/.exec(l);
    if (req) {
      const host = (req[1] ?? req[3] ?? "").toLowerCase();
      this.port.set(host, Number(req[2] ?? req[4] ?? (req[3] ? 80 : 443)));
      return null;
    }
    const ok = /Established connection to host "([^"]+)"/.exec(l);
    const no = /Proxying refused on filtered domain "([^"]+)"/.exec(l);
    const m = ok ?? no;
    if (!m) return null;
    const host = m[1]!.toLowerCase();
    const allowed = Boolean(ok);
    const k = `${host}|${allowed}`;
    if (this.seen.has(k)) return null;
    this.seen.add(k);
    return netConn(host, this.port.get(host) ?? null, allowed);
  }
}

/** Follow the proxy's log while the lab is open; returns a stop function. */
export function watchProxy(instance: Instance, onEvent: (ev: SandboxEvent) => void): () => void {
  const p = instance.engine.spawn(["logs", "-f", "--since", "1s", instance.proxy]);
  const parser = new ProxyLogParser();
  let buf = "";
  const feed = (b: Buffer) => {
    buf += b.toString("utf8");
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const l of lines) {
      const ev = parser.line(l);
      if (ev) onEvent(ev);
    }
  };
  p.stdout.on("data", feed);
  p.stderr.on("data", feed); // tinyproxy logs to stderr
  p.stdin.end();
  p.on("error", () => {});
  return () => p.kill();
}
