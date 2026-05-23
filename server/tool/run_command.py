import subprocess
from smolagents.tools import Tool
from .memory_manager import memory

class RunCommandTool(Tool):
    name = "run_command"
    description = "Runs a shell command and returns its output. Can optionally run in the background."
    inputs = {
        "command": {
            "type": "string",
            "description": "The shell command to run."
        },
        "run_in_background": {
            "type": "boolean",
            "description": "If true, starts the command in the background and returns a command ID. You can check status later or send input.",
            "nullable": True
        }
    }
    output_type = "string"

    def __init__(self, workspace_path=None, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def forward(self, command: str, run_in_background: bool | None = False) -> str:
        if not self.workspace_path:
            return "Error: No workspace is active. Command execution is only allowed when a workspace is open."

        try:
            if run_in_background:
                # Use subprocess.Popen for background execution
                process = subprocess.Popen(
                    command, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    cwd=self.workspace_path
                )
                command_id = memory.register_process(process)
                return f"Started background process '{command}' in {self.workspace_path} with ID: {command_id}"
            else:
                result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=self.workspace_path)
                output = result.stdout
                if result.stderr:
                    output += "\nError output:\n" + result.stderr
                return output
        except Exception as e:
            import traceback
            return f"Error running command: {e}\n\nTraceback:\n{traceback.format_exc()}"
