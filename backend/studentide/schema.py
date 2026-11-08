"""Event schema shared by the logger (frontend) and the analysis pipeline.

Every event the editor records has the same envelope:

    seq   - per-session counter assigned by the client, starting at 0.
            (session_id, seq) is unique, which makes uploads idempotent.
    t     - milliseconds since the session started, from the browser's
            high-resolution clock (sub-millisecond, monotonic).
    type  - one of EVENT_TYPES below.
    data  - type-specific payload, validated by the matching model.

Bump SCHEMA_VERSION whenever a payload changes shape, so later phases can
tell old recordings apart. See docs/event-schema.md for the prose version.

Version 2 (Sandbox Labs, desktop app) is additive: key.surface/path,
edit.path, snapshot.path, run.source/command, and the terminal and instance
events term_cmd, term_output, term_paste, pkg_install, net_conn. Every v1
batch is a valid v2 batch, so the server accepts both versions.

Version 3 (Sandbox Labs monitoring) is additive again: fs_change (a workspace
file changed outside our editor, from the sidecar watcher) and port_open
(something in the instance started or stopped listening). The desktop app
also sends batches with a signed, hash-chained envelope (batches.py); that is
transport, not payload, so it is not part of this schema.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SCHEMA_VERSION = 3
SUPPORTED_VERSIONS = (1, 2, 3)


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


Surface = Literal["editor", "terminal", "terminal-editor"]
KeyClass = Literal["letter", "digit", "space", "enter", "tab", "punct", "backspace", "delete", "nav", "modifier", "other"]


class KeyData(_Payload):
    """A physical key press or release. Timing source for keystroke dynamics."""

    action: Literal["down", "up"]
    code: str = Field(max_length=32)  # KeyboardEvent.code, e.g. "KeyA" (layout-independent)
    cls: KeyClass
    repeat: bool = False
    shift: bool = False
    ctrl: bool = False
    alt: bool = False
    meta: bool = False
    # v2: where the key was typed. "terminal" = shell prompt, "terminal-editor" = vim/nano in the
    # desktop terminal (path = the file it opened). Only "editor" keys feed the identity channel.
    surface: Surface = "editor"
    path: str | None = Field(default=None, max_length=512)


class EditData(_Payload):
    """One editor transaction that changed the document.

    changes: [from, to, inserted_text] triples in the coordinates of the
    document *before* this edit, ascending by `from`. Replaying them in
    order of seq reconstructs the document exactly (see replay.py).
    Offsets and lengths are UTF-16 code units, as JavaScript counts them.
    """

    origin: str = Field(max_length=64)  # CodeMirror userEvent: input.type, input.paste, delete.backward, undo, ...
    changes: list[tuple[int, int, str]]
    len_before: int
    len_after: int
    path: str | None = Field(default=None, max_length=512)  # v2: file of a multi-file workspace; None = the one document

    @model_validator(mode="after")
    def _check(self) -> "EditData":
        prev_end = -1
        delta = 0
        for frm, to, text in self.changes:
            if frm < 0 or to < frm or frm < prev_end or to > self.len_before:
                raise ValueError("changes must be non-overlapping, ascending and inside the document")
            prev_end = to
            delta += len(text.encode("utf-16-le")) // 2 - (to - frm)
        if self.len_before + delta != self.len_after:
            raise ValueError("len_after does not match changes")
        return self


class ClipboardData(_Payload):
    """paste / copy / cut on the editor. The pasted text itself arrives in the
    following edit event (origin input.paste); this records the clipboard side."""

    action: Literal["paste", "copy", "cut"]
    length: int
    lines: int
    text: str  # clipboard text, truncated to MAX_CLIPBOARD by the client
    truncated: bool = False


class CursorData(_Payload):
    """Selection change not caused by an edit (clicks, arrow keys). Throttled."""

    anchor: int
    head: int
    line: int


class RunData(_Payload):
    """The student pressed Run. Full result lives in the runs table under run_id."""

    run_id: str
    code_sha256: str
    exit_code: int | None = None
    duration_ms: float | None = None
    error_type: str | None = None  # e.g. "SyntaxError", "Timeout", None if clean
    # v2 (desktop): "button" (Run), "test" (local Check) or "terminal" (a compile/run command typed
    # in the terminal, run_id "t-…" has no row in the runs table); command = what ran.
    source: Literal["button", "test", "terminal"] | None = None
    command: str | None = Field(default=None, max_length=4096)


class SnapshotData(_Payload):
    """Full document text, taken at session start, every N seconds, on run and at end.
    Lets analysis jump into the middle of a session and double-checks replay."""

    reason: Literal["start", "periodic", "run", "end"]
    text: str
    path: str | None = Field(default=None, max_length=512)  # v2: as edit.path


class FocusData(_Payload):
    """Editor focus, window focus, and tab visibility changes. In a lab with
    several questions, target "question" marks the student switching to
    another question of the same sitting ("out") and back to this one ("in"),
    and in an any-language competition the student switching this question to
    another language (each language is its own session) and back."""

    target: Literal["editor", "window", "page", "question"]
    state: Literal["in", "out"]


class SessionData(_Payload):
    """session_start / session_end markers."""

    wall_clock_ms: float  # Date.now() at this event, to anchor t to real time
    reason: str | None = None  # for session_end: "submit", "pagehide", ...


class TermCmdData(_Payload):
    """v2: a command line the desktop terminal's shell ran, from its shell hooks (best effort:
    the student has sudo and can remove them). phase "start" when it begins, "end" when the
    prompt is back, with the exit code and duration."""

    term_id: str = Field(max_length=32)
    phase: Literal["start", "end"]
    command: str = Field(max_length=4096)
    cwd: str = Field(max_length=1024)
    truncated: bool = False
    exit_code: int | None = None
    duration_ms: float | None = None


class TermOutputData(_Payload):
    """v2: output of one terminal command: bytes written and a clipped, escape-free tail."""

    term_id: str = Field(max_length=32)
    bytes: int = Field(ge=0)
    tail: str = Field(max_length=4096)
    truncated: bool = False


class TermPasteData(_Payload):
    """v2: a paste into the terminal, like ClipboardData for the editor."""

    term_id: str = Field(max_length=32)
    length: int
    lines: int
    text: str
    truncated: bool = False
    sha256: str = Field(max_length=64)


class PkgInstallData(_Payload):
    """v2: a package command that succeeded in the student's instance (feeds the setup recipe)."""

    manager: str = Field(max_length=16)
    action: Literal["install", "remove"]
    packages: list[str] = Field(max_length=200)
    command: str = Field(max_length=4096)


