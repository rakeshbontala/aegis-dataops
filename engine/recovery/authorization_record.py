"""Authorization audit record.

Re-derives whether execution is authorized from the current approval and
verification artifacts (fail-closed: any missing/failed check blocks
authorization). Preserves a prior EXECUTED_SANDBOX execution_status so
re-running this stage after execution does not make execution look
re-runnable (sandbox_execution_engine also idempotency-checks independently).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings
from engine.security.identifiers import validate_incident_id, validate_strategy_id

APPROVAL_FILE = settings.paths.sandbox_recovery_dir / "approval" / "approval_request.json"
VERIFICATION_FILE = settings.paths.sandbox_recovery_dir / "verification" / "recovery_verification.json"
OUTPUT_FILE = settings.paths.sandbox_recovery_dir / "approval" / "authorization_record.json"
EXECUTION_RECORD_FILE = settings.paths.sandbox_recovery_dir / "approval" / "execution_record.json"


def authorize(
    incident_id: str = "INC-20260930-001",
    strategy_id: str = "REC-002",
) -> dict[str, Any]:
    validate_incident_id(incident_id)
    validate_strategy_id(strategy_id)

    approval = json.loads(APPROVAL_FILE.read_text(encoding="utf-8"))
    verification = json.loads(VERIFICATION_FILE.read_text(encoding="utf-8"))

    required_checks = {
        "incident_match": approval["incident_id"] == incident_id,
        "strategy_match": approval["requested_strategy"]["strategy_id"] == strategy_id,
        "verification_passed": verification["verification_status"] == "PASSED",
        "approval_status": approval["approval_status"] == "APPROVED",
        "approved_by_present": bool(approval["approved_by"]),
        "execution_allowed": approval["execution_allowed"] is True,
    }

    authorization_allowed = all(required_checks.values())

    execution_status = "NOT_EXECUTED"
    if EXECUTION_RECORD_FILE.exists():
        existing_execution = json.loads(EXECUTION_RECORD_FILE.read_text(encoding="utf-8"))
        if (
            existing_execution.get("incident_id") == incident_id
            and existing_execution.get("strategy_id") == strategy_id
            and existing_execution.get("execution_status") == "EXECUTED_SANDBOX"
        ):
            execution_status = "EXECUTED_SANDBOX"

    authorization_status = "AUTHORIZED" if authorization_allowed else "BLOCKED"

    # Idempotency: if nothing meaningful changed since the last authorization
    # record, return it unchanged instead of regenerating authorized_at.
    if OUTPUT_FILE.exists():
        existing_record = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        if (
            existing_record.get("incident_id") == incident_id
            and existing_record.get("strategy_id") == strategy_id
            and existing_record.get("authorization_status") == authorization_status
            and existing_record.get("execution_status") == execution_status
            and existing_record.get("safety_checks") == required_checks
            and existing_record.get("approved_at") == approval.get("approved_at")
        ):
            return existing_record

    record = {
        "incident_id": approval["incident_id"],
        "strategy_id": approval["requested_strategy"]["strategy_id"],
        "strategy_name": approval["requested_strategy"]["name"],
        "authorization_status": authorization_status,
        "authorized_by": approval["approved_by"],
        "approved_at": approval.get("approved_at"),
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "verification_status": verification["verification_status"],
        "safety_checks": required_checks,
        "execution_status": execution_status,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(record, indent=2), encoding="utf-8")

    return record


def main() -> None:
    record = authorize()

    print("AUTHORIZATION AUDIT RECORD CREATED")
    print(json.dumps(record, indent=2))
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

