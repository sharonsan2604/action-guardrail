import os
import time
import logging
import inspect
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from multi_layer_guardrail import MultiLayerGuardrail
from behaviour_monitor import BehaviourMonitor
from pattern_detector import PatternDetector
from database import get_session, AuditEntry
from audit_log import AuditLog
from tools import TOOL_REGISTRY
from agent import Agent
import threading

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("guardrail.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Action Guardrail API",
    description="REST API for validating and auditing AI Agent actions",
    version="1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Core services
guardrail = MultiLayerGuardrail()
audit_log = AuditLog()
agent = Agent()

# Global Session Store mapping session_id -> session state
SESSION_STORE = {}

def get_agent_context(agent_id: str, purpose: str, tool: str, params: dict) -> dict:
    now = datetime.now()
    session_id = f"session-{agent_id}"
    if session_id not in SESSION_STORE:
        SESSION_STORE[session_id] = {
            "session_id": session_id,
            "session_start_time": now.isoformat(),
            "action_count_this_session": 0,
            "tables_accessed_this_session": [],
            "paths_accessed_this_session": [],
            "emails_sent_this_session": 0,
            "current_hour": now.hour
        }
    
    session = SESSION_STORE[session_id]
    session["action_count_this_session"] += 1
    session["current_hour"] = now.hour
    
    if tool == "delete_records":
        table = params.get("table")
        if table and table not in session["tables_accessed_this_session"]:
            session["tables_accessed_this_session"].append(table)
    elif tool == "read_file":
        path = params.get("path")
        if path and path not in session["paths_accessed_this_session"]:
            session["paths_accessed_this_session"].append(path)
    elif tool == "send_email":
        session["emails_sent_this_session"] += 1
        
    if "previous_actions" not in session:
        session["previous_actions"] = []
    
    prev_actions = list(session["previous_actions"])
    
    # Store action for next queries
    action_summary = f"{tool}({params})"
    session["previous_actions"].append(action_summary)
    if len(session["previous_actions"]) > 5:
        session["previous_actions"].pop(0)
        
    return {
        "agent_id": agent_id,
        "agent_purpose": purpose,
        "session_id": session_id,
        "session": session,
        "previous_actions": prev_actions
    }

# Background thread daemon for periodic pattern detection scanning
def run_periodic_pattern_scan():
    # Allow uvicorn to startup first
    time.sleep(10)
    while True:
        session = get_session()
        try:
            logger.info("Starting background pattern detection scan...")
            detector = PatternDetector(session)
            detector.run_all_patterns()
        except Exception as e:
            logger.error(f"Error in background pattern detector scan: {e}")
        finally:
            session.close()
        # Sleep for 15 minutes (900 seconds)
        time.sleep(900)

@app.on_event("startup")
def start_background_tasks():
    t = threading.Thread(target=run_periodic_pattern_scan, daemon=True)
    t.start()
    logger.info("FastAPI successfully spawned periodic pattern scanner daemon.")

# Request/Response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next: Any) -> Response:
    start_time = time.time()
    logger.info(f"Incoming Request: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(f"Response: {request.method} {request.url.path} - Status: {response.status_code} - Duration: {duration:.4f}s")
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Request Failed: {request.method} {request.url.path} - Error: {e} - Duration: {duration:.4f}s", exc_info=True)
        return Response(
            content=f'{{"error": true, "message": "Internal server error", "detail": "{str(e)}"}}',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            media_type="application/json"
        )

# Pydantic Request Models
class ActRequest(BaseModel):
    tool: str = Field(..., description="Name of the tool to execute")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters to pass to the tool")
    dry_run: bool = Field(False, description="If true, evaluates policy but does not execute the tool")

class RequestLLMRequest(BaseModel):
    user_message: str = Field(..., description="Plain text instruction for the AI agent")
    dry_run: bool = Field(False, description="If true, evaluates policy but does not execute the tool")

class ApproveRequest(BaseModel):
    reviewer_name: str = Field(..., description="Name of the human reviewer")
    notes: Optional[str] = Field(None, description="Optional review notes")

class RejectRequest(BaseModel):
    reviewer_name: str = Field(..., description="Name of the human reviewer")
    reason: str = Field(..., description="Reason for rejection")

# Endpoints
@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, Any]:
    """
    Returns system status and timestamp.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0"
    }

@app.post("/act")
def evaluate_and_act(body: ActRequest) -> Dict[str, Any]:
    """
    Validates a tool action against security rules, audits it, and executes if allowed.
    """
    try:
        action = {"tool": body.tool, "params": body.params}
        
        # Validate that the tool exists in registry
        if body.tool not in TOOL_REGISTRY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tool '{body.tool}' is not registered in TOOL_REGISTRY."
            )
            
        tool_func = TOOL_REGISTRY[body.tool]
        
        # Validate required parameters
        sig = inspect.signature(tool_func)
        missing_params = []
        for param_name, param in sig.parameters.items():
            if param.default == inspect.Parameter.empty and param_name not in body.params:
                missing_params.append(param_name)
        if missing_params:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required parameters for tool '{body.tool}': {', '.join(missing_params)}"
            )
            
        # Check dry run config
        env_dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        is_dry_run = body.dry_run or env_dry_run
        
        # Mock Agent Context for direct playground evaluations
        agent_id = body.params.get("agent_id") or "direct-playground"
        purpose = body.params.get("agent_purpose") or "Security Playground tester verifying policy conditions."
        agent_context = {
            "agent_id": agent_id,
            "agent_purpose": purpose,
            "session_id": f"session-{agent_id}",
            "session": {
                "action_count_this_session": 1,
                "tables_accessed_this_session": [],
                "paths_accessed_this_session": [],
                "emails_sent_this_session": 0,
                "current_hour": datetime.now().hour
            },
            "previous_actions": []
        }
            
        # Evaluate rules using Multi-Layer Orchestrator
        ml_result = guardrail.evaluate(action, agent_context, dry_run=is_dry_run)
        outcome = ml_result.outcome
        entry_id = ml_result.audit_id
        
        executed = False
        result = None
        
        if outcome == "allowed" and not is_dry_run:
            try:
                tool_params = {k: v for k, v in body.params.items() if k not in ("agent_id", "agent_purpose")}
                result = tool_func(**tool_params)
                executed = True
                if entry_id:
                    audit_log.mark_executed(entry_id)
            except Exception as tool_err:
                logger.error(f"Error executing tool '{body.tool}': {tool_err}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Tool execution error: {str(tool_err)}"
                )
        
        return {
            "outcome": outcome,
            "matched_rule": ml_result.layer1.get("rule", "default"),
            "reason": ml_result.final_reason,
            "executed": executed,
            "result": result,
            "audit_id": entry_id,
            "dry_run": is_dry_run,
            "layers": {
                "layer1": ml_result.layer1,
                "layer2": ml_result.layer2,
                "layer3": ml_result.layer3,
                "layer4": ml_result.layer4
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /act: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/request")
def agent_request(body: RequestLLMRequest) -> Dict[str, Any]:
    """
    Decides actions using Gemini LLM (with local fallback parser), runs the guardrail, logs it, and executes if allowed.
    """
    try:
        # Ask Agent to decide on a tool (handles Gemini API with offline regex fallback)
        action = agent.decide(body.user_message)
        agent_mode = "Gemini LLM (Free Online)" if agent.model else "Local Pattern Parser (Offline)"
        
        if not action:
            return {
                "outcome": "none",
                "matched_rule": "none",
                "reason": "Agent did not select any tool execution.",
                "executed": False,
                "action_decided": None,
                "dry_run": body.dry_run,
                "agent_mode": agent_mode
            }
            
        tool_name = action["tool"]
        params = action["params"]
        
        # Check dry run config
        env_dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        is_dry_run = body.dry_run or env_dry_run
        
        # Setup agent metadata
        agent_id = "sim-agent-001"
        agent_purpose = "Customer support agent: read customer records, send support emails"
        
        # Get active session state context
        agent_context = get_agent_context(agent_id, agent_purpose, tool_name, params)
        
        # Verify tool registry
        if tool_name not in TOOL_REGISTRY:
            final_reason = f"Agent requested invalid tool '{tool_name}' which is not registered."
            ml_result = MultiLayerResult(
                outcome="blocked",
                layer1={"outcome": "blocked", "rule": "invalid_tool", "reason": final_reason},
                layer2={"tags": [], "risk_level": "low", "classification_source": "invalid_tool"},
                layer3={"risk_score": 100, "recommendation": "block", "reasoning": "Invalid tool call", "flags": []},
                layer4={"anomaly_score": 0, "status": "normal", "flags": []},
                final_reason=final_reason,
                dry_run=is_dry_run
            )
            if not is_dry_run:
                entry = audit_log.record_multi_layer(action, ml_result.__dict__)
                entry_id = entry.get("id")
            else:
                entry_id = None
                
            return {
                "outcome": "blocked",
                "matched_rule": "invalid_tool",
                "reason": final_reason,
                "executed": False,
                "action_decided": action,
                "audit_id": entry_id,
                "dry_run": is_dry_run,
                "agent_mode": agent_mode
            }
            
        # Evaluate using Multi-Layer Orchestrator
        ml_result = guardrail.evaluate(action, agent_context, dry_run=is_dry_run)
        outcome = ml_result.outcome
        entry_id = ml_result.audit_id
        
        executed = False
        result = None
        
        if outcome == "allowed" and not is_dry_run:
            tool_func = TOOL_REGISTRY[tool_name]
            result = tool_func(**params)
            executed = True
            if entry_id:
                audit_log.mark_executed(entry_id)
            
        return {
            "outcome": outcome,
            "matched_rule": ml_result.layer1.get("rule", "default"),
            "reason": ml_result.final_reason,
            "executed": executed,
            "result": result,
            "action_decided": action,
            "audit_id": entry_id,
            "dry_run": is_dry_run,
            "agent_mode": agent_mode,
            "layers": {
                "layer1": ml_result.layer1,
                "layer2": ml_result.layer2,
                "layer3": ml_result.layer3,
                "layer4": ml_result.layer4
            }
        }
    except Exception as e:
        logger.error(f"Error in /request endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/audit")
def get_audit_logs(limit: int = 50, outcome: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns audit log entries, newest first, optional filtering.
    """
    try:
        entries = audit_log.all_entries()
        
        # Filter by outcome if provided
        if outcome:
            entries = [e for e in entries if e.get("outcome") == outcome]
            
        # Order by ID / timestamp descending (newest first)
        sorted_entries = sorted(entries, key=lambda x: x.get("id", 0), reverse=True)
        return sorted_entries[:limit]
    except Exception as e:
        logger.error(f"Error reading audit log: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/audit/{entry_id}")
def get_audit_entry(entry_id: int) -> Dict[str, Any]:
    """
    Returns a single audit entry by its ID.
    """
    match = audit_log.get_entry_by_id(entry_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit entry with ID {entry_id} not found."
        )
    return match

@app.get("/review")
def get_pending_reviews() -> List[Dict[str, Any]]:
    """
    Returns all reviews waiting for Human-in-the-Loop review.
    """
    return audit_log.pending_reviews()

@app.post("/review/{entry_id}/approve")
def approve_action(entry_id: int, body: ApproveRequest) -> Dict[str, Any]:
    """
    Approves a held action and executes it immediately.
    """
    entry = audit_log.get_entry_by_id(entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit entry with ID {entry_id} not found."
        )
        
    if entry.get("outcome") != "pending_review" or entry.get("review_status") is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This entry is not in a pending review state or has already been resolved."
        )
        
    tool_name = entry.get("tool")
    params = entry.get("params", {})
    
    if tool_name not in TOOL_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute tool '{tool_name}' because it is not registered."
        )
        
    # Execute tool first, then commit to DB
    try:
        tool_func = TOOL_REGISTRY[tool_name]
        result = tool_func(**params)
        
        # Update database status
        audit_log.update_review_status(
            entry_id=entry_id,
            review_status="approved",
            reviewer_name=body.reviewer_name,
            reviewer_notes=body.notes or "",
            executed=True
        )
        
        logger.info(f"HITL Approved: Entry #{entry_id} executed by reviewer '{body.reviewer_name}'")
        return {
            "approved": True,
            "executed": True,
            "result": result
        }
    except Exception as tool_err:
        logger.error(f"Error executing tool in HITL approval: {tool_err}", exc_info=True)
        # Update status even on tool failure so it isn't retried indefinitely
        audit_log.update_review_status(
            entry_id=entry_id,
            review_status="approved_failed",
            reviewer_name=body.reviewer_name,
            reviewer_notes=f"Failed execution: {str(tool_err)}",
            executed=False
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool execution failed during approval: {str(tool_err)}"
        )

