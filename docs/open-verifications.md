# Open verifications

Status as of 2026-10-12. Live model calls and the neatlogs dashboard are partly checked, as noted per item. Nothing has been checked against AWS.

| Item | Kind | Status | Who closes it |
| --- | --- | --- | --- |
| Crustdata credits per enrich call | code marker | Open: docs say 2 credits; the dashboard charge is unchecked | builder |
| LiteLLM accepts `max_tokens` and returns `usage` | code marker | Partly done: Sonnet returns `usage`; Haiku and the token cap are unchecked | the first optimize run |
| neatlogs span attributes render as intended | manual | Names now taken from the neatlogs SDK's attribute map; the dashboard view after the rewrite is unchecked | builder |
| Lambda Tail log ends with the REPORT line | code marker | Open: not deployed | builder, after `make lambda-deploy` |
| Lambda deployment | manual | Not run; the zip builds locally | builder |
| neatlogs smoke check | manual | Partly done: traces arrive and nest; rerun after the attribute rewrite | builder |
| Collector image and file output | config | Open: image not pinned, file write untested | builder |
| Model names and per-token prices | config | Done 2026-10-12: `claude-haiku` and `claude-sonnet-4.6` at the proxy's rates | — |
| Crustdata USD price per credit | config | Open: `0.00` placeholder; needs a stated assumption | builder |
| Crustdata endpoint, headers, and field mapping | checked | Done 2026-10-11 against the docs and one live call | — |

## TODO(VERIFY: Crustdata credits charged per company enrich call)

- Where: `src/costwise/adapters/data/crustdata_client.py`, `CREDITS_PER_ENRICH = Decimal(2)`.
- Source so far: the Crustdata pricing page lists `/company/enrich` at 2 credits per record, plus 2 when `technographics` is requested. costwise does not request `technographics`.
- Still unchecked: what the dashboard actually charged for the 2026-10-11 `retool.com` call, and whether a no-match call is billed.

## TODO(VERIFY: LiteLLM proxy accepts max_tokens and returns usage for the chosen models)

- Where: `src/costwise/adapters/llm/openai_compatible.py`.
- Source so far: the neatHack models page gives the base URL `https://litellm.vision.aivar.app/v1`, Bearer auth, the OpenAI-compatible `/chat/completions` route, and reads `choices[0].message.content`. The client also sends `max_tokens` and `temperature` and reads `usage.prompt_tokens` and `usage.completion_tokens`, as the build spec requires.
- 2026-10-12: the team key works. `GET /v1/models` and `GET /v1/model/info` returned 200 and list all seven models.
- 2026-10-12 dry run: 5 `claude-sonnet-4.6` calls returned `usage` (25,748 to 50,579 input tokens, 108 to 138 output tokens).
- Still unchecked: a `claude-haiku` call, and whether `max_tokens` is honored. No output came near the 512-token cap.

## neatlogs span attributes (manual, not a code marker)

- Where: `src/costwise/adapters/telemetry/attributes.py`, `task_spans.py`, `iteration_spans.py`.
- 2026-10-12 smoke run, as seen by the builder on the dashboard: every span showed as type CHAIN, the INPUT and OUTPUT columns were empty, and a failed guardrail showed only through its ERROR status, with no Passed/Blocked label.
- Cause: costwise sent its own attribute names. The neatlogs Python SDK 1.4.26 (PyPI wheel, `neatlogs/config/attribute-mapping.json`) defines the names the backend reads:
  - `neatlogs.span.kind`, lowercase (`workflow`, `agent`, `llm`, `tool`, `guardrail`, `evaluator`, ...);
  - `neatlogs.<kind>.input` and `neatlogs.<kind>.output`;
  - `neatlogs.llm.model_name`, `.provider`, `.token_count.prompt|completion|total`, `.cost_usd`;
  - `neatlogs.session.id`, `neatlogs.end_user.id`, `neatlogs.end_user.metadata` on the root span;
  - `neatlogs.guardrail.passed` as a boolean, plus `.name` and `.reason`.
- Change: spans now use those names. Each task is a `workflow` trace with a `tool` span for the company lookup, one `llm` span per model call, and an `evaluator` span for the label score. Each optimizer iteration is an `agent` trace with a `guardrail` span for the human approval, an `evaluator` span for the candidate run, and one `guardrail` span per check. All traces of a run share `neatlogs.session.id` = run id. `neatlogs.end_user.id` is the company domain being qualified, so the Users view lists companies, not people.
- Still unchecked: that the dashboard shows the kinds, inputs and outputs, Passed/Blocked, sessions, users, and cost after this change. Check: run `scripts/smoke_neatlogs.py` or `scripts/replay_neatlogs.py --run-id demo`.

