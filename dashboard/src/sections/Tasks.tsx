import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, ChevronRight, Database, Search, XCircle } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { Section } from "../components/ui/Section";
import { Segmented } from "../components/ui/Segmented";
import { compact, ms, total, usd } from "../lib/format";
import { standard } from "../lib/motion";
import type { DashboardRun, TaskRow } from "../lib/types";

type SplitFilter = "all" | "eval" | "heldout";
type ResultFilter = "all" | "success" | "failure";

export function Tasks({ run }: { run: DashboardRun }) {
  const versions = run.report.versions.map((stats) => String(stats.version));
  const [version, setVersion] = useState(versions[0] ?? "1");
  const [split, setSplit] = useState<SplitFilter>("all");
  const [result, setResult] = useState<ResultFilter>("all");
  const [query, setQuery] = useState("");
  const searchId = useId();

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return run.tasks.filter(
      (task) =>
        String(task.version) === version &&
        (split === "all" || task.split === split) &&
        (result === "all" || task.success === (result === "success")) &&
        (needle === "" || task.domain.includes(needle) || task.task_id.includes(needle)),
    );
  }, [run.tasks, version, split, result, query]);

  const successes = rows.filter((task) => task.success).length;

  return (
    <Section
      id="tasks"
      label="06 · Task explorer"
      title="Every company the agent qualified"
      description="One row per task: the company, the split, whether the answer matched its label, what it cost, and the model's own reasons."
    >
      <Card lift={false} spotlight={false}>
        <div className="flex flex-col gap-4 border-b border-line p-5 lg:flex-row lg:items-center">
          <div className="flex flex-wrap items-center gap-3">
            <Segmented
              label="Config version"
              size="sm"
              value={version}
              onChange={setVersion}
              options={versions.map((v) => ({ value: v, label: `v${v}` }))}
            />
            <Segmented<SplitFilter>
              label="Split"
              size="sm"
              value={split}
              onChange={setSplit}
              options={[
                { value: "all", label: "All" },
                { value: "eval", label: "Eval" },
                { value: "heldout", label: "Held-out" },
              ]}
            />
            <Segmented<ResultFilter>
              label="Result"
              size="sm"
              value={result}
              onChange={setResult}
              options={[
                { value: "all", label: "All" },
                { value: "success", label: "Correct" },
                { value: "failure", label: "Wrong" },
              ]}
            />
          </div>
          <div className="relative lg:ml-auto lg:w-72">
            <label htmlFor={searchId} className="sr-only">
              Search by domain or task id
            </label>
            <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-muted" />
            <input
              id={searchId}
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search domain or task id"
              className="w-full rounded-lg border border-white/10 bg-bg-input py-2 pr-3 pl-9 text-sm text-gray-100 placeholder:text-gray-500 transition-[border-color,box-shadow] duration-200 ease-expo focus:border-accent focus:shadow-[0_0_0_3px_rgba(94,106,210,0.25)] focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
            />
          </div>
        </div>

        <p className="px-5 pt-4 text-xs text-fg-muted" aria-live="polite">
          {rows.length} tasks · {successes} correct
        </p>
        <div
          aria-hidden
          className="label-mono mx-2 mt-3 hidden grid-cols-[16px_minmax(0,2fr)_repeat(4,minmax(0,1fr))_16px] gap-x-4 border-b border-line px-3 pb-3 md:grid"
        >
          <span />
          <span>Company</span>
          <span>Split</span>
          <span>Answer</span>
          <span>Cost</span>
          <span>Latency</span>
          <span />
        </div>

        <ul className="scrollbar-thin max-h-[640px] overflow-y-auto p-2" aria-label="Tasks">
          {rows.map((task) => (
            <TaskItem key={`${task.version}-${task.task_id}`} task={task} />
          ))}
          {rows.length === 0 && <li className="px-4 py-10 text-center text-sm text-fg-muted">No tasks match these filters.</li>}
        </ul>
      </Card>
    </Section>
  );
}

