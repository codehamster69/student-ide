import { forwardRef, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from "react";
import { cn } from "./cn";

const control =
  "w-full rounded-lg border border-border bg-surface px-3 text-sm text-text shadow-sm outline-none " +
  "placeholder:text-faint transition-[border-color,box-shadow] duration-150 " +
  "hover:border-border-strong focus:border-accent focus:ring-4 focus:ring-accent/15";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} className={cn(control, "h-11", className)} {...rest} />;
});

export const TextArea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function TextArea(
  { className, ...rest },
  ref,
) {
  return <textarea ref={ref} className={cn(control, "py-2", className)} {...rest} />;
});

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="grid gap-1.5">
      <span className="text-[13px] font-medium text-text">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </label>
  );
}

/** Native checkbox, restyled, so it stays keyboard and test friendly. */
export function Checkbox({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="checkbox"
      className={cn(
        "peer size-[18px] shrink-0 cursor-pointer appearance-none rounded-[5px] border border-border-strong bg-surface",
        "transition-[background-color,border-color,box-shadow] duration-150",
        "checked:border-accent checked:bg-accent focus-visible:ring-4 focus-visible:ring-accent/20",
        "sid-checkbox",
        className,
      )}
      {...rest}
    />
  );
}
