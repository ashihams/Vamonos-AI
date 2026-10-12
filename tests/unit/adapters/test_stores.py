"""JSONL run store and JSON config store."""

from decimal import Decimal
from pathlib import Path

import pytest

from costwise.adapters.storage.file_config_store import FileConfigStore
from costwise.adapters.storage.jsonl_run_store import JsonlRunStore
from costwise.domain.config import Lever, OptimizerConfig
from costwise.domain.errors import CostwiseError
from costwise.domain.guardrails import CheckOutcome, GuardrailResult
from costwise.domain.proposals import ApprovalDecision, IterationRecord, Proposal
from tests.unit.domain.builders import ResultSpec, make_config, make_result, make_summary


def _iteration() -> IterationRecord:
    """Build one iteration whose summary contains a decimal cost."""
    return IterationRecord(
        iteration=1,
        proposal=Proposal(
            lever=Lever.CACHE,
            new_value=True,
            rationale="enable cache",
            predicted_cost_change_pct=-10.0,
            risk="low",
        ),
        decision=ApprovalDecision(approved=True, note="ok"),
        baseline_version=1,
        candidate_version=2,
        candidate_summary=make_summary(1.0, 10),
        guardrails=GuardrailResult(
            passed=True,
            checks=(CheckOutcome(name="eval_success", passed=True, detail="ok"),),
        ),
        accepted=True,
        reason="kept",
    )


def test_results_and_iterations_round_trip(tmp_path: Path) -> None:
    """Decimals, an empty result file, and append order survive the JSONL store."""
    store = JsonlRunStore(tmp_path)
    result = make_result(ResultSpec(model_usd=Decimal("0.10")))
    store.save_results("run-1", 1, [result])
    loaded = store.load_results("run-1", 1)
    assert loaded[0].costs.model_usd == Decimal("0.10")
    assert loaded[0] == result
    written = (tmp_path / "run-1" / "results_v1.jsonl").read_text(encoding="utf-8")
    assert '"0.10"' in written
    (tmp_path / "run-1" / "results_v1.jsonl").write_text(written + "\n", encoding="utf-8")
    assert store.load_results("run-1", 1) == [result]

    store.save_results("run-1", 2, [])
    assert store.load_results("run-1", 2) == []
    assert store.load_iterations("run-1") == []
    first = _iteration()
    second = first.model_copy(update={"iteration": 2})
    store.save_iteration("run-1", first)
    store.save_iteration("run-1", second)
    assert store.load_iterations("run-1") == [first, second]


def test_config_round_trip_keeps_payload_fields(tmp_path: Path) -> None:
    """A config with payload fields reloads as the same model."""
    store = FileConfigStore(tmp_path)
    config = OptimizerConfig.model_validate(
        {**make_config().model_dump(), "payload_fields": ["domain"]}
    )
    store.save("run-1", config)
    assert store.load("run-1", 1) == config
    assert (tmp_path / "run-1" / "config_v1.json").is_file()


def test_stores_reject_bad_paths_and_files(tmp_path: Path) -> None:
    """Traversal, a negative version, a missing file, and bad JSON are errors."""
    runs = JsonlRunStore(tmp_path)
    configs = FileConfigStore(tmp_path)
    with pytest.raises(CostwiseError, match="invalid run id"):
        runs.save_results("../escape", 1, [])
    with pytest.raises(CostwiseError, match="invalid config version"):
        configs.load("run-1", -1)
    with pytest.raises(CostwiseError, match="missing store file"):
        runs.load_results("run-1", 1)
    with pytest.raises(CostwiseError, match="missing store file"):
        configs.load("run-1", 1)

    path = tmp_path / "run-1" / "results_v3.jsonl"
    path.parent.mkdir()
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(CostwiseError, match="invalid store file"):
        runs.load_results("run-1", 3)
    config_path = tmp_path / "run-1" / "config_v4.json"
    config_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(CostwiseError, match="invalid store file"):
        configs.load("run-1", 4)
    iteration_path = tmp_path / "run-1" / "iterations.jsonl"
    iteration_path.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(CostwiseError, match="invalid store file"):
        runs.load_iterations("run-1")