@app.post("/review/{entry_id}/reject")
def reject_action(entry_id: int, body: RejectRequest) -> Dict[str, Any]:
    """
    Rejects a held action and keeps it blocked from execution.
    """
    entry = audit_log.get_entry_by_id(entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit entry with ID {entry_id} not found."
        )
        
    if entry.get("outcome") != "pending_review" or entry.get("review_status") is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This entry is not in a pending review state or has already been resolved."
        )
        
    # Update status in DB
    success = audit_log.update_review_status(
        entry_id=entry_id,
        review_status="rejected",
        reviewer_name=body.reviewer_name,
        reviewer_notes=body.reason,
        executed=False
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update database record."
        )
        
    logger.info(f"HITL Rejected: Entry #{entry_id} blocked by reviewer '{body.reviewer_name}'")
    return {
        "rejected": True
    }

@app.get("/rules")
def get_policy_rules() -> Dict[str, Any]:
    """
    Returns current policy rules from the YAML configurations.
    """
    return {
        "rules": guardrail.layer1.rules,
        "default_action": guardrail.layer1.default_action,
        "rules_file": guardrail.layer1.rules_path
    }

@app.get("/patterns")
def get_pattern_alerts() -> List[Dict[str, Any]]:
    """
    Runs all pattern scans and returns any flagged alerts.
    """
    session = get_session()
    try:
        detector = PatternDetector(session)
        alerts = detector.run_all_patterns()
        return [a.__dict__ for a in alerts]
    finally:
        session.close()

