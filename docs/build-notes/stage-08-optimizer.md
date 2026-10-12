Written 2026-10-12 from the chat history and git log, after the stage was built.

## What Stage 8 had to deliver

`docs/SPEC.md` asks for one valid proposal per step: a deterministic heuristic, then an LLM proposer that falls back to it, always re-validated. The optimizer sees the evaluation-split summary only, never held-out results. No STOP AND ASK. The human later said to open the pull request and move to the next phase.

## How it was built

No model was called. The model proposer is tested against a scripted fake. The run summary gained `repeat_rate`, the share of tasks whose domain appeared earlier in the run. That is the evidence for the cache rule. `ICP_FIELDS` lists the three fields the ICP rule reads. `strip_code_fence` became a shared helper.

`HeuristicProposer` tries five rules in a fixed order and skips levers the runner lacks and changes already rejected. It turns the cache on when domains repeat. It sends easy tasks to the cheap model when more than 10% of them used the strong one. It trims the payload to the three ICP fields when inputs average over 2,000 tokens. It steps the output cap down when answers use under half of it. It steps Lambda memory down one size. Otherwise it returns nothing. Predicted savings are upper bounds from the summary, for example the data cost times the repeat rate. Lowering the output cap predicts no saving, because tokens are billed as used.

`LLMProposer` asks the strong model at temperature 0 for one JSON proposal. The prompt includes the lever bounds, the config, the evaluation-split summary, and past rejections. An invalid reply gets one repair attempt with the reason. A second failure or a model error returns nothing. A budget stop is not swallowed. Prompt version `propose-v1` is logged. `OptimizerService` tries the model proposer, then the heuristic, and drops any proposal that is out of bounds, makes no change, or repeats a rejected one.

Commit `5ffe54a` on `feat/optimizer`, 12 files: `services/proposers.py`, `services/llm_proposer.py`, `services/optimizer.py`, plus changes to `domain/analysis.py`, `domain/icp.py`, and `services/parsing.py`. New tests: `test_proposers.py` (15), `test_llm_proposer.py` (11), `test_optimizer.py` (7).

`make check` exited 0. pytest: 271 passed. Overall coverage 99.79%. Domain and services 100%. The three new services and the changed domain modules are recorded at 100%.

PR #9 is open against `feat/telemetry`: https://github.com/ashihams/Vamonos-AI/pull/9

## What did not work

While testing, the routing rule proposed "no change" when routing was already cheap and the missing-fields threshold was already at its maximum. The optimizer dropped that and never reached the later rules. The rule now returns nothing in that case.

The spec says "average input above the median". With no median available, the chat used a fixed 2,000-token threshold. "Cache potential" was read as `repeat_rate`. The routing rule switches a strong default to cheap and keeps near-threshold companies on the strong model, because only raising the missing-fields threshold would change nothing while the default is strong. The dry-run projection still leaves out the optimizer's own model calls.

## Left open

No new `TODO(VERIFY)` items. The model proposer had not been tried against a live model. The LiteLLM key had not arrived.
