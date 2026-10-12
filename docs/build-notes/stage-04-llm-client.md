Written 2026-10-12 from the chat history and git log, after the stage was built.

## What Stage 4 had to deliver

`docs/SPEC.md` asks for an OpenAI-compatible chat client, a retry decorator, a budget decorator, and `BudgetService`. The stage is STOP AND ASK: do not guess the cheap and strong model names or their prices.

## Human decisions

Cursor asked which pair to use, where prices should come from, and whether the team key was claimed. The models page listed seven models and a shared budget, and it did not publish per-token prices. The human said they did not have a Claude key and asked about free models, then said to carry on and come back later. A string pasted in chat was not the team key. The human said to move on and to open separate pull requests for the two stages that had been written together. Model names and prices stayed the spec placeholders. No live completion call was made.

## How it was built

`OpenAICompatibleClient` posts to `{base_url}/chat/completions` with a Bearer key, a 60 second timeout, `max_tokens`, and `temperature`. It returns the message text, prompt and completion token counts, and latency from the injected clock. HTTP 429, 5xx, and timeouts raise `TransientLLMError`. Other statuses and malformed bodies raise `LLMError`. Error messages never include the key. The client reports the configured model name, not the name the proxy returns.

`RetryingLLMClient` retries transient errors at most twice. `BudgetedLLMClient` checks the budget before a call and records cost after. `guarded_client` wraps budget around retry, so one logical call is checked once and charged once, and failed attempts cost nothing. `BudgetService` tracks spend in Decimal under a lock and refuses calls at the stop fraction of the cap. `usage_cost` in `domain/cost.py` is shared with the cost breakdown. `ports/budget.py` exists because an adapter may not import a service.

Commit `bce8be1`, 14 files, on `feat/llm-client`. New files: `adapters/llm/openai_compatible.py`, `adapters/llm/decorators.py`, `services/budget.py`, `ports/budget.py`, `tests/contract/test_openai_compatible.py`, `tests/unit/adapters/test_llm_decorators.py`, `tests/unit/services/test_budget.py`, and `tests/testing_fakes/fake_budget.py`. `TickingClock` was added for latency tests.

`make check` exited 0. pytest: 183 passed. Overall coverage 99.91%. Domain and services 100%. The tests cover success, a 429 then success, three 500s, a timeout, eight malformed or rejected responses, decorator order, and budget recording from 8 threads at once. Each commit passed `make check` on its own before it was pushed. `gh pr create` opened PR #5 against `feat/ports-and-company-data`: https://github.com/ashihams/Vamonos-AI/pull/5

## What did not work

Stages 4 and 5 had been written in one working tree. The Stage 5 test clock and the Stage 5 log entry were taken out of this commit and restored on the next branch, so this pull request contains only Stage 4. The budget check and the cost recording are separate steps. The stage report notes that calls already in flight can pass the stop line by up to one call each. That follows the spec, and a test bounds it.

## Left open

`TODO(VERIFY: LiteLLM proxy accepts max_tokens and returns usage for the chosen models)`, to be checked on the first live call. `config/pricing.yaml` still had placeholder names and zero prices.
