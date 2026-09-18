from engine_v2.bank_profiles import detect_bank_profile


def test_detects_national_bank_bilingual_signature():
    profile = detect_bank_profile(
        "BANQUE NATIONALE DU CANADA / NATIONAL BANK statement"
    )
    assert profile is not None
    assert profile.bank_id == "NBC"


def test_unknown_bank_returns_none():
    assert detect_bank_profile("Generic financial statement") is None
