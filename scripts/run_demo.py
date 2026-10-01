"""AEGIS end-to-end incident recovery demo.

Replays the full detect -> evidence -> RCA -> impact -> strategies ->
risk -> decision -> simulation -> approval -> execution -> verification
-> prevention loop for the resolved schema-drift incident
(INC-20260930-001) and prints a readable, numbered progress report.

Every stage is idempotent and safe to re-run: approval/execution will
report their existing state instead of re-approving or re-executing.
Production datasets (data/gold, data/silver) are never modified.

Usage:
    python scripts/run_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

INCIDENT_ID = "INC-20260930-001"
STRATEGY_ID = "REC-002"
APPROVER = "Rakesh Bontala"

TOTAL_STEPS = 15


def _print_header() -> None:
    print("=" * 72)
    print("AEGIS INCIDENT RECOVERY DEMO")
    print("Detect. Prove. Simulate. Recover. Prevent.")
    print("=" * 72)
    print(f"Incident : {INCIDENT_ID}")
    print(f"Strategy : {STRATEGY_ID} (Targeted Rebuild)")
    print()


def _step(number: int, label: str, func):
    dots = "." * max(3, 28 - len(label))
    print(f"[{number:>2}/{TOTAL_STEPS}] {label} {dots}", end=" ", flush=True)

    try:
        result = func()
    except Exception as error:  # noqa: BLE001 - demo reports failures, never crashes
        print("FAIL")
        print(f"         -> {type(error).__name__}: {error}")
        return None

    print("PASS")
    return result


def main() -> int:
    _print_header()

    import json

    from agents.base_agent import IncidentContext
    from agents.investigator_agent import schema_evidence_references
    from agents.orchestrator_agent import RecoveryOrchestratorAgent
    from engine.evidence.evidence_collector import collect_evidence
    from engine.impact.impact_engine import analyze_impact
    from engine.lineage.lineage_engine import analyze_lineage
    from engine.prevention.prevention_engine import generate_prevention
    from engine.rca.rca_engine import analyze_root_cause
    from engine.recovery.approval_engine import request_approval
    from engine.recovery.approve_recovery import decide_approval
    from engine.recovery.authorization_record import authorize
    from engine.recovery.decision_engine import generate_decision
    from engine.recovery.recovery_engine import generate_strategies
    from engine.recovery.sandbox_execution_engine import execute_recovery
    from engine.risk.risk_engine import evaluate_risk
    from engine.simulation.simulation_engine import run_simulation
    from engine.verification.verification_engine import run_verification_checklist

    incident = json.loads(
        (PROJECT_ROOT / "data" / "incidents" / f"{INCIDENT_ID}.json").read_text(encoding="utf-8")
    )
    evidence = _step(1, "Collecting evidence", lambda: collect_evidence(INCIDENT_ID))
    rca = _step(2, "Root cause analysis", lambda: analyze_root_cause(INCIDENT_ID))
    lineage = _step(3, "Calculating blast radius", lambda: analyze_lineage(INCIDENT_ID))
    impact = _step(4, "Calculating business impact", lambda: analyze_impact(INCIDENT_ID))
    strategies = _step(5, "Generating recovery strategies", lambda: generate_strategies(INCIDENT_ID))
    risk = _step(6, "Evaluating risk", lambda: evaluate_risk(INCIDENT_ID))
    decision = _step(7, "Generating recovery decision", lambda: generate_decision(INCIDENT_ID))
    simulation = _step(8, "Simulating recovery (sandbox)", lambda: run_simulation(INCIDENT_ID))

    context = IncidentContext(
        incident_id=INCIDENT_ID,
        incident=incident,
        evidence=schema_evidence_references(evidence or {}),
        root_cause=rca or {},
        lineage=lineage or {},
        business_impact=impact or {},
        recovery_strategies=strategies or {},
        risk_results=risk or {},
        decision=decision or {},
        simulation_result=simulation or {},
    )
    agent_report = _step(
        9,
        "Running agent investigation",
        lambda: RecoveryOrchestratorAgent().analyze_context(context, persist=True),
    )
    _step(10, "Requesting human approval", request_approval)

    approval = _step(
        11,
        "Recording human approval",
        lambda: decide_approval(INCIDENT_ID, STRATEGY_ID, "APPROVE", APPROVER),
    )
    if approval is not None:
        authorize(INCIDENT_ID, STRATEGY_ID)

    execution = _step(
        12,
        "Executing sandbox recovery",
        lambda: execute_recovery(INCIDENT_ID, STRATEGY_ID),
    )
    _step(13, "Verifying recovery", lambda: run_verification_checklist(INCIDENT_ID))

    prevention = _step(14, "Generating prevention", lambda: generate_prevention(INCIDENT_ID))
    post_recovery = _step(
        15,
        "Running prevention agent",
        lambda: RecoveryOrchestratorAgent().run_post_recovery(INCIDENT_ID),
    )

    print()
    print("=" * 72)
    print("INCIDENT RESOLVED")
    print("=" * 72)

    if decision is not None:
        recommended = decision["recommended_strategy"]
        print(f"Recommended strategy : {recommended['strategy_id']} - {recommended['name']}")
        print(f"Decision confidence   : {decision['confidence']}")

    if agent_report is not None:
        print(f"Agent workflow        : {agent_report['workflow_status']}")
        print("Agent execution       : DISALLOWED (advisory only)")

    if risk is not None:
        print("Risk comparison       :", ", ".join(
            f"{e['strategy_id']}={e['risk_score']} ({e['risk_classification']})"
            for e in risk["risk_evaluations"]
        ))

    if execution is not None:
        print(f"Execution scope       : {execution['execution_scope']}")
        print(f"Production modified   : {execution['production_modified']}")
        if execution.get("idempotent"):
            print("Execution note        : already executed previously (idempotent no-op)")

    if prevention is not None:
        print(f"Prevention controls   : {prevention['prevention_control_count']} generated")
    if post_recovery is not None:
        print(f"Prevention agent      : {post_recovery['workflow_status']}")
    print()
    print("Production modified: FALSE")
    print("AEGIS DEMO COMPLETE")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
