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
```

## Telemetry

- With `NEATLOGS_API_KEY` set, task and iteration spans are exported to neatlogs over OTLP/gRPC with TLS at `ingest.neatlogs.com:443`, using the `x-api-key` header.
- Without it, telemetry is discarded.
- Check the neatlogs connection with `uv run python scripts/smoke_neatlogs.py`, then find the logged `run_id` in the dashboard.
- Summary metrics go only to a local Collector. Start it with `docker compose --env-file .env -f infra/collector/docker-compose.yaml up -d` and set `OTEL_COLLECTOR_ENDPOINT=localhost:4317`. The Collector writes `infra/collector/data/telemetry.jsonl`.
- If exports hang with `DEADLINE_EXCEEDED`, set `GRPC_DNS_RESOLVER=native` in the environment.
