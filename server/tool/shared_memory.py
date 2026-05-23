from smolagents.tools import Tool
from .memory_manager import memory

class AppendSharedMemoryTool(Tool):
    name = "append_shared_memory"
    description = "Appends highly important information to the blazing fast RAM-based shared memory to communicate context with other agents. IMPORTANT: Do not bloat the shared memory with specific details. Only include critical context that other agents absolutely need to know."
    inputs = {
        "content": {
            "type": "string",
            "description": "The content to append to the memory."
        }
    }
    output_type = "string"

    def forward(self, content: str) -> str:
        try:
            memory.append_shared_memory(content)
            return "Successfully appended to shared memory."
        except Exception as e:
            import traceback
            return f"Error writing to shared memory: {e}\n\nTraceback:\n{traceback.format_exc()}"

class ReadSharedMemoryTool(Tool):
    name = "read_shared_memory"
    description = "Reads the content of the RAM-based shared memory to get context from other agents."
    inputs = {}
    output_type = "string"

    def forward(self) -> str:
        try:
            content = memory.get_shared_memory()
            if not content:
                return "Shared memory is currently empty."
            return content
        except Exception as e:
            import traceback
            return f"Error reading shared memory: {e}\n\nTraceback:\n{traceback.format_exc()}"
