import pytest

from agents.base_agent import IncidentContext
from agents.investigator_agent import IncidentInvestigatorAgent, schema_evidence_references


def analyze_schema(evidence, classification, root_cause):
    context = IncidentContext(
        incident_id="INC-20990101-999",
        incident={"incident_id": "INC-20990101-999", "affected_assets": ["silver.customers"]},
        evidence=schema_evidence_references({"schema_contract_evidence": [evidence]}),
        root_cause={
            "classification": classification,
            "root_cause": root_cause,
            "confidence": 1.0,
        },
    )
    return IncidentInvestigatorAgent().analyze(context)


def test_scenario_a_schema_drift_is_grounded():
    result = analyze_schema(
        {
            "expected_columns": ["customer_id", "status"],
            "actual_columns": ["customer_id", "status", "customer_segment"],
            "unexpected_columns": ["customer_segment"],
        },
        "SCHEMA_CONTRACT_VIOLATION",
        "An unapproved column was added.",
    )

    assert result.status == "COMPLETED"
    assert "customer_segment" in result.summary


def test_scenario_b_required_column_removed_is_grounded():
    result = analyze_schema(
        {
            "expected_columns": ["customer_id", "status"],
            "actual_columns": ["customer_id"],
            "unexpected_columns": [],
            "missing_columns": ["status"],
        },
        "REQUIRED_COLUMN_REMOVED",
        "A required contract column is absent.",
    )

    assert result.status == "COMPLETED"
    assert "Missing required column(s): status" in result.summary


@pytest.mark.parametrize(
    ("scenario", "evidence"),
    [
        ("datatype drift", {"type_changes": {"customer_id": ["integer", "string"]}}),
        ("duplicate records", {"duplicate_count": 4}),
        ("null required field", {"null_counts": {"customer_id": 2}}),
        ("invalid status", {"invalid_values": {"status": ["UNKNOWN"]}}),
        ("late-arriving data", {"late_record_count": 7}),
        ("multiple simultaneous issues", {"duplicate_count": 4, "null_counts": {"customer_id": 2}}),
    ],
)
def test_scenarios_without_deterministic_detector_fail_closed(scenario, evidence):
    result = analyze_schema(evidence, "UNKNOWN", "Insufficient deterministic evidence.")

    assert result.status == "BLOCKED", scenario
    assert result.confidence == "INSUFFICIENT_EVIDENCE"