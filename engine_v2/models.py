from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CoverageStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class ReconciliationStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class TransactionDirection(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class TransactionRecord(BaseModel):
    transaction_id: str
    statement_id: str
    source_file: str
    page: Optional[int] = None
    transaction_date: date
    description: str
    amount: Decimal = Field(gt=0)
    direction: TransactionDirection
    running_balance: Optional[Decimal] = None
    raw_text: Optional[str] = None


class StatementCoverage(BaseModel):
    statement_id: str
    period_start: date
    period_end: date
    expected_days: int = Field(gt=0)
    observed_days: int = Field(ge=0)
    coverage_pct: float = Field(ge=0, le=100)
    status: CoverageStatus
    warning: Optional[str] = None


class ReconciliationResult(BaseModel):
    statement_id: str
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    total_credits: Decimal = Decimal("0")
    total_debits: Decimal = Decimal("0")
    calculated_closing_balance: Optional[Decimal] = None
    variance: Optional[Decimal] = None
    tolerance: Decimal = Decimal("2.00")
    status: ReconciliationStatus
    warning: Optional[str] = None


class AuditEvent(BaseModel):
    event_id: str
    occurred_at: datetime
    event_type: str
    entity_type: str
    entity_id: str
    actor: str = "system"
    payload: dict = Field(default_factory=dict)
