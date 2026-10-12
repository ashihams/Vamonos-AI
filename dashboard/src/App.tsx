import { MotionConfig } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { AmbientBackground } from "./components/layout/AmbientBackground";
import { Footer } from "./components/layout/Footer";
import { Nav } from "./components/layout/Nav";
import { runMetrics } from "./lib/derive";
import type { DashboardData } from "./lib/types";
import { useDashboardData } from "./lib/useDashboardData";
import { Hero } from "./sections/Hero";
import { Iterations } from "./sections/Iterations";
import { Method } from "./sections/Method";
import { Overview } from "./sections/Overview";
import { Quality } from "./sections/Quality";
import { Replay } from "./sections/Replay";
import { Stack } from "./sections/Stack";
import { Tasks } from "./sections/Tasks";
import { Versions } from "./sections/Versions";

export function App() {
  const state = useDashboardData();
  return (
    <MotionConfig reducedMotion="user">
      <AmbientBackground />
      {state.status === "ready" ? (
        <Dashboard data={state.data} />
      ) : (
        <main className="grid min-h-screen place-items-center px-6 text-center">
          {state.status === "loading" ? (
            <p className="label-mono animate-pulse" role="status">
              Loading recorded runs…
            </p>
          ) : (
            <div role="alert" className="max-w-md">
              <p className="text-lg font-semibold">The run data could not be loaded.</p>
              <p className="mt-2 text-sm text-fg-muted">{state.message}</p>
              <p className="mt-4 font-mono text-xs text-fg-muted">uv run costwise dashboard</p>
            </div>
          )}
        </main>
      )}
    </MotionConfig>
  );
}

function Dashboard({ data }: { data: DashboardData }) {
  const runIds = data.runs.map((run) => run.report.run_id);
  const [runId, setRunId] = useState(() => runIds.at(-1) ?? "");
  const run = data.runs.find((candidate) => candidate.report.run_id === runId) ?? data.runs[0]!;
  const metrics = useMemo(() => runMetrics(run), [run]);

  useEffect(() => {
    const target = window.location.hash ? document.querySelector(window.location.hash) : null;
    target?.scrollIntoView();
  }, []);

  return (
    <>
      <Nav runIds={runIds} runId={run.report.run_id} onRunChange={setRunId} />
      <main id="main" key={run.report.run_id}>
        <Hero run={run} />
        <Overview run={run} metrics={metrics} />
        <Iterations run={run} />
        <Replay run={run} />
        <Versions run={run} />
        <Quality run={run} />
        <Tasks run={run} />
        <Stack />
        <Method />
      </main>
      <Footer />
    </>
  );
}
