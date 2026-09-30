# Demo Guide

## One-command demo

```powershell
& .venv\Scripts\Activate.ps1
python scripts/run_demo.py
```

This runs all 12 stages in-process (no Spark required for the demo path —
detection has already occurred and its evidence is persisted in the
incident record) and prints a numbered progress report:

```
[ 1/12] Collecting evidence ......... PASS
[ 2/12] Root cause analysis ......... PASS
[ 3/12] Calculating blast radius .... PASS
[ 4/12] Calculating business impact ... PASS
[ 5/12] Generating recovery strategies ... PASS
[ 6/12] Evaluating risk ............. PASS
[ 7/12] Generating recovery decision ... PASS
[ 8/12] Simulating recovery (sandbox) ... PASS
[ 9/12] Requesting human approval ... PASS
[10/12] Recording human approval .... PASS
[11/12] Executing sandbox recovery ... PASS
[12/12] Verifying recovery .......... PASS

INCIDENT RESOLVED
Recommended strategy : REC-002 - Targeted Rebuild
Decision confidence   : HIGH
Risk comparison       : REC-001=11 (HIGH_RISK), REC-002=8 (MEDIUM_RISK), REC-003=11 (HIGH_RISK)
Execution scope       : SANDBOX_ONLY
Production modified   : False
Prevention controls   : 4 generated

Production modified: FALSE
AEGIS DEMO COMPLETE
```

Safe to run repeatedly: every stage is idempotent, and no stage modifies
`data/gold` or `data/silver`.

## Dashboard walkthrough

```powershell
python -m uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000/` and scroll through:

1. **Hero** — incident id, pipeline, severity, status.
2. **Incident lifecycle** — the 8-stage timeline with real timestamps.
3. **Root cause / affected assets** and **recovery verification** checks.
4. **Recovery risk evaluation** — REC-001/002/003 side by side (11 / 8 / 11).
5. **Recovery decision** — the recommended strategy, why it was chosen, its
   trade-offs, and why the other two were rejected — all sourced from
   `GET /api/incidents/{id}/decision`.
6. **Blast radius** and **prevention** — downstream assets and generated
   prevention controls.
7. **Audit trail** — every recorded engine action, chronologically.

## Suggested narration (5–7 minutes)

1. *"At 3 AM, a source schema changes."* — `customer_segment` appears in
   `silver.customers`.
2. *"AEGIS detects the contract violation"* — not a pipeline failure claim;
   the Spark pipeline is schema-tolerant, and AEGIS says so.
3. *"AEGIS proves what changed"* — evidence panel, exact column diff.
4. *"AEGIS investigates"* — root cause + blast radius (2 downstream assets).
5. *"AEGIS generates and compares recovery strategies"* — risk panel.
6. *"AEGIS recommends, with reasons"* — decision panel: factors, trade-offs,
   rejected alternatives.
7. *"AEGIS simulates safely"* — sandbox dry run, no production impact.
8. *"A human approves"* — real approver, real timestamp, in the audit trail.
9. *"AEGIS executes only the approved, sandboxed, allowlisted action"* —
   execution scope `SANDBOX_ONLY`, `production_modified: false`.
10. *"AEGIS verifies"* — schema/rows/business values, all PASSED.
11. *"AEGIS prevents recurrence"* — 4 prevention controls generated.
12. Close with the safety invariant: *"AI may recommend. The policy engine
    evaluates. A human approves. Execution is allowlisted. Verification
    confirms."*
