import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from database import get_session, AuditEntry

logger = logging.getLogger(__name__)

class AuditLog:
    """
    Manages audit log storage and retrieval using a SQLite database via SQLAlchemy.
    """
    def __init__(self, filepath: str = None) -> None:
        """
        Initializes the AuditLog manager.
        filepath is accepted for backward compatibility but Database configuration
        is loaded from environment variables in database.py.
        """
        # Connection is managed via database.py
        pass

    def _to_dict(self, entry: AuditEntry) -> Dict[str, Any]:
        """
        Converts an AuditEntry SQLAlchemy model instance to a dictionary.
        """
        return {
            "id": entry.id,
            "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
            "tool": entry.tool,
            "params": entry.params,
            "outcome": entry.outcome,
            "matched_rule": entry.matched_rule,
            "reason": entry.reason,
            
            # New Multi-Layer columns
            "layer1_outcome": entry.layer1_outcome,
            "layer1_rule": entry.layer1_rule,
            "layer2_tags": entry.layer2_tags,
            "layer2_risk_level": entry.layer2_risk_level,
            "layer3_risk_score": entry.layer3_risk_score,
            "layer3_reasoning": entry.layer3_reasoning,
            "layer3_flags": entry.layer3_flags,
            "layer4_anomaly_score": entry.layer4_anomaly_score,
            "layer4_status": entry.layer4_status,
            "layer4_flags": entry.layer4_flags,
            "final_reason": entry.final_reason,
            "reviewer_context": entry.reviewer_context,
            
            "reviewer_name": entry.reviewer_name,
            "reviewer_notes": entry.reviewer_notes,
            "review_status": entry.review_status,
            "review_timestamp": entry.review_timestamp.isoformat() if entry.review_timestamp else None,
            "executed": entry.executed
        }

    def record(self, action: Dict[str, Any], outcome: str, matched_rule: str, reason: str) -> Dict[str, Any]:
        """
        Creates and stores a basic audit entry in the database.
        """
        session = get_session()
        try:
            entry = AuditEntry(
                tool=action.get("tool"),
                params=action.get("params", {}),
                outcome=outcome,
                matched_rule=matched_rule,
                reason=reason,
                executed=False
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            logger.info(f"Recorded DB audit entry #{entry.id}: {entry.tool} -> {outcome}")
            return self._to_dict(entry)
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to write audit entry to DB: {e}", exc_info=True)
            raise e
        finally:
            session.close()

    def record_multi_layer(self, action: Dict[str, Any], final_decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates and stores a detailed multi-layer audit entry in the database.
        """
        session = get_session()
        try:
            l1 = final_decision.get("layer1", {})
            l2 = final_decision.get("layer2", {})
            l3 = final_decision.get("layer3", {})
            l4 = final_decision.get("layer4", {})
            
            entry = AuditEntry(
                tool=action.get("tool"),
                params=action.get("params", {}),
                outcome=final_decision.get("outcome", "allowed"),
                matched_rule=l1.get("rule", "default"),
                reason=final_decision.get("final_reason", ""),
                
                layer1_outcome=l1.get("outcome"),
                layer1_rule=l1.get("rule"),
                layer2_tags=l2.get("tags"),
                layer2_risk_level=l2.get("risk_level"),
                layer3_risk_score=l3.get("risk_score"),
                layer3_reasoning=l3.get("reasoning"),
                layer3_flags=l3.get("flags"),
                layer4_anomaly_score=l4.get("anomaly_score"),
                layer4_status=l4.get("status"),
                layer4_flags=l4.get("flags"),
                final_reason=final_decision.get("final_reason"),
                reviewer_context=final_decision.get("reviewer_context"),
                
                executed=False
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            logger.info(f"Recorded multi-layer DB audit entry #{entry.id}: {entry.tool} -> {entry.outcome}")
            return self._to_dict(entry)
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to write multi-layer audit entry to DB: {e}", exc_info=True)
            raise e
        finally:
            session.close()

    def all_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieves all stored audit entries, ordered by ID descending.
        """
        session = get_session()
        try:
            entries = session.query(AuditEntry).order_by(AuditEntry.id.desc()).limit(limit).all()
            return [self._to_dict(e) for e in entries]
        except Exception as e:
            logger.error(f"Failed to query all audit entries: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def get_entry_by_id(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single audit entry by its ID.
        """
        session = get_session()
        try:
            entry = session.query(AuditEntry).filter(AuditEntry.id == entry_id).first()
            if entry:
                return self._to_dict(entry)
            return None
        except Exception as e:
            logger.error(f"Failed to query audit entry ID {entry_id}: {e}", exc_info=True)
            return None
        finally:
            session.close()

    def pending_reviews(self) -> List[Dict[str, Any]]:
        """
        Retrieves all unresolved actions pending human review.
        """
        session = get_session()
        try:
            entries = session.query(AuditEntry).filter(
                AuditEntry.outcome == "pending_review",
                AuditEntry.review_status.is_(None)
            ).all()
            return [self._to_dict(e) for e in entries]
        except Exception as e:
            logger.error(f"Failed to query pending reviews: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def update_review_status(
        self, 
        entry_id: int, 
        review_status: str, 
        reviewer_name: str, 
        reviewer_notes: str, 
        executed: bool
    ) -> bool:
        """
        Updates the review resolution status and execution state of an action.
        """
        session = get_session()
        try:
            entry = session.query(AuditEntry).filter(AuditEntry.id == entry_id).first()
            if not entry:
                return False
                
            entry.review_status = review_status
            entry.reviewer_name = reviewer_name
            entry.reviewer_notes = reviewer_notes
            entry.review_timestamp = datetime.now(timezone.utc)
            entry.executed = executed
            
            session.commit()
            logger.info(f"Updated review status for entry #{entry_id} to '{review_status}'")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update review status for entry #{entry_id}: {e}", exc_info=True)
            return False
        finally:
            session.close()

    def mark_executed(self, entry_id: int) -> bool:
        """
        Marks an entry as executed after successful tool execution.
        """
        session = get_session()
        try:
            entry = session.query(AuditEntry).filter(AuditEntry.id == entry_id).first()
            if not entry:
                return False
            entry.executed = True
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to mark entry #{entry_id} as executed: {e}", exc_info=True)
            return False
        finally:
            session.close()
