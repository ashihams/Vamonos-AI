import { motion } from "framer-motion";
import { type KeyboardEvent, useId } from "react";
import { cn } from "../../lib/cn";
import { quick } from "../../lib/motion";

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
  hint?: string;
}

interface SegmentedProps<T extends string> {
  label: string;
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: "sm" | "md";
}

/** Radio group with a sliding indicator; arrow keys move between options. */
export function Segmented<T extends string>({ label, options, value, onChange, size = "md" }: SegmentedProps<T>) {
  const groupId = useId();
  const index = options.findIndex((option) => option.value === value);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 0;
    if (step === 0) return;
    event.preventDefault();
    const next = options[(index + step + options.length) % options.length];
    if (next) onChange(next.value);
  };

  return (
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={onKeyDown}
      className="relative inline-flex rounded-lg bg-white/[0.04] p-1 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]"
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            title={option.hint}
            onClick={() => onChange(option.value)}
            className={cn(
              "relative rounded-md font-medium transition-colors duration-200 ease-expo",
              size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm",
              selected ? "text-fg" : "text-fg-muted hover:text-fg",
            )}
          >
            {selected && (
              <motion.span
                layoutId={`${groupId}-indicator`}
                transition={quick}
                className="absolute inset-0 rounded-md bg-white/[0.08] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.1),0_0_0_1px_rgba(255,255,255,0.08)]"
              />
            )}
            <span className="relative">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
