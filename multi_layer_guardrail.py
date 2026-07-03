import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from guardrail import Guardrail
from data_classifier import DataClassifier, ClassificationResult
from semantic_evaluator import SemanticEvaluator, SemanticResult
from behaviour_monitor import BehaviourMonitor, BehaviourResult
from audit_log import AuditLog

logger = logging.getLogger(__name__)

@dataclass
class MultiLayerResult:
    outcome: str  # allowed | blocked | pending_review
    layer1: Dict[str, Any] = field(default_factory=dict)
    layer2: Dict[str, Any] = field(default_factory=dict)
    layer3: Dict[str, Any] = field(default_factory=dict)
    layer4: Dict[str, Any] = field(default_factory=dict)
    final_reason: str = ""
    reviewer_context: str = ""
    dry_run: bool = False
    audit_id: Optional[int] = None

class MultiLayerGuardrail:
    """
    Main orchestrator that evaluates incoming tool actions through all 5 guardrail layers:
    L1 YAML Rules -> L2 Data Classification -> L3 Semantic Eval -> L4 Behaviour Baseline -> L5 Pattern Logging.
    """
    def __init__(self, db_session=None) -> None:
        self.layer1 = Guardrail("rules.yaml")
        self.layer2 = DataClassifier("data_registry.yaml")
        self.layer3 = SemanticEvaluator()
        self.layer4 = BehaviourMonitor(db_session)
        self.audit = AuditLog()

    def generate_hitl_summary(self, tool: str, params: dict, l1: dict, l2: dict, l3: dict, l4: dict, final_verdict: str) -> str:
        summary_parts = []
        summary_parts.append(f"AI Agent requested tool execution: '{tool}' with parameters: {params}.")
        
        # L2 tag summaries
        tags = l2.get("tags", [])
        risk = l2.get("risk_level", "low").upper()
        if tags:
            summary_parts.append(f"Layer 2 Data Classification categorized the input as {risk} risk with tags: [{','.join(tags)}].")
        else:
            summary_parts.append("Layer 2 Data Classification analyzed the data as unclassified (General access).")
            
        # L3 Semantic summaries
        score = l3.get("risk_score", 0)
        reason = l3.get("reasoning", "")
        summary_parts.append(f"Layer 3 Semantic LLM Evaluator graded the request risk at {score}/100. Reasoning: '{reason}'.")
        
        # L4 anomaly summaries
        l4_status = l4.get("status", "normal").upper()
        l4_flags = l4.get("flags", [])
        if l4_status != "NORMAL":
            summary_parts.append(f"Layer 4 Behaviour Monitor flagged an anomaly alert ({l4_status} - Anomaly Score: {l4.get('anomaly_score')}/100). Flags: {', '.join(l4_flags)}.")
        else:
            summary_parts.append("Layer 4 Behaviour Monitor reports action fits the agent's historical baseline profile.")
            
        summary_parts.append(f"Final Decision Verdict: {final_verdict.upper()}. Recommended resolution: review parameters carefully before approving.")
        return " ".join(summary_parts)

    def evaluate(self, action: Dict[str, Any], agent_context: Dict[str, Any], dry_run: bool = False) -> MultiLayerResult:
        tool = action.get("tool")
        params = action.get("params", {})
        agent_id = agent_context.get("agent_id", "default_agent")
        session_id = agent_context.get("session_id", "default_session")
        
        logger.info(f"Evaluating action '{tool}' through 5-Layer Intelligent Guardrail for agent '{agent_id}'")

        # Open database session dynamically if not provided
        close_session = False
        if not self.layer4.session:
            from database import get_session
            self.layer4.session = get_session()
            close_session = True

        try:
            # ---------------------------------------------------------
            # STEP 1 - Layer 1: YAML Rules pre-check
            # ---------------------------------------------------------
            l1_eval = self.layer1.evaluate_action(action)
            l1_outcome = l1_eval["outcome"]
            l1_rule = l1_eval["matched_rule"]
            l1_reason = l1_eval["reason"]
            
            l1_dict = {"outcome": l1_outcome, "rule": l1_rule, "reason": l1_reason}

            # Check for L1 HARD Block (First match blocks immediately, skipping other steps)
            if l1_outcome == "blocked" and l1_rule != "semantic_check":
                final_verdict = "blocked"
                final_reason = f"Blocked by Layer 1 YAML Rule: '{l1_rule}'. Reason: {l1_reason}"
                
                result = MultiLayerResult(
                    outcome=final_verdict,
                    layer1=l1_dict,
                    layer2={"tags": [], "risk_level": "low", "classification_source": "skipped"},
                    layer3={"risk_score": 0, "recommendation": "block", "reasoning": "Skipped due to L1 block", "flags": []},
                    layer4={"anomaly_score": 0, "status": "normal", "flags": []},
                    final_reason=final_reason,
                    reviewer_context="",
                    dry_run=dry_run
                )
                if not dry_run:
                    entry = self.audit.record_multi_layer(action, result.__dict__)
                    result.audit_id = entry.get("id")
                return result

            # ---------------------------------------------------------
            # STEP 2 - Layer 2: Data Classification
            # ---------------------------------------------------------
            l2_eval = self.layer2.classify(action)
            l2_dict = {
                "tags": l2_eval.tags,
                "risk_level": l2_eval.risk_level,
                "classification_source": l2_eval.classification_source,
                "recommended_action": l2_eval.recommended_action
            }

            # Check for L2 hard block (e.g. Deleting LEGAL_HOLD resources)
            if l2_eval.recommended_action == "block":
                final_verdict = "blocked"
                final_reason = f"Blocked by Layer 2 Data classification: {l2_eval.details_str}"
                
                result = MultiLayerResult(
                    outcome=final_verdict,
                    layer1=l1_dict,
                    layer2=l2_dict,
                    layer3={"risk_score": 100, "recommendation": "block", "reasoning": "Data flagged with block restrictions.", "flags": ["LEGAL_HOLD_delete"]},
                    layer4={"anomaly_score": 0, "status": "normal", "flags": []},
                    final_reason=final_reason,
                    reviewer_context="",
                    dry_run=dry_run
                )
                if not dry_run:
                    entry = self.audit.record_multi_layer(action, result.__dict__)
                    result.audit_id = entry.get("id")
                return result

            # ---------------------------------------------------------
            # STEP 3 - Layer 3: Semantic LLM Evaluation
            # ---------------------------------------------------------
            l3_eval = self.layer3.evaluate(action, l2_eval, agent_context)
            l3_dict = {
                "risk_score": l3_eval.risk_score,
                "recommendation": l3_eval.recommendation,
                "reasoning": l3_eval.reasoning,
                "flags": l3_eval.flags,
                "confidence": l3_eval.confidence
            }

            # ---------------------------------------------------------
            # STEP 4 - Layer 4: Behavioural Baseline Check
            # ---------------------------------------------------------
            # Retrieve or construct session context object
            session_ctx = agent_context.get("session", {})
            l4_eval = self.layer4.check_action(agent_id, action, session_ctx)
            l4_dict = {
                "anomaly_score": l4_eval.anomaly_score,
                "status": l4_eval.status,
                "flags": l4_eval.flags,
                "baseline_summary": l4_eval.baseline_summary
            }

            # ---------------------------------------------------------
            # STEP 5 - Combine All Layer Signals
            # ---------------------------------------------------------
            # Final Decision Resolution Logic
            final_verdict = "allowed"
            
            # Checks:
            # A. Fired a hard L1 block
            if l1_outcome == "blocked":
                final_verdict = "blocked"
                final_reason = f"Layer 1 YAML policy triggered block condition '{l1_rule}'."
                
            # B. Fired an LLM Semantic block (score >= 61)
            elif l3_eval.risk_score >= 61 or l3_eval.recommendation == "block":
                final_verdict = "blocked"
                final_reason = f"Layer 3 Semantic Auditor flagged action as critical risk ({l3_eval.risk_score}/100). reasoning: {l3_eval.reasoning}"
                
            # C. Escalations to Human-In-The-Loop review (outcome = pending_review)
            elif (
                l1_outcome == "pending_review" or 
                l3_eval.risk_score >= 31 or 
                l3_eval.recommendation == "require_hitl" or
                l2_eval.recommended_action == "require_hitl" or
                l4_eval.status == "alert" or
                l4_eval.status == "warning"
            ):
                final_verdict = "pending_review"
                
                # Combine reasons
                reasons = []
                if l1_outcome == "pending_review": 
                    reasons.append(f"L1 YAML '{l1_rule}' requires HITL")
                if l2_eval.recommended_action == "require_hitl": 
                    reasons.append(f"L2 Data classified high risk ({l2_eval.risk_level})")
                if l3_eval.risk_score >= 31: 
                    reasons.append(f"L3 Semantic Auditor flagged risk score {l3_eval.risk_score}/100")
                if l4_eval.status == "alert" or l4_eval.status == "warning": 
                    reasons.append(f"L4 Behaviour monitor flagged baseline anomaly ({l4_eval.status.upper()})")
                    
                final_reason = "Escalated for human review: " + ", ".join(reasons)
                
            # D. Otherwise allowed
            else:
                final_verdict = "allowed"
                final_reason = "Action approved. All safety and semantic compliance checks passed."

            # Generate Human-Friendly detailed explanation context for HITL Reviews
            reviewer_context = ""
            if final_verdict == "pending_review":
                reviewer_context = self.generate_hitl_summary(
                    tool, params, l1_dict, l2_dict, l3_dict, l4_dict, final_verdict
                )

            # Construct return container
            result = MultiLayerResult(
                outcome=final_verdict,
                layer1=l1_dict,
                layer2=l2_dict,
                layer3=l3_dict,
                layer4=l4_dict,
                final_reason=final_reason,
                reviewer_context=reviewer_context,
                dry_run=dry_run
            )

            # ---------------------------------------------------------
            # STEP 6 - Write to Database (Audit Log Logging)
            # ---------------------------------------------------------
            if not dry_run:
                entry = self.audit.record_multi_layer(action, result.__dict__)
                result.audit_id = entry.get("id")

            return result

        finally:
            if close_session:
                if self.layer4.session:
                    self.layer4.session.close()
                self.layer4.session = None
