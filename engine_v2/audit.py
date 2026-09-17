from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .models import AuditEvent


def build_audit_event(
    *,
    event_type: str,
    entity_type: str,
    entity_id: str,
    actor: str = "system",
    payload: dict | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_id=str(uuid4()),
        occurred_at=datetime.now(timezone.utc),
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        payload=payload or {},
    )
