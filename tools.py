from typing import Any, Dict

def delete_records(table: str, count: int) -> Dict[str, Any]:
    """
    Simulates deleting records from a database table.
    
    Args:
        table (str): The name of the database table.
        count (int): The number of records to delete.
        
    Returns:
        Dict[str, Any]: A execution status dictionary.
    """
    if not table:
        return {"status": "error", "message": "Table name cannot be empty."}
    if count is None or not isinstance(count, int) or count < 0:
        return {"status": "error", "message": "Invalid record count."}
        
    print(f"[TOOL EXECUTED] Deleted {count} records from {table}")
    return {"status": "success", "deleted": count, "table": table}

def send_email(to: str, domain: str, body: str) -> Dict[str, Any]:
    """
    Simulates sending an email.
    
    Args:
        to (str): Recipient user portion of the email.
        domain (str): Domain portion of the email.
        body (str): Email body content.
        
    Returns:
        Dict[str, Any]: An execution status dictionary.
    """
    if not to or not domain:
        return {"status": "error", "message": "Recipient and domain cannot be empty."}
        
    print(f"[TOOL EXECUTED] Email sent to {to}@{domain}")
    return {"status": "success", "to": to, "domain": domain}

def read_file(path: str) -> Dict[str, Any]:
    """
    Simulates reading a file.
    
    Args:
        path (str): Path of the file to read.
        
    Returns:
        Dict[str, Any]: An execution status dictionary.
    """
    if not path:
        return {"status": "error", "message": "File path cannot be empty."}
        
    print(f"[TOOL EXECUTED] Read file at {path}")
    return {"status": "success", "path": path}

TOOL_REGISTRY = {
    "delete_records": delete_records,
    "send_email": send_email,
    "read_file": read_file,
}
