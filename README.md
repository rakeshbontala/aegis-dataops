# AEGIS

**AI-Powered Data Incident Recovery & Prevention Engine**

*Detect. Prove. Simulate. Recover. Prevent.*

AEGIS is a deterministic incident-response platform for the "3 AM data
incident problem": a source schema changes, a dataset breaks a contract, or a
pipeline silently drifts — and someone has to figure out what happened, what
it affects, how to fix it safely, and how to stop it from happening again.

> Before changing production, AEGIS evaluates multiple recovery strategies
> against the incident evidence, the dependency graph, data-quality
> constraints and business impact, then presents an auditable recovery
> decision for human approval.

AEGIS is **not** simply a root-cause-analysis tool, and it is **not** a
self-healing pipeline that silently mutates production. It is a
detect → prove → investigate → assess impact → generate options → evaluate
risk → compare → simulate → approve → execute (sandbox-only, allowlisted) →
verify → prevent → remember loop, with a human required in the loop before
anything is executed.

---

## 1. Architecture

```
Detection → Evidence → RCA → Lineage/Impact → Recovery Strategies
    → Risk Evaluation → Decision Engine → Simulation → Human Approval
    → Authorization → Execution (sandbox-only) → Verification
    → Prevention → Incident Memory
```

| Layer | Location | Responsibility |
|---|---|---|
| Detection | `engine/detection/` | Real Spark read of `data/silver/customers` vs `config/customer_schema_contract.json`. |
| Evidence | `engine/evidence/` | Collects the schema-contract evidence attached to the incident record. |
| RCA | `engine/rca/` | Deterministic root-cause classification. |
| Lineage / Impact | `engine/lineage/`, `engine/impact/` | Blast-radius BFS + business-criticality mapping. |
| Strategy generation | `engine/recovery/recovery_engine.py` | Produces REC-001/002/003 (Full Rebuild / Targeted Rebuild / Rollback). |
| Risk evaluation | `engine/risk/risk_engine.py` | Configurable, weighted risk scoring — reads the strategies file (single source of truth), no duplicated constants. |
| **Decision engine** | `engine/recovery/decision_engine.py` | Ranks strategies, recommends one, explains trade-offs and rejected alternatives. Never executes anything. |
| Simulation | `engine/simulation/simulation_engine.py` | Sandbox dry-run validation checks per strategy. |
| Approval | `engine/recovery/approval_engine.py`, `approve_recovery.py` | Human-in-the-loop gate; fail-closed if sandbox verification hasn't passed. |
| Authorization | `engine/recovery/authorization_record.py` | Re-derives whether execution is authorized from current approval + verification state. |
| Execution | `engine/recovery/sandbox_execution_engine.py` | Fail-closed, idempotent, **sandbox-only** copy of the recovered dataset. Production is never touched. |
| Verification | `engine/verification/` | Schema/row-count/business-value checks, before vs after. |
| Prevention | `engine/prevention/prevention_engine.py` | Generates and persists prevention recommendations per incident. |
| Memory | `engine/prevention/incident_memory.py` | Persists a historical fingerprint of the incident. |
| **Advisory AI narration** | `agents/recovery_agent.py` | Optional, isolated layer that rephrases the decision engine's own facts into an executive summary. Off by default; falls back to a deterministic narrative built from the same fields if no LLM is configured. Never influences the recommendation, approval, or execution. |
| **Operational agents** | `agents/investigator_agent.py`, `recovery_strategy_agent.py`, `orchestrator_agent.py`, `prevention_agent.py` | Structured, evidence-grounded investigation, strategy explanation, safe orchestration, and prevention analysis. The orchestrator stops for human approval and has no direct execution tool. |
| Audit | `engine/audit/audit_log.py` | Append-only JSONL audit trail per incident. |
| Security | `engine/security/identifiers.py` | Allowlist validation for incident/strategy ids and actor names (path-traversal/injection defense). |
| Config | `config/settings.py` | Environment-driven paths, risk weights, execution-safety flags, feature flags. |
| API | `api/main.py` | FastAPI surface over all of the above. |
| UI | `ui/static/` | Dark-themed operations dashboard. |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/ARCHITECTURE_AUDIT.md](docs/ARCHITECTURE_AUDIT.md) for the full audit
and target-architecture rationale.

## 2. The production-safety invariant

```
AI / engines MAY RECOMMEND.
POLICY (config/settings.py execution_safety) MAY EVALUATE.
A HUMAN MUST APPROVE.
THE EXECUTION ENGINE MAY EXECUTE ONLY ALLOWLISTED, SANDBOX-SCOPED ACTIONS.
VERIFICATION MUST CONFIRM THE RESULT.
```

- `AEGIS_PRODUCTION_EXECUTION_ENABLED` defaults to `false`.
- `sandbox_execution_engine.execute_recovery()` fails closed: missing
  authorization, wrong strategy, unauthorized incident, or a disallowed
  execution scope all raise `ExecutionBlockedError` (→ HTTP 409) instead of
  proceeding.
- Execution is **idempotent**: re-invoking it for an already-executed
  incident/strategy returns the existing record unchanged (no duplicate
  copies, no corrupted output).

## 3. Setup