function TaskItem({ task }: { task: TaskRow }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const tokens = task.calls.reduce((sum, call) => sum + call.input_tokens + call.output_tokens, 0);

  return (
    <li className="rounded-xl transition-colors duration-200 ease-expo hover:bg-white/[0.03]">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="grid w-full grid-cols-[16px_1fr_16px] items-center gap-x-4 gap-y-1 rounded-xl px-3 py-3 text-left md:grid-cols-[16px_minmax(0,2fr)_repeat(4,minmax(0,1fr))_16px]"
      >
        {task.success ? (
          <CheckCircle2 aria-label="Correct" className="size-4 text-pass" />
        ) : (
          <XCircle aria-label="Wrong" className="size-4 text-block" />
        )}
        <span className="min-w-0">
          <span className="block truncate font-medium">{task.domain}</span>
          <span className="block font-mono text-[11px] text-fg-muted">{task.task_id}</span>
        </span>
        <span className="hidden md:block">
          <Badge tone={task.split === "heldout" ? "accent" : "neutral"}>{task.split === "heldout" ? "held-out" : "eval"}</Badge>
        </span>
        <span className="hidden text-sm text-fg-muted md:block">
          {task.icp_fit === null ? "no answer" : task.icp_fit ? "fits ICP" : "not a fit"}
        </span>
        <span className="hidden font-mono text-sm tabular-nums md:block">{usd(total(task.costs), 4)}</span>
        <span className="hidden text-sm tabular-nums text-fg-muted md:block">{ms(task.latency_ms)}</span>
        <ChevronRight
          aria-hidden
          className={`size-4 text-fg-muted transition-transform duration-200 ease-expo ${open ? "rotate-90" : ""}`}
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={panelId}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={standard}
            className="overflow-hidden"
          >
            <div className="grid gap-6 px-3 pt-1 pb-5 md:grid-cols-5 md:pl-11">
              <div className="md:col-span-3">
                <p className="label-mono mb-2">{task.error ? "Error" : "Model's reasons"}</p>
                {task.error ? (
                  <p className="rounded-lg border border-block/30 bg-block/10 px-3 py-2 font-mono text-xs text-[#ff8589]">{task.error}</p>
                ) : (
                  <ul className="flex list-disc flex-col gap-1.5 pl-4 text-sm leading-relaxed text-fg-muted marker:text-accent">
                    {task.reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                )}
                <div className="mt-4 flex flex-wrap gap-2">
                  <Badge>{task.difficulty}</Badge>
                  {task.cache_hit && <Badge tone="accent" icon={Database}>cache hit</Badge>}
                  <Badge>infra {task.infra_source}</Badge>
                </div>
              </div>
              <div className="md:col-span-2">
                <p className="label-mono mb-2">Model calls · {compact(tokens)} tokens</p>
                <ul className="flex flex-col gap-2">
                  {task.calls.map((call, index) => (
                    <li key={index} className="rounded-lg border border-line bg-white/[0.02] px-3 py-2.5 font-mono text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-fg">{call.model}</span>
                        <Badge tone={call.tier === "cheap" ? "pass" : "accent"}>{call.tier}</Badge>
                      </div>
                      <div className="mt-1.5 text-fg-muted">
                        {call.input_tokens.toLocaleString()} in · {call.output_tokens} out · {ms(call.latency_ms)}
                      </div>
                    </li>
                  ))}
                  {task.calls.length === 0 && <li className="text-xs text-fg-muted">No model call was made.</li>}
                </ul>
                <p className="mt-3 font-mono text-[11px] text-fg-muted tabular-nums">
                  model {usd(Number(task.costs.model_usd), 6)} · infra {usd(Number(task.costs.infra_usd), 6)} · data{" "}
                  {usd(Number(task.costs.data_usd), 4)}
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}
