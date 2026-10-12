import { RotateCw } from "lucide-react";
import { Badge, type Tone } from "../ui/Badge";
import { ActionButton } from "../ui/Button";
import { changePct, humanize, num, pct, signedPct, usd } from "../../lib/format";
import { type ReplayPath, type ReplayStep, MAX_REJECTIONS_IN_A_ROW, versionOf } from "../../lib/replay";
import type { ReportData } from "../../lib/types";

function outcome(step: ReplayStep): { tone: Tone; label: string } {
  if (step.result.kind === "declined") return { tone: "warn", label: "rejected · no run" };
  if (step.result.kind === "not-run") return { tone: "neutral", label: "never ran in the recording" };
  return step.result.kept ? { tone: "pass", label: `kept · v${step.result.candidate.version}` } : { tone: "block", label: "rolled back" };
}

/** Where the visitor's decisions ended up, next to what the recorded run ended with. */
export function ReplaySummary({ report, path, onRestart }: { report: ReportData; path: ReplayPath; onRestart: () => void }) {
  const mine = versionOf(report, path.acceptedVersion) ?? report.baseline;
  const base = report.baseline;
  const stoppedEarly = path.steps.length < report.iterations.length;
  const rows = [
    { label: "Your accepted config", stats: mine },
    { label: "Recorded run ended at", stats: report.final },
  ];

  return (
    <div className="flex flex-col gap-6" aria-live="polite">
      <ol className="flex flex-col gap-2">
        {path.steps.map((step) => {
          const { tone, label } = outcome(step);
          return (
            <li key={step.record.iteration} className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-white/[0.02] px-4 py-3 text-sm">
              <span className="font-medium">Proposal {step.record.iteration}</span>
              <Badge tone="accent">{humanize(step.record.proposal.lever)}</Badge>
              <span className="text-fg-muted">you chose {step.choice}</span>
              <Badge tone={tone} className="ml-auto">{label}</Badge>
            </li>
          );
        })}
      </ol>

      {stoppedEarly && (
        <p className="text-sm text-fg-muted">
          The loop stopped after {MAX_REJECTIONS_IN_A_ROW} rejections in a row, as the real optimizer does.
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {rows.map(({ label, stats }) => (
          <div key={label} className="rounded-xl border border-line bg-white/[0.03] p-4 shadow-inner-hi">
            <p className="label-mono">{label}</p>
            <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">
              v{stats.version} · {usd(num(stats.cost_per_successful_task))}
            </p>
            <p className="mt-1 text-xs text-fg-muted">
              {signedPct(changePct(num(base.cost_per_successful_task), num(stats.cost_per_successful_task)), 2)} vs baseline · held-out{" "}
              {pct(stats.heldout_success_rate, 0)} · eval {pct(stats.eval_success_rate)}
            </p>
          </div>
        ))}
      </div>

      {path.steps.some((step) => step.diverged) && (
        <p className="text-sm text-fg-muted">
          Your choices left a different config in place than the recording had. Later proposals and their results are still the
          recorded ones; a live run could have proposed something else.
        </p>
      )}

      <div>
        <ActionButton icon={RotateCw} variant="secondary" onClick={onRestart}>
          Start again
        </ActionButton>
      </div>
    </div>
  );
}
