"""JSON logging and credential redaction."""

import json
import logging

import pytest

from costwise.logging_setup import configure_logging, redact_text


def test_redact_text_covers_bearer_labels_and_sk_keys() -> None:
    """Bearer tokens, labeled secrets, and sk- keys are replaced."""
    raw = "Authorization: Bearer super-token api_key=abcd1234 sk-live-abc123 done"
    redacted = redact_text(raw)
    assert "super-token" not in redacted
    assert "abcd1234" not in redacted
    assert "sk-live-abc123" not in redacted
    assert "[REDACTED]" in redacted
    assert redact_text("task finished") == "task finished"


def test_configure_logging_emits_one_redacted_json_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Configuring twice still writes one JSON line, with the secret removed."""
    configure_logging()
    configure_logging()
    secret = "sk-" + "live-abc123"
    logging.getLogger("costwise").info("token=%s", secret)
    lines = [line for line in capsys.readouterr().err.splitlines() if line.startswith("{")]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload == {
        "level": "INFO",
        "logger": "costwise",
        "message": "token=[REDACTED]",
    }
    assert secret not in lines[0]
