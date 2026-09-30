from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INCIDENT_FILE = (
    PROJECT_ROOT
    / "data"
    / "incidents"
    / "INC-20260930-001.json"
)

APPROVAL_FILE = (
    PROJECT_ROOT
    / "data"
    / "sandbox"
    / "recovery"
    / "approval"
    / "approval_request.json"
)

VERIFICATION_FILE = (
    PROJECT_ROOT
    / "data"
    / "sandbox"
    / "recovery"
    / "verification"
    / "recovery_verification.json"
)


def main() -> None:
    incident = json.loads(
        INCIDENT_FILE.read_text(encoding="utf-8")
    )

    approval = json.loads(
        APPROVAL_FILE.read_text(encoding="utf-8")
    )

    verification = json.loads(
        VERIFICATION_FILE.read_text(encoding="utf-8")
    )

    checks = {
        "incident_match": (
            approval.get("incident_id")
            == incident.get("incident_id")
        ),
        "strategy_match": (
            approval.get("requested_strategy", {}).get("strategy_id")
            == "REC-002"
        ),
        "verification_passed": (
            verification.get("verification_status") == "PASSED"
        ),
        "approval_status": (
            approval.get("approval_status") == "APPROVED"
        ),
        "approved_by_present": bool(
            approval.get("approved_by")
        ),
        "execution_allowed": (
            approval.get("execution_allowed") is True
        ),
    }

    execution_allowed = all(checks.values())

    if not execution_allowed:
        result = {
            "incident_id": incident["incident_id"],
            "strategy_id": approval.get(
                "requested_strategy", {}
            ).get("strategy_id"),
            "execution_status": "BLOCKED",
            "execution_allowed": False,
            "safety_checks": checks,
            "reason": (
                "Recovery execution is blocked because every "
                "safety condition has not been satisfied."
            ),
        }

        print("Recovery Execution:")
        print(json.dumps(result, indent=2))
        print("RECOVERY EXECUTION SAFETY CHECK PASSED")
        return

    result = {
        "incident_id": incident["incident_id"],
        "strategy_id": approval["requested_strategy"]["strategy_id"],
        "execution_status": "EXECUTION_AUTHORIZED",
        "execution_allowed": True,
        "approved_by": approval["approved_by"],
        "safety_checks": checks,
    }

    print("Recovery Execution:")
    print(json.dumps(result, indent=2))
    print("RECOVERY EXECUTION AUTHORIZED")


if __name__ == "__main__":
    main()
