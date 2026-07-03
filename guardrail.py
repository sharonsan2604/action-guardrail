import yaml
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class ParamsProxy:
    """
    A helper proxy class to allow dot-notation access to a dictionary's keys
    within safety-restricted eval() environments.
    """
    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data or {}

    def get(self, name: str, default: Any = None) -> Any:
        return self._data.get(name, default)

    def __getattr__(self, name: str) -> Any:
        # Check if the key exists, else return None
        return self._data.get(name, None)

    def __getitem__(self, name: str) -> Any:
        return self._data.get(name, None)

    def __contains__(self, item: str) -> bool:
        return item in self._data

    def __repr__(self) -> str:
        return repr(self._data)


class Guardrail:
    """
    Evaluates actions against security rules defined in a YAML policy configuration.
    """
    def __init__(self, rules_path: str = "rules.yaml") -> None:
        """
        Initializes the Guardrail engine by loading the rules configuration.
        
        Args:
            rules_path (str): The file path to the rules YAML.
        """
        self.rules_path = rules_path
        self.rules: List[Dict[str, Any]] = []
        self.default_action: str = "log_and_allow"
        self.load_rules()

    def load_rules(self) -> None:
        """
        Loads and parses the rules from the configured rules.yaml.
        """
        try:
            with open(self.rules_path, "r") as file:
                config = yaml.safe_load(file) or {}
                self.rules = config.get("rules", [])
                self.default_action = config.get("default_action", "log_and_allow")
            logger.info(f"Loaded {len(self.rules)} rules from {self.rules_path}. Default action: {self.default_action}")
        except Exception as e:
            logger.error(f"Failed to load rules from {self.rules_path}: {e}", exc_info=True)
            # Default fallbacks
            self.rules = []
            self.default_action = "block"  # Safe default on load failure

    def evaluate_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates an action against the loaded rules to determine security outcome.
        
        Args:
            action (Dict[str, Any]): The action structure containing 'tool' and 'params'.
                                     Example: {'tool': 'delete_records', 'params': {'count': 500}}
                                     
        Returns:
            Dict[str, Any]: Evaluation result mapping to:
                             - outcome: 'blocked' | 'pending_review' | 'allowed'
                             - matched_rule: rule name or 'default'
                             - reason: description of why policy decided this
        """
        tool = action.get("tool")
        params_dict = action.get("params", {})
        
        action_map = {
            "block": "blocked",
            "require_hitl": "pending_review",
            "log_and_allow": "allowed",
            "semantic_check": "semantic_check"
        }

        # Create the environment for eval
        eval_globals = {
            "__builtins__": {
                "abs": abs,
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "any": any,
                "all": all,
            }
        }
        params_proxy = ParamsProxy(params_dict)
        eval_locals = {
            "params": params_proxy
        }

        for rule in self.rules:
            # Check if this rule is for the action's tool
            if rule.get("tool") == tool:
                condition_str = rule.get("condition")
                rule_name = rule.get("name", "unnamed")
                rule_action = rule.get("action", "block")

                # If no condition is specified, it matches unconditionally
                if not condition_str:
                    outcome = action_map.get(rule_action, "blocked")
                    reason = f"Rule '{rule_name}' matched unconditionally."
                    logger.info(f"Action '{tool}' matched rule '{rule_name}': {outcome}")
                    return {
                        "outcome": outcome,
                        "matched_rule": rule_name,
                        "reason": reason
                    }

                try:
                    # Evaluate the condition string safely
                    match = eval(condition_str, eval_globals, eval_locals)
                    if match:
                        outcome = action_map.get(rule_action, "blocked")
                        reason = f"Rule '{rule_name}' condition '{condition_str}' evaluated to True."
                        logger.info(f"Action '{tool}' matched rule '{rule_name}': {outcome}")
                        return {
                            "outcome": outcome,
                            "matched_rule": rule_name,
                            "reason": reason
                        }
                except Exception as e:
                    # Log condition evaluation errors as warnings and continue evaluating other rules
                    logger.warning(f"Failed to evaluate condition '{condition_str}' for rule '{rule_name}': {e}")
                    # If evaluation fails, we might want to default to safety, but standard behavior here is warning and proceed
                    continue

        # If no rules match, apply default action
        outcome = action_map.get(self.default_action, "allowed")
        reason = f"No matching rules. Default action '{self.default_action}' applied."
        logger.info(f"Action '{tool}' fell back to default: {outcome}")
        return {
            "outcome": outcome,
            "matched_rule": "default",
            "reason": reason
        }
