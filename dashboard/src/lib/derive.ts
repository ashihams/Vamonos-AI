import { changePct, num, total } from "./format";
import type { DashboardRun, IterationRecord, TaskRow, VersionStats } from "./types";

export type Outcome = "kept" | "rolled back" | "declined";

export function outcomeOf(record: IterationRecord): Outcome {
  if (!record.decision.approved) return "declined";
  return record.accepted ? "kept" : "rolled back";
}

export interface RunMetrics {
  baseline: VersionStats;
  final: VersionStats;
  unitChangePct: number;
  spendUsd: number;
  tasksRun: number;
  inputTokens: number;
  outputTokens: number;
  calls: number;
  kept: number;
  rolledBack: number;
  declined: number;
  cheapestRejected: { stats: VersionStats; record: IterationRecord } | null;
}

export function runMetrics(run: DashboardRun): RunMetrics {
  const { baseline, final, versions, iterations } = run.report;
  const spendUsd = versions.reduce((sum, stats) => sum + total(stats.totals), 0);
  const calls = run.tasks.flatMap((task) => task.calls);
  const outcomes = iterations.map(outcomeOf);
  return {
    baseline,
    final,
    unitChangePct: changePct(
      num(baseline.cost_per_successful_task),
      num(final.cost_per_successful_task),
    ),
    spendUsd,
    tasksRun: run.tasks.length,
    inputTokens: calls.reduce((sum, call) => sum + call.input_tokens, 0),
    outputTokens: calls.reduce((sum, call) => sum + call.output_tokens, 0),
    calls: calls.length,
    kept: outcomes.filter((o) => o === "kept").length,
    rolledBack: outcomes.filter((o) => o === "rolled back").length,
    declined: outcomes.filter((o) => o === "declined").length,
    cheapestRejected: cheapestRejected(versions, iterations),
  };
}

function cheapestRejected(
  versions: VersionStats[],
  iterations: IterationRecord[],
): RunMetrics["cheapestRejected"] {
  let best: RunMetrics["cheapestRejected"] = null;
  for (const record of iterations) {
    if (record.accepted || record.candidate_version === null) continue;
    const stats = versions.find((v) => v.version === record.candidate_version);
    if (!stats) continue;
    const unit = num(stats.cost_per_successful_task);
    if (best === null || unit < num(best.stats.cost_per_successful_task)) {
      best = { stats, record };
    }
  }
  return best;
}

export function iterationFor(run: DashboardRun, version: number): IterationRecord | undefined {
  return run.report.iterations.find((record) => record.candidate_version === version);
}

export function tierShare(tasks: TaskRow[]): { cheap: number; strong: number } {
  const calls = tasks.flatMap((task) => task.calls);
  const cheap = calls.filter((call) => call.tier === "cheap").length;
  return { cheap, strong: calls.length - cheap };
}

export function versionLabel(stats: VersionStats): string {
  return `v${stats.version}`;
}