## TODO(VERIFY: the Tail log of a text-format python3.12 function ends with this REPORT line)

- Where: `src/costwise/adapters/runners/report_line.py`, `_REPORT`.
- Source so far: the build spec gives `REPORT RequestId: <id> Duration: 123.45 ms Billed Duration: 124 ms Memory Size: 512 MB Max Memory Used: 100 MB`, plus `Init Duration` on cold starts. The parser accepts tabs or spaces between fields and uses the last REPORT line in the tail. The deploy script leaves the function's log format at its default; a JSON log format would not produce this line.
- Check: after `make lambda-deploy`, run `costwise eval baseline --run-id lambda-smoke --runner lambda --tasks 3` and confirm the results carry `billed_ms`, `memory_mb`, and a cold start on the first task.

## Lambda deployment (manual, not a code marker)

- Not yet run: `make lambda-deploy` needs AWS credentials for us-east-1, which the builder will set up before deploying.
- The deploy creates one IAM role (`costwise-qualify-role`, basic execution policy only) and one function (`costwise-qualify`, python3.12, x86_64, 60 s timeout), both tagged `project=costwise`. `LITELLM_BASE_URL` and `LITELLM_API_KEY` are copied from `.env` into the function's environment variables; nothing else is.
- `make lambda-build` was run locally on 2026-10-12: a 14.9 MB zip with Linux x86_64 wheels, the `costwise` package, `config/icp.yaml`, and 40 raw fixture files. No AWS call was made.

## neatlogs smoke check (manual, not a code marker)

- Source: neatlogs engineers, as recorded in the build spec, gave OTLP over gRPC at `ingest.neatlogs.com:443` with TLS and the `x-api-key` header. Only `neatlogs.workflow.*`, `neatlogs.session.*`, and `neatlogs.end_user.id` are filterable.
- 2026-10-12, session `smoke-1791796161019`: both traces arrived at 2:39 PM IST under the `costwise` service. The iteration trace nests its two guardrail spans, as described above.
- The `gen_ai.*` token fields from that run were replaced by `neatlogs.llm.*`; see "neatlogs span attributes" above.
- Still unchecked:
  - whether `neatlogs.workflow.*` attributes filter;
  - whether the model-call spans nest under the task span;
  - whether `neatlogs.llm.cost_usd` feeds the cost analytics.

## Collector image and file output (config, not a code marker)

- Where: `infra/collector/docker-compose.yaml` uses `otel/opentelemetry-collector-contrib:latest`, which is not pinned. Pin a tag once one is confirmed to work.
- Not yet run: whether the container can write `/data/telemetry.jsonl` on the mounted folder, since the image may not run as root.

## Model names and per-token prices (config values, done 2026-10-12)

- Builder's choice: `claude-haiku` as the cheap model and `claude-sonnet-4.6` as the strong model, in `config/policy.yaml`.
- Source: the proxy's `GET /v1/model/info`, which reports the rates it charges against the team key. `claude-haiku` maps to `bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0` at 1.10 / 5.50 USD per 1M input / output tokens. `claude-sonnet-4.6` maps to `bedrock/us.anthropic.claude-sonnet-4-6` at 3.30 / 16.50.
- Cross-check: [Anthropic's pricing page](https://docs.anthropic.com/en/docs/about-claude/pricing) lists Haiku 4.5 at 1 / 5 and Sonnet 4.6 at 3 / 15, so the proxy's rates are 10% higher. The AWS Bedrock pricing page did not render its current tables to a static fetch.

## Crustdata USD price per credit (config value, not a code marker)

- Where: `config/pricing.yaml`, `crustdata_usd_per_credit: "0.00"`.
- The docs give credits per call but not a dollar price per credit. The hackathon credits are free to participants, so the cost model needs a stated assumption before data cost is reported.

## Checked against the docs and one live call (2026-10-11)

- Endpoint `POST https://api.crustdata.com/company/enrich`, header `authorization: Bearer <key>`, header `x-api-version: 2025-11-01`.
- Response: top-level array of `{matched_on, match_type, matches: [{confidence_score, company_data}]}`. No match is `200` with `matches: []`; the spec also defines `404`.
- `fields` must list every section besides `basic_info`. costwise requests `basic_info, headcount, funding, hiring, taxonomy`.
- Field mapping used by `crustdata_mapper.py`: `headcount.total`, `funding.last_round_type` (values like `series_c`), `funding.total_investment_usd`, `hiring.openings_count`, `taxonomy.professional_network_industry`, `headcount.growth_percent.six_months`.
- `hiring.openings_count` counts all open roles. The response has no engineering-only open-role count, so `engineering_open_roles` holds total openings.
