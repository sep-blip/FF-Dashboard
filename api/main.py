from __future__ import annotations

import hashlib
import os
from dataclasses import asdict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from api.upload_policy import (
    max_statement_files,
    validate_pdf_upload,
)
from engine_v2.credit_extraction import extract_credit_profile
from engine_v2.funding import FundingPolicy, calculate_funding_capacity
from engine_v2.metrics import select_revenue_baseline
from engine_v2.pipeline import UnderwritingPipelineResult, analyze_statement_files
from engine_v2.review import (
    ReviewedTransaction,
    TransactionOverride,
    recalculate_after_review,
)
from engine_v2.scorecard import ScorecardInputs, calculate_scorecard
from engine_v2.statement_parser import extract_text_with_fallbacks

from .schemas import (
    AuditManifestResponse,
    ClassifiedTransactionResponse,
    CreditProfileResponse,
    DebtRatioResponse,
    DecisionReadinessResponse,
    FundingCapacityRequest,
    FundingCapacityResponse,
    HealthResponse,
    McaPositionResponse,
    RevenueBaselineRequest,
    RevenueBaselineResponse,
    ReviewRecalculationRequest,
    ReviewRecalculationResponse,
    OverrideAuditResponse,
    ScorecardRequest,
    ScorecardResponse,
    SourceDocumentAuditResponse,
    StatementAnalysisResponse,
    StatementSummaryResponse,
    UnderwritingFeaturesResponse,
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
    if len(files) > max_statement_files():
        raise HTTPException(
            status_code=413,
            detail=(
                f"Too many statement files: {len(files)}. "
                f"Configured limit is {max_statement_files()}."
            ),
        )

    payloads: list[tuple[str, bytes]] = []
    for upload in files:
        filename = upload.filename or "statement.pdf"
        payload = await upload.read()
        validate_pdf_upload(
            filename=filename,
            payload=payload,
        )
        payloads.append((filename, payload))
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

    features = None
    if result.features:
        features = UnderwritingFeaturesResponse(
            **asdict(result.features)
        )

    readiness = None
    if result.decision_readiness:
        readiness = DecisionReadinessResponse(
            status=result.decision_readiness.status.value,
            automated_offer_allowed=(
                result.decision_readiness.automated_offer_allowed
            ),
            blocking_reasons=list(
                result.decision_readiness.blocking_reasons
            ),
            review_reasons=list(
                result.decision_readiness.review_reasons
            ),
            checks=result.decision_readiness.checks,
        )

    audit_manifest = None
    if result.audit_manifest:
        audit_manifest = AuditManifestResponse(
            run_id=result.audit_manifest.run_id,
            generated_at=result.audit_manifest.generated_at.isoformat(),
            engine_version=result.audit_manifest.engine_version,
            classifier_model=result.audit_manifest.classifier_model,
            vision_model=result.audit_manifest.vision_model,
            enable_ocr=result.audit_manifest.enable_ocr,
            enable_vision_fallback=(
                result.audit_manifest.enable_vision_fallback
            ),
            source_documents=[
                SourceDocumentAuditResponse(
                    source_file=document.source_file,
                    sha256=document.sha256,
                    statement_id=document.statement_id,
                    bank_id=document.bank_id,
                    page_count=document.page_count,
                )
                for document in result.audit_manifest.source_documents
            ],
        )

    return StatementAnalysisResponse(
        statements=statements,
        transactions=transactions,
        mca_positions=mca_positions,
        monthly_true_revenue=result.monthly_true_revenue,
        revenue_baseline=baseline,
        debt_ratios=debt_ratios,
        features=features,
        decision_readiness=readiness,
        audit_manifest=audit_manifest,
        skipped_duplicates=result.skipped_duplicates,
        warnings=result.warnings,
    )


def _run_statement_analysis(
    payloads: list[tuple[str, bytes]],
    *,
    enable_ocr: bool,
    enable_vision_fallback: bool,
    use_ai_classifier: bool,
) -> UnderwritingPipelineResult:
    classifier_client = (
        _optional_openai_client()
        if use_ai_classifier
        else None
    )
    vision_client = (
        _optional_openai_client()
        if enable_vision_fallback
        else None
    )
    return analyze_statement_files(
        files=payloads,
        ai_client=classifier_client,
        vision_client=vision_client,
        classifier_model=os.getenv(
            "TRANSACTION_CLASSIFIER_MODEL",
            "gpt-5.6-terra",
        ),
        enable_ocr=enable_ocr,
        enable_vision_fallback=enable_vision_fallback,
        vision_model=os.getenv(
            "VISION_LEDGER_MODEL",
            "gpt-5.6-terra",
        ),
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
    enable_vision_fallback: bool = Form(True),
    use_ai_classifier: bool = Form(True),
) -> StatementAnalysisResponse:
    payloads = await _read_uploads(files)
    result = _run_statement_analysis(
        payloads,
        enable_ocr=enable_ocr,
        enable_vision_fallback=enable_vision_fallback,
        use_ai_classifier=use_ai_classifier,
    )
    return _analysis_response(result)


@app.post(
    "/v1/underwriting/recalculate-reviewed-transactions",
    response_model=ReviewRecalculationResponse,
)
def recalculate_reviewed_transactions(
    payload: ReviewRecalculationRequest,
) -> ReviewRecalculationResponse:
    try:
        result = recalculate_after_review(
            transactions=[
                ReviewedTransaction(
                    transaction_id=transaction.transaction_id,
                    date=transaction.date,
                    description=transaction.description,
                    amount=transaction.amount,
                    direction=transaction.direction,
                    category=transaction.category,
                    needs_review=transaction.needs_review,
                )
                for transaction in payload.transactions
            ],
            overrides=[
                TransactionOverride(
                    transaction_id=override.transaction_id,
                    category=override.category,
                    reason=override.reason,
                )
                for override in payload.overrides
            ],
            coverage_status_by_month=payload.coverage_status_by_month,
            monthly_debt_service_by_lender=(
                payload.monthly_debt_service_by_lender
            ),
            readiness_checks=payload.readiness_checks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ReviewRecalculationResponse(
        categories_by_transaction=result.categories_by_transaction,
        needs_review_by_transaction=result.needs_review_by_transaction,
        monthly_true_revenue=result.monthly_true_revenue,
        revenue_baseline=RevenueBaselineResponse(
            average_monthly_true_revenue=(
                result.revenue_baseline.average_monthly_true_revenue
            ),
            months_used=list(result.revenue_baseline.months_used),
            partial_months_excluded=list(
                result.revenue_baseline.partial_months_excluded
            ),
            basis=result.revenue_baseline.basis,
            warning=result.revenue_baseline.warning,
        ),
        debt_ratios=DebtRatioResponse(
            average_monthly_true_revenue=(
                result.debt_ratios.average_monthly_true_revenue
            ),
            total_monthly_debt_service=(
                result.debt_ratios.total_monthly_debt_service
            ),
            total_debt_ratio_pct=result.debt_ratios.total_debt_ratio_pct,
            individual_ratios_pct=(
                result.debt_ratios.individual_ratios_pct
            ),
        ),
        features=UnderwritingFeaturesResponse(
            **asdict(result.features)
        ),
        remaining_review_count=result.remaining_review_count,
        override_audit=[
            OverrideAuditResponse(
                transaction_id=event.transaction_id,
                previous_category=event.previous_category,
                new_category=event.new_category,
                reason=event.reason,
            )
            for event in result.override_audit
        ],
        readiness_status=result.readiness_status,
        automated_offer_allowed=result.automated_offer_allowed,
        readiness_checks=result.readiness_checks,
    )


@app.post(
    "/v1/documents/credit-report/analyze",
    response_model=CreditProfileResponse,
)
async def analyze_credit_report(
    file: UploadFile = File(...),
    enable_ocr: bool = Form(True),
) -> CreditProfileResponse:
    client = _optional_openai_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "OPENAI_API_KEY is required for structured credit-report "
                "extraction."
            ),
        )

    payload = await file.read()
    validate_pdf_upload(
        filename=file.filename or "credit-report.pdf",
        payload=payload,
    )
    text, diagnostics = extract_text_with_fallbacks(
        payload,
        enable_ocr=enable_ocr,
    )
    if not text:
        raise HTTPException(
            status_code=422,
            detail=(
                "No readable text could be extracted from the credit report."
            ),
        )

    try:
        profile = extract_credit_profile(
            client=client,
            credit_text=text,
            model=os.getenv(
                "CREDIT_REPORT_MODEL",
                "gpt-5.6-sol",
            ),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Credit-report extraction failed: {exc}",
        ) from exc

    warnings = list(profile.warnings)
    warnings.extend(
        diagnostic
        for diagnostic in diagnostics
        if "failed" in diagnostic.lower()
        or "fallback" in diagnostic.lower()
    )

    return CreditProfileResponse(
        source_file=file.filename or "credit-report.pdf",
        sha256=hashlib.sha256(payload).hexdigest(),
        owner_name=profile.owner_name,
        fico_score=profile.fico_score,
        total_high_credit=profile.total_high_credit,
        revolving_credit_utilization_pct=(
            profile.revolving_credit_utilization_pct
        ),
        active_collections_count=profile.active_collections_count,
        total_collections_amount=profile.total_collections_amount,
        bankruptcies_found=profile.bankruptcies_found,
        number_of_mortgages=profile.number_of_mortgages,
        mortgage_ltv_details=profile.mortgage_ltv_details,
        evidence=profile.evidence,
        warnings=warnings,
        model_name=profile.model_name,
    )


@app.post(
    "/v1/underwriting/scorecard",
    response_model=ScorecardResponse,
)
def underwriting_scorecard(
    payload: ScorecardRequest,
) -> ScorecardResponse:
    result = calculate_scorecard(
        ScorecardInputs(**payload.model_dump())
    )
    return ScorecardResponse(
        policy_version=result.policy_version,
        score=result.score,
        max_score=result.max_score,
        grade=result.grade,
        risk_tier=result.risk_tier,
        revenue_advance_multiple=result.revenue_advance_multiple,
        max_total_debt_burden_pct=(
            result.max_total_debt_burden_pct
        ),
        hard_stop=result.hard_stop,
        hard_stop_reasons=list(result.hard_stop_reasons),
        breakdown=result.breakdown,
    )
