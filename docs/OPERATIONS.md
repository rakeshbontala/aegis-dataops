# Operations

## Running locally

```powershell
& .venv\Scripts\Activate.ps1
$env:PATH = "$env:HADOOP_HOME\bin;" + $env:PATH   # only needed for Spark-backed stages
python -m uvicorn api.main:app --reload
```

## Environment variables

See `.env.example`. Key ones:

| Variable | Default | Effect |
|---|---|---|
| `AEGIS_ENV` | `development` | Informational; surfaced nowhere security-critical. |
| `AEGIS_LOG_LEVEL` | `INFO` | Reserved for future structured logging config. |
| `AEGIS_PRODUCTION_EXECUTION_ENABLED` | `false` | Kill-switch; no production execution path exists regardless. |
| `AEGIS_HUMAN_APPROVAL_REQUIRED` | `true` | The API refuses to start an execution flow if this is ever set `false` (defense in depth — checked explicitly in `api/main.py`). |
| `AEGIS_RISK_WEIGHT_EXECUTION` / `_RUNTIME` / `_DATA_LOSS` / `_IMPACT_SCOPE` | `1.0` each | Multiply the qualitative HIGH/MEDIUM/LOW severity points before summing into a risk score. |
| `AEGIS_RISK_HIGH_THRESHOLD` / `_MEDIUM_THRESHOLD` / `_BLOCKED_THRESHOLD` | `10` / `7` / `999` | Score cut-offs for `HIGH_RISK` / `MEDIUM_RISK` / `LOW_RISK` / `BLOCKED`. |
| `AEGIS_ENABLE_AUDIT_LOG` | `true` | Disables audit persistence if `false` (events are still computed, just not written). |

## Data safety

- `data/raw`, `data/bronze`, `data/silver`, `data/gold`, `data/incidents`,
  `data/historical` are git-ignored (only `.gitkeep` is tracked) — they are
  local, regenerable artifacts, not source code.
- `data/sandbox/recovery/` holds every recovery artifact; nothing under it
  is a production dataset.
- Re-running `python -m engine.orchestrator` is safe — every stage that
  writes shared state (`approval_engine`, `sandbox_execution_engine`,
  `authorization_record`) is idempotent and will not regress an
  already-approved/already-executed incident back to an earlier state.

## Logs

Every engine stage still prints human-readable progress to stdout (useful
for `python -m engine.orchestrator` and CI). Structured audit events are
additionally persisted as JSONL at
`data/incidents/{incident_id}/audit_log.jsonl` and are queryable via
`GET /api/incidents/{id}/audit`. No secrets are ever written to either.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'dotenv'` | `python-dotenv` listed in `requirements.txt` but not installed in the active venv. | `pip install -r requirements.txt` in the *active* venv (`.venv\Scripts\Activate.ps1` first — a fresh terminal may default to a different interpreter). |
| `Py4JJavaError ... NativeIO$Windows.access0` | Hadoop's `winutils.exe`/`hadoop.dll` not on `PATH`. | `$env:PATH = "$env:HADOOP_HOME\bin;" + $env:PATH` before running any Spark-backed command. |
| `POST /api/incidents/{id}/execute` returns `409` | A safety gate failed (not authorized, wrong strategy, not yet approved). | Check `detail` in the response; it names the exact unmet condition. This is expected, fail-closed behavior, not a bug. |
| Dashboard shows `PENDING` for human approval right after clearing the audit log | No `approval_granted`/`approval_rejected` event has been recorded yet. | Run `scripts/run_demo.py` (or the approval API/CLI step) once. |
