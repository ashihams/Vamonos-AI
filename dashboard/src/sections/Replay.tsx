import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, GitBranch } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { ProposalPanel } from "../components/replay/ProposalPanel";
import { ReplaySummary } from "../components/replay/ReplaySummary";
import { ResultPanel } from "../components/replay/ResultPanel";
import { Badge } from "../components/ui/Badge";
import { ActionButton } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Section } from "../components/ui/Section";
import { num, usd } from "../lib/format";
import { standard } from "../lib/motion";
import { type Choice, isFinished, replayPath, versionOf } from "../lib/replay";
import type { DashboardRun } from "../lib/types";

export function Replay({ run }: { run: DashboardRun }) {
  const { report } = run;
  const [choices, setChoices] = useState<Choice[]>([]);
  const [cursor, setCursor] = useState(0);
  const path = useMemo(() => replayPath(report, choices), [report, choices]);
  const finished = isFinished(report, path);
  const decided = choices.length > cursor;
  const showSummary = finished && cursor >= path.steps.length;
  const record = report.iterations[cursor];
  const step = path.steps[cursor];
  const accepted = versionOf(report, step?.startVersion ?? path.acceptedVersion);

  const [revealed, setRevealed] = useState(-1);
  const onRevealed = useCallback(() => setRevealed(cursor), [cursor]);

  const choose = (choice: Choice) => setChoices((previous) => [...previous.slice(0, cursor), choice]);
  const next = () => setCursor((value) => value + 1);
  const restart = () => {
    setChoices([]);
    setCursor(0);
    setRevealed(-1);
  };

  return (
    <Section
      id="replay"
      label="03 · Be the approver"
      title="Every change waits for a yes."
      description={
        <>
          A replay of run <span className="font-mono text-fg">{report.run_id}</span>. Each proposal is the one the optimizer really
          made. Approve it to see the full-workload re-run and guardrail verdict measured at the time. Reject it and costwise does
          what it does at the terminal: records the decision, skips the run, keeps the current config. No model is called on this
          page.
        </>
      }
    >
      {report.iterations.length === 0 ? (
        <p className="text-fg-muted">This run has no proposals to replay.</p>
      ) : (
        <Card variant="gradient" lift={false} className="p-6 md:p-8">
          <header className="mb-6 flex flex-wrap items-center gap-3">
            <h3 className="text-xl font-semibold tracking-tight md:text-2xl">
              {showSummary ? "Where your decisions landed" : `Proposal ${cursor + 1} of ${report.iterations.length}`}
            </h3>
            {!showSummary && accepted && (
              <Badge icon={GitBranch} className="ml-auto">
                accepted now: v{accepted.version} · {usd(num(accepted.cost_per_successful_task))} / success
              </Badge>
            )}
          </header>

          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={showSummary ? "summary" : cursor}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={standard}
            >
              {showSummary ? (
                <ReplaySummary report={report} path={path} onRestart={restart} />
              ) : record ? (
                <div className="grid gap-8 lg:grid-cols-5">
                  <div className="lg:col-span-3">
                    <ProposalPanel record={record} decided={decided} onChoose={choose} />
                  </div>
                  <div className="flex flex-col gap-5 lg:col-span-2">
                    {step ? (
                      <>
                        {step.diverged && (
                          <p className="text-xs text-fg-muted">
                            An earlier choice differs from the recording, which started this step from a different config.
                          </p>
                        )}
                        <ResultPanel step={step} start={accepted} onRevealed={onRevealed} />
                        {revealed === cursor && (
                          <div>
                            <ActionButton icon={ArrowRight} onClick={next}>
                              {finished ? "See where you landed" : "Next proposal"}
                            </ActionButton>
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="text-sm text-fg-muted">Your call. Approve to re-run the workload, or reject to keep the current config.</p>
                    )}
                  </div>
                </div>
              ) : null}
            </motion.div>
          </AnimatePresence>
        </Card>
      )}
    </Section>
  );
}
