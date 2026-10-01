"""Append-only, per-incident audit event log.

Every safety-relevant action (detection, evidence, RCA, impact, strategy
generation, risk evaluation, decision, simulation, approval, execution,
verification, prevention) should emit an event through `record_event`.

Events are stored as JSON Lines (one JSON object per line) under
`data/incidents/{incident_id}/audit_log.jsonl` so the file can be
appended to safely without re-reading/rewriting the whole history, and
can be tailed/streamed.

Never log secrets, tokens, or credentials in `details`.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings
from engine.security.identifiers import validate_incident_id

VALID_ACTIONS = {
    "incident_detected",
    "evidence_collected",
    "rca_completed",
    "lineage_calculated",
    "impact_calculated",
    "strategy_generated",
    "risk_evaluated",
    "decision_generated",
    "simulation_started",
    "simulation_completed",
    "approval_requested",
    "approval_granted",
    "approval_rejected",
    "execution_started",
    "execution_completed",
    "execution_blocked",
    "verification_started",
    "verification_completed",
    "incident_resolved",
    "prevention_generated",
    "agent_invoked",
}

_SECRET_KEY_HINTS = ("password", "token", "secret", "api_key", "apikey", "credential")


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    incident_id: str
    timestamp: str
    actor: str
    action: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)


def _audit_file(incident_id: str) -> Path:
    validate_incident_id(incident_id)
    incident_dir = settings.paths.incidents_dir / incident_id
    incident_dir.mkdir(parents=True, exist_ok=True)
    return incident_dir / "audit_log.jsonl"


def _scrub(details: dict[str, Any]) -> dict[str, Any]:
    """Drop any key that looks like it could hold a secret."""
    return {
        key: value
        for key, value in details.items()
        if not any(hint in key.lower() for hint in _SECRET_KEY_HINTS)
    }


def record_event(
    incident_id: str,
    action: str,
    status: str,
    actor: str = "AEGIS",
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append one audit event for an incident. Fails closed on bad input."""
    validate_incident_id(incident_id)

    if action not in VALID_ACTIONS:
        raise ValueError(f"Unknown audit action: {action!r}")

    if not settings.features.enable_audit_log:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            incident_id=incident_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            action=action,
            status=status,
            details=_scrub(details or {}),
        )
        return event

    event = AuditEvent(
        event_id=str(uuid.uuid4()),
        incident_id=incident_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        actor=actor,
        action=action,
        status=status,
        details=_scrub(details or {}),
    )

    audit_file = _audit_file(incident_id)
    with audit_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event.__dict__) + "\n")

    return event


def read_events(incident_id: str) -> list[dict[str, Any]]:
    """Return all recorded audit events for an incident, oldest first."""
    audit_file = _audit_file(incident_id)

    if not audit_file.exists():
        return []

    events: list[dict[str, Any]] = []
    with audit_file.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    return events
