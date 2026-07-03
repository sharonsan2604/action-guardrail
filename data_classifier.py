import yaml
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

@dataclass
class ClassificationResult:
    tags: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low | medium | high | critical
    classification_source: str = "default"
    recommended_action: str = "allow"  # allow | semantic_check | require_hitl | block
    details_str: str = ""

class DataClassifier:
    """
    Evaluates actions against a data classification registry to assign risk categories and security tags.
    """
    def __init__(self, registry_path: str = "data_registry.yaml") -> None:
        self.registry_path = registry_path
        self.tables: Dict[str, List[str]] = {}
        self.paths: Dict[str, List[str]] = {}
        self.email_recipients: Dict[str, List[str]] = {}
        self.email_keywords: List[str] = []
        self.unclassified_action: str = "semantic_check"
        self.load_registry()

    def load_registry(self) -> None:
        try:
            with open(self.registry_path, "r") as file:
                config = yaml.safe_load(file) or {}
                self.tables = config.get("tables", {})
                self.paths = config.get("paths", {})
                self.email_recipients = config.get("email_recipients", {})
                self.email_keywords = config.get("email_keywords_high_risk", [])
                self.unclassified_action = config.get("unclassified_action", "semantic_check")
            logger.info(f"Loaded data registry from {self.registry_path}")
        except Exception as e:
            logger.error(f"Failed to load data registry: {e}", exc_info=True)

    def classify(self, action: Dict[str, Any]) -> ClassificationResult:
        tool = action.get("tool")
        params = action.get("params", {})
        tags = []
        source = "unclassified"
        
        if tool == "delete_records":
            table = params.get("table", "")
            if table in self.tables:
                tags = list(self.tables[table])
                source = f"table:{table}"
            else:
                source = f"unclassified_table:{table}"

        elif tool == "read_file":
            path = params.get("path", "")
            # Longest prefix match for paths
            best_prefix = ""
            best_tags = []
            for prefix, prefix_tags in self.paths.items():
                if path.startswith(prefix) and len(prefix) > len(best_prefix):
                    best_prefix = prefix
                    best_tags = prefix_tags
            
            if best_prefix:
                tags = list(best_tags)
                source = f"path_prefix:{best_prefix}"
            else:
                source = f"unclassified_path:{path}"

        elif tool == "send_email":
            to = params.get("to", "")
            domain = params.get("domain", "")
            body = params.get("body", "")
            
            email_address = f"{to}@{domain}"
            email_source_parts = []
            
            # Check direct recipient match
            if email_address in self.email_recipients:
                tags.extend(self.email_recipients[email_address])
                email_source_parts.append(f"recipient:{email_address}")
            elif to in self.email_recipients:
                tags.extend(self.email_recipients[to])
                email_source_parts.append(f"recipient:{to}")
                
            # Scan email body for high-risk terms
            body_lower = body.lower()
            found_keywords = []
            for keyword in self.email_keywords:
                if keyword.lower() in body_lower:
                    found_keywords.append(keyword)
            
            if found_keywords:
                email_source_parts.append(f"keywords:{','.join(found_keywords)}")
                # Map keyword classifications
                for kw in found_keywords:
                    if kw in ["salary", "compensation", "termination"]:
                        if "FINANCIAL" not in tags: tags.append("FINANCIAL")
                        if "PII" not in tags: tags.append("PII")
                    elif kw in ["confidential", "board", "acquisition", "lawsuit"]:
                        if "EXECUTIVE" not in tags: tags.append("EXECUTIVE")
                    elif kw in ["password", "credentials"]:
                        if "SYSTEM" not in tags: tags.append("SYSTEM")
            
            # Deduplicate email tags
            tags = list(set(tags))
            if email_source_parts:
                source = ";".join(email_source_parts)
            else:
                source = "unclassified_email"

        # If no classifications matched, set to default unclassified
        is_unclassified = (len(tags) == 0)

        # Compute risk_level from tags:
        # LEGAL_HOLD or EXECUTIVE -> critical
        # PII + FINANCIAL together -> high
        # PII alone or FINANCIAL alone -> medium
        # SYSTEM -> medium
        # PUBLIC -> low
        # Empty tags (unclassified) -> medium (unknown = caution)
        risk_level = "low"
        if "LEGAL_HOLD" in tags or "EXECUTIVE" in tags:
            risk_level = "critical"
        elif "PII" in tags and "FINANCIAL" in tags:
            risk_level = "high"
        elif "PII" in tags or "FINANCIAL" in tags or "SYSTEM" in tags:
            risk_level = "medium"
        elif "PUBLIC" in tags:
            risk_level = "low"
        elif is_unclassified:
            risk_level = "medium" # default caution for unknown items

        # Compute recommended_action from risk_level and tags:
        # critical -> block (if LEGAL_HOLD & delete) or require_hitl (EXECUTIVE/LEGAL_HOLD read)
        # high -> require_hitl
        # medium -> semantic_check
        # low -> allow
        recommended_action = "allow"
        
        if "LEGAL_HOLD" in tags:
            if tool == "delete_records":
                recommended_action = "block"
            else:
                recommended_action = "require_hitl"
        elif "EXECUTIVE" in tags:
            recommended_action = "require_hitl"
        elif risk_level == "high":
            recommended_action = "require_hitl"
        elif risk_level == "medium":
            recommended_action = "semantic_check"
        elif is_unclassified:
            # Check defaults
            recommended_action = self.unclassified_action
        else:
            recommended_action = "allow"

        details_str = f"Source: {source} | Risk: {risk_level.upper()} | Tags: {','.join(tags) if tags else 'none'}"

        return ClassificationResult(
            tags=tags,
            risk_level=risk_level,
            classification_source=source,
            recommended_action=recommended_action,
            details_str=details_str
        )
