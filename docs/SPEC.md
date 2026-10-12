# Cursor Build Spec: `costwise` (AI-Infra Cost Agent)

Give this file to Cursor as `docs/SPEC.md`. It is written to be executed **one stage at a time**.

---

## 0. How to use this with Cursor

1. A human does the prerequisites in section 0.1.
2. Paste the **master prompt** (0.2) once at the start of the Cursor chat.
3. For each stage, paste: `Implement Stage N from docs/SPEC.md exactly. Do not touch other stages. Stop when make check passes and give me the stage report.`
4. Review the stage report, run `make check` yourself, commit, then go to the next stage.

### 0.1 Human prerequisites (before Stage 0)
- [ ] Python 3.12 and `uv` installed
- [ ] Empty git repo created; `entire enable` run in it (Entire is a required hackathon tool)
- [ ] neatlogs project created; project API key ready
- [ ] LiteLLM key and base URL from the check-in email
- [ ] Crustdata account with promo code applied; API key ready
- [ ] AWS credentials configured locally (needed only for Stage 10)
- [ ] ~50 company domains chosen, saved as `domains.txt`

### 0.2 Master prompt (paste once)

```
You are building the project described in docs/SPEC.md. Follow it literally.

Rules you must obey at all times:
1. Work on ONE stage at a time. Never implement later stages early.
2. Never invent an external API endpoint, request field, or response field. If the spec marks
   something VERIFY or you do not know it, write TODO(VERIFY: <what>) in code, add it to
   docs/open-verifications.md, implement against the port with fakes, and ask me.
3. All I/O lives in adapters. Services and domain are pure and testable without network or disk.
4. Obey the layering contracts and quality gates in sections 2 and 3. `make check` must pass
   before you say a stage is done.
5. Money is Decimal. Time and randomness are injected. No globals, no singletons, no print().
6. When finished with a stage, output a stage report: files created, tests added, coverage,
   any TODO(VERIFY) items, anything you were unsure about.
```

---

## 1. What we are building (recap)

An **optimizer agent** that lowers the cost of a target AI app and proves quality did not drop.

- **Target app:** account qualification. Input: a company domain. Output: JSON `{icp_fit, reasons, headcount_band, stage}`. Company data comes from Crustdata (frozen into fixtures).
- **Metric:** `cost_per_successful_task = (model + infra + data cost) / successful tasks`.
- **Levers the agent can change (one per iteration):** model routing, payload trimming, output token cap, company-data cache, Lambda memory.
- **Loop:** baseline → analyze → propose → human approval → apply → re-run → guardrails → keep or roll back. Three iterations.
- **Evidence tools:** neatlogs (traces via OpenTelemetry), Entire (checkpoints from commits), cfo.ai (business plan from exported numbers).

Honesty rules baked into the code:
- Every cost carries a source tag: `measured` or `modeled`. The report prints which is which.
- Data cost is **modeled** (credits measured once per live call, cache hits decided by the driver).
- Held-out tasks are never shown to the optimizer.

---

## 2. Architecture and layering (non-negotiable)

Ports-and-adapters. Dependencies point inward only.

```
apps  →  bootstrap  →  services  ┐
                       adapters  ┘→  ports  →  domain
```

| Layer | Contains | May import | Must NOT import |
|---|---|---|---|
| `domain` | Pydantic models, enums, pure functions | stdlib, pydantic | everything else in the project |
| `ports` | `typing.Protocol` interfaces + their request/response models | `domain` | services, adapters, apps |
| `services` | Business logic, one responsibility each | `domain`, `ports` | adapters, apps, any I/O library |
| `adapters` | Implementations of ports (HTTP, boto3, OTel, files) | `domain`, `ports` | services, apps |
| `bootstrap` | Composition root: builds objects, injects dependencies | everything | apps |
| `apps` | Typer CLI, Lambda handler (thin: parse input, call a service, format output) | everything | n/a |

### 2.1 Repo layout

```
costwise/
  pyproject.toml  Makefile  .env.example  .gitignore  README.md
  .cursor/rules/            # section 4
  config/                   # pricing.yaml  icp.yaml  policy.yaml  (section 7)
  docs/                     # SPEC.md  open-verifications.md  architecture.md
  fixtures/                 # raw/*.json  labels.json  (generated in Stage 3)
  infra/
    collector/config.yaml  docker-compose.yaml
    aws/                    # deploy.py  teardown.py  (not part of the package)
  scripts/                  # check_file_length.py  check_todos.py  dry_run.py  smoke_neatlogs.py
  src/costwise/
    domain/                 # errors.py company.py task.py config.py cost.py icp.py
                            # scoring.py guardrails.py analysis.py proposals.py
    ports/                  # llm.py data.py runner.py telemetry.py storage.py approval.py clock.py
    services/               # payload.py routing.py prompt.py parsing.py task.py budget.py
                            # workload.py fixtures.py evaluation.py optimizer.py
                            # iteration.py report.py
    adapters/
      llm/                  # openai_compatible.py decorators.py
      data/                 # crustdata_client.py crustdata_mapper.py fixture_source.py
      runners/              # local_runner.py lambda_runner.py report_line.py
      telemetry/            # attributes.py otel_sink.py null_sink.py
      storage/              # jsonl_run_store.py file_config_store.py yaml_loaders.py
      approval/             # cli_approver.py auto_approver.py
    settings.py  logging_setup.py  bootstrap.py
    apps/
      cli/                  # main.py  commands_*.py
      lambda_handler/       # handler.py
  tests/
    unit/  contract/  integration/  testing_fakes/
```

### 2.2 Import-linter contracts (put in `pyproject.toml` in Stage 0)

```toml
[tool.importlinter]
root_package = "costwise"

[[tool.importlinter.contracts]]
name = "domain is pure"
type = "forbidden"
source_modules = ["costwise.domain"]
forbidden_modules = ["costwise.ports", "costwise.services", "costwise.adapters",
                     "costwise.bootstrap", "costwise.apps"]

[[tool.importlinter.contracts]]
name = "ports depend only on domain"
type = "forbidden"
source_modules = ["costwise.ports"]
forbidden_modules = ["costwise.services", "costwise.adapters", "costwise.bootstrap", "costwise.apps"]

[[tool.importlinter.contracts]]
name = "services do not touch adapters or apps"
type = "forbidden"
source_modules = ["costwise.services"]
forbidden_modules = ["costwise.adapters", "costwise.bootstrap", "costwise.apps"]

[[tool.importlinter.contracts]]
name = "adapters do not touch services or apps"
type = "forbidden"
source_modules = ["costwise.adapters"]
forbidden_modules = ["costwise.services", "costwise.bootstrap", "costwise.apps"]

[[tool.importlinter.contracts]]
name = "domain and services stay free of I/O libraries"
type = "forbidden"
source_modules = ["costwise.domain", "costwise.services"]
forbidden_modules = ["httpx", "boto3", "botocore", "opentelemetry", "yaml", "typer", "requests"]
```

