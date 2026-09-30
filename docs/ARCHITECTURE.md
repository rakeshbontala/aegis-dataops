# AEGIS Architecture

## Design principle

Every stage is an **importable function with a printing CLI wrapper**:

```python
def evaluate_risk(incident_id: str = DEFAULT_INCIDENT_ID) -> dict:
    ...          # pure logic, persists an artifact, returns a dict

def main() -> None:
    result = evaluate_risk()
    print(...)   # CLI/orchestrator-friendly output

if __name__ == "__main__":
    main()
```

This lets the same logic be called from:
- the CLI (`python -m engine.risk.risk_engine`),
- the orchestrator (`engine/orchestrator.py`, which shells out to each stage),
- the API (`api/main.py` imports and calls the functions directly — no
  subprocess, no duplicated logic),
- the demo runner (`scripts/run_demo.py`),
- and tests (`tests/unit`, `tests/integration`).

## Data flow

```
data/raw/customers.csv
   -> pipelines/bronze_ingestion.py -> data/bronze/customers
   -> pipelines/silver_transformation.py -> data/silver/customers
   -> pipelines/gold_transformation.py -> data/gold/customer_summary
```

```
engine/detection/schema_drift_detector.py
   reads data/silver/customers (Spark) vs config/customer_schema_contract.json
```

```
data/incidents/{incident_id}.json                 <- incident record
data/incidents/{incident_id}/audit_log.jsonl       <- append-only audit trail
data/incidents/{incident_id}/prevention.json       <- prevention recommendations

data/sandbox/recovery/
  strategies/recovery_strategies.json   <- engine.recovery.recovery_engine
  risk/risk_evaluation.json             <- engine.risk.risk_engine (reads strategies file)
  impact/impact_analysis.json           <- engine.impact.impact_engine
  lineage/lineage_analysis.json         <- engine.lineage.lineage_engine
  decision/recovery_decision.json       <- engine.recovery.decision_engine
  simulation/simulation_results.json    <- engine.simulation.simulation_engine
  approval/approval_request.json        <- engine.recovery.approval_engine / approve_recovery
  approval/authorization_record.json    <- engine.recovery.authorization_record
  approval/execution_record.json        <- engine.recovery.sandbox_execution_engine
  verification/recovery_verification.json          <- engine.verification.recovery_verifier (Spark)
  verification/post_execution_verification.json    <- engine.verification.post_execution_verifier
  verification/post_execution_data_verification.json <- engine.verification.post_execution_data_verifier (Spark)
  before/, targeted_rebuild/, executed/REC-002/    <- sandbox datasets (parquet)
```

No stage writes to `data/gold` or `data/silver` (production) during recovery
— only to `data/sandbox/recovery/...`.

## Why a single source of truth for strategies

Originally, strategy metadata (risk level, runtime class, data-loss risk)
was hardcoded independently in three files (`recovery_engine.py`,
`risk_engine.py`, `simulation_engine.py`). `risk_engine.py` now reads
`recovery_strategies.json` and derives `impact_scope` as `len(scope)` instead
of a fourth hardcoded number — a change to a strategy's scope automatically
flows into its risk score, with no manual synchronization required.

## Configuration (`config/settings.py`)

```python
settings.risk_weights.execution / .runtime / .data_loss / .impact_scope
settings.risk_weights.high_risk_threshold / .medium_risk_threshold / .blocked_risk_threshold
settings.execution_safety.production_execution_enabled   # default False
settings.execution_safety.human_approval_required         # default True
settings.execution_safety.allowlisted_execution_scopes    # ("SANDBOX_ONLY",)
settings.paths.*            # canonical data/config paths
settings.features.enable_audit_log / .enable_ai_recommendations
```

All are environment-variable driven (see `.env.example`), with safe
defaults that reproduce the original unweighted risk formula.

## Security boundary

`engine/security/identifiers.py` is imported by every module that turns an
incident/strategy id into a filesystem path, and by the API before any path
is constructed from a URL path parameter. See
[SECURITY.md](SECURITY.md).
