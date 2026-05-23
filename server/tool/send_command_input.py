from smolagents.tools import Tool
from .memory_manager import memory

class SendCommandInputTool(Tool):
    name = "send_command_input"
    description = "Sends standard input to a running background command, or terminates it."
    inputs = {
        "command_id": {
            "type": "string",
            "description": "The ID of the background command."
        },
        "input_text": {
            "type": "string",
            "description": "The text to send to stdin. Include newline (\\n) if needed.",
            "nullable": True
        },
        "terminate": {
            "type": "boolean",
            "description": "If true, terminates the background process.",
            "nullable": True
        }
    }
    output_type = "string"

    def forward(self, command_id: str, input_text: str | None = None, terminate: bool | None = False) -> str:
        try:
            process = memory.get_process(command_id)
            if not process:
                return f"Error: No active process found with ID {command_id}."
                
            if terminate:
                memory.terminate_process(command_id)
                return f"Terminated process {command_id}."
                
            if input_text and process.stdin:
                process.stdin.write(input_text)
                process.stdin.flush()
                return f"Sent input to process {command_id}."
                
            return "No action taken. Provide input_text or set terminate to true."
        except Exception as e:
            import traceback
            return f"Error sending input: {e}\n\nTraceback:\n{traceback.format_exc()}"
