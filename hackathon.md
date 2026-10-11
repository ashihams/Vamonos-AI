# neatHack build log

This file records what was built and what was checked. It does not establish contest rules and does not qualify the project.

## Project

costwise: an agent that lowers the cost per successful task of a company-qualification app and checks that quality did not drop.

Problem: model, infrastructure, and data cost can be cut without a measured record of whether successful qualifications fell.

## Team

Published handle: GitHub `ashihams`. No other name or teammate has been chosen for the submission.

## Stack

Used in the repository now: Python 3.12, uv, pydantic, pydantic-settings, PyYAML, httpx, tenacity, local JSON/JSONL files, and the Crustdata company enrich API.

Planned, not integrated: neatlogs, Entire, cfo.ai, LiteLLM, and AWS Lambda. `config/pricing.yaml` and `config/icp.yaml` still hold the placeholder values from the build spec.

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

Planned and not started: the local runner, neatlogs telemetry, the optimizer, the iteration loop, the business plan, and the demo. Lambda remains a stretch stage.

## Demo

No demo URL. Nothing has been deployed or submitted.

## Known limitations and next steps

- Model names and prices are placeholders. Lambda and Crustdata prices in the example file are the spec placeholders, not a verified bill.
- neatlogs, Entire, and cfo.ai are not connected. `entire enable` has not been run. There is no business plan yet.
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
