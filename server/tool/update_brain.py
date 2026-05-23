from smolagents.tools import Tool
from .memory_manager import memory

class UpdateBrainTool(Tool):
    name = "update_brain"
    description = "Updates your brain file with a new learning, fixed mistake, or optimized process. This will be injected into your prompt for all future tasks."
    inputs = {
        "agent_name": {
            "type": "string",
            "description": "Your agent name."
        },
        "learning": {
            "type": "string",
            "description": "The rule, process, or mistake fix you want to remember permanently."
        }
    }
    output_type = "string"

    def forward(self, agent_name: str, learning: str) -> str:
        try:
            memory.update_brain(agent_name, learning)
            return f"Successfully updated brain for {agent_name} with: {learning}"
        except Exception as e:
            return f"Error updating brain: {e}"