---

## 3. Code quality gates (enforced by `make check`)

`make check` runs all of these and must exit 0. Cursor may not weaken any threshold.

| Gate | Tool | Threshold |
|---|---|---|
| Format | `ruff format --check` | no diffs |
| Lint | `ruff check` | zero findings; rule sets `E,F,I,B,UP,C90,PLR,SIM,RUF,ANN,S,T20,D1` |
| Complexity | ruff `C901` | max cyclomatic complexity **8** |
| Function size | ruff `PLR0915` | max **40** statements |
| Arguments | ruff `PLR0913` | max **5** parameters (use a Pydantic model beyond that) |
| Types | `mypy --strict` plus `disallow_any_explicit` | zero errors; no `Any` in `domain`, `ports`, `services` |
| Layering | `lint-imports` | all contracts kept |
| File length | `scripts/check_file_length.py` | **250 lines max** per file in `src/` |
| TODO policy | `scripts/check_todos.py` | only `TODO(VERIFY: ...)` allowed; each must appear in `docs/open-verifications.md` |
| Tests | `pytest -q` with `pytest-socket` | all pass; **network disabled** in unit and integration tests |
| Coverage | `pytest --cov` | **≥ 90%** on `domain` and `services`, **≥ 80%** overall |

### 3.1 Coding constraints
1. **No monolith files.** One class or one cohesive set of pure functions per module.
2. **Constructor injection only.** No module-level state, no singletons, no service locators.
3. **Frozen models.** Domain models are `pydantic.BaseModel` with `frozen=True`, `extra="forbid"`.
4. **Money is `Decimal`.** Never `float`. Quantize at the boundary only.
5. **Inject time and randomness.** Use the `Clock` port and explicit `seed` arguments.
6. **No bare `except`**, no swallowed errors. Raise typed errors from `domain/errors.py`.
7. **No `print`.** Use `logging` through `logging_setup.py`. Never log secrets, prompts containing keys, or full API payloads at INFO.
8. **Secrets only via env** (`pydantic-settings`). Never in code, tests, fixtures, or logs.
9. **Public classes and functions have docstrings** (one line is fine) stating the contract.
10. **Every service has unit tests using fakes of its ports.** No mocking of the code under test.
11. **Tests are deterministic.** No sleeps, no real clock, no real network, fixed seeds.
12. **Small commits.** Conventional commits (`feat(services): ...`). Commit at least at every stage's mid-point and end. This feeds Entire checkpoints.
13. **No new dependency without stating why** in the stage report. Pin through `uv.lock`.

---

## 4. Cursor rule files (create these in Stage 0)

`.cursor/rules/00-architecture.mdc`
```
---
description: Layering and structure rules for costwise
alwaysApply: true
---
- Layers: domain <- ports <- (services | adapters) <- bootstrap <- apps. Dependencies point inward only.
- domain and services never import I/O libraries (httpx, boto3, opentelemetry, yaml, typer).
- Services receive collaborators through constructors typed as ports (Protocols). No globals.
- apps/* and lambda handler stay thin: parse input, call one service, format output.
- Each module has one responsibility and stays under 250 lines. Split rather than grow.
- New external behavior goes behind a port in src/costwise/ports first, then an adapter.
```

`.cursor/rules/01-quality.mdc`
```
---
description: Code quality gates for costwise
alwaysApply: true
---
- Run `make check` before declaring any task done. Never lower a threshold to make it pass.
- Python 3.12, full type hints, mypy strict, no Any in domain/ports/services.
- Money is Decimal. Models are frozen pydantic models with extra="forbid".
- Inject Clock and random seeds. No print(). No bare except. No mutable default args.
- Max function length 40 statements, complexity 8, 5 parameters.
- Unit tests use fakes from tests/testing_fakes. No network, no sleeps.
- Do not invent API details. Use TODO(VERIFY: ...) and record it in docs/open-verifications.md.
```

`.cursor/rules/02-stage-discipline.mdc`
```
---
description: Work one stage at a time
alwaysApply: true
---
- Read docs/SPEC.md. Implement only the stage the user names.
- At the end, output a stage report: files, tests, coverage, open VERIFY items, doubts.
- If a stage says STOP AND ASK, stop and ask the human before continuing.
```

---

## 5. Contracts (signatures Cursor must implement)

These are the shapes. Cursor fills bodies and may add private helpers. Field names are fixed so stages connect.

### 5.1 `domain`

