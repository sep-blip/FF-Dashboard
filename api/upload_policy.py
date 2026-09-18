from __future__ import annotations

import io
import os

import pdfplumber
from fastapi import HTTPException


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be positive.")
    return value


def max_statement_files() -> int:
    return _positive_int_env("MAX_STATEMENT_FILES", 24)


def max_pdf_bytes() -> int:
    return _positive_int_env("MAX_PDF_BYTES", 25 * 1024 * 1024)


def max_pdf_pages() -> int:
    return _positive_int_env("MAX_PDF_PAGES", 100)


def validate_pdf_upload(
    *,
    filename: str,
    payload: bytes,
) -> int:
    """Validate a PDF before expensive extraction/model calls.

    Returns the detected page count.
    """
    if not payload:
        raise HTTPException(
            status_code=400,
            detail=f"{filename}: uploaded file is empty.",
        )

    if len(payload) > max_pdf_bytes():
        raise HTTPException(
            status_code=413,
            detail=(
                f"{filename}: file exceeds the configured "
                f"{max_pdf_bytes()} byte limit."
            ),
        )

    if not payload.lstrip().startswith(b"%PDF-"):
        raise HTTPException(
            status_code=415,
            detail=f"{filename}: content is not a valid PDF header.",
        )

    try:
        with pdfplumber.open(io.BytesIO(payload)) as pdf:
            page_count = len(pdf.pages)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{filename}: PDF could not be opened.",
        ) from exc

    if page_count <= 0:
        raise HTTPException(
            status_code=422,
            detail=f"{filename}: PDF contains no pages.",
        )

    if page_count > max_pdf_pages():
        raise HTTPException(
            status_code=413,
            detail=(
                f"{filename}: PDF has {page_count} pages; configured limit is "
                f"{max_pdf_pages()}."
            ),
        )

    return page_count
