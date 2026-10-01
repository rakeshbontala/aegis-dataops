# API Reference

Base URL (local): `http://127.0.0.1:8000`

All `{incident_id}` path parameters must match `INC-\d{8}-\d{3}` and all
`strategy_id` values (query/body) must match `REC-\d{3}`; otherwise the API
returns `400`. Unknown but well-formed ids return `404`.

## Read endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Service status + whether production execution is enabled. |
| GET | `/api/incidents` | List all incidents (id, pipeline, severity, status, error type). |
| GET | `/api/incidents/{id}` | Full incident record (evidence, root cause, lifecycle, verification, resolution). |
| GET | `/api/incidents/{id}/risk` | Weighted risk evaluation for every generated strategy. |
| GET | `/api/incidents/{id}/strategies` | Generated recovery strategies (REC-001/002/003). |
| GET | `/api/incidents/{id}/decision` | Decision engine output: recommendation, factors, trade-offs, rejected alternatives. |
| GET | `/api/incidents/{id}/explanation` | Advisory-only narrative of the decision (deterministic by default; optionally LLM-phrased, see `docs/RECOVERY_DECISION.md`). |
| GET | `/api/incidents/{id}/impact` | Business impact + blast radius (lineage). |
| GET | `/api/incidents/{id}/verification` | Sandbox verification + post-execution verification artifacts (whichever exist). |
| GET | `/api/incidents/{id}/audit` | Full audit event trail (JSONL, oldest first). |
| GET | `/api/incidents/{id}/prevention` | Persisted prevention recommendations. |
| GET | `/api/incidents/{id}/agents` | Persisted structured investigator and recovery-agent report. |
| GET | `/api/incidents/{id}/memory` | Structured incident memory plus real matching historical incident references. |

## Guarded, state-changing endpoints

| Method | Path | Body / Query | Behavior |
|---|---|---|---|
| POST | `/api/incidents/{id}/investigate` | — | Runs deterministic evidence/RCA/impact/strategy/risk/decision/simulation stages and structured advisory agents. Always stops at `WAITING_FOR_HUMAN_APPROVAL`; never approves or executes. |
| POST | `/api/incidents/{id}/prevention/analyze` | — | Runs prevention and memory analysis only after successful post-execution verification; otherwise returns `409`. |
| POST | `/api/incidents/{id}/simulate` | — | Runs the sandbox simulation stage; `404` if strategies haven't been generated yet. |
| POST | `/api/incidents/{id}/approval` | `{"strategy_id", "decision": "APPROVE"\|"REJECT", "approver"}` | Fail-closed: `409` if verification hasn't passed, if the request has already been rejected, or if the strategy doesn't match. Idempotent if already approved. On success, also re-derives the authorization record. |
| POST | `/api/incidents/{id}/execute` | `?strategy_id=REC-002` | Fail-closed (`409`) unless authorized. Idempotent: returns the existing execution record (`"idempotent": true`) if already executed — never re-copies. |
| POST | `/api/incidents/{id}/verify` | — | Runs the (non-Spark) verification checklist. |

None of these endpoints bypass human approval, and none can reach a
production dataset — `execute` only ever copies within
`data/sandbox/recovery/`.

## Example: full guarded flow

```powershell
$base = "http://127.0.0.1:8000"

Invoke-RestMethod -Method POST "$base/api/incidents/INC-20260930-001/simulate"

$body = '{"strategy_id":"REC-002","decision":"APPROVE","approver":"Jane Doe"}'
Invoke-RestMethod -Method POST "$base/api/incidents/INC-20260930-001/approval" `
    -Body $body -ContentType "application/json"

Invoke-RestMethod -Method POST "$base/api/incidents/INC-20260930-001/execute?strategy_id=REC-002"

Invoke-RestMethod -Method POST "$base/api/incidents/INC-20260930-001/verify"
```

## Error shape

```json
{ "detail": "human-readable reason" }
```

`400` — malformed id. `404` — not found. `409` — safety gate blocked the
request (with the specific reason in `detail`).
