import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

export type Tone = "neutral" | "accent" | "pass" | "block" | "warn";

const TONES: Record<Tone, string> = {
  neutral: "border-white/10 bg-white/[0.04] text-fg-muted",
  accent: "border-line-accent bg-accent/10 text-[#b4bbf5]",
  pass: "border-pass/30 bg-pass/10 text-pass",
  block: "border-block/30 bg-block/10 text-[#ff8589]",
  warn: "border-warn/30 bg-warn/10 text-warn",
};

interface BadgeProps {
  children: ReactNode;
  tone?: Tone;
  icon?: LucideIcon;
  className?: string;
}

/** Pill label; meaning is carried by text and icon, never by color alone. */
export function Badge({ children, tone = "neutral", icon: Icon, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
        TONES[tone],
        className,
      )}
    >
      {Icon && <Icon aria-hidden className="size-3.5" strokeWidth={2.25} />}
      {children}
    </span>
  );
}
