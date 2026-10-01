"""Shared interface for AEGIS advisory agents.

AI MAY RECOMMEND. It never decides, never approves, never executes.
Every agent must work correctly with no external model configured — the
LLM path is strictly an optional narration upgrade over an always-available
deterministic explanation built from real, already-computed evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol

AgentStatus = Literal["COMPLETED", "BLOCKED", "FAILED"]
Confidence = Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT_EVIDENCE"]


@dataclass(frozen=True)
class EvidenceReference:
    evidence_id: str
    supports: str
    source: str
    fact: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "supports": self.supports,
            "source": self.source,
            "fact": self.fact,
        }


@dataclass(frozen=True)
class IncidentContext:
    """Canonical, bounded view of deterministic facts available to agents."""

    incident_id: str
    incident: Mapping[str, Any]
    evidence: tuple[EvidenceReference, ...] = ()
    root_cause: Mapping[str, Any] = field(default_factory=dict)
    lineage: Mapping[str, Any] = field(default_factory=dict)
    business_impact: Mapping[str, Any] = field(default_factory=dict)
    recovery_strategies: Mapping[str, Any] = field(default_factory=dict)
    risk_results: Mapping[str, Any] = field(default_factory=dict)
    decision: Mapping[str, Any] = field(default_factory=dict)
    simulation_result: Mapping[str, Any] = field(default_factory=dict)
    verification_result: Mapping[str, Any] = field(default_factory=dict)
    prevention: Mapping[str, Any] = field(default_factory=dict)
    incident_memory: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    """Auditable agent output containing summaries, never hidden reasoning."""

    agent: str
    agent_role: str
    agent_version: str
    incident_id: str
    status: AgentStatus
    summary: str
    confidence: Confidence
    evidence: tuple[EvidenceReference, ...] = ()
    reasoning_summary: str = ""
    recommendations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    provider: str = "deterministic"
    model: str | None = None
    latency_ms: int | None = None
    requires_human_approval: bool = True
    production_execution_allowed: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Agent evidence references must be unique.")
        if self.production_execution_allowed:
            raise ValueError("Advisory agents cannot allow production execution.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "agent_role": self.agent_role,
            "agent_version": self.agent_version,
            "incident_id": self.incident_id,
            "status": self.status,
            "summary": self.summary,
            "confidence": self.confidence,
            "evidence": [item.to_dict() for item in self.evidence],
            "reasoning_summary": self.reasoning_summary,
            "recommendations": list(self.recommendations),
            "warnings": list(self.warnings),
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "requires_human_approval": self.requires_human_approval,
            "production_execution_allowed": self.production_execution_allowed,
            "details": dict(self.details),
        }


class AgentProvider(Protocol):
    name: str
    model: str | None

    def enhance(self, result: AgentResult) -> AgentResult:
        """Optionally enhance prose without changing deterministic facts."""
        ...


@dataclass(frozen=True)
class AgentResponse:
    narrative: str
    source: Literal["deterministic", "llm"]
    model: str | None = None


class AgentUnavailableError(Exception):
    """Raised internally when the LLM path cannot be used; callers should
    catch this and fall back to the deterministic narrative, never crash."""


def validate_agent_result(result: AgentResult, context: IncidentContext) -> None:
    """Reject outputs that cite facts outside the bounded incident context."""
    if result.incident_id != context.incident_id:
        raise ValueError("Agent result does not match the incident context.")

    available_evidence = {item.evidence_id for item in context.evidence}
    unknown_evidence = {
        item.evidence_id for item in result.evidence
    } - available_evidence
    if unknown_evidence:
        unknown = ", ".join(sorted(unknown_evidence))
        raise ValueError(f"Agent result cites unknown evidence: {unknown}")


def apply_provider(
    provider: AgentProvider,
    result: AgentResult,
    context: IncidentContext,
) -> AgentResult:
    """Use an optional provider without making it a workflow dependency."""
    try:
        enhanced = provider.enhance(result)
    except Exception as error:  # noqa: BLE001 - provider failure is non-fatal
        raise AgentUnavailableError(str(error)) from error

    if not isinstance(enhanced, AgentResult):
        raise ValueError("Agent provider returned malformed output.")
    validate_agent_result(enhanced, context)
    return enhanced
