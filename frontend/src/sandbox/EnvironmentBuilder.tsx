// The environment builder (plan §5.2): pick a base, tick tools, optional extra
// packages and a setup script, or reuse a shared environment. No Docker needed.
import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { Check, ChevronDown, Search, Share2 } from "lucide-react";
import { Badge, Checkbox, Field, Input, TextArea, cn, spring } from "../ui";
import { get } from "../review/api";
import { BASE_ICON, BuildBadge, mb } from "./bits";
import { emptyRecipe, type BaseInfo, type Environment, type Recipe, type Tool } from "./api";

export type EnvChoice = { kind: "new"; recipe: Recipe } | { kind: "reuse"; environment_id: string };

export function useCatalogue() {
  const [bases, setBases] = useState<BaseInfo[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  useEffect(() => {
    get<BaseInfo[]>("/api/sandbox/bases").then(setBases, () => {});
    get<Tool[]>("/api/sandbox/tools").then(setTools, () => {});
  }, []);
  return { bases, tools };
}

/** Mirrors sandbox.recipe_size_mb: base + ticked tools the base doesn't already include. */
export function sizeOf(recipe: Recipe, bases: BaseInfo[], tools: Tool[]): number {
  const base = bases.find((b) => b.id === recipe.base);
  if (!base) return 0;
  return base.mb + recipe.tools.filter((t) => !base.tools.includes(t)).reduce((s, t) => s + (tools.find((x) => x.id === t)?.mb ?? 0), 0);
}

const words = (s: string) => s.split(/[\s,]+/).map((w) => w.trim()).filter(Boolean);

export function RecipeEditor({ recipe, onChange, bases, tools }: {
  recipe: Recipe; onChange: (r: Recipe) => void; bases: BaseInfo[]; tools: Tool[];
}) {
  const [q, setQ] = useState("");
  const [more, setMore] = useState(!!(recipe.apt.length || recipe.pip.length || recipe.npm.length || recipe.setup || recipe.dockerfile));
  const base = bases.find((b) => b.id === recipe.base);
  const groups = useMemo(() => {
    const by = new Map<string, Tool[]>();
    tools.filter((t) => !q || `${t.label} ${t.group} ${t.id}`.toLowerCase().includes(q.toLowerCase()))
      .forEach((t) => by.set(t.group, [...(by.get(t.group) ?? []), t]));
    return [...by.entries()];
  }, [tools, q]);
  const total = sizeOf(recipe, bases, tools);
  const toggle = (id: string) => onChange({ ...recipe, tools: recipe.tools.includes(id) ? recipe.tools.filter((t) => t !== id) : [...recipe.tools, id] });

  return (
    <div className="grid gap-5">
      <div>
        <p className="mb-2 text-[13px] font-medium text-text">1. Pick a base</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {bases.map((b) => {
            const Icon = BASE_ICON[b.id];
            const on = recipe.base === b.id;
            return (
              <motion.button key={b.id} type="button" whileHover={{ y: -2 }} transition={spring} onClick={() => onChange({ ...recipe, base: b.id })}
                className={cn("relative grid gap-1 rounded-xl border p-3 text-left shadow-sm transition-colors",
                  on ? "border-accent bg-accent-soft" : "border-border bg-surface hover:border-border-strong")}>
                <span className="flex items-center gap-2 text-sm font-medium text-text"><Icon className="size-4 text-accent" />{b.label}</span>
                <span className="text-xs text-muted">{b.includes}</span>
                <span className="font-mono text-[11px] text-faint">{mb(b.mb)}</span>
                {on && <motion.span layoutId="base-tick" transition={spring} className="absolute right-2 top-2 grid size-5 place-items-center rounded-full bg-accent text-accent-fg"><Check className="size-3" /></motion.span>}
              </motion.button>
            );
          })}
        </div>
      </div>

      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-[13px] font-medium text-text">2. Tick extra tools</p>
          <label className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 size-3.5 text-faint" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search tools" className="h-8 w-48 pl-8 text-[13px]" />
          </label>
        </div>
        <div className="max-h-72 overflow-y-auto rounded-xl border border-border bg-surface p-2">
          {groups.map(([group, ts]) => (
            <div key={group} className="mb-2">
              <p className="px-2 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wide text-faint">{group}</p>
              <div className="grid gap-0.5 sm:grid-cols-2">
                {ts.map((t) => {
                  const inBase = base?.tools.includes(t.id);
                  return (
                    <label key={t.id} className={cn("flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-[13px] hover:bg-surface-2", inBase && "opacity-60")}>
                      <Checkbox checked={inBase || recipe.tools.includes(t.id)} disabled={inBase} onChange={() => toggle(t.id)} />
                      <span className="flex-1 text-text">{t.label}</span>
                      <span className="font-mono text-[11px] text-faint">{inBase ? "in base" : mb(t.mb)}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        <SizeMeter mb={total} />
      </div>

      <div>
        <button type="button" onClick={() => setMore(!more)} className="flex items-center gap-1 text-[13px] font-medium text-muted hover:text-text">
          <ChevronDown className={cn("size-4 transition-transform", more && "rotate-180")} /> 3. Optional extras
        </button>
        {more && (
          <div className="mt-3 grid gap-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="apt packages" hint="by name, spaces or commas">
                <Input value={recipe.apt.join(" ")} onChange={(e) => onChange({ ...recipe, apt: words(e.target.value) })} className="h-9 font-mono text-xs" />
              </Field>
              <Field label="pip packages">
                <Input value={recipe.pip.join(" ")} onChange={(e) => onChange({ ...recipe, pip: words(e.target.value) })} className="h-9 font-mono text-xs" />
              </Field>
              <Field label="npm packages">
                <Input value={recipe.npm.join(" ")} onChange={(e) => onChange({ ...recipe, npm: words(e.target.value) })} className="h-9 font-mono text-xs" />
              </Field>
            </div>
            <Field label="Setup script" hint="Runs once as root while the image is built, e.g. to download a dataset every lab uses.">
              <TextArea rows={3} value={recipe.setup} onChange={(e) => onChange({ ...recipe, setup: e.target.value })} className="font-mono text-xs" />
            </Field>
            <Field label="Raw Dockerfile (instead of all of the above)" hint="An admin has to approve it before it is built. Keep a student user with uid 1000.">
              <TextArea rows={3} value={recipe.dockerfile} onChange={(e) => onChange({ ...recipe, dockerfile: e.target.value })} className="font-mono text-xs" />
            </Field>
          </div>
        )}
      </div>
    </div>
  );
}

export function SizeMeter({ mb: size }: { mb: number }) {
  const pct = Math.min(100, (size / 3000) * 100);
  const tone = size > 2500 ? "bg-danger" : size > 1500 ? "bg-warn" : "bg-success";
  return (
    <div className="mt-2 flex items-center gap-3 text-xs text-muted">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-3">
        <motion.div className={cn("h-full rounded-full", tone)} initial={false} animate={{ width: `${pct}%` }} transition={spring} />
      </div>
      <span className="w-28 text-right font-mono">about {mb(size)}</span>
    </div>
  );
}

/** New recipe, or one of the environments this teacher may use (own and shared). */
export function EnvironmentPicker({ value, onChange }: { value: EnvChoice; onChange: (c: EnvChoice) => void }) {
  const { bases, tools } = useCatalogue();
  const [envs, setEnvs] = useState<Environment[]>([]);
  useEffect(() => { get<Environment[]>("/api/sandbox/environments").then(setEnvs, () => {}); }, []);
  const ready = envs.filter((e) => e.versions.length);

  return (
    <div className="grid gap-4">
      {ready.length > 0 && (
        <div className="flex rounded-lg border border-border bg-surface-2 p-0.5 text-[13px]">
          {(["new", "reuse"] as const).map((k) => (
            <button key={k} type="button" onClick={() => onChange(k === "new" ? { kind: "new", recipe: emptyRecipe() } : { kind: "reuse", environment_id: ready[0].id })}
              className={cn("relative flex-1 rounded-md px-3 py-1.5 font-medium", value.kind === k ? "text-text" : "text-muted")}>
              {value.kind === k && <motion.span layoutId="env-mode" transition={spring} className="absolute inset-0 rounded-md bg-surface shadow-sm" />}
              <span className="relative">{k === "new" ? "Build a new one" : "Reuse an environment"}</span>
            </button>
          ))}
        </div>
      )}
      {value.kind === "new" ? (
        <RecipeEditor recipe={value.recipe} onChange={(recipe) => onChange({ kind: "new", recipe })} bases={bases} tools={tools} />
      ) : (
        <div className="grid gap-2">
          {ready.map((e) => {
            const v = e.versions[e.versions.length - 1];
            const Icon = BASE_ICON[v.recipe.base] ?? BASE_ICON.linux;
            return (
              <label key={e.id} className={cn("flex cursor-pointer items-center gap-3 rounded-xl border p-3",
                value.environment_id === e.id ? "border-accent bg-accent-soft" : "border-border bg-surface hover:border-border-strong")}>
                <input type="radio" className="sr-only" checked={value.environment_id === e.id} onChange={() => onChange({ kind: "reuse", environment_id: e.id })} />
                <Icon className="size-4 text-accent" />
                <span className="flex-1">
                  <span className="block text-sm font-medium text-text">{e.title}</span>
                  <span className="block text-xs text-muted">
                    {v.recipe.tools.length ? v.recipe.tools.join(", ") : "base tools only"} · v{v.version} · {mb(v.size_mb)}
                  </span>
                </span>
                {!e.mine && <Badge tone="accent"><Share2 className="size-3" /> shared</Badge>}
                <BuildBadge status={v.status} />
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}
