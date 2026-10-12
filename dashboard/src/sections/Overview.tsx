import { motion } from "framer-motion";
import { Activity, CircleDollarSign, Gauge, GitBranch, ShieldCheck, Sparkles, Timer } from "lucide-react";
import { TrajectoryChart } from "../components/charts/TrajectoryChart";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Section } from "../components/ui/Section";
import { Stat } from "../components/ui/Stat";
import type { RunMetrics } from "../lib/derive";
import { compact, ms, num, pct, signedPct, usd } from "../lib/format";
import { stagger } from "../lib/motion";
import type { DashboardRun } from "../lib/types";

interface OverviewProps {
  run: DashboardRun;
  metrics: RunMetrics;
}

export function Overview({ run, metrics }: OverviewProps) {
  const { baseline, final } = metrics;
  const rejected = metrics.cheapestRejected;
  const flat = Math.abs(metrics.unitChangePct) < 1;

  return (
    <Section
      id="overview"
      label="01 · Overview"
      title="Cost per successful task, version by version"
      description="Every version below ran on the same full workload. Success is checked against rule-based labels, on an evaluation split the optimizer sees and a held-out split it never sees."
    >
      <motion.div variants={stagger} className="grid grid-cols-1 gap-4 md:grid-cols-6 md:auto-rows-[180px]">
        <Card variant="gradient" className="md:col-span-4 md:row-span-2">
          <div className="flex h-full flex-col p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="label-mono">Cost per successful task</p>
                <p className="mt-3 flex items-baseline gap-3 tabular-nums">
                  <span className="text-gradient text-4xl font-semibold tracking-tight md:text-5xl">
                    {usd(num(final.cost_per_successful_task), 4)}
                  </span>
                  <span className="text-sm text-fg-muted">
                    from {usd(num(baseline.cost_per_successful_task), 4)} at v{baseline.version}
                  </span>
                </p>
              </div>
              <Badge tone={flat ? "neutral" : metrics.unitChangePct < 0 ? "pass" : "block"} icon={Activity}>
                {signedPct(metrics.unitChangePct, 2)} · {flat ? "no real saving" : metrics.unitChangePct < 0 ? "cheaper" : "dearer"}
              </Badge>
            </div>
            <div className="mt-4 min-h-[220px] flex-1 md:min-h-0">
              <TrajectoryChart versions={run.report.versions} />
            </div>
          </div>
        </Card>

        <Card className="md:col-span-2">
          <Stat
            icon={ShieldCheck}
            label="Eval success"
            value={pct(final.eval_success_rate)}
            detail={`v${final.version} on ${final.eval_tasks} tasks · baseline ${pct(baseline.eval_success_rate)}`}
          />
        </Card>
        <Card className="md:col-span-2">
          <Stat
            icon={Gauge}
            label="Held-out success"
            value={pct(final.heldout_success_rate)}
            detail={`${final.heldout_tasks} tasks the optimizer never sees · baseline ${pct(baseline.heldout_success_rate)}`}
          />
        </Card>

        <Card className="md:col-span-2">
          <Stat
            icon={CircleDollarSign}
            label="Spend across versions"
            value={usd(metrics.spendUsd, 2)}
            detail={`${metrics.tasksRun} tasks · ${metrics.calls} model calls`}
          />
        </Card>
        <Card className="md:col-span-2">
          <Stat
            icon={Timer}
            label="p95 latency"
            value={ms(final.p95_latency_ms)}
            detail={`v${final.version} · baseline ${ms(baseline.p95_latency_ms)} · cold starts excluded`}
          />
        </Card>
        <Card className="md:col-span-2">
          <Stat
            icon={GitBranch}
            label="Iterations"
            value={
              <span className="flex items-baseline gap-3">
                {run.report.iterations.length}
                <span className="text-base font-normal text-fg-muted">
                  {metrics.kept} kept · {metrics.rolledBack} rolled back
                  {metrics.declined > 0 && ` · ${metrics.declined} declined`}
                </span>
              </span>
            }
            detail={`accepted config: v${final.version}`}
          />
        </Card>

        {rejected ? (
          <Card variant="glass" className="md:col-span-4">
            <div className="flex h-full flex-col justify-between gap-4 p-6 md:flex-row md:items-center">
              <div className="max-w-xl">
                <p className="label-mono flex items-center gap-2">
                  <Sparkles aria-hidden className="size-3.5 text-[#a5acf0]" /> The saving it refused
                </p>
                <p className="mt-3 text-lg leading-relaxed text-fg md:text-xl">
                  v{rejected.stats.version} cut the unit cost to{" "}
                  <span className="font-semibold text-[#b4bbf5]">{usd(num(rejected.stats.cost_per_successful_task), 4)}</span>, but
                  held-out success fell to <span className="font-semibold text-[#ff8589]">{pct(rejected.stats.heldout_success_rate, 0)}</span>.
                  The guardrails rolled it back.
                </p>
              </div>
              <Badge tone="block" className="self-start md:self-center">
                {rejected.record.proposal.lever.replaceAll("_", " ")} · rolled back
              </Badge>
            </div>
          </Card>
        ) : (
          <Card variant="glass" className="md:col-span-4">
            <Stat icon={Sparkles} label="Rejected candidates" value="None" detail="Every evaluated change was kept." />
          </Card>
        )}
        <Card className="md:col-span-2">
          <Stat
            icon={Activity}
            label="Tokens"
            value={compact(metrics.inputTokens + metrics.outputTokens)}
            detail={`${compact(metrics.inputTokens)} in · ${compact(metrics.outputTokens)} out`}
          />
        </Card>
      </motion.div>
    </Section>
  );
}
