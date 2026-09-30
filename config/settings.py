"""Central, environment-driven configuration for AEGIS.

All configurable values (paths, risk weights, feature flags, execution
safety switches) live here instead of being scattered/hardcoded across
`engine/*` modules. Values are read from environment variables (loaded
from a local `.env` file if present) with safe defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a local .env file, if present. Never commit secrets.
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


# --------------------------------------------------------------------------
# Application identity
# --------------------------------------------------------------------------
APP_NAME = _env_str("AEGIS_APP_NAME", "AEGIS")
APP_VERSION = "0.2.0"
APP_ENV = _env_str("AEGIS_ENV", "development")
LOG_LEVEL = _env_str("AEGIS_LOG_LEVEL", "INFO")
SPARK_MASTER = _env_str("SPARK_MASTER", "local[2]")


@dataclass(frozen=True)
class RiskWeights:
    """Configurable weighted factors used by the risk engine.

    Kept backward compatible with the original unweighted formula
    (execution_risk + runtime_risk + data_loss_risk + impact_scope) when
    all weights are left at 1.0.
    """

    execution: float = _env_float("AEGIS_RISK_WEIGHT_EXECUTION", 1.0)
    runtime: float = _env_float("AEGIS_RISK_WEIGHT_RUNTIME", 1.0)
    data_loss: float = _env_float("AEGIS_RISK_WEIGHT_DATA_LOSS", 1.0)
    impact_scope: float = _env_float("AEGIS_RISK_WEIGHT_IMPACT_SCOPE", 1.0)

    # Score thresholds (inclusive lower bound) mapped to classifications.
    high_risk_threshold: float = _env_float("AEGIS_RISK_HIGH_THRESHOLD", 10.0)
    medium_risk_threshold: float = _env_float("AEGIS_RISK_MEDIUM_THRESHOLD", 7.0)
    blocked_risk_threshold: float = _env_float("AEGIS_RISK_BLOCKED_THRESHOLD", 999.0)


@dataclass(frozen=True)
class ExecutionSafety:
    """Fail-closed production execution safeguards.

    Production execution is disabled by default. Enabling it requires an
    explicit environment variable AND is still subject to every safety
    gate (approval, authorization, verification, allowlisting) enforced
    by the execution engine.
    """

    production_execution_enabled: bool = _env_bool(
        "AEGIS_PRODUCTION_EXECUTION_ENABLED", False
    )
    human_approval_required: bool = _env_bool(
        "AEGIS_HUMAN_APPROVAL_REQUIRED", True
    )
    allowlisted_execution_scopes: tuple[str, ...] = ("SANDBOX_ONLY",)


@dataclass(frozen=True)
class DataPaths:
    """Canonical, project-relative data locations."""

    root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / "data"
    incidents_dir: Path = PROJECT_ROOT / "data" / "incidents"
    historical_dir: Path = PROJECT_ROOT / "data" / "historical"
    raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    bronze_dir: Path = PROJECT_ROOT / "data" / "bronze"
    silver_dir: Path = PROJECT_ROOT / "data" / "silver"
    gold_dir: Path = PROJECT_ROOT / "data" / "gold"
    sandbox_recovery_dir: Path = PROJECT_ROOT / "data" / "sandbox" / "recovery"
    schema_contract_file: Path = PROJECT_ROOT / "config" / "customer_schema_contract.json"


@dataclass(frozen=True)
class FeatureFlags:
    enable_ai_recommendations: bool = _env_bool("AEGIS_ENABLE_AI_RECOMMENDATIONS", False)
    enable_audit_log: bool = _env_bool("AEGIS_ENABLE_AUDIT_LOG", True)


@dataclass(frozen=True)
class Settings:
    app_name: str = APP_NAME
    app_version: str = APP_VERSION
    app_env: str = APP_ENV
    log_level: str = LOG_LEVEL
    spark_master: str = SPARK_MASTER
    risk_weights: RiskWeights = field(default_factory=RiskWeights)
    execution_safety: ExecutionSafety = field(default_factory=ExecutionSafety)
    paths: DataPaths = field(default_factory=DataPaths)
    features: FeatureFlags = field(default_factory=FeatureFlags)


settings = Settings()
