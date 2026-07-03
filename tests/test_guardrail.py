import os
import sys
import pytest

# Ensure the parent directory is in Python path to import guardrail modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guardrail import Guardrail

@pytest.fixture
def guardrail():
    # Load guardrail rules with standard rules.yaml path in parent directory
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rules_path = os.path.join(parent_dir, "rules.yaml")
    return Guardrail(rules_path=rules_path)

def test_block_bulk_delete(guardrail):
    action = {"tool": "delete_records", "params": {"table": "customers", "count": 500}}
    result = guardrail.evaluate_action(action)
    assert result["outcome"] == "blocked"
    assert result["matched_rule"] == "block_bulk_delete"

def test_allow_small_delete(guardrail):
    action = {"tool": "delete_records", "params": {"table": "customers", "count": 5}}
    result = guardrail.evaluate_action(action)
    assert result["outcome"] == "allowed"

def test_hitl_external_email(guardrail):
    action = {"tool": "send_email", "params": {"to": "alice", "domain": "gmail.com", "body": "test"}}
    result = guardrail.evaluate_action(action)
    assert result["outcome"] == "pending_review"
    assert result["matched_rule"] == "hitl_external_email"

def test_allow_internal_email(guardrail):
    action = {"tool": "send_email", "params": {"to": "bob", "domain": "mycompany.com", "body": "test"}}
    result = guardrail.evaluate_action(action)
    assert result["outcome"] in ("allowed", "semantic_check")

def test_log_confidential_read(guardrail):
    action = {"tool": "read_file", "params": {"path": "/data/confidential/x.csv"}}
    result = guardrail.evaluate_action(action)
    assert result["outcome"] == "allowed"
    assert result["matched_rule"] == "log_confidential_read"

def test_default_action_for_unknown(guardrail):
    action = {"tool": "read_file", "params": {"path": "/public/data.csv"}}
    result = guardrail.evaluate_action(action)
    assert result["outcome"] == "allowed"
    assert result["matched_rule"] == "default"
