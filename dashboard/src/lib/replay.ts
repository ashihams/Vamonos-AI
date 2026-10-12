import type { IterationRecord, ReportData, VersionStats } from "./types";

export type Choice = "approve" | "reject";

export type StepResult =
  | { kind: "declined" }
  | { kind: "not-run" }
  | { kind: "measured"; kept: boolean; candidate: VersionStats; record: IterationRecord };

export interface ReplayStep {
  record: IterationRecord;
  choice: Choice;
  result: StepResult;
  /** Accepted version before this step, on the visitor's path. */
  startVersion: number;
  /** True when an earlier choice left the visitor on a different config than the recording. */
  diverged: boolean;
}

export interface ReplayPath {
  steps: ReplayStep[];
  acceptedVersion: number;
  rejectionsInARow: number;
}

/** Stop rule of the real optimizer: two rejections in a row end the loop. */
export const MAX_REJECTIONS_IN_A_ROW = 2;

function stepResult(record: IterationRecord, choice: Choice, versions: VersionStats[]): StepResult {
  if (choice === "reject") return { kind: "declined" };
  const candidate = versions.find((v) => v.version === record.candidate_version);
  if (!record.decision.approved || !candidate) return { kind: "not-run" };
  return { kind: "measured", kept: record.accepted, candidate, record };
}

/** Recorded accepted version after each iteration, to tell when the visitor's path differs. */
function recordedAccepted(report: ReportData): number[] {
  let accepted = report.baseline.version;
  return report.iterations.map((record) => {
    if (record.accepted && record.candidate_version !== null) accepted = record.candidate_version;
    return accepted;
  });
}

export function replayPath(report: ReportData, choices: Choice[]): ReplayPath {
  const recorded = recordedAccepted(report);
  let acceptedVersion = report.baseline.version;
  let rejectionsInARow = 0;
  const steps: ReplayStep[] = [];
  choices.forEach((choice, index) => {
    const record = report.iterations[index];
    if (!record) return;
    const recordedStart = index === 0 ? report.baseline.version : recorded[index - 1];
    const diverged = acceptedVersion !== recordedStart;
    const result = stepResult(record, choice, report.versions);
    steps.push({ record, choice, result, startVersion: acceptedVersion, diverged });
    if (result.kind === "measured" && result.kept) {
      acceptedVersion = result.candidate.version;
      rejectionsInARow = 0;
    } else {
      rejectionsInARow += 1;
    }
  });
  return { steps, acceptedVersion, rejectionsInARow };
}

export function isFinished(report: ReportData, path: ReplayPath): boolean {
  return path.steps.length >= report.iterations.length || path.rejectionsInARow >= MAX_REJECTIONS_IN_A_ROW;
}

export function versionOf(report: ReportData, version: number): VersionStats | undefined {
  return report.versions.find((v) => v.version === version);
}
