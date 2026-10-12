"""Turn model text into a validated qualification answer."""

import re

from pydantic import ValidationError

from costwise.domain.errors import ParseError
from costwise.domain.task import QualificationAnswer

_FENCE = re.compile(r"^```[A-Za-z]*\s*\n?(.*?)\n?```$", re.DOTALL)


def strip_code_fence(text: str) -> str:
    """Return text trimmed, without one surrounding Markdown code fence if present."""
    body = text.strip()
    fenced = _FENCE.match(body)
    return fenced.group(1).strip() if fenced is not None else body


class ParsingService:
    """Parse JSON-only answers, tolerating one surrounding code fence."""

    def parse(self, text: str) -> QualificationAnswer:
        """Return the answer or raise ParseError for anything that is not exactly the schema."""
        try:
            return QualificationAnswer.model_validate_json(strip_code_fence(text), strict=True)
        except ValidationError as exc:
            raise ParseError(
                f"model answer is not a valid qualification: {exc.error_count()} errors"
            ) from exc
