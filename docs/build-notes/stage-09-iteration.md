Written 2026-10-12 from the chat history and git log, after the stage was built.

## What Stage 9 had to deliver

`docs/SPEC.md` asks for the full loop: propose, approve, apply, re-run, guardrails, keep or roll back. The CLI is `costwise optimize --run-id ID --iterations 3 [--auto-approve]`. No STOP AND ASK. The human had said to open the Stage 8 pull request and move to the next phase. After this stage they asked for the pull request and how many stages were left.

## How it was built

No live run. The loop ran on fakes and against a mocked model endpoint. `optimize` loads the stored version-1 baseline or runs it first. It refuses a stored baseline that covers different tasks, and a run id that already has iterations. Each iteration proposes from the EVAL summary only. The approver decides. An approved change gets a new config version and a full re-run. It is kept only if all three guardrails pass against the current accepted config. Otherwise it is rolled back. A Lambda memory change also applies the infrastructure, runs 3 warm-up invocations that are excluded from results, and restores the old setting on rollback.

The loop stops at the iteration limit, when there is no usable proposal, after two rejections in a row (declined or failed guardrails), or at the budget stop line. A candidate cut short by the budget is recorded as not accepted. Every record is saved to `runs/<id>/iterations.jsonl` and sent to telemetry, which is flushed on exit.

The terminal approver prints the lever, new value, rationale, predicted change, risk, and the EVAL success rate, cost per successful task, p95, and cost split. It then reads y/n and an optional note. `--auto-approve` tags the note `auto-approved`. The spec's nine constructor arguments are grouped into two bundles to stay within the 5-argument limit. `MissingStoreError` separates "no baseline stored yet" from a corrupt store.

Commit `1871008` on `feat/iteration`, 19 files. New: `services/iteration.py`, `services/verdict.py`, `adapters/approval/cli_approver.py`, `adapters/approval/auto_approver.py`, `apps/cli/commands_optimize.py`. Tests: `tests/integration/test_iteration_loop.py` (13) and `tests/unit/adapters/test_approvers.py` (5), plus updated CLI and end-to-end tests.

`make check` exited 0. pytest: 293 passed. Overall coverage 99.86%. Domain and services 100%. On the fake workload the loop kept the cache (data cost 0.20 to 0.16 USD), rolled back cheap routing because hard companies were missed (EVAL and held-out success both failed), then kept a lower output cap. An end-to-end test runs `optimize --auto-approve` through the real wiring with the model endpoint mocked: 40 baseline calls, one proposer call, 40 candidate calls.

PR #10 is open against `feat/optimizer`: https://github.com/ashihams/Vamonos-AI/pull/10

## What did not work

Nothing in the chat is recorded as a failing `make check` for this stage. The stage report flags readings, not red tests. A candidate is compared with the current accepted config, not the original baseline, so over three accepted iterations success could slide by up to 3 times 2 points. Both a human "no" and a failed guardrail count toward the two-in-a-row stop. `optimize` has no `--tasks` option, because a run needs at least one success in both splits.

## Left open

No new `TODO(VERIFY)` items. Nothing had run against the live model. The LiteLLM key had not arrived.
