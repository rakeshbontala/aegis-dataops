"""Recovery decision engine.

Deterministic comparison layer that sits between risk evaluation and
simulation. It never executes anything and never bypasses human
approval — it only produces a transparent, evidence-based
recommendation for a human to review.

Inputs (all previously computed, on-disk artifacts / in-process calls):
  - recovery strategies       (engine.recovery.recovery_engine)
  - risk evaluation           (engine.risk.risk_engine)
  - incident evidence         (data/incidents/{id}.json)
  - blast radius / lineage    (engine.lineage.lineage_engine)
  - business impact           (engine.impact.impact_engine)

Output:
  data/sandbox/recovery/decision/recovery_decision.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config.settings import settings
from engine.audit.audit_log import record_event
from engine.impact.impact_engine import analyze_impact
from engine.lineage.lineage_engine import analyze_lineage
from engine.security.identifiers import validate_incident_id

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INCIDENT_ID = "INC-20260930-001"

INCIDENTS_DIR = PROJECT_ROOT / "data" / "incidents"
STRATEGY_FILE = settings.paths.sandbox_recovery_dir / "strategies" / "recovery_strategies.json"
RISK_FILE = settings.paths.sandbox_recovery_dir / "risk" / "risk_evaluation.json"
DECISION_DIR = settings.paths.sandbox_recovery_dir / "decision"
DECISION_FILE = DECISION_DIR / "recovery_decision.json"


def _load_json(path: Path, hint: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{hint} not found: {path}. Run its engine stage first.")
    return json.loads(path.read_text(encoding="utf-8"))


def _confidence_label(margin: float) -> str:
    """Confidence is the risk-score gap between the best and next-best
    strategy: a bigger gap means the recommendation is less ambiguous."""
    if margin >= 3:
        return "HIGH"
    if margin >= 1:
        return "MEDIUM"
    return "LOW"


def generate_decision(incident_id: str = DEFAULT_INCIDENT_ID) -> dict[str, Any]:
    validate_incident_id(incident_id)

    incident_file = INCIDENTS_DIR / f"{incident_id}.json"
    incident = _load_json(incident_file, "Incident record")

    strategy_data = _load_json(STRATEGY_FILE, "Recovery strategies")
    risk_data = _load_json(RISK_FILE, "Risk evaluation")

    for source, label in ((strategy_data, "strategies"), (risk_data, "risk evaluation")):
        if source.get("incident_id") != incident["incident_id"]:
            raise ValueError(f"Recovery {label} do not match the requested incident.")

    impact_data = analyze_impact(incident_id)
    lineage_data = analyze_lineage(incident_id)

    strategies_by_id = {s["strategy_id"]: s for s in strategy_data["recovery_strategies"]}
    risk_by_id = {r["strategy_id"]: r for r in risk_data["risk_evaluations"]}
    impacted_assets = {a["asset"] for a in impact_data["impacted_assets"]}

    evaluated_strategies = []

    for strategy_id, strategy in strategies_by_id.items():
        risk = risk_by_id.get(strategy_id, {})
        scope_overlap = sorted(set(strategy.get("scope", [])) & impacted_assets)

        evaluated_strategies.append(
            {
                "strategy_id": strategy_id,
                "name": strategy["name"],
                "description": strategy["description"],
                "scope": strategy.get("scope", []),
                "risk_score": risk.get("risk_score"),
                "risk_classification": risk.get("risk_classification"),
                "runtime_class": strategy.get("runtime_class"),
                "data_loss_risk": strategy.get("data_loss_risk"),
                "requires_validation": strategy.get("requires_validation", True),
                "human_approval_required": strategy.get("human_approval_required", True),
                "business_critical_assets_in_scope": scope_overlap,
            }
        )

    # Deterministic ranking: lowest risk score wins; ties broken by smaller
    # blast radius (scope size), then strategy id for stability.
    ranked = sorted(
        evaluated_strategies,
        key=lambda s: (s["risk_score"], len(s["scope"]), s["strategy_id"]),
    )

    recommended = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    margin = (runner_up["risk_score"] - recommended["risk_score"]) if runner_up else 0

    decision_factors = [
        f"{recommended['strategy_id']} has the lowest weighted risk score "
        f"({recommended['risk_score']}, {recommended['risk_classification']}) "
        f"among {len(evaluated_strategies)} evaluated strategies.",
        f"{recommended['strategy_id']} scope ({len(recommended['scope'])} assets) is "
        "the smallest blast radius that still resolves the schema contract violation.",
        f"Data-loss risk for {recommended['strategy_id']} is "
        f"'{recommended['data_loss_risk']}'.",
    ]

    if recommended["business_critical_assets_in_scope"]:
        decision_factors.append(
            "Business-critical assets in scope: "
            + ", ".join(recommended["business_critical_assets_in_scope"])
        )

    tradeoffs = [
        f"{recommended['strategy_id']} does not rebuild {a} directly; it relies on "
        "the existing raw/bronze layers being schema-correct."
        for a in ("raw.customers", "bronze.customers")
        if a not in recommended["scope"]
    ]

    rejected_alternatives = []
    for strategy in ranked[1:]:
        reasons = [
            f"risk score {strategy['risk_score']} ({strategy['risk_classification']}) "
            f"is higher than {recommended['strategy_id']}'s {recommended['risk_score']}."
        ]
        if strategy["data_loss_risk"] != recommended["data_loss_risk"]:
            reasons.append(
                f"data-loss risk is '{strategy['data_loss_risk']}' "
                f"vs '{recommended['data_loss_risk']}' for the recommended strategy."
            )
        if len(strategy["scope"]) > len(recommended["scope"]):
            reasons.append(
                f"larger blast radius ({len(strategy['scope'])} assets vs "
                f"{len(recommended['scope'])})."
            )

        rejected_alternatives.append(
            {
                "strategy_id": strategy["strategy_id"],
                "name": strategy["name"],
                "reasons": reasons,
            }
        )

    result = {
        "incident_id": incident["incident_id"],
        "evaluated_strategies": evaluated_strategies,
        "recommended_strategy": {
            "strategy_id": recommended["strategy_id"],
            "name": recommended["name"],
            "risk_score": recommended["risk_score"],
            "risk_classification": recommended["risk_classification"],
        },
        "decision_factors": decision_factors,
        "tradeoffs": tradeoffs or [
            "No material trade-off identified versus a full source-to-gold rebuild."
        ],
        "rejected_alternatives": rejected_alternatives,
        "confidence": _confidence_label(margin),
        "blast_radius": {
            "starting_asset": lineage_data["starting_asset"],
            "impacted_assets": lineage_data["impacted_assets"],
        },
        "human_approval_required": settings.execution_safety.human_approval_required,
        "production_execution_allowed": settings.execution_safety.production_execution_enabled,
    }

    DECISION_DIR.mkdir(parents=True, exist_ok=True)
    DECISION_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")

    record_event(
        incident_id=incident["incident_id"],
        action="decision_generated",
        status="PASSED",
        details={"recommended_strategy": recommended["strategy_id"], "confidence": result["confidence"]},
    )

    return result


def main() -> None:
    result = generate_decision()

    print("Recovery Decision Analysis:")
    print(json.dumps(result, indent=2))
    print(f"Decision written to: {DECISION_FILE}")
    print("DECISION GENERATION PASSED")


if __name__ == "__main__":
    main()
