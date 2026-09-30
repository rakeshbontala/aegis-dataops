"""AEGIS command-line interface.

Additive convenience wrapper around the existing engine modules — it does
not move or duplicate their logic, it only calls the same importable
functions already used by the API, the demo runner, and the tests.

Usage:
    python -m aegis detect
    python -m aegis investigate
    python -m aegis strategies
    python -m aegis risk
    python -m aegis decision
    python -m aegis simulate
    python -m aegis approve --approver "Jane Doe"
    python -m aegis execute
    python -m aegis verify
    python -m aegis prevention
    python -m aegis demo
"""

from __future__ import annotations

import argparse
import json
import sys

DEFAULT_INCIDENT_ID = "INC-20260930-001"
DEFAULT_STRATEGY_ID = "REC-002"


def _print(result: object) -> None:
    print(json.dumps(result, indent=2, default=str))


def cmd_detect(args: argparse.Namespace) -> None:
    from engine.detection.schema_drift_detector import main as detect_main

    detect_main()


def cmd_investigate(args: argparse.Namespace) -> None:
    from engine.evidence.evidence_collector import collect_evidence
    from engine.impact.impact_engine import analyze_impact
    from engine.lineage.lineage_engine import analyze_lineage
    from engine.rca.rca_engine import analyze_root_cause

    _print(
        {
            "evidence": collect_evidence(args.incident_id),
            "root_cause_analysis": analyze_root_cause(args.incident_id),
            "lineage": analyze_lineage(args.incident_id),
            "impact": analyze_impact(args.incident_id),
        }
    )


def cmd_strategies(args: argparse.Namespace) -> None:
    from engine.recovery.recovery_engine import generate_strategies

    _print(generate_strategies(args.incident_id))


def cmd_risk(args: argparse.Namespace) -> None:
    from engine.risk.risk_engine import evaluate_risk

    _print(evaluate_risk(args.incident_id))


def cmd_decision(args: argparse.Namespace) -> None:
    from engine.recovery.decision_engine import generate_decision

    _print(generate_decision(args.incident_id))


def cmd_simulate(args: argparse.Namespace) -> None:
    from engine.simulation.simulation_engine import run_simulation

    _print(run_simulation(args.incident_id))


def cmd_approve(args: argparse.Namespace) -> None:
    from engine.recovery.approval_engine import request_approval
    from engine.recovery.approve_recovery import decide_approval

    request_approval()
    result = decide_approval(
        args.incident_id, args.strategy_id, "APPROVE", args.approver
    )
    _print(result)


def cmd_execute(args: argparse.Namespace) -> None:
    from engine.recovery.authorization_record import authorize
    from engine.recovery.sandbox_execution_engine import execute_recovery

    authorize(args.incident_id, args.strategy_id)
    _print(execute_recovery(args.incident_id, args.strategy_id))


def cmd_verify(args: argparse.Namespace) -> None:
    from engine.verification.verification_engine import run_verification_checklist

    _print(run_verification_checklist(args.incident_id))


def cmd_prevention(args: argparse.Namespace) -> None:
    from engine.prevention.prevention_engine import generate_prevention

    _print(generate_prevention(args.incident_id))


def cmd_demo(args: argparse.Namespace) -> None:
    import runpy

    runpy.run_module("scripts.run_demo", run_name="__main__")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aegis", description=__doc__)
    parser.add_argument(
        "--incident-id", dest="incident_id", default=DEFAULT_INCIDENT_ID
    )
    parser.add_argument(
        "--strategy-id", dest="strategy_id", default=DEFAULT_STRATEGY_ID
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("detect", help="Run Spark-backed schema drift detection.")
    subparsers.add_parser("investigate", help="Evidence + RCA + lineage + impact.")
    subparsers.add_parser("strategies", help="Generate recovery strategies.")
    subparsers.add_parser("risk", help="Evaluate recovery strategy risk.")
    subparsers.add_parser("decision", help="Generate the recovery decision.")
    subparsers.add_parser("simulate", help="Run the sandbox simulation.")

    approve_parser = subparsers.add_parser("approve", help="Record human approval.")
    approve_parser.add_argument("--approver", required=True)

    subparsers.add_parser("execute", help="Authorize + execute sandbox recovery.")
    subparsers.add_parser("verify", help="Run the verification checklist.")
    subparsers.add_parser("prevention", help="Generate prevention recommendations.")
    subparsers.add_parser("demo", help="Run the full end-to-end demo.")

    return parser


COMMANDS = {
    "detect": cmd_detect,
    "investigate": cmd_investigate,
    "strategies": cmd_strategies,
    "risk": cmd_risk,
    "decision": cmd_decision,
    "simulate": cmd_simulate,
    "approve": cmd_approve,
    "execute": cmd_execute,
    "verify": cmd_verify,
    "prevention": cmd_prevention,
    "demo": cmd_demo,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = COMMANDS[args.command]
    handler(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