```powershell
# from the repository root
python -m venv .venv
& .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Spark-backed steps (schema detection, recovery verification) require Java 17
and, on Windows, Hadoop's `winutils`/`hadoop.dll` on `PATH`:

```powershell
$env:HADOOP_HOME = "C:\Aegis\hadoop-3.5.0"
$env:PATH = "$env:HADOOP_HOME\bin;" + $env:PATH
```

Copy `.env.example` to `.env` and adjust if needed (all values have safe
defaults; production execution stays disabled unless explicitly enabled).

## 4. Running the system

```powershell
# API + dashboard
python -m uvicorn api.main:app --reload
# then open http://127.0.0.1:8000/
```

```powershell
# Full deterministic + agent demo (15-step, safe to re-run)
python scripts/run_demo.py
```

```powershell
# Individual engine stages (subprocess-orchestrated)
python -m engine.orchestrator
```

## 5. Tests

```powershell
python -m pytest tests/ -v
```

63 tests across `tests/unit` and `tests/integration`, including negative
paths: execution blocked without authorization, wrong strategy blocked,
rejected approvals cannot be silently re-approved, duplicate execution is
idempotent (not destructive), malformed incident/strategy ids are rejected
everywhere they could reach a file path.

## 6. Demo scenario

Incident `INC-20260930-001`: `customer_segment` appears in
`silver.customers` without an approved schema-contract update
(`config/customer_schema_contract.json` has `allow_new_columns: false`).
AEGIS detects the **contract violation** — the downstream Spark pipeline is
schema-tolerant and does not actually fail, and AEGIS does not claim it does.

AEGIS generates three recovery strategies, evaluates their risk (11 / 8 /
11), recommends **REC-002 (Targeted Rebuild)** because it has the lowest
risk score and smallest blast radius, simulates it in a sandbox, requires
and records human approval, executes only the sandbox-scoped, allowlisted
copy, verifies schema/row-count/business values (all PASSED), confirms
`production_modified: false`, and generates prevention recommendations.

## 7. API

See [docs/API.md](docs/API.md) for the full endpoint reference. Summary:

```
GET  /health
GET  /api/incidents
GET  /api/incidents/{id}
GET  /api/incidents/{id}/risk
GET  /api/incidents/{id}/strategies
GET  /api/incidents/{id}/decision
GET  /api/incidents/{id}/explanation
GET  /api/incidents/{id}/impact
GET  /api/incidents/{id}/verification
GET  /api/incidents/{id}/audit
GET  /api/incidents/{id}/prevention
GET  /api/incidents/{id}/agents
GET  /api/incidents/{id}/memory

POST /api/incidents/{id}/investigate
POST /api/incidents/{id}/prevention/analyze
POST /api/incidents/{id}/simulate
POST /api/incidents/{id}/approval   { strategy_id, decision, approver }
POST /api/incidents/{id}/execute    ?strategy_id=...
POST /api/incidents/{id}/verify
```

Every incident/strategy id is validated against an allowlist regex
(`engine/security/identifiers.py`) before it is used to build any file path.

## 8. UI

`ui/static/` — a single-page dashboard (no build step) that renders, from
live API data: incident summary, lifecycle timeline, root cause, affected
assets, recovery risk comparison, the AEGIS recommendation with its
reasoning and rejected alternatives, blast radius, prevention
recommendations, structured agent investigation with evidence references,
verification results, and a full audit trail. Nothing on
the dashboard is hardcoded to look "approved" — the approval badge is
derived from the actual audit log.

## 9. Limitations

- The AI narration layer (`agents/recovery_agent.py`) is off by default and,
  even when enabled with `OPENAI_API_KEY`, only rephrases facts the
  deterministic decision engine already computed — it is not a
  recommendation model and cannot be asked to decide anything.
- The demo incident (`INC-20260930-001`) and its three strategies are the
  only fully wired end-to-end scenario; strategy generation itself is still
  a fixed catalog rather than dynamically synthesized from arbitrary
  incidents.
- Production execution is implemented as a policy flag
  (`AEGIS_PRODUCTION_EXECUTION_ENABLED`) that is always `false` today —
  there is no production execution *engine* to enable, by design, until an
  allowlisted production action is explicitly implemented and reviewed.
- No authentication/authorization layer sits in front of the API — it is a
  local/demo deployment, not exposed to the public internet.
- Detection currently targets one schema contract (`customer_schema_contract.json`)
  for one pipeline; it is not a generic multi-pipeline monitoring service.
- The investigator supports additive schema drift and required-column removal
  when deterministic schema evidence is supplied. Datatype drift, duplicates,
  null violations, invalid statuses, late data, and combined failures remain
  fail-closed until deterministic detectors are implemented for those facts.

## 10. Future improvements

- Multi-incident, multi-pipeline detection and strategy generation.
- Pluggable LLM-backed recommendation layer behind `agents/`, kept strictly
  advisory (see the safety invariant above) — not implemented today.
- Persisted, queryable incident-memory similarity search across many
  historical incidents (today: one JSON fingerprint per incident).
- Auth/RBAC for the API and dashboard.

---

**This project is not described as "production-ready."** It has real tests,
real fail-closed safety gates, and a real audit trail for one complete
incident scenario — but broader hardening (auth, multi-tenant detection,
production execution allowlisting) has not been implemented or verified yet.
