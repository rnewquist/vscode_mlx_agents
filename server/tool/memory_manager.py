import os
import subprocess
import uuid
import shutil

class MemoryManager:
    def __init__(self):
        # RAM storage
        self.shared_memory = []
        self.interaction_logs = []
        
        # Background processes
        self.active_processes = {}
        
        # Base directory (parent of 'tool' directory)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Disk paths
        self.gemini_dir = os.path.abspath(os.path.join(base_dir, ".gemini"))
        self.shared_memory_file = os.path.join(self.gemini_dir, "execution_memory.md")
        self.interaction_logs_file = os.path.join(self.gemini_dir, "interaction_logs.md")
        self.models_config_file = os.path.join(self.gemini_dir, "models_config.json")
        self.agents_dir = os.path.join(self.gemini_dir, "agents")
        
        # Ensure base directories exist
        os.makedirs(self.gemini_dir, exist_ok=True)
        os.makedirs(self.agents_dir, exist_ok=True)
        
        import sys
        sys.stderr.write(f"MemoryManager initialized with base_dir: {base_dir}\n")
        sys.stderr.write(f"Models config path: {self.models_config_file}\n")
        
        # Load existing disk content into RAM if files exist
        if os.path.exists(self.shared_memory_file):
            with open(self.shared_memory_file, "r") as f:
                content = f.read().strip()
                if content:
                    self.shared_memory = content.split("\n")
                    
        if os.path.exists(self.interaction_logs_file):
            with open(self.interaction_logs_file, "r") as f:
                content = f.read().strip()
                if content:
                    self.interaction_logs = content.split("\n")

    def get_models_config(self) -> dict:
        import json
        import sys
        if os.path.exists(self.models_config_file):
            try:
                with open(self.models_config_file, "r") as f:
                    config = json.load(f)
                    sys.stderr.write(f"Successfully loaded models config from disk: {config}\n")
                    return config
            except Exception as e:
                sys.stderr.write(f"Failed to load models config from {self.models_config_file}: {e}\n")
                return {}
        sys.stderr.write(f"Models config file not found at {self.models_config_file}\n")
        return {}

    def save_models_config(self, config: dict):
        import json
        import sys
        try:
            os.makedirs(os.path.dirname(self.models_config_file), exist_ok=True)
            with open(self.models_config_file, "w") as f:
                json.dump(config, f, indent=4)
            sys.stderr.write(f"Successfully saved models config to disk: {config}\n")
        except Exception as e:
            sys.stderr.write(f"Failed to save models config: {e}\n")

    def append_shared_memory(self, content: str):
        self.shared_memory.append(content)
        
    def get_shared_memory(self) -> str:
        return "\n".join(self.shared_memory)

    def log_interaction(self, sender: str, recipient: str, message: str):
        log_entry = f"[{sender} -> {recipient}]: {message}"
        self.interaction_logs.append(log_entry)

    def setup_agent_workspace(self, agent_name: str) -> str:
        agent_dir = os.path.join(self.agents_dir, agent_name)
        scratch_dir = os.path.join(agent_dir, "scratch")
        os.makedirs(scratch_dir, exist_ok=True)
        return scratch_dir

    def read_brain(self, agent_name: str) -> str:
        brain_path = os.path.join(self.agents_dir, agent_name, "brain.md")
        if os.path.exists(brain_path):
            with open(brain_path, "r") as f:
                return f.read()
        return "You have no past learnings yet. This is an empty brain."

    def update_brain(self, agent_name: str, learning: str):
        agent_dir = os.path.join(self.agents_dir, agent_name)
        os.makedirs(agent_dir, exist_ok=True)
        brain_path = os.path.join(agent_dir, "brain.md")
        # Append to the brain file immediately
        with open(brain_path, "a") as f:
            f.write(f"- {learning}\n")

    # --- Main Agent Brain (workspace-scoped, persistent) ---

    def read_main_brain(self, workspace_path: str) -> str:
        """Read the main agent's brain from the given workspace."""
        brain_path = os.path.join(workspace_path, ".gemini", "main_brain.md")
        if os.path.exists(brain_path):
            with open(brain_path, "r") as f:
                return f.read()
        return "You have no past learnings yet for this workspace. This is a fresh brain."

    def update_main_brain(self, workspace_path: str, learning: str):
        """Append a learning to the main agent's brain in the given workspace."""
        gemini_dir = os.path.join(workspace_path, ".gemini")
        os.makedirs(gemini_dir, exist_ok=True)
        brain_path = os.path.join(gemini_dir, "main_brain.md")
        with open(brain_path, "a") as f:
            f.write(f"- {learning}\n")

    # --- Subagent Workspace Management ---

    def delete_agent_workspace(self, agent_name: str):
        agent_dir = os.path.join(self.agents_dir, agent_name)
        if os.path.exists(agent_dir):
            shutil.rmtree(agent_dir, ignore_errors=True)

    def flush_to_disk(self):
        # Write shared memory
        with open(self.shared_memory_file, "w") as f:
            f.write("\n".join(self.shared_memory))
            
        # Write logs
        with open(self.interaction_logs_file, "w") as f:
            f.write("\n".join(self.interaction_logs))

    def clear_all(self):
        # 1. Clear RAM
        self.shared_memory = []
        self.interaction_logs = []
        
        # 2. Terminate all active processes
        for cmd_id, proc in self.active_processes.items():
            try:
                proc.terminate()
            except Exception:
                pass
        self.active_processes = {}
        
        # 3. Delete execution and log files
        if os.path.exists(self.shared_memory_file):
            os.remove(self.shared_memory_file)
        if os.path.exists(self.interaction_logs_file):
            os.remove(self.interaction_logs_file)
            
        # 4. Delete all agent workspaces
        if os.path.exists(self.agents_dir):
            shutil.rmtree(self.agents_dir, ignore_errors=True)
            os.makedirs(self.agents_dir, exist_ok=True)

    # Process Management
    def register_process(self, process: subprocess.Popen) -> str:
        command_id = str(uuid.uuid4())[:8]
        self.active_processes[command_id] = process
        return command_id

    def get_process(self, command_id: str) -> subprocess.Popen | None:
        return self.active_processes.get(command_id)

    def terminate_process(self, command_id: str) -> bool:
        process = self.active_processes.get(command_id)
        if process:
            process.terminate()
            return True
        return False

# Global instance for blazing fast RAM access across all tools
memory = MemoryManager()
