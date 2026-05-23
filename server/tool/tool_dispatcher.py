"""
A meta-tool that acts as a lazy dispatcher.
The agent sees ONE tool in its prompt but can access ALL tools through it.
This dramatically reduces prefill tokens since only one schema is serialized.
"""

import traceback
from smolagents import Tool


class ToolDispatcher(Tool):
    name = "use_tool"
    description = (
        "Access any tool from the toolbox. Pass the tool name and its arguments as a JSON string. "
        "Available tools:\n"
    )
    inputs = {
        "tool_name": {
            "type": "string",
            "description": "Name of the tool to invoke (see available tools in your system prompt).",
        },
        "arguments": {
            "type": "string",
            "description": 'JSON string of arguments for the tool, e.g. {"file_path": "/tmp/test.txt", "content": "hello"}',
        },
    }
    output_type = "string"

    def __init__(self, tools: list[Tool], **kwargs):
        # Build the catalog BEFORE calling super().__init__
        # so self.description is complete when smolagents serializes it
        catalog_lines = []
        self._tool_map: dict[str, Tool] = {}
        for tool in tools:
            self._tool_map[tool.name] = tool
            # Compact: just name + one-line description
            inputs_summary = ", ".join(tool.inputs.keys()) if tool.inputs else "none"
            catalog_lines.append(f"  - {tool.name}({inputs_summary}): {tool.description[:120]}")

        ToolDispatcher.description = (
            "Access any tool from the toolbox. Pass the tool name and its arguments as a JSON string.\n"
            "Available tools:\n" + "\n".join(catalog_lines)
        )

        super().__init__(**kwargs)

    def forward(self, tool_name: str, arguments: str) -> str:
        try:
            import json

            tool = self._tool_map.get(tool_name)
            if not tool:
                available = ", ".join(self._tool_map.keys())
                return f"Error: Unknown tool '{tool_name}'. Available: {available}"

            # Parse the arguments JSON
            if arguments.strip():
                args = json.loads(arguments)
            else:
                args = {}

            # Invoke the actual tool
            result = tool.forward(**args)
            return str(result)

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON arguments: {e}. Pass a valid JSON object string."
        except Exception as e:
            return f"Error calling '{tool_name}': {e}\n\nTraceback:\n{traceback.format_exc()}"
