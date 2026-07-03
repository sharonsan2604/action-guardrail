import pytest
from unittest.mock import MagicMock
from data_classifier import DataClassifier
from behaviour_monitor import BehaviourMonitor, BehaviourResult
from multi_layer_guardrail import MultiLayerGuardrail, MultiLayerResult

# =====================================================================
# LAYER 2 TESTS (Data Classification)
# =====================================================================

def test_l2_pii_table_detection():
    action = {"tool": "delete_records", "params": {"table": "employees", "count": 5}}
    result = DataClassifier().classify(action)
    assert "PII" in result.tags
    assert "FINANCIAL" in result.tags
    assert result.risk_level == "high"
    assert result.recommended_action == "require_hitl"

def test_l2_legal_hold_block():
    action = {"tool": "delete_records", "params": {"table": "audit_trail", "count": 1}}
    result = DataClassifier().classify(action)
    assert "LEGAL_HOLD" in result.tags
    assert result.recommended_action == "block"

def test_l2_email_body_keyword_scan():
    action = {
        "tool": "send_email", 
        "params": {
            "to": "bob", 
            "domain": "mycompany.com",
            "body": "Here are the salary compensation figures for review"
        }
    }
    result = DataClassifier().classify(action)
    assert "FINANCIAL" in result.tags
    assert "PII" in result.tags
    assert result.risk_level == "high"

def test_l2_unclassified_path_triggers_semantic_check():
    action = {"tool": "read_file", "params": {"path": "/common_files/anything.xlsx"}}
    result = DataClassifier().classify(action)
    assert result.recommended_action == "semantic_check"

def test_l2_path_prefix_matching():
    action = {"tool": "read_file", "params": {"path": "/data/hr/team_list.csv"}}
    result = DataClassifier().classify(action)
    assert "PII" in result.tags
    assert "FINANCIAL" in result.tags

# =====================================================================
# LAYER 4 TESTS (Behaviour Monitoring - using mock baseline)
# =====================================================================

def test_l4_normal_action_no_anomaly():
    monitor = BehaviourMonitor(None)
    # Mock baseline return
    monitor.get_agent_baseline = MagicMock(return_value={
        "avg_actions_per_session": 10.0,
        "avg_delete_count": 5.0,
        "typical_tables": {"customers"},
        "typical_paths": {"/public/"},
        "typical_email_count_per_session": 2.0,
        "active_hours": [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
        "typical_session_duration_minutes": 15.0
    })
    
    session_ctx = {
        "action_count_this_session": 8,
        "tables_accessed_this_session": ["customers"],
        "paths_accessed_this_session": [],
        "emails_sent_this_session": 0,
        "current_hour": 14
    }
    
    action = {"tool": "delete_records", "params": {"table": "customers", "count": 5}}
    result = monitor.check_action("agent1", action, session_ctx)
    assert result.status == "normal"
    assert result.anomaly_score < 30

def test_l4_high_action_count_triggers_alert():
    monitor = BehaviourMonitor(None)
    monitor.get_agent_baseline = MagicMock(return_value={
        "avg_actions_per_session": 10.0,
        "avg_delete_count": 5.0,
        "typical_tables": {"customers"},
        "typical_paths": {"/public/"},
        "typical_email_count_per_session": 2.0,
        "active_hours": [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    })
    
    session_ctx = {
        "action_count_this_session": 150,  # 15x baseline average
        "current_hour": 14
    }
    
    action = {"tool": "read_file", "params": {"path": "/public/readme.txt"}}
    result = monitor.check_action("agent1", action, session_ctx)
    assert result.status in ("warning", "alert")
    assert result.anomaly_score >= 25

def test_l4_unknown_table_flagged():
    monitor = BehaviourMonitor(None)
    monitor.get_agent_baseline = MagicMock(return_value={
        "avg_actions_per_session": 10.0,
        "avg_delete_count": 5.0,
        "typical_tables": {"customers"},
        "typical_paths": {"/public/"},
        "typical_email_count_per_session": 2.0,
        "active_hours": [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    })
    
    session_ctx = {
        "action_count_this_session": 2,
        "current_hour": 14
    }
    
    action = {"tool": "delete_records", "params": {"table": "board_minutes", "count": 1}}
    result = monitor.check_action("agent1", action, session_ctx)
    assert any("board_minutes" in f for f in result.flags)

# =====================================================================
# INTEGRATION TESTS (MultiLayer Orchestrator)
# =====================================================================

def test_multilayer_hard_block_skips_later_layers():
    # Dry run evaluation for L1 hard block
    guardrail = MultiLayerGuardrail()
    action = {"tool": "delete_records", "params": {"table": "audit_trail", "count": 2}}
    agent_context = {
        "agent_id": "agent1",
        "agent_purpose": "Auditing records",
        "session": {"action_count_this_session": 1, "current_hour": 12}
    }
    
    # Run evaluation with dry run to prevent database writes
    result = guardrail.evaluate(action, agent_context, dry_run=True)
    assert result.outcome == "blocked"
    assert result.layer1["outcome"] == "blocked"
    # Layer 2 details should be skipped
    assert result.layer2["classification_source"] == "skipped"

def test_multilayer_l2_escalates_yaml_allow():
    guardrail = MultiLayerGuardrail()
    action = {"tool": "delete_records", "params": {"table": "employees", "count": 3}}
    agent_context = {
        "agent_id": "agent1",
        "agent_purpose": "HR management",
        "session": {"action_count_this_session": 1, "current_hour": 12}
    }
    
    result = guardrail.evaluate(action, agent_context, dry_run=True)
    # L1 says allow (count 3 < 40), but L2 classifies employees as PII/FINANCIAL which escalates to HITL
    assert result.outcome == "pending_review"
    assert "PII" in result.layer2["tags"]

def test_l4_cumulative_deletes_escalate():
    monitor = BehaviourMonitor(None)
    monitor.get_agent_baseline = MagicMock(return_value={
        "avg_actions_per_session": 10.0,
        "avg_delete_count": 5.0,
        "typical_tables": {"customers"},
        "typical_paths": {"/public/"},
        "typical_email_count_per_session": 2.0,
        "active_hours": [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    })
    
    mock_entry = MagicMock()
    mock_entry.tool = "delete_records"
    mock_entry.params = {"count": 95, "agent_id": "agent1"}
    mock_entry.executed = True
    
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = [mock_entry]
    
    monitor.session = MagicMock()
    monitor.session.query.return_value = mock_query
    
    session_ctx = {
        "action_count_this_session": 2,
        "current_hour": 14
    }
    
    action = {"tool": "delete_records", "params": {"table": "customers", "count": 10}}
    result = monitor.check_action("agent1", action, session_ctx)
    assert any("Cumulative deletes in last hour" in f for f in result.flags)
    assert result.anomaly_score >= 45
