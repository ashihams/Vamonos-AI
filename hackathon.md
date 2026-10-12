# neatHack build log

This file records what was built and what was checked. It does not establish contest rules and does not qualify the project.

## Project

costwise: an agent that lowers the cost per successful task of a company-qualification app and checks that quality did not drop.

Problem: model, infrastructure, and data cost can be cut without a measured record of whether successful qualifications fell.

## Team

Published handle: GitHub `ashihams`. No other name or teammate has been chosen for the submission.

## Stack

Used in the repository now: Python 3.12, uv, pydantic, pydantic-settings, PyYAML, httpx, tenacity, local JSON/JSONL files, and the Crustdata company enrich API.

In use since 2026-10-12: the LiteLLM proxy (`claude-haiku`, `claude-sonnet-4.6`), neatlogs traces over OpenTelemetry, and Entire checkpoints. cfo.ai holds the business model, built in its chat from `cfo_inputs.json` (no code integration). AWS Lambda is not deployed (code done).

## Build log

### 2026-10-11 — Stage 2 ports, settings, loaders, stores, fakes

Completed in this session, not committed:

- Ports for the LLM, company data, runner, telemetry, storage, approval, and clock.
- `Settings` reads keys, the model budget, and paths from the process environment. Secrets are `SecretStr`. No env file is loaded.
- YAML loaders turn `config/pricing.yaml`, `config/icp.yaml`, and `config/policy.yaml` into domain models. A validation failure raises `ConfigError` with the file name and field. The workload section is present and unread.
- `JsonlRunStore` writes `results_v<n>.jsonl` and `iterations.jsonl`. `FileConfigStore` writes `config_v<n>.json`. A round trip kept `Decimal("0.10")` as a string in the file and as `Decimal` in the model. Run ids that can escape the store root are rejected.
- JSON logs go to stderr. A filter redacts Bearer values, `api_key`/`token`/`secret`/`authorization` assignments, and `sk-` keys.
- Test fakes: `FakeLLMClient`, `FakeCompanySource`, `FakeRunner`, `RecordingTelemetrySink`, `FixedClock`, `ScriptedApprover`, `InMemoryRunStore`, `InMemoryConfigStore`.
- Project skill added at `.cursor/skills/neathack/SKILL.md`.

`make check` was run from this project on 2026-10-11 and exited 0. pytest: 140 passed. Coverage: domain 476 statements, 100% (gate 95); services 0 statements, 100% (gate 90); overall 729 statements, 1 missed, 99.86% (gate 80). The missed line is the empty validation-location branch in `yaml_loaders.py`. Import-linter kept 5 contracts. No network calls; pytest-socket is on.

Already completed before this session, on branch `feat/domain-models`:

