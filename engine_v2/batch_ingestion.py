from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from .statement_parser import ParsedStatement, parse_statement_pdf


@dataclass
class BatchIngestionResult:
    statements: list[ParsedStatement] = field(default_factory=list)
    skipped_duplicates: list[str] = field(default_factory=list)


def parse_statement_batch(
    files: list[tuple[str, bytes]],
    *,
    enable_ocr: bool = False,
    vision_client: Any | None = None,
    enable_vision_fallback: bool = False,
    vision_model: str = "gpt-5.6-terra",
) -> BatchIngestionResult:
    """Parse a set of statement PDFs while skipping byte-identical duplicates."""
    seen_hashes: dict[str, str] = {}
    result = BatchIngestionResult()

    for filename, pdf_bytes in files:
        sha = hashlib.sha256(pdf_bytes).hexdigest()
        if sha in seen_hashes:
            result.skipped_duplicates.append(
                f"{filename} (duplicate of {seen_hashes[sha]})"
            )
            continue
        seen_hashes[sha] = filename
        result.statements.append(
            parse_statement_pdf(
                pdf_bytes,
                source_file=filename,
                enable_ocr=enable_ocr,
                vision_client=vision_client,
                enable_vision_fallback=enable_vision_fallback,
                vision_model=vision_model,
            )
        )

    return result
