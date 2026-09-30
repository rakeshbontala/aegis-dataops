from pathlib import Path
import json
from typing import Any

from config.settings import settings
from engine.audit.audit_log import record_event
from engine.security.identifiers import validate_incident_id

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INCIDENT_ID = "INC-20260930-001"
INCIDENTS_DIR = PROJECT_ROOT / "data" / "incidents"

IMPACT_DIR = settings.paths.sandbox_recovery_dir / "impact"
IMPACT_FILE = IMPACT_DIR / "impact_analysis.json"

# Business criticality/impact knowledge base for known downstream assets.
IMPACT_MAP = {
    "customer_gold_pipeline": {
        "asset_type": "PIPELINE",
        "criticality": "HIGH",
        "impact_level": "HIGH",
        "reason": "Direct downstream dependency of silver.customers."
    },
    "gold.customer_summary": {
        "asset_type": "GOLD_DATASET",
        "criticality": "HIGH",
        "impact_level": "HIGH",
        "reason": "Produced by the affected customer_gold_pipeline."
    }
}


def analyze_impact(incident_id: str = DEFAULT_INCIDENT_ID) -> dict[str, Any]:
    validate_incident_id(incident_id)

    incident_file = INCIDENTS_DIR / f"{incident_id}.json"
    incident = json.loads(incident_file.read_text(encoding="utf-8"))

    impacted_assets = [
        {"asset": asset_name, **details}
        for asset_name, details in IMPACT_MAP.items()
    ]

    result = {
        "incident_id": incident["incident_id"],
        "starting_asset": "silver.customers",
        "impact_count": len(impacted_assets),
        "impacted_assets": impacted_assets
    }

    IMPACT_DIR.mkdir(parents=True, exist_ok=True)
    IMPACT_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")

    record_event(
        incident_id=incident["incident_id"],
        action="impact_calculated",
        status="PASSED",
        details={"impact_count": len(impacted_assets)},
    )

    return result


def main() -> None:
    result = analyze_impact()

    print("Blast Radius Analysis:")
    print(json.dumps(result, indent=2))
    print(f"Impact analysis written to: {IMPACT_FILE}")
    print("IMPACT ANALYSIS PASSED")


if __name__ == "__main__":
    main()
