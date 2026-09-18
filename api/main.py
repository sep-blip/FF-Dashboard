from __future__ import annotations

import os
from dataclasses import asdict

from fastapi import FastAPI, File, Form, UploadFile
from openai import OpenAI

from engine_v2.funding import FundingPolicy, calculate_funding_capacity
from engine_v2.metrics import select_revenue_baseline
from engine_v2.pipeline import analyze_statement_files

from .schemas import (
    ClassifiedTransactionResponse,
    DebtRatioResponse,
    FundingCapacityRequest,
    FundingCapacityResponse,
    HealthResponse,
    McaPositionResponse,
    RevenueBaselineRequest,
    RevenueBaselineResponse,
    StatementAnalysisResponse,
    StatementSummaryResponse,
)


app = FastAPI(
    title="Forward Funding Underwriting API",
    version="0.2.0",
    description=(
        "Underwriting services for statement ingestion, deterministic financial "
        "calculations, transaction classification, and funding-capacity analysis."
    ),
)


def _optional_openai_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=api_key) if api_key else None


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="underwriting-api")


@app.post(
    "/v1/underwriting/revenue-baseline",
    response_model=RevenueBaselineResponse,
)
def revenue_baseline(payload: RevenueBaselineRequest) -> RevenueBaselineResponse:
    result = select_revenue_baseline(
        monthly_true_revenue=payload.monthly_true_revenue,
        coverage_status_by_month=payload.coverage_status_by_month,
    )
    return RevenueBaselineResponse(
        average_monthly_true_revenue=result.average_monthly_true_revenue,
        months_used=list(result.months_used),
        partial_months_excluded=list(result.partial_months_excluded),
        basis=result.basis,
        warning=result.warning,
    )


@app.post(
    "/v1/underwriting/funding-capacity",
    response_model=FundingCapacityResponse,
)
def funding_capacity(payload: FundingCapacityRequest) -> FundingCapacityResponse:
    policy = FundingPolicy(**payload.policy.model_dump())
    result = calculate_funding_capacity(
        average_monthly_true_revenue=payload.average_monthly_true_revenue,
        existing_monthly_debt_service=payload.existing_monthly_debt_service,
        policy=policy,
    )
    return FundingCapacityResponse(**asdict(result))


@app.post(
    "/v1/documents/bank-statements/analyze",
    response_model=StatementAnalysisResponse,
)
async def analyze_bank_statements(
    files: list[UploadFile] = File(...),
    enable_ocr: bool = Form(False),
    use_ai_classifier: bool = Form(True),
) -> StatementAnalysisResponse:
    """Analyze one or more bank-statement PDFs.

    The endpoint remains useful without an OpenAI key: deterministic rules and
    financial calculations still run, while unresolved credits are routed to
    manual review. When an API key is configured, only unresolved credits are
    sent to the structured AI classifier.
    """

    upload_payload: list[tuple[str, bytes]] = []
    for upload in files:
        payload = await upload.read()
        upload_payload.append((upload.filename or "statement.pdf", payload))

    client = _optional_openai_client() if use_ai_classifier else None
    result = analyze_statement_files(
        files=upload_payload,
        ai_client=client,
        classifier_model=os.getenv(
            "TRANSACTION_CLASSIFIER_MODEL",
            "gpt-5.6-terra",
        ),
        enable_ocr=enable_ocr,
    )

    statements = []
    for statement in result.statements:
        statements.append(
            StatementSummaryResponse(
                statement_id=statement.statement_id,
                source_file=statement.source_file,
                page_count=statement.page_count,
                period_start=(
                    statement.period_start.isoformat()
                    if statement.period_start
                    else None
                ),
                period_end=(
                    statement.period_end.isoformat()
                    if statement.period_end
                    else None
                ),
                coverage_status=(
                    statement.coverage.status.value
                    if statement.coverage
                    else "UNKNOWN"
                ),
                coverage_pct=(
                    statement.coverage.coverage_pct
                    if statement.coverage
                    else None
                ),
                integrity_score=(
                    statement.integrity.score
                    if statement.integrity
                    else None
                ),
                integrity_status=(
                    statement.integrity.status
                    if statement.integrity
                    else None
                ),
                reconciliation_status=statement.reconciliation_status,
                reconciliation_variance=(
                    str(statement.reconciliation_variance)
                    if statement.reconciliation_variance is not None
                    else None
                ),
                transaction_count=len(statement.transactions),
                credit_anchor=(
                    str(statement.credit_anchor)
                    if statement.credit_anchor is not None
                    else None
                ),
                credit_anchor_method=statement.credit_anchor_method,
            )
        )

    transactions = [
        ClassifiedTransactionResponse(**asdict(transaction))
        for transaction in result.transactions
    ]

    mca_positions = [
        McaPositionResponse(
            lender=position.lender,
            tier=position.tier,
            payment_amount=position.payment_amount,
            frequency=position.frequency,
            monthly_payment=position.monthly_payment,
            observed_payments=position.observed_payments,
            first_observed_date=position.first_observed_date.isoformat(),
            last_observed_date=position.last_observed_date.isoformat(),
        )
        for position in result.mca_positions
    ]

    baseline = None
    if result.revenue_baseline:
        baseline = RevenueBaselineResponse(
            average_monthly_true_revenue=(
                result.revenue_baseline.average_monthly_true_revenue
            ),
            months_used=list(result.revenue_baseline.months_used),
            partial_months_excluded=list(
                result.revenue_baseline.partial_months_excluded
            ),
            basis=result.revenue_baseline.basis,
            warning=result.revenue_baseline.warning,
        )

    debt_ratios = None
    if result.debt_ratios:
        debt_ratios = DebtRatioResponse(
            average_monthly_true_revenue=(
                result.debt_ratios.average_monthly_true_revenue
            ),
            total_monthly_debt_service=(
                result.debt_ratios.total_monthly_debt_service
            ),
            total_debt_ratio_pct=result.debt_ratios.total_debt_ratio_pct,
            individual_ratios_pct=result.debt_ratios.individual_ratios_pct,
        )

    return StatementAnalysisResponse(
        statements=statements,
        transactions=transactions,
        mca_positions=mca_positions,
        monthly_true_revenue=result.monthly_true_revenue,
        revenue_baseline=baseline,
        debt_ratios=debt_ratios,
        skipped_duplicates=result.skipped_duplicates,
        warnings=result.warnings,
    )
