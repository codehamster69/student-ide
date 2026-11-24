import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { CornerDownLeft, Search } from "lucide-react";
import { cn } from "./cn";
import { fade, pop } from "./motion";
import { Kbd } from "./Badge";

/**
 * Ctrl+K / ⌘K jump list: pages plus whatever `load` returns (labs, sessions…),
 * fetched each time it opens. Only mounted on screens that do not record typing.
 */

export interface Command {
  id: string;
  label: string;
  group: string;
  href: string;
  hint?: string;
  keywords?: string;
  icon?: ComponentType<{ className?: string }>;
}

const mac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
export const paletteKey = mac ? "⌘K" : "Ctrl K";

export function useCommandPalette() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);
  return { open, setOpen };
}

/** The top-bar button that opens the palette. */
export function SearchButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick}
      className="flex h-8 items-center gap-2 rounded-md border border-border bg-surface px-2.5 text-[13px] text-faint shadow-sm transition-colors hover:border-border-strong hover:text-muted">
      <Search className="size-3.5" />
      <span className="hidden md:inline">Search or jump to…</span>
      <Kbd className="ml-2 hidden border-border text-faint md:inline-flex">{paletteKey}</Kbd>
    </button>
  );
}

export function CommandPalette({ open, onClose, commands, load }: {
  open: boolean;
  onClose: () => void;
  commands: Command[];
  load?: () => Promise<Command[]>;
}) {
  const [q, setQ] = useState("");
  const [extra, setExtra] = useState<Command[]>([]);
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!open) return;
    setQ(""); setSel(0);
    const t = window.setTimeout(() => input.current?.focus(), 20);
    let live = true;
    load?.().then((c) => live && setExtra(c)).catch(() => undefined);
    return () => { live = false; window.clearTimeout(t); };
  }, [open, load]);

  const results = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    const all = [...commands, ...extra];
    const hit = words.length
      ? all.filter((c) => { const hay = `${c.label} ${c.group} ${c.hint ?? ""} ${c.keywords ?? ""}`.toLowerCase(); return words.every((w) => hay.includes(w)); })
      : all;
    // labels that contain the whole query first, then the rest in their groups
    const whole = q.trim().toLowerCase();
    const ranked = whole ? [...hit.filter((c) => c.label.toLowerCase().includes(whole)), ...hit.filter((c) => !c.label.toLowerCase().includes(whole))] : hit;
    return ranked.slice(0, 60);
  }, [q, commands, extra]);

  useEffect(() => { setSel(0); }, [q]);
  useEffect(() => { list.current?.querySelector<HTMLElement>(`[data-i="${sel}"]`)?.scrollIntoView({ block: "nearest" }); }, [sel]);

  const go = (c?: Command) => { if (!c) return; onClose(); location.hash = c.href.replace(/^#/, ""); };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); go(results[sel]); }
    else if (e.key === "Escape") { e.preventDefault(); onClose(); }
  };

  let lastGroup = "";
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[60] flex justify-center px-4 pt-[12vh]" initial="initial" animate="animate" exit="exit">
          <motion.div variants={fade} className="absolute inset-0 bg-black/40" onClick={onClose} />
          <motion.div variants={pop} role="dialog" aria-modal="true" aria-label="Search"
            className="relative flex max-h-[min(560px,70vh)] w-full max-w-xl flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-lg">
            <div className="flex items-center gap-2.5 border-b border-border px-4">
              <Search className="size-4 shrink-0 text-faint" />
              <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey}
                placeholder="Search pages, labs, sessions…" aria-label="Search"
                role="combobox" aria-expanded="true" aria-controls="palette-list" aria-activedescendant={results[sel] ? `pc-${sel}` : undefined}
                className="h-12 flex-1 bg-transparent text-[15px] text-text outline-none placeholder:text-faint" />
              <Kbd className="border-border text-faint">Esc</Kbd>
            </div>
            <ul ref={list} id="palette-list" role="listbox" className="flex-1 overflow-y-auto p-1.5">
              {!results.length && <li className="px-3 py-8 text-center text-sm text-muted">Nothing matches “{q}”.</li>}
              {results.map((c, i) => {
                const head = c.group !== lastGroup ? (lastGroup = c.group) : null;
                const Icon = c.icon;
                return (
                  <li key={c.id} role="presentation">
                    {head && <div className="px-2.5 pb-1 pt-2.5 text-[11.5px] font-medium text-faint">{head}</div>}
                    <div id={`pc-${i}`} data-i={i} role="option" aria-selected={i === sel}
                      onMouseMove={() => setSel(i)} onClick={() => go(c)}
                      className={cn("flex h-9 cursor-pointer items-center gap-2.5 rounded-md px-2.5 text-sm", i === sel ? "bg-accent-soft text-text" : "text-muted")}>
                      {Icon && <Icon className={cn("size-4 shrink-0", i === sel ? "text-accent" : "text-faint")} />}
                      <span className="truncate text-text">{c.label}</span>
                      {c.hint && <span className="truncate text-xs text-faint">{c.hint}</span>}
                      {i === sel && <CornerDownLeft className="ml-auto size-3.5 shrink-0 text-accent" />}
                    </div>
                  </li>
                );
              })}
            </ul>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
