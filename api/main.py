from __future__ import annotations

import os
from dataclasses import asdict

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from engine_v2.funding import FundingPolicy, calculate_funding_capacity
from engine_v2.metrics import select_revenue_baseline
from engine_v2.pipeline import UnderwritingPipelineResult, analyze_statement_files

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
    version="0.4.0",
    description=(
        "Stateless underwriting services for statement ingestion, deterministic "
        "financial calculations, transaction classification, integrity controls, "
        "and funding analysis."
    ),
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _optional_openai_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=api_key) if api_key else None


async def _read_uploads(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    payloads: list[tuple[str, bytes]] = []
    for upload in files:
        payloads.append(
            (
                upload.filename or "statement.pdf",
                await upload.read(),
            )
        )
    return payloads


def _analysis_response(
    result: UnderwritingPipelineResult,
) -> StatementAnalysisResponse:
    statements = []
    for statement in result.statements:
        statements.append(
            StatementSummaryResponse(
                statement_id=statement.statement_id,
                source_file=statement.source_file,
                page_count=statement.page_count,
                bank_id=statement.bank_id,
                bank_name=statement.bank_name,
                extraction_quality_score=(
                    statement.extraction_quality.score
                    if statement.extraction_quality else None
                ),
                extraction_quality_status=(
                    statement.extraction_quality.status
                    if statement.extraction_quality else None
                ),
                extraction_mode=(
                    statement.extraction_quality.extraction_mode
                    if statement.extraction_quality else None
                ),
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
                    (statement.composite_integrity or statement.integrity).score
                    if (statement.composite_integrity or statement.integrity)
                    else None
                ),
                integrity_status=(
                    (statement.composite_integrity or statement.integrity).status
                    if (statement.composite_integrity or statement.integrity)
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


def _run_statement_analysis(
    payloads: list[tuple[str, bytes]],
    *,
    enable_ocr: bool,
    use_ai_classifier: bool,
) -> UnderwritingPipelineResult:
    client = _optional_openai_client() if use_ai_classifier else None
    return analyze_statement_files(
        files=payloads,
        ai_client=client,
        classifier_model=os.getenv(
            "TRANSACTION_CLASSIFIER_MODEL",
            "gpt-5.6-terra",
        ),
        enable_ocr=enable_ocr,
    )


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
    payloads = await _read_uploads(files)
    result = _run_statement_analysis(
        payloads,
        enable_ocr=enable_ocr,
        use_ai_classifier=use_ai_classifier,
    )
    return _analysis_response(result)
