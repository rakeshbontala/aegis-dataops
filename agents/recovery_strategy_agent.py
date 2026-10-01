"""Advisory comparison of deterministic recovery strategies and risk."""

from __future__ import annotations

from agents.base_agent import AgentResult, IncidentContext


class RecoveryStrategyAgent:
    name = "recovery_strategy_agent"
    role = "Explain deterministic recovery options and trade-offs"
    version = "1.0"

    def analyze(self, context: IncidentContext) -> AgentResult:
        strategies = context.recovery_strategies.get("recovery_strategies", [])
        evaluations = context.risk_results.get("risk_evaluations", [])
        recommended = context.decision.get("recommended_strategy", {})
        if not strategies:
            return self._blocked(context, "No deterministic recovery strategies are available.")
        if not evaluations or not recommended:
            return self._blocked(context, "Risk evaluation or recovery decision is missing.")

        strategies_by_id = {item.get("strategy_id"): item for item in strategies}
        risks_by_id = {item.get("strategy_id"): item for item in evaluations}
        strategy_id = recommended.get("strategy_id")
        if strategy_id not in strategies_by_id or strategy_id not in risks_by_id:
            return self._blocked(context, f"Unknown recommended strategy: {strategy_id!r}.")

        strategy = strategies_by_id[strategy_id]
        risk = risks_by_id[strategy_id]
        if recommended.get("risk_score") != risk.get("risk_score"):
            return self._blocked(context, "Decision and risk evaluation conflict.")

        comparisons = [
            {
                "strategy_id": item.get("strategy_id"),
                "name": item.get("name"),
                "scope": item.get("scope", []),
                "risk_score": risks_by_id.get(item.get("strategy_id"), {}).get("risk_score"),
                "risk_classification": risks_by_id.get(item.get("strategy_id"), {}).get("risk_classification"),
                "requires_validation": item.get("requires_validation", True),
            }
            for item in strategies
        ]
        return AgentResult(
            agent=self.name,
            agent_role=self.role,
            agent_version=self.version,
            incident_id=context.incident_id,
            status="COMPLETED",
            summary=(
                f"The deterministic decision recommends {strategy_id} "
                f"({strategy.get('name')}) with {risk.get('risk_classification')} risk."
            ),
            confidence=context.decision.get("confidence", "LOW"),
            evidence=context.evidence,
            reasoning_summary="Recommendation is copied from the deterministic decision and risk evaluation.",
            recommendations=(
                f"Request explicit human approval for {strategy_id} after sandbox simulation passes.",
            ),
            warnings=("This advisory output cannot approve or execute recovery.",),
            details={
                "recommended_strategy": dict(recommended),
                "strategy_comparison": comparisons,
                "decision_factors": list(context.decision.get("decision_factors", [])),
                "tradeoffs": list(context.decision.get("tradeoffs", [])),
                "blast_radius": dict(context.decision.get("blast_radius", {})),
                "required_validation": strategy.get("requires_validation", True),
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