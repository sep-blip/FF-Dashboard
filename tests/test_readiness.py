from dataclasses import dataclass

from engine_v2.readiness import ReadinessStatus, assess_decision_readiness


@dataclass
class FakeStatus:
    value: str


@dataclass
class FakeCoverage:
    status: FakeStatus


@dataclass
class FakeQuality:
    status: str


@dataclass
class FakeIntegrity:
    status: str


@dataclass
class FakeStatement:
    source_file: str
    extraction_quality: FakeQuality | None
    reconciliation_status: str
    composite_integrity: FakeIntegrity | None
    integrity: FakeIntegrity | None
    coverage: FakeCoverage | None


@dataclass
class FakeTransaction:
    direction: str
    needs_review: bool


@dataclass
class FakeBaseline:
    average_monthly_true_revenue: float
    basis: str


def test_ready_requires_clean_controls():
    result = assess_decision_readiness(
        statements=[
            FakeStatement(
                source_file="a.pdf",
                extraction_quality=FakeQuality("HIGH"),
                reconciliation_status="PASS",
                composite_integrity=FakeIntegrity("LOW_CONCERN"),
                integrity=None,
                coverage=FakeCoverage(FakeStatus("COMPLETE")),
            )
        ],
        transactions=[FakeTransaction("credit", False)],
        revenue_baseline=FakeBaseline(
            100000,
            "VERIFIED_COMPLETE_MONTHS",
        ),
    )
    assert result.status == ReadinessStatus.READY
    assert result.automated_offer_allowed


def test_failed_reconciliation_blocks_automated_offer():
    result = assess_decision_readiness(
        statements=[
            FakeStatement(
                source_file="a.pdf",
                extraction_quality=FakeQuality("HIGH"),
                reconciliation_status="FAIL",
                composite_integrity=FakeIntegrity("LOW_CONCERN"),
                integrity=None,
                coverage=FakeCoverage(FakeStatus("COMPLETE")),
            )
        ],
        transactions=[FakeTransaction("credit", False)],
        revenue_baseline=FakeBaseline(
            100000,
            "VERIFIED_COMPLETE_MONTHS",
        ),
    )
    assert result.status == ReadinessStatus.BLOCKED
    assert not result.automated_offer_allowed


def test_partial_month_routes_to_review_not_failure():
    result = assess_decision_readiness(
        statements=[
            FakeStatement(
                source_file="partial.pdf",
                extraction_quality=FakeQuality("HIGH"),
                reconciliation_status="PASS",
                composite_integrity=FakeIntegrity("LOW_CONCERN"),
                integrity=None,
                coverage=FakeCoverage(FakeStatus("PARTIAL")),
            )
        ],
        transactions=[FakeTransaction("credit", False)],
        revenue_baseline=FakeBaseline(
            100000,
            "VERIFIED_COMPLETE_MONTHS",
        ),
    )
    assert result.status == ReadinessStatus.REVIEW_REQUIRED
