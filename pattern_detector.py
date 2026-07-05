import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Any
from database import AuditEntry
from sqlalchemy import func

logger = logging.getLogger(__name__)

@dataclass
class PatternAlert:
    type: str  # potential_exfiltration | guardrail_probing | scope_drift
    agent_id: str
    severity: str  # low | medium | high | critical
    description: str
    recommended_action: str
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidence: List[int] = field(default_factory=list)

class PatternDetector:
    """
    Scans the historical Audit logs across sessions to detect complex multi-session threat patterns.
    """
    def __init__(self, db_session) -> None:
        self.session = db_session
        self.EXFILTRATION_READ_THRESHOLD = 50
        self.PROBING_BLOCK_THRESHOLD = 5
        self.SCOPE_DRIFT_THRESHOLD = 0.4

    def run_all_patterns(self) -> List[PatternAlert]:
        alerts = []
        if not self.session:
            return alerts
            
        try:
            alerts.extend(self.detect_exfiltration_pattern())
            alerts.extend(self.detect_probing_pattern())
            alerts.extend(self.detect_scope_drift())
            alerts.extend(self.detect_cumulative_deletes_pattern())
            logger.info(f"Executed cross-session patterns scan. Found {len(alerts)} alerts.")
        except Exception as e:
            logger.error(f"Failed to scan security patterns: {e}", exc_info=True)
            
        return alerts

    def detect_exfiltration_pattern(self) -> List[PatternAlert]:
        alerts = []
        try:
            # Query last 24 hours of file reads
            one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
            entries = self.session.query(AuditEntry).filter(
                AuditEntry.timestamp >= one_day_ago,
                AuditEntry.tool == "read_file",
                AuditEntry.executed == True
            ).all()

            # Group by agent
            agent_reads: Dict[str, List[AuditEntry]] = {}
            for entry in entries:
                agent_id = entry.params.get("agent_id", "unknown_agent") if isinstance(entry.params, dict) else "unknown_agent"
                if agent_id not in agent_reads:
                    agent_reads[agent_id] = []
                agent_reads[agent_id].append(entry)

            for agent_id, agent_entries in agent_reads.items():
                count = len(agent_entries)
                if count >= self.EXFILTRATION_READ_THRESHOLD:
                    evidence_ids = [e.id for e in agent_entries[:10]]  # limit evidence list size
                    alerts.append(PatternAlert(
                        type="potential_exfiltration",
                        agent_id=agent_id,
                        severity="high",
                        description=f"Agent '{agent_id}' read {count} files in the last 24h. Possible bulk exfiltration attempt.",
                        recommended_action="suspend_agent",
                        evidence=evidence_ids
                    ))
        except Exception as e:
            logger.error(f"Error checking exfiltration pattern: {e}", exc_info=True)
            
        return alerts

    def detect_probing_pattern(self) -> List[PatternAlert]:
        alerts = []
        try:
            # Query last 1 hour of blocks
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            entries = self.session.query(AuditEntry).filter(
                AuditEntry.timestamp >= one_hour_ago,
                AuditEntry.outcome == "blocked"
            ).all()

            # Group by agent
            agent_blocks: Dict[str, List[AuditEntry]] = {}
            for entry in entries:
                agent_id = entry.params.get("agent_id", "unknown_agent") if isinstance(entry.params, dict) else "unknown_agent"
                if agent_id not in agent_blocks:
                    agent_blocks[agent_id] = []
                agent_blocks[agent_id].append(entry)

            for agent_id, agent_entries in agent_blocks.items():
                count = len(agent_entries)
                if count >= self.PROBING_BLOCK_THRESHOLD:
                    evidence_ids = [e.id for e in agent_entries]
                    alerts.append(PatternAlert(
                        type="guardrail_probing",
                        agent_id=agent_id,
                        severity="critical",
                        description=f"Agent '{agent_id}' triggered {count} blocks in the last hour. Highly likely policy probing behavior.",
                        recommended_action="require_hitl_all_actions",
                        evidence=evidence_ids
                    ))
        except Exception as e:
            logger.error(f"Error checking policy probing pattern: {e}", exc_info=True)
            
        return alerts

    def detect_scope_drift(self) -> List[PatternAlert]:
        alerts = []
        try:
            # For each active agent, compare last 24h access list with baseline (earlier than 24h ago)
            one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
            
            # Query last 24h entries
            current_entries = self.session.query(AuditEntry).filter(
                AuditEntry.timestamp >= one_day_ago,
                AuditEntry.executed == True
            ).all()

            # Group current resources by agent
            agent_current_resources: Dict[str, Dict[str, Set[str]]] = {}
            for entry in current_entries:
                agent_id = entry.params.get("agent_id", "unknown") if isinstance(entry.params, dict) else "unknown"
                if agent_id == "unknown":
                    continue
                if agent_id not in agent_current_resources:
                    agent_current_resources[agent_id] = {"tables": set(), "paths": set()}
                
                if entry.tool == "delete_records":
                    table = entry.params.get("table", "") if isinstance(entry.params, dict) else ""
                    if table: agent_current_resources[agent_id]["tables"].add(table)
                elif entry.tool == "read_file":
                    path = entry.params.get("path", "") if isinstance(entry.params, dict) else ""
                    if path: agent_current_resources[agent_id]["paths"].add(path)

            # Check each agent's current resources against historical baseline
            for agent_id, current in agent_current_resources.items():
                # Query history (older than 24h)
                historical_entries = self.session.query(AuditEntry).filter(
                    AuditEntry.timestamp < one_day_ago,
                    AuditEntry.executed == True
                ).all()

                historical_tables = set()
                historical_paths = set()
                historical_ids = []

                for entry in historical_entries:
                    entry_agent = entry.params.get("agent_id", "unknown") if isinstance(entry.params, dict) else "unknown"
                    if entry_agent == agent_id:
                        historical_ids.append(entry.id)
                        if entry.tool == "delete_records":
                            table = entry.params.get("table", "") if isinstance(entry.params, dict) else ""
                            if table: historical_tables.add(table)
                        elif entry.tool == "read_file":
                            path = entry.params.get("path", "") if isinstance(entry.params, dict) else ""
                            if path: historical_paths.add(path)

                # Skip drift analysis if history is empty (new agent)
                if not historical_tables and not historical_paths:
                    continue

                # Calculate table drift fraction
                total_current_tables = len(current["tables"])
                drifted_tables = len(current["tables"] - historical_tables)
                table_drift_ratio = drifted_tables / total_current_tables if total_current_tables > 0 else 0.0

                # Calculate path drift fraction
                total_current_paths = len(current["paths"])
                drifted_paths = len(current["paths"] - historical_paths)
                path_drift_ratio = drifted_paths / total_current_paths if total_current_paths > 0 else 0.0

                max_drift = max(table_drift_ratio, path_drift_ratio)

                if max_drift >= self.SCOPE_DRIFT_THRESHOLD:
                    alerts.append(PatternAlert(
                        type="scope_drift",
                        agent_id=agent_id,
                        severity="medium",
                        description=f"Agent '{agent_id}' is accessing resources outside historical baseline (Scope drift ratio: {max_drift:.2f}).",
                        recommended_action="flag_for_review",
                        evidence=historical_ids[-10:]  # last 10 baseline entries as reference
                    ))
        except Exception as e:
            logger.error(f"Error checking scope drift pattern: {e}", exc_info=True)
            
        return alerts

    def detect_cumulative_deletes_pattern(self) -> List[PatternAlert]:
        alerts = []
        try:
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            entries = self.session.query(AuditEntry).filter(
                AuditEntry.timestamp >= one_hour_ago,
                AuditEntry.tool == "delete_records"
            ).all()

            # Sort entries by timestamp to find consecutive sequences
            entries = sorted(entries, key=lambda e: e.timestamp)

            agent_deletes = {}
            for entry in entries:
                agent_id = entry.params.get("agent_id", "unknown_agent") if isinstance(entry.params, dict) else "unknown_agent"
                if agent_id not in agent_deletes:
                    agent_deletes[agent_id] = []
                agent_deletes[agent_id].append(entry)

            for agent_id, agent_entries in agent_deletes.items():
                current_streak = []
                longest_streak = []
                
                for entry in agent_entries:
                    count = entry.params.get("count", 0) if isinstance(entry.params, dict) else 0
                    if 20 <= count <= 100:
                        current_streak.append(entry)
                        if len(current_streak) > len(longest_streak):
                            longest_streak = list(current_streak)
                    else:
                        current_streak = []
                
                if len(longest_streak) > 5:
                    evidence_ids = [e.id for e in longest_streak]
                    alerts.append(PatternAlert(
                        type="cumulative_deletion",
                        agent_id=agent_id,
                        severity="high",
                        description=f"Agent '{agent_id}' deleted between 20 and 100 records continuously {len(evidence_ids)} times in the last hour.",
                        recommended_action="suspend_agent",
                        evidence=evidence_ids
                    ))
        except Exception as e:
            logger.error(f"Error checking cumulative deletes pattern: {e}", exc_info=True)
            
        return alerts
