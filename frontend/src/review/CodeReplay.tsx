// Read-only editor showing the code as it stood at the playhead. Lines that
// are new or changed in the last 30 seconds are tinted.

import { useEffect, useRef } from "react";
import { EditorState, RangeSetBuilder, StateEffect, StateField } from "@codemirror/state";
import { Decoration, EditorView, lineNumbers, type DecorationSet } from "@codemirror/view";
import { python } from "@codemirror/lang-python";
import { editorTheme } from "../editor/theme";

const setMarks = StateEffect.define<number[]>();

const marks = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(value, tr) {
    for (const e of tr.effects) {
      if (e.is(setMarks)) {
        const b = new RangeSetBuilder<Decoration>();
        for (const n of e.value) if (n <= tr.state.doc.lines) b.add(tr.state.doc.line(n).from, tr.state.doc.line(n).from, recent);
        return b.finish();
      }
    }
    return value.map(tr.changes);
  },
  provide: (f) => EditorView.decorations.from(f),
});

const recent = Decoration.line({ class: "cm-recent" });

const replayTheme = EditorView.theme({
  "&": { fontSize: "13px" },
  ".cm-recent": { backgroundColor: "color-mix(in srgb, var(--accent) 11%, transparent)", boxShadow: "inset 2px 0 0 var(--accent)" },
  ".cm-content": { padding: "10px 0" },
});

export function CodeReplay({ doc, changed, caret }: { doc: string; changed: number[]; caret: number }) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);

  useEffect(() => {
    view.current = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc,
        extensions: [lineNumbers(), python(), editorTheme, replayTheme, marks, EditorState.readOnly.of(true), EditorView.editable.of(false)],
      }),
    });
    return () => view.current?.destroy();
    // created once; later docs arrive through dispatch below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const v = view.current;
    if (!v) return;
    const same = v.state.doc.toString() === doc;
    const pos = Math.min(caret, doc.length);
    v.dispatch({
      changes: same ? undefined : { from: 0, to: v.state.doc.length, insert: doc },
      effects: [setMarks.of(changed), EditorView.scrollIntoView(pos, { y: "nearest", yMargin: 48 })],
    });
  }, [doc, changed, caret]);

  return <div ref={host} className="h-full overflow-hidden [&_.cm-editor]:h-full" />;
}
