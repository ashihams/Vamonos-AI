Written 2026-10-12 from the chat history and git log, after the stage was built.

## What Stage 12 had to deliver

`docs/SPEC.md` asks for the README, `docs/architecture.md`, a status pass on `docs/open-verifications.md`, `scripts/dry_run.py`, a `make check` sweep, a secrets scan, and a `v0.1.0` tag. This branch also holds the live runs and the two fixes those runs forced. No new AskQuestion is in the stage itself until the tag.

## How Stage 12 was built

Commit `fcf92b4` rewrote the README (what costwise is, the metric, a Mermaid architecture diagram, quickstart, the demo commands, and limitations), added `docs/architecture.md`, opened `docs/open-verifications.md` with a status table, added `scripts/dry_run.py`, and removed the unused all-in-one `Settings` class. Its tests now cover `EvalSettings`. At that point nine verification items were still open and only the Crustdata endpoint check was done.

`make check` exited 0. pytest: 343 passed. Overall coverage 99.88%. Domain and services 100%. A fresh clone of the commit passed `make install && make check` with no `.env` and no raw fixtures. In that clone, `costwise --help` listed every command, and `scripts/dry_run.py` without keys exited 2 naming the missing settings. A history scan printed counts only: no API-key, AWS-key, private-key, or bearer-token patterns. Two `LITELLM_LICENSE=` lines in tests are placeholders (`unrelated`, `unrelated-value`). No `.env`, raw fixture, or sample file was committed.

A combined amend-and-tag command was blocked by auto-review. The build log went out as its own commit, `0a642f9`. The sandbox also blocked deleting `%TEMP%\costwise-fresh`. `estimate_tokens` is required by the spec and nothing calls it. It was left in.

`hackathon.md` says the branch was tagged `v0.1.0` locally. `git tag` lists no tags. The later chat says the tag was not created: the human chose to tag `v0.1.0` on `main` after the pull requests merge. PR #13 is open against `feat/report`: https://github.com/ashihams/Vamonos-AI/pull/13

## Live runs and fixes

The human later gave the LiteLLM key. It lives in the gitignored `.env`. The proxy's model list and model info calls returned 200. The human chose `claude-haiku` as cheap and `claude-sonnet-4.6` as strong. `config/pricing.yaml` uses the proxy's rates: 1.10 / 5.50 and 3.30 / 16.50 USD per 1M input / output tokens, 10% above the list prices the chat cites. The human chose to keep the Crustdata price per credit at `0.00`, because the hackathon credits were free, and to say so in the report. `make check` exited 0. pytest: 343 passed. Auto-review blocked one lookup that used the new key. The chat said it would resend that command for approval. The result of the resend is not recorded in the notes sources used here. The 200s above are from `hackathon.md`.

`scripts/dry_run.py --iterations 1`: 5 of 5 tasks succeeded on `claude-sonnet-4.6`, 25,748 to 50,579 input tokens each. Model cost 0.607 USD, about 0.121 per task. Infra 0.0003 USD, modeled. Data 0. The projected cost of 80 tasks was 9.71 USD, more than half of the 9.39 USD left under `MODEL_BUDGET_USD=10`, so the dry run refused (exit 1).

The human then chose 28 requests (23 evaluation, 5 held-out) and `MODEL_BUDGET_USD=15`. Contract tests pin their own 40-request workload. `make check` exited 0 (343 passed). A second dry run (`--iterations 1 --run-id dry-run-2`) was 5 of 5 and 0.608 USD. The projected cost of 56 tasks was 6.80 USD, within half of the 14.39 left. It passed.

`eval baseline --run-id demo`: 28 tasks, all on `claude-sonnet-4.6` with the full payload. Success 27. Evaluation 22 of 23 (95.7%). Held-out 5 of 5 (100%). `task-0010` returned an invalid answer on the first try and on the retry (`ParseError`). Model 2.887 USD, infra 0.0015 USD modeled, data 0. Total 2.888 USD, about 0.107 USD per successful task. Input tokens 7,495 to 50,579. Output never exceeded 281. Spent on the shared key, by costwise's accounting: about 4.10 USD.

The human chose `optimize --run-id demo --iterations 1 --auto-approve`. The model proposer suggested routing to `claude-haiku` by default, escalating to Sonnet when 2 or more fields are missing or the company is near a threshold. It predicted a 35% saving, at medium risk. Version 2 ran 27 of 28 tasks on Haiku. Model cost fell from 2.887 to 1.023 USD, and cost per successful task from 0.107 to 0.054 USD. Evaluation success fell to 17 of 23 (73.9%, floor 93.7%) and held-out to 2 of 5 (40%, floor 98%). Both success guardrails failed, so the change was rolled back and v1 stayed accepted. The p95 check passed (5,662 ms against a 6,139 ms limit). `costwise report --run-id demo` wrote `runs/demo/report/`. The report now says that zero data cost means the hackathon credits were free. `make check` passed (344 tests). Spent: about 5.1 USD, plus one proposer call.

The human chose a second run, `optimize --run-id demo-2 --iterations 2 --auto-approve`. Baseline v1: 27 of 28 tasks, 2.886 USD model cost, 0.107 USD per successful task. Iteration 1 suggested Haiku routing again (45% predicted). Rejections were remembered only within a run, so this repeated the change rejected in `demo`. Evaluation 73.9%, held-out 40%, rolled back, 1.02 USD. Iteration 2 turned on the company-data cache (20% predicted). Guardrails passed (evaluation 95.7%, held-out 100%, p95 5,771 against 7,045 ms), so v3 was kept. The kept cache saved nothing: 0.106967 to 0.106976 USD per successful task. The cache only avoids Crustdata credits priced at 0.00, and it does not shrink what is sent to the model. The loop kept any change that passed the guardrails. Spent: about 11.9 USD by costwise's accounting. About 8 USD was left. Evidence is in `evidence/demo-2026-10-12/` and `evidence/demo-2-2026-10-12/`. Those commits are `77cbba0` and `f0cb4f5`.

The human then chose both free fixes. A change is kept only if the guardrails pass and cost per successful task drops by at least `min_saving_pct`, set to 1% in `config/policy.yaml`. Rejected proposals are remembered across runs that share the same version-1 config. An exact repeat is dropped. A near-duplicate is only discouraged in the prompt. `make check` exited 0. pytest: 353 passed. The chat also records 99.89% coverage for that run. Commit `b6be1b8`. No paid calls were made for the fix.

The neatlogs key was then put in `.env`. `scripts/smoke_neatlogs.py` sent one fake task trace and one fake iteration trace as session `smoke-1791796161019`, with no exporter errors. The human's dashboard check: both traces arrived at 2:39 PM IST. The iteration trace shows `optimizer_iteration`, with `guardrail eval_success` and a failed `guardrail heldout_success` (ERROR), ending with "smoke failure". neatlogs flags that trace "Execution Failed". The task trace had not been opened yet. The human chose no more paid model runs. Commit `72a613b` records that smoke check. This branch is one commit ahead of `origin/feat/release` at that commit.

## Left open

The task-trace dashboard check, filterable attributes, the Lambda deploy, the `v0.1.0` tag, cfo.ai, the business plan, and the demo were still open. A model that always answers "not a fit" would still score about 79% on the labeled set.