```python
# domain/errors.py
class CostwiseError(Exception): ...
class ConfigError(CostwiseError): ...
class BudgetExceededError(CostwiseError): ...
class DataSourceError(CostwiseError): ...
class LLMError(CostwiseError): ...
class RunnerError(CostwiseError): ...
class ParseError(CostwiseError): ...

# domain/company.py
class CompanyRecord(BaseModel):          # normalized; adjust fields to real data in Stage 3, max 8 fields
    domain: str
    employee_count: int | None
    funding_stage: str | None
    total_funding_usd: int | None
    engineering_open_roles: int | None
    industry: str | None
    headcount_growth_pct_6m: float | None

# domain/task.py
class Difficulty(StrEnum):  EASY = "easy"; HARD = "hard"
class Split(StrEnum):       EVAL = "eval"; HELDOUT = "heldout"
class ModelTier(StrEnum):   CHEAP = "cheap"; STRONG = "strong"
class InfraCostSource(StrEnum): MEASURED = "measured"; MODELED = "modeled"

class QualificationRequest(BaseModel):   # frozen
    task_id: str; domain: str; split: Split; data_cache_hit: bool

class QualificationAnswer(BaseModel):    # frozen
    icp_fit: bool; reasons: tuple[str, ...]; headcount_band: str | None; stage: str | None

class CallRecord(BaseModel):             # one model call
    model: str; tier: ModelTier; input_tokens: int; output_tokens: int
    latency_ms: int; started_offset_ms: int

class InvocationResult(BaseModel):       # what a runner returns; serializable; Lambda returns this JSON
    task_id: str; answer: QualificationAnswer | None; calls: tuple[CallRecord, ...]
    data_credits: Decimal; total_latency_ms: int; error: str | None
    billed_ms: int | None; memory_mb: int | None; cold_start: bool

class TaskResult(BaseModel):             # InvocationResult + ground truth + costs
    request: QualificationRequest; config_version: int; difficulty: Difficulty
    invocation: InvocationResult; success: bool; costs: "CostBreakdown"
    infra_source: InfraCostSource; started_at_ns: int

# domain/config.py
class RoutingPolicy(BaseModel):
    default_tier: ModelTier
    strong_if_missing_fields_gte: int        # 0..5
    strong_if_near_threshold: bool

class OptimizerConfig(BaseModel):
    version: int; cheap_model: str; strong_model: str; routing: RoutingPolicy
    payload_fields: tuple[str, ...] | None   # None = send full payload
    max_output_tokens: int                   # 64..1024
    cache_company_data: bool
    lambda_memory_mb: int                    # one of 256, 512, 1024, 2048

class Lever(StrEnum):
    ROUTING = "routing"; PAYLOAD_FIELDS = "payload_fields"; MAX_OUTPUT_TOKENS = "max_output_tokens"
    CACHE = "cache_company_data"; LAMBDA_MEMORY = "lambda_memory_mb"

# domain/cost.py
class ModelPrice(BaseModel):  input_per_1m_usd: Decimal; output_per_1m_usd: Decimal
class PriceBook(BaseModel):
    models: dict[str, ModelPrice]; lambda_usd_per_gb_second: Decimal
    lambda_usd_per_request: Decimal; crustdata_usd_per_credit: Decimal
class CostBreakdown(BaseModel):  model_usd: Decimal; infra_usd: Decimal; data_usd: Decimal
    # property total_usd
def model_cost(calls, prices) -> Decimal
def infra_cost(billed_ms, memory_mb, prices) -> Decimal
def data_cost(credits, prices) -> Decimal
def breakdown(invocation, prices) -> CostBreakdown

# domain/icp.py
class IcpRule(BaseModel):  # loaded from config/icp.yaml
    min_employees: int; max_employees: int; allowed_stages: frozenset[str]
    min_engineering_open_roles: int; near_threshold_pct: float
def label_company(record: CompanyRecord, rule: IcpRule) -> bool
def classify_difficulty(record: CompanyRecord, rule: IcpRule) -> Difficulty
    # HARD if any rule field is None or any numeric value is within near_threshold_pct of a threshold
def missing_field_count(record: CompanyRecord, rule: IcpRule) -> int
def is_near_threshold(record: CompanyRecord, rule: IcpRule) -> bool

# domain/scoring.py
def is_success(answer: QualificationAnswer | None, expected_fit: bool) -> bool
    # success = answer parsed AND answer.icp_fit == expected_fit

# domain/analysis.py
class GroupStats(BaseModel): n: int; successes: int; cost_usd: Decimal
class RunSummary(BaseModel):
    n: int; success_rate: float; cost_per_successful_task: Decimal
    totals: CostBreakdown; by_difficulty: dict[str, GroupStats]; by_tier: dict[str, GroupStats]
    p50_latency_ms: int; p95_latency_ms: int; cache_hit_rate: float
    avg_input_tokens: float; avg_output_tokens: float
    easy_routed_strong: int; hard_routed_cheap_failed: int
def summarize(results: Sequence[TaskResult]) -> RunSummary

# domain/guardrails.py
class GuardrailPolicy(BaseModel):
    max_success_drop_pp: float; p95_multiplier: float; budget_stop_fraction: float
class CheckOutcome(BaseModel):  name: str; passed: bool; detail: str
class GuardrailResult(BaseModel):  passed: bool; checks: tuple[CheckOutcome, ...]
def evaluate_guardrails(baseline: RunSummary, candidate: RunSummary,
                        candidate_heldout: RunSummary, baseline_heldout: RunSummary,
                        policy: GuardrailPolicy) -> GuardrailResult

# domain/proposals.py
class Proposal(BaseModel):
    lever: Lever; new_value: JsonValue; rationale: str
    predicted_cost_change_pct: float; risk: Literal["low", "medium", "high"]
def validate_proposal(proposal, current: OptimizerConfig, available: frozenset[Lever]) -> None
    # raises ConfigError: lever unavailable, value out of bounds, or no actual change
def apply_proposal(current: OptimizerConfig, proposal: Proposal) -> OptimizerConfig  # version + 1

class ApprovalDecision(BaseModel): approved: bool; note: str
class IterationRecord(BaseModel):
    iteration: int; proposal: Proposal; decision: ApprovalDecision
    baseline_version: int; candidate_version: int | None
    candidate_summary: RunSummary | None; guardrails: GuardrailResult | None
    accepted: bool; reason: str
```

### 5.2 `ports`

```python
# ports/llm.py
class LLMRequest(BaseModel):  model: str; system: str; user: str; max_output_tokens: int; temperature: float = 0.0
class TokenUsage(BaseModel):  input_tokens: int; output_tokens: int
class LLMResponse(BaseModel): text: str; usage: TokenUsage; latency_ms: int; model: str
class LLMClient(Protocol):    def complete(self, request: LLMRequest) -> LLMResponse: ...

# ports/data.py
class CompanyFetch(BaseModel): record: CompanyRecord; raw: dict[str, JsonValue]; credits_used: Decimal
class CompanyDataSource(Protocol):  def fetch(self, domain: str) -> CompanyFetch: ...

# ports/runner.py
class RunnerCapabilities(BaseModel):
    levers: frozenset[Lever]; infra_source: InfraCostSource
class TaskRunner(Protocol):
    def capabilities(self) -> RunnerCapabilities: ...
    def apply_infra(self, config: OptimizerConfig) -> None: ...
    def run(self, request: QualificationRequest, config: OptimizerConfig) -> InvocationResult: ...

# ports/telemetry.py
class TelemetrySink(Protocol):
    def record_task(self, run_id: str, result: TaskResult) -> None: ...
    def record_iteration(self, run_id: str, record: IterationRecord) -> None: ...
    def record_summary(self, run_id: str, version: int, summary: RunSummary) -> None: ...
    def flush(self) -> None: ...

# ports/storage.py
class RunStore(Protocol):
    def save_results(self, run_id: str, version: int, results: Sequence[TaskResult]) -> None: ...
    def load_results(self, run_id: str, version: int) -> list[TaskResult]: ...
    def save_iteration(self, run_id: str, record: IterationRecord) -> None: ...
    def load_iterations(self, run_id: str) -> list[IterationRecord]: ...
class ConfigStore(Protocol):
    def save(self, run_id: str, config: OptimizerConfig) -> None: ...
    def load(self, run_id: str, version: int) -> OptimizerConfig: ...

# ports/approval.py
class Approver(Protocol):
    def review(self, proposal: Proposal, evidence: RunSummary) -> ApprovalDecision: ...

# ports/clock.py
class Clock(Protocol):  def now_ns(self) -> int: ...
```

