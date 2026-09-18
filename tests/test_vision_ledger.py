import base64

import pytest
from pydantic import ValidationError

from engine_v2.vision_ledger import VisionTransaction, image_data_url


def test_image_data_url_is_base64_png():
    payload = b"fake-png"
    url = image_data_url(payload)
    assert url.startswith("data:image/png;base64,")
    encoded = url.split(",", 1)[1]
    assert base64.b64decode(encoded) == payload


def test_vision_transaction_requires_one_direction():
    with pytest.raises(ValidationError):
        VisionTransaction(
            transaction_date="2026-08-01",
            description="AMBIGUOUS",
            debit=10,
            credit=10,
            evidence_text="AMBIGUOUS 10.00 10.00",
        )
