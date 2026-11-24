import { useEffect, useState, type ComponentType, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronRight, Menu, X } from "lucide-react";
import { cn } from "./cn";
import { Logo } from "./Logo";
import { fade } from "./motion";

/**
 * App frame shared by the teacher area and the student home: a left sidebar of
 * sections, a slim top bar with breadcrumbs and page-wide actions, and the page.
 * Below `lg` the sidebar becomes a drawer behind a menu button.
 */

export interface NavItem {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  active?: boolean;
  /** A small count or dot next to the label (e.g. open live labs). */
  badge?: ReactNode;
  title?: string;
}
export interface NavSection { title?: string; items: NavItem[] }
export interface Crumb { label: string; href?: string }

export function AppShell({ home, subtitle, nav, footer, trail, actions, children }: {
  home: string;
  subtitle?: string;
  nav: NavSection[];
  /** Bottom of the sidebar: who is signed in, sign out. */
  footer?: ReactNode;
  trail?: Crumb[];
  /** Right side of the top bar (search, help). */
  actions?: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  // close the drawer whenever the page changes
  useEffect(() => {
    const close = () => setOpen(false);
    window.addEventListener("hashchange", close);
    return () => window.removeEventListener("hashchange", close);
  }, []);

  const sidebar = (
    <div className="flex h-full flex-col">
      <a href={home} className="flex h-14 shrink-0 items-center rounded-lg px-4"><Logo subtitle={subtitle} /></a>
      <nav aria-label="Main" className="flex-1 overflow-y-auto px-2.5 pb-4">
        {nav.map((s, i) => (
          <div key={s.title ?? i} className={cn(i > 0 && "mt-5")}>
            {s.title && <div className="px-2.5 pb-1.5 text-[11.5px] font-medium text-faint">{s.title}</div>}
            <ul className="grid gap-px">
              {s.items.map((it) => <SideLink key={it.href} item={it} />)}
            </ul>
          </div>
        ))}
      </nav>
      {footer && <div className="shrink-0 border-t border-border p-2.5">{footer}</div>}
    </div>
  );

  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 border-r border-border bg-sidebar lg:block">{sidebar}</aside>
      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-50 lg:hidden" initial="initial" animate="animate" exit="exit">
            <motion.div variants={fade} className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
            <motion.aside
              initial={{ x: -280 }} animate={{ x: 0 }} exit={{ x: -280 }} transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
              className="absolute inset-y-0 left-0 w-64 border-r border-border bg-sidebar shadow-lg">
              <button onClick={() => setOpen(false)} aria-label="Close menu"
                className="absolute right-2 top-3 grid size-8 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text">
                <X className="size-4" />
              </button>
              {sidebar}
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-bg/85 px-3 backdrop-blur-md sm:px-5">
          <button onClick={() => setOpen(true)} aria-label="Open menu"
            className="grid size-9 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text lg:hidden">
            <Menu className="size-[18px]" />
          </button>
          <Breadcrumbs trail={trail ?? []} />
          <div className="ml-auto flex items-center gap-1">{actions}</div>
        </header>
        <main className="relative flex-1">{children}</main>
      </div>
    </div>
  );
}

function SideLink({ item }: { item: NavItem }) {
  const Icon = item.icon;
  return (
    <li>
      <a href={item.href} title={item.title} aria-current={item.active ? "page" : undefined}
        className={cn(
          "group relative flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[13.5px] transition-colors",
          item.active ? "bg-surface-3 font-medium text-text" : "text-muted hover:bg-surface-2 hover:text-text",
        )}>
        {item.active && <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-full bg-accent" />}
        <Icon className={cn("size-4 shrink-0", item.active ? "text-accent" : "text-faint group-hover:text-muted")} />
        <span className="truncate">{item.label}</span>
        {item.badge != null && <span className="ml-auto">{item.badge}</span>}
      </a>
    </li>
  );
}

export function Breadcrumbs({ trail }: { trail: Crumb[] }) {
  if (!trail.length) return null;
  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1 text-[13px]">
        {trail.map((c, i) => {
          const last = i === trail.length - 1;
          return (
            <li key={`${c.label}-${i}`} className={cn("flex min-w-0 items-center gap-1", !last && "hidden sm:flex")}>
              {i > 0 && <ChevronRight className="size-3.5 shrink-0 text-faint" />}
              {c.href && !last
                ? <a href={c.href} className="truncate rounded px-1 text-muted hover:text-text">{c.label}</a>
                : <span aria-current={last ? "page" : undefined} className={cn("truncate px-1", last ? "font-medium text-text" : "text-muted")}>{c.label}</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** A square icon button for the top bar. */
export function TopBarButton({ label, onClick, href, children, className }: {
  label: string; onClick?: () => void; href?: string; children: ReactNode; className?: string;
}) {
  const cls = cn("inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-[13px] font-medium text-muted transition-colors hover:bg-surface-2 hover:text-text", className);
  return href
    ? <a href={href} title={label} aria-label={label} className={cls}>{children}</a>
    : <button type="button" onClick={onClick} title={label} aria-label={label} className={cls}>{children}</button>;
}
