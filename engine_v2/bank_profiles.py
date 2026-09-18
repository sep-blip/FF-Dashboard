from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BankProfile:
    bank_id: str
    display_name: str
    signatures: tuple[str, ...]
    date_order: str = "DMY"
    notes: str | None = None


BANK_PROFILES: tuple[BankProfile, ...] = (
    BankProfile(
        bank_id="RBC",
        display_name="Royal Bank of Canada",
        signatures=(
            "ROYAL BANK OF CANADA",
            "RBC ROYAL BANK",
            "RBC BUSINESS",
        ),
    ),
    BankProfile(
        bank_id="TD",
        display_name="TD Canada Trust",
        signatures=(
            "TD CANADA TRUST",
            "TORONTO-DOMINION BANK",
            "TD BUSINESS BANKING",
        ),
    ),
    BankProfile(
        bank_id="BMO",
        display_name="Bank of Montreal",
        signatures=(
            "BANK OF MONTREAL",
            "BMO BANK OF MONTREAL",
            "BMO FINANCIAL GROUP",
        ),
    ),
    BankProfile(
        bank_id="NBC",
        display_name="National Bank of Canada",
        signatures=(
            "BANQUE NATIONALE",
            "NATIONAL BANK OF CANADA",
            "NATIONAL BANK",
        ),
        date_order="MDY",
    ),
    BankProfile(
        bank_id="CIBC",
        display_name="CIBC",
        signatures=(
            "CANADIAN IMPERIAL BANK OF COMMERCE",
            "CIBC BUSINESS",
            "CIBC",
        ),
    ),
    BankProfile(
        bank_id="SCOTIA",
        display_name="Scotiabank",
        signatures=(
            "BANK OF NOVA SCOTIA",
            "SCOTIABANK",
            "SCOTIA ONLINE",
        ),
    ),
    BankProfile(
        bank_id="DESJARDINS",
        display_name="Desjardins",
        signatures=(
            "DESJARDINS",
            "CAISSE DESJARDINS",
            "MOUVEMENT DESJARDINS",
        ),
    ),
)


def detect_bank_profile(text: str) -> BankProfile | None:
    upper = str(text or "").upper()
    candidates: list[tuple[int, BankProfile]] = []

    for profile in BANK_PROFILES:
        score = sum(
            len(signature)
            for signature in profile.signatures
            if signature in upper
        )
        if score:
            candidates.append((score, profile))

    if not candidates:
        return None

    return max(candidates, key=lambda item: item[0])[1]