---

## 6. Stages

Each stage lists: goal, files, behavior, tests, acceptance, commit. Timeboxes assume a one-day build; they are guidance.

### Stage 0: Scaffold and quality gates (≈1 h)

**Goal:** an empty, green project with every gate wired.

**Do:**
- Create `pyproject.toml` (Python 3.12, `uv`), package skeleton under `src/costwise` with empty `__init__.py` for every directory in 2.1.
- Dependencies: `pydantic>=2`, `pydantic-settings`, `typer`, `httpx`, `pyyaml`, `tenacity`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc`. Optional extra `aws`: `boto3`. Dev: `pytest`, `pytest-cov`, `pytest-socket`, `respx`, `hypothesis`, `ruff`, `mypy`, `import-linter`, `pre-commit`, `types-PyYAML`.
- Configure ruff, mypy, pytest (`--disable-socket` in `addopts`), coverage, and the import-linter contracts from 2.2.
- Write `scripts/check_file_length.py` (fails if any `src/**/*.py` exceeds 250 lines) and `scripts/check_todos.py` (fails on any `TODO` not written as `TODO(VERIFY: ...)`, or whose text is missing from `docs/open-verifications.md`).
- `Makefile` targets: `install`, `fmt`, `lint`, `types`, `layers`, `test`, `check` (runs all gates in order), `clean`.
- `.pre-commit-config.yaml` running ruff, mypy, lint-imports on commit.
- `.env.example` with: `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `CRUSTDATA_API_KEY`, `NEATLOGS_API_KEY`, `AWS_REGION`, `LAMBDA_FUNCTION_NAME`, `MODEL_BUDGET_USD`, `GRPC_DNS_RESOLVER`.
- `.gitignore` (venv, `.env`, `runs/`, `build/`, caches). Create the three `.cursor/rules` files from section 4. Create empty `docs/open-verifications.md`.
- One placeholder test so `pytest` collects something.

**Acceptance:** `make check` exits 0. A deliberately broken import (domain importing services) makes `make layers` fail (try it once, then revert).
**Commit:** `chore: scaffold project with quality gates`

### Stage 1: Domain models and pure logic (≈1.5 h)

**Goal:** everything in 5.1, fully unit tested, no I/O.

**Files:** `domain/errors.py company.py task.py config.py cost.py icp.py scoring.py guardrails.py analysis.py proposals.py`.

**Behavior details:**
- `breakdown()` returns `infra_usd = 0` when `billed_ms` or `memory_mb` is `None` (local runner computes its own modeled values before this; see Stage 6).
- `infra_cost = (billed_ms / 1000) * (memory_mb / 1024) * lambda_usd_per_gb_second + lambda_usd_per_request`, all `Decimal`.
- `summarize()`: `cost_per_successful_task = totals.total / successes`; if zero successes, raise `CostwiseError("no successful tasks")`. Percentiles use nearest-rank. `cache_hit_rate` is the share of results with `request.data_cache_hit`. `easy_routed_strong` counts EASY tasks whose first call tier is STRONG. `hard_routed_cheap_failed` counts HARD tasks routed CHEAP with `success == False`.
- `evaluate_guardrails` checks, each as a `CheckOutcome`: (1) eval success rate ≥ baseline − `max_success_drop_pp`; (2) held-out success rate ≥ baseline held-out − `max_success_drop_pp`; (3) candidate p95 ≤ baseline p95 × `p95_multiplier`.
- `validate_proposal` enforces: lever in `available`; `max_output_tokens` within 64..1024; `lambda_memory_mb` in {256, 512, 1024, 2048}; `routing.strong_if_missing_fields_gte` within 0..5; `payload_fields` only from the allowed field names in `CompanyRecord`; new value must differ from current.
- `apply_proposal` returns a new config with `version + 1` and exactly one lever changed.

**Tests:** table-driven tests for every function; `hypothesis` property tests for `infra_cost` (monotonic in billed_ms and memory) and `summarize` (cost components sum to total); boundary tests for guardrails (exactly at threshold passes).
**Acceptance:** `make check` green; coverage on `domain` ≥ 95%.
**Commit:** `feat(domain): models, cost math, scoring, guardrails, proposals`

### Stage 2: Ports, settings, config loaders, test fakes (≈1 h)

**Goal:** interfaces plus the plumbing every later stage needs.

**Files:** all `ports/*.py` from 5.2; `settings.py`; `logging_setup.py`; `adapters/storage/yaml_loaders.py`, `jsonl_run_store.py`, `file_config_store.py`; `tests/testing_fakes/` (`FakeLLMClient`, `FakeCompanySource`, `FakeRunner`, `RecordingTelemetrySink`, `FixedClock`, `ScriptedApprover`, `InMemoryRunStore`, `InMemoryConfigStore`).

**Behavior details:**
- `Settings` (pydantic-settings, env-driven) holds keys, base URLs, `model_budget_usd`, paths. Secrets typed `SecretStr`.
- `yaml_loaders.py` loads `config/pricing.yaml` → `PriceBook`, `config/icp.yaml` → `IcpRule`, `config/policy.yaml` → `GuardrailPolicy`, and the initial `OptimizerConfig`. Validation errors raise `ConfigError` with the file name and field.
- `JsonlRunStore` writes `runs/<run_id>/results_v<n>.jsonl` and `iterations.jsonl`; `FileConfigStore` writes `runs/<run_id>/config_v<n>.json`. Round trip must be lossless including `Decimal`.
- `logging_setup.py` configures JSON-line logging to stderr with a redaction filter for anything resembling a key.
- `FakeLLMClient` takes a scripted list or a callable and records requests.

