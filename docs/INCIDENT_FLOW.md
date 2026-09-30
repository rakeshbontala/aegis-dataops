# Incident Lifecycle

```
DETECTED -> INVESTIGATED -> RECOVERY_PLANNED -> SANDBOX_VERIFIED
   -> HUMAN_APPROVED -> EXECUTED_SANDBOX -> RECOVERY_VERIFIED -> RESOLVED
```

Each transition is backed by a real artifact, not a status string alone:

| Status | Backed by |
|---|---|
| `DETECTED` | `engine/detection/schema_drift_detector.py` (Spark schema comparison) + the persisted incident record's `evidence`. |
| `INVESTIGATED` | `engine/evidence/evidence_collector.py`, `engine/rca/rca_engine.py`, `engine/lineage/lineage_engine.py`, `engine/impact/impact_engine.py`. |
| `RECOVERY_PLANNED` | `engine/recovery/recovery_engine.py` (strategies) + `engine/risk/risk_engine.py` (risk) + `engine/recovery/decision_engine.py` (recommendation). |
| `SANDBOX_VERIFIED` | `engine/verification/recovery_verifier.py` — Spark before/after comparison of the sandbox rebuild. |
| `HUMAN_APPROVED` | `engine/recovery/approval_engine.py` (request) + `engine/recovery/approve_recovery.py` (decision) + `engine/recovery/authorization_record.py`. |
| `EXECUTED_SANDBOX` | `engine/recovery/sandbox_execution_engine.py` — copies the recovered dataset into `data/sandbox/recovery/executed/{strategy_id}/`. Production untouched. |
| `RECOVERY_VERIFIED` | `engine/verification/post_execution_verifier.py` + `post_execution_data_verifier.py`. |
| `RESOLVED` | `engine/incident_lifecycle.py` stitches the above into the incident record's `lifecycle` array using the *actual* recorded timestamps (never fabricated). |

Every stage additionally emits one or more structured audit events via
`engine.audit.audit_log.record_event()`, retrievable via
`GET /api/incidents/{id}/audit`. The audit trail and the lifecycle array
are complementary: the lifecycle is the coarse, human-readable status
history; the audit trail is the fine-grained, per-engine-call event log.

## Reproducing the incident from scratch

```powershell
python scripts/data_simulator.py        # writes data/raw/customers.csv
python -m pipelines.bronze_ingestion
python -m pipelines.silver_transformation
python -m pipelines.gold_transformation
python scripts/create_schema_contract.py
python scripts/create_schema_drift.py   # adds customer_segment to raw/customers.csv
python scripts/persist_incident.py      # writes data/incidents/INC-20260930-001.json
python -m engine.orchestrator           # runs detection through incident memory
```

Then, to complete the human-in-the-loop steps (not run by the orchestrator,
by design):

```powershell
python -m engine.recovery.approval_engine
python -m engine.recovery.approve_recovery
python -m engine.recovery.authorization_record
python -m engine.recovery.sandbox_execution_engine
python -m engine.verification.post_execution_verifier
python -m engine.verification.post_execution_data_verifier
python -m engine.incident_lifecycle
```

Or simply: `python scripts/run_demo.py`, which replays the whole thing
deterministically and idempotently in one process.
