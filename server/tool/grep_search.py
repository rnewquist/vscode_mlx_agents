import subprocess
from smolagents.tools import Tool

class GrepSearchTool(Tool):
    name = "grep_search"
    description = "Uses standard grep to find exact pattern matches within files or directories."
    inputs = {
        "search_path": {
            "type": "string",
            "description": "The path to search. This can be a directory or a file."
        },
        "query": {
            "type": "string",
            "description": "The search term or pattern to look for within files."
        }
    }
    output_type = "string"

    def __init__(self, workspace_path=None, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def forward(self, search_path: str, query: str) -> str:
        if not self.workspace_path:
            return "Error: No workspace is active. Grep search is only allowed when a workspace is open."
        
        # Resolve path relative to workspace if needed
        abs_path = os.path.abspath(search_path if os.path.isabs(search_path) else os.path.join(self.workspace_path, search_path))
        
        if not abs_path.startswith(os.path.abspath(self.workspace_path)):
            return f"Error: Attempted to search outside of the active workspace ({self.workspace_path})."

        try:
            # -r: recursive, -n: line number, -I: ignore binary
            cmd = ["grep", "-rnI", query, abs_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout
            elif result.returncode == 1:
                return f"No matches found for '{query}' in {search_path}."
            else:
                return f"Error running grep: {result.stderr}"
        except Exception as e:
            import traceback
            return f"Exception during grep search: {e}\n\nTraceback:\n{traceback.format_exc()}"
