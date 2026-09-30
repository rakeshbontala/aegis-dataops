# Recovery Decision Engine

`engine/recovery/decision_engine.py` — `generate_decision(incident_id)`

## What it does

1. Loads the persisted recovery strategies
   (`data/sandbox/recovery/strategies/recovery_strategies.json`).
2. Loads the persisted risk evaluation
   (`data/sandbox/recovery/risk/risk_evaluation.json`).
3. Loads the incident record (root cause, evidence, affected assets).
4. Calls `engine.impact.impact_engine.analyze_impact()` and
   `engine.lineage.lineage_engine.analyze_lineage()` **in-process** (not by
   re-reading possibly-stale files) to get business criticality and blast
   radius.
5. Ranks strategies deterministically by
   `(risk_score, len(scope), strategy_id)` — lowest risk first, ties broken
   by smaller blast radius, then by id for stability.
6. Persists `data/sandbox/recovery/decision/recovery_decision.json`.

## What it never does

- It never calls the approval, authorization, or execution engines.
- It never sets `approval_status` or `execution_status`.
- `production_execution_allowed` in its output is read directly from
  `settings.execution_safety.production_execution_enabled` (default
  `False`) — the decision engine cannot override policy.

## Output shape

```json
{
  "incident_id": "...",
  "evaluated_strategies": [ { "strategy_id": "...", "risk_score": ..., "scope": [...], "business_critical_assets_in_scope": [...] }, ... ],
  "recommended_strategy": { "strategy_id": "REC-002", "name": "...", "risk_score": 8, "risk_classification": "MEDIUM_RISK" },
  "decision_factors": [ "REC-002 has the lowest weighted risk score ..." ],
  "tradeoffs": [ "REC-002 does not rebuild raw.customers directly; ..." ],
  "rejected_alternatives": [ { "strategy_id": "REC-001", "reasons": [ "risk score 11 (HIGH_RISK) is higher than REC-002's 8.", "larger blast radius (4 assets vs 3)." ] }, ... ],
  "confidence": "HIGH",
  "blast_radius": { "starting_asset": "silver.customers", "impacted_assets": [...] },
  "human_approval_required": true,
  "production_execution_allowed": false
}
```

## Confidence

`confidence` is computed from the risk-score gap between the top-ranked and
runner-up strategy — not an LLM self-assessment:

```python
def _confidence_label(margin: float) -> str:
    if margin >= 3: return "HIGH"
    if margin >= 1: return "MEDIUM"
    return "LOW"
```

For the demo incident, margin = 11 − 8 = 3 → `HIGH`.

## Why REC-002 is recommended

REC-001 (Full Rebuild): risk 11, scope 4 assets.
REC-002 (Targeted Rebuild): risk 8, scope 3 assets, LOW data-loss risk.
REC-003 (Rollback): risk 11, scope 5 assets, MEDIUM data-loss risk (would
discard the newly introduced `customer_segment` column per the simulation).

REC-002 wins on every axis: lowest risk score, smallest blast radius, lowest
data-loss risk. This matches the strategy that was independently
human-approved in the original incident record — the decision engine's
output is consistent with, not fabricated to match, that history.

## No fake AI

No LLM is involved in the ranking, scoring, or recommendation logic on this
page — all of it is deterministic and computed above.

An optional, isolated narration layer exists at `agents/recovery_agent.py`
(`GET /api/incidents/{id}/explanation`): it is **off by default**
(`AEGIS_ENABLE_AI_RECOMMENDATIONS=false`), and even when enabled with an
`OPENAI_API_KEY`, it only rephrases the exact fields already produced by
`generate_decision()` into an executive summary — it is not permitted to
introduce new claims, and it falls back to a deterministic, template-built
narrative (still derived from real fields, just not LLM-phrased) on any
missing dependency, missing credential, or API error. The API response
always reports which path was used via `"source": "deterministic" | "llm"`,
and the dashboard displays that source badge honestly rather than implying
AI involvement that didn't happen.

This module, the policy engine (`config/settings.py`), and the human
approval gate are what actually decide — the narration layer cannot.
