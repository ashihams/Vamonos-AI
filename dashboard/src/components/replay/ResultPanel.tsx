import { motion, useReducedMotion } from "framer-motion";
import { CheckCircle2, Info, RotateCcw, ShieldAlert, ShieldCheck, UserX } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { Badge } from "../ui/Badge";
import { changePct, humanize, num, prettyDetail, signedPct, usd } from "../../lib/format";
import { quick } from "../../lib/motion";
import type { ReplayStep } from "../../lib/replay";
import type { VersionStats } from "../../lib/types";

const RUN_MS = 1600;
const CHECK_MS = 450;

/** What happened after the decision: no run, or the recorded re-run, guardrails, and verdict. */
interface ResultPanelProps {
  step: ReplayStep;
  start: VersionStats | undefined;
  onRevealed: () => void;
}

export function ResultPanel({ step, start, onRevealed }: ResultPanelProps) {
  const { result } = step;
  useEffect(() => {
    if (result.kind !== "measured") onRevealed();
  }, [result.kind, onRevealed]);
  if (result.kind === "declined") {
    return (
      <Notice icon={UserX} title="Rejected by approver">
        No re-run and no spend. v{step.startVersion} stays the accepted config. Two rejections in a row end the loop.
      </Notice>
    );
  }
  if (result.kind === "not-run") {
    return (
      <Notice icon={Info} title="No measured result">
        This proposal was declined in the recording, so it never ran. There is nothing measured to show.
      </Notice>
    );
  }
  return <Measured result={result} startVersion={step.startVersion} start={start} onRevealed={onRevealed} />;
}

interface MeasuredProps {
  result: Extract<ReplayStep["result"], { kind: "measured" }>;
  startVersion: number;
  start: VersionStats | undefined;
  onRevealed: () => void;
}

function Measured({ result, startVersion, start, onRevealed }: MeasuredProps) {
  const { candidate, kept, record } = result;
  const checks = record.guardrails?.checks ?? [];
  const stage = useStage(checks.length + 1);
  useEffect(() => {
    if (stage > checks.length) onRevealed();
  }, [stage, checks.length, onRevealed]);
  const reduce = useReducedMotion();
  const change = start ? changePct(num(start.cost_per_successful_task), num(candidate.cost_per_successful_task)) : Number.NaN;

  return (
    <div className="flex flex-col gap-5" aria-live="polite">
      <div>
        <p className="label-mono mb-2">Re-running the full workload · {candidate.tasks} tasks</p>
        <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-accent to-accent-bright"
            initial={{ width: reduce ? "100%" : "0%" }}
            animate={{ width: "100%" }}
            transition={{ duration: reduce ? 0 : RUN_MS / 1000, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>
        {stage > 0 && (
          <p className="mt-2 text-xs text-fg-muted">
            v{candidate.version}: {candidate.successes} of {candidate.tasks} correct · {usd(num(candidate.cost_per_successful_task))} per success
          </p>
        )}
      </div>

      <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-lg border border-line bg-white/[0.02]">
        {checks.map((check, index) =>
          stage > index ? (
            <motion.li key={check.name} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={quick} className="flex items-start gap-3 px-3.5 py-3">
              {check.passed ? (
                <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-pass" />
              ) : (
                <ShieldAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-block" />
              )}
              <div className="min-w-0">
                <p className="text-sm font-medium">
                  {humanize(check.name)}{" "}
                  <span className={check.passed ? "text-pass" : "text-[#ff8589]"}>· {check.passed ? "passed" : "blocked"}</span>
                </p>
                <p className="mt-0.5 break-words font-mono text-[11.5px] text-fg-muted">{prettyDetail(check.detail)}</p>
              </div>
            </motion.li>
          ) : (
            <li key={check.name} className="px-3.5 py-3 text-sm text-fg-subtle">
              {humanize(check.name)} · checking…
            </li>
          ),
        )}
      </ul>

      {stage > checks.length && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={quick} className="flex flex-wrap items-center gap-3">
          <Badge tone={kept ? "pass" : "block"} icon={kept ? CheckCircle2 : RotateCcw}>
            {kept ? `Kept · v${candidate.version} is now accepted` : `Rolled back · v${startVersion} stays`}
          </Badge>
          <span className="text-sm text-fg-muted">
            measured {signedPct(change, 2)} cost per success vs v{start?.version ?? startVersion}
          </span>
          <span className="w-full text-sm text-fg-muted">{record.reason}</span>
        </motion.div>
      )}
    </div>
  );
}

/** Advance from 0 to `last` once the run bar fills, one guardrail at a time. */
function useStage(last: number): number {
  const reduce = useReducedMotion();
  const [stage, setStage] = useState(reduce ? last : 0);
  useEffect(() => {
    if (reduce) return;
    const timers = Array.from({ length: last }, (_, index) =>
      window.setTimeout(() => setStage(index + 1), RUN_MS + index * CHECK_MS),
    );
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [last, reduce]);
  return stage;
}

function Notice({ icon: Icon, title, children }: { icon: typeof Info; title: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-line bg-white/[0.03] p-4" aria-live="polite">
      <Icon aria-hidden className="mt-0.5 size-4 shrink-0 text-warn" />
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="mt-1 text-sm leading-relaxed text-fg-muted">{children}</p>
      </div>
    </div>
  );
}
