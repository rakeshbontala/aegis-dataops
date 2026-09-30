"""Shared interface for AEGIS advisory agents.

AI MAY RECOMMEND. It never decides, never approves, never executes.
Every agent must work correctly with no external model configured — the
LLM path is strictly an optional narration upgrade over an always-available
deterministic explanation built from real, already-computed evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AgentResponse:
    narrative: str
    source: Literal["deterministic", "llm"]
    model: str | None = None


class AgentUnavailableError(Exception):
    """Raised internally when the LLM path cannot be used; callers should
    catch this and fall back to the deterministic narrative, never crash."""
