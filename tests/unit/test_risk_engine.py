"""Unit tests for the risk engine's weighted, configurable scoring."""

from engine.risk.risk_engine import _classify, _severity_points, evaluate_risk


def test_severity_points_known_levels():
    assert _severity_points("HIGH") == 3
    assert _severity_points("MEDIUM") == 2
    assert _severity_points("LOW") == 1


def test_severity_points_unknown_level_defaults_to_medium():
    assert _severity_points("UNKNOWN") == _severity_points("MEDIUM")


def test_classify_thresholds():
    assert _classify(11) == "HIGH_RISK"
    assert _classify(10) == "HIGH_RISK"
    assert _classify(9) == "MEDIUM_RISK"
    assert _classify(7) == "MEDIUM_RISK"
    assert _classify(6) == "LOW_RISK"


def test_evaluate_risk_matches_known_demo_scenario():
    """Regression test for the resolved INC-20260930-001 scenario: the
    weighted formula (with default weights of 1.0) must reproduce the
    original hardcoded scores exactly."""
    result = evaluate_risk("INC-20260930-001")

    scores = {e["strategy_id"]: e["risk_score"] for e in result["risk_evaluations"]}
    classifications = {
        e["strategy_id"]: e["risk_classification"] for e in result["risk_evaluations"]
    }

    assert scores == {"REC-001": 11, "REC-002": 8, "REC-003": 11}
    assert classifications == {
        "REC-001": "HIGH_RISK",
        "REC-002": "MEDIUM_RISK",
        "REC-003": "HIGH_RISK",
    }


def test_evaluate_risk_rejects_invalid_incident_id():
    import pytest

    from engine.security.identifiers import InvalidIdentifierError

    with pytest.raises(InvalidIdentifierError):
        evaluate_risk("not-a-real-id")
