"""Recovery decision narration agent.

Turns the deterministic decision-engine output into a readable executive
summary. The LLM path (opt-in, requires `AEGIS_ENABLE_AI_RECOMMENDATIONS=true`
and `OPENAI_API_KEY`) only ever *rephrases* the same structured facts the
deterministic path already renders — it cannot introduce new claims, and it
never touches approval, authorization, or execution state.

Falls back to the deterministic narrative on any missing dependency,
missing credential, or API error — the agent must never crash the caller.
"""

from __future__ import annotations

import os
from typing import Any

from agents.base_agent import AgentResponse
from config.settings import settings


def build_deterministic_narrative(decision: dict[str, Any], incident: dict[str, Any]) -> str:
    """Render the decision engine's own fields into readable prose.

    Every sentence maps directly to a field already present in `decision`
    (see engine.recovery.decision_engine) - nothing is invented here.
    """
    recommended = decision.get("recommended_strategy", {})
    rejected = decision.get("rejected_alternatives", [])

    lines = [
        f"AEGIS recommends {recommended.get('strategy_id', '?')} "
        f"({recommended.get('name', 'unknown strategy')}) for incident "
        f"{decision.get('incident_id', incident.get('incident_id', '?'))}, "
        f"a {incident.get('severity', 'unspecified severity')} "
        f"{incident.get('error_type', 'incident')} on "
        f"{incident.get('pipeline_name', 'the affected pipeline')}.",
    ]

    for factor in decision.get("decision_factors", []):
        lines.append(factor)

    tradeoffs = decision.get("tradeoffs", [])
    if tradeoffs:
        lines.append("Trade-offs: " + " ".join(tradeoffs))

    if rejected:
        summaries = [
            f"{alt.get('strategy_id')} ({'; '.join(alt.get('reasons', []))})"
            for alt in rejected
        ]
        lines.append(
            f"{len(rejected)} alternative strategy(ies) were considered and "
            f"rejected: {'; '.join(summaries)}."
        )

    lines.append(
        f"Confidence: {decision.get('confidence', 'UNKNOWN')}. "
        f"Human approval required: {decision.get('human_approval_required', True)}. "
        f"Production execution allowed: {decision.get('production_execution_allowed', False)}."
    )

    return " ".join(lines)


def _try_llm_narrative(decision: dict[str, Any], incident: dict[str, Any]) -> AgentResponse | None:
    api_key = os.getenv("OPENAI_API_KEY")

    if not settings.features.enable_ai_recommendations or not api_key:
        return None

    try:
        from openai import OpenAI  # optional dependency, not in requirements.txt
    except ImportError:
        return None

    try:
        client = OpenAI(api_key=api_key)
        model = os.getenv("AEGIS_OPENAI_MODEL", "gpt-4o-mini")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Rephrase the following incident recovery decision as a "
                        "concise executive summary. Use only the facts given - "
                        "do not invent risk scores, approvals, or outcomes."
                    ),
                },
                {
                    "role": "user",
                    "content": build_deterministic_narrative(decision, incident),
                },
            ],
            timeout=10,
        )

        narrative = response.choices[0].message.content
        if not narrative:
            return None

        return AgentResponse(narrative=narrative.strip(), source="llm", model=model)

    except Exception:  # noqa: BLE001 - any LLM failure must fall back, never crash
        return None


def explain_recovery_decision(
    decision: dict[str, Any], incident: dict[str, Any]
) -> AgentResponse:
    llm_response = _try_llm_narrative(decision, incident)
    if llm_response is not None:
        return llm_response

    return AgentResponse(
        narrative=build_deterministic_narrative(decision, incident),
        source="deterministic",
        model=None,
    )
