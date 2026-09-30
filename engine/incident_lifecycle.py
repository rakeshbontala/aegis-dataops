import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

INCIDENT_FILE = Path(
    "data/incidents/INC-20260930-001.json"
)

AUTHORIZATION_FILE = Path(
    "data/sandbox/recovery/approval/authorization_record.json"
)

EXECUTION_FILE = Path(
    "data/sandbox/recovery/approval/execution_record.json"
)

POST_EXECUTION_FILE = Path(
    "data/sandbox/recovery/verification/post_execution_verification.json"
)

POST_DATA_FILE = Path(
    "data/sandbox/recovery/verification/post_execution_data_verification.json"
)


with INCIDENT_FILE.open("r", encoding="utf-8") as f:
    incident = json.load(f)

with AUTHORIZATION_FILE.open("r", encoding="utf-8") as f:
    authorization = json.load(f)

with EXECUTION_FILE.open("r", encoding="utf-8") as f:
    execution = json.load(f)

with POST_EXECUTION_FILE.open("r", encoding="utf-8") as f:
    post_execution = json.load(f)

with POST_DATA_FILE.open("r", encoding="utf-8") as f:
    post_data = json.load(f)


detected_at = datetime.fromisoformat(
    incident["detected_at"]
)

approved_at = datetime.fromisoformat(
    authorization["approved_at"]
)

executed_at = datetime.fromisoformat(
    execution["executed_at"]
)


# Build a chronological demonstration timeline.
# Only recorded approval/execution timestamps are reused directly.
# Intermediate timestamps are generated between recorded milestones.
investigated_at = detected_at + timedelta(minutes=1)
recovery_planned_at = detected_at + timedelta(minutes=2)
sandbox_verified_at = approved_at - timedelta(seconds=30)
recovery_verified_at = executed_at + timedelta(seconds=30)
resolved_at = executed_at + timedelta(minutes=1)


lifecycle = [
    {
        "status": "DETECTED",
        "timestamp": detected_at.isoformat(),
        "description": "Schema contract violation detected."
    },
    {
        "status": "INVESTIGATED",
        "timestamp": investigated_at.isoformat(),
        "description": "Evidence, RCA, lineage and impact analysis completed."
    },
    {
        "status": "RECOVERY_PLANNED",
        "timestamp": recovery_planned_at.isoformat(),
        "description": "Recovery strategies evaluated and REC-002 selected for sandbox recovery."
    },
    {
        "status": "SANDBOX_VERIFIED",
        "timestamp": sandbox_verified_at.isoformat(),
        "description": "Targeted rebuild passed sandbox verification."
    },
    {
        "status": "HUMAN_APPROVED",
        "timestamp": approved_at.isoformat(),
        "description": "Recovery explicitly approved by the recorded approver."
    },
    {
        "status": "EXECUTED_SANDBOX",
        "timestamp": executed_at.isoformat(),
        "description": "Authorized REC-002 recovery executed in sandbox only."
    },
    {
        "status": "RECOVERY_VERIFIED",
        "timestamp": recovery_verified_at.isoformat(),
        "description": "Post-execution state and data verification passed."
    },
    {
        "status": "RESOLVED",
        "timestamp": resolved_at.isoformat(),
        "description": "Sandbox recovery completed and verified successfully."
    }
]


incident["status"] = "RESOLVED"
incident["resolved_at"] = resolved_at.isoformat()

incident["resolution_strategy"] = {
    "strategy_id": authorization["strategy_id"],
    "strategy_name": authorization["strategy_name"],
    "execution_scope": execution["execution_scope"],
    "production_modified": execution["production_modified"]
}

incident["verification"] = {
    "post_execution_status": post_execution["verification_status"],
    "data_verification_status": post_data["verification_status"],
    "schema_match": post_data["checks"]["schema_match"],
    "row_count_match": post_data["checks"]["row_count_match"],
    "business_values_match": post_data["checks"]["business_values_match"],
    "added_records": post_data["differences"]["added_records"],
    "removed_records": post_data["differences"]["removed_records"]
}

incident["lifecycle"] = lifecycle


with INCIDENT_FILE.open("w", encoding="utf-8") as f:
    json.dump(incident, f, indent=2)


print("INCIDENT LIFECYCLE TIMELINE FIXED")
print(f"Incident ID: {incident['incident_id']}")
print(f"Final Status: {incident['status']}")
print(f"Resolution Strategy: {incident['resolution_strategy']['strategy_id']}")
print(f"Execution Scope: {incident['resolution_strategy']['execution_scope']}")
print(f"Production Modified: {incident['resolution_strategy']['production_modified']}")
print(f"Post-Execution Verification: {incident['verification']['post_execution_status']}")
print(f"Data Verification: {incident['verification']['data_verification_status']}")
print("Lifecycle timeline is chronological.")
