from pathlib import Path
import json
from typing import Any

from engine.audit.audit_log import record_event
from engine.security.identifiers import validate_incident_id

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INCIDENT_ID = "INC-20260930-001"
INCIDENTS_DIR = PROJECT_ROOT / "data" / "incidents"


def collect_evidence(incident_id: str = DEFAULT_INCIDENT_ID) -> dict[str, Any]:
    validate_incident_id(incident_id)

    incident_file = INCIDENTS_DIR / f"{incident_id}.json"
    incident = json.loads(
        incident_file.read_text(encoding="utf-8")
    )

    evidence = {
        "incident_id": incident["incident_id"],
        "pipeline_name": incident["pipeline_name"],
        "error_type": incident["error_type"],
        "affected_assets": incident["affected_assets"],
        "schema_contract_evidence": incident["evidence"],
        "root_cause": incident["root_cause"],
    }

    record_event(
        incident_id=incident["incident_id"],
        action="evidence_collected",
        status="PASSED",
    )

    return evidence


def main() -> None:
    evidence = collect_evidence()

    print("Evidence collected:")
    print(json.dumps(evidence, indent=2))
    print("EVIDENCE COLLECTION PASSED")


if __name__ == "__main__":
    main()

