from engine_v2.credit_extraction import (
    credit_report_schema,
    validate_credit_profile,
)


def test_missing_fields_can_be_null_in_schema():
    schema = credit_report_schema()["json_schema"]["schema"]
    assert "null" in schema["properties"]["fico_score"]["type"]
    assert "null" in schema["properties"]["total_high_credit"]["type"]


def test_out_of_range_fico_is_discarded_not_trusted():
    profile = validate_credit_profile(
        {
            "owner_name": "Example",
            "fico_score": 1200,
            "total_high_credit": None,
            "revolving_credit_utilization_pct": None,
            "active_collections_count": None,
            "total_collections_amount": None,
            "bankruptcies_found": None,
            "number_of_mortgages": None,
            "mortgage_ltv_details": None,
            "evidence": {},
        },
        model="test",
    )
    assert profile.fico_score is None
    assert profile.warnings
