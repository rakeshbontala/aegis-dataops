from pathlib import Path
import json
from typing import Any

from engine.audit.audit_log import record_event
from engine.security.identifiers import validate_incident_id

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INCIDENT_ID = "INC-20260930-001"
INCIDENTS_DIR = PROJECT_ROOT / "data" / "incidents"

STRATEGY_DIR = (
    PROJECT_ROOT
    / "data"
    / "sandbox"
    / "recovery"
    / "strategies"
)

STRATEGY_FILE = STRATEGY_DIR / "recovery_strategies.json"


def generate_strategies(incident_id: str = DEFAULT_INCIDENT_ID) -> dict[str, Any]:
    validate_incident_id(incident_id)

    incident_file = INCIDENTS_DIR / f"{incident_id}.json"
    incident = json.loads(
        incident_file.read_text(encoding="utf-8")
    )

    strategies = [
        {
            "strategy_id": "REC-001",
            "name": "Full Rebuild",
            "description": "Rebuild all downstream customer data assets from the source.",
            "scope": [
                "bronze.customers",
                "silver.customers",
                "customer_gold_pipeline",
                "gold.customer_summary"
            ],
            "risk_level": "HIGH",
            "runtime_class": "HIGH",
            "data_loss_risk": "LOW",
            "requires_validation": True,
            "human_approval_required": True
        },
        {
            "strategy_id": "REC-002",
            "name": "Targeted Rebuild",
            "description": "Rebuild only the affected downstream customer assets.",
            "scope": [
                "silver.customers",
                "customer_gold_pipeline",
                "gold.customer_summary"
            ],
            "risk_level": "MEDIUM",
            "runtime_class": "MEDIUM",
            "data_loss_risk": "LOW",
            "requires_validation": True,
            "human_approval_required": True
        },
        {
            "strategy_id": "REC-003",
            "name": "Rollback",
            "description": "Restore the previous known-good source schema and regenerate affected assets.",
            "scope": [
                "raw.customers",
                "bronze.customers",
                "silver.customers",
                "customer_gold_pipeline",
                "gold.customer_summary"
            ],
            "risk_level": "MEDIUM",
            "runtime_class": "MEDIUM",
            "data_loss_risk": "MEDIUM",
            "requires_validation": True,
            "human_approval_required": True
        }
    ]

    result = {
        "incident_id": incident["incident_id"],
        "strategy_count": len(strategies),
        "recovery_strategies": strategies
    }

    STRATEGY_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    STRATEGY_FILE.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8"
    )

    record_event(
        incident_id=incident["incident_id"],
        action="strategy_generated",
        status="PASSED",
        details={"strategy_count": len(strategies)},
    )

    return result


def main() -> None:
    result = generate_strategies()

    print("Recovery Strategies:")
    print(json.dumps(result, indent=2))
    print(f"Recovery strategies written to: {STRATEGY_FILE}")
    print("RECOVERY STRATEGY GENERATION PASSED")


if __name__ == "__main__":
    main()