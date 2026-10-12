import type { TaskRow } from "./types";

/**
 * Quality beyond the success rate, recovered from recorded results.
 *
 * A task succeeds exactly when the model's `icp_fit` equals the rule-based label, so the
 * label is `icp_fit` on a success and its opposite on a failure. Tasks with no parsed
 * answer have no recoverable label and are counted as `unknown`.
 */
export interface Quality {
  fits: number;
  fitsCaught: number;
  nonFits: number;
  nonFitsCorrect: number;
  unknown: number;
  successRate: number;
  balancedAccuracy: number;
  alwaysNoRate: number;
}

export function qualityOf(tasks: TaskRow[]): Quality {
  let fits = 0;
  let fitsCaught = 0;
  let nonFits = 0;
  let nonFitsCorrect = 0;
  let unknown = 0;
  for (const task of tasks) {
    if (task.icp_fit === null) {
      unknown += 1;
      continue;
    }
    const label = task.success ? task.icp_fit : !task.icp_fit;
    if (label) {
      fits += 1;
      if (task.success) fitsCaught += 1;
    } else {
      nonFits += 1;
      if (task.success) nonFitsCorrect += 1;
    }
  }
  const known = fits + nonFits;
  const recall = fits === 0 ? Number.NaN : fitsCaught / fits;
  const specificity = nonFits === 0 ? Number.NaN : nonFitsCorrect / nonFits;
  return {
    fits,
    fitsCaught,
    nonFits,
    nonFitsCorrect,
    unknown,
    successRate: tasks.length === 0 ? Number.NaN : tasks.filter((t) => t.success).length / tasks.length,
    balancedAccuracy: (recall + specificity) / 2,
    alwaysNoRate: known === 0 ? Number.NaN : nonFits / known,
  };
}

export function qualityByVersion(tasks: TaskRow[], version: number): Quality {
  return qualityOf(tasks.filter((task) => task.version === version));
}

/** Success-rate points one task is worth in a split of this size. */
export function pointsPerTask(splitSize: number): number {
  return splitSize === 0 ? Number.NaN : 100 / splitSize;
}
