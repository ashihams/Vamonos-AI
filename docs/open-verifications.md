# Open verifications

## TODO(VERIFY: Crustdata credits charged per company enrich call)

- Where: `src/costwise/adapters/data/crustdata_client.py`, `CREDITS_PER_ENRICH = Decimal(2)`.
- Source so far: the Crustdata pricing page lists `/company/enrich` at 2 credits per record, plus 2 when `technographics` is requested. costwise does not request `technographics`.
- Still unchecked: what the dashboard actually charged for the 2026-10-11 `retool.com` call, and whether a no-match call is billed.

## TODO(VERIFY: LiteLLM proxy accepts max_tokens and returns usage for the chosen models)

- Where: `src/costwise/adapters/llm/openai_compatible.py`.
- Source so far: the neatHack models page gives the base URL `https://litellm.vision.aivar.app/v1`, Bearer auth, the OpenAI-compatible `/chat/completions` route, and reads `choices[0].message.content`. The client also sends `max_tokens` and `temperature` and reads `usage.prompt_tokens` and `usage.completion_tokens`, as the build spec requires.
- Still unchecked: no live call yet, because the team key has not been claimed. Confirm one Nova and one Claude call return `usage`, and that `max_tokens` is honored.

## TODO(VERIFY: neatlogs renders neatlogs.guardrail.passed on plain OTLP spans as Passed/Blocked)

- Where: `src/costwise/adapters/telemetry/attributes.py`, `GUARDRAIL_PASSED`, set on each guardrail child span of an iteration span.
- Source so far: the build spec names the attribute. The span status is also set to OK or ERROR, so the outcome shows even if neatlogs ignores the attribute.
- Check: run `scripts/smoke_neatlogs.py` and look at the `guardrail heldout_success` span, which is a failed check.

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
- Still unchecked:
  - whether the smoke trace arrives;
  - whether `gen_ai.usage.*` token fields show;
  - whether `neatlogs.workflow.*` attributes filter;
  - whether the two model-call spans nest under the task span;
  - whether numeric cost attributes keep their values.

## Collector image and file output (config, not a code marker)

- Where: `infra/collector/docker-compose.yaml` uses `otel/opentelemetry-collector-contrib:latest`, which is not pinned. Pin a tag once one is confirmed to work.
- Not yet run: whether the container can write `/data/telemetry.jsonl` on the mounted folder, since the image may not run as root.

## Model names and per-token prices (config values, not code markers)

- Where: `config/pricing.yaml` and `config/policy.yaml` still hold `<cheap-model-name>`, `<strong-model-name>`, and `"0.00"` prices.
- Available on the shared key (models page, 2026-10-12): `nova-micro`, `nova-lite`, `nova-pro`, `nova-2-lite`, `claude-haiku`, `claude-sonnet-4.6`, `claude-opus-4.6`. The page publishes no prices.
- Waiting on the builder to pick the cheap and strong pair and the price source.

## Crustdata USD price per credit (config value, not a code marker)

- Where: `config/pricing.yaml`, `crustdata_usd_per_credit: "0.00"`.
- The docs give credits per call but not a dollar price per credit. The hackathon credits are free to participants, so the cost model needs a stated assumption before data cost is reported.

## Checked against the docs and one live call (2026-10-11)

- Endpoint `POST https://api.crustdata.com/company/enrich`, header `authorization: Bearer <key>`, header `x-api-version: 2025-11-01`.
- Response: top-level array of `{matched_on, match_type, matches: [{confidence_score, company_data}]}`. No match is `200` with `matches: []`; the spec also defines `404`.
- `fields` must list every section besides `basic_info`. costwise requests `basic_info, headcount, funding, hiring, taxonomy`.
- Field mapping used by `crustdata_mapper.py`: `headcount.total`, `funding.last_round_type` (values like `series_c`), `funding.total_investment_usd`, `hiring.openings_count`, `taxonomy.professional_network_industry`, `headcount.growth_percent.six_months`.
- `hiring.openings_count` counts all open roles. The response has no engineering-only open-role count, so `engineering_open_roles` holds total openings.
