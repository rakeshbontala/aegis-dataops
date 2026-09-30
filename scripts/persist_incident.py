from datetime import datetime, timezone
from pathlib import Path
import json

from engine.incident import Incident


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INCIDENT_DIR = PROJECT_ROOT / "data" / "incidents"


def main() -> None:
    incident = Incident(
        incident_id="INC-20260930-001",
        pipeline_name="customer_gold_pipeline",
        severity="P1",
        status="DETECTED",
        detected_at=datetime.now(timezone.utc),
        error_type="SCHEMA_DRIFT",
        error_message="Unexpected column detected in silver.customers: customer_segment",
        affected_assets=[
            "silver.customers",
            "customer_gold_pipeline"
        ],
        evidence=[
            {
                "type": "SCHEMA_CONTRACT",
                "expected_columns": [
                    "customer_id",
                    "customer_name",
                    "country",
                    "status"
                ],
                "actual_columns": [
                    "customer_id",
                    "customer_name",
                    "country",
                    "status",
                    "customer_segment"
                ],
                "unexpected_columns": [
                    "customer_segment"
                ]
            }
        ],
        root_cause="Source schema changed by adding customer_segment without an approved schema contract update."
    )

    INCIDENT_DIR.mkdir(parents=True, exist_ok=True)

    incident_file = INCIDENT_DIR / f"{incident.incident_id}.json"

    incident_data = {
        "incident_id": incident.incident_id,
        "pipeline_name": incident.pipeline_name,
        "severity": incident.severity,
        "status": incident.status,
        "detected_at": incident.detected_at.isoformat(),
        "error_type": incident.error_type,
        "error_message": incident.error_message,
        "affected_assets": incident.affected_assets,
        "evidence": incident.evidence,
        "root_cause": incident.root_cause,
    }

    incident_file.write_text(
        json.dumps(incident_data, indent=2),
        encoding="utf-8"
    )

    print(f"Incident saved: {incident_file}")
    print("INCIDENT PERSISTENCE PASSED")


if __name__ == "__main__":
    main()
