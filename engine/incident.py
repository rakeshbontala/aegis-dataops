from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Incident:
    incident_id: str
    pipeline_name: str
    severity: str
    status: str
    detected_at: datetime
    error_type: str
    error_message: str
    affected_assets: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    root_cause: str | None = None
