import { motion, type HTMLMotionProps } from "motion/react";
import { cn } from "./cn";

export function Card({ className, ...rest }: HTMLMotionProps<"div">) {
  return <motion.div className={cn("rounded-xl border border-border", className)} {...rest} />;
}