**Tests:** round-trip store tests using `tmp_path`; settings tests with `monkeypatch.setenv`; redaction filter test.
**Acceptance:** `make check` green.
**Commit:** `feat(ports,adapters): ports, settings, loaders, run store, test fakes`

### Stage 3: Company data and fixtures (≈1.5 h) — STOP AND ASK

**Goal:** frozen, labeled company fixtures and a workload generator.

**STOP AND ASK the human for:** (a) one real Crustdata response for a known company (pasted JSON, key removed), (b) the ICP thresholds for `config/icp.yaml`. Do not guess the Crustdata endpoint or response shape.

**Files:** `adapters/data/crustdata_client.py`, `crustdata_mapper.py`, `fixture_source.py`; `services/fixtures.py`, `services/workload.py`; `config/icp.yaml`.

**Behavior details:**
- `CrustdataClient` implements `CompanyDataSource` with `httpx`. Base URL, auth header name, API version, and endpoint path come from `Settings`/constants marked `TODO(VERIFY: Crustdata endpoint, auth header, credits per call)`. Timeouts 10 s; retry 2 times on 5xx and timeouts with `tenacity`; map failures to `DataSourceError`.
- `crustdata_mapper.py` is a pure function `map_company(raw) -> CompanyRecord`, written against the sample JSON the human provides. Missing fields become `None`.
- `FixtureCompanySource` reads `fixtures/raw/<domain>.json` and returns the stored `credits_used` (a measured-once constant saved alongside).
- `FixtureService.build(domains, source, out_dir)` fetches each domain once, writes raw JSON plus `credits_used`. `FixtureService.label(out_dir, rule, heldout_count, seed)` writes `fixtures/labels.json`: per domain `{expected_fit, difficulty, split}`; held-out chosen by seeded shuffle, stratified so both splits contain EASY and HARD.
- `WorkloadService.build(labels, n_requests, repeat_ratio, seed)` returns a deterministic ordered tuple of `QualificationRequest` (with `data_cache_hit=False`), drawing repeats so about `repeat_ratio` of requests repeat an earlier domain.

**Tests:** mapper tested against the provided sample and a missing-field variant; label and difficulty determinism; workload determinism for fixed seed; stratification test; client contract test with `respx` using the sample payload.
**Acceptance:** `make check` green; `costwise fixtures build` and `costwise fixtures label` commands exist (CLI wiring in Stage 6; for now callable via a script in `scripts/`).
**Commit:** `feat(data): crustdata client, mapper, fixtures, labeling, workload`

### Stage 4: LLM client and decorators (≈1 h) — STOP AND ASK

**STOP AND ASK the human for:** exact model names for `cheap_model` and `strong_model`, and their per-1M-token prices, to fill `config/pricing.yaml`. Do not guess prices.

**Files:** `adapters/llm/openai_compatible.py`, `adapters/llm/decorators.py`; `services/budget.py`.

**Behavior details:**
- `OpenAICompatibleClient` calls `POST {base_url}/chat/completions` with `httpx` (no `litellm` package: it is heavy and unnecessary for Lambda). Reads `usage.prompt_tokens` and `usage.completion_tokens`. Measures latency with the injected `Clock`. Errors map to `LLMError`.
- Decorators (each wraps an `LLMClient`): `RetryingLLMClient` (max 2 retries, exponential backoff, only on 429/5xx/timeouts), `BudgetedLLMClient` (asks `BudgetService` before each call, records cost after).
- `BudgetService(cap_usd, stop_fraction, prices)`: `record(model, usage)`, `remaining()`, `assert_can_spend()` raising `BudgetExceededError` at `stop_fraction × cap`. Thread-safe with a lock.

**Tests:** `respx`-mocked contract tests (success, 429 then success, 500 exhaustion, malformed body); budget tests including concurrency (use threads and a small cap); decorator ordering test.
**Acceptance:** `make check` green.
**Commit:** `feat(llm): openai-compatible client, retry and budget decorators`

### Stage 5: Task pipeline services (≈1.5 h)

**Goal:** the target app's logic as small services.

**Files:** `services/payload.py`, `routing.py`, `prompt.py`, `parsing.py`, `task.py`.

**Behavior details:**
- `PayloadService.trim(raw, fields) -> dict`: `None` fields = full payload; otherwise keep only listed top-level normalized keys. Also `estimate_tokens(text) -> int` (chars/4, documented as an estimate used only for logging, not cost).
- `RoutingService.choose(record, policy, rule) -> ModelTier`: STRONG if `missing_field_count >= strong_if_missing_fields_gte` (when threshold > 0), or if `strong_if_near_threshold` and `is_near_threshold`; otherwise `policy.default_tier`.
- `PromptService.build(record_payload, rule) -> tuple[str, str]` returns `(system, user)`. System prompt states the ICP rule in plain text and demands JSON only with exactly the keys `icp_fit, reasons, headcount_band, stage`. Prompt text lives in one module-level constant per prompt, with a version string logged on every call.
- `ParsingService.parse(text) -> QualificationAnswer`: strips code fences, parses JSON, validates with the model, raises `ParseError` otherwise.
- `TaskService(data_source, llm, router, payloads, prompts, parser, clock)`: `run(request, config) -> InvocationResult`:
  1. fetch company (credits are `0` if `request.data_cache_hit`, else the fetched `credits_used`);
  2. choose tier and model; trim payload; build prompt;
  3. call the LLM; record a `CallRecord`;
  4. parse; on `ParseError`, retry **once** on the STRONG tier (this fallback is part of the app and shows up in traces); record both calls;
  5. return `InvocationResult` with `billed_ms=None`, `memory_mb=None`, `cold_start=False` (runners fill these) and `error` set on failure instead of raising.

**Tests:** unit tests per service; `TaskService` tests with `FakeCompanySource` and `FakeLLMClient` covering: normal path, cache hit zeroes credits, parse failure triggers one strong retry, LLM failure becomes `error`, routing by thresholds.
**Acceptance:** `make check` green; coverage on `services` ≥ 90%.
**Commit:** `feat(services): payload, routing, prompt, parsing, task pipeline`

