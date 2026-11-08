"""The registries-only proxy for teacher previews: allowlist, refusals, CONNECT
tunnels and plain-HTTP forwarding, and the same host list as the desktop runtime."""

import asyncio
import pathlib
import re
import subprocess

import pytest

from studentide import registry_proxy as rp

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_host_allowed():
    assert rp.host_allowed("pypi.org") and rp.host_allowed("FILES.pythonhosted.org.")
    assert rp.host_allowed("in.archive.ubuntu.com")  # mirrors are sub-domains
    assert not rp.host_allowed("evilpypi.org") and not rp.host_allowed("pypi.org.evil.com")
    assert not rp.host_allowed("chat.openai.com") and not rp.host_allowed("10.0.0.1")


def _ts_hosts(text: str) -> list[str]:
    block = text.split("REGISTRY_HOSTS", 1)[1].split("];", 1)[0]
    return re.findall(r'"([^"]+)"', block)


def test_same_hosts_as_desktop_runtime():
    path = ROOT / "desktop/sandbox/src/registries.ts"
    if path.exists():
        text = path.read_text()
    else:  # the desktop runtime may live on its own branch until it merges
        try:
            text = subprocess.run(["git", "-C", str(ROOT), "show", "origin/claude/project-thread-qhgxwz:"
                                   "desktop/sandbox/src/registries.ts"], capture_output=True, text=True,
                                  check=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("desktop/sandbox/src/registries.ts not available")
    assert tuple(_ts_hosts(text)) == rp.REGISTRY_HOSTS


async def _exchange(port: int, data: bytes, then: bytes | None = None) -> bytes:
    r, w = await asyncio.open_connection("127.0.0.1", port)
    w.write(data)
    await w.drain()
    out = b""
    if then is not None:
        out = await r.readuntil(b"\r\n\r\n")
        w.write(then)
        await w.drain()
    out += await asyncio.wait_for(r.read(65536), 5)
    w.close()
    return out


def _run(coro):
    return asyncio.run(coro)


def test_refuses_other_hosts_and_ports():
    async def go():
        server = await rp.serve("127.0.0.1", 0, rp.Proxy())
        port = server.sockets[0].getsockname()[1]
        async with server:
            a = await _exchange(port, b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com\r\n\r\n")
            b = await _exchange(port, b"CONNECT pypi.org:22 HTTP/1.1\r\n\r\n")
            c = await _exchange(port, b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n")
            d = await _exchange(port, b"GET /relative HTTP/1.1\r\n\r\n")
        return a, b, c, d
    a, b, c, d = _run(go())
    assert a.startswith(b"HTTP/1.1 403") and b"package registries" in a
    assert b.startswith(b"HTTP/1.1 403") and c.startswith(b"HTTP/1.1 403")
    assert d.startswith(b"HTTP/1.1 400")


def test_connect_tunnel_and_http_forwarding():
    """A local 'registry' on 127.0.0.1 stands in for pypi; the proxy allows it by name."""
    async def go():
        seen = []

        async def registry(r, w):
            head = await r.readuntil(b"\r\n\r\n")
            seen.append(head)
            w.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
            await w.drain()
            w.close()

        up = await asyncio.start_server(registry, "127.0.0.1", 0)
        up_port = up.sockets[0].getsockname()[1]
        server = await rp.serve("127.0.0.1", 0, rp.Proxy(hosts=("127.0.0.1",), ports={up_port}))
        port = server.sockets[0].getsockname()[1]
        async with up, server:
            tunnel = await _exchange(port, f"CONNECT 127.0.0.1:{up_port} HTTP/1.1\r\n\r\n".encode(),
                                     then=b"GET /simple/ HTTP/1.1\r\nHost: x\r\n\r\n")
            plain = await _exchange(port, f"GET http://127.0.0.1:{up_port}/ubuntu/dists?x=1 HTTP/1.1\r\n"
                                          f"Host: 127.0.0.1\r\nProxy-Connection: keep-alive\r\n\r\n".encode())
        return seen, tunnel, plain
    seen, tunnel, plain = _run(go())
    assert tunnel.startswith(b"HTTP/1.1 200 Connection established") and tunnel.endswith(b"ok")
    assert plain.startswith(b"HTTP/1.1 200 OK") and plain.endswith(b"ok")
    assert seen[0].startswith(b"GET /simple/ ")
    assert seen[1].startswith(b"GET /ubuntu/dists?x=1 HTTP/1.1") and b"Proxy-Connection" not in seen[1]
    assert b"Connection: close" in seen[1]
