from engine_v2.ai_classifier import build_payload, categorization_schema
from engine_v2.constants import ALLOWED_CATEGORIES


def test_payload_preserves_transaction_lineage():
    payload = build_payload(
        [
            {
                "transaction_id": "txn_1",
                "date": "2026-09-01",
                "description": "EFT CREDIT ABC",
                "amount": 1234.567,
                "tx_type": "credit",
            }
        ]
    )
    assert payload[0]["transaction_id"] == "txn_1"
    assert payload[0]["amount"] == 1234.57


def test_schema_restricts_categories():
    schema = categorization_schema()
    enum_values = (
        schema["json_schema"]["schema"]["properties"]["decisions"]["items"]
        ["properties"]["category"]["enum"]
    )
    assert tuple(enum_values) == tuple(ALLOWED_CATEGORIES)
