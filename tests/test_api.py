import fitz
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def _blank_pdf_bytes() -> bytes:
    pdf = fitz.open()
    pdf.new_page(width=612, height=792)
    payload = pdf.tobytes()
    pdf.close()
    return payload


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_funding_capacity_endpoint():
    response = client.post(
        "/v1/underwriting/funding-capacity",
        json={
            "average_monthly_true_revenue": 100000,
            "existing_monthly_debt_service": 10000,
            "policy": {
                "revenue_multiple": 0.8,
                "max_total_debt_burden_pct": 20,
                "factor_rate": 1.3,
                "term_business_days": 126
            }
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recommended_advance"] <= body["max_by_revenue"]
    assert body["projected_total_debt_ratio_pct"] <= 20.01


def test_revenue_baseline_endpoint_excludes_partial_when_complete_exists():
    response = client.post(
        "/v1/underwriting/revenue-baseline",
        json={
            "monthly_true_revenue": {
                "2026-07": 100000,
                "2026-08": 120000,
                "2026-09": 55000
            },
            "coverage_status_by_month": {
                "2026-07": "COMPLETE",
                "2026-08": "COMPLETE",
                "2026-09": "PARTIAL"
            }
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["average_monthly_true_revenue"] == 110000
    assert body["partial_months_excluded"] == ["2026-09"]


def test_statement_analysis_endpoint_degrades_gracefully_without_ai():
    response = client.post(
        "/v1/documents/bank-statements/analyze",
        files=[
            ("files", ("statement.pdf", _blank_pdf_bytes(), "application/pdf")),
        ],
        data={
            "enable_ocr": "false",
            "use_ai_classifier": "false",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["statements"]) == 1
    assert body["transactions"] == []
    assert body["mca_positions"] == []


def test_statement_analysis_endpoint_skips_duplicate_uploads():
    payload = _blank_pdf_bytes()
    response = client.post(
        "/v1/documents/bank-statements/analyze",
        files=[
            ("files", ("a.pdf", payload, "application/pdf")),
            ("files", ("b.pdf", payload, "application/pdf")),
        ],
        data={"use_ai_classifier": "false"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["statements"]) == 1
    assert len(body["skipped_duplicates"]) == 1


def test_statement_analysis_rejects_non_pdf_content():
    response = client.post(
        "/v1/documents/bank-statements/analyze",
        files=[
            (
                "files",
                ("fake.pdf", b"not-a-real-pdf", "application/pdf"),
            ),
        ],
        data={"use_ai_classifier": "false"},
    )
    assert response.status_code == 415


def test_review_recalculation_endpoint_applies_manual_override():
    response = client.post(
        "/v1/underwriting/recalculate-reviewed-transactions",
        json={
            "transactions": [
                {
                    "transaction_id": "t1",
                    "date": "2026-08-01",
                    "description": "CUSTOMER PAYMENT",
                    "amount": 10000,
                    "direction": "credit",
                    "category": "Review Required - Unidentified / Unusual Deposit",
                    "needs_review": True
                }
            ],
            "overrides": [
                {
                    "transaction_id": "t1",
                    "category": "True Revenue - Customer Payment / Cheque",
                    "reason": "Verified invoice payment"
                }
            ],
            "coverage_status_by_month": {
                "2026-08": "COMPLETE"
            },
            "monthly_debt_service_by_lender": {},
            "readiness_checks": {
                "documents": "PASS",
                "ledger": "PASS",
                "extraction_quality": "PASS",
                "reconciliation": "PASS",
                "integrity": "PASS",
                "coverage": "PASS",
                "classification": "REVIEW",
                "revenue_baseline": "PASS"
            }
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["monthly_true_revenue"]["2026-08"] == 10000
    assert body["remaining_review_count"] == 0
    assert body["readiness_status"] == "READY"


def test_credit_report_endpoint_requires_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post(
        "/v1/documents/credit-report/analyze",
        files=[
            (
                "file",
                ("credit.pdf", b"not-a-real-pdf", "application/pdf"),
            )
        ],
        data={"enable_ocr": "false"},
    )
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_scorecard_endpoint_returns_versioned_score():
    response = client.post(
        "/v1/underwriting/scorecard",
        json={
            "average_monthly_true_revenue": 100000,
            "revenue_trend_pct": 5,
            "average_deposit_count": 25,
            "revenue_volatility_pct": 12,
            "average_daily_balance": 10000,
            "mca_position_count": 1,
            "mca_burden_pct": 8,
            "borrowing_velocity": "0 in 90 Days",
            "returned_ach_or_missed_payments": 0,
            "negative_days": 1,
            "time_in_business_months": 48,
            "industry_score": 7,
            "seasonality_score": 5,
            "credit_score": 700,
            "public_records": "Clean",
            "bank_verification": "Original PDF",
            "revenue_concentration_pct": 20,
            "suspected_fraud": False,
            "severe_wash_transactions": False,
            "active_lender_default": False
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["policy_version"] == "ff-scorecard-v1"
    assert body["max_score"] == 93
    assert body["score"] > 0
