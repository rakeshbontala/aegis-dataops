from pathlib import Path
import json
from typing import Any

from config.settings import settings
from engine.audit.audit_log import record_event
from engine.security.identifiers import validate_incident_id

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INCIDENT_ID = "INC-20260930-001"
INCIDENTS_DIR = PROJECT_ROOT / "data" / "incidents"

LINEAGE_DIR = settings.paths.sandbox_recovery_dir / "lineage"
LINEAGE_FILE = LINEAGE_DIR / "lineage_analysis.json"

# Known asset dependency graph for the customer data pipeline.
LINEAGE_GRAPH = {
    "raw.customers": {
        "downstream": ["bronze.customers"]
    },
    "bronze.customers": {
        "downstream": ["silver.customers"]
    },
    "silver.customers": {
        "downstream": ["customer_gold_pipeline"]
    },
    "customer_gold_pipeline": {
        "downstream": ["gold.customer_summary"]
    },
    "gold.customer_summary": {
        "downstream": []
    }
}


def analyze_lineage(incident_id: str = DEFAULT_INCIDENT_ID) -> dict[str, Any]:
    validate_incident_id(incident_id)

    incident_file = INCIDENTS_DIR / f"{incident_id}.json"
    incident = json.loads(incident_file.read_text(encoding="utf-8"))

    start_asset = "silver.customers"
    impacted_assets: list[str] = []
    queue = [start_asset]
    visited: set[str] = set()

    while queue:
        asset = queue.pop(0)

        if asset in visited:
            continue

        visited.add(asset)

        for downstream in LINEAGE_GRAPH.get(asset, {}).get("downstream", []):
            impacted_assets.append(downstream)
            queue.append(downstream)

    result = {
        "incident_id": incident["incident_id"],
        "starting_asset": start_asset,
        "impacted_assets": impacted_assets,
        "blast_radius_depth": len(impacted_assets),
    }

    LINEAGE_DIR.mkdir(parents=True, exist_ok=True)
    LINEAGE_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")

    record_event(
        incident_id=incident["incident_id"],
        action="lineage_calculated",
        status="PASSED",
        details={"blast_radius_depth": len(impacted_assets)},
    )

    return result


def main() -> None:
    result = analyze_lineage()

    print("Lineage / Blast Radius Candidates:")
    print(json.dumps(result, indent=2))
    print(f"Lineage analysis written to: {LINEAGE_FILE}")
    print("LINEAGE ANALYSIS PASSED")


if __name__ == "__main__":
    main()
