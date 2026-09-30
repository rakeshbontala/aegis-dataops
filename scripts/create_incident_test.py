from datetime import datetime, timezone

from engine.incident import Incident


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
            "unexpected_columns": [
                "customer_segment"
            ]
        }
    ],
    root_cause="Source schema changed by adding customer_segment without an approved schema contract update."
)

print("Incident ID:", incident.incident_id)
print("Pipeline:", incident.pipeline_name)
print("Severity:", incident.severity)
print("Status:", incident.status)
print("Error type:", incident.error_type)
print("Affected assets:", incident.affected_assets)
print("Root cause:", incident.root_cause)
print("INCIDENT MODEL TEST PASSED")
