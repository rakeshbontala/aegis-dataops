"""Unit tests for engine.security.identifiers.

These validators are the first line of defense against path traversal
and injection via untrusted incident/strategy ids and actor names.
"""

import pytest

from engine.security.identifiers import (
    InvalidIdentifierError,
    is_valid_incident_id,
    is_valid_strategy_id,
    validate_actor_name,
    validate_incident_id,
    validate_strategy_id,
)


@pytest.mark.parametrize(
    "incident_id",
    [
        "INC-20260930-001",
        "INC-20991231-999",
    ],
)
def test_valid_incident_ids_accepted(incident_id):
    assert validate_incident_id(incident_id) == incident_id
    assert is_valid_incident_id(incident_id) is True


@pytest.mark.parametrize(
    "incident_id",
    [
        "../../etc/passwd",
        "INC-2026-001",
        "inc-20260930-001",
        "INC-20260930-0001",
        "'; DROP TABLE incidents;--",
        "",
        None,
    ],
)
def test_invalid_incident_ids_rejected(incident_id):
    assert is_valid_incident_id(incident_id) is False
    with pytest.raises(InvalidIdentifierError):
        validate_incident_id(incident_id)


@pytest.mark.parametrize("strategy_id", ["REC-001", "REC-999"])
def test_valid_strategy_ids_accepted(strategy_id):
    assert validate_strategy_id(strategy_id) == strategy_id
    assert is_valid_strategy_id(strategy_id) is True


@pytest.mark.parametrize("strategy_id", ["REC-1", "rec-001", "REC001", "../REC-001", ""])
def test_invalid_strategy_ids_rejected(strategy_id):
    assert is_valid_strategy_id(strategy_id) is False
    with pytest.raises(InvalidIdentifierError):
        validate_strategy_id(strategy_id)


def test_valid_actor_name_accepted():
    assert validate_actor_name("Rakesh Bontala") == "Rakesh Bontala"


@pytest.mark.parametrize("actor", ["", "a" * 65, "<script>alert(1)</script>"])
def test_invalid_actor_name_rejected(actor):
    with pytest.raises(InvalidIdentifierError):
        validate_actor_name(actor)
