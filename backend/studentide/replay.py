"""Rebuild the document from edit events.

Later phases need the code as it stood at any moment (e.g. AST build order
per 30-second window). Snapshots give checkpoints; edits fill the gaps.
"""

from __future__ import annotations

from typing import Iterable, Iterator


class ReplayError(ValueError):
    pass


def utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def apply_edit(doc: str, data: dict) -> str:
    """Apply one edit event. Offsets are UTF-16 code units, as in the browser
    (CodeMirror), so characters outside the BMP such as emoji count as two."""
    buf = doc.encode("utf-16-le")
    if len(buf) // 2 != data["len_before"]:
        raise ReplayError(f"document length {len(buf) // 2} != len_before {data['len_before']}")
    # changes are ascending in pre-edit coordinates; apply back to front so offsets stay valid
    for frm, to, text in reversed(data["changes"]):
        buf = buf[: 2 * frm] + text.encode("utf-16-le") + buf[2 * to :]
    if len(buf) // 2 != data["len_after"]:
        raise ReplayError("length after edit does not match len_after")
    return buf.decode("utf-16-le")


def replay(events: Iterable[dict], initial: str | None = None) -> Iterator[tuple[dict, str]]:
    """Yield (event, document_after_event) for every event, in seq order.

    The document starts from `initial`, or from the first `snapshot` event.
    Each later snapshot is checked against the replayed text; a mismatch means
    lost or reordered events and raises ReplayError.
    """
    doc = initial
    for ev in events:
        if ev["type"] == "snapshot":
            if doc is None:
                doc = ev["data"]["text"]
            elif doc != ev["data"]["text"]:
                raise ReplayError(f"replay diverged from snapshot at seq {ev['seq']}")
        elif ev["type"] == "edit":
            if doc is None:
                raise ReplayError("edit before any snapshot and no initial text")
            doc = apply_edit(doc, ev["data"])
        yield ev, doc if doc is not None else ""


def final_text(events: Iterable[dict], initial: str | None = None) -> str:
    doc = initial or ""
    for _, doc in replay(events, initial):
        pass
    return doc
