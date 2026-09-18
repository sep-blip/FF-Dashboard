from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class CreditProfile(BaseModel):
    owner_name: str | None = None
    fico_score: int | None = None
    total_high_credit: float | None = None
    revolving_credit_utilization_pct: float | None = None
    active_collections_count: int | None = None
    total_collections_amount: float | None = None
    bankruptcies_found: bool | None = None
    number_of_mortgages: int | None = None
    mortgage_ltv_details: str | None = None
    evidence: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    model_name: str | None = None


def credit_report_schema() -> dict[str, Any]:
    nullable_string = {"type": ["string", "null"]}
    nullable_number = {"type": ["number", "null"]}
    nullable_integer = {"type": ["integer", "null"]}
    nullable_boolean = {"type": ["boolean", "null"]}

    evidence_properties = {
        "owner_name": nullable_string,
        "fico_score": nullable_string,
        "total_high_credit": nullable_string,
        "revolving_credit_utilization_pct": nullable_string,
        "active_collections_count": nullable_string,
        "total_collections_amount": nullable_string,
        "bankruptcies_found": nullable_string,
        "number_of_mortgages": nullable_string,
        "mortgage_ltv_details": nullable_string,
    }

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "credit_report_extraction_v2",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "owner_name": nullable_string,
                    "fico_score": nullable_integer,
                    "total_high_credit": nullable_number,
                    "revolving_credit_utilization_pct": nullable_number,
                    "active_collections_count": nullable_integer,
                    "total_collections_amount": nullable_number,
                    "bankruptcies_found": nullable_boolean,
                    "number_of_mortgages": nullable_integer,
                    "mortgage_ltv_details": nullable_string,
                    "evidence": {
                        "type": "object",
                        "properties": evidence_properties,
                        "required": list(evidence_properties),
                        "additionalProperties": False,
                    },
                },
                "required": [
                    "owner_name",
                    "fico_score",
                    "total_high_credit",
                    "revolving_credit_utilization_pct",
                    "active_collections_count",
                    "total_collections_amount",
                    "bankruptcies_found",
                    "number_of_mortgages",
                    "mortgage_ltv_details",
                    "evidence",
                ],
                "additionalProperties": False,
            },
        },
    }


SYSTEM_INSTRUCTIONS = """Extract underwriting fields from the supplied credit-report text.

Accuracy rules:
- Extract only values explicitly supported by the report text.
- If a field is absent, unreadable, ambiguous, or only inferable, return null. Never substitute a typical/default value.
- FICO/Beacon score must be an explicitly printed 3-digit score.
- total_high_credit means the exact explicit report value labelled High Credit/HighCred when present. Do not sum trade limits or calculate it yourself.
- Utilization must come from an explicit report metric; do not calculate it from balances and limits.
- Collection counts and amounts must refer to active/unpaid collections when the report distinguishes status.
- bankruptcies_found may be true only with explicit bankruptcy/consumer-proposal evidence; return false only when the report explicitly supports no such record, otherwise null.
- Mortgage count must come from explicit mortgage trades or an explicit report summary.
- Do not invent property values or LTV. If property value is absent, return null for mortgage_ltv_details unless the report explicitly says it is unavailable.
- For every field, evidence must be a short verbatim-adjacent label/value fragment from the supplied text, or null if the value is null.
"""


def validate_credit_profile(payload: dict[str, Any], *, model: str | None = None) -> CreditProfile:
    warnings: list[str] = []

    fico = payload.get("fico_score")
    if fico is not None and not 300 <= int(fico) <= 900:
        warnings.append(f"Discarded out-of-range FICO/Beacon value: {fico}")
        payload["fico_score"] = None

    utilization = payload.get("revolving_credit_utilization_pct")
    if utilization is not None and float(utilization) < 0:
        warnings.append("Discarded negative revolving-utilization value.")
        payload["revolving_credit_utilization_pct"] = None

    for field in (
        "total_high_credit",
        "active_collections_count",
        "total_collections_amount",
        "number_of_mortgages",
    ):
        value = payload.get(field)
        if value is not None and float(value) < 0:
            warnings.append(f"Discarded negative value for {field}.")
            payload[field] = None

    evidence = {
        key: value
        for key, value in (payload.get("evidence") or {}).items()
        if value is not None
    }

    return CreditProfile(
        owner_name=payload.get("owner_name"),
        fico_score=payload.get("fico_score"),
        total_high_credit=payload.get("total_high_credit"),
        revolving_credit_utilization_pct=payload.get("revolving_credit_utilization_pct"),
        active_collections_count=payload.get("active_collections_count"),
        total_collections_amount=payload.get("total_collections_amount"),
        bankruptcies_found=payload.get("bankruptcies_found"),
        number_of_mortgages=payload.get("number_of_mortgages"),
        mortgage_ltv_details=payload.get("mortgage_ltv_details"),
        evidence=evidence,
        warnings=warnings,
        model_name=model,
    )


def extract_credit_profile(
    *,
    client: Any,
    credit_text: str,
    model: str = "gpt-5.6-sol",
    timeout: float = 60.0,
) -> CreditProfile:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": credit_text},
        ],
        response_format=credit_report_schema(),
        timeout=timeout,
    )
    payload = json.loads(response.choices[0].message.content)
    return validate_credit_profile(payload, model=model)
