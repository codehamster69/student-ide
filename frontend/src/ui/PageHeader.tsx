import type { ComponentType, ReactNode } from "react";
import { cn } from "./cn";

/**
 * Page layout pieces: a width-limited page body, the page's title row with its
 * main actions on the right, and an empty state that says what to do next.
 */

export function Page({ wide = false, className, children }: { wide?: boolean; className?: string; children: ReactNode }) {
  return <div className={cn("mx-auto w-full px-4 pb-20 pt-6 sm:px-6 sm:pt-8", wide ? "max-w-[1440px]" : "max-w-[1120px]", className)}>{children}</div>;
}

export function PageHeader({ title, description, actions, meta, className }: {
  title: ReactNode;
  description?: ReactNode;
  /** Primary action last, so it sits at the right edge. */
  actions?: ReactNode;
  /** A row of badges or facts under the title. */
  meta?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-3", className)}>
      <div className="min-w-0 max-w-3xl">
        <h1 className="text-[22px] font-semibold leading-tight tracking-[-0.015em] text-text">{title}</h1>
        {description && <p className="mt-1.5 text-sm leading-relaxed text-muted">{description}</p>}
        {meta && <div className="mt-2.5 flex flex-wrap items-center gap-2">{meta}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action, className }: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid justify-items-center rounded-xl border border-dashed border-border-strong px-6 py-12 text-center", className)}>
      <span className="grid size-10 place-items-center rounded-lg bg-accent-soft text-accent"><Icon className="size-5" /></span>
      <h2 className="mt-3 text-[15px] font-semibold text-text">{title}</h2>
      {children && <div className="mt-1 max-w-md text-sm leading-relaxed text-muted">{children}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
