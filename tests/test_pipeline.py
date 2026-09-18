from engine_v2.pipeline import _coverage_status_by_month


def test_coverage_resolution_prefers_partial_over_complete():
    # Lightweight fake objects with only the attributes used by the helper.
    class Coverage:
        def __init__(self, status):
            self.status = type("Status", (), {"value": status})()

    class Statement:
        def __init__(self, status):
            from datetime import date
            self.period_start = date(2026, 9, 1)
            self.period_end = date(2026, 9, 30)
            self.coverage = Coverage(status)
            self.transactions = []

    statuses = _coverage_status_by_month(
        [Statement("COMPLETE"), Statement("PARTIAL")]
    )
    assert statuses["2026-09"] == "PARTIAL"
