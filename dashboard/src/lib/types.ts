/** Mirrors costwise.services.dashboard.DashboardData as exported by `costwise dashboard`. */

export type Decimal = string;

export interface CostBreakdown {
  model_usd: Decimal;
  infra_usd: Decimal;
  data_usd: Decimal;
}

export interface VersionStats {
  version: number;
  status: "baseline" | "kept" | "rolled back";
  tasks: number;
  eval_tasks: number;
  heldout_tasks: number;
  successes: number;
  totals: CostBreakdown;
  cost_per_successful_task: Decimal | null;
  eval_success_rate: number | null;
  heldout_success_rate: number | null;
  p95_latency_ms: number | null;
  infra_sources: ("measured" | "modeled")[];
}

export interface CheckOutcome {
  name: string;
  passed: boolean;
  detail: string;
}

export interface RunSummary {
  n: number;
  success_rate: number;
  cost_per_successful_task: Decimal;
  totals: CostBreakdown;
  p50_latency_ms: number;
  p95_latency_ms: number;
  cache_hit_rate: number;
  repeat_rate: number;
  avg_input_tokens: number;
  avg_output_tokens: number;
}

export type JsonValue = boolean | number | string | null | JsonValue[] | { [key: string]: JsonValue };

export interface IterationRecord {
  iteration: number;
  proposal: {
    lever: string;
    new_value: JsonValue;
    rationale: string;
    predicted_cost_change_pct: number;
    risk: "low" | "medium" | "high";
  };
  decision: { approved: boolean; note: string };
  baseline_version: number;
  candidate_version: number | null;
  candidate_summary: RunSummary | null;
  guardrails: { passed: boolean; checks: CheckOutcome[] } | null;
  accepted: boolean;
  reason: string;
}

export interface CallRecord {
  model: string;
  tier: "cheap" | "strong";
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  started_offset_ms: number;
}

export interface TaskRow {
  version: number;
  task_id: string;
  domain: string;
  split: "eval" | "heldout";
  difficulty: "easy" | "hard";
  success: boolean;
  cache_hit: boolean;
  icp_fit: boolean | null;
  reasons: string[];
  error: string | null;
  latency_ms: number;
  costs: CostBreakdown;
  infra_source: "measured" | "modeled";
  calls: CallRecord[];
}

export interface ReportData {
  run_id: string;
  baseline: VersionStats;
  final: VersionStats;
  versions: VersionStats[];
  iterations: IterationRecord[];
}

export interface DashboardRun {
  report: ReportData;
  tasks: TaskRow[];
}

export interface DashboardData {
  runs: DashboardRun[];
}