### Stage 6: Local runner, evaluation, CLI baseline (≈1.5 h)

**Goal:** run a full baseline end to end locally, with costs, stored.

**Files:** `adapters/runners/local_runner.py`; `services/evaluation.py`; `bootstrap.py`; `apps/cli/main.py`, `commands_eval.py`, `commands_fixtures.py`.

**Behavior details:**
- `LocalRunner(task_service, clock)` implements `TaskRunner`. `capabilities()` returns levers `{ROUTING, PAYLOAD_FIELDS, MAX_OUTPUT_TOKENS, CACHE}` (no `LAMBDA_MEMORY`) and `InfraCostSource.MODELED`. `run()` measures wall time, fills `billed_ms = ceil(wall_ms)` and `memory_mb = config.lambda_memory_mb`. `apply_infra` is a no-op. Because wall time does not depend on memory locally, the report must print "infra cost modeled; memory lever not available locally".
- `EvaluationService(runner, prices, rule_labels, telemetry, store, budget, clock)`:
  `evaluate(run_id, config, requests, max_workers=4) -> list[TaskResult]`:
  - decides `data_cache_hit` deterministically when `config.cache_company_data`: first occurrence of a domain in the request order is a miss, later ones are hits; when the cache is off, all are misses;
  - runs requests with a thread pool, results returned in request order;
  - checks `budget.assert_can_spend()` before submitting each request; stops cleanly and returns partial results with a logged warning if the budget guard trips;
  - builds `TaskResult` (difficulty and expected fit from labels, `is_success`, `breakdown`, source tag);
  - sends each result to the telemetry sink; saves results to the store; returns them.
- `bootstrap.py` builds the object graph from `Settings`: `build_eval_stack(settings, runner_kind)`; this is the only place concrete adapters are chosen.
- CLI (Typer): `costwise fixtures build|label`, `costwise eval baseline --run-id ID --runner local --tasks N`, `costwise dry-run --tasks 5` (runs a small baseline and prints measured cost per task, projected cost of the full plan versus the remaining budget; refuses to continue if the projection exceeds 50% of the budget). Commands only parse arguments and call services.

**Tests:** evaluation tests with `FakeRunner` and fakes (ordering, cache-hit determinism, budget stop returns partial, telemetry called once per result); a CLI smoke test with Typer's `CliRunner` using fakes via bootstrap override.
**Acceptance:** `make check` green; `costwise dry-run --tasks 5` works against real fixtures and the real LLM key (human runs this).
**Commit:** `feat(eval): local runner, evaluation service, cli baseline and dry-run`

### Stage 7: Telemetry to neatlogs through OpenTelemetry (≈1.5 h) — STOP AND ASK

**STOP AND ASK the human to:** confirm the neatlogs key works, run `scripts/smoke_neatlogs.py`, and tell Cursor what the dashboard shows. Neatlogs engineers confirmed: OTLP over **gRPC** at `ingest.neatlogs.com:443` (TLS), header `x-api-key` (never `Authorization: Bearer`); custom attributes are only filterable if named `neatlogs.workflow.*`, `neatlogs.session.*` or `neatlogs.end_user.id`; spans must be ended and the provider flushed before exit.

**Files:** `adapters/telemetry/attributes.py`, `otel_sink.py`, `null_sink.py`; `infra/collector/config.yaml`, `docker-compose.yaml`; `scripts/smoke_neatlogs.py`.

**Behavior details:**
- `attributes.py` holds all attribute-name constants (no string literals elsewhere):
  `neatlogs.workflow.config_version`, `.task_category`, `.success`, `.cost_model_usd`, `.cost_infra_usd`, `.cost_data_usd`, `.task_id`, `.infra_source`, `neatlogs.session.run_id`, plus `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.operation.name`. Values sent as strings where filtering is needed (`"true"`/`"false"`), numbers otherwise.
- `OtelSink` implements `TelemetrySink`. **Spans are emitted driver-side** from returned data: one root span per task (explicit start time `started_at_ns`, end time start + `total_latency_ms`) and one child span per `CallRecord` (start offset from `started_offset_ms`). This avoids exporting from Lambda. Use a dedicated `TracerProvider` (never the global one) with `BatchSpanProcessor` and `OTLPSpanExporter(endpoint="ingest.neatlogs.com:443", headers=(("x-api-key", key),))`.
- `record_iteration` emits one span per iteration with attributes for lever, decision, accepted, reason; guardrail checks become child spans, each with a passed or failed status. TODO(VERIFY: whether neatlogs renders `neatlogs.guardrail.passed` on a plain OTLP span as Passed/Blocked).
- `record_summary` writes aggregate metrics (`cost_per_task_usd`, `success_rate`, `latency_p95_ms`) as OTel metrics to the local Collector only; never use task id as a metric label.
- `flush()` calls `force_flush()`; the CLI calls it at the end of every command.
- Collector config: OTLP receiver (gRPC and HTTP), `otlp/neatlogs` exporter to `ingest.neatlogs.com:443` with the `x-api-key` header from env, and a `file` exporter to `/data/telemetry.jsonl` for local analysis; metrics go to the file only.
- If export hangs with `DEADLINE_EXCEEDED`, document `GRPC_DNS_RESOLVER=native` in the README.
- `scripts/smoke_neatlogs.py` sends one fake task trace with all attributes so the human can inspect it in the dashboard and confirm: token fields show, `neatlogs.workflow.*` attributes are filterable, child spans nest correctly.

**Tests:** `OtelSink` tested with the in-memory span exporter from `opentelemetry-sdk` (assert span tree, timestamps, attribute names and values, no secrets in attributes); attribute-constants test that no other module hard-codes these strings (grep-style test); `NullSink` no-op test.
**Acceptance:** `make check` green; human confirms the smoke trace in neatlogs; open VERIFY items recorded.
**Commit:** `feat(telemetry): otel sink exporting to neatlogs, collector config`

### Stage 8: Analysis and optimizer proposals (≈1.5 h)

**Goal:** the agent's brain: read a summary, propose one valid change.

**Files:** `services/optimizer.py` (plus `services/proposers.py` if it exceeds 250 lines).

