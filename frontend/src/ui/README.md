# Student IDE design system

Shared look and motion for the student editor and the teacher dashboard.
React 18 + Tailwind CSS v4 + [Motion](https://motion.dev).

## Pieces

| file | what |
|------|------|
| `tokens.css` | Semantic colour tokens (`--surface`, `--accent`, `--syn-*` …) with light and dark themes, fonts (Inter, JetBrains Mono, self-hosted), keyframes. Exposed to Tailwind as `bg-surface`, `text-muted`, `border-border`, `bg-accent-soft`, etc. Import once at the app entry. |
| `motion.ts` | Durations, easings, springs and variants (`page`, `stagger`, `item`, `pop`, `fade`). |
| `Button`, `Input`/`TextArea`/`Field`/`Checkbox`, `Badge`/`LiveDot`/`Kbd`/`Spinner`, `Card`, `Dialog`, `Stepper`, `Logo` | Primitives. |
| `AppShell` (+ `Breadcrumbs`, `TopBarButton`) | App frame: left sidebar of sections, top bar with breadcrumbs and actions, drawer below `lg`. The teacher area uses it (`review/ReviewApp.tsx`, `SECTIONS`). |
| `Page`, `PageHeader`, `EmptyState` | Page body width, title row (title, description, actions on the right), and empty states that say what to do next. New pages should use these instead of hand-rolled headers. |
| `CommandPalette` (+ `useCommandPalette`, `SearchButton`) | Ctrl+K / ⌘K jump list of pages plus loaded items (labs, subjects). Never mount it on a screen that records typing. |
| `RhythmBars` | One bar per inter-key interval; pauses drawn muted. Used on sign-in and in the review replay. |
| `TypingDemo` | Self-typing code card with a live rhythm strip (sign-in screen). |

Everything is re-exported from `ui/index.ts`.

## Look

"Acid Night": ink backgrounds, one lime accent (`cta`, `brand`) and a pink second accent
(`accent-2`, used for badges and highlights). Space Grotesk (`font-display`) for page titles, Inter
for the interface, JetBrains Mono for code and roll numbers. Dark mode adds a faint pink and lime
glow behind the page (`--bg-glow`); light mode is warm off-white with ink text and darker lime.

### Border-first (Rohan's guideline)

- No background fills for emphasis. Cards, tabs, rows and badges sit on the page background.
- Borders separate things only when they must stand apart from their siblings (a card in a grid,
  an input, the selected item).
- Buttons are text at rest. On hover or keyboard focus a border pops in with a 1 px lift; the
  primary button also glows lime (`--button-glow`). Danger buttons are red text with a red border on hover.
- Active and selected states use a border, an underline or a left rule plus accent text, never a
  filled pill.
- Fills stay only where they do a job: the page base, dialog scrims and panels, the code editor,
  the console, images and charts.

## Theme

The theme follows the OS. Force one with `document.documentElement.dataset.theme = "light" | "dark"`.
`--ch-identity` / `--ch-process` colour the two detector channels on the review timeline (validated as a
colour-vision-safe pair in both themes); always pair them with the channel name.

Prefer the semantic utilities over raw Tailwind colours so both themes stay correct.

## Motion rules (important for the research data)

Keystroke timing is the thesis's raw signal, so on any screen that records:

1. Never animate per keystroke, and never put the CodeMirror document in React
   state. The editor is created once and left alone.
2. Animate only `opacity` and `transform`, and only on discrete actions
   (a run, a dialog, a screen change).
3. Keep durations short (`duration.fast`/`base`/`slow`). `MotionConfig
   reducedMotion="user"` and a CSS media query honour the OS reduced-motion setting.

`frontend/e2e/record.mjs` fails if any main-thread task over 50 ms overlaps the
typing window.

## Page recipe

Every staff page and every student screen outside the editor follows the same shape:

```tsx
<Page>                                   {/* wide for boards and timelines */}
  <PageHeader title="Labs" description="One sentence on what this page is for."
    actions={<><Button>Secondary</Button><Button variant="primary">New lab</Button></>} />
  {loading ? <Skeleton/> : rows.length ? <List/> : <EmptyState icon={…} title="No labs yet" action={…}>What to do first.</EmptyState>}
</Page>
```

- Back links live in the top-bar breadcrumbs (`trail()` in `routes.ts`), not as "← Back" rows above the title.
  Student screens have no breadcrumbs, so they keep a quiet back button.
- Section headings inside a page: `text-[15px] font-semibold`, sentence case. No uppercase/tracked labels.
- Lists of things are one bordered container with divided rows (`divide-y divide-border`), not a stack of
  separate floating cards; use cards for genuinely separate objects (a tile grid, a summary panel).
- Numbers that change or line up use `tabular-nums`. Mono only for code, roll numbers and ids.
- Errors say what failed and what to do; empty states say what to do first.