@app.get("/patterns/alerts")
def get_active_pattern_alerts() -> List[Dict[str, Any]]:
    """
    Returns only unresolved alerts of severity >= medium.
    """
    session = get_session()
    try:
        detector = PatternDetector(session)
        alerts = detector.run_all_patterns()
        severity_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        active = [a.__dict__ for a in alerts if severity_map.get(a.severity, 0) >= 2]
        return active
    finally:
        session.close()

@app.get("/agent/{agent_id}/profile")
def get_agent_profile(agent_id: str) -> Dict[str, Any]:
    """
    Returns the baseline metrics profile for the given agent.
    """
    session = get_session()
    try:
        monitor = BehaviourMonitor(session)
        baseline = monitor.get_agent_baseline(agent_id)
        if not baseline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No baseline profile found for agent '{agent_id}'."
            )
        return baseline
    finally:
        session.close()

@app.get("/audit/{id}/explanation")
def get_audit_explanation(id: int) -> Dict[str, Any]:
    """
    Returns a human-readable security analysis explanation for the specified audit entry.
    """
    session = get_session()
    try:
        entry = session.query(AuditEntry).filter(AuditEntry.id == id).first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audit entry with ID {id} not found."
            )
        return {
            "id": id,
            "reviewer_context": entry.reviewer_context or entry.reason or "No detailed explanation context was logged for this entry."
        }
    finally:
        session.close()
