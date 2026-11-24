import { forwardRef } from "react";
import { motion, type HTMLMotionProps } from "motion/react";
import { cn } from "./cn";
import { spring } from "./motion";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg" | "icon";

const variants: Record<Variant, string> = {
  /* Borders, not fills (Rohan's guideline): every button is text at rest; on
     hover or keyboard focus a border pops in (with a lift and, for the main
     action, a lime glow). See the border-first section of ui/README.md. */
  primary: "font-semibold text-cta hover:border-cta hover:shadow-[var(--button-glow)] focus-visible:border-cta focus-visible:shadow-[var(--button-glow)]",
  secondary: "text-text hover:border-border-strong focus-visible:border-border-strong",
  ghost: "text-muted hover:text-text hover:border-border focus-visible:border-border",
  danger: "text-danger hover:border-danger/70 focus-visible:border-danger/70",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5 rounded-md",
  md: "h-9 px-4 text-sm gap-2 rounded-[10px]",
  lg: "h-11 px-5 text-[15px] gap-2 rounded-xl",
  icon: "size-8 rounded-md",
};

export interface ButtonProps extends HTMLMotionProps<"button"> {
  variant?: Variant;
  size?: Size;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", className, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <motion.button
      ref={ref}
      type={type}
      disabled={disabled}
      whileHover={disabled ? undefined : { y: -1 }}
      whileTap={disabled ? undefined : { scale: 0.97, y: 0 }}
      transition={spring}
      className={cn(
        "inline-flex select-none items-center justify-center whitespace-nowrap border border-transparent bg-transparent font-medium",
        "transition-[background-color,border-color,color,opacity,box-shadow] duration-150",
        "disabled:cursor-not-allowed disabled:opacity-45",
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    />
  );
});
