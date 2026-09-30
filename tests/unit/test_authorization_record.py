"""Regression test: authorize() must be idempotent - repeated calls with
unchanged inputs must not regenerate `authorized_at` (this previously
caused timestamp drift on every POST /approval call, even no-op ones)."""

from engine.recovery.authorization_record import authorize


def test_authorize_is_idempotent_when_nothing_changed():
    first = authorize("INC-20260930-001", "REC-002")
    second = authorize("INC-20260930-001", "REC-002")

    assert first["authorized_at"] == second["authorized_at"]
    assert first == second


def test_authorize_reports_authorized_status():
    record = authorize("INC-20260930-001", "REC-002")
    assert record["authorization_status"] == "AUTHORIZED"
    assert all(record["safety_checks"].values())