- Stage 0 scaffold: [pull/1](https://github.com/ashihams/Vamonos-AI/pull/1), open.
- Stage 1 domain models: [pull/2](https://github.com/ashihams/Vamonos-AI/pull/2), open, commit `0492160`.

### 2026-10-12 — Stage 3 company data and fixtures

Completed. Stages 2 and 3 were committed together as `244c39b` and opened as [PR #4](https://github.com/ashihams/Vamonos-AI/pull/4).

- The Crustdata company plugin could not sign in (two attempts timed out), so costwise calls Crustdata's REST API directly. The endpoint, auth header, and version header come from Crustdata's public docs. They were confirmed by one live call for `retool.com` (HTTP 200, 2 credits per the pricing page).
- `CrustdataClient` posts to `/company/enrich` with a 10 s timeout and retries server errors and timeouts twice. Other failures raise `DataSourceError`. It removes the funding contact email and phone before anything is stored.
- `map_company` was written against the real response. `engineering_open_roles` holds `hiring.openings_count`, which counts all open roles, because the response has no engineering-only count.
- Fixture store, fixture source, labeling with a seeded held-out split that keeps EASY and HARD in both splits, and a seeded workload builder.
- `scripts/fixtures.py build` fetched `retool.com` through the new client and wrote `fixtures/raw/retool.com.json` (exit 0, fetched=1).

`make check` exited 0. pytest: 170 passed. Coverage: domain 488 statements, 100%; services 83 statements, 100%; overall 99.90%. Client tests replay the trimmed real response with HTTP mocked.

Fixture build, same day: 20 domains listed in `fixtures/domains.txt`. The first run fetched 15. Crustdata returned HTTP 429 (rate limit) for the last 4, and the client does not retry 429. A rerun fetched those 4 and skipped the 16 already stored. That is 20 calls, about 40 credits by the published rate.

Labeling with `config/icp.yaml`: 7 EASY, 13 HARD, 3 expected fits (`browserbase.com`, `langchain.com`, `retool.com`). Many companies have no `hiring.openings_count`, which makes them HARD and not a fit. Held out (seed 42): `cal.com`, `clerk.com`, `langchain.com`, `supabase.com`. The workload was reduced to 20 requests, 25% repeats, and 4 held out to fit 20 companies. The workload built from the 16 EVAL companies had 20 requests over 15 distinct domains.

Fixing the fit imbalance, same session (builder's choice: add clear fits, relax the open-roles minimum, and accept what remains):

- Crustdata company search filtered on Series A–C, 150–800 employees, Software Development, sorted by followers, returned 20 companies. Search cannot filter on `hiring.openings_count` (HTTP 400 "Unsupported columns") and returned no openings values. The first search, 100–900 employees sorted by headcount, clustered near 900, which the ICP rule treats as near the 1000 threshold, so it was replaced.
- 19 of those were enriched (`marketo.com` skipped, acquired). Crustdata allows 15 enrich calls per minute; the 16th to 19th got HTTP 429 and were fetched after waiting. About 25 search credits and 38 enrich credits by the published rates.
- `min_engineering_open_roles` changed from 1 to 0. A company with no openings value is still not a fit and is HARD.
- Result for 39 companies: 8 expected fits, 31 not (about 21% fit). Every fit is EASY; every HARD company lacks open-role data. Workload set to 40 requests, 25% repeats, 8 held out. Held out: `e2b.dev`, `linear.app`, `lucidya.com`, `neon.tech`, `opkey.com`, `retool.com`, `sarvam.ai`, `temporal.io`. The 40-request workload has 30 distinct companies and 9 requests for fits.
- Accepted limitation: a model that always answers "not a fit" would score about 79%. Read success rates against that baseline.

Open: credits actually billed per call, the USD price per credit, and whether the client should retry HTTP 429 using the documented `X-RateLimit-Reset` header.

### 2026-10-12 — Stage 4 LLM client, retry, and budget (mocked only)

Completed and committed on its own branch, `feat/llm-client`, stacked on PR #4. The team's LiteLLM key has not been claimed yet, so no live model call has been made and every test mocks HTTP.

- `OpenAICompatibleClient` posts to `{base_url}/chat/completions` with a Bearer key, a 60 s timeout, `max_tokens`, and `temperature`. It returns the message text, prompt and completion token counts, and latency from the injected clock. HTTP 429, 5xx, and timeouts raise a retryable `TransientLLMError`; other statuses and malformed bodies raise `LLMError`. Error messages never include the key.
- `RetryingLLMClient` retries transient errors up to twice. `BudgetedLLMClient` checks the budget before a call and records its cost after. `guarded_client` wraps budget around retry, so one logical call is checked once and charged once, and failed attempts cost nothing.
- `BudgetService` tracks spend in Decimal under a lock and refuses calls once spend reaches a set fraction of the cap. The cost math is shared with the domain cost breakdown through a new `usage_cost` function.

`make check` exited 0. pytest: 183 passed. Overall coverage 99.91%; domain and services at 100%. The tests cover success, 429 then success, three 500s, timeouts, eight malformed or rejected responses, decorator order, and budget recording from 8 threads at once.

Open: confirm on the first live call that the proxy honors `max_tokens` and returns `usage`. Pick the cheap and strong models from the seven on the shared key and set their prices; `config/pricing.yaml` still has placeholders and zero prices.

### 2026-10-12 — Stage 5 qualification pipeline (mocked models only)

Completed and committed on its own branch, `feat/task-pipeline`, stacked on the Stage 4 branch. No model has been called; tests use a scripted fake model.

- `PayloadService` sends the full stored Crustdata payload when no fields are configured, otherwise only the listed normalized fields. It also gives a rough token estimate (characters / 4) for logs only.
- `RoutingService` picks the strong model when the policy's missing-field count or near-threshold rule applies, otherwise the policy default.
- `PromptService` states the ICP thresholds, where to find each value in both raw and normalized data, and demands JSON with exactly `icp_fit`, `reasons`, `headcount_band`, `stage`. Prompt version `qualify-v1` is logged on every build.
- `ParsingService` accepts bare JSON or one code fence and rejects wrong types, missing or extra keys, and surrounding prose.
- `TaskService` fetches the company, routes, trims, prompts, calls the model, and parses. On a parse failure it retries once on the strong model and records both calls. Data, model, budget, and parse failures come back as an error on the result instead of an exception.

`make check` exited 0. pytest: 200 passed. Overall coverage 99.92%; domain and services at 100%.

Measured for later cost planning: the 39 stored payloads average about 160 KB of JSON each (smallest 36 KB, largest 325 KB). The starting config sends the full payload, so each baseline call will carry tens of thousands of input tokens.

### 2026-10-12 — Stage 6 local runner, evaluation, and CLI (mocked models only)

Completed and committed on its own branch, `feat/eval-baseline`, stacked on the Stage 5 branch. The LiteLLM key is still not claimed, so the real `costwise dry-run --tasks 5` has not been run.

- `costwise` command with `fixtures build`, `fixtures label`, `eval baseline --run-id ID [--tasks N]`, and `dry-run [--tasks 5]`. It replaces `scripts/fixtures.py`. Settings come from process variables or the gitignored `.env`; unrelated keys there are ignored. Missing settings are reported by name only, never with values.
- `LocalRunner` runs the pipeline in-process, bills wall time rounded up to whole milliseconds at the configured memory, and offers every lever except Lambda memory. Reports print "infra cost modeled; memory lever not available locally".
- `EvaluationService` runs up to 4 tasks at once, returns results in request order, marks repeated domains as cache hits only when the cache is on, checks the budget before each task, and on a budget stop keeps finished results and logs a warning. Results are scored against labels, costed, sent to telemetry, and saved to `runs/<id>/`.
- `dry-run` projects measured model cost per task over the full plan (40 requests × baseline plus 3 iterations = 160 tasks) and refuses, exit 1, if that exceeds half of the remaining model budget. Telemetry is a no-op until the neatlogs stage.

`make check` exited 0. pytest: 227 passed. Overall coverage 99.88%; domain and services at 100%. An end-to-end test runs the real CLI and wiring on temporary fixtures with the model endpoint mocked.

Local smoke runs, same day: `costwise fixtures label` reproduced the committed labels (39 labeled, 8 held out, 8 fits; file content unchanged). `costwise eval baseline --run-id smoke --tasks 1` without a key exited 2 with "missing or invalid settings: litellm_api_key, litellm_base_url, model_budget_usd".

### 2026-10-12 — Stage 7 neatlogs telemetry (code done, dashboard check pending)

Completed in code and committed on its own branch, `feat/telemetry`, stacked on the Stage 6 branch, before the dashboard check (builder's choice). Nothing has been sent to neatlogs yet; the smoke check needs the builder's neatlogs key.

- `OtelSink` builds spans on the driver from returned results, with explicit timestamps. Each task gets one root span with run, task, config version, category, split, success, cache hit, infra source, and the three cost components. Each model call gets a nested child span with `gen_ai.*` model and token attributes.
- An optimizer iteration is one span with lever, decision, accepted, and reason, plus one child span per guardrail check with an OK or ERROR status.
- Summary gauges (cost per task, success rate, p95 latency) are labeled by run and config version, never task id. They go only to a local Collector, when one is configured.
- Export goes to neatlogs over OTLP/gRPC with TLS at `ingest.neatlogs.com:443` with the `x-api-key` header, through a dedicated tracer provider, only when `NEATLOGS_API_KEY` is set. Without the key, telemetry is a no-op.
- All attribute names live in `attributes.py`, and a test fails if another module spells one out.
- Collector config and Docker Compose file added; their output folder is gitignored. `scripts/smoke_neatlogs.py` sends one fake task trace (two model calls) and one iteration trace (one passed and one failed guardrail).

`make check` exited 0. pytest: 237 passed. Overall coverage 99.77%; domain and services at 100%. Span tree, timestamps, attributes, statuses, and gauge labels are checked with the OpenTelemetry in-memory exporter and reader.

Open: the dashboard check (token fields, filterable attributes, span nesting, guardrail rendering) and the unpinned Collector image.

### 2026-10-12 — Stage 8 optimizer proposals

Committed on its own branch, `feat/optimizer`, stacked on the Stage 7 branch. No model has been called; the model proposer is tested only against a scripted fake.

- The run summary now records `repeat_rate`, the share of tasks whose domain appeared earlier in the run. This is the evidence for the cache rule.
- `HeuristicProposer` tries five rules in a fixed order. It turns the cache on when domains repeat, and sends easy tasks to the cheap model when more than 10% of them used the strong one. It trims the payload to the three ICP fields when inputs average over 2,000 tokens, steps the output cap down when answers use under half of it, and steps Lambda memory down one size. It skips levers the runner lacks and changes already rejected.
- Predicted savings are upper bounds from the summary, for example the data cost times the repeat rate. Lowering the output cap predicts no saving, because tokens are billed as used.
- `LLMProposer` asks the strong model at temperature 0 for one JSON proposal. The prompt includes the lever bounds, the config, the evaluation-split summary, and past rejections. An invalid reply gets one repair attempt with the reason; a second failure or a model error returns nothing. A budget stop is not swallowed. Prompt version `propose-v1` is logged.
- `OptimizerService` tries the model proposer, then the heuristic. It re-validates every proposal and drops any that is out of bounds, makes no change, or repeats a rejected one.

`make check` exited 0. pytest: 271 passed. Overall coverage 99.79%; domain and services at 100%.

### 2026-10-12 — Stage 9 approval loop

Committed on its own branch, `feat/iteration`, stacked on the Stage 8 branch. No live run: the loop has run only on fakes and against a mocked model endpoint.

- `costwise optimize --run-id ID --iterations 3 [--auto-approve]` loads the stored version-1 baseline or runs it first. It refuses a stored baseline that covers different tasks, and a run id that already has iterations.
- Each iteration: the optimizer proposes from the EVAL summary only, and the approver decides. An approved change gets a new config version and a full re-run. It is kept only if all three guardrails pass against the current accepted config; otherwise it is rolled back. A Lambda memory change also applies the infrastructure, runs 3 warm-up invocations that are excluded from results, and restores the old setting on rollback.
- The loop stops at the iteration limit, when there is no usable proposal, after two rejections in a row (declined or failed guardrails), or at the budget stop line. A candidate cut short by the budget is recorded as not accepted. Every record is saved to `runs/<id>/iterations.jsonl` and sent to telemetry, which is flushed on exit.
- The terminal approver prints the lever, new value, rationale, predicted change, risk, and the EVAL success rate, cost per successful task, p95, and cost split. It then reads y/n and an optional note. `--auto-approve` tags the note `auto-approved`.

`make check` exited 0. pytest: 293 passed. Overall coverage 99.86%; domain and services at 100%. On the fake workload, the loop kept the cache (data cost 0.20 to 0.16 USD), rolled back cheap routing because hard companies were missed (EVAL and held-out success both failed), then kept a lower output cap. An end-to-end test runs `optimize --auto-approve` through the real wiring with the model endpoint mocked: 40 baseline calls, one proposer call, 40 candidate calls.

### 2026-10-12 — Stage 10 AWS Lambda runner (code done, not deployed)

Committed on its own branch, `feat/lambda`, stacked on the Stage 9 branch. Builder's choices before building: region us-east-1, function `costwise-qualify`, AWS credentials to be set up before deploying. Nothing has been deployed and no AWS call has been made.

- `LambdaRunner` invokes the function once per task with the log tail. It reads billed duration, memory size, and cold start from the `REPORT` line, and marks infrastructure cost as measured. It charges the local budget for every model call the function reports. A memory change updates the function and waits for the update to finish.
- The handler parses the event, builds the task once per container from bundled fixtures and the model endpoint, and returns the invocation as JSON. There is no telemetry export and no Crustdata key in Lambda.
- A failed invocation (function error or throttling) becomes one errored task instead of stopping the run. Cold starts are left out of latency percentiles.
- `make lambda-build`, `lambda-deploy`, `lambda-teardown`. The deploy creates one role (basic execution policy only) and one function, both tagged `project=costwise`, and reminds you to tear down after the demo.
- Fixed along the way: the log redaction filter treated the `sk-` inside `task-0001` as an API key and redacted task ids. It now needs a word boundary before `sk-`.

`make check` exited 0. pytest: 318 passed. Overall coverage 99.87%; domain and services at 100%. The runner is tested against botocore's Stubber (invoke, function error, throttling, bad payloads, memory update and waiter). `make lambda-build` ran locally: a 14.9 MB zip with Linux x86_64 wheels.

Open: deploying, and checking the REPORT line format against a real log.

### 2026-10-12 — Stage 11 report and cfo.ai inputs

Committed on its own branch, `feat/report`, stacked on the Stage 10 branch. No report has been produced from a live run yet; the outputs below come from fixed test data.

- `costwise report --run-id ID` writes `report.md`, `trajectory.csv`, `cfo_inputs.json`, and `trajectory.mmd` to `runs/<id>/report/`.
- The report compares the baseline with the last accepted version. Every cost line says where its number came from: model cost from measured tokens times configured prices, infra cost measured from Lambda REPORT lines or modeled from local wall time, and data cost modeled from fixture credits. Held-out success has its own labeled row.
- `cfo_inputs.json` carries the two unit costs, the split, task counts, and sources. Selling price per task and monthly volumes are left empty for the builder to fill in cfo.ai as assumptions.

`make check` exited 0. pytest: 341 passed. Overall coverage 99.88%; domain and services at 100%. Golden-file tests pin all four files for a fixed run (one change kept, one rolled back, one declined). The end-to-end CLI test now runs `report` after `optimize` against a mocked model endpoint.

### 2026-10-12 — Stage 12 docs and v0.1.0

Committed on its own branch, `feat/release`, stacked on the Stage 11 branch, and tagged `v0.1.0` locally. Stage 10 and 11 are open as stacked pull requests #11 and #12.

- README rewritten: what costwise is, the metric, an architecture diagram in Mermaid, quickstart, the demo command sequence, and limitations (modeled data cost, frozen fixtures, rule-based labels, small infra lever, placeholder prices, no live run yet).
- `docs/architecture.md`: layers and the import rules that enforce them, a table of ports and adapters, and step-by-step guides for adding a lever or a runner.
- `docs/open-verifications.md` now opens with a status table. All nine open items are still open; only the Crustdata endpoint check is done.
- `scripts/dry_run.py` runs the 5-task budget check.
- Removed the unused all-in-one `Settings` class; its tests now cover `EvalSettings`, which the CLI uses.
- History scan for secrets (counts only, values never printed): no API-key, AWS-key, private-key, or bearer-token patterns. Two `LITELLM_LICENSE=` lines in tests are placeholders (`unrelated`, `unrelated-value`) that check unrelated `.env` keys are ignored. No `.env`, raw fixture, or sample file was ever committed. The spec still asks the builder to run their own `git log -p` check.

`make check` exited 0. pytest: 343 passed. Overall coverage 99.88%; domain and services at 100%. A fresh clone of the commit passed `make install && make check` with no `.env` and no raw fixtures. In that clone, `costwise --help` listed every command, and `scripts/dry_run.py` without keys exited 2 naming the missing settings.

### 2026-10-12 — LiteLLM key claimed, models and prices set

- The team key is in the local `.env`, which is gitignored. The proxy's model list and model info calls returned 200; no completion call has been made yet.
- Builder's choice: `claude-haiku` (cheap) and `claude-sonnet-4.6` (strong). The proxy maps them to Bedrock Claude Haiku 4.5 and Claude Sonnet 4.6.
- `config/pricing.yaml` uses the proxy's own rates: 1.10 / 5.50 and 3.30 / 16.50 USD per 1M input / output tokens. These are 10% above Anthropic's list prices.
- Builder's choice: the Crustdata price per credit stays `0.00`, because data was free under the hackathon credits. The report must say so.

`make check` exited 0. pytest: 343 passed.

First live run: `scripts/dry_run.py --iterations 1`. All 5 of 5 tasks succeeded on `claude-sonnet-4.6`, with the full company payload of 25,748 to 50,579 input tokens per task. Model cost was 0.607 USD, about 0.121 per task. Infra cost was 0.0003 USD, modeled locally. Data cost was 0, by choice. The projected cost of a 40-task baseline plus one iteration (80 tasks) is 9.71 USD. That is more than half of the 9.39 USD left under `MODEL_BUDGET_USD=10`, so the dry run refused (exit 1), as designed.

Builder's choice after the refusal: shrink the workload to 28 requests (23 evaluation, 5 held-out) and set `MODEL_BUDGET_USD=15`. The contract tests now pin their own 40-request workload, so tuning the real config cannot break them. `make check` exited 0 (343 passed).

- Second dry run (`--iterations 1 --run-id dry-run-2`): all 5 of 5 succeeded, 0.608 USD. The projected cost of 56 tasks is 6.80 USD, within half of the 14.39 left. Passed.
- Live baseline (`eval baseline --run-id demo`): 28 tasks, all on `claude-sonnet-4.6` with the full payload.
  - Success: 27. Evaluation 22 of 23 (95.7%); held-out 5 of 5 (100%).
  - The miss, `task-0010`, returned an invalid answer on the first try and on the retry (`ParseError`).
  - Cost: model 2.887 USD, infra 0.0015 USD (modeled), data 0. Total 2.888 USD, so about 0.107 USD per successful task.
  - Input tokens per call ranged from 7,495 to 50,579; output never exceeded 281.
- Spent on the shared key so far (costwise's own accounting at the proxy's rates): about 4.10 USD.

First live optimize iteration (`optimize --run-id demo --iterations 1 --auto-approve`, builder's choice to auto-approve):

- The model proposer suggested routing to `claude-haiku` by default, escalating to Sonnet when 2 or more fields are missing or the company is near a threshold. It predicted a 35% saving, at medium risk.
- Version 2 ran 27 of 28 tasks on Haiku. Model cost fell from 2.887 to 1.023 USD, and cost per successful task fell from 0.107 to 0.054 USD.
- Quality fell: evaluation success 17 of 23 (73.9%, floor 93.7%), held-out 2 of 5 (40%, floor 98%). Both success guardrails failed, so the change was rolled back and v1 stays accepted. The p95 check passed (5,662 ms against a 6,139 ms limit).
- This is the guardrails working on real data: the cheap model halves the unit cost, but loses too many correct answers.

`costwise report --run-id demo` wrote `runs/demo/report/`. The report now explains that zero data cost means the hackathon Crustdata credits were free; a test covers this, and `make check` passed (344 tests). Spent on the shared key: about 5.1 USD, plus one proposer call.

Second live run (`optimize --run-id demo-2 --iterations 2 --auto-approve`, builder's choice), with a fresh baseline:

- Baseline v1 nearly matched the first run: 27 of 28 tasks, 2.886 USD in model cost, 0.107 USD per successful task.
- Iteration 1: the model proposer suggested Haiku routing again (escalating on 2 or more missing fields), predicting a 45% saving. Rejections are remembered only within a run, so this repeated the change rejected in `demo`. The result was the same: evaluation 73.9%, held-out 40%, rolled back. It cost 1.02 USD.
- Iteration 2: the proposer suggested turning on the company-data cache, predicting a 20% saving. All guardrails passed (evaluation 95.7%, held-out 100%, p95 5,771 against a 7,045 ms limit), so v3 was kept.
- **The kept cache change saved nothing:** 0.106967 to 0.106976 USD per successful task. The cache only avoids Crustdata credits, which are priced at 0.00, and it does not shrink what is sent to the model. The proposer's claim that caching would reduce input tokens was wrong. The loop keeps any change that passes the guardrails; it does not require a saving. This is a design gap to raise, not hide.
- Spent on the shared key so far: about 11.9 USD by costwise's accounting (baseline 2.89, v2 1.02, v3 2.89, plus two proposer calls, on top of the earlier 5.1). About 8 USD is left.

Evidence from both runs is in `evidence/demo-2026-10-12/` and `evidence/demo-2-2026-10-12/`.

### 2026-10-12 — Fixes from the live runs: require a saving, remember rejections

Builder's choice after `demo-2`: fix both gaps it exposed. No paid calls were made for this.

- A change is now kept only if the guardrails pass **and** cost per successful task (both splits) drops by at least `min_saving_pct`, set to 1% in `config/policy.yaml`. Otherwise it is rolled back with "guardrails passed but no saving". Under this rule the `demo-2` cache change (0.106967 to 0.106976 USD) would have been rolled back.
- Rejected proposals are now remembered across runs. Before proposing, `optimize` collects non-accepted proposals from other runs whose version-1 config matches this run's. Both proposers see them, and an exact repeat is dropped. A near-duplicate, such as the same routing with a different threshold, is only discouraged through the prompt, not blocked.
- New tests cover the saving rule, cross-run memory, and `RunStore.run_ids`. The integration fake now responds to the output cap and Lambda memory, so those levers change cost in tests.

`make check` exited 0. pytest: 353 passed.

### 2026-10-12 — neatlogs key claimed, smoke traces sent

- The neatlogs key is in the local `.env` (gitignored).
- `scripts/smoke_neatlogs.py` sent one fake task trace and one fake iteration trace as session `smoke-1791796161019`, with no exporter errors.
- Dashboard check by the builder: both traces arrived at 2:39 PM IST. The iteration trace shows `optimizer_iteration`, with `guardrail eval_success` and a failed `guardrail heldout_success` (ERROR) under it, ending with error "smoke failure". neatlogs flags that trace "Execution Failed". The task trace, with its token counts and model-call spans, has not been opened yet.
- Builder's choice: no more paid model runs. The cfo.ai model will use the measured numbers already in `evidence/`. Those show no cost saving: the only cheaper change, Haiku routing, was rolled back for losing quality.

### 2026-10-12 — Entire enabled, build notes checkpointed

- Entire CLI 0.11.4, built with `go install` because the PowerShell installer got HTTP 403 from the GitHub API. `entire enable --agent cursor`, with telemetry off and local redaction rules for the model and neatlogs keys. Past chats were not imported, because they contain keys.
- Builder's choice: instead of rebuilding the repo, a new Cursor chat wrote one build-notes file per stage PR (`docs/build-notes/stage-*.md`) from `hackathon.md`, the git log, and the chat history. Each file says on its first line that it was written after the stage was built.
- Entire's Cursor hooks did not fire, since its log shows no hook calls. The chat was linked to each notes commit with `entire session attach --agent cursor --force`. All 13 notes commits carry `Entire-Checkpoint: 01M4QYRRBQ1DCFT4WRZ808FXGW`, one checkpoint for the one chat that wrote them.
- Before pushing, the checkpoint and all notes commits were scanned for keys, `.env` lines, and personal-data patterns: none found.
- Pushed. `refs/entire/checkpoints/GW/01M4QYRRBQ1DCFT4WRZ808FXGW` is on GitHub. After the builder installed the Entire GitHub App, the repo was mirrored, and the checkpoint shows publicly at [entire.io/gh/ashihams/Vamonos-AI/commit/68602e8](https://entire.io/gh/ashihams/Vamonos-AI/commit/68602e828e325879ab67cbc76637e4f4676a0a7f).

### 2026-10-12 — cfo.ai economics and business plan

- Shared model: [app.cfo.ai/s/nBLdLr1K8qA0Jnd3](https://app.cfo.ai/s/nBLdLr1K8qA0Jnd3), "costwise — Economics & business plan", built in cfo.ai's chat from `evidence/demo-2-2026-10-12/cfo_inputs.json`.
- Measured inputs: run `demo-2`, 27 of 28 tasks successful, 0.106967 versus 0.106976 USD per success (no saving). Model cost is measured tokens times configured prices, infrastructure is modeled, and data was credit-funded.
- Builder's assumptions, labeled as such in the model: 0.50 USD per delivered qualification (including "does not fit" answers), 5,000 / 25,000 / 100,000 per month, and 200 USD fixed monthly costs.
- cfo.ai's results: gross profit 0.393 USD per qualification. Unit gross profit stays positive only while Crustdata costs less than 0.1965 USD per credit, at two credits per lookup. The rejected Haiku routing (about 0.054 USD per success, 40% held-out accuracy) is shown as an unshipped counterfactual.
- cfo.ai notes the held-out sample size as "not provided". It was 5 tasks, and the evaluation set 23.

### 2026-10-12 — neatlogs spans rebuilt on the SDK's attribute names

- Why: in the smoke run, every span showed as type CHAIN, the INPUT and OUTPUT columns were empty, and guardrails had no Passed/Blocked label. costwise had been sending its own attribute names.
- Source: the neatlogs Python SDK 1.4.26 wheel from PyPI, file `neatlogs/config/attribute-mapping.json`, which lists the attribute names the backend reads. The SDK itself is not a dependency; spans are still built with OpenTelemetry.
- Task traces: the task is a `workflow` root, with `neatlogs.session.id` = run id, `neatlogs.end_user.id` = company domain, and JSON input and output. Under it are:
  - a `tool` span for the company lookup;
  - one `llm` span per model call, carrying model, provider, token counts, and `cost_usd` from `config/pricing.yaml`;
  - an `evaluator` span for the label score.
- Iteration traces: the iteration is an `agent` root, with the proposal as input and the decision as output. Under it are:
  - a `guardrail` span for the human approval;
  - an `evaluator` span with the candidate's results;
  - one `guardrail` span per check, with `neatlogs.guardrail.passed` as a boolean.
- New `scripts/replay_neatlogs.py` re-sends stored runs without model calls. It sent `demo` (56 task traces, 1 iteration) and `demo-2` (84 task traces, 2 iterations) with no exporter errors. Task spans keep their recorded start times; iteration spans are stamped at replay time.
- The end-to-end optimize test was flaky under coverage: with a mocked model, baseline p95 is a few milliseconds, so the 1.25× latency guardrail tripped on scheduler noise. That test's own workspace now sets `p95_multiplier: 1000.0`; `config/policy.yaml` is unchanged.
- `make check` exited 0. pytest: 358 passed, total coverage 99.89%.
- Dashboard check of the rebuilt traces: not done yet.

### 2026-10-12 — results dashboard

- New `costwise dashboard` command, behind a `DashboardSink` port, writes the stored runs to `dashboard/public/data/dashboard.json`. It exported `demo` and `demo-2`: 2 runs, 140 task results. No new model calls.
- `dashboard/` is a static Vite + React + TypeScript + Tailwind + Framer Motion site in a dark "Linear"-style theme. Sections: an overview with the cost-per-success trajectory, the iteration timeline (proposal, reasoning, approval, predicted versus measured change, guardrails), the version table, a filterable task table with per-call costs, the sponsor stack, and the method notes saying what is measured and what is modeled.
- Every number on the page comes from the exported file. The Lambda tile says "Runner built, not deployed".
- Checked in a desktop browser: all sections render, rows expand, the run switch works. Phone-width layout not checked in a browser.
- `npm run build` passed. `make check` exited 0: 367 passed, total coverage 99.89%.

- Deployed on the builder's instruction to Vercel production: [dashboard-ten-beryl-63.vercel.app](https://dashboard-ten-beryl-63.vercel.app). The page and `/data/dashboard.json` both returned HTTP 200 without a login.

### 2026-10-12 — Lambda runner deployed and smoke-tested

- On the builder's instruction, `infra/aws/deploy.py deploy` ran against the builder's own AWS account in ap-south-1, not the hackathon's us-east-1 credits. It created one IAM role with the basic execution policy and the function `costwise-qualify` (python3.12, 1024 MB), both tagged `project=costwise`. Only the LiteLLM URL and key went into the function's environment.
- Smoke run `lambda-smoke`, 3 tasks on Lambda: 3 of 3 successful. Model cost 0.351249 USD. Infrastructure 0.000225 USD, now measured from each invocation's `REPORT` line instead of modeled.
- The three invocations billed 4236, 4568 and 4666 ms at 1024 MB, and all three were cold starts, because the evaluator runs up to 4 tasks at once.
- This closes the `REPORT`-line `TODO(VERIFY)`. The Lambda per-GB-second and per-request prices are still build spec values, unchecked for ap-south-1.
- Torn down right after, on the builder's instruction: the function, the policy attachment, and the role were deleted, and a follow-up listing found no `costwise` function or role left.

### 2026-10-12 — dashboard: approval replay and quality metrics

- New "Be the approver" section. It steps through the recorded proposals of the selected run, with `apply this change? [y/n]` as in the terminal.
  - **Approve:** shows the recorded full-workload re-run, each guardrail check, and the verdict.
  - **Reject:** does what `costwise optimize` does: no run, current config kept. Two rejections in a row end the loop.
  - It is labeled as a replay; no model is called on the site.
  - If the visitor's choices leave a different config than the recording had, the page says later proposals are still the recorded ones.
- New "Quality beyond success rate" section. Per version: real fits caught, non-fits answered correctly, balanced accuracy, and the score of always answering "not a fit". These are recovered from recorded answers, because a task succeeds exactly when the model's answer equals the label.
  - In `demo-2`, the rolled-back routing change caught 4 of 4 fits but only 15 of 23 non-fits: 67.9%, below the 85.2% that always answering "not a fit" scores.
  - v1 and v3 caught 4 of 4 fits and 23 of 23 non-fits; the one failure had no parsed answer.
- README limitations updated: the Lambda smoke run, the guardrail's sensitivity on 5 held-out and 23 evaluation tasks, and the replay's limits.

Planned and not started: the dashboard check of the rebuilt traces and the demo video.

## Demo

Results dashboard: [dashboard-ten-beryl-63.vercel.app](https://dashboard-ten-beryl-63.vercel.app), a static site showing the recorded runs `demo` and `demo-2`. Nothing has been submitted.

## Known limitations and next steps

- Model prices are the LiteLLM proxy's own rates. Lambda prices are unverified, and Crustdata data is priced at 0 because the hackathon credits were free.
- The cfo.ai model rests on one 28-task run and on the builder's price and volume assumptions. Entire covers only the build-notes commits, not the original build sessions.
- One defensive branch, a validation error with no field location, has no test.
- 39 fixture companies, of which 8 fit the ICP. Always answering "not a fit" would score about 79%. The workload is 40 requests rather than the spec's 60.
- A full enrich payload is about 230 KB per company. Sending it whole to a model would be expensive, so payload trimming matters in later stages.

## Submission

Fetched 2026-10-11 from [neatlogs.com/hackathon](https://neatlogs.com/hackathon) and [luma.com/s5blr882](https://luma.com/s5blr882).

Confirmed on the neatlogs page:

- Dates: 10–12 October 2026. Start Saturday 12:30 PM IST. Kickoff 9:00 AM IST on 10 October. Submit Monday 12 October, 7:00–11:55 PM IST planned close. Winners 16 October.
- One track: “Build an agent that works (literally).”
- The project must use neatlogs, Entire, and cfo.ai. The demo must cover all three.
- Submit one public quote post of the official neatlogs post on X, with team, name, project, public repo, and demo. Include a video of at most 3 minutes covering architecture, implementation, runtime, reasoning, and result for each tool. Evidence stays in the repo. Code must be committed during the hackathon.
- Judging weights published there: agent 30%, neatlogs/Entire/cfo.ai 25%, demo video 20%, building in public 15%, usefulness and originality 10%.
- Prizes published there: $19,000 including credits. 1st $2,000 plus $5,000 Dodo. 2nd $1,000 plus $3,000 Dodo. 3rd $500 plus $1,000 Dodo. Each winner 3 months neatlogs Pro, stated worth $1,500. Community winner $500, scored separately.
- Credits published there: AWS $25 for the first 350 teams to web check-in, us-east-1, no Bedrock. LiteLLM $20 shared Nova/Claude via the check-in email, models page `neatlogs.com/hackathon/models`. Crustdata 5,000 credits for participants. cfo.ai requires a card; cancel immediately in Settings → Billing. Credits come from the neatHack team.

Pending:

- The official X post URL. The page says the Submit on X button appears when the window is live. Opening a draft is not a submission.
- The final cutoff. The page says it will be announced on Discord.
- Luma says registration is closed and still says “Tracks drop on October 8.” The neatlogs page fetched the same day names one track.
- Demo URL, public evidence for neatlogs, Entire, and cfo.ai, and the business plan.
