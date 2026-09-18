from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class StatementPeriodDetection(BaseModel):
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    confidence: float = Field(ge=0, le=1)
    method: str
    warning: Optional[str] = None


_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%d/%m/%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
)


def _parse_date(value: str) -> date | None:
    cleaned = re.sub(r"\s+", " ", value.strip())
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def extract_statement_period(text: str) -> StatementPeriodDetection:
    """Extract only explicit statement date ranges.

    The function intentionally returns UNKNOWN rather than inferring a period
    from transaction activity, because inactive days are still valid statement
    coverage and should not make a complete statement appear partial.
    """
    normalized = re.sub(r"[\t\r]+", " ", str(text or ""))
    normalized = re.sub(r" +", " ", normalized)

    date_token = (
        r"(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|"
        r"\d{1,2}[-/]\d{1,2}[-/]\d{4}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
        r"(?:uary|ruary|ch|il|e|y|ust|ember|ober|ember|ember)?\s+\d{1,2},\s+\d{4}|"
        r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
        r"(?:uary|ruary|ch|il|e|y|ust|ember|ober|ember|ember)?\s+\d{4})"
    )

    patterns = (
        rf"(?:statement\s+period|statement\s+dates?|period)\s*[:\-]?\s*({date_token})\s*(?:to|through|thru|\-|–|—)\s*({date_token})",
        rf"(?:from)\s+({date_token})\s+(?:to|through|thru)\s+({date_token})",
        rf"(?:beginning\s+date)\s*[:\-]?\s*({date_token})[\s\S]{{0,120}}?(?:ending\s+date)\s*[:\-]?\s*({date_token})",
    )

    for idx, pattern in enumerate(patterns):
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        start = _parse_date(match.group(1))
        end = _parse_date(match.group(2))
        if start and end and start <= end:
            return StatementPeriodDetection(
                period_start=start,
                period_end=end,
                confidence=0.95 if idx == 0 else 0.90,
                method="explicit_statement_period",
            )

    return StatementPeriodDetection(
        confidence=0.0,
        method="not_detected",
        warning=(
            "No explicit statement period was detected. Processing may continue, "
            "but month-completeness must remain unknown rather than being inferred "
            "from transaction activity."
        ),
    )
