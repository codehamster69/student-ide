"""The "registries only" network for teacher previews: a tiny forward proxy that
lets package registries through and refuses everything else.

Preview containers sit on an internal Docker network with no route out; this
proxy is on that network and on one with internet access, and the containers
get HTTP(S)_PROXY pointing at it (previews.DockerDriver). It understands
CONNECT (HTTPS, never decrypted) and plain-HTTP requests with an absolute URL
(apt's mirrors). It logs host names only, never contents, like the desktop
runtime's sidecar, and uses the same host list
(desktop/sandbox/src/registries.ts; tests/test_registry_proxy.py keeps the two equal).

    python -m studentide.registry_proxy --port 8888
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from urllib.parse import urlsplit

REGISTRY_HOSTS: tuple[str, ...] = (
    # apt (Ubuntu)
    "archive.ubuntu.com", "security.ubuntu.com", "ports.ubuntu.com", "ppa.launchpadcontent.net",
    # Python
    "pypi.org", "files.pythonhosted.org", "repo.anaconda.com", "conda.anaconda.org",
    # JavaScript
    "registry.npmjs.org", "registry.yarnpkg.com",
    # Java
    "repo.maven.apache.org", "repo1.maven.org", "plugins.gradle.org", "services.gradle.org", "downloads.gradle.org",
    # Rust and Go
    "crates.io", "index.crates.io", "static.crates.io", "static.rust-lang.org",
    "proxy.golang.org", "sum.golang.org", "storage.googleapis.com",
    # GitHub release assets
    "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com", "codeload.github.com",
)
PORTS = {80, 443}
log = logging.getLogger("registry_proxy")


def host_allowed(host: str, hosts=REGISTRY_HOSTS) -> bool:
    h = host.lower().rstrip(".")
    return any(h == a or h.endswith("." + a) for a in hosts)


async def _pipe(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
    try:
        while data := await r.read(65536):
            w.write(data)
            await w.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            w.close()
        except Exception:
            pass


async def _refuse(w: asyncio.StreamWriter, code: int, why: str) -> None:
    body = f"Student IDE preview: {why}\n".encode()
    w.write(f"HTTP/1.1 {code} {why}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body)
    try:
        await w.drain()
    finally:
        w.close()


class Proxy:
    def __init__(self, hosts=REGISTRY_HOSTS, ports=PORTS, timeout: float = 15):
        self.hosts, self.ports, self.timeout = hosts, ports, timeout

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), self.timeout)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError):
            writer.close()
            return
        line, _, rest = head.partition(b"\r\n")
        try:
            method, target, version = line.decode("latin-1").split(" ", 2)
        except ValueError:
            return await _refuse(writer, 400, "Bad Request")
        if method == "CONNECT":
            host, _, port = target.rpartition(":")
            port = int(port) if port.isdigit() else 0
        else:
            u = urlsplit(target)
            if u.scheme != "http" or not u.hostname:
                return await _refuse(writer, 400, "Bad Request")
            host, port = u.hostname, u.port or 80
        host = host.strip("[]")
        if not host_allowed(host, self.hosts) or port not in self.ports:
            log.info("refused %s %s:%s from %s", method, host, port, peer and peer[0])
            return await _refuse(writer, 403, "Forbidden: only package registries are reachable")
        log.info("allowed %s %s:%s from %s", method, host, port, peer and peer[0])
        try:
            up_r, up_w = await asyncio.wait_for(asyncio.open_connection(host, port), self.timeout)
        except (OSError, asyncio.TimeoutError):
            return await _refuse(writer, 502, "Bad Gateway")
        if method == "CONNECT":
            writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await writer.drain()
        else:  # origin-form request line; ask the server to close so one connection = one host
            u = urlsplit(target)
            path = (u.path or "/") + (f"?{u.query}" if u.query else "")
            headers = [h for h in rest.split(b"\r\n") if h and not h.lower().startswith((b"proxy-", b"connection:"))]
            up_w.write(f"{method} {path} {version}\r\n".encode("latin-1") + b"\r\n".join(headers)
                       + b"\r\nConnection: close\r\n\r\n")
            await up_w.drain()
        await asyncio.gather(_pipe(reader, up_w), _pipe(up_r, writer))


async def serve(host: str, port: int, proxy: Proxy | None = None) -> asyncio.base_events.Server:
    return await asyncio.start_server((proxy or Proxy()).handle, host, port)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8888)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    async def run() -> None:
        server = await serve(a.host, a.port)
        log.info("registries-only proxy on %s:%s, %d hosts", a.host, a.port, len(REGISTRY_HOSTS))
        async with server:
            await server.serve_forever()

    asyncio.run(run())


if __name__ == "__main__":
    main()
