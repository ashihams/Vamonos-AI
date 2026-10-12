Written 2026-10-12 from the chat history and git log, after the stage was built.

## What Stage 10 had to deliver

`docs/SPEC.md` asks for a Lambda runner, a thin handler, a REPORT-line parser, and `make lambda-build`, `lambda-deploy`, and `lambda-teardown`. It is a stretch stage and STOP AND ASK: confirm AWS credentials, the region, and the function name. The human said to build Stage 10 and then Stage 11, starting with Stage 10.

## Human decisions

`hackathon.md` records the builder's choices before building: region us-east-1, function `costwise-qualify`, and AWS credentials to be set up before deploying. The chat records that deploy was left for later because those credentials were not ready. No AWS command was run. The deploy creates one role (basic execution policy only) and one function, both tagged `project=costwise`, and the Makefile reminds you to tear down after the demo.

## How it was built

`LambdaRunner` invokes the function once per task with the log tail. It reads billed duration, memory size, and cold start from the REPORT line, and marks infrastructure cost as measured. It charges the local budget for every model call the function reports, so the runner takes the budget instead of a clock. A memory change updates the function and waits for the update to finish. The handler parses the event, builds the task once per container from bundled fixtures and the model endpoint, and returns the invocation as JSON. There is no telemetry export and no Crustdata key in Lambda. A failed invocation (function error or throttling) becomes one errored task instead of stopping the run. Cold starts are left out of latency percentiles. The LiteLLM key is copied into the function environment at deploy time. The zip bundles `fixtures/raw`, which the stage report says contains named people, into the builder's own function. Those names are not repeated here.

Commit `422cb48` on `feat/lambda`, 26 files. New code includes `lambda_runner.py`, `report_line.py`, `apps/lambda_handler/handler.py`, `bootstrap_lambda.py`, `infra/aws/deploy.py`, `infra/aws/teardown.py`, and `infra/aws/aws_common.py`. Tests use botocore's Stubber (invoke, function error, throttling, bad payloads, memory update and waiter) with fake credentials so no network call is made.

`make check` exited 0. pytest: 318 passed. Overall coverage 99.87%. Domain and services 100%. `make lambda-build` ran locally: a 14.9 MB zip with Linux x86_64 wheels. `hackathon.md` and `docs/open-verifications.md` also say the zip includes the `costwise` package, `config/icp.yaml`, and 40 raw fixture files.

The stage was committed locally first. PR #11 was opened later, against `feat/iteration`: https://github.com/ashihams/Vamonos-AI/pull/11

## What did not work

The log redaction filter treated the `sk-` inside `task-0001` as an API key and redacted task ids. The chat found this while tests were failing. The pattern now needs a word boundary before `sk-`. A logging handler left closed by an earlier test was also noted in that debugging pass. The stage report records the redaction fix.

## Left open

Deploying has not been done. The REPORT line format has not been checked against a real log. `docs/open-verifications.md` leaves both of those open.
