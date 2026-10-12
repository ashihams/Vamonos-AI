import { motion } from "framer-motion";
import { Badge, type Tone } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Section } from "../components/ui/Section";
import { pct } from "../lib/format";
import { fadeUp } from "../lib/motion";
import { pointsPerTask, qualityByVersion, type Quality as QualityStats } from "../lib/quality";
import type { DashboardRun, VersionStats } from "../lib/types";

const STATUS_TONE: Record<VersionStats["status"], Tone> = { baseline: "accent", kept: "pass", "rolled back": "block" };

export function Quality({ run }: { run: DashboardRun }) {
  const { versions, baseline } = run.report;
  const heldoutPoints = pointsPerTask(baseline.heldout_tasks);
  const evalPoints = pointsPerTask(baseline.eval_tasks);
  return (
    <Section
      id="quality"
      label="05 · Quality beyond success rate"
      title="A high success rate is not enough"
      description="Most companies in this workload do not fit the profile, so answering “not a fit” every time already scores well. These figures are recovered from the recorded answers: a task succeeds exactly when the model's answer matches the rule-based label."
    >
      <div className="grid gap-4 md:grid-cols-3">
        {versions.map((stats) => (
          <VersionQuality key={stats.version} stats={stats} quality={qualityByVersion(run.tasks, stats.version)} />
        ))}
      </div>

      <motion.div variants={fadeUp} className="mt-4 grid gap-4 md:grid-cols-2">
        <Card lift={false} className="p-6">
          <p className="label-mono">Small samples</p>
          <p className="mt-3 leading-relaxed text-fg-muted">
            The held-out split has <span className="text-fg">{baseline.heldout_tasks} tasks</span>, so one miss moves its success
            rate by <span className="text-fg">{heldoutPoints.toFixed(0)} points</span>. The evaluation split has{" "}
            {baseline.eval_tasks}, where one miss is {evalPoints.toFixed(1)} points. The guardrail allows a 2-point drop, so in
            practice any extra miss in either split blocks a change. That is strict, and it is noisy.
          </p>
        </Card>
        <Card lift={false} className="p-6">
          <p className="label-mono">Labels</p>
          <p className="mt-3 leading-relaxed text-fg-muted">
            Labels come from a written rule, 50 to 1,000 employees and a seed to Series C round, not from human judgement.
            Success means the model agreed with that rule.
          </p>
        </Card>
      </motion.div>
    </Section>
  );
}

function VersionQuality({ stats, quality }: { stats: VersionStats; quality: QualityStats }) {
  const beatsAlwaysNo = quality.successRate > quality.alwaysNoRate;
  return (
    <Card lift={false} className="p-6">
      <div className="flex items-center gap-2">
        <span className="font-mono font-medium">v{stats.version}</span>
        <Badge tone={STATUS_TONE[stats.status]}>{stats.status}</Badge>
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
        <Metric label="Success rate" value={pct(quality.successRate)} />
        <Metric label="Balanced accuracy" value={pct(quality.balancedAccuracy)} />
        <Metric label="Real fits caught" value={`${quality.fitsCaught} of ${quality.fits}`} />
        <Metric label="Non-fits correct" value={`${quality.nonFitsCorrect} of ${quality.nonFits}`} />
      </dl>
      <p className="mt-5 border-t border-line pt-4 text-xs leading-relaxed text-fg-muted">
        Always answering “not a fit” would score <span className="text-fg">{pct(quality.alwaysNoRate)}</span> on these tasks
        {beatsAlwaysNo ? "; this version beats it." : "; this version does not beat it."}
        {quality.unknown === 1 && " 1 task had no parsed answer and is left out."}
        {quality.unknown > 1 && ` ${quality.unknown} tasks had no parsed answer and are left out.`}
      </p>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="label-mono">{label}</dt>
      <dd className="mt-1 text-xl font-semibold tracking-tight tabular-nums">{value}</dd>
    </div>
  );
}
