Written 2026-10-12 from the chat history and git log, after the stage was built.

## What Stage 0 had to deliver

`docs/SPEC.md` asks for an empty, green Python 3.12 project with every quality gate wired: the package skeleton, ruff, mypy strict, import-linter, pytest with the network disabled, coverage gates, the file-length and TODO scripts, a Makefile, pre-commit config, `.env.example`, `.gitignore`, the three Cursor rules, an empty `docs/open-verifications.md`, and one placeholder test. Acceptance is `make check` exiting 0, and one deliberate broken import that makes `make layers` fail, then reverted.

The human asked to build one stage at a time and to wait for approval after each stage.

## How it was built

Cursor wrote the scaffold in one pass and stopped. The files include `pyproject.toml`, `uv.lock`, the Makefile, `scripts/check_file_length.py`, `scripts/check_todos.py`, the empty `src/costwise` tree, `tests/unit/test_scaffold.py`, the three `.cursor/rules` files, and the two source documents copied in as `docs/SPEC.md` and `docs/stack-and-integration-plan.md`. Example `config/*.yaml` files were left for Stage 2, when the loaders exist.

GNU Make was not on the machine at the start. A winget search found ezwinports Make 4.4.1, already installed, and that is what `make check` used. The project is pinned to Python 3.12 because the default interpreter was 3.13.

`make check` exited 0. pytest: 1 passed (`tests/unit/test_scaffold.py` imports every scaffold package). Coverage: overall 100% (gate 80), domain 100% (gate 90), services 100% (gate 90). Those packages were docstring-only, so coverage saw 0 statements. No `TODO(VERIFY)` items.

This directory was not a git repo yet. The chat gave the PowerShell commands to init `chore/scaffold-quality-gates`, commit, add `origin`, and open the pull request. Git log on this branch:

- `75cbda4` Initial commit (remote `main`, `LICENSE` only)
- `9daf2c3` `chore: scaffold project with quality gates`
- `0c88b80` `Merge remote main into scaffold branch`

PR #1, "chore: scaffold project with quality gates", is open against `main`: https://github.com/ashihams/Vamonos-AI/pull/1

## What did not work

- import-linter 2.15 will not enforce the external I/O ban unless `include_external_packages = true`. That flag was set so the httpx, boto3, and yaml contract actually runs. Ruff's assert rule (`S101`) is ignored under `tests/` only. The stage report calls both adjustments, not weaker gates.
- A `costwise.domain` import of `costwise.services` made `make layers` fail with "domain is pure BROKEN". A bare `TODO` made `scripts/check_todos.py` fail. Both were reverted, as the spec asks.
- GitHub refused the first pull request: this branch and `main` had no commits in common, because the scaffold was created with `git init` and `main` held only `LICENSE`. `origin/main` was merged with `--allow-unrelated-histories`, then `gh pr create` opened PR #1.
- `entire enable` had not been run.

## Left open

No verification items. Stage 1 had not been started, and the human still had to approve Stage 0. The example config files were not created.
