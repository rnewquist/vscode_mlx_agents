from smolagents.tools import Tool
from .memory_manager import memory

class SendMessageTool(Tool):
    name = "send_message"
    description = "Sends a message or task to another subagent in the system."
    inputs = {
        "sender_agent": {
            "type": "string",
            "description": "The name or role of the agent sending the message."
        },
        "recipient_agent": {
            "type": "string",
            "description": "The name or role of the agent to send the message to (e.g., 'tester', 'reviewer')."
        },
        "message": {
            "type": "string",
            "description": "The message or task instructions to send."
        }
    }
    output_type = "string"

    def forward(self, sender_agent: str, recipient_agent: str, message: str) -> str:
        try:
            memory.log_interaction(sender_agent, recipient_agent, message)
            return f"Successfully sent message to {recipient_agent}: {message}"
        except Exception as e:
            import traceback
            return f"Error sending message to {recipient_agent}: {e}\n\nTraceback:\n{traceback.format_exc()}"
