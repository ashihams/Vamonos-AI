Written 2026-10-12 from the chat history and git log, after the stage was built.

## What Stage 11 had to deliver

`docs/SPEC.md` asks for `costwise report --run-id ID` to write `report.md`, `trajectory.csv`, `cfo_inputs.json`, and `trajectory.mmd` under `runs/<id>/report/`. Every cost line says whether it is measured or modeled. Held-out success is labeled on its own. Selling price and monthly volume stay empty for the human to fill in cfo.ai. No STOP AND ASK. The human had already said to build this stage after Stage 10.

## How it was built

No report had been produced from a live run. The outputs come from fixed test data. The report compares the baseline with the last accepted version. Model cost is measured tokens times configured prices. Infra cost is measured from Lambda REPORT lines or modeled from local wall time. Data cost is modeled from fixture credits. `cfo_inputs.json` carries the two unit costs, the split, task counts, and sources. `price_per_task_usd` and `monthly_volume_scenarios` are left empty and marked as assumptions. `trajectory.mmd` is a Mermaid `xychart-beta` text, not a rendered chart.

The services were split to stay under 250 lines: `report.py`, `report_data.py`, `report_format.py`, `report_render.py`, and `report_exports.py`. A port `ports/report.py` and adapter `adapters/storage/report_files.py` write the files. `apps/cli/commands_report.py` is wired in `bootstrap.py`. `build(run_id)` matches the spec. A separate `collect()` returns the numbers without writing files. The CSV has more columns than the spec lists: the cost split, success rate per split, and infra source. `report.md` points at the CSV for the per-version table instead of repeating it. `.gitattributes` keeps the golden files in Unix line endings.

Commit `1b4bcd9` on `feat/report`, 28 files, stacked on `feat/lambda`. Golden-file tests pin all four files for a fixed run (one change kept, one rolled back, one declined). One test checks that every line showing a dollar figure has a source tag. Another checks that held-out numbers are labeled. Edge cases cover no successes, an empty version, mixed measured and modeled infra, and file-name safety. The end-to-end CLI test now runs `report` after `optimize` against a mocked model endpoint.

`make check` exited 0. pytest: 341 passed. Overall coverage 99.88%. Domain and services 100%. The chat records an earlier pass of the same 341 and 99.88% before the end-to-end report step was added, then the same totals after it.

After Stages 10 and 11 were committed locally, Cursor asked whether to push both branches and open stacked pull requests and then build Stage 12, to open the pull requests and stop, to build Stage 12 while keeping everything local, or to stop. PR #12 was opened against `feat/lambda`: https://github.com/ashihams/Vamonos-AI/pull/12

## What did not work

Nothing in the chat is recorded as a red `make check` for this stage. The report had only been produced from test data.

## Left open

No new verification items. The human still had to use `cfo_inputs.json` in cfo.ai. That had not been done.
