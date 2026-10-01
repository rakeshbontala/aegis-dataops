from agents.base_agent import IncidentContext
from agents.investigator_agent import schema_evidence_references
from agents.orchestrator_agent import RecoveryOrchestratorAgent


EVIDENCE_DATA = {
    "schema_contract_evidence": [
        {
            "expected_columns": ["customer_id"],
            "actual_columns": ["customer_id", "customer_segment"],
            "unexpected_columns": ["customer_segment"],
        }
    ]
}


def context(simulation_status="PASSED"):
    return IncidentContext(
        incident_id="INC-20990101-999",
        incident={
            "incident_id": "INC-20990101-999",
            "affected_assets": ["silver.customers"],
        },
        evidence=schema_evidence_references(EVIDENCE_DATA),
        root_cause={
            "classification": "SCHEMA_CONTRACT_VIOLATION",
            "root_cause": "Unapproved schema change.",
            "confidence": 1.0,
        },
        lineage={"impacted_assets": ["customer_gold_pipeline"]},
        business_impact={"impact_count": 1},
        recovery_strategies={
            "recovery_strategies": [
                {
                    "strategy_id": "REC-002",
                    "name": "Targeted Rebuild",
                    "scope": ["silver.customers"],
                    "requires_validation": True,
                }
            ]
        },
        risk_results={
            "risk_evaluations": [
                {
                    "strategy_id": "REC-002",
                    "risk_score": 8,
                    "risk_classification": "MEDIUM_RISK",
                }
            ]
        },
        decision={
            "recommended_strategy": {
                "strategy_id": "REC-002",
                "name": "Targeted Rebuild",
                "risk_score": 8,
            },
            "confidence": "HIGH",
        },
        simulation_result={
            "simulations": [
                {
                    "strategy_id": "REC-002",
                    "simulation_status": simulation_status,
                    "sandbox_execution": True,
                }
            ]
        },
    )


def test_orchestrator_stops_for_human_approval(monkeypatch):
    events = []
    monkeypatch.setattr(
        "agents.orchestrator_agent.record_event",
        lambda **kwargs: events.append(kwargs),
    )

    report = RecoveryOrchestratorAgent().analyze_context(context())

    assert report["workflow_status"] == "WAITING_FOR_HUMAN_APPROVAL"
    assert report["execution_allowed"] is False
    assert report["production_execution_allowed"] is False
    assert "Human approval" in report["next_required_action"]
    assert len(events) == 2
    assert all(event["action"] == "agent_invoked" for event in events)


def test_orchestrator_blocks_failed_simulation(monkeypatch):
    monkeypatch.setattr("agents.orchestrator_agent.record_event", lambda **kwargs: None)

    report = RecoveryOrchestratorAgent().analyze_context(context("FAILED"))

    assert report["workflow_status"] == "BLOCKED"
    assert report["execution_allowed"] is False


def test_post_recovery_blocks_without_verified_incident(monkeypatch):
    monkeypatch.setattr(
        RecoveryOrchestratorAgent,
        "_load_incident",
        staticmethod(lambda incident_id: {"incident_id": incident_id, "verification": {}}),
    )

    report = RecoveryOrchestratorAgent().run_post_recovery("INC-20990101-999")

    assert report["workflow_status"] == "BLOCKED"
    assert report["execution_allowed"] is False
