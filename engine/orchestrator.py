from pathlib import Path
import json
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INCIDENT_ID = "INC-20260930-001"


def run_engine(module_name: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", module_name],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Engine failed: {module_name}\n"
            f"{result.stdout}\n"
            f"{result.stderr}"
        )

    return result.stdout


def main() -> None:
    stages = [
        ("Detection", "engine.detection.schema_drift_detector"),
        ("Evidence", "engine.evidence.evidence_collector"),
        ("RCA", "engine.rca.rca_engine"),
        ("Lineage", "engine.lineage.lineage_engine"),
        ("Impact", "engine.impact.impact_engine"),
        ("Recovery", "engine.recovery.recovery_engine"),
        ("Risk", "engine.risk.risk_engine"),
        ("Decision", "engine.recovery.decision_engine"),
        ("Simulation", "engine.simulation.simulation_engine"),
        ("Approval", "engine.recovery.approval_engine"),
        ("Execution Safety", "engine.recovery.execution_engine"),
        ("Verification", "engine.verification.verification_engine"),
        ("Prevention", "engine.prevention.prevention_engine"),
        ("Incident Memory", "engine.prevention.incident_memory")
    ]

    results = []

    for stage_name, module_name in stages:
        print(f"\n=== {stage_name} ===")
        output = run_engine(module_name)
        print(output.strip())

        results.append(
            {
                "stage": stage_name,
                "module": module_name,
                "status": "PASSED"
            }
        )

    summary = {
        "incident_id": INCIDENT_ID,
        "pipeline": "customer_gold_pipeline",
        "stage_count": len(results),
        "stages": results,
        "overall_status": "PASSED"
    }

    print("\n=== AEGIS ORCHESTRATION SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print("\nAEGIS ORCHESTRATION PASSED")


if __name__ == "__main__":
    main()
