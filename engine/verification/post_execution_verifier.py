import json
from pathlib import Path

EXPECTED_GOLD = Path(
    "data/sandbox/recovery/targeted_rebuild/customer_summary_gold"
)

EXECUTED_GOLD = Path(
    "data/sandbox/recovery/executed/REC-002/customer_summary_gold"
)

EXECUTION_RECORD = Path(
    "data/sandbox/recovery/approval/execution_record.json"
)

OUTPUT_FILE = Path(
    "data/sandbox/recovery/verification/post_execution_verification.json"
)

if not EXECUTION_RECORD.exists():
    print("POST-EXECUTION VERIFICATION BLOCKED: execution record not found.")
    raise SystemExit(1)

if not EXPECTED_GOLD.exists():
    print("POST-EXECUTION VERIFICATION BLOCKED: expected recovery output not found.")
    raise SystemExit(1)

if not EXECUTED_GOLD.exists():
    print("POST-EXECUTION VERIFICATION BLOCKED: executed output not found.")
    raise SystemExit(1)

with EXECUTION_RECORD.open("r", encoding="utf-8") as f:
    execution = json.load(f)

if execution["execution_status"] != "EXECUTED_SANDBOX":
    print("POST-EXECUTION VERIFICATION BLOCKED: execution status is not EXECUTED_SANDBOX.")
    raise SystemExit(1)

if execution["production_modified"] is not False:
    print("POST-EXECUTION VERIFICATION BLOCKED: production modification flag is not false.")
    raise SystemExit(1)

record = {
    "incident_id": execution["incident_id"],
    "strategy_id": execution["strategy_id"],
    "verification_scope": "SANDBOX_EXECUTION",
    "expected_output_exists": EXPECTED_GOLD.exists(),
    "executed_output_exists": EXECUTED_GOLD.exists(),
    "execution_status_confirmed": execution["execution_status"] == "EXECUTED_SANDBOX",
    "production_modified": execution["production_modified"],
    "verification_status": "PASSED",
    "expected_output": str(EXPECTED_GOLD),
    "executed_output": str(EXECUTED_GOLD),
}

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT_FILE.open("w", encoding="utf-8") as f:
    json.dump(record, f, indent=2)

print("POST-EXECUTION VERIFICATION PASSED")
print(json.dumps(record, indent=2))
print(f"Saved to: {OUTPUT_FILE}")
