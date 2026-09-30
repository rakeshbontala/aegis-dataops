"""Failure-path / negative tests for the safety gate loop.

These intentionally break preconditions to prove AEGIS fails closed:
missing approval, wrong strategy, malformed ids, and duplicate/blocked
execution must never be allowed through.
"""

import json

import pytest
from fastapi.testclient import TestClient

from api.main import app
from config.settings import settings
from engine.recovery.approve_recovery import ApprovalError, decide_approval
from engine.recovery.sandbox_execution_engine import ExecutionBlockedError, execute_recovery

client = TestClient(app)

INCIDENT_ID = "INC-20260930-001"
FAKE_INCIDENT_ID = "INC-20990101-999"  # isolates audit-log side effects from the real incident
APPROVAL_FILE = settings.paths.sandbox_recovery_dir / "approval" / "approval_request.json"


def test_production_execution_disabled_by_default():
    """The most important invariant: production execution must be
    disabled unless explicitly enabled by configuration."""
    assert settings.execution_safety.production_execution_enabled is False


def test_execute_blocked_without_prior_authorization(tmp_path, monkeypatch):
    """If no authorization record exists at all, execution must be blocked
    (fail-closed), never silently allowed."""
    from engine.recovery import sandbox_execution_engine as see

    monkeypatch.setattr(see, "AUTHORIZATION_FILE", tmp_path / "missing_authorization.json")

    # Use a strategy that has never been executed so the idempotency
    # short-circuit does not mask the missing-authorization check.
    with pytest.raises(ExecutionBlockedError, match="No authorization record found"):
        see.execute_recovery(INCIDENT_ID, "REC-999")


def test_execute_blocked_when_strategy_does_not_match_authorization():
    """Attempting to execute a strategy that was never approved/authorized
    must be blocked, even though the incident itself is valid."""
    with pytest.raises(ExecutionBlockedError):
        execute_recovery(INCIDENT_ID, "REC-001")


def test_execute_api_blocks_unauthorized_strategy():
    response = client.post(f"/api/incidents/{INCIDENT_ID}/execute?strategy_id=REC-003")
    assert response.status_code == 409


def test_approval_cannot_be_granted_when_sandbox_verification_failed(tmp_path, monkeypatch):
    """Simulated verification failure must block approval (fail-closed)."""
    from engine.recovery import approve_recovery as ar

    fake_request = {
        "incident_id": FAKE_INCIDENT_ID,
        "requested_strategy": {"strategy_id": "REC-002", "name": "Targeted Rebuild"},
        "approval_status": "PENDING",
        "approved_by": None,
        "approval_allowed": False,  # sandbox verification did NOT pass
        "execution_allowed": False,
    }
    fake_file = tmp_path / "approval_request.json"
    fake_file.write_text(json.dumps(fake_request), encoding="utf-8")
    monkeypatch.setattr(ar, "APPROVAL_FILE", fake_file)

    with pytest.raises(ApprovalError, match="sandbox verification has not passed"):
        ar.decide_approval(FAKE_INCIDENT_ID, "REC-002", "APPROVE", "Someone")


def test_approval_cannot_be_re_approved_after_rejection(tmp_path, monkeypatch):
    from engine.recovery import approve_recovery as ar

    fake_request = {
        "incident_id": FAKE_INCIDENT_ID,
        "requested_strategy": {"strategy_id": "REC-002", "name": "Targeted Rebuild"},
        "approval_status": "REJECTED",
        "approved_by": "Someone",
        "approval_allowed": True,
        "execution_allowed": False,
    }
    fake_file = tmp_path / "approval_request.json"
    fake_file.write_text(json.dumps(fake_request), encoding="utf-8")
    monkeypatch.setattr(ar, "APPROVAL_FILE", fake_file)

    with pytest.raises(ApprovalError, match="already been rejected"):
        ar.decide_approval(FAKE_INCIDENT_ID, "REC-002", "APPROVE", "Someone")


def test_duplicate_execution_request_is_idempotent_not_destructive():
    """Executing the same already-executed incident/strategy twice must
    return the existing record unchanged, never re-copy/corrupt output."""
    first = execute_recovery(INCIDENT_ID, "REC-002")
    second = execute_recovery(INCIDENT_ID, "REC-002")

    assert first["idempotent"] is True
    assert second["idempotent"] is True
    assert first["executed_at"] == second["executed_at"]


def test_malformed_incident_id_rejected_everywhere():
    from engine.security.identifiers import InvalidIdentifierError

    with pytest.raises(InvalidIdentifierError):
        execute_recovery("../../etc/passwd", "REC-002")

    response = client.get("/api/incidents/../../etc")
    assert response.status_code in (400, 404)


def test_missing_recovery_verification_artifact_blocks_approval(tmp_path, monkeypatch):
    """If the verification artifact required for a fresh approval request
    is missing, request_approval must fail rather than approve blindly."""
    from engine.recovery import approval_engine as ae

    monkeypatch.setattr(ae, "APPROVAL_OUTPUT", tmp_path / "approval_request.json")
    monkeypatch.setattr(ae, "VERIFICATION_FILE", tmp_path / "missing_verification.json")

    with pytest.raises(FileNotFoundError):
        ae.request_approval()
