Written 2026-10-12 from the chat history and git log, after the stage was built.

## What Stage 1 had to deliver

`docs/SPEC.md` asks for the pure domain layer in section 5.1, fully unit tested, with no I/O. That is company and task models, Decimal cost math, ICP labels, scoring, run summaries, guardrails, and one-lever proposals. `breakdown()` returns zero infrastructure cost when billed time or memory is missing. Guardrails check evaluation success, held-out success, and p95. `validate_proposal` rejects an unavailable lever, an out-of-bounds value, or a no-op. `apply_proposal` returns a new config with the version increased by one and exactly one lever changed. Acceptance is `make check` green and domain coverage at least 95%.

No AskQuestion was recorded for this stage. The human said to move to the next phase, then to open the pull request for the stage.

## How it was built

Cursor raised the domain coverage gate in the Makefile from 90 to 95, then wrote the domain modules and table-driven tests, and stopped. Commit `0492160`, `feat(domain): models, cost math, scoring, guardrails, proposals`, changes 24 files. The modules are `errors.py`, `company.py`, `task.py`, `config.py`, `cost.py`, `frozen.py`, `icp.py`, `scoring.py`, `guardrails.py`, `analysis.py`, and `proposals.py`, with tests under `tests/unit/domain/`.

`make check` passed. pytest: 126 passed. Hypothesis checks that infrastructure cost does not fall as billed time or memory rises, and that summary cost components add up to the total. Guardrails pass when a candidate sits exactly on the limit. Coverage: domain 100% (the gate is now 95%). Services 100% with no statements yet. Overall 100%. No new packages. No `TODO(VERIFY)` items.

The stage report locked in these readings so later stages stay consistent. `success_rate` is a fraction from 0 to 1, and `max_success_drop_pp` is percentage points, so a 2 point drop means 0.02. Missing and near-threshold checks use employee count, funding stage, and engineering open roles. A clear miss is easy. A missing or borderline value is hard. Latency percentiles use nearest rank. Token averages are the mean, over tasks, of the sum of that task's calls. Routing counts use the first call's tier. JSON values are not coerced.

Mypy uses the Pydantic plugin that already ships with Pydantic, so frozen models typecheck under strict mode. In tests only, the magic-number lint is off. Production code still has that rule.

The human then asked for the pull request. Cursor created `feat/domain-models` from the scaffold branch, committed only the domain files and the Makefile and `pyproject.toml` coverage change, pushed with `git push -u origin HEAD`, and ran `gh pr create --base chore/scaffold-quality-gates --head feat/domain-models`. That opened PR #2: https://github.com/ashihams/Vamonos-AI/pull/2. The PR body records 126 tests and 100 percent domain coverage. PR #3 is the same head opened against `main`: https://github.com/ashihams/Vamonos-AI/pull/3. Later messages call #2 and #3 duplicates and say to close one of them. Git log on this branch, above the scaffold commits, is only `0492160`.

## What did not work

The first `gh pr create` for PR #2 timed out after the branch was already on GitHub. The same command was run again and opened the pull request.

## Left open

Nothing in `docs/open-verifications.md`. Stage 2 had not been started when the stage report was written. The report's suggested commit message is the message on `0492160`.

The stage report also listed doubts that were not AskQuestion choices. Infrastructure cost is 0 when billed time or memory is missing, which is what the spec says for `breakdown()`. The human was asked to approve the stage before Stage 2. The next human message was the request to create this pull request, not a change to those readings.

`gh pr view` for #2 shows one commit, `0492160`, based on `chore/scaffold-quality-gates`. `gh pr view` for #3 shows three commits, because its base is `main`: the scaffold commit, the unrelated-histories merge, and `0492160`. Both pull requests were still open when this note was written.
