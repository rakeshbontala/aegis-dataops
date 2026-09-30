# AEGIS — Architecture Audit

Date: 2026-09-30
Scope: Full repository inspection prior to hardening work.

## 1. Current Architecture

AEGIS today is a **linear, script-based demonstration pipeline** built around a single
hand-crafted incident (`INC-20260930-001`, schema drift on `silver.customers`).

```
scripts/persist_incident.py        -> writes data/incidents/INC-20260930-001.json
engine/orchestrator.py             -> runs each stage as `python -m engine.x.y` subprocess
  detection.schema_drift_detector  -> real Spark read of data/silver vs schema contract
  evidence.evidence_collector      -> re-reads incident.json, reprints evidence
  rca.rca_engine                   -> re-reads incident.json, classifies root cause
  lineage.lineage_engine           -> hardcoded lineage graph, BFS blast radius
  impact.impact_engine             -> hardcoded impact map
  recovery.recovery_engine         -> hardcoded REC-001/002/003, writes strategies.json
  risk.risk_engine                 -> hardcoded REC-001/002/003 (again), writes risk_evaluation.json
  simulation.simulation_engine     -> hardcoded simulation results (print only)
  recovery.approval_engine         -> reads verification, writes approval_request.json
  recovery.approve_recovery        -> flips approval_status -> APPROVED (hardcoded approver)
  recovery.authorization_record    -> writes authorization_record.json
  recovery.execution_engine        -> safety-check print only (does not execute)
  recovery.sandbox_execution_engine-> copies sandbox output, writes execution_record.json
  verification.recovery_verifier   -> Spark before/after compare (targeted_rebuild)
  verification.post_execution_verifier      -> file-existence checks
  verification.post_execution_data_verifier -> Spark before/executed compare
  prevention.prevention_engine     -> hardcoded prevention controls (print only)
  prevention.incident_memory       -> writes data/historical/{id}.json
engine/incident_lifecycle.py       -> standalone script that stitches timestamps into
                                       data/incidents/INC-20260930-001.json
api/main.py                        -> FastAPI: `/`, `/health`,
                                       `/api/incidents/{id}`, `/api/incidents/{id}/risk`
ui/static/*                        -> dark dashboard, fetches the two incident endpoints
```

## 2. Existing Components That Work

- **Real Spark-backed schema drift detection** (`engine/detection/schema_drift_detector.py`)
  reads actual `data/silver/customers` parquet and compares against
  `config/customer_schema_contract.json`. This is genuine, not fabricated.
- **Real Spark-backed recovery simulation and verification**
  (`pipelines/targeted_recovery.py`, `engine/verification/recovery_verifier.py`,
  `engine/verification/post_execution_data_verifier.py`) actually read/write parquet,
  compute row counts and set-differences. Not fabricated.
- **Sandbox-only execution** (`engine/recovery/sandbox_execution_engine.py`) copies files
  under `data/sandbox/recovery/executed/REC-002/` and never touches `data/gold` or
  `data/silver` production paths. `production_modified: false` is accurate.
- **Human approval gate** (`approve_recovery.py`) — real file-based state transition,
  requires prior `approval_allowed=true` from sandbox verification.
- **Resolved incident record** `data/incidents/INC-20260930-001.json` — internally
  consistent lifecycle (DETECTED → ... → RESOLVED) with real timestamps taken from the
  actual approval/execution artifacts (not synthetic).
- **Dashboard** renders incident, lifecycle, root cause, affected assets, verification,
  and the risk comparison grid from real API responses.

## 3. Technical Debt / Weaknesses

| Area | Issue |
|---|---|
| Duplication | Recovery strategy metadata (REC-001/002/003) is hardcoded independently in `recovery_engine.py`, `risk_engine.py`, and `simulation_engine.py`. `risk_engine.py` does not read the `recovery_strategies.json` that `recovery_engine.py` produces — a change to one will silently desync from the others. |
| Testability | Every "engine" is a top-level script with logic inside `if __name__ == "__main__":` / module scope. Nothing is unit-testable without subprocess execution. `tests/unit` and `tests/integration` are both empty. |
| Hardcoded incident ID | `INC-20260930-001` and fixed file paths are hardcoded throughout `engine/*`, `pipelines/targeted_recovery.py`, `approve_recovery.py`, etc. Nothing is parametrized by incident id. |
| Missing decision layer | No component compares strategies against risk/impact/evidence and produces a recommended strategy with rationale. The "approved" strategy (REC-002) is simply asserted in scripts, not derived. |
| Config management | `config/settings.py` has 5 hardcoded constants. No environment variable loading, no risk weights, no feature flags, no path configuration, no execution-safety switches. `.env.example` lists Databricks/Snowflake/Azure/OpenAI variables that are not referenced anywhere in the code (dead config). |
| Security | `api/main.py` builds file paths as `INCIDENTS_DIR / f"{incident_id}.json"` directly from the URL path parameter with **no validation** — a path-traversal-style input (e.g. `..%2f..%2fsecrets`) is not rejected before path construction. No input validation exists anywhere in the API. |
| Observability | No `logging` usage anywhere; every module uses `print()`. No structured audit trail of incident actions (detected/approved/executed/verified) beyond the ad hoc JSON artifacts. |
| Execution safety | `execution_engine.py` only prints a safety-check result — it does not gate the real `sandbox_execution_engine.py`, which independently re-checks the same conditions. There's no single authorized "can I execute" gate reused by both the CLI and a future API endpoint. No idempotency key — running `sandbox_execution_engine.py` twice would `rmtree` and recopy silently (destructive re-run, not detected as "already executed" until after the fact). |
| API coverage | Only 4 endpoints exist. No endpoints for strategies, decision, impact, verification, audit, prevention, and no POST endpoints for simulate/approval/execute/verify at all — the whole approval/execution flow is CLI-only today. |
| Documentation | `README.md` is empty. `docs/` is empty. No architecture, API, security, or demo docs exist. |
| Dependencies | `requirements.txt` has no test framework (`pytest`, `httpx` for `TestClient`) despite FastAPI being used. |
| Prevention persistence | `prevention_engine.py` only prints; nothing is persisted per-incident (spec calls for `data/incidents/{id}/prevention.json`). |
| Approver identity | `approve_recovery.py` hardcodes `APPROVER = "Rakesh Bontala"` as a module constant — acceptable for a single-operator demo, but not parametrized. |

