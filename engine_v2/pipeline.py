from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .ai_classifier import classify_unresolved_transactions
from .batch_ingestion import BatchIngestionResult, parse_statement_batch
from .classification import classify_by_rules
from .constants import REVIEW_REQUIRED
from .mca import McaPosition, aggregate_positions
from .metrics import DebtRatioMetrics, RevenueBaseline, calculate_debt_ratios, select_revenue_baseline
from .models import TransactionDirection
from .readiness import DecisionReadiness, assess_decision_readiness
from .statement_parser import ParsedStatement


@dataclass
class ClassifiedTransaction:
    transaction_id: str
    statement_id: str
    source_file: str
    source_page: int | None
    date: str
    description: str
    amount: float
    direction: str
    category: str
    classification_source: str
    classification_reason: str
    classification_model: str | None = None
    needs_review: bool = False

    @property
    def is_true_revenue(self) -> bool:
        return self.direction == "credit" and self.category.startswith("True Revenue")


@dataclass
class UnderwritingPipelineResult:
    statements: list[ParsedStatement] = field(default_factory=list)
    transactions: list[ClassifiedTransaction] = field(default_factory=list)
    mca_positions: list[McaPosition] = field(default_factory=list)
    monthly_true_revenue: dict[str, float] = field(default_factory=dict)
    revenue_baseline: RevenueBaseline | None = None
    debt_ratios: DebtRatioMetrics | None = None
    decision_readiness: DecisionReadiness | None = None
    skipped_duplicates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _coverage_status_by_month(statements: list[ParsedStatement]) -> dict[str, str]:
    statuses: dict[str, list[str]] = defaultdict(list)

    for statement in statements:
        month = None
        if (
            statement.period_start
            and statement.period_end
            and statement.period_start.year == statement.period_end.year
            and statement.period_start.month == statement.period_end.month
        ):
            month = statement.period_start.strftime("%Y-%m")
        elif statement.transactions:
            months = {
                txn.transaction_date.strftime("%Y-%m")
                for txn in statement.transactions
            }
            if len(months) == 1:
                month = next(iter(months))

        if month is None:
            continue

        if statement.coverage is None:
            statuses[month].append("UNKNOWN")
        else:
            statuses[month].append(statement.coverage.status.value)

    resolved: dict[str, str] = {}
    for month, month_statuses in statuses.items():
        if "PARTIAL" in month_statuses:
            resolved[month] = "PARTIAL"
        elif "UNKNOWN" in month_statuses:
            resolved[month] = "UNKNOWN"
        elif month_statuses and all(status == "COMPLETE" for status in month_statuses):
            resolved[month] = "COMPLETE"
        else:
            resolved[month] = "UNKNOWN"
    return resolved


