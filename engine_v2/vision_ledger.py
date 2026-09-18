from __future__ import annotations

import base64
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator


class VisionTransaction(BaseModel):
    transaction_date: date
    description: str = Field(min_length=1)
    debit: Decimal | None = Field(default=None, gt=0)
    credit: Decimal | None = Field(default=None, gt=0)
    running_balance: Decimal | None = None
    evidence_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def exactly_one_direction(self):
        if (self.debit is None) == (self.credit is None):
            raise ValueError(
                "Exactly one of debit or credit must be populated."
            )
        return self


class VisionPageLedger(BaseModel):
    page_number: int = Field(ge=1)
    transactions: list[VisionTransaction] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


SYSTEM_INSTRUCTIONS = """You extract bank-statement ledger rows from a single page image.

This is transcription, not underwriting and not classification.

Rules:
- Extract only transaction rows visibly present on this page.
- Never invent a transaction, date, description, amount, or balance.
- Preserve the printed transaction description as closely as possible.
- A transaction must have exactly one debit or credit amount.
- If a row is too ambiguous to determine debit versus credit, omit the row and add a warning.
- When the page uses a continuation date convention, use the most recent visibly printed transaction date only when the page layout clearly shows subsequent rows belong to that date.
- Do not extract opening balances, closing balances, totals, subtotals, page summaries, account numbers, fees summaries, or column headers as transactions.
- evidence_text must be a short text fragment visible in the row that supports the extraction.
- If there are no readable transaction rows, return an empty transactions list.
"""


def image_data_url(png_bytes: bytes) -> str:
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def extract_page_ledger_with_vision(
    *,
    client: Any,
    png_bytes: bytes,
    page_number: int,
    model: str = "gpt-5.6-terra",
) -> VisionPageLedger:
    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": SYSTEM_INSTRUCTIONS,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"Transcribe transaction rows from statement page "
                            f"{page_number}. Return only rows visibly supported "
                            "by the page."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": image_data_url(png_bytes),
                        "detail": "high",
                    },
                ],
            },
        ],
        text_format=VisionPageLedger,
    )

    parsed = response.output_parsed
    if parsed is None:
        return VisionPageLedger(
            page_number=page_number,
            warnings=["Vision model returned no structured ledger."],
        )

    if parsed.page_number != page_number:
        parsed.page_number = page_number
    return parsed


def render_pdf_page_png(
    pdf_bytes: bytes,
    *,
    page_number: int,
    scale: float = 2.0,
) -> bytes:
    import fitz

    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        index = page_number - 1
        if index < 0 or index >= len(pdf):
            raise IndexError(f"Page {page_number} is out of range.")
        page = pdf[index]
        pix = page.get_pixmap(
            matrix=fitz.Matrix(scale, scale),
            alpha=False,
        )
        return pix.tobytes("png")
    finally:
        pdf.close()
