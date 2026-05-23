import subprocess
from smolagents.tools import Tool
from .memory_manager import memory

class CommandStatusTool(Tool):
    name = "command_status"
    description = "Checks the status and reads the output of a background terminal command."
    inputs = {
        "command_id": {
            "type": "string",
            "description": "The ID of the background command to check."
        }
    }
    output_type = "string"

    def forward(self, command_id: str) -> str:
        try:
            process = memory.get_process(command_id)
            if not process:
                return f"Error: No active process found with ID {command_id}."
            
            # Read output if available (non-blocking)
            import fcntl
            import os
            
            # Helper to make stream non-blocking
            def set_non_blocking(fd):
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            
            if process.stdout:
                set_non_blocking(process.stdout.fileno())
            if process.stderr:
                set_non_blocking(process.stderr.fileno())
                
            stdout_data = ""
            stderr_data = ""
            
            if process.stdout:
                try:
                    stdout_data = process.stdout.read() or ""
                except (IOError, TypeError):
                    pass
                    
            if process.stderr:
                try:
                    stderr_data = process.stderr.read() or ""
                except (IOError, TypeError):
                    pass
            
            status = process.poll()
            state = "RUNNING" if status is None else f"EXITED with code {status}"
            
            output = f"Status: {state}\n"
            if stdout_data:
                output += f"Stdout:\n{stdout_data}\n"
            if stderr_data:
                output += f"Stderr:\n{stderr_data}\n"
                
            if not stdout_data and not stderr_data:
                output += "(No new output)"
                
            return output
        except Exception as e:
            import traceback
            return f"Error checking command status: {e}\n\nTraceback:\n{traceback.format_exc()}"
