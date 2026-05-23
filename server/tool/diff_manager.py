import threading
import uuid
import os
from . import artifact_manager

# Global registry for pending diffs
pending_diffs = {}

class DiffRequest:
    def __init__(self, file_path: str, original_content: str, new_content: str, tool_name: str):
        self.id = str(uuid.uuid4())
        self.file_path = file_path
        self.original_content = original_content
        self.new_content = new_content
        self.tool_name = tool_name
        self.event = threading.Event()
        self.status = "pending" # 'pending', 'accepted', 'rejected'
        self.feedback = ""

def request_diff(file_path: str, original_content: str, new_content: str, tool_name: str) -> str:
    """
    Submits a diff request.
    Automatically approves and writes if the file is local to the project.
    Otherwise, blocks until the user accepts or rejects it.
    """
    abs_path = os.path.abspath(file_path)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Auto-approve if the file is within our project root
    is_auto_approve = abs_path.startswith(base_dir)
    
    if is_auto_approve:
        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            artifact_manager.add_artifact(abs_path)
            return f"Successfully applied {tool_name} to {file_path}. (Auto-approved local file)"
        except Exception as e:
            return f"Failed to write to {file_path}: {e}"

    req = DiffRequest(file_path, original_content, new_content, tool_name)
    pending_diffs[req.id] = req
    
    # Block and wait for frontend resolution
    req.event.wait()
    
    if req.status == "accepted":
        try:
            # Ensure directory exists before writing
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            
            # Register as an artifact
            artifact_manager.add_artifact(file_path)
                
            return f"Successfully applied {tool_name} to {file_path}. User approved."
        except Exception as e:
            return f"User approved, but failed to write to {file_path}: {e}"
    else:
        return f"User REJECTED the change to {file_path}. Feedback: {req.feedback}"

def get_all_pending() -> list:
    return [
        {
            "id": req.id,
            "file_path": req.file_path,
            "original_content": req.original_content,
            "new_content": req.new_content,
            "tool_name": req.tool_name
        }
        for req in pending_diffs.values() if req.status == "pending"
    ]

def resolve(diff_id: str, accept: bool, feedback: str):
    if diff_id in pending_diffs:
        req = pending_diffs[diff_id]
        req.status = "accepted" if accept else "rejected"
        req.feedback = feedback
        req.event.set()
        del pending_diffs[diff_id]
        return True
    return False
