// Shared motion vocabulary. Keep animations short, ease-out, and limited to
// opacity and transform so they stay on the compositor. Screens that capture
// keystrokes must only animate in response to discrete actions (a run, a
// dialog), never per keystroke.

import type { Transition, Variants } from "motion/react";

export const ease = {
  out: [0.22, 1, 0.36, 1] as const,
  inOut: [0.65, 0, 0.35, 1] as const,
};

export const duration = { fast: 0.15, base: 0.24, slow: 0.42 };

export const spring: Transition = { type: "spring", stiffness: 420, damping: 32, mass: 0.8 };
export const softSpring: Transition = { type: "spring", stiffness: 220, damping: 26 };

/** Whole-screen enter/exit. */
export const page: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: duration.slow, ease: ease.out } },
  exit: { opacity: 0, y: -8, transition: { duration: duration.fast, ease: ease.inOut } },
};

/** Parent that reveals its `item` children one after another. */
export const stagger = (gap = 0.06, delay = 0.05): Variants => ({
  initial: {},
  animate: { transition: { staggerChildren: gap, delayChildren: delay } },
});

export const item: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: duration.slow, ease: ease.out } },
};

export const pop: Variants = {
  initial: { opacity: 0, scale: 0.96, y: 6 },
  animate: { opacity: 1, scale: 1, y: 0, transition: spring },
  exit: { opacity: 0, scale: 0.98, y: 4, transition: { duration: duration.fast } },
};

export const fade: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: duration.base } },
  exit: { opacity: 0, transition: { duration: duration.fast } },
};
