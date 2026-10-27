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
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SCHEMA_VERSION = 1


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class SnapshotData(_Payload):
    """Full document text, taken at session start, every N seconds, on run and at end.
    Lets analysis jump into the middle of a session and double-checks replay."""

    reason: Literal["start", "periodic", "run", "end"]
    text: str


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
    schema_version: int = SCHEMA_VERSION
    events: list[Event] = Field(max_length=5000)
