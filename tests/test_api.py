from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


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
