import os
from smolagents.tools import Tool

class ViewFileTool(Tool):
    name = "view_file"
    description = "View the contents of a local file. You can specify start_line and end_line to view specific sections."
    inputs = {
        "file_path": {
            "type": "string",
            "description": "The absolute or relative path to the file to view."
        },
        "start_line": {
            "type": "integer",
            "description": "Optional starting line number (1-indexed). Defaults to 1.",
            "nullable": True
        },
        "end_line": {
            "type": "integer",
            "description": "Optional ending line number. Defaults to the end of the file.",
            "nullable": True
        }
    }
    output_type = "string"

    def __init__(self, workspace_path=None, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def forward(self, file_path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        if not self.workspace_path:
            return "Error: No workspace is active. File viewing is only allowed when a workspace is open."
        
        # Resolve path relative to workspace if needed
        abs_path = os.path.abspath(file_path if os.path.isabs(file_path) else os.path.join(self.workspace_path, file_path))
        
        if not abs_path.startswith(os.path.abspath(self.workspace_path)):
            return f"Error: Attempted to view file outside of the active workspace ({self.workspace_path})."

        try:
            if not os.path.exists(abs_path):
                return f"Error: File '{abs_path}' does not exist."
            
            with open(abs_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            if start_line is None:
                start_line = 1
            if end_line is None:
                end_line = len(lines)
                
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)
            
            content = "".join(lines[start_idx:end_idx])
            return f"--- {file_path} (Lines {start_line}-{end_line}) ---\n{content}"
        except Exception as e:
            import traceback
            return f"Error viewing file {file_path}: {e}\n\nTraceback:\n{traceback.format_exc()}"