**Behavior details:**
- `HeuristicProposer.propose(config, summary, available, rejected) -> Proposal | None`, deterministic, first matching rule wins and skipping any lever/value already rejected:
  1. cache off and `cache_hit_rate` potential > 0 → enable cache;
  2. `easy_routed_strong / n` > 0.10 → raise `strong_if_missing_fields_gte` by 1;
  3. `avg_input_tokens` above the median of the current payload and `payload_fields is None` → set `payload_fields` to the fields used by the ICP rule;
  4. `avg_output_tokens` < 0.5 × `max_output_tokens` → lower the cap to the next tier down;
  5. `LAMBDA_MEMORY` available → step memory to the next lower size;
  6. otherwise `None`.
- `LLMProposer(llm, model)` asks the strong model for one proposal as strict JSON matching `Proposal`, given: current config, `RunSummary` JSON, available levers, bounds, and prior rejections. Temperature 0. Parses with `Proposal.model_validate_json`; on invalid or failed `validate_proposal`, one repair attempt, then returns `None`.
- `OptimizerService(llm_proposer, heuristic, ...)`: `next_proposal(config, summary, available, history) -> Proposal | None` tries the LLM proposer first, falls back to the heuristic, always runs `validate_proposal`, and never returns an invalid proposal. Prompts are versioned constants.
- The optimizer never receives held-out results; its input type is `RunSummary` from the EVAL split only.

**Tests:** heuristic rule-by-rule with crafted summaries; LLM proposer with `FakeLLMClient` returning valid, invalid, then repaired JSON; fallback path; rejected-history respected; invalid proposals never escape.
**Acceptance:** `make check` green.
**Commit:** `feat(optimizer): heuristic and llm proposers with validation`

### Stage 9: Iteration loop with human approval (≈1.5 h)

**Goal:** the full propose → approve → apply → re-run → verify → keep/rollback loop.

**Files:** `services/iteration.py`; `adapters/approval/cli_approver.py`, `auto_approver.py`; `apps/cli/commands_optimize.py`.

**Behavior details:**
- `IterationService(evaluation, optimizer, approver, runner, guardrail_policy, store, config_store, telemetry, budget)`:
  `run(run_id, iterations) -> list[IterationRecord]`:
  1. load the baseline (version 1 results for EVAL and HELDOUT splits; if missing, evaluate them first);
  2. loop up to `iterations`: summarize the **current accepted** EVAL results; ask the optimizer for a proposal; stop if `None`;
  3. ask the `Approver`; if rejected, record it and continue (counts toward a stop after two consecutive rejections);
  4. apply the proposal to get a candidate config; if `LAMBDA_MEMORY` changed, `runner.apply_infra(candidate)` then run 3 warm-up invocations excluded from results;
  5. evaluate the candidate on EVAL and HELDOUT;
  6. `evaluate_guardrails`; accepted only if all checks pass;
  7. on accept: candidate becomes current accepted; on reject: roll back (`runner.apply_infra(previous)` if infra changed);
  8. save the config version, results, and `IterationRecord`; emit telemetry.
- Stop conditions: iteration limit, no proposal, two consecutive rejections, `BudgetExceededError` (finish the report with what exists).
- `CliApprover` prints lever, rationale, predicted change, risk, and key evidence numbers, then reads `y/n` plus an optional note; `AutoApprover` approves everything and tags the note `auto-approved` (used in tests and dry runs; the demo uses the CLI approver).
- CLI: `costwise optimize --run-id ID --iterations 3 [--auto-approve]`.

**Tests:** integration test (no network) with `FakeRunner` whose cost responds predictably to config, `ScriptedApprover`, and in-memory stores: one accepted iteration, one rejected by guardrail (success drop) with rollback, stop on two rejections, budget stop, cache lever reducing data cost. Assert the final accepted config and the stored iteration records.
**Acceptance:** `make check` green; integration test proves the loop converges on the fake.
**Commit:** `feat(iteration): approval loop with guardrails and rollback`

### Stage 10: AWS Lambda runner (≈2 h) — STOP AND ASK; stretch stage (see cut line)

**STOP AND ASK the human to:** confirm AWS credentials and region (us-east-1), and that the function name is acceptable.

**Files:** `apps/lambda_handler/handler.py`; `adapters/runners/lambda_runner.py`, `report_line.py`; `infra/aws/deploy.py`, `teardown.py`; `Makefile` targets `lambda-build`, `lambda-deploy`, `lambda-teardown`.

**Behavior details:**
- `handler.py` stays thin: parse event (`request`, `config`), build the Lambda stack through a small `bootstrap_lambda()` (fixture source bundled in the zip, OpenAI-compatible client from env vars, **no telemetry export**), call `TaskService.run`, return `InvocationResult` JSON. No Crustdata key in Lambda.
- `report_line.py`: pure parser for the `REPORT` log line extracting `Duration`, `Billed Duration`, `Memory Size`, `Max Memory Used`, and optional `Init Duration` (cold start flag). Format example: `REPORT RequestId: <id> Duration: 123.45 ms Billed Duration: 124 ms Memory Size: 512 MB Max Memory Used: 100 MB`. Unit tests with warm and cold samples and a malformed line (raises `RunnerError`).
- `LambdaRunner(boto_client, function_name, clock)`: `run()` calls `invoke(..., LogType="Tail", Payload=...)`, decodes `LogResult` (base64), parses the REPORT line, merges `billed_ms`, `memory_mb`, `cold_start` into the returned `InvocationResult`. Handles function errors (`FunctionError` header) as `RunnerError`. `capabilities()` returns all levers and `InfraCostSource.MEASURED`. `apply_infra()` calls `update_function_configuration(MemorySize=...)` and waits with the `function_updated_v2` waiter.
- Warm-up: the iteration service runs 3 throwaway invocations after any memory change; cold-start results are flagged and excluded from latency percentiles (add `exclude_cold_start` to `summarize`, covered by tests).
- `infra/aws/deploy.py`: builds the zip with `uv pip install --target build --python-platform x86_64-manylinux2014 --only-binary :all:` for runtime Python 3.12, includes `src/costwise` and `fixtures/`, creates the execution role (basic execution policy only), creates or updates the function (timeout 60 s, initial memory from config, env vars from `.env`). `teardown.py` deletes the function and role. Tag every resource `project=costwise`.
- Never create EC2 instances, load balancers, or anything else. Print a reminder to run `make lambda-teardown` after recording the demo.

