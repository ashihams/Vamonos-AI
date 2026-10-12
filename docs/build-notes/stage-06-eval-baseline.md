Written 2026-10-12 from the chat history and git log, after the stage was built.

## What Stage 6 had to deliver

`docs/SPEC.md` asks for a local runner, evaluation, and a thin CLI that can run a baseline and a dry run. Acceptance includes `make check` and a human `costwise dry-run --tasks 5` against the real key. That live command had not been run, because the LiteLLM key was still not claimed. No AskQuestion is recorded for this stage. The previous human message was to open the Stage 5 pull request and move on.

## How it was built

`costwise` replaces `scripts/fixtures.py`, which this commit deletes. Commands: `fixtures build`, `fixtures label`, `eval baseline --run-id ID [--tasks N]`, and `dry-run [--tasks 5]`. Settings come from the process environment or the gitignored `.env`. Unrelated keys there are ignored. Missing settings are reported by name only.

`LocalRunner` runs the pipeline in-process. It bills wall time rounded up to whole milliseconds at the configured memory. It offers every lever except Lambda memory. Reports print "infra cost modeled; memory lever not available locally". `apply_infra` is a no-op. The runner reaches the pipeline through a new `QualificationTask` port, because adapters may not import services.

`EvaluationService` runs up to 4 tasks at once and returns results in request order. Repeated domains are cache hits only when the cache is on. The budget is checked before each task. On a budget stop, finished results are kept and a warning is logged. Results are scored, costed, sent to telemetry, and saved. The spec's 7 constructor arguments are grouped down to 5. Baseline and dry-run steps sit in `BaselineService` so the commands stay thin. `bootstrap.py` is the only place concrete adapters are chosen. Telemetry is a no-op until Stage 7.

`dry-run` projects measured model cost per task over the full plan (40 requests times a baseline plus 3 iterations = 160 tasks) and refuses, exit 1, if that exceeds half of the remaining model budget.

Commit `dd4892f` on `feat/eval-baseline`, 24 files. New code includes `local_runner.py`, `system_clock.py`, `null_sink.py`, `bootstrap.py`, `services/evaluation.py`, `services/baseline.py`, and `apps/cli/main.py`, `commands_eval.py`, `commands_fixtures.py`, `support.py`. `pyproject.toml` adds the `costwise` command.

`make check` exited 0. pytest: 227 passed. Overall coverage 99.88%. Domain and services 100%. An end-to-end test runs the real CLI and wiring on temporary fixtures with the model endpoint mocked. It checks that the key from `.env` is sent, the costs, and the files under `runs/`.

Local smoke, same day: `costwise fixtures label` reproduced the committed labels (39 labeled, 8 held out, 8 fits; file content unchanged). `costwise eval baseline --run-id smoke --tasks 1` without a key exited 2 with "missing or invalid settings: litellm_api_key, litellm_base_url, model_budget_usd".

`gh pr create` opened PR #7 against `feat/task-pipeline`: https://github.com/ashihams/Vamonos-AI/pull/7

## What did not work

The spec's acceptance command, a real 5-task dry run, could not be run. The smoke baseline without a key is the check that was recorded instead. ruff, mypy, and pytest results beyond the `make check` exit and the 227 count are not recorded separately.

## Left open

No new `TODO(VERIFY)` items. Model names, prices, and whether the proxy honors `max_tokens` and returns usage still waited on the key.
