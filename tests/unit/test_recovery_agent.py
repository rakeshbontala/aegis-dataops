"""Unit tests for the recovery narration agent.

The agent must work with zero external configuration (deterministic path)
and must never crash even if the optional LLM path is misconfigured.
"""

from agents.base_agent import AgentResponse
from agents.recovery_agent import build_deterministic_narrative, explain_recovery_decision
from engine.recovery.decision_engine import generate_decision

INCIDENT = {
    "incident_id": "INC-20260930-001",
    "pipeline_name": "customer_gold_pipeline",
    "severity": "P1",
    "error_type": "SCHEMA_DRIFT",
}


def test_deterministic_narrative_mentions_recommended_strategy():
    decision = generate_decision("INC-20260930-001")
    narrative = build_deterministic_narrative(decision, INCIDENT)

    assert "REC-002" in narrative
    assert "Targeted Rebuild" in narrative
    assert "Human approval required" in narrative


def test_explain_recovery_decision_defaults_to_deterministic(monkeypatch):
    """With AI recommendations disabled (the default), no network call
    should be attempted and the response must be deterministic."""
    decision = generate_decision("INC-20260930-001")

    response = explain_recovery_decision(decision, INCIDENT)

    assert isinstance(response, AgentResponse)
    assert response.source == "deterministic"
    assert response.model is None
    assert "REC-002" in response.narrative


def test_explain_recovery_decision_falls_back_without_api_key(monkeypatch):
    """Settings are frozen dataclasses, so replace the module-level
    `settings` binding used inside agents.recovery_agent rather than
    mutating the shared instance."""
    import types

    from agents import recovery_agent

    fake_settings = types.SimpleNamespace(
        features=types.SimpleNamespace(enable_ai_recommendations=True)
    )
    monkeypatch.setattr(recovery_agent, "settings", fake_settings)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    decision = generate_decision("INC-20260930-001")
    response = explain_recovery_decision(decision, INCIDENT)

    assert response.source == "deterministic"
