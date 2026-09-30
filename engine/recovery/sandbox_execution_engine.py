"""Sandbox-only recovery execution.

Fail-closed: every safety condition (authorization, matching strategy,
execution-allowed flag, sandbox artifacts present) must hold before any
file is copied. Idempotent: re-invoking for an already-executed
incident/strategy returns the existing execution record unchanged
instead of re-copying (avoids duplicate/destructive re-runs).

Production datasets (data/gold, data/silver) are never touched here.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings
from engine.audit.audit_log import record_event
from engine.security.identifiers import validate_incident_id, validate_strategy_id

DEFAULT_INCIDENT_ID = "INC-20260930-001"
DEFAULT_STRATEGY_ID = "REC-002"

AUTHORIZATION_FILE = settings.paths.sandbox_recovery_dir / "approval" / "authorization_record.json"
SOURCE_SILVER = settings.paths.sandbox_recovery_dir / "targeted_rebuild" / "customers_silver"
SOURCE_GOLD = settings.paths.sandbox_recovery_dir / "targeted_rebuild" / "customer_summary_gold"
EXECUTION_ROOT = settings.paths.sandbox_recovery_dir / "executed" / DEFAULT_STRATEGY_ID
OUTPUT_SILVER = EXECUTION_ROOT / "customers_silver"
OUTPUT_GOLD = EXECUTION_ROOT / "customer_summary_gold"
EXECUTION_RECORD = settings.paths.sandbox_recovery_dir / "approval" / "execution_record.json"


class ExecutionBlockedError(Exception):
    """Raised when a fail-closed safety condition is not satisfied."""


def _already_executed(incident_id: str, strategy_id: str) -> dict[str, Any] | None:
    if not EXECUTION_RECORD.exists():
        return None

    existing = json.loads(EXECUTION_RECORD.read_text(encoding="utf-8"))
    if (
        existing.get("incident_id") == incident_id
        and existing.get("strategy_id") == strategy_id
        and existing.get("execution_status") == "EXECUTED_SANDBOX"
        and EXECUTION_ROOT.exists()
    ):
        return existing
    return None


def execute_recovery(
    incident_id: str = DEFAULT_INCIDENT_ID,
    strategy_id: str = DEFAULT_STRATEGY_ID,
) -> dict[str, Any]:
    validate_incident_id(incident_id)
    validate_strategy_id(strategy_id)

    # Idempotency check first: never re-copy an already-executed recovery.
    existing = _already_executed(incident_id, strategy_id)
    if existing is not None:
        return {**existing, "idempotent": True}

    if not AUTHORIZATION_FILE.exists():
        raise ExecutionBlockedError("No authorization record found.")

    authorization = json.loads(AUTHORIZATION_FILE.read_text(encoding="utf-8"))

    if authorization.get("incident_id") != incident_id:
        raise ExecutionBlockedError("Authorization does not match the requested incident.")

    if authorization.get("strategy_id") != strategy_id:
        raise ExecutionBlockedError("Authorization does not match the requested strategy.")

    if authorization.get("authorization_status") != "AUTHORIZED":
        raise ExecutionBlockedError("Recovery is not authorized.")

    if not authorization.get("safety_checks", {}).get("execution_allowed"):
        raise ExecutionBlockedError("Execution safety check failed.")

    if "SANDBOX_ONLY" not in settings.execution_safety.allowlisted_execution_scopes:
        raise ExecutionBlockedError("SANDBOX_ONLY execution scope is not allowlisted by policy.")

    if not SOURCE_SILVER.exists():
        raise ExecutionBlockedError(f"Sandbox Silver output not found: {SOURCE_SILVER}")

    if not SOURCE_GOLD.exists():
        raise ExecutionBlockedError(f"Sandbox Gold output not found: {SOURCE_GOLD}")

    record_event(
        incident_id=incident_id,
        action="execution_started",
        status="IN_PROGRESS",
        actor=authorization["authorized_by"],
        details={"strategy_id": strategy_id},
    )

    if EXECUTION_ROOT.exists():
        shutil.rmtree(EXECUTION_ROOT)

    EXECUTION_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE_SILVER, OUTPUT_SILVER)
    shutil.copytree(SOURCE_GOLD, OUTPUT_GOLD)

    record = {
        "incident_id": incident_id,
        "strategy_id": strategy_id,
        "strategy_name": authorization["strategy_name"],
        "execution_status": "EXECUTED_SANDBOX",
        "executed_by": authorization["authorized_by"],
        "authorized_at": authorization["authorized_at"],
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "execution_scope": "SANDBOX_ONLY",
        "production_modified": False,
        "source_silver": str(SOURCE_SILVER),
        "source_gold": str(SOURCE_GOLD),
        "executed_silver": str(OUTPUT_SILVER),
        "executed_gold": str(OUTPUT_GOLD),
    }

    EXECUTION_RECORD.parent.mkdir(parents=True, exist_ok=True)
    EXECUTION_RECORD.write_text(json.dumps(record, indent=2), encoding="utf-8")

    record_event(
        incident_id=incident_id,
        action="execution_completed",
        status="PASSED",
        actor=authorization["authorized_by"],
        details={
            "strategy_id": strategy_id,
            "execution_scope": record["execution_scope"],
            "production_modified": record["production_modified"],
        },
    )

    return {**record, "idempotent": False}


def main() -> None:
    try:
        record = execute_recovery()
    except ExecutionBlockedError as error:
        print(f"EXECUTION BLOCKED: {error}")
        raise SystemExit(1)

    if record.get("idempotent"):
        print("EXECUTION ALREADY COMPLETED - NO ACTION TAKEN (idempotent)")
    else:
        print("SANDBOX RECOVERY EXECUTED")

    print(json.dumps(record, indent=2))
    print("PRODUCTION MODIFIED: FALSE")
    print(f"Execution record saved to: {EXECUTION_RECORD}")


if __name__ == "__main__":
    main()
