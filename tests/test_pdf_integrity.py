from engine_v2.pdf_integrity import (
    count_eof_markers,
    looks_like_general_authoring_software,
)


def test_incremental_eof_count():
    assert count_eof_markers(b"%PDF fake %%EOF more %%EOF") == 2


def test_general_authoring_software_marker():
    marker = looks_like_general_authoring_software(
        {"Producer": "Adobe Photoshop 2026"}
    )
    assert marker == "ADOBE PHOTOSHOP"


def test_bankish_producer_is_not_automatically_flagged():
    marker = looks_like_general_authoring_software(
        {"Producer": "Bank Statement Generator"}
    )
    assert marker is None
