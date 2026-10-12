import { motion } from "framer-motion";
import { Badge, type Tone } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Section } from "../components/ui/Section";
import { iterationFor } from "../lib/derive";
import { humanize, ms, num, pct, total, usd } from "../lib/format";
import { EXPO_OUT } from "../lib/motion";
import type { DashboardRun, VersionStats } from "../lib/types";

const STATUS_TONE: Record<VersionStats["status"], Tone> = { baseline: "accent", kept: "pass", "rolled back": "block" };

const PARTS = [
  { key: "model_usd", label: "Model", note: "measured tokens × proxy prices", color: "bg-accent" },
  { key: "infra_usd", label: "Infra", note: "modeled from wall time", color: "bg-[#a78bfa]" },
  { key: "data_usd", label: "Data", note: "credits × configured price", color: "bg-[#38bdf8]" },
] as const;

export function Versions({ run }: { run: DashboardRun }) {
  const { versions } = run.report;
  const maxTotal = Math.max(...versions.map((stats) => total(stats.totals)));
  return (
    <Section
      id="versions"
      label="04 · Versions"
      title="Where the money goes"
      description="Model calls dominate the bill. Infrastructure is modeled from wall time, and data is shown at the configured price per Crustdata credit, which is still $0 because the hackathon credits were free."
    >
      <div className="grid gap-4">
        <Card lift={false} className="overflow-hidden">
          <div className="scrollbar-thin overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <caption className="sr-only">Quality, cost, and latency for each evaluated config version</caption>
              <thead>
                <tr className="border-b border-line text-fg-muted">
                  {["Version", "Change", "Eval", "Held-out", "Cost / success", "p95"].map((head) => (
                    <th key={head} scope="col" className="label-mono px-5 py-4 font-normal whitespace-nowrap">
                      {head}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {versions.map((stats) => {
                  const record = iterationFor(run, stats.version);
                  return (
                    <tr key={stats.version} className="border-b border-line/60 whitespace-nowrap transition-colors duration-200 last:border-0 hover:bg-white/[0.03]">
                      <th scope="row" className="px-5 py-4 font-mono font-medium">
                        <span className="mr-2">v{stats.version}</span>
                        <Badge tone={STATUS_TONE[stats.status]}>{stats.status}</Badge>
                      </th>
                      <td className="px-5 py-4 text-fg-muted">{record ? humanize(record.proposal.lever) : "starting config"}</td>
                      <td className="px-5 py-4 tabular-nums">{pct(stats.eval_success_rate)}</td>
                      <td className="px-5 py-4 tabular-nums">{pct(stats.heldout_success_rate)}</td>
                      <td className="px-5 py-4 font-mono tabular-nums text-fg">{usd(num(stats.cost_per_successful_task), 4)}</td>
                      <td className="px-5 py-4 tabular-nums text-fg-muted">{ms(stats.p95_latency_ms)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        <Card lift={false} className="p-6">
          <p className="label-mono">Spend per version, by component</p>
          <ul className="mt-6 grid gap-6 md:grid-cols-3 md:gap-8">
            {versions.map((stats, index) => (
              <SplitBar key={stats.version} stats={stats} index={index} scale={maxTotal} />
            ))}
          </ul>
          <ul className="mt-8 flex flex-col gap-2 border-t border-line pt-5 text-xs text-fg-muted md:flex-row md:gap-8">
            {PARTS.map((part) => (
              <li key={part.key} className="flex items-center gap-2.5">
                <span aria-hidden className={`size-2 rounded-full ${part.color}`} />
                <span className="text-fg">{part.label}</span> {part.note}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </Section>
  );
}

function SplitBar({ stats, index, scale }: { stats: VersionStats; index: number; scale: number }) {
  const sum = total(stats.totals);
  return (
    <li>
      <div className="mb-2 flex items-baseline justify-between text-sm">
        <span className="font-mono">v{stats.version}</span>
        <span className="font-mono tabular-nums text-fg-muted">{usd(sum, 4)} total</span>
      </div>
      <div
        className="flex h-2.5 overflow-hidden rounded-full bg-white/[0.05]"
        role="img"
        aria-label={PARTS.map((part) => `${part.label} ${usd(num(stats.totals[part.key]), 6)}`).join(", ")}
      >
        {PARTS.map((part) => {
          const share = scale > 0 ? (num(stats.totals[part.key]) / scale) * 100 : 0;
          return (
            <motion.span
              key={part.key}
              className={`${part.color} h-full first:rounded-l-full last:rounded-r-full`}
              initial={{ width: 0 }}
              whileInView={{ width: `${share}%` }}
              viewport={{ once: true }}
              transition={{ duration: 0.8, delay: index * 0.08, ease: EXPO_OUT }}
              style={{ minWidth: share > 0 ? 3 : 0 }}
            />
          );
        })}
      </div>
      <div className="mt-2 flex gap-4 font-mono text-[11px] text-fg-muted tabular-nums">
        {PARTS.map((part) => (
          <span key={part.key}>
            {part.label.toLowerCase()} {usd(num(stats.totals[part.key]), part.key === "model_usd" ? 2 : 4)}
          </span>
        ))}
      </div>
    </li>
  );
}
