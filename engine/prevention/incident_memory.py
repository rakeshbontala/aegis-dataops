from pathlib import Path
import json
from datetime import datetime, timezone
from typing import Any

from config.settings import settings
from engine.security.identifiers import validate_incident_id

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INCIDENTS_DIR = PROJECT_ROOT / "data" / "incidents"
HISTORICAL_DIR = PROJECT_ROOT / "data" / "historical"
DEFAULT_INCIDENT_ID = "INC-20260930-001"


def _load_matching(path: Path, incident_id: str) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if data.get("incident_id") == incident_id else {}


def record_incident_memory(incident_id: str = DEFAULT_INCIDENT_ID) -> dict[str, Any]:
    validate_incident_id(incident_id)
    incident_file = INCIDENTS_DIR / f"{incident_id}.json"
    incident = json.loads(incident_file.read_text(encoding="utf-8"))
    schema_evidence = incident.get("evidence", [{}])[0]
    unexpected_columns = schema_evidence.get("unexpected_columns", [])
    strategy_data = _load_matching(
        settings.paths.sandbox_recovery_dir / "strategies" / "recovery_strategies.json",
        incident_id,
    )
    simulation_data = _load_matching(
        settings.paths.sandbox_recovery_dir / "simulation" / "simulation_results.json",
        incident_id,
    )
    prevention_data = _load_matching(
        INCIDENTS_DIR / incident_id / "prevention.json",
        incident_id,
    )
    verification = incident.get("verification", {})

    memory = {
        "incident_id": incident["incident_id"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "incident_type": incident["error_type"],
        "pipeline": incident["pipeline_name"],
        "root_cause": incident["root_cause"],
        "affected_assets": incident["affected_assets"],
        "recovery": {
            "strategies_evaluated": strategy_data.get("strategy_count"),
            "selected_strategy": incident.get("resolution_strategy"),
            "simulation_completed": bool(simulation_data.get("simulations")),
            "human_approval_required": settings.execution_safety.human_approval_required,
            "verification_completed": verification.get("post_execution_status") == "PASSED",
            "verification_status": verification.get("post_execution_status"),
        },
        "prevention": {
            "controls_generated": prevention_data.get("prevention_control_count")
        },
        "incident_signature": {
            "error_type": incident["error_type"],
            "unexpected_columns": unexpected_columns,
        }
    }

    HISTORICAL_DIR.mkdir(parents=True, exist_ok=True)
    output_file = HISTORICAL_DIR / f"{incident['incident_id']}.json"

    output_file.write_text(
        json.dumps(memory, indent=2),
        encoding="utf-8"
    )
    return memory


def find_similar_incidents(incident_id: str) -> list[dict[str, Any]]:
    validate_incident_id(incident_id)
    current_file = HISTORICAL_DIR / f"{incident_id}.json"
    if not current_file.exists():
        return []

    current = json.loads(current_file.read_text(encoding="utf-8"))
    current_signature = current.get("incident_signature")
    matches = []
    for history_file in sorted(HISTORICAL_DIR.glob("INC-*.json")):
        candidate = json.loads(history_file.read_text(encoding="utf-8"))
        if (
            candidate.get("incident_id") != incident_id
            and current_signature
            and candidate.get("incident_signature") == current_signature
            and candidate.get("recovery", {}).get("verification_completed") is True
        ):
            matches.append(
                {
                    "incident_id": candidate.get("incident_id"),
                    "incident_type": candidate.get("incident_type"),
                    "pipeline": candidate.get("pipeline"),
                    "selected_strategy": candidate.get("recovery", {}).get("selected_strategy"),
                }
            )
    return matches


def main() -> None:
    memory = record_incident_memory()
    output_file = HISTORICAL_DIR / f"{memory['incident_id']}.json"

    print("Incident Memory:")
    print(json.dumps(memory, indent=2))
    print(f"Memory written to: {output_file}")
    print("INCIDENT MEMORY PASSED")


if __name__ == "__main__":
    main()
