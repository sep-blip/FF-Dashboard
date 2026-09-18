from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .statement_parser import ParsedStatement, parse_statement_pdf


@dataclass
class BatchIngestionResult:
    statements: list[ParsedStatement] = field(default_factory=list)
    skipped_duplicates: list[str] = field(default_factory=list)


def parse_statement_batch(
    files: list[tuple[str, bytes]],
    *,
    enable_ocr: bool = False,
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
            )
        )

    return result
