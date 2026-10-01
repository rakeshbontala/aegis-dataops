from dataclasses import replace

import pytest

from agents.base_agent import (
    AgentResult,
    AgentUnavailableError,
    EvidenceReference,
    IncidentContext,
    apply_provider,
    validate_agent_result,
)
from agents.investigator_agent import IncidentInvestigatorAgent, schema_evidence_references
from agents.prevention_agent import PreventionAgent
from agents.recovery_strategy_agent import RecoveryStrategyAgent


EVIDENCE_DATA = {
    "schema_contract_evidence": [
        {
            "expected_columns": ["customer_id", "status"],
            "actual_columns": ["customer_id", "status", "customer_segment"],
            "unexpected_columns": ["customer_segment"],
        }
    ]
}


def make_context(**overrides):
    values = {
        "incident_id": "INC-20990101-999",
        "incident": {
            "incident_id": "INC-20990101-999",
            "error_type": "SCHEMA_DRIFT",
            "affected_assets": ["silver.customers"],
            "verification": {"post_execution_status": "PASSED"},
        },
        "evidence": schema_evidence_references(EVIDENCE_DATA),
        "root_cause": {
            "classification": "SCHEMA_CONTRACT_VIOLATION",
            "root_cause": "Source schema changed without an approved contract update.",
            "confidence": 1.0,
        },
        "lineage": {"impacted_assets": ["customer_gold_pipeline"]},
        "business_impact": {"impact_count": 1},
        "recovery_strategies": {
            "recovery_strategies": [
                {
                    "strategy_id": "REC-002",
                    "name": "Targeted Rebuild",
                    "scope": ["silver.customers"],
                    "requires_validation": True,
                }
            ]
        },
        "risk_results": {
            "risk_evaluations": [
                {
                    "strategy_id": "REC-002",
                    "risk_score": 8,
                    "risk_classification": "MEDIUM_RISK",
                }
            ]
        },
        "decision": {
            "recommended_strategy": {
                "strategy_id": "REC-002",
                "name": "Targeted Rebuild",
                "risk_score": 8,
                "risk_classification": "MEDIUM_RISK",
            },
            "confidence": "HIGH",
            "decision_factors": ["REC-002 has the lowest risk score."],
            "tradeoffs": ["Relies on valid upstream data."],
        },
        "verification_result": {"verification_status": "PASSED"},
        "prevention": {
            "based_on_root_cause": "Schema contract violation",
            "prevention_controls": [
                {"control_id": "PREV-001", "description": "Enforce schema contracts."}
            ],
        },
        "incident_memory": {"similar_incidents": []},
    }
    values.update(overrides)
    return IncidentContext(**values)


def test_investigator_uses_only_supplied_evidence():
    result = IncidentInvestigatorAgent().analyze(make_context())

    assert result.status == "COMPLETED"
    assert result.confidence == "HIGH"
    assert "customer_segment" in result.summary
    assert {item.evidence_id for item in result.evidence} == {"EV-001", "EV-002", "EV-003", "EV-004"}
    assert result.production_execution_allowed is False


def test_investigator_blocks_missing_evidence():
    result = IncidentInvestigatorAgent().analyze(make_context(evidence=()))

    assert result.status == "BLOCKED"
    assert result.confidence == "INSUFFICIENT_EVIDENCE"


def test_investigator_blocks_conflicting_evidence():
    conflicting = tuple(
        replace(item, fact=[] if item.evidence_id == "EV-003" else item.fact)
        for item in schema_evidence_references(EVIDENCE_DATA)
    )

    result = IncidentInvestigatorAgent().analyze(make_context(evidence=conflicting))

    assert result.status == "BLOCKED"
    assert "conflicting" in result.summary


def test_recovery_agent_explains_deterministic_recommendation():
    result = RecoveryStrategyAgent().analyze(make_context())

    assert result.status == "COMPLETED"
    assert result.details["recommended_strategy"]["strategy_id"] == "REC-002"
    assert "human approval" in result.recommendations[0]


def test_recovery_agent_blocks_without_strategies():
    result = RecoveryStrategyAgent().analyze(
        make_context(recovery_strategies={"recovery_strategies": []})
    )

    assert result.status == "BLOCKED"


def test_recovery_agent_blocks_unknown_strategy():
    context = make_context(
        decision={
            "recommended_strategy": {"strategy_id": "REC-999", "risk_score": 8},
            "confidence": "LOW",
        }
    )

    result = RecoveryStrategyAgent().analyze(context)

    assert result.status == "BLOCKED"
    assert "Unknown" in result.summary


def test_prevention_agent_requires_successful_verification():
    context = make_context(
        incident={"incident_id": "INC-20990101-999", "verification": {}},
        verification_result={"verification_status": "FAILED"},
    )

    result = PreventionAgent().analyze(context)

    assert result.status == "BLOCKED"


def test_prevention_agent_uses_existing_controls():
    result = PreventionAgent().analyze(make_context())

    assert result.status == "COMPLETED"
    assert result.recommendations == ("PREV-001: Enforce schema contracts.",)


def test_hallucinated_evidence_reference_is_rejected():
    context = make_context()
    result = IncidentInvestigatorAgent().analyze(context)
    hallucinated = replace(
        result,
        evidence=result.evidence + (EvidenceReference("EV-999", "invented", "none", "fake"),),
    )

    with pytest.raises(ValueError, match="unknown evidence"):
        validate_agent_result(hallucinated, context)


def test_unavailable_provider_does_not_replace_deterministic_result():
    class UnavailableProvider:
        name = "unavailable"
        model = None

        def enhance(self, result):
            raise TimeoutError("provider timed out")

    context = make_context()
    result = IncidentInvestigatorAgent().analyze(context)

    with pytest.raises(AgentUnavailableError, match="provider timed out"):
        apply_provider(UnavailableProvider(), result, context)


def test_malformed_provider_output_is_rejected():
    class MalformedProvider:
        name = "malformed"
        model = "test"

        def enhance(self, result):
            return {"summary": "not an AgentResult"}

    context = make_context()
    result = IncidentInvestigatorAgent().analyze(context)

    with pytest.raises(ValueError, match="malformed output"):
        apply_provider(MalformedProvider(), result, context)


def test_agent_result_cannot_allow_production_execution():
    with pytest.raises(ValueError, match="cannot allow production execution"):
        AgentResult(
            agent="unsafe",
            agent_role="unsafe",
            agent_version="1.0",
            incident_id="INC-20990101-999",
            status="COMPLETED",
            summary="unsafe",
            confidence="LOW",
            production_execution_allowed=True,
        )
