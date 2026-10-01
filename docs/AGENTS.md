# AEGIS Agent Architecture

AEGIS agents are advisory participants around the deterministic engines. They
do not replace detection, RCA, risk, decision, policy, approval, execution, or
verification.

## Responsibilities

| Agent | Input | Output | Restriction |
|---|---|---|---|
| Incident Investigator | Deterministic evidence, RCA, lineage, impact | Root-cause summary, confidence, evidence references, missing evidence | Cannot invent or collect external facts |
| Recovery Strategy Agent | Generated strategies, risk evaluation, decision | Strategy comparison and deterministic recommendation explanation | Cannot create commands, change risk, approve, or execute |
| Recovery Orchestrator | Existing engine functions and bounded incident context | Persisted workflow report ending at human approval | Has no approval, authorization, shell, database, or execution tool |
| Prevention Agent | Passed verification, generated controls, incident memory | Prevention and historical-pattern explanation | Cannot modify production configuration |

## Structured Contract

`IncidentContext` is the canonical bounded input. `AgentResult` includes agent
identity/version, status, summary, confidence, evidence references, concise
reasoning summary, recommendations, warnings, provider metadata, latency, and
fixed safety fields. Constructing a result with
`production_execution_allowed=true` raises an error.

Every cited evidence ID is validated against the supplied context. Unknown
evidence, malformed provider output, conflicting schema facts, missing risk or
strategy data, and failed simulation produce a blocked result.

## Safe Flow

```text
Incident -> deterministic evidence/RCA/impact/strategies/risk/decision
         -> Investigator Agent + Recovery Strategy Agent
         -> sandbox simulation
         -> WAITING_FOR_HUMAN_APPROVAL
         -> existing approval and authorization engines
         -> allowlisted sandbox execution
         -> verification
         -> deterministic prevention + Prevention Agent + incident memory
```

The orchestrator never calls approval, authorization, or execution. Those
remain separate guarded paths.

## Provider Behavior

Deterministic output is always available. `AgentProvider` is an optional prose
enhancement boundary. Provider exceptions are treated as unavailable, malformed
outputs are rejected, and returned evidence is revalidated. No API key is
required for tests or the demo.

## Current Scenario Coverage

| Scenario | Current behavior |
|---|---|
| Additive schema drift | Supported from expected/observed/unexpected schema facts |
| Required column removed | Supported when missing-column evidence is supplied |
| Datatype drift | Blocked until a deterministic detector supplies type-change evidence |
| Duplicate records | Blocked until a deterministic detector supplies duplicate evidence |
| NULL required field | Blocked until a deterministic detector supplies null evidence |
| Invalid status | Blocked until a deterministic rule engine supplies invalid-value evidence |
| Late-arriving data | Blocked until a deterministic freshness detector supplies evidence |
| Multiple simultaneous issues | Blocked until each issue has independently validated evidence |

This boundary is intentional: unsupported incidents report insufficient
evidence rather than allowing the agent to infer logs, metrics, impact, or
recovery actions.