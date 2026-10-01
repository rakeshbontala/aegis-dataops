from pathlib import Path
import json
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents.orchestrator_agent import RecoveryOrchestratorAgent, load_agent_report
from config.settings import settings
from engine.audit.audit_log import read_events
from engine.prevention.incident_memory import find_similar_incidents
from engine.recovery.approve_recovery import ApprovalError, decide_approval
from engine.recovery.authorization_record import authorize
from engine.recovery.sandbox_execution_engine import ExecutionBlockedError, execute_recovery
from engine.security.identifiers import is_valid_incident_id, is_valid_strategy_id
from engine.simulation.simulation_engine import run_simulation
from engine.verification.verification_engine import run_verification_checklist
from agents.recovery_agent import explain_recovery_decision

BASE_DIR = Path(__file__).resolve().parent.parent
INCIDENTS_DIR = settings.paths.incidents_dir
RECOVERY_DIR = settings.paths.sandbox_recovery_dir
RISK_FILE = RECOVERY_DIR / "risk" / "risk_evaluation.json"
STRATEGY_FILE = RECOVERY_DIR / "strategies" / "recovery_strategies.json"
DECISION_FILE = RECOVERY_DIR / "decision" / "recovery_decision.json"
IMPACT_FILE = RECOVERY_DIR / "impact" / "impact_analysis.json"
LINEAGE_FILE = RECOVERY_DIR / "lineage" / "lineage_analysis.json"
RECOVERY_VERIFICATION_FILE = RECOVERY_DIR / "verification" / "recovery_verification.json"
POST_EXECUTION_FILE = RECOVERY_DIR / "verification" / "post_execution_verification.json"
POST_DATA_FILE = RECOVERY_DIR / "verification" / "post_execution_data_verification.json"
UI_DIR = BASE_DIR / "ui" / "static"


app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Data Incident Recovery & Prevention Engine",
    version=settings.app_version,
)


app.mount("/static", StaticFiles(directory=UI_DIR), name="static")


def _require_valid_incident_id(incident_id: str) -> None:
    """Reject malformed incident ids before any path is built (OWASP A03)."""
    if not is_valid_incident_id(incident_id):
        raise HTTPException(status_code=400, detail=f"Invalid incident id: {incident_id!r}")


def _require_valid_strategy_id(strategy_id: str) -> None:
    if not is_valid_strategy_id(strategy_id):
        raise HTTPException(status_code=400, detail=f"Invalid strategy id: {strategy_id!r}")


def _load_incident(incident_id: str) -> dict[str, Any]:
    _require_valid_incident_id(incident_id)
    incident_file = INCIDENTS_DIR / f"{incident_id}.json"

    if not incident_file.exists():
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")

    with incident_file.open("r", encoding="utf-8") as file:
        return json.load(file)


def _load_artifact(path: Path, incident_id: str, label: str) -> dict[str, Any]:
    _require_valid_incident_id(incident_id)

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{label} not found for incident: {incident_id}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if data.get("incident_id") != incident_id:
        raise HTTPException(status_code=404, detail=f"{label} not found for incident: {incident_id}")

    return data


@app.get("/")
def dashboard():
    return FileResponse(UI_DIR / "index.html")


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "production_execution_enabled": settings.execution_safety.production_execution_enabled,
    }


@app.get("/api/incidents")
def list_incidents():
    incidents = []

    for incident_file in sorted(INCIDENTS_DIR.glob("*.json")):
        with incident_file.open("r", encoding="utf-8") as file:
            incident = json.load(file)

        incidents.append(
            {
                "incident_id": incident.get("incident_id"),
                "pipeline_name": incident.get("pipeline_name"),
                "severity": incident.get("severity"),
                "status": incident.get("status"),
                "error_type": incident.get("error_type"),
            }
        )

    return {"incident_count": len(incidents), "incidents": incidents}


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    return _load_incident(incident_id)


@app.get("/api/incidents/{incident_id}/risk")
def get_incident_risk(incident_id: str):
    return _load_artifact(RISK_FILE, incident_id, "Risk evaluation")


@app.get("/api/incidents/{incident_id}/strategies")
def get_incident_strategies(incident_id: str):
    return _load_artifact(STRATEGY_FILE, incident_id, "Recovery strategies")


@app.get("/api/incidents/{incident_id}/decision")
def get_incident_decision(incident_id: str):
    return _load_artifact(DECISION_FILE, incident_id, "Recovery decision")


@app.get("/api/incidents/{incident_id}/explanation")
def get_incident_explanation(incident_id: str):
    """Advisory-only narration of the decision engine's output.

    AI (if configured) may only rephrase these already-computed facts; it
    never influences the recommendation, approval, or execution.
    """
    incident = _load_incident(incident_id)
    decision = _load_artifact(DECISION_FILE, incident_id, "Recovery decision")

    response = explain_recovery_decision(decision, incident)

    return {
        "incident_id": incident_id,
        "narrative": response.narrative,
        "source": response.source,
        "model": response.model,
    }


