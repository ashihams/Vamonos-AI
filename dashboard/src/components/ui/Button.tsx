import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

type Variant = "primary" | "secondary" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent text-white shadow-cta hover:bg-accent-bright hover:shadow-cta-hover before:absolute before:inset-0 before:-translate-x-full before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent before:transition-transform before:duration-700 before:ease-expo hover:before:translate-x-full",
  secondary:
    "bg-white/[0.05] text-fg shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08),inset_0_1px_0_0_rgba(255,255,255,0.06)] hover:bg-white/[0.08] hover:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.12),0_0_24px_rgba(94,106,210,0.12)]",
  ghost: "text-fg-muted hover:bg-white/[0.05] hover:text-fg",
};

interface ButtonProps {
  children: ReactNode;
  href: string;
  variant?: Variant;
  icon?: LucideIcon;
  external?: boolean;
  className?: string;
}

/** Link styled as a button; every action on this site navigates. */
export function Button({ children, href, variant = "primary", icon: Icon, external, className }: ButtonProps) {
  return (
    <a
      href={href}
      {...(external ? { target: "_blank", rel: "noreferrer" } : {})}
      className={cn(
        "relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-lg px-4 py-2.5 text-sm font-medium transition-[background-color,box-shadow,color,transform] duration-200 ease-expo active:scale-[0.98]",
        VARIANTS[variant],
        className,
      )}
    >
      <span className="relative inline-flex items-center gap-2">
        {children}
        {Icon && <Icon aria-hidden className="size-4" />}
      </span>
      {external && <span className="sr-only"> (opens in a new tab)</span>}
    </a>
  );
}
