from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from .statement_parser import ParsedStatement


ENGINE_VERSION = "underwriting-engine-v2.1"


class SourceDocumentAudit(BaseModel):
    source_file: str
    sha256: str
    statement_id: str
    bank_id: str | None = None
    page_count: int = Field(ge=0)


class AuditManifest(BaseModel):
    run_id: str
    generated_at: datetime
    engine_version: str
    classifier_model: str
    vision_model: str
    enable_ocr: bool
    enable_vision_fallback: bool
    source_documents: list[SourceDocumentAudit]


def build_audit_manifest(
    *,
    statements: list[ParsedStatement],
    classifier_model: str,
    vision_model: str,
    enable_ocr: bool,
    enable_vision_fallback: bool,
) -> AuditManifest:
    return AuditManifest(
        run_id=str(uuid4()),
        generated_at=datetime.now(timezone.utc),
        engine_version=ENGINE_VERSION,
        classifier_model=classifier_model,
        vision_model=vision_model,
        enable_ocr=enable_ocr,
        enable_vision_fallback=enable_vision_fallback,
        source_documents=[
            SourceDocumentAudit(
                source_file=statement.source_file,
                sha256=statement.file_sha256,
                statement_id=statement.statement_id,
                bank_id=statement.bank_id,
                page_count=statement.page_count,
            )
            for statement in statements
        ],
    )
