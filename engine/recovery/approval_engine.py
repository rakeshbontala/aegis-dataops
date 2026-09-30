from pathlib import Path
import json
from typing import Any

from engine.audit.audit_log import record_event

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INCIDENT_FILE = (
    PROJECT_ROOT
    / "data"
    / "incidents"
    / "INC-20260930-001.json"
)

VERIFICATION_FILE = (
    PROJECT_ROOT
    / "data"
    / "sandbox"
    / "recovery"
    / "verification"
    / "recovery_verification.json"
)

APPROVAL_OUTPUT = (
    PROJECT_ROOT
    / "data"
    / "sandbox"
    / "recovery"
    / "approval"
    / "approval_request.json"
)


def request_approval() -> dict[str, Any]:
    incident = json.loads(
        INCIDENT_FILE.read_text(encoding="utf-8")
    )

    # Idempotency: if a request for this incident/strategy has already been
    # approved, do not regress it back to PENDING on a re-run.
    if APPROVAL_OUTPUT.exists():
        existing = json.loads(APPROVAL_OUTPUT.read_text(encoding="utf-8"))
        if (
            existing.get("incident_id") == incident["incident_id"]
            and existing.get("requested_strategy", {}).get("strategy_id") == "REC-002"
            and existing.get("approval_status") == "APPROVED"
        ):
            return existing

    verification = json.loads(
        VERIFICATION_FILE.read_text(encoding="utf-8")
    )

    verification_passed = (
        verification.get("verification_status") == "PASSED"
    )

    approval_allowed = verification_passed

    approval_request = {
        "incident_id": incident["incident_id"],
        "requested_strategy": {
            "strategy_id": "REC-002",
            "name": "Targeted Rebuild",
        },
        "approval_status": "PENDING",
        "requested_by": "AEGIS",
        "approved_by": None,
        "approval_required": True,
        "approval_reason": (
            "Recovery execution requires explicit human approval "
            "after risk evaluation, simulation, and sandbox verification."
        ),
        "simulation_completed": True,
        "risk_evaluation_completed": True,
        "sandbox_verification": {
            "status": verification.get("verification_status"),
            "schema_match": verification["checks"]["schema_match"],
            "row_count_match": verification["checks"]["row_count_match"],
            "business_values_match": verification["checks"]["business_values_match"],
        },
        "approval_allowed": approval_allowed,
        "execution_allowed": False,
    }

    APPROVAL_OUTPUT.write_text(
        json.dumps(approval_request, indent=2),
        encoding="utf-8",
    )

    record_event(
        incident_id=incident["incident_id"],
        action="approval_requested",
        status="PASSED" if approval_allowed else "BLOCKED",
        details={"strategy_id": "REC-002"},
    )

    return approval_request


def main() -> None:
    approval_request = request_approval()

    print("Human Approval Request:")
    print(json.dumps(approval_request, indent=2))

    if approval_request.get("approval_status") == "APPROVED":
        print("APPROVAL ALREADY GRANTED - REQUEST UNCHANGED")
        return

    print(f"\nApproval request saved to: {APPROVAL_OUTPUT}")

    if approval_request["approval_allowed"]:
        print("SANDBOX VERIFICATION PASSED")
        print("HUMAN APPROVAL GATE READY")
    else:
        print("SANDBOX VERIFICATION FAILED")
        print("HUMAN APPROVAL BLOCKED")


if __name__ == "__main__":
    main()
