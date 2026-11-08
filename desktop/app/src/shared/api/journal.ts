/**
 * `studentDesktop.journal`: the app's event journal (@studentide/sandbox journal.ts).
 *
 * In the desktop app the web Recorder does not upload events itself: it hands
 * each batch here, the main process writes it to disk before answering, and
 * uploads it signed and hash-chained. While the server cannot be reached the
 * student keeps working for 5 minutes ("Reconnecting…"); after that `readOnly`
 * is true and the lab screen stops taking input until the connection is back.
 */

export interface JournalState {
  online: boolean;
  offlineSince: number | null; // Date.now() when the connection was lost
  readOnly: boolean;
  pending: number;             // events on disk not yet accepted by the server
  remainingMs: number | null;  // buffer left before read-only, while offline
}

export interface JournalApi {
  /** Write events (the Recorder's {seq, t, type, data}) for this session; resolves once they are on disk. */
  append(sessionId: string, events: unknown[]): Promise<JournalState>;
  /** The session ended: upload what is left, then forget it. */
  close(sessionId: string): Promise<void>;
  state(): Promise<JournalState>;
}

export interface JournalEvents {
  /** online / offline / read-only changed */
  "journal.state": JournalState;
}
