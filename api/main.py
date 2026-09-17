from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI

from engine_v2.funding import FundingPolicy, calculate_funding_capacity
from engine_v2.metrics import select_revenue_baseline

from .schemas import (
    FundingCapacityRequest,
    FundingCapacityResponse,
    HealthResponse,
    RevenueBaselineRequest,
    RevenueBaselineResponse,
)


app = FastAPI(
    title="Forward Funding Underwriting API",
    version="0.1.0",
    description=(
        "Deterministic underwriting services. Document ingestion and persistent "
        "application workflows will be added behind the same versioned API."
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
