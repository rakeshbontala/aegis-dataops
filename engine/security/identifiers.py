"""Shared input validation for untrusted identifiers.

Any incident id, strategy id, or actor name that is used to build a file
path or is echoed back into API responses must first pass through these
validators. This prevents path traversal and injection via crafted
identifiers (OWASP A03: Injection / path traversal).
"""

from __future__ import annotations

import re

# INC-YYYYMMDD-NNN, e.g. INC-20260930-001
INCIDENT_ID_PATTERN = re.compile(r"^INC-\d{8}-\d{3}$")

# REC-NNN, e.g. REC-002
STRATEGY_ID_PATTERN = re.compile(r"^REC-\d{3}$")

# Printable, restricted actor-name charset (letters, numbers, spaces, . _ -)
ACTOR_NAME_PATTERN = re.compile(r"^[A-Za-z0-9 ._-]{1,64}$")


class InvalidIdentifierError(ValueError):
    """Raised when an untrusted identifier fails validation."""


def validate_incident_id(incident_id: str) -> str:
    if not isinstance(incident_id, str) or not INCIDENT_ID_PATTERN.match(incident_id):
        raise InvalidIdentifierError(f"Invalid incident id: {incident_id!r}")
    return incident_id


def validate_strategy_id(strategy_id: str) -> str:
    if not isinstance(strategy_id, str) or not STRATEGY_ID_PATTERN.match(strategy_id):
        raise InvalidIdentifierError(f"Invalid strategy id: {strategy_id!r}")
    return strategy_id


def validate_actor_name(actor: str) -> str:
    if not isinstance(actor, str) or not ACTOR_NAME_PATTERN.match(actor):
        raise InvalidIdentifierError(f"Invalid actor name: {actor!r}")
    return actor


def is_valid_incident_id(incident_id: str) -> bool:
    return isinstance(incident_id, str) and bool(INCIDENT_ID_PATTERN.match(incident_id))


def is_valid_strategy_id(strategy_id: str) -> bool:
    return isinstance(strategy_id, str) and bool(STRATEGY_ID_PATTERN.match(strategy_id))
