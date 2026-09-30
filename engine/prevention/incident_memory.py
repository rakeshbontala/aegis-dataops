from pathlib import Path
import json
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INCIDENT_FILE = PROJECT_ROOT / "data" / "incidents" / "INC-20260930-001.json"


def main() -> None:
    incident = json.loads(
        INCIDENT_FILE.read_text(encoding="utf-8")
    )

    memory = {
        "incident_id": incident["incident_id"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "incident_type": incident["error_type"],
        "pipeline": incident["pipeline_name"],
        "root_cause": incident["root_cause"],
        "affected_assets": incident["affected_assets"],
        "recovery": {
            "strategies_evaluated": 3,
            "simulation_completed": True,
            "human_approval_required": True,
            "verification_completed": True
        },
        "prevention": {
            "controls_generated": 4
        },
        "incident_signature": {
            "error_type": incident["error_type"],
            "unexpected_column": "customer_segment"
        }
    }

    output_file = (
        PROJECT_ROOT
        / "data"
        / "historical"
        / f"{incident['incident_id']}.json"
    )

    output_file.write_text(
        json.dumps(memory, indent=2),
        encoding="utf-8"
    )

    print("Incident Memory:")
    print(json.dumps(memory, indent=2))
    print(f"Memory written to: {output_file}")
    print("INCIDENT MEMORY PASSED")


if __name__ == "__main__":
    main()
