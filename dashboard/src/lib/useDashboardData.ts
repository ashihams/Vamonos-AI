import { useEffect, useState } from "react";
import type { DashboardData } from "./types";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: DashboardData };

const DATA_URL = "/data/dashboard.json";

export function useDashboardData(): State {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetch(DATA_URL, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`could not load ${DATA_URL} (${response.status})`);
        return response.json() as Promise<DashboardData>;
      })
      .then((data) => {
        if (data.runs.length === 0) throw new Error("the data file holds no runs");
        setState({ status: "ready", data });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({ status: "error", message: error instanceof Error ? error.message : String(error) });
      });
    return () => controller.abort();
  }, []);

  return state;
}
