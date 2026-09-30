# Security

## Threat model scope

AEGIS is a local/demo incident-response platform. This document covers the
controls actually implemented, not a general security audit of FastAPI,
Spark, or the OS.

## Input validation (OWASP A03 — Injection / Path Traversal)

Every incident id and strategy id that could reach a filesystem path is
validated against an allowlist regex **before** any path is built:

```python
INCIDENT_ID_PATTERN = re.compile(r"^INC-\d{8}-\d{3}$")   # e.g. INC-20260930-001
STRATEGY_ID_PATTERN = re.compile(r"^REC-\d{3}$")          # e.g. REC-002
ACTOR_NAME_PATTERN = re.compile(r"^[A-Za-z0-9 ._-]{1,64}$")
```

(`engine/security/identifiers.py`)

- The original API (`GET /api/incidents/{incident_id}`) built
  `INCIDENTS_DIR / f"{incident_id}.json"` directly from an unvalidated path
  parameter — a path-traversal-class defect. Every endpoint now validates
  the id first and returns `400` for a malformed id, `404` for a
  well-formed but unknown id.
- Tested in `tests/integration/test_api.py::test_get_incident_rejects_malformed_id`
  and `tests/integration/test_failure_paths.py::test_malformed_incident_id_rejected_everywhere`
  with payloads including `'; DROP TABLE incidents;--` and `../../etc/passwd`.

## Fail-closed execution safety

`engine/recovery/sandbox_execution_engine.execute_recovery()` requires, in
order, before copying a single file:

1. Valid incident id / strategy id (regex).
2. An authorization record exists, matches the incident and strategy, and
   has `authorization_status == "AUTHORIZED"`.
3. `safety_checks.execution_allowed is True` in that authorization record.
4. `"SANDBOX_ONLY"` is present in `settings.execution_safety.allowlisted_execution_scopes`.
5. The sandbox source datasets actually exist on disk.

Any missing condition raises `ExecutionBlockedError` (mapped to HTTP `409`
by the API) instead of proceeding. There is no fallback/"fail open" path.

## Idempotency (prevents duplicate/destructive re-execution)

`execute_recovery()` checks for a prior matching `execution_record.json`
**first**. If found, it returns the existing record with `idempotent: true`
and takes no filesystem action — it does not re-`rmtree`/re-copy. Verified
in `tests/integration/test_failure_paths.py::test_duplicate_execution_request_is_idempotent_not_destructive`.

## Human-in-the-loop

`decide_approval()` (`engine/recovery/approve_recovery.py`) enforces:

- Approval can only be granted if the prior sandbox verification's
  `approval_allowed` flag is `True` (fail-closed).
- A rejected approval cannot be silently re-approved — a new request cycle
  is required.
- Approving an already-approved request is idempotent (no-op, no change to
  `approved_by`/`approved_at`), preventing a second caller from silently
  overwriting who approved the original recovery.

## Production execution default

`AEGIS_PRODUCTION_EXECUTION_ENABLED` defaults to `false`
(`config/settings.py::ExecutionSafety`). There is currently no code path
that performs a production-scope execution — enabling the flag alone does
not create new capability; it only documents the intended kill-switch for
when/if a production execution action is implemented and reviewed.

## Secrets

- `.env` is git-ignored; `.env.example` contains no real values.
- `engine/audit/audit_log.py` scrubs any detail key containing
  `password`/`token`/`secret`/`api_key`/`credential` before writing an
  audit event.
- No secrets are logged via `print()` anywhere in `engine/*`.

## Known gaps (not implemented)

- No authentication/authorization on the API — do not expose this service
  directly to the internet.
- No rate limiting.
- No CSRF protection (not applicable to the current read-mostly, JSON-only
  API, but relevant if browser-based state-changing forms are added later).
