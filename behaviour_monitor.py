import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from database import AuditEntry

logger = logging.getLogger(__name__)

@dataclass
class BehaviourResult:
    anomaly_score: int = 0
    status: str = "normal"  # normal | warning | alert | no_baseline
    flags: List[str] = field(default_factory=list)
    baseline_summary: Dict[str, Any] = field(default_factory=dict)

class BehaviourMonitor:
    """
    Monitors AI Agent action execution patterns against an established historical baseline.
    Flags anomalies such as off-hours queries, new tables, or action count spikes.
    """
    def __init__(self, db_session) -> None:
        self.session = db_session

    def get_agent_baseline(self, agent_id: str) -> Optional[Dict[str, Any]]:
        if not self.session:
            # Fallback if no database session is active (e.g. CLI simulation mockup baseline)
            return None

        try:
            # Query log entries for the last 30 days
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            
            # Simple query using SQLAlchemy session
            entries = self.session.query(AuditEntry).filter(
                AuditEntry.timestamp >= thirty_days_ago,
                AuditEntry.executed == True
            ).all()

            if not entries:
                return None

            # Calculate session-grouped aggregates
            # To compute average actions per session, group by parameter keys or paths
            sessions: Dict[str, List[AuditEntry]] = {}
            for entry in entries:
                # Retrieve session ID if present in params, else fallback to generic string
                sess_id = entry.params.get("session_id", "default_sess") if isinstance(entry.params, dict) else "default_sess"
                if sess_id not in sessions:
                    sessions[sess_id] = []
                sessions[sess_id].append(entry)

            # Sum statistics
            total_sessions = len(sessions)
            if total_sessions == 0:
                return None

            total_actions = len(entries)
            avg_actions = total_actions / total_sessions

            delete_counts = []
            typical_tables: Set[str] = set()
            typical_paths: Set[str] = set()
            active_hours: Set[int] = set()
            emails_per_session: Dict[str, int] = {}

            for sess_id, sess_entries in sessions.items():
                email_count = 0
                for entry in sess_entries:
                    active_hours.add(entry.timestamp.hour)
                    
                    if entry.tool == "delete_records":
                        count = entry.params.get("count", 0) if isinstance(entry.params, dict) else 0
                        delete_counts.append(count)
                        table = entry.params.get("table", "") if isinstance(entry.params, dict) else ""
                        if table:
                            typical_tables.add(table)
                            
                    elif entry.tool == "read_file":
                        path = entry.params.get("path", "") if isinstance(entry.params, dict) else ""
                        if path:
                            # Use parent directory path prefix
                            prefix = "/".join(path.split("/")[:-1]) + "/"
                            typical_paths.add(prefix)
                            
                    elif entry.tool == "send_email":
                        email_count += 1
                
                emails_per_session[sess_id] = email_count

            avg_delete = sum(delete_counts) / len(delete_counts) if delete_counts else 5.0
            avg_emails = sum(emails_per_session.values()) / len(emails_per_session) if emails_per_session else 2.0

            # Default active hours fallback (standard working hours) if history is sparse
            if not active_hours:
                active_hours = set(range(8, 19)) # 8 AM to 6 PM

            return {
                "avg_actions_per_session": float(avg_actions),
                "avg_delete_count": float(avg_delete),
                "typical_tables": typical_tables,
                "typical_paths": typical_paths,
                "typical_email_count_per_session": float(avg_emails),
                "active_hours": list(active_hours),
                "typical_session_duration_minutes": 15.0
            }

        except Exception as e:
            logger.error(f"Error computing agent baseline: {e}", exc_info=True)
            return None

    def check_action(self, agent_id: str, action: Dict[str, Any], session_context: Dict[str, Any]) -> BehaviourResult:
        tool = action.get("tool")
        params = action.get("params", {})
        
        baseline = self.get_agent_baseline(agent_id)
        
        # If no baseline exists, return normal/building state
        if not baseline:
            return BehaviourResult(
                anomaly_score=0,
                status="no_baseline",
                flags=["Building historical baseline profile"],
                baseline_summary={"status": "New agent - building baseline"}
            )

        avg_actions = baseline.get("avg_actions_per_session", 10.0)
        avg_delete = baseline.get("avg_delete_count", 5.0)
        avg_emails = baseline.get("typical_email_count_per_session", 2.0)

        anomaly_score = 0
        flags = []

        # 1. High session action count check
        action_count = session_context.get("action_count_this_session", 1)
        if action_count > avg_actions * 10:
            flags.append(f"Critical spike in session action frequency ({action_count} vs baseline {avg_actions:.1f})")
            anomaly_score += 65
        elif action_count > avg_actions * 3:
            flags.append(f"Unusually high action count this session ({action_count} vs baseline {avg_actions:.1f})")
            anomaly_score += 25

        # 2. Large delete count check
        if tool == "delete_records":
            count = params.get("count", 0)
            if count > avg_delete * 5:
                flags.append(f"Delete count {count} is 5x above baseline average ({avg_delete:.1f})")
                anomaly_score += 30

        # 2b. Cumulative deletes check (proactive defense against multi-step deletion attacks)
        if tool == "delete_records" and self.session:
            try:
                one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                past_entries = self.session.query(AuditEntry).filter(
                    AuditEntry.timestamp >= one_hour_ago,
                    AuditEntry.tool == "delete_records"
                ).all()
                
                cumulative_count = 0
                for entry in past_entries:
                    p = entry.params or {}
                    p_agent = p.get("agent_id") if isinstance(p, dict) else None
                    if p_agent == agent_id or (not p_agent and agent_id == "direct-playground"):
                        cumulative_count += p.get("count", 0) if isinstance(p, dict) else 0
                
                count = params.get("count", 0)
                if cumulative_count + count > 100:
                    flags.append(f"Cumulative deletes in last hour ({cumulative_count + count} records) exceeds safe threshold of 100")
                    anomaly_score += 45
            except Exception as ex:
                logger.error(f"Error checking cumulative deletes baseline: {ex}")

        # 3. Access to unknown tables check
        if tool == "delete_records":
            table = params.get("table", "")
            typical_tables = set(baseline.get("typical_tables", []))
            if table and table not in typical_tables:
                flags.append(f"Agent accessing table '{table}' which is not in its baseline")
                anomaly_score += 20

        # 4. Access to unknown directories check
        if tool == "read_file":
            path = params.get("path", "")
            typical_paths = baseline.get("typical_paths", [])
            # Prefix prefix checks
            path_match = False
            for p in typical_paths:
                if path.startswith(p):
                    path_match = True
                    break
            
            if not path_match and typical_paths:
                flags.append(f"File path '{path}' is outside agent baseline paths")
                anomaly_score += 20

        # 5. Off-hours activity check
        current_hour = session_context.get("current_hour", datetime.now().hour)
        active_hours = baseline.get("active_hours", list(range(8, 19)))
        if current_hour not in active_hours:
            flags.append(f"Action at hour {current_hour}:00 is outside normal active hours")
            anomaly_score += 15

        # 6. High email volume check
        if tool == "send_email":
            emails_sent = session_context.get("emails_sent_this_session", 0)
            if emails_sent > avg_emails * 4:
                flags.append(f"Email volume this session ({emails_sent}) is 4x above baseline ({avg_emails:.1f})")
                anomaly_score += 30

        # Cap score at 100
        anomaly_score = min(anomaly_score, 100)
        
        # Classify status
        if anomaly_score < 30:
            status = "normal"
        elif anomaly_score < 60:
            status = "warning"
        else:
            status = "alert"

        # Format baseline summary for dashboard visualization
        baseline_summary = {
            "avg_actions_per_session": f"{avg_actions:.1f}",
            "avg_delete_count": f"{avg_delete:.1f}",
            "typical_tables": list(typical_tables) if tool == "delete_records" else [],
            "typical_paths": list(typical_paths) if tool == "read_file" else [],
            "typical_email_count": f"{avg_emails:.1f}",
            "active_hours": f"{min(active_hours)}:00-{max(active_hours)}:00" if active_hours else "None"
        }

        return BehaviourResult(
            anomaly_score=anomaly_score,
            status=status,
            flags=flags,
            baseline_summary=baseline_summary
        )