**Tests:** parser tests; `LambdaRunner` tested with `botocore.stub.Stubber` (invoke response, function error, memory update); handler test with fakes via `bootstrap_lambda` override.
**Acceptance:** `make check` green; human runs `make lambda-deploy` then a 3-task baseline with `--runner lambda` and sees `measured` infra costs.
**Commit:** `feat(aws): lambda runner, handler, deploy and teardown`

### Stage 11: Reporting and cfo.ai export (≈1 h)

**Goal:** the evidence pack.

**Files:** `services/report.py`; `apps/cli/commands_report.py`.

**Behavior details:**
- `ReportService.build(run_id) -> ReportBundle` from the stores. Outputs written to `runs/<run_id>/report/`:
  - `report.md`: baseline vs final cost per successful task, % change, component split (model / infra / data) with source tags, success rate (EVAL and HELDOUT reported separately), p95 latency, iteration table (lever, decision, accepted, reason), and a plain-language "what is measured vs modeled" section;
  - `trajectory.csv`: version, cost per successful task, success rate, p95;
  - `cfo_inputs.json`: baseline and optimized cost per successful task, component split, number of tasks, plus placeholder fields `price_per_task_usd`, `monthly_volume_scenarios` for the human to fill (marked as assumptions);
  - `trajectory.mmd`: a Mermaid `xychart-beta` text of cost per task across versions (raw code, not rendered).
- CLI: `costwise report --run-id ID`.

**Tests:** golden-file tests of `report.md`, CSV, and JSON from a fixed set of fake results; test that every cost line carries a source tag; test that held-out numbers are labeled.
**Acceptance:** `make check` green; human uses `cfo_inputs.json` to build the cfo.ai model.
**Commit:** `feat(report): evidence pack and cfo.ai inputs`

### Stage 12: Hardening, docs, demo readiness (≈1 h)

**Do:**
- `README.md`: what it is, the metric, the architecture diagram as raw Mermaid, quickstart, the exact command sequence for the demo, honest limitations (modeled data cost, small infra lever, frozen fixtures, rule-based labels).
- `docs/architecture.md`: layers, ports table, how to add a lever or a runner.
- `docs/open-verifications.md`: every remaining VERIFY item with its current status.
- `scripts/dry_run.py` wrapper for the 5-task budget check.
- Full `make check` sweep; remove dead code; confirm no secrets in git history (`git log -p | grep -i key` style check by the human).
- Tag `v0.1.0`.

**Acceptance:** fresh clone → `make install && make check` passes; README commands work.
**Commit:** `docs: readme, architecture, verifications; release v0.1.0`

---

## 7. Example config files (Cursor creates; human fills real values)

`config/pricing.yaml`
```yaml
models:
  "<cheap-model-name>":  { input_per_1m_usd: "0.00", output_per_1m_usd: "0.00" }   # fill from provider pricing
  "<strong-model-name>": { input_per_1m_usd: "0.00", output_per_1m_usd: "0.00" }   # fill from provider pricing
lambda_usd_per_gb_second: "0.0000166667"   # verify on the AWS Lambda pricing page
lambda_usd_per_request: "0.0000002"        # verify on the AWS Lambda pricing page
crustdata_usd_per_credit: "0.00"           # fill after checking Crustdata pricing
```

`config/icp.yaml`
```yaml
min_employees: 50
max_employees: 1000
allowed_stages: [seed, series_a, series_b, series_c]
min_engineering_open_roles: 1
near_threshold_pct: 10.0
```

`config/policy.yaml`
```yaml
guardrails:
  max_success_drop_pp: 2.0
  p95_multiplier: 1.25
  budget_stop_fraction: 0.8
initial_config:
  version: 1
  cheap_model: "<cheap-model-name>"
  strong_model: "<strong-model-name>"
  routing: { default_tier: strong, strong_if_missing_fields_gte: 0, strong_if_near_threshold: false }
  payload_fields: null
  max_output_tokens: 512
  cache_company_data: false
  lambda_memory_mb: 1024
workload:
  n_requests: 60
  repeat_ratio: 0.25
  heldout_count: 10
  seed: 42
```

The initial config is deliberately the **reasonable but unoptimized** default (strong model everywhere, full payload, no cache). Do not make it artificially wasteful.

---

## 8. Test strategy summary

- **Unit (most tests):** domain and services with fakes. No network (`pytest-socket`), no disk except `tmp_path`.
- **Contract:** adapters against recorded or `respx`/`Stubber` responses (Crustdata client, LLM client, Lambda runner, OTel sink with in-memory exporter).
- **Integration (no network):** the full evaluation and iteration loop with fake runner, fake LLM and in-memory stores.
- **Manual smoke (human):** `scripts/smoke_neatlogs.py`, `costwise dry-run --tasks 5`, Lambda 3-task baseline.
- **Property tests:** cost math monotonicity and summary invariants.

---

## 9. Human checkpoints and open verifications

| Stage | Human must provide or confirm |
|---|---|
| 3 | Sample Crustdata response; ICP thresholds; whether indexed Company endpoints are covered by promo credits and credits per call |
| 4 | Cheap and strong model names; per-token prices |
| 7 | neatlogs dashboard check of the smoke trace (token fields, filterable attributes, span nesting, guardrail rendering) |
| 10 | AWS credentials; confirm Lambda price per GB-second |
| any | Hackathon rules on pre-existing code and public repo format (ask in Discord) |

All of these are tracked in `docs/open-verifications.md` as `TODO(VERIFY: ...)`.

---

## 10. Cut line and time budget

Rough total: about 17 hours of stage timeboxes, so **not everything fits in the time left**. Build in this priority order and stop adding when the clock says so:

1. **Must have:** Stages 0, 1, 2, 3, 4, 5, 6, 7, 9, 11. This gives local baseline, neatlogs traces, the approval loop, and the cfo.ai inputs, with the model, routing, payload, and cache levers.
2. **Cut next:** Stage 8's `LLMProposer` (keep the heuristic proposer; the loop still works). Say so in the README.
3. **Stretch:** Stage 10 (Lambda). Without it, infra cost is modeled and the memory lever is unavailable. Say so plainly in the report; do not present modeled infra numbers as measured.
4. **Always last:** Stage 12 polish, but never skip the README's limitations section.

Never cut: the quality gates, the held-out split, the measured-versus-modeled tags, or the evidence for neatlogs, Entire, and cfo.ai.