## 4. Risks

- Any edit to strategy/risk logic in one file without updating the other 2–3 duplicated
  copies will make the UI/API show incorrect or inconsistent numbers.
- The API's unvalidated `incident_id` path parameter is a path-traversal-class defect
  that must be fixed before any additional file-path-based endpoints are added (several
  are requested: strategies, decision, impact, verification, audit, prevention).
- Without an idempotency/execution-state gate exposed to the API, adding a `POST
  /execute` endpoint naively would allow duplicate/destructive re-execution.
- No automated tests means every refactor risks silently breaking the one working
  end-to-end demo scenario.

## 5. Missing Functionality (per requested scope)

- Recovery decision engine (comparison, recommendation, trade-offs, rejected alternatives).
- Configurable, weighted risk model.
- Structured audit event log.
- Persisted prevention recommendations per incident.
- API endpoints: strategies, decision, impact, verification, audit, prevention, and
  guarded POST simulate/approval/execute/verify.
- Test suite (unit + integration), including negative-path tests.
- Documentation set (README, ARCHITECTURE, RECOVERY_DECISION, SECURITY, API, DEMO,
  OPERATIONS, INCIDENT_FLOW).
- Deterministic demo runner.
- Basic CI workflow.

## 6. Recommended Target Architecture

Keep the existing five-layer data flow (raw → bronze → silver → gold, plus sandbox
recovery), but turn every `engine/*` script into an **importable, pure-function core**
with a thin CLI wrapper (`if __name__ == "__main__": main()` stays, for orchestrator
compatibility), so the same logic is callable from the API, tests, and CLI without
subprocess overhead. Concretely:

- `engine/recovery/decision_engine.py` — new deterministic decision layer consuming
  strategies + risk + incident evidence, producing
  `data/sandbox/recovery/decision/recovery_decision.json`.
- `engine/risk/risk_engine.py` — refactored to read
  `data/sandbox/recovery/strategies/recovery_strategies.json` instead of a second
  hardcoded strategy list, with configurable weights from `config/settings.py`.
- `config/settings.py` — expanded to a small typed settings object reading environment
  variables (via `python-dotenv`, already a dependency), exposing paths, risk weights,
  and execution-safety flags (`PRODUCTION_EXECUTION_ENABLED=false` by default).
- `engine/security/identifiers.py` — new shared incident-id / strategy-id validators
  used by both the API and engines to reject unsafe input before any path is built.
- `engine/audit/audit_log.py` — new shared JSONL audit event writer/reader, one file per
  incident under `data/incidents/{id}/audit_log.jsonl`.
- `api/main.py` — expanded with the requested read endpoints plus fail-closed guarded
  POST endpoints that call the same engine functions the CLI uses (no duplicate logic),
  validating incident id/strategy id and current lifecycle state before allowing any
  state-changing action.
- `tests/unit` and `tests/integration` — populated with real tests covering the new
  decision/risk/security logic and the API's safety gating.

## 7. Migration / Refactoring Plan

1. Add configuration, security-validation, and audit-log primitives (additive, no
   behavior change to existing scripts).
2. Refactor `risk_engine.py` to consume the persisted strategies file and configurable
   weights; keep the same output shape so the UI/API contract is unchanged.
3. Add `decision_engine.py` (new artifact + new logic, does not touch existing files).
4. Add prevention persistence (extend `prevention_engine.py` to also write
   `data/incidents/{id}/prevention.json`; keep console output identical).
5. Expand `api/main.py` with new GET endpoints (read-only, additive) and guarded POST
   endpoints that re-use engine functions with fail-closed checks + idempotency.
6. Extend the dashboard to render the new decision/blast-radius/audit data without
   removing any existing card/section.
7. Add unit + integration tests validating both the new logic and the existing
   resolved-incident scenario end to end.
8. Add documentation set and a deterministic `scripts/run_demo.py`.
9. Add minimal CI workflow and an API-only Dockerfile.

No existing data under `data/raw`, `data/bronze`, `data/silver`, `data/gold`,
`data/incidents`, `data/sandbox` will be deleted or overwritten by this plan; new
artifacts are added alongside the existing ones.
