from smolagents.tools import Tool
import os
from . import diff_manager

class EditFileTool(Tool):
    name = "edit_file"
    description = "Edits a file by replacing occurrences of target_text with replacement_text."
    inputs = {
        "file_path": {
            "type": "string",
            "description": "The path to the file to edit."
        },
        "target_text": {
            "type": "string",
            "description": "The exact text to find and replace in the file."
        },
        "replacement_text": {
            "type": "string",
            "description": "The new text to insert in place of target_text."
        }
    }
    output_type = "string"

    def __init__(self, workspace_path=None, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def forward(self, file_path: str, target_text: str, replacement_text: str) -> str:
        if not self.workspace_path:
            return "Error: No workspace is active. Code edits are only allowed when a workspace is open."
        
        # Resolve path relative to workspace if needed
        abs_path = os.path.abspath(file_path if os.path.isabs(file_path) else os.path.join(self.workspace_path, file_path))
        
        if not abs_path.startswith(os.path.abspath(self.workspace_path)):
            return f"Error: Attempted to edit file outside of the active workspace ({self.workspace_path})."

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            if target_text not in content:
                return f"Error: '{target_text}' not found in {file_path}"
                
            new_content = content.replace(target_text, replacement_text)
            
            return diff_manager.request_diff(file_path, content, new_content, self.name)
        except Exception as e:
            import traceback
            return f"Error staging edit for {file_path}: {e}\n\nTraceback:\n{traceback.format_exc()}"
