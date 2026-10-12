import { motion } from "framer-motion";
import { Ban, CheckCircle2, RotateCcw, ShieldAlert, ShieldCheck, UserCheck, UserX } from "lucide-react";
import { Badge, type Tone } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Section } from "../components/ui/Section";
import { type Outcome, outcomeOf } from "../lib/derive";
import { changePct, humanize, num, prettyDetail, signedPct, usd } from "../lib/format";
import { fadeUp } from "../lib/motion";
import type { DashboardRun, IterationRecord, VersionStats } from "../lib/types";

const OUTCOME: Record<Outcome, { tone: Tone; icon: typeof CheckCircle2; label: string }> = {
  kept: { tone: "pass", icon: CheckCircle2, label: "Kept" },
  "rolled back": { tone: "block", icon: RotateCcw, label: "Rolled back" },
  declined: { tone: "warn", icon: Ban, label: "Declined" },
};

const RISK: Record<IterationRecord["proposal"]["risk"], Tone> = { low: "pass", medium: "warn", high: "block" };

export function Iterations({ run }: { run: DashboardRun }) {
  const { iterations, versions } = run.report;
  return (
    <Section
      id="iterations"
      label="02 · Optimizer iterations"
      aside={
        <a href="#replay" className="text-sm font-medium text-[#b4bbf5] underline-offset-4 hover:underline">
          Be the approver →
        </a>
      }
      title="Propose one change. Measure it. Keep it only if it holds."
      description="Each iteration changes exactly one lever. The change is approved (by a person at the terminal, or automatically with --auto-approve), the full workload re-runs, and the guardrails decide whether it is kept."
    >
      {iterations.length === 0 ? (
        <p className="text-fg-muted">This run has no iterations.</p>
      ) : (
        <ol className="relative flex flex-col gap-6 md:pl-10">
          <span aria-hidden className="absolute top-2 bottom-2 left-[5px] hidden w-px bg-gradient-to-b from-accent/60 via-white/10 to-transparent md:block" />
          {iterations.map((record) => (
            <IterationItem key={record.iteration} record={record} versions={versions} />
          ))}
        </ol>
      )}
    </Section>
  );
}

function IterationItem({ record, versions }: { record: IterationRecord; versions: VersionStats[] }) {
  const outcome = OUTCOME[outcomeOf(record)];
  const before = versions.find((v) => v.version === record.baseline_version);
  const after = versions.find((v) => v.version === record.candidate_version);
  const measured =
    before && after ? changePct(num(before.cost_per_successful_task), num(after.cost_per_successful_task)) : Number.NaN;

  return (
    <motion.li variants={fadeUp} className="relative">
      <span
        aria-hidden
        className={`absolute top-8 -left-10 hidden size-[11px] rounded-full ring-4 ring-bg-base md:block ${
          outcome.tone === "pass" ? "bg-pass" : outcome.tone === "block" ? "bg-block" : "bg-warn"
        }`}
      />
      <Card as="article" lift={false} className="p-6 md:p-8">
        <header className="flex flex-wrap items-center gap-3">
          <h3 className="text-xl font-semibold tracking-tight md:text-2xl">Iteration {record.iteration}</h3>
          <Badge tone="accent">{humanize(record.proposal.lever)}</Badge>
          <Badge tone={RISK[record.proposal.risk]}>{record.proposal.risk} risk</Badge>
          <Badge tone={outcome.tone} icon={outcome.icon} className="ml-auto">
            {outcome.label}
          </Badge>
        </header>

        <div className="mt-6 grid gap-8 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <p className="label-mono mb-2">Proposed value</p>
            <pre className="scrollbar-thin overflow-x-auto rounded-lg border border-white/10 bg-bg-input px-4 py-3 font-mono text-[13px] text-[#c7ccf7]">
              {JSON.stringify(record.proposal.new_value, null, 2)}
            </pre>
            <p className="label-mono mt-6 mb-2">The agent's reasoning</p>
            <p className="leading-relaxed text-fg-muted">{record.proposal.rationale}</p>
            <div className="mt-6 flex flex-wrap items-center gap-3 text-sm">
              {record.decision.approved ? (
                <Badge tone="pass" icon={UserCheck}>Approved</Badge>
              ) : (
                <Badge tone="warn" icon={UserX}>Declined</Badge>
              )}
              {record.decision.note && <span className="text-fg-muted">“{record.decision.note}”</span>}
            </div>
          </div>

          <div className="flex flex-col gap-5 lg:col-span-2">
            <div className="grid grid-cols-2 gap-3">
              <Figure label="Predicted" value={signedPct(record.proposal.predicted_cost_change_pct)} hint="cost change" />
              <Figure
                label="Measured"
                value={signedPct(measured, 2)}
                hint={after ? `${usd(num(after.cost_per_successful_task))} / success` : "not run"}
                tone={Number.isFinite(measured) ? (measured < 0 ? "good" : "bad") : undefined}
              />
            </div>

            <div>
              <p className="label-mono mb-2">Guardrails</p>
              {record.guardrails ? (
                <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-lg border border-line bg-white/[0.02]">
                  {record.guardrails.checks.map((check) => (
                    <li key={check.name} className="flex items-start gap-3 px-3.5 py-3">
                      {check.passed ? (
                        <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-pass" />
                      ) : (
                        <ShieldAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-block" />
                      )}
                      <div className="min-w-0">
                        <p className="text-sm font-medium">
                          {humanize(check.name)}{" "}
                          <span className={check.passed ? "text-pass" : "text-[#ff8589]"}>
                            · {check.passed ? "passed" : "blocked"}
                          </span>
                        </p>
                        <p className="mt-0.5 break-words font-mono text-[11.5px] text-fg-muted">{prettyDetail(check.detail)}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-fg-muted">Not evaluated — the proposal never ran.</p>
              )}
            </div>
            <p className="text-sm text-fg-muted">
              <span className="text-fg">Outcome:</span> {record.reason}
            </p>
          </div>
        </div>
      </Card>
    </motion.li>
  );
}

function Figure({ label, value, hint, tone }: { label: string; value: string; hint: string; tone?: "good" | "bad" }) {
  const color = tone === "good" ? "text-pass" : tone === "bad" ? "text-[#ff8589]" : "text-fg";
  return (
    <div className="rounded-xl border border-line bg-white/[0.03] p-4 shadow-inner-hi">
      <p className="label-mono">{label}</p>
      <p className={`mt-2 text-2xl font-semibold tracking-tight tabular-nums ${color}`}>{value}</p>
      <p className="mt-1 text-xs text-fg-muted">{hint}</p>
    </div>
  );
}