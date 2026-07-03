import os
import re
import json
import logging
from typing import Any, Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Define functions mapping directly to available tools for Gemini's auto-schema extraction.
def delete_records(table: str, count: int):
    """
    Delete records from a database table.
    
    Args:
        table: The name of the database table (e.g. 'customers').
        count: The number of records to delete.
    """
    pass

def send_email(to: str, domain: str, body: str):
    """
    Send an email to a recipient.
    
    Args:
        to: The recipient name (e.g. 'alice').
        domain: The email domain (e.g. 'gmail.com').
        body: The body content of the email.
    """
    pass

def read_file(path: str):
    """
    Read a file from the filesystem.
    
    Args:
        path: The full path of the file to read (e.g. '/data/confidential/file.csv').
    """
    pass


class Agent:
    """
    LLM Agent powered by Google Gemini (with Offline fallback) that determines 
    actions based on natural language inputs.
    """
    def __init__(self) -> None:
        """
        Initializes the Gemini client using the GEMINI_API_KEY from environment variables.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "YOUR_GEMINI_KEY_HERE":
            logger.warning("GEMINI_API_KEY is not configured or contains placeholder value. Falling back to local offline parser.")
            self.model = None
        else:
            try:
                genai.configure(api_key=api_key)
                # Initialize Gemini model with tools
                self.model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    tools=[delete_records, send_email, read_file]
                )
                logger.info("Successfully configured Gemini API Client for Free-Tier execution.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}", exc_info=True)
                self.model = None

    def decide_offline(self, user_request: str) -> Optional[Dict[str, Any]]:
        """
        Regex-based offline pattern matching to parse tool actions when API key is missing.
        """
        req_lower = user_request.lower()
        
        # 1. Matches for delete_records
        if any(keyword in req_lower for keyword in ["delete", "remove", "drop", "purge", "clear"]):
            count = 1
            # Extract count (any number)
            count_match = re.search(r'\b(\d+)\b', req_lower)
            if count_match:
                count = int(count_match.group(1))
                
            table = "customers"
            # Try to extract table name: "from customers", "from the users table"
            table_match = re.search(r'from\s+(?:the\s+)?([a-zA-Z0-9_]+)', req_lower)
            if table_match:
                table = table_match.group(1)
            else:
                table_match2 = re.search(r'([a-zA-Z0-9_]+)\s+table', req_lower)
                if table_match2:
                    table = table_match2.group(1)
                    
            return {
                "tool": "delete_records",
                "params": {"table": table, "count": count}
            }
            
        # 2. Matches for send_email
        elif any(keyword in req_lower for keyword in ["email", "mail", "send"]):
            recipient = "recipient"
            domain = "mycompany.com"
            body = "System notification: SentinelAI Action Intercepted."
            
            # Check for emails like: "alice@gmail.com" or "alice at gmail.com"
            email_match = re.search(r'([a-zA-Z0-9_\.-]+)\s*@\s*([a-zA-Z0-9_\.-]+\.[a-zA-Z]{2,})', req_lower)
            if email_match:
                recipient = email_match.group(1)
                domain = email_match.group(2)
            else:
                at_match = re.search(r'([a-zA-Z0-9_\.-]+)\s+at\s+([a-zA-Z0-9_\.-]+\.[a-zA-Z]{2,})', req_lower)
                if at_match:
                    recipient = at_match.group(1)
                    domain = at_match.group(2)
                else:
                    # Look for recipient after 'to'
                    to_match = re.search(r'to\s+([a-zA-Z0-9_-]+)', req_lower)
                    if to_match:
                        recipient = to_match.group(1)
                        
            # Try to extract email body after saying, body, content, or message
            body_match = re.search(r'(?:saying|body|content|message)\s*[:=]?\s*(.+)', user_request, re.IGNORECASE)
            if body_match:
                body = body_match.group(1).strip()
            else:
                # Default body representation
                body = f"Notification email sent regarding: {user_request}"
                
            return {
                "tool": "send_email",
                "params": {"to": recipient, "domain": domain, "body": body}
            }
            
        # 3. Matches for read_file
        elif any(keyword in req_lower for keyword in ["read", "file", "open", "view", "cat"]):
            path = "/data/confidential/file.csv"
            # Match paths starting with "/" or containing typical formats
            path_match = re.search(r'(/[a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)', user_request)
            if path_match:
                path = path_match.group(1)
            else:
                path_match2 = re.search(r'(?:path|file)\s*[:=]?\s*([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)', user_request, re.IGNORECASE)
                if path_match2:
                    path = path_match2.group(1)
                    if not path.startswith('/'):
                        path = '/' + path
            return {
                "tool": "read_file",
                "params": {"path": path}
            }
            
        return None

    def decide(self, user_request: str) -> Optional[Dict[str, Any]]:
        """
        Queries Gemini to decide if a tool should be executed for the user request.
        Falls back to local offline parser if API key is not configured or fails.
        """
        # If Gemini is configured, try calling it
        if self.model:
            try:
                logger.info("Attempting tool-calling prediction using Gemini-1.5-Flash (Free-Tier API)...")
                response = self.model.generate_content(user_request)
                
                # Check for tool call
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if part.function_call:
                            fn_call = part.function_call
                            tool_name = fn_call.name
                            params = dict(fn_call.args)
                            
                            # Convert count param to int if it parsed as float/string
                            if "count" in params:
                                try:
                                    params["count"] = int(params["count"])
                                except Exception:
                                    pass
                                    
                            logger.info(f"Gemini decided to use tool '{tool_name}' with parameters: {params}")
                            return {
                                "tool": tool_name,
                                "params": params
                            }
                
                logger.info("Gemini resolved the request without proposing any registered tools.")
                return None
                
            except Exception as e:
                logger.warning(f"Gemini API request failed ({e}). Falling back to local offline parser.")
                
        # Trigger offline fallback parser
        logger.info("Running local offline heuristic agent engine.")
        offline_action = self.decide_offline(user_request)
        if offline_action:
            logger.info(f"Offline parser identified action: {offline_action['tool']} with parameters: {offline_action['params']}")
        else:
            logger.info("Offline parser found no matching tool patterns.")
        return offline_action
