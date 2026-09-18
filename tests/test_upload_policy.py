import pytest
from fastapi import HTTPException

from api.upload_policy import validate_pdf_upload


def test_non_pdf_is_rejected_before_extraction():
    with pytest.raises(HTTPException) as exc:
        validate_pdf_upload(
            filename="fake.pdf",
            payload=b"not a PDF",
        )
    assert exc.value.status_code == 415


def test_empty_upload_is_rejected():
    with pytest.raises(HTTPException) as exc:
        validate_pdf_upload(filename="empty.pdf", payload=b"")
    assert exc.value.status_code == 400
