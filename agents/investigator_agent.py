"""Evidence-grounded incident investigator.

This agent summarizes deterministic evidence and RCA output. It does not
inspect external systems, infer unavailable business metrics, or execute
recovery actions.
"""

from __future__ import annotations

from typing import Any

from agents.base_agent import AgentResult, EvidenceReference, IncidentContext


def schema_evidence_references(evidence: dict[str, Any]) -> tuple[EvidenceReference, ...]:
    schema_items = evidence.get("schema_contract_evidence", [])
    if not schema_items or not isinstance(schema_items[0], dict):
        return ()

    schema = schema_items[0]
    source = "incident.evidence[0]"
    return (
        EvidenceReference("EV-001", "expected schema", source, schema.get("expected_columns")),
        EvidenceReference("EV-002", "observed schema", source, schema.get("actual_columns")),
        EvidenceReference("EV-003", "unexpected columns", source, schema.get("unexpected_columns", [])),
        EvidenceReference("EV-004", "missing required columns", source, schema.get("missing_columns", [])),
    )


class IncidentInvestigatorAgent:
    name = "incident_investigator"
    role = "Evidence-grounded incident investigation"
    version = "1.0"

    def analyze(self, context: IncidentContext) -> AgentResult:
        if not context.evidence:
            return self._blocked(context, "Incident evidence is missing.")

        facts = {item.evidence_id: item.fact for item in context.evidence}
        expected = facts.get("EV-001")
        observed = facts.get("EV-002")
        reported_unexpected = facts.get("EV-003")
        reported_missing = facts.get("EV-004")
        if not all(
            isinstance(value, list)
            for value in (expected, observed, reported_unexpected, reported_missing)
        ):
            return self._blocked(context, "Schema evidence is incomplete or malformed.")

        derived_unexpected = [column for column in observed if column not in expected]
        derived_missing = [column for column in expected if column not in observed]
        if (
            set(derived_unexpected) != set(reported_unexpected)
            or set(derived_missing) != set(reported_missing)
        ):
            return self._blocked(context, "Schema evidence is conflicting.")

        classification = context.root_cause.get("classification", "UNKNOWN")
        root_cause = context.root_cause.get("root_cause")
        confidence_value = context.root_cause.get("confidence", 0)
        if classification == "UNKNOWN" or not root_cause:
            return AgentResult(
                agent=self.name,
                agent_role=self.role,
                agent_version=self.version,
                incident_id=context.incident_id,
                status="COMPLETED",
                summary="The current evidence is insufficient to determine a root cause.",
                confidence="INSUFFICIENT_EVIDENCE",
                evidence=context.evidence,
                reasoning_summary="No supported deterministic RCA classification is available.",
                recommendations=("Collect additional deterministic evidence.",),
                warnings=("Insufficient evidence.",),
                details={"probable_root_cause": None, "missing_evidence": ["supported RCA"]},
            )

        affected_assets = list(context.incident.get("affected_assets", []))
        impacted_assets = list(context.lineage.get("impacted_assets", []))
        schema_changes = []
        if reported_unexpected:
            schema_changes.append(f"Unexpected column(s): {', '.join(reported_unexpected)}.")
        if reported_missing:
            schema_changes.append(f"Missing required column(s): {', '.join(reported_missing)}.")
        return AgentResult(
            agent=self.name,
            agent_role=self.role,
            agent_version=self.version,
            incident_id=context.incident_id,
            status="COMPLETED",
            summary=(
                f"{classification}: {root_cause} {' '.join(schema_changes)}"
            ),
            confidence="HIGH" if confidence_value >= 0.8 else "MEDIUM",
            evidence=context.evidence,
            reasoning_summary="Conclusion is based on EV-001 through EV-004 plus deterministic RCA.",
            recommendations=("Continue with deterministic recovery strategy evaluation.",),
            details={
                "probable_root_cause": {
                    "type": classification,
                    "description": root_cause,
                    "confidence": "HIGH" if confidence_value >= 0.8 else "MEDIUM",
                },
                "affected_assets": affected_assets,
                "blast_radius": impacted_assets,
                "business_impact": dict(context.business_impact),
                "missing_evidence": [],
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
            details={"missing_evidence": [reason]},
        )