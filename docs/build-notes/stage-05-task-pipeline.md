Written 2026-10-12 from the chat history and git log, after the stage was built.

## What Stage 5 had to deliver

`docs/SPEC.md` asks for the qualification pipeline as small services: payload trimming, routing, the prompt, parsing, and `TaskService`. No STOP AND ASK. The human said to move to Stage 5 and to discuss models and prices after the key and credits arrived, and to open a separate pull request from Stage 4.

## How it was built

No model was called. Tests use a scripted fake. `PayloadService` sends the full stored payload when no fields are configured, otherwise only the listed normalized fields, in that order. `estimate_tokens` is characters divided by 4, for logs only. `RoutingService` picks the strong model when the missing-field count or the near-threshold rule applies, otherwise the policy default. `PromptService` states the ICP thresholds, where each value lives in raw and normalized data, and demands JSON with exactly `icp_fit`, `reasons`, `headcount_band`, and `stage`. Prompt version `qualify-v1` is logged on every build. `ParsingService` accepts bare JSON or one code fence and rejects wrong types, missing or extra keys, and surrounding prose. `TaskService` fetches, routes, trims, prompts, calls, and parses. A parse failure retries once on the strong model and records both calls. A cache hit costs zero credits. Data, model, budget, and parse failures come back as an error on the result.

The spec's `TaskService` takes 7 constructor arguments. Routing, payload, prompt, parser, and the ICP rule are grouped into `TaskSteps`, so the service takes 4. `trim` also takes the normalized record, because the field names belong to the record.

Commit `90ce098` on `feat/task-pipeline`, stacked on `bce8be1`. Ten files: `services/payload.py`, `routing.py`, `prompt.py`, `parsing.py`, `task.py`, `tests/unit/services/test_task.py`, `test_task_steps.py`, and `SteppingClock` in `fake_clock.py`. The Stage 5 clock and log entry had been held out of the Stage 4 commit and put back here. `make check` passed on this commit before it was pushed.

pytest: 200 passed. Overall coverage 99.92%. Domain and services 100% (services gate 90%). Covered cases include the normal path, a cache hit zeroing credits, one strong retry after a parse failure, a second parse failure reported as an error, a model failure, a tripped budget, an unknown domain, trimmed payloads, routing by thresholds, and six kinds of bad parser output.

`gh pr create` opened PR #6 against `feat/llm-client`: https://github.com/ashihams/Vamonos-AI/pull/6

Measured for later cost planning: the 39 stored payloads average about 160 KB of JSON each (smallest 36 KB, largest 325 KB). The starting config sends the full payload.

## What did not work

Model calls that fail outright have no token usage, so they are not listed on the result. Retries inside the retry wrapper are not visible either. That is recorded as a reading of the stage, not a later code change.

## Left open

No new `TODO(VERIFY)` items. Model names, prices, and whether the proxy honors `max_tokens` and returns `usage` still waited on the LiteLLM key.
