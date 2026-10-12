import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import { fadeUp, inView, stagger } from "../../lib/motion";

interface SectionProps {
  id: string;
  label: string;
  title: ReactNode;
  description?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** Page section: mono label, gradient title, optional controls, staggered reveal. */
export function Section({ id, label, title, description, aside, children, className }: SectionProps) {
  const headingId = `${id}-title`;
  return (
    <section id={id} aria-labelledby={headingId} className={cn("relative border-t border-line py-16 md:py-24 lg:py-28", className)}>
      <div aria-hidden className="hairline absolute inset-x-0 -top-px h-px" />
      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={inView}
        variants={stagger}
        className="mx-auto w-full max-w-7xl px-5 md:px-8"
      >
        <motion.header variants={fadeUp} className="mb-10 flex flex-col gap-6 md:mb-14 md:flex-row md:items-end md:justify-between">
          <div className="max-w-2xl">
            <p className="label-mono mb-4">{label}</p>
            <h2 id={headingId} className="text-gradient text-3xl font-semibold leading-tight tracking-tight md:text-4xl">
              {title}
            </h2>
            {description && <p className="mt-4 text-base leading-relaxed text-fg-muted md:text-lg">{description}</p>}
          </div>
          {aside && <div className="shrink-0">{aside}</div>}
        </motion.header>
        {children}
      </motion.div>
    </section>
  );
}
