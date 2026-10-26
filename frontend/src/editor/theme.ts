// CodeMirror theme built from the design-system CSS variables, so the editor
// follows light/dark mode with the rest of the UI.

import { EditorView } from "@codemirror/view";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags as t } from "@lezer/highlight";

const chrome = EditorView.theme({
  "&": { height: "100%", fontSize: "14.5px", color: "var(--text)", backgroundColor: "var(--surface)" },
  ".cm-scroller": { fontFamily: "var(--font-mono)", lineHeight: "1.7", fontVariantLigatures: "none" },
  ".cm-content": { padding: "14px 0", caretColor: "var(--accent)" },
  ".cm-line": { padding: "0 18px 0 12px" },
  "&.cm-focused": { outline: "none" },
  ".cm-cursor, .cm-dropCursor": { borderLeft: "2px solid var(--accent)" },
  "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, ::selection":
    { backgroundColor: "color-mix(in srgb, var(--accent) 22%, transparent) !important" },
  ".cm-activeLine": { backgroundColor: "color-mix(in srgb, var(--accent) 5%, transparent)" },
  ".cm-gutters": { backgroundColor: "var(--surface)", color: "var(--text-faint)", border: "none", paddingLeft: "6px" },
  ".cm-lineNumbers .cm-gutterElement": { minWidth: "32px", fontSize: "12.5px" },
  ".cm-activeLineGutter": { backgroundColor: "transparent", color: "var(--text)" },
  ".cm-foldGutter .cm-gutterElement": { color: "var(--text-faint)" },
  "&.cm-focused .cm-matchingBracket": { backgroundColor: "color-mix(in srgb, var(--accent) 18%, transparent)", outline: "none" },
  ".cm-selectionMatch": { backgroundColor: "color-mix(in srgb, var(--accent) 10%, transparent)" },
  ".cm-searchMatch": { backgroundColor: "color-mix(in srgb, var(--warn) 25%, transparent)", outline: "none" },
  ".cm-tooltip": {
    border: "1px solid var(--border)", borderRadius: "10px", backgroundColor: "var(--surface)",
    boxShadow: "var(--shadow-md)", overflow: "hidden",
  },
  ".cm-tooltip-autocomplete > ul": { fontFamily: "var(--font-mono)", fontSize: "13px", padding: "4px" },
  ".cm-tooltip-autocomplete > ul > li": { borderRadius: "6px", padding: "2px 8px !important" },
  ".cm-tooltip-autocomplete > ul > li[aria-selected]": { backgroundColor: "var(--accent-soft)", color: "var(--text)" },
  ".cm-panels": { backgroundColor: "var(--surface-2)", color: "var(--text)", borderColor: "var(--border)" },
  ".cm-panel input, .cm-panel button": { fontFamily: "inherit", fontSize: "12px" },
  ".cm-textfield": { border: "1px solid var(--border)", borderRadius: "6px", backgroundColor: "var(--surface)" },
  ".cm-button": { backgroundImage: "none", backgroundColor: "var(--surface)", border: "1px solid var(--border)", borderRadius: "6px" },
});

const highlight = HighlightStyle.define([
  { tag: [t.keyword, t.controlKeyword, t.definitionKeyword, t.moduleKeyword, t.operatorKeyword], color: "var(--syn-keyword)" },
  { tag: [t.string, t.special(t.string)], color: "var(--syn-string)" },
  { tag: [t.number], color: "var(--syn-number)" },
  { tag: [t.bool, t.null, t.atom], color: "var(--syn-constant)" },
  { tag: [t.comment, t.lineComment, t.blockComment], color: "var(--syn-comment)", fontStyle: "italic" },
  { tag: [t.function(t.variableName), t.function(t.propertyName)], color: "var(--syn-function)" },
  { tag: [t.definition(t.variableName), t.definition(t.function(t.variableName)), t.className, t.definition(t.className)], color: "var(--syn-def)" },
  { tag: [t.standard(t.variableName), t.self], color: "var(--syn-builtin)" },
  { tag: [t.operator, t.punctuation, t.bracket], color: "var(--syn-operator)" },
  { tag: t.invalid, color: "var(--danger)" },
]);

export const editorTheme = [chrome, syntaxHighlighting(highlight)];
