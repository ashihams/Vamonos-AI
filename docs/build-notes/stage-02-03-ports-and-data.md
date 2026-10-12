Written 2026-10-12 from the chat history and git log, after the stage was built.

## What Stages 2 and 3 had to deliver

Stage 2 in `docs/SPEC.md` is the ports, env settings with `SecretStr` keys, YAML loaders, JSONL run store, JSON config store, redacting logs, and the test fakes. Stage 3 is the Crustdata client, a mapper written against one real response, frozen fixtures, seeded labeling, and a seeded workload. Stage 3 says STOP AND ASK: do not guess the endpoint or the response shape.

## Human decisions

The Crustdata plugin could not sign in. Two auth attempts timed out, so its tools stayed unavailable. The human asked whether the stage could proceed without the plugin, then told Cursor to run the call itself. The chat had already been given the Crustdata key. It was used only for those commands and was not written into the repo.

`config/icp.yaml` was left at the spec thresholds at first, as the human asked. After labeling, only 3 of 20 companies fit. The human then chose all three offered fixes: add Series A–C firms around 100–900 employees, relax `min_engineering_open_roles`, and accept what remains. The minimum open-roles value went from 1 to 0.

Stages 2 and 3 were committed together. The chat records that several files changed in both stages, so a Stage 2-only commit would not have passed the checks on its own. The human asked for one pull request.

## How it was built

Stage 2 was written first, on `feat/domain-models`, and not committed. Ports cover the LLM, company data, runner, telemetry, storage, approval, and clock. Loaders turn `config/pricing.yaml`, `config/icp.yaml`, and `config/policy.yaml` into domain models. A validation failure raises `ConfigError` with the file name and field. The workload section is present and unread. `JsonlRunStore` and `FileConfigStore` round-trip `Decimal("0.10")`. Run ids that can escape the store root are rejected. JSON logs go to stderr. The project skill was added at `.cursor/skills/neathack/SKILL.md`.

`make check` on 2026-10-11 exited 0. ruff, mypy strict, import-linter (5 contracts), file length, and the TODO check passed. pytest: 140 passed. Coverage: domain 476 statements, 100% (gate 95); services 0 statements, 100% (gate 90); overall 729 statements, 1 missed, 99.86% (gate 80). The missed line is the empty validation-location branch in `yaml_loaders.py`. No network calls.

Stage 3 then called Crustdata's REST API directly. One live call for `retool.com` returned HTTP 200. `scripts/fixtures.py build` wrote `fixtures/raw/retool.com.json` (exit 0, fetched=1) and removed the funding contact email and phone before storage. `map_company` was written against that response. `engineering_open_roles` holds `hiring.openings_count`, which counts all open roles, because the response has no engineering-only count. The fixture service writes through a fixture-store port, because services cannot do file I/O.

`make check` exited 0. pytest: 170 passed. Coverage: domain 488 statements, 100%; services 83 statements, 100%; overall 99.90%. Client tests replay a trimmed response with HTTP mocked.

The same day, 20 domains in `fixtures/domains.txt` were fetched. The first run fetched 15. Crustdata returned HTTP 429 for the last 4, and the client does not retry 429. A rerun fetched those 4 and skipped the 16 already stored. That is 20 calls, about 40 credits by the published rate. Labels: 7 EASY, 13 HARD, 3 expected fits (`browserbase.com`, `langchain.com`, `retool.com`). Held out (seed 42): `cal.com`, `clerk.com`, `langchain.com`, `supabase.com`. The workload was reduced to 20 requests, 25% repeats, and 4 held out.

The follow-up search used Series A–C, 150–800 employees, Software Development, sorted by followers, 20 companies. An earlier search, 100–900 employees sorted by headcount, clustered near 900 and was replaced. Search cannot filter on `hiring.openings_count` (HTTP 400 "Unsupported columns"). `marketo.com` was skipped as acquired. 19 profiles were enriched. The 16th to 19th got HTTP 429 and were fetched after waiting. About 25 search credits and 38 enrich credits by the published rates.

Result for 39 companies: 8 expected fits, 31 not (about 21% fit). Every fit is EASY. Every HARD company lacks open-role data. Workload set to 40 requests, 25% repeats, 8 held out. Held out: `e2b.dev`, `linear.app`, `lucidya.com`, `neon.tech`, `opkey.com`, `retool.com`, `sarvam.ai`, `temporal.io`. The transcript records `make check` still passing with 170 tests after that change. Coverage for that rerun is not recorded.

Commit `244c39b` on `feat/ports-and-company-data`. PR #4 is open against `feat/domain-models`: https://github.com/ashihams/Vamonos-AI/pull/4. Raw company files stayed gitignored. The committed sample names no people.

## What did not work

The plugin sign-in timed out twice. HTTP 429 stopped the first fixture run and the later enrich batch. The client does not retry 429. The first company search was replaced because it clustered near the ICP headcount edge. A no-change open-roles filter was rejected by the search API.

## Left open

Credits actually billed per call, the USD price per credit, and whether the client should retry HTTP 429 using the documented `X-RateLimit-Reset` header. A model that always answers "not a fit" would score about 79%.
