import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface StatProps {
  icon: LucideIcon;
  label: string;
  value: ReactNode;
  detail?: ReactNode;
}

/** Bento metric: icon tile, mono label, large figure, one line of context. */
export function Stat({ icon: Icon, label, value, detail }: StatProps) {
  return (
    <div className="flex h-full flex-col justify-between gap-4 p-6">
      <div className="flex items-center gap-3">
        <span className="grid size-9 place-items-center rounded-xl border border-white/10 bg-white/[0.04] shadow-inner-hi">
          <Icon aria-hidden className="size-4 text-[#a5acf0]" />
        </span>
        <span className="label-mono">{label}</span>
      </div>
      <div>
        <div className="text-gradient text-3xl font-semibold tracking-tight tabular-nums md:text-4xl">{value}</div>
        {detail && <div className="mt-1.5 text-sm leading-relaxed text-fg-muted">{detail}</div>}
      </div>
    </div>
  );
}
