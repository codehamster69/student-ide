# Student IDE design system

Shared look and motion for the student editor and the teacher dashboard.
React 18 + Tailwind CSS v4 + [Motion](https://motion.dev).

## Pieces

| file | what |
|------|------|
| `tokens.css` | Semantic colour tokens (`--surface`, `--accent`, `--syn-*` …) with light and dark themes, fonts (Inter, JetBrains Mono, self-hosted), keyframes. Exposed to Tailwind as `bg-surface`, `text-muted`, `border-border`, `bg-accent-soft`, etc. Import once at the app entry. |
| `motion.ts` | Durations, easings, springs and variants (`page`, `stagger`, `item`, `pop`, `fade`). |
| `Button`, `Input`/`TextArea`/`Field`/`Checkbox`, `Badge`/`LiveDot`/`Kbd`/`Spinner`, `Card`, `Dialog`, `Stepper`, `Logo` | Primitives. |
| `RhythmBars` | One bar per inter-key interval; pauses drawn muted. Intended for the teacher timeline. |
| `TypingDemo` | Self-typing code card with a live rhythm strip (sign-in screen). |

Everything is re-exported from `ui/index.ts`.

## Theme

The theme follows the OS. Force one with `document.documentElement.dataset.theme = "light" | "dark"`.
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
