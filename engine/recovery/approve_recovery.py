"""Human approval decision for a proposed recovery strategy.

Fail-closed: approval can only be granted if the prior sandbox
verification passed (`approval_allowed` was already computed by
`engine.recovery.approval_engine`). Idempotent: approving an
already-approved request is a no-op; a rejected request cannot be
silently re-approved.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings
from engine.audit.audit_log import record_event
from engine.security.identifiers import (
    validate_actor_name,
    validate_incident_id,
    validate_strategy_id,
)

APPROVAL_FILE = settings.paths.sandbox_recovery_dir / "approval" / "approval_request.json"
DEFAULT_APPROVER = "Rakesh Bontala"


class ApprovalError(Exception):
    """Raised when an approval decision cannot be safely applied."""


def decide_approval(
    incident_id: str = "INC-20260930-001",
    strategy_id: str = "REC-002",
    decision: str = "APPROVE",
    approver: str = DEFAULT_APPROVER,
) -> dict[str, Any]:
    validate_incident_id(incident_id)
    validate_strategy_id(strategy_id)
    validate_actor_name(approver)

    if decision not in {"APPROVE", "REJECT"}:
        raise ApprovalError(f"Invalid decision: {decision!r}")

    if not APPROVAL_FILE.exists():
        raise ApprovalError("No approval request found. Run the approval stage first.")

    approval = json.loads(APPROVAL_FILE.read_text(encoding="utf-8"))

    if approval.get("incident_id") != incident_id:
        raise ApprovalError("Approval request does not match the requested incident.")

    if approval.get("requested_strategy", {}).get("strategy_id") != strategy_id:
        raise ApprovalError("Approval request does not match the requested strategy.")

    if approval.get("approval_status") == "APPROVED":
        record_event(
            incident_id=incident_id,
            action="approval_granted",
            status="PASSED",
            actor=approval.get("approved_by") or "AEGIS",
            details={"strategy_id": strategy_id, "idempotent": True},
        )
        return approval  # idempotent no-op

    if approval.get("approval_status") == "REJECTED":
        raise ApprovalError(
            "Recovery has already been rejected; a new approval request is required."
        )

    if decision == "REJECT":
        approval["approval_status"] = "REJECTED"
        approval["approved_by"] = approver
        approval["approved_at"] = datetime.now(timezone.utc).isoformat()
        approval["execution_allowed"] = False

        APPROVAL_FILE.write_text(json.dumps(approval, indent=2), encoding="utf-8")

        record_event(
            incident_id=incident_id,
            action="approval_rejected",
            status="REJECTED",
            actor=approver,
            details={"strategy_id": strategy_id},
        )
        return approval

    if not approval.get("approval_allowed"):
        record_event(
            incident_id=incident_id,
            action="approval_rejected",
            status="BLOCKED",
            actor=approver,
            details={"reason": "sandbox verification has not passed"},
        )
        raise ApprovalError("Approval blocked: sandbox verification has not passed.")

    approval["approval_status"] = "APPROVED"
    approval["approved_by"] = approver
    approval["approved_at"] = datetime.now(timezone.utc).isoformat()
    approval["execution_allowed"] = True

    APPROVAL_FILE.write_text(json.dumps(approval, indent=2), encoding="utf-8")

    record_event(
        incident_id=incident_id,
        action="approval_granted",
        status="PASSED",
        actor=approver,
        details={"strategy_id": strategy_id},
    )

    return approval


def main() -> None:
    try:
        approval = decide_approval()
    except ApprovalError as error:
        print(f"APPROVAL BLOCKED: {error}")
        raise SystemExit(1)

    print("HUMAN APPROVAL RECORDED")
    print(f"Approved by: {approval['approved_by']}")
    print(f"Approved at: {approval['approved_at']}")
    print(f"Strategy: {approval['requested_strategy']}")
    print(f"Execution allowed: {approval['execution_allowed']}")


if __name__ == "__main__":
    main()

