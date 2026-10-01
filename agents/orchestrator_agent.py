"""Safety-preserving orchestration for AEGIS advisory agents.

The analysis phase calls existing deterministic engines and always stops
before approval or execution. Existing guarded API/engine paths remain the
only way to approve, authorize, and execute sandbox recovery.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from agents.base_agent import AgentResult, IncidentContext, validate_agent_result
from agents.investigator_agent import IncidentInvestigatorAgent, schema_evidence_references
from agents.prevention_agent import PreventionAgent
from agents.recovery_strategy_agent import RecoveryStrategyAgent
from config.settings import settings
from engine.audit.audit_log import record_event
from engine.evidence.evidence_collector import collect_evidence
from engine.impact.impact_engine import analyze_impact
from engine.lineage.lineage_engine import analyze_lineage
from engine.prevention.incident_memory import find_similar_incidents, record_incident_memory
from engine.prevention.prevention_engine import generate_prevention
from engine.rca.rca_engine import analyze_root_cause
from engine.recovery.decision_engine import generate_decision
from engine.recovery.recovery_engine import generate_strategies
from engine.risk.risk_engine import evaluate_risk
from engine.security.identifiers import validate_incident_id
from engine.simulation.simulation_engine import run_simulation

AGENT_REPORT_NAME = "agent_workflow.json"


class RecoveryOrchestratorAgent:
    name = "recovery_orchestrator"
    version = "1.0"

    def run_analysis(self, incident_id: str) -> dict[str, Any]:
        """Run deterministic investigation and advisory analysis only."""
        validate_incident_id(incident_id)
        incident = self._load_incident(incident_id)
        evidence_data = collect_evidence(incident_id)
        root_cause = analyze_root_cause(incident_id)
        lineage = analyze_lineage(incident_id)
        impact = analyze_impact(incident_id)
        strategies = generate_strategies(incident_id)
        risk = evaluate_risk(incident_id)
        decision = generate_decision(incident_id)
        simulation = run_simulation(incident_id)

        context = IncidentContext(
            incident_id=incident_id,
            incident=incident,
            evidence=schema_evidence_references(evidence_data),
            root_cause=root_cause,
            lineage=lineage,
            business_impact=impact,
            recovery_strategies=strategies,
            risk_results=risk,
            decision=decision,
            simulation_result=simulation,
        )
        return self.analyze_context(context, persist=True)

    def analyze_context(
        self, context: IncidentContext, persist: bool = False
    ) -> dict[str, Any]:
        """Run agents over already-computed deterministic results."""
        investigator = self._invoke(IncidentInvestigatorAgent(), context)
        recovery = self._invoke(RecoveryStrategyAgent(), context)
        recommended_id = context.decision.get("recommended_strategy", {}).get("strategy_id")
        simulation = next(
            (
                item
                for item in context.simulation_result.get("simulations", [])
                if item.get("strategy_id") == recommended_id
            ),
            None,
        )
        prerequisites_passed = (
            investigator.status == "COMPLETED"
            and recovery.status == "COMPLETED"
            and simulation is not None
            and simulation.get("simulation_status") == "PASSED"
        )
        status = "WAITING_FOR_HUMAN_APPROVAL" if prerequisites_passed else "BLOCKED"
        report = {
            "incident_id": context.incident_id,
            "orchestrator": self.name,
            "orchestrator_version": self.version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "workflow_status": status,
            "execution_allowed": False,
            "production_execution_allowed": False,
            "next_required_action": (
                f"Human approval for {recommended_id} is required."
                if prerequisites_passed
                else "Resolve blocked analysis or simulation prerequisites."
            ),
            "investigation": investigator.to_dict(),
            "recovery_analysis": recovery.to_dict(),
            "simulation": simulation,
        }
        if persist:
            self._write_report(context.incident_id, report)
        return report

    def run_post_recovery(self, incident_id: str) -> dict[str, Any]:
        """Explain prevention only after the incident records passed verification."""
        validate_incident_id(incident_id)
        incident = self._load_incident(incident_id)
        if incident.get("verification", {}).get("post_execution_status") != "PASSED":
            return {
                "incident_id": incident_id,
                "workflow_status": "BLOCKED",
                "execution_allowed": False,
                "reason": "Successful post-execution verification is required.",
            }

        evidence_data = collect_evidence(incident_id)
        prevention = generate_prevention(incident_id)
        memory = record_incident_memory(incident_id)
        memory = {**memory, "similar_incidents": find_similar_incidents(incident_id)}
        context = IncidentContext(
            incident_id=incident_id,
            incident=incident,
            evidence=schema_evidence_references(evidence_data),
            verification_result={"verification_status": "PASSED"},
            prevention=prevention,
            incident_memory=memory,
        )
        result = self._invoke(PreventionAgent(), context)
        return {
            "incident_id": incident_id,
            "workflow_status": "COMPLETED" if result.status == "COMPLETED" else "BLOCKED",
            "execution_allowed": False,
            "prevention_analysis": result.to_dict(),
            "incident_memory": memory,
        }

    def _invoke(self, agent: Any, context: IncidentContext) -> AgentResult:
        started = perf_counter()
        result = agent.analyze(context)
        latency_ms = round((perf_counter() - started) * 1000)
        result = AgentResult(**{**result.__dict__, "latency_ms": latency_ms})
        validate_agent_result(result, context)
        context_hash = hashlib.sha256(
            json.dumps(
                {
                    "incident_id": context.incident_id,
                    "agent": agent.name,
                    "evidence_ids": [item.evidence_id for item in context.evidence],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        record_event(
            incident_id=context.incident_id,
            action="agent_invoked",
            status="PASSED" if result.status == "COMPLETED" else result.status,
            actor=agent.name,
            details={
                "agent_version": agent.version,
                "context_hash": context_hash,
                "output_status": result.status,
                "confidence": result.confidence,
                "evidence_references": [item.evidence_id for item in result.evidence],
                "provider": result.provider,
                "model": result.model,
                "latency_ms": latency_ms,
            },
        )
        return result

    @staticmethod
    def _load_incident(incident_id: str) -> dict[str, Any]:
        incident_file = settings.paths.incidents_dir / f"{incident_id}.json"
        if not incident_file.exists():
            raise FileNotFoundError(f"Incident not found: {incident_id}")
        return json.loads(incident_file.read_text(encoding="utf-8"))

    @staticmethod
    def _write_report(incident_id: str, report: dict[str, Any]) -> None:
        incident_dir = settings.paths.incidents_dir / incident_id
        incident_dir.mkdir(parents=True, exist_ok=True)
        (incident_dir / AGENT_REPORT_NAME).write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )


def load_agent_report(incident_id: str) -> dict[str, Any]:
    validate_incident_id(incident_id)
    path: Path = settings.paths.incidents_dir / incident_id / AGENT_REPORT_NAME
    if not path.exists():
        raise FileNotFoundError(f"Agent workflow report not found for: {incident_id}")
    return json.loads(path.read_text(encoding="utf-8"))