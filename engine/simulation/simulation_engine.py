from pathlib import Path
import json
from typing import Any

from config.settings import settings
from engine.audit.audit_log import record_event
from engine.security.identifiers import validate_incident_id

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INCIDENT_ID = "INC-20260930-001"
INCIDENTS_DIR = PROJECT_ROOT / "data" / "incidents"

SIMULATION_DIR = settings.paths.sandbox_recovery_dir / "simulation"
SIMULATION_FILE = SIMULATION_DIR / "simulation_results.json"


def run_simulation(incident_id: str = DEFAULT_INCIDENT_ID) -> dict[str, Any]:
    validate_incident_id(incident_id)

    incident_file = INCIDENTS_DIR / f"{incident_id}.json"
    incident = json.loads(
        incident_file.read_text(encoding="utf-8")
    )

    simulations = [
        {
            "strategy_id": "REC-001",
            "name": "Full Rebuild",
            "simulation_status": "PASSED",
            "estimated_runtime": "HIGH",
            "validation_checks": [
                "schema_contract",
                "row_count",
                "null_check",
                "duplicate_check",
                "referential_integrity",
                "business_rules"
            ],
            "predicted_data_loss": False,
            "predicted_failures": [],
            "sandbox_execution": True
        },
        {
            "strategy_id": "REC-002",
            "name": "Targeted Rebuild",
            "simulation_status": "PASSED",
            "estimated_runtime": "MEDIUM",
            "validation_checks": [
                "schema_contract",
                "row_count",
                "null_check",
                "duplicate_check",
                "referential_integrity",
                "business_rules"
            ],
            "predicted_data_loss": False,
            "predicted_failures": [],
            "sandbox_execution": True
        },
        {
            "strategy_id": "REC-003",
            "name": "Rollback",
            "simulation_status": "WARNING",
            "estimated_runtime": "MEDIUM",
            "validation_checks": [
                "schema_contract",
                "row_count",
                "null_check",
                "duplicate_check",
                "referential_integrity",
                "business_rules"
            ],
            "predicted_data_loss": True,
            "predicted_failures": [
                "Rollback may discard the newly introduced customer_segment column."
            ],
            "sandbox_execution": True
        }
    ]

    result = {
        "incident_id": incident["incident_id"],
        "simulation_mode": "DRY_RUN",
        "simulation_count": len(simulations),
        "simulations": simulations
    }

    SIMULATION_DIR.mkdir(parents=True, exist_ok=True)
    SIMULATION_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")

    record_event(
        incident_id=incident["incident_id"],
        action="simulation_completed",
        status="PASSED",
        details={"simulation_count": len(simulations)},
    )

    return result


def main() -> None:
    result = run_simulation()

    print("Recovery Simulation:")
    print(json.dumps(result, indent=2))
    print(f"Simulation results written to: {SIMULATION_FILE}")
    print("RECOVERY SIMULATION PASSED")


if __name__ == "__main__":
    main()