class NetConnData(_Payload):
    """v2: the instance reached a new host through the lab's proxy. Host name only, never contents."""

    host: str = Field(max_length=253)
    port: int | None = None
    allowed: bool


class FsChangeData(_Payload):
    """v3: a workspace file changed and our editor did not write it, seen by the sidecar watcher
    (root in the instance cannot stop it). origin: "terminal-editor" (vim/nano was in the
    foreground), "terminal" (another command was running: cat >, git checkout, a script),
    "outside" (no command we can see: docker cp, a host tool, a background job).
    added = the new lines of this save (clipped), the evidence check reads it."""

    path: str = Field(max_length=512)
    size: int = Field(ge=0)
    sha256: str = Field(max_length=64)
    origin: Literal["terminal-editor", "terminal", "outside"]
    command: str | None = Field(default=None, max_length=4096)
    deleted: bool = False
    binary: bool = False
    added: str = Field(default="", max_length=20000)
    added_lines: int = Field(default=0, ge=0)
    removed_lines: int = Field(default=0, ge=0)
    diff: str = Field(default="", max_length=8000)
    truncated: bool = False


class PortOpenData(_Payload):
    """v3: a program in the instance started (open) or stopped listening on a TCP port."""

    port: int = Field(ge=0, le=65535)
    process: str = Field(default="", max_length=64)
    open: bool


PAYLOADS: dict[str, type[_Payload]] = {
    "key": KeyData,
    "edit": EditData,
    "clipboard": ClipboardData,
    "cursor": CursorData,
    "run": RunData,
    "snapshot": SnapshotData,
    "focus": FocusData,
    "session_start": SessionData,
    "session_end": SessionData,
    "term_cmd": TermCmdData,
    "term_output": TermOutputData,
    "term_paste": TermPasteData,
    "pkg_install": PkgInstallData,
    "net_conn": NetConnData,
    "fs_change": FsChangeData,
    "port_open": PortOpenData,
}
EVENT_TYPES = tuple(PAYLOADS)


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=0)
    t: float = Field(ge=0)
    type: Literal[EVENT_TYPES]  # type: ignore[valid-type]
    data: dict

    @model_validator(mode="after")
    def _validate_payload(self) -> "Event":
        try:
            self.data = PAYLOADS[self.type].model_validate(self.data).model_dump()
        except ValidationError as e:
            raise ValueError(f"bad {self.type} payload: {e}") from e
        return self


class EventBatch(BaseModel):
    schema_version: Literal[SUPPORTED_VERSIONS] = SCHEMA_VERSION  # type: ignore[valid-type]
    events: list[Event] = Field(max_length=5000)
