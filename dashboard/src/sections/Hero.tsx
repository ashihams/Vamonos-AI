import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { ArrowDown, FolderGit2 } from "lucide-react";
import { type ReactNode, useRef } from "react";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { outcomeOf } from "../lib/derive";
import { changePct, jsonInline, num, signedPct } from "../lib/format";
import { REPO_URL } from "../lib/links";
import { fadeUp, scaleIn, stagger } from "../lib/motion";
import type { DashboardRun } from "../lib/types";

export function Hero({ run }: { run: DashboardRun }) {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const opacity = useTransform(scrollYProgress, [0, 0.45], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.45], [1, 0.95]);
  const y = useTransform(scrollYProgress, [0, 0.45], [0, 100]);
  const { report } = run;

  return (
    <section ref={ref} id="top" aria-labelledby="hero-title" className="relative overflow-hidden pb-16 pt-16 md:pb-24 md:pt-24 lg:pt-28">
      <motion.div
        initial="hidden"
        animate="show"
        variants={stagger}
        className="mx-auto flex max-w-7xl flex-col items-center px-5 text-center md:px-8"
      >
        <motion.div style={reduce ? undefined : { opacity, scale, y }} className="flex flex-col items-center">
        <motion.div variants={fadeUp}>
          <Badge tone="accent" className="mb-8 px-3 py-1 font-mono text-[11px] tracking-widest uppercase">
            neatHack 2026 · recorded run {report.run_id}
          </Badge>
        </motion.div>

        <motion.h1
          id="hero-title"
          variants={fadeUp}
          className="max-w-5xl text-4xl font-semibold leading-[1.02] tracking-[-0.03em] md:text-6xl lg:text-7xl xl:text-8xl"
        >
          <span className="text-gradient">Cut the cost of AI.</span>
          <br />
          <span className="text-gradient-accent animate-shimmer">Only when it stays right.</span>
        </motion.h1>

        <motion.p variants={fadeUp} className="mt-8 max-w-2xl text-base leading-relaxed text-fg-muted md:text-lg lg:text-xl">
          costwise is an optimizer agent for a company-qualification AI app. It proposes one change, re-runs the whole
          workload, and keeps the change only if every guardrail passes and the cost per successful task goes down.
        </motion.p>

        <motion.div variants={fadeUp} className="mt-10 flex flex-col gap-3 sm:flex-row">
          <Button href="#iterations" icon={ArrowDown}>
            See what the agent tried
          </Button>
          <Button href={REPO_URL} variant="secondary" icon={FolderGit2} external>
            Read the source
          </Button>
        </motion.div>
        </motion.div>

        <motion.div variants={scaleIn} className="mt-16 w-full max-w-4xl md:mt-20">
          <TerminalMock run={run} />
        </motion.div>
      </motion.div>
    </section>
  );
}

function TerminalMock({ run }: { run: DashboardRun }) {
  const { report } = run;
  const change = changePct(num(report.baseline.cost_per_successful_task), num(report.final.cost_per_successful_task));
  return (
    <figure className="relative rounded-2xl bg-bg-elevated/90 text-left shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_24px_80px_rgba(0,0,0,0.6),0_0_120px_rgba(94,106,210,0.18),inset_0_1px_0_0_rgba(255,255,255,0.08)] backdrop-blur-xl">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <span className="size-2.5 rounded-full bg-white/10" />
        <span className="size-2.5 rounded-full bg-white/10" />
        <span className="size-2.5 rounded-full bg-white/10" />
        <span className="ml-3 font-mono text-xs text-fg-muted">costwise — {report.run_id}</span>
      </div>
      <pre className="scrollbar-thin overflow-x-auto p-5 font-mono text-[12.5px] leading-6 md:p-6 md:text-[13px]">
        <code>
          <Line prompt>costwise optimize --run-id {report.run_id}</Line>
          {report.iterations.map((record) => {
            const outcome = outcomeOf(record);
            const tone = outcome === "kept" ? "text-pass" : outcome === "declined" ? "text-warn" : "text-[#ff8589]";
            return (
              <Line key={record.iteration}>
                <span className="text-fg-muted">iteration {record.iteration}: </span>
                <span className="text-[#b4bbf5]">
                  {record.proposal.lever}={jsonInline(record.proposal.new_value)}
                </span>{" "}
                <span className={tone}>{outcome}</span>
                <span className="text-fg-muted"> ({record.reason})</span>
              </Line>
            );
          })}
          <Line>
            <span className="text-fg-muted">accepted config version: </span>
            <span className="text-fg">{report.final.version}</span>
          </Line>
          <Line prompt>costwise report --run-id {report.run_id}</Line>
          <Line>
            <span className="text-fg-muted">cost per successful task usd: </span>v{report.baseline.version}{" "}
            {num(report.baseline.cost_per_successful_task).toFixed(6)} → v{report.final.version}{" "}
            {num(report.final.cost_per_successful_task).toFixed(6)}{" "}
            <span className="text-fg-muted">({signedPct(change, 2)})</span>
          </Line>
        </code>
      </pre>
      <figcaption className="border-t border-line px-5 py-3 text-xs text-fg-muted md:px-6">
        Rebuilt from this run's stored iteration records, in the CLI's own output format.
      </figcaption>
    </figure>
  );
}

function Line({ children, prompt = false }: { children: ReactNode; prompt?: boolean }) {
  return (
    <span className="block whitespace-pre-wrap break-words">
      {prompt && <span className="select-none text-accent-bright">$ </span>}
      <span className={prompt ? "text-fg" : undefined}>{children}</span>
    </span>
  );
}
