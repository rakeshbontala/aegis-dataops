from pathlib import Path
import json
from typing import Any

from engine.audit.audit_log import record_event
from engine.security.identifiers import validate_incident_id

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INCIDENT_ID = "INC-20260930-001"
INCIDENTS_DIR = PROJECT_ROOT / "data" / "incidents"


def analyze_root_cause(incident_id: str = DEFAULT_INCIDENT_ID) -> dict[str, Any]:
    validate_incident_id(incident_id)

    incident_file = INCIDENTS_DIR / f"{incident_id}.json"
    incident = json.loads(
        incident_file.read_text(encoding="utf-8")
    )

    error_type = incident["error_type"]
    evidence = incident["evidence"][0]

    if error_type == "SCHEMA_DRIFT":
        unexpected_columns = evidence["unexpected_columns"]

        root_cause = (
            "Upstream source schema changed without an approved "
            "schema contract update."
        )

        rca = {
            "incident_id": incident["incident_id"],
            "classification": "SCHEMA_CONTRACT_VIOLATION",
            "root_cause": root_cause,
            "confidence": 1.0,
            "evidence": {
                "unexpected_columns": unexpected_columns,
                "expected_columns": evidence["expected_columns"],
                "actual_columns": evidence["actual_columns"],
            },
        }
    else:
        rca = {
            "incident_id": incident["incident_id"],
            "classification": "UNKNOWN",
            "root_cause": "Unable to determine root cause.",
            "confidence": 0.0,
            "evidence": {},
        }

    record_event(
        incident_id=incident["incident_id"],
        action="rca_completed",
        status="PASSED",
        details={"classification": rca["classification"]},
    )

    return rca


def main() -> None:
    rca = analyze_root_cause()

    print("Root Cause Analysis:")
    print(json.dumps(rca, indent=2))
    print("RCA ANALYSIS PASSED")


if __name__ == "__main__":
    main()
