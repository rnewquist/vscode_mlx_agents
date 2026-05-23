from smolagents.tools import Tool
import os
from . import diff_manager

class WriteFileTool(Tool):
    name = "write_file"
    description = "Writes content to a new file or completely overwrites an existing file."
    inputs = {
        "file_path": {
            "type": "string",
            "description": "The path to the file to write."
        },
        "content": {
            "type": "string",
            "description": "The content to write to the file."
        }
    }
    output_type = "string"

    def __init__(self, workspace_path=None, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def forward(self, file_path: str, content: str) -> str:
        if not self.workspace_path:
            return "Error: No workspace is active. File writes are only allowed when a workspace is open."
        
        # Resolve path relative to workspace if needed
        abs_path = os.path.abspath(file_path if os.path.isabs(file_path) else os.path.join(self.workspace_path, file_path))
        
        if not abs_path.startswith(os.path.abspath(self.workspace_path)):
            return f"Error: Attempted to write file outside of the active workspace ({self.workspace_path})."

        try:
            original_content = ""
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
            
            return diff_manager.request_diff(abs_path, original_content, content, self.name)
        except Exception as e:
            import traceback
            return f"Error staging write for {file_path}: {e}\n\nTraceback:\n{traceback.format_exc()}"