def analyze_statement_files(
    *,
    files: list[tuple[str, bytes]],
    ai_client: Any | None = None,
    vision_client: Any | None = None,
    classifier_model: str = "gpt-5.6-terra",
    enable_ocr: bool = False,
    enable_vision_fallback: bool = False,
    vision_model: str = "gpt-5.6-terra",
) -> UnderwritingPipelineResult:
    batch: BatchIngestionResult = parse_statement_batch(
        files,
        enable_ocr=enable_ocr,
        vision_client=(
            vision_client
            if vision_client is not None
            else ai_client
        ),
        enable_vision_fallback=enable_vision_fallback,
        vision_model=vision_model,
    )

    result = UnderwritingPipelineResult(
        statements=batch.statements,
        skipped_duplicates=batch.skipped_duplicates,
    )

    unresolved_payload: list[dict] = []
    pending_by_id: dict[str, ClassifiedTransaction] = {}

    for statement in batch.statements:
        effective_integrity = statement.composite_integrity or statement.integrity
        if effective_integrity and effective_integrity.status != "LOW_CONCERN":
            result.warnings.append(
                f"{statement.source_file}: statement integrity review status "
                f"{effective_integrity.status} ({effective_integrity.score}/100)."
            )
        if statement.coverage and statement.coverage.warning:
            result.warnings.append(
                f"{statement.source_file}: {statement.coverage.warning}"
            )
        if statement.reconciliation_status in {"WARNING", "FAIL"}:
            result.warnings.append(
                f"{statement.source_file}: reconciliation status "
                f"{statement.reconciliation_status}"
                + (
                    f" (variance {statement.reconciliation_variance})"
                    if statement.reconciliation_variance is not None
                    else ""
                )
            )

        for txn in statement.transactions:
            if txn.direction == TransactionDirection.DEBIT:
                classification = ClassifiedTransaction(
                    transaction_id=txn.transaction_id,
                    statement_id=txn.statement_id,
                    source_file=txn.source_file,
                    source_page=txn.page,
                    date=txn.transaction_date.isoformat(),
                    description=txn.description,
                    amount=float(txn.amount),
                    direction=txn.direction.value,
                    category="Debit / Cash Outflow",
                    classification_source="SYSTEM",
                    classification_reason="Debit transaction; not evaluated as revenue.",
                )
                result.transactions.append(classification)
                continue

            rule = classify_by_rules(
                txn.description,
                direction=txn.direction.value,
            )
            if rule.category:
                classification = ClassifiedTransaction(
                    transaction_id=txn.transaction_id,
                    statement_id=txn.statement_id,
                    source_file=txn.source_file,
                    source_page=txn.page,
                    date=txn.transaction_date.isoformat(),
                    description=txn.description,
                    amount=float(txn.amount),
                    direction=txn.direction.value,
                    category=rule.category,
                    classification_source="RULE",
                    classification_reason=rule.reason,
                )
                result.transactions.append(classification)
                continue

            classification = ClassifiedTransaction(
                transaction_id=txn.transaction_id,
                statement_id=txn.statement_id,
                source_file=txn.source_file,
                source_page=txn.page,
                date=txn.transaction_date.isoformat(),
                description=txn.description,
                amount=float(txn.amount),
                direction=txn.direction.value,
                category=REVIEW_REQUIRED,
                classification_source="FALLBACK",
                classification_reason="No deterministic rule matched.",
                needs_review=True,
            )
            result.transactions.append(classification)
            pending_by_id[txn.transaction_id] = classification
            unresolved_payload.append(
                {
                    "transaction_id": txn.transaction_id,
                    "date": txn.transaction_date.isoformat(),
                    "description": txn.description,
                    "amount": float(txn.amount),
                    "tx_type": txn.direction.value,
                }
            )

    if unresolved_payload and ai_client is not None:
        try:
            decisions = classify_unresolved_transactions(
                client=ai_client,
                rows=unresolved_payload,
                model=classifier_model,
            )
            for transaction_id, decision in decisions.items():
                pending = pending_by_id.get(transaction_id)
                if pending is None:
                    continue
                pending.category = decision.category
                pending.classification_source = "AI"
                pending.classification_reason = decision.reason
                pending.classification_model = decision.model_name
                pending.needs_review = decision.requires_review or decision.category == REVIEW_REQUIRED
        except Exception as exc:
            result.warnings.append(
                f"AI transaction classification unavailable; unresolved credits "
                f"remain in manual review. Error: {exc}"
            )
    elif unresolved_payload:
        result.warnings.append(
            f"{len(unresolved_payload)} credit transaction(s) require manual review "
            "because no AI classifier was configured."
        )

    monthly_revenue: dict[str, float] = defaultdict(float)
    for txn in result.transactions:
        if txn.is_true_revenue:
            month = txn.date[:7]
            monthly_revenue[month] += txn.amount
    result.monthly_true_revenue = {
        month: round(amount, 2)
        for month, amount in sorted(monthly_revenue.items())
    }

    coverage_statuses = _coverage_status_by_month(batch.statements)
    result.revenue_baseline = select_revenue_baseline(
        monthly_true_revenue=result.monthly_true_revenue,
        coverage_status_by_month=coverage_statuses,
    )
    if result.revenue_baseline.warning:
        result.warnings.append(result.revenue_baseline.warning)

    result.mca_positions = aggregate_positions(
        debit
        for statement in batch.statements
        for debit in statement.mca_debits
    )
    monthly_debt = {
        position.lender: position.monthly_payment
        for position in result.mca_positions
    }
    result.debt_ratios = calculate_debt_ratios(
        average_monthly_true_revenue=(
            result.revenue_baseline.average_monthly_true_revenue
            if result.revenue_baseline
            else 0.0
        ),
        monthly_debt_service_by_lender=monthly_debt,
    )

    result.decision_readiness = assess_decision_readiness(
        statements=result.statements,
        transactions=result.transactions,
        revenue_baseline=result.revenue_baseline,
    )

    return result
