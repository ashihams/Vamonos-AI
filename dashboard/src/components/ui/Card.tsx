import { motion } from "framer-motion";
import { type CSSProperties, type MouseEvent, type ReactNode, useCallback, useRef } from "react";
import { fadeUp, standard } from "../../lib/motion";
import { cn } from "../../lib/cn";

type Variant = "default" | "glass" | "gradient";

const VARIANTS: Record<Variant, string> = {
  default: "bg-gradient-to-b from-white/[0.08] to-white/[0.02]",
  glass: "bg-white/[0.03] backdrop-blur-xl",
  gradient:
    "bg-[radial-gradient(120%_120%_at_0%_0%,rgba(94,106,210,0.16),transparent_55%),linear-gradient(to_bottom,rgba(255,255,255,0.07),rgba(255,255,255,0.02))]",
};

interface CardProps {
  children: ReactNode;
  className?: string;
  variant?: Variant;
  spotlight?: boolean;
  lift?: boolean;
  as?: "div" | "article" | "section" | "li";
}

/** Elevated surface: hairline border, top inner highlight, layered shadow, cursor spotlight. */
export function Card({
  children,
  className,
  variant = "default",
  spotlight = true,
  lift = true,
  as = "div",
}: CardProps) {
  const ref = useRef<HTMLElement>(null);
  const onMove = useCallback((event: MouseEvent<HTMLElement>) => {
    const node = ref.current;
    if (!node) return;
    const rect = node.getBoundingClientRect();
    node.style.setProperty("--spot-x", `${event.clientX - rect.left}px`);
    node.style.setProperty("--spot-y", `${event.clientY - rect.top}px`);
  }, []);

  const Tag = motion[as];
  return (
    <Tag
      ref={ref as never}
      variants={fadeUp}
      onMouseMove={spotlight ? onMove : undefined}
      whileHover={lift ? { y: -4, transition: standard } : undefined}
      style={{ "--spot-x": "50%", "--spot-y": "0px" } as CSSProperties}
      className={cn(
        "group/card relative isolate overflow-hidden rounded-2xl shadow-card transition-shadow duration-300 ease-expo hover:shadow-card-hover",
        VARIANTS[variant],
        className,
      )}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent"
      />
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl p-px opacity-0 transition-opacity duration-300 ease-expo [mask-composite:exclude] [mask:linear-gradient(#fff_0_0)_content-box,linear-gradient(#fff_0_0)] bg-gradient-to-b from-accent/40 to-transparent group-hover/card:opacity-100"
      />
      {spotlight && (
        <span
          aria-hidden
          className="pointer-events-none absolute -z-10 size-[300px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent/15 opacity-0 blur-3xl transition-opacity duration-300 ease-expo group-hover/card:opacity-100"
          style={{ left: "var(--spot-x)", top: "var(--spot-y)" }}
        />
      )}
      {children}
    </Tag>
  );
}
