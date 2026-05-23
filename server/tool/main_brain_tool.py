"""
Tool that allows the Main Agent to update its own persistent brain
during reasoning. The brain is workspace-scoped.
"""

import traceback
from smolagents import Tool


class UpdateMainBrainTool(Tool):
    name = "update_my_brain"
    description = (
        "Save an important learning, fact, or user preference to your persistent brain. "
        "This information will survive across sessions and be available next time this workspace is opened. "
        "Use this to remember things the user tells you about their preferences, project architecture, or key decisions."
    )
    inputs = {
        "learning": {
            "type": "string",
            "description": "The fact, preference, or learning to permanently remember.",
        },
    }
    output_type = "string"

    def __init__(self, memory, **kwargs):
        super().__init__(**kwargs)
        self._memory = memory
        self._workspace_path = None  # Set dynamically before each run

    def forward(self, learning: str) -> str:
        try:
            if not self._workspace_path:
                return "Error: workspace_path not set. Cannot persist brain."
            self._memory.update_main_brain(self._workspace_path, learning)
            return f"Saved to brain: {learning}"
        except Exception as e:
            return f"Error saving to brain: {e}\n\nTraceback:\n{traceback.format_exc()}"
