import os
from smolagents.tools import Tool

class ListDirTool(Tool):
    name = "list_dir"
    description = "Lists the contents of a directory, returning files and folders."
    inputs = {
        "directory_path": {
            "type": "string",
            "description": "The path to the directory to list."
        }
    }
    output_type = "string"

    def __init__(self, workspace_path=None, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def forward(self, directory_path: str) -> str:
        if not self.workspace_path:
            return "Error: No workspace is active. Directory listing is only allowed when a workspace is open."
        
        # Resolve path relative to workspace if needed
        abs_path = os.path.abspath(directory_path if os.path.isabs(directory_path) else os.path.join(self.workspace_path, directory_path))
        
        if not abs_path.startswith(os.path.abspath(self.workspace_path)):
            return f"Error: Attempted to list directory outside of the active workspace ({self.workspace_path})."

        try:
            if not os.path.exists(abs_path):
                return f"Error: Directory '{abs_path}' does not exist."
            if not os.path.isdir(abs_path):
                return f"Error: '{abs_path}' is not a directory."
                
            items = os.listdir(abs_path)
            output = [f"Contents of {directory_path}:"]
            for item in sorted(items):
                full_item_path = os.path.join(abs_path, item)
                item_type = "DIR" if os.path.isdir(full_item_path) else "FILE"
                output.append(f"[{item_type}] {item}")
            return "\n".join(output)
        except Exception as e:
            import traceback
            return f"Error listing directory {directory_path}: {e}\n\nTraceback:\n{traceback.format_exc()}"
