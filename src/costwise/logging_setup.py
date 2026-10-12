"""JSON-line logging to stderr with credential redaction."""

import json
import logging
import re
import sys

_HANDLER_NAME = "costwise-json"
_LOGGER_NAME = "costwise"
_BEARER_SECRET = re.compile(r"(?i)(bearer\s+)\S+")
_LABELED_SECRET = re.compile(r"(?i)((?:x-)?api[_-]?key|token|secret|authorization)(\s*[:=]\s*)\S+")
_SK_SECRET = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]+")


def redact_text(text: str) -> str:
    """Replace credential-shaped text with a redaction marker."""
    without_bearer = _BEARER_SECRET.sub(r"\1[REDACTED]", text)
    labeled = _LABELED_SECRET.sub(r"\1\2[REDACTED]", without_bearer)
    return _SK_SECRET.sub("[REDACTED]", labeled)


class RedactionFilter(logging.Filter):
    """Rewrite a log record's message when it looks like a credential."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the rendered message and keep the record."""
        redacted = redact_text(record.getMessage())
        record.msg = redacted
        record.args = ()
        record.message = redacted
        return True


class JsonLineFormatter(logging.Formatter):
    """Format one log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        """Return a JSON object with level, logger name, and message."""
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(level: int = logging.INFO) -> None:
    """Attach one redacting JSON handler to the costwise logger's stderr stream."""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    for handler in list(logger.handlers):
        if handler.name == _HANDLER_NAME:
            logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.name = _HANDLER_NAME
    handler.setFormatter(JsonLineFormatter())
    handler.addFilter(RedactionFilter())
    logger.addHandler(handler)