@app.get("/api/incidents/{incident_id}/impact")
def get_incident_impact(incident_id: str):
    impact = _load_artifact(IMPACT_FILE, incident_id, "Impact analysis")

    blast_radius = None
    if LINEAGE_FILE.exists():
        lineage = json.loads(LINEAGE_FILE.read_text(encoding="utf-8"))
        if lineage.get("incident_id") == incident_id:
            blast_radius = lineage

    return {**impact, "blast_radius": blast_radius}


@app.get("/api/incidents/{incident_id}/verification")
def get_incident_verification(incident_id: str):
    _require_valid_incident_id(incident_id)

    verification: dict[str, Any] = {"incident_id": incident_id}
    found = False

    for key, path in (
        ("sandbox_verification", RECOVERY_VERIFICATION_FILE),
        ("post_execution_verification", POST_EXECUTION_FILE),
        ("post_execution_data_verification", POST_DATA_FILE),
    ):
        if path.exists():
            verification[key] = json.loads(path.read_text(encoding="utf-8"))
            found = True

    if not found:
        raise HTTPException(status_code=404, detail=f"No verification artifacts found for incident: {incident_id}")

    return verification


@app.get("/api/incidents/{incident_id}/audit")
def get_incident_audit(incident_id: str):
    _require_valid_incident_id(incident_id)
    events = read_events(incident_id)
    return {"incident_id": incident_id, "event_count": len(events), "events": events}


@app.get("/api/incidents/{incident_id}/prevention")
def get_incident_prevention(incident_id: str):
    _require_valid_incident_id(incident_id)
    prevention_file = INCIDENTS_DIR / incident_id / "prevention.json"

    if not prevention_file.exists():
        raise HTTPException(status_code=404, detail=f"Prevention recommendations not found for incident: {incident_id}")

    return json.loads(prevention_file.read_text(encoding="utf-8"))


@app.get("/api/incidents/{incident_id}/agents")
def get_incident_agent_report(incident_id: str):
    _load_incident(incident_id)
    try:
        return load_agent_report(incident_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/incidents/{incident_id}/memory")
def get_incident_memory(incident_id: str):
    _load_incident(incident_id)
    memory_file = settings.paths.historical_dir / f"{incident_id}.json"
    if not memory_file.exists():
        raise HTTPException(status_code=404, detail=f"Incident memory not found: {incident_id}")
    memory = json.loads(memory_file.read_text(encoding="utf-8"))
    return {**memory, "similar_incidents": find_similar_incidents(incident_id)}


# --------------------------------------------------------------------------
# Guarded state-changing endpoints.
#
# These never bypass human approval and never execute anything against
# production. Every check is fail-closed: on any missing precondition the
# request is rejected (4xx) rather than silently proceeding.
# --------------------------------------------------------------------------


@app.post("/api/incidents/{incident_id}/investigate")
def investigate_incident(incident_id: str):
    _load_incident(incident_id)
    try:
        return RecoveryOrchestratorAgent().run_analysis(incident_id)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/incidents/{incident_id}/prevention/analyze")
def analyze_incident_prevention(incident_id: str):
    _load_incident(incident_id)
    result = RecoveryOrchestratorAgent().run_post_recovery(incident_id)
    if result.get("workflow_status") == "BLOCKED":
        raise HTTPException(status_code=409, detail=result.get("reason", "Agent workflow blocked."))
    return result


@app.post("/api/incidents/{incident_id}/simulate")
def simulate_recovery(incident_id: str):
    _load_incident(incident_id)

    if not STRATEGY_FILE.exists():
        raise HTTPException(status_code=409, detail="Recovery strategies have not been generated yet.")

    return run_simulation(incident_id)


class ApprovalRequest(BaseModel):
    strategy_id: str
    decision: Literal["APPROVE", "REJECT"]
    approver: str


@app.post("/api/incidents/{incident_id}/approval")
def submit_approval(incident_id: str, request: ApprovalRequest):
    _load_incident(incident_id)
    _require_valid_strategy_id(request.strategy_id)

    try:
        approval = decide_approval(
            incident_id=incident_id,
            strategy_id=request.strategy_id,
            decision=request.decision,
            approver=request.approver,
        )
    except ApprovalError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    if approval.get("approval_status") == "APPROVED":
        authorize(incident_id=incident_id, strategy_id=request.strategy_id)

    return approval


@app.post("/api/incidents/{incident_id}/execute")
def execute_incident_recovery(incident_id: str, strategy_id: str):
    _load_incident(incident_id)
    _require_valid_strategy_id(strategy_id)

    if not settings.execution_safety.human_approval_required:
        raise HTTPException(status_code=500, detail="Server misconfiguration: human approval must remain required.")

    try:
        record = execute_recovery(incident_id=incident_id, strategy_id=strategy_id)
    except ExecutionBlockedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return record


@app.post("/api/incidents/{incident_id}/verify")
def verify_incident_recovery(incident_id: str):
    _load_incident(incident_id)
    return run_verification_checklist(incident_id)