from pathlib import Path
import json
from datetime import datetime, timezone
from typing import Any

from engine.audit.audit_log import record_event
from engine.security.identifiers import validate_incident_id

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INCIDENT_ID = "INC-20260930-001"
INCIDENTS_DIR = PROJECT_ROOT / "data" / "incidents"


def generate_prevention(incident_id: str = DEFAULT_INCIDENT_ID) -> dict[str, Any]:
    validate_incident_id(incident_id)

    incident_file = INCIDENTS_DIR / f"{incident_id}.json"
    incident = json.loads(
        incident_file.read_text(encoding="utf-8")
    )

    prevention_controls = [
        {
            "control_id": "PREV-001",
            "name": "Schema Contract Enforcement",
            "type": "PREVENTION",
            "description": (
                "Reject unexpected source columns unless the schema "
                "contract is explicitly updated."
            ),
            "trigger": "Schema contract violation",
            "enabled": True
        },
        {
            "control_id": "PREV-002",
            "name": "Schema Compatibility Test",
            "type": "TEST",
            "description": (
                "Validate source and downstream schema compatibility "
                "before pipeline execution."
            ),
            "trigger": "Pipeline deployment",
            "enabled": True
        },
        {
            "control_id": "PREV-003",
            "name": "Schema Drift Alert",
            "type": "MONITORING",
            "description": (
                "Generate an alert when a source dataset changes "
                "without an approved contract update."
            ),
            "trigger": "Runtime schema inspection",
            "enabled": True
        },
        {
            "control_id": "PREV-004",
            "name": "Deployment Gate",
            "type": "GOVERNANCE",
            "description": (
                "Block deployment when schema compatibility validation fails."
            ),
            "trigger": "CI/CD pipeline",
            "enabled": True
        }
    ]

    result = {
        "incident_id": incident["incident_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "based_on_root_cause": incident.get("root_cause"),
        "prevention_control_count": len(prevention_controls),
        "prevention_controls": prevention_controls
    }

    incident_dir = INCIDENTS_DIR / incident["incident_id"]
    incident_dir.mkdir(parents=True, exist_ok=True)
    prevention_file = incident_dir / "prevention.json"
    prevention_file.write_text(json.dumps(result, indent=2), encoding="utf-8")

    record_event(
        incident_id=incident["incident_id"],
        action="prevention_generated",
        status="PASSED",
        details={"prevention_control_count": len(prevention_controls)},
    )

    return result


def main() -> None:
    result = generate_prevention()
    incident_dir = INCIDENTS_DIR / result["incident_id"]

    print("Prevention Controls:")
    print(json.dumps(result, indent=2))
    print(f"Prevention recommendations written to: {incident_dir / 'prevention.json'}")
    print("PREVENTION ANALYSIS PASSED")


if __name__ == "__main__":
    main()
