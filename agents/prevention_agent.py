"""Post-recovery explanation of deterministic prevention controls."""

from __future__ import annotations

from agents.base_agent import AgentResult, IncidentContext


class PreventionAgent:
    name = "prevention_agent"
    role = "Explain prevention controls and reusable incident patterns"
    version = "1.0"

    def analyze(self, context: IncidentContext) -> AgentResult:
        controls = context.prevention.get("prevention_controls", [])
        verification = context.verification_result
        verification_passed = (
            verification.get("verification_status") == "PASSED"
            or context.incident.get("verification", {}).get("post_execution_status") == "PASSED"
        )
        if not verification_passed:
            return self._blocked(context, "Successful recovery verification is required.")
        if not controls:
            return self._blocked(context, "Deterministic prevention controls are missing.")

        memory = context.incident_memory
        similar_incidents = list(memory.get("similar_incidents", []))
        return AgentResult(
            agent=self.name,
            agent_role=self.role,
            agent_version=self.version,
            incident_id=context.incident_id,
            status="COMPLETED",
            summary=f"{len(controls)} deterministic prevention controls are available for review.",
            confidence="HIGH",
            evidence=context.evidence,
            reasoning_summary="Recommendations reproduce verified prevention controls and stored incident memory.",
            recommendations=tuple(
                f"{control.get('control_id', 'UNKNOWN')}: {control.get('description', '')}"
                for control in controls
            ),
            warnings=("Recommendations do not modify production configuration.",),
            details={
                "root_cause": context.prevention.get("based_on_root_cause"),
                "prevention_controls": list(controls),
                "similar_incidents": similar_incidents,
                "memory_recorded": bool(memory),
            },
        )

    def _blocked(self, context: IncidentContext, reason: str) -> AgentResult:
        return AgentResult(
            agent=self.name,
            agent_role=self.role,
            agent_version=self.version,
            incident_id=context.incident_id,
            status="BLOCKED",
            summary=reason,
            confidence="INSUFFICIENT_EVIDENCE",
            evidence=context.evidence,
            reasoning_summary=reason,
            warnings=(reason,),
        )