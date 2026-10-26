import { motion, type HTMLMotionProps } from "motion/react";
import { cn } from "./cn";

export function Card({ className, ...rest }: HTMLMotionProps<"div">) {
  return <motion.div className={cn("rounded-2xl border border-border bg-surface shadow-md", className)} {...rest} />;
}
