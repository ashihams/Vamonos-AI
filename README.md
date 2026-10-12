# costwise

Optimizer agent that lowers the cost of a target AI qualification app and proves quality did not drop.

The build contract is [docs/SPEC.md](docs/SPEC.md).

## Setup

```
uv sync --all-extras --all-groups
cp .env.example .env   # fill in keys locally; .env is gitignored
make check
```

## Commands

```
uv run costwise fixtures build      # fetch Crustdata fixtures (CRUSTDATA_API_KEY)
uv run costwise fixtures label      # label fixtures and choose the held-out split
uv run costwise dry-run --tasks 5   # small run plus a budget projection for the full plan
uv run costwise eval baseline --run-id baseline-1
uv run costwise optimize --run-id baseline-1 --iterations 3   # asks y/n per proposal
uv run costwise report --run-id baseline-1                    # evidence pack and cfo.ai inputs
```

`optimize` reuses the stored version-1 baseline for the run id, or runs it first. Each iteration proposes one lever change, asks for approval (`--auto-approve` skips the question), re-runs the full workload, and keeps the change only if every guardrail passes against the current accepted config. It stops at the iteration limit, when nothing is left to propose, after two rejections in a row, or at the budget stop line.

`report` reads the stored results and iterations and writes four files to `runs/<run_id>/report/`:

- `report.md`: baseline versus final accepted cost per successful task, the model, infra, and data split with a `[source: ...]` tag on every cost line, evaluation and held-out success rates on separate rows, p95 latency, the iteration table, and a section on what is measured and what is modeled.
- `trajectory.csv`: one row per evaluated version, including rolled-back ones.
- `cfo_inputs.json`: baseline and optimized unit costs, the cost split, task counts, and sources for the cfo.ai model. `price_per_task_usd` and `monthly_volume_scenarios` are left empty for you to fill in as assumptions.
- `trajectory.mmd`: a Mermaid `xychart-beta` of cost per successful task by version.

## AWS Lambda runner (optional)

With the Lambda runner, each task is one invocation of a deployed function, and infrastructure cost is measured from the `REPORT` log line (billed duration and memory) instead of modeled. It also enables the Lambda memory lever.

```
make lambda-build      # build build/costwise-lambda.zip; no AWS calls
make lambda-deploy     # create or update the role and function (needs AWS credentials)
uv run costwise eval baseline --run-id lambda-smoke --runner lambda --tasks 3
make lambda-teardown   # delete the function and role after the demo
```

Defaults are region `us-east-1` and function `costwise-qualify`; set `AWS_REGION` and `LAMBDA_FUNCTION_NAME` to change them. The deploy creates only an IAM role with the basic execution policy and one function, both tagged `project=costwise`. It copies `LITELLM_BASE_URL` and `LITELLM_API_KEY` from `.env` into the function's environment and bundles the company fixtures, so no Crustdata or neatlogs key goes to AWS. The model budget is enforced on the machine running the CLI, which charges every model call the function reports.

## Telemetry

- With `NEATLOGS_API_KEY` set, task and iteration spans are exported to neatlogs over OTLP/gRPC with TLS at `ingest.neatlogs.com:443`, using the `x-api-key` header.
- Without it, telemetry is discarded.
- Check the neatlogs connection with `uv run python scripts/smoke_neatlogs.py`, then find the logged `run_id` in the dashboard.
- Summary metrics go only to a local Collector. Start it with `docker compose --env-file .env -f infra/collector/docker-compose.yaml up -d` and set `OTEL_COLLECTOR_ENDPOINT=localhost:4317`. The Collector writes `infra/collector/data/telemetry.jsonl`.
- If exports hang with `DEADLINE_EXCEEDED`, set `GRPC_DNS_RESOLVER=native` in the environment.
