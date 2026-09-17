from __future__ import annotations

import io
from collections import Counter
from typing import Any

import pdfplumber
from pydantic import BaseModel, Field

from .integrity import FindingSeverity, IntegrityFinding


class PdfIntegrityReport(BaseModel):
    score: int = Field(ge=0, le=100)
    status: str
    page_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    findings: list[IntegrityFinding] = Field(default_factory=list)


_AUTHORING_SOFTWARE_MARKERS = (
    "ADOBE PHOTOSHOP",
    "ADOBE ILLUSTRATOR",
    "CANVA",
    "MICROSOFT WORD",
    "LIBREOFFICE",
    "OPENOFFICE",
    "AFFINITY DESIGNER",
    "AFFINITY PHOTO",
)


def count_eof_markers(pdf_bytes: bytes) -> int:
    return pdf_bytes.count(b"%%EOF")


def looks_like_general_authoring_software(metadata: dict[str, Any]) -> str | None:
    haystack = " ".join(
        str(metadata.get(key, "") or "")
        for key in ("Producer", "Creator", "producer", "creator")
    ).upper()
    for marker in _AUTHORING_SOFTWARE_MARKERS:
        if marker in haystack:
            return marker
    return None


def analyze_pdf_integrity(pdf_bytes: bytes) -> PdfIntegrityReport:
    """Perform conservative structural checks on a PDF.

    Findings are review signals, not proof of manipulation. The function avoids
    declaring fraud because legitimate bank documents can be re-saved, merged,
    printed to PDF, or contain multiple page templates.
    """
    score = 100
    findings: list[IntegrityFinding] = []
    metadata: dict[str, Any] = {}

    eof_count = count_eof_markers(pdf_bytes)
    if eof_count > 1:
        score -= min(10, (eof_count - 1) * 3)
        findings.append(
            IntegrityFinding(
                code="PDF_INCREMENTAL_UPDATES",
                severity=FindingSeverity.INFO,
                message=(
                    f"PDF contains {eof_count} EOF markers, consistent with one or "
                    "more incremental saves/updates. This is not proof of alteration."
                ),
                evidence={"eof_markers": eof_count},
            )
        )

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as doc:
            metadata = dict(doc.metadata or {})
            page_count = len(doc.pages)

            authoring_marker = looks_like_general_authoring_software(metadata)
            if authoring_marker:
                score -= 15
                findings.append(
                    IntegrityFinding(
                        code="GENERAL_AUTHORING_SOFTWARE",
                        severity=FindingSeverity.WARNING,
                        message=(
                            f"PDF metadata references {authoring_marker}. A document "
                            "created or re-saved in general-purpose authoring software "
                            "should receive manual integrity review."
                        ),
                        evidence={"software": authoring_marker},
                    )
                )

            dimensions = [
                (round(float(page.width), 1), round(float(page.height), 1))
                for page in doc.pages
            ]
            dimension_counts = Counter(dimensions)
            if len(dimension_counts) > 1:
                score -= min(10, (len(dimension_counts) - 1) * 4)
                findings.append(
                    IntegrityFinding(
                        code="MIXED_PAGE_DIMENSIONS",
                        severity=FindingSeverity.WARNING,
                        message="The PDF contains multiple page dimensions.",
                        evidence={
                            "dimensions": {
                                f"{w}x{h}": count
                                for (w, h), count in dimension_counts.items()
                            }
                        },
                    )
                )

            page_fonts: list[set[str]] = []
            blank_pages: list[int] = []
            for page_no, page in enumerate(doc.pages, 1):
                chars = page.chars or []
                fonts = {
                    str(char.get("fontname"))
                    for char in chars
                    if char.get("fontname")
                }
                page_fonts.append(fonts)
                if not chars and not (page.images or []):
                    blank_pages.append(page_no)

            if blank_pages:
                score -= min(15, len(blank_pages) * 5)
                findings.append(
                    IntegrityFinding(
                        code="BLANK_PAGES",
                        severity=FindingSeverity.WARNING,
                        message="One or more pages contain neither text-layer characters nor images.",
                        evidence={"pages": blank_pages},
                    )
                )

            if len(page_fonts) >= 2:
                common_fonts = set.intersection(
                    *(fonts for fonts in page_fonts if fonts)
                ) if all(page_fonts) else set()
                unique_font_pages = []
                for idx, fonts in enumerate(page_fonts, 1):
                    if fonts and not common_fonts and idx > 1:
                        previous = page_fonts[idx - 2]
                        if previous and fonts.isdisjoint(previous):
                            unique_font_pages.append(idx)
                if unique_font_pages:
                    score -= min(10, len(unique_font_pages) * 3)
                    findings.append(
                        IntegrityFinding(
                            code="FONT_SET_DISCONTINUITY",
                            severity=FindingSeverity.INFO,
                            message=(
                                "One or more pages use a font set disjoint from the "
                                "preceding page. This can be legitimate but warrants "
                                "review alongside bank-template expectations."
                            ),
                            evidence={"pages": unique_font_pages},
                        )
                    )

    except Exception as exc:
        return PdfIntegrityReport(
            score=0,
            status="HIGH_REVIEW",
            page_count=0,
            metadata={},
            findings=[
                IntegrityFinding(
                    code="PDF_OPEN_FAILED",
                    severity=FindingSeverity.HIGH,
                    message="The PDF could not be structurally inspected.",
                    evidence={"error": str(exc)},
                )
            ],
        )

    score = max(0, min(100, score))
    status = "LOW_CONCERN" if score >= 85 else "REVIEW" if score >= 65 else "HIGH_REVIEW"
    return PdfIntegrityReport(
        score=score,
        status=status,
        page_count=page_count,
        metadata=metadata,
        findings=findings,
    )
