# Demo Guide

## One-command demo

```powershell
& .venv\Scripts\Activate.ps1
python scripts/run_demo.py
```

This runs all 15 stages in-process (no Spark required for the demo path —
detection has already occurred and its evidence is persisted in the
incident record) and prints a numbered progress report:

```
[ 1/15] Collecting evidence ......... PASS
[ 2/15] Root cause analysis ......... PASS
[ 3/15] Calculating blast radius .... PASS
[ 4/15] Calculating business impact ... PASS
[ 5/15] Generating recovery strategies ... PASS
[ 6/15] Evaluating risk ............. PASS
[ 7/15] Generating recovery decision ... PASS
[ 8/15] Simulating recovery (sandbox) ... PASS
[ 9/15] Running agent investigation ... PASS
[10/15] Requesting human approval ... PASS
[11/15] Recording human approval .... PASS
[12/15] Executing sandbox recovery ... PASS
[13/15] Verifying recovery .......... PASS
[14/15] Generating prevention ....... PASS
[15/15] Running prevention agent .... PASS

INCIDENT RESOLVED
Recommended strategy : REC-002 - Targeted Rebuild
Decision confidence   : HIGH
Agent workflow        : WAITING_FOR_HUMAN_APPROVAL
Agent execution       : DISALLOWED (advisory only)
Risk comparison       : REC-001=11 (HIGH_RISK), REC-002=8 (MEDIUM_RISK), REC-003=11 (HIGH_RISK)
Execution scope       : SANDBOX_ONLY
Production modified   : False
Prevention controls   : 4 generated
Prevention agent      : COMPLETED

Production modified: FALSE
AEGIS DEMO COMPLETE
```

Safe to run repeatedly: every stage is idempotent, and no stage modifies
`data/gold` or `data/silver`.

## Measured timing (real, not estimated)

Measured locally with `Measure-Command { python scripts/run_demo.py }` and
cross-checked against `data/incidents/INC-20260930-001/audit_log.jsonl`
event timestamps:

- Full process (interpreter start + all 15 stages + console output): **~0.15s**.
- The 15 logged engine/agent stages themselves (evidence → prevention
  agent, from audit event timestamps): **~12ms**.
- Each advisory agent invocation (`agent_invoked` audit events) reports
  `latency_ms: 0` — negligible overhead over the deterministic engines it reads from.

This is **automated compute time only**. It explicitly excludes: the
original Spark-based schema-drift detection (run separately, requires
Java/Hadoop), and real-world human approval wait time (the demo
auto-approves for repeatability). A baseline "manual investigation" timing
has **not** been measured — do not quote a before/after percentage without
running that comparison first.

## Dashboard walkthrough

```powershell
python -m uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000/` and scroll through:

1. **Hero** — incident id, pipeline, severity, status.
2. **Incident lifecycle** — the 8-stage timeline with real timestamps.
3. **Root cause / affected assets** and **recovery verification** checks.
4. **Agent workflow** — Investigator Agent and Recovery Strategy Agent
   output, evidence references (EV-001..EV-004), and the explicit
   AI/deterministic/human/sandbox/verified boundary — sourced from
   `GET /api/incidents/{id}/agents`.
5. **Recovery risk evaluation** — REC-001/002/003 side by side (11 / 8 / 11).
6. **Recovery decision** — the recommended strategy, why it was chosen, its
   trade-offs, and why the other two were rejected — all sourced from
   `GET /api/incidents/{id}/decision`.
7. **Blast radius** and **prevention** — downstream assets and generated
   prevention controls.
8. **Audit trail** — every recorded engine and agent action, chronologically.

## 10-minute final demo timeline

| Time | Screen | What to say |
|---|---|---|
| 0:00–1:00 | Slide deck | "At 3 AM, a source schema changes. This is the 3 AM Problem." |
| 1:00–2:00 | Incident hero | `customer_segment` appears in `silver.customers`, unapproved. |
| 2:00–3:00 | Evidence panel | "AEGIS detects the contract violation — the pipeline itself is schema-tolerant, it won't crash, so nothing else would have caught this." |
| 3:00–4:00 | Agent workflow panel | "The Investigator Agent explains the root cause from evidence EV-001..EV-004 — it cannot invent evidence." |
| 4:00–5:00 | Blast radius panel | Lineage BFS: 2 downstream assets. |
| 5:00–6:00 | Risk panel | REC-001=11, REC-002=8, REC-003=11 — transparent, configurable formula. |
| 6:00–7:00 | Decision + approval | Recommended REC-002; submit `POST /approval` live, watch the audit trail update. |
| 7:00–8:00 | Execute | `POST /execute`; call out `production_modified: false`. |
| 8:00–9:00 | Verification panel | Schema / row-count / business values, all PASSED. |
| 9:00–10:00 | Prevention + close | 4 controls generated; close with the safety invariant line below. |

Close with the safety invariant: *"AI may recommend. The policy engine
evaluates. A human approves. Execution is allowlisted and sandbox-only.
Verification confirms."*

