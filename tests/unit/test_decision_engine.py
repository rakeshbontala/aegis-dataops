"""Unit tests for the deterministic recovery decision engine."""

import pytest

from engine.recovery.decision_engine import generate_decision
from engine.security.identifiers import InvalidIdentifierError


def test_decision_recommends_lowest_risk_strategy():
    decision = generate_decision("INC-20260930-001")

    assert decision["recommended_strategy"]["strategy_id"] == "REC-002"
    assert decision["recommended_strategy"]["risk_score"] == 8
    assert decision["human_approval_required"] is True
    assert decision["production_execution_allowed"] is False


def test_decision_ranks_all_strategies_and_rejects_others():
    decision = generate_decision("INC-20260930-001")

    rejected_ids = {r["strategy_id"] for r in decision["rejected_alternatives"]}
    assert rejected_ids == {"REC-001", "REC-003"}
    assert len(decision["evaluated_strategies"]) == 3

    for rejection in decision["rejected_alternatives"]:
        assert len(rejection["reasons"]) >= 1


def test_decision_never_allows_production_execution_by_default():
    decision = generate_decision("INC-20260930-001")
    assert decision["production_execution_allowed"] is False


def test_decision_rejects_invalid_incident_id():
    with pytest.raises(InvalidIdentifierError):
        generate_decision("../../etc/passwd")
