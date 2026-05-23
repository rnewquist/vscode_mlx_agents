"""
Management tools that the Main Agent uses during its own reasoning.
These are smolagents Tool subclasses that let the orchestrator
create, list, delegate to, and shut down subagents autonomously.
"""

import sys
import traceback
from contextlib import redirect_stdout
from smolagents import Tool, CodeAgent


class CreateAgentTool(Tool):
    name = "create_agent"
    description = "Create a new specialized subagent with a given name and personality. Use this when a task would benefit from a dedicated specialist."
    inputs = {
        "agent_name": {"type": "string", "description": "Unique name for the new agent."},
        "system_prompt": {"type": "string", "description": "Instructions and personality for the agent."},
    }
    output_type = "string"

    def __init__(self, agents_registry, memory, **kwargs):
        super().__init__(**kwargs)
        self._registry = agents_registry
        self._memory = memory

    def forward(self, agent_name: str, system_prompt: str) -> str:
        try:
            if agent_name in self._registry:
                return f"Agent '{agent_name}' already exists."

            scratch_dir = self._memory.setup_agent_workspace(agent_name)

            identity_prompt = (
                f"\n\nIMPORTANT: Your agent name is '{agent_name}'. "
                f"You share RAM memory with other agents via 'append_shared_memory' and 'read_shared_memory'. "
                f"You can update your permanent knowledge by calling 'update_brain' using your name. "
                f"Your personal scratch space for temporary files, notes, and scratchpads is located at: '{scratch_dir}'."
            )
            self._registry[agent_name] = system_prompt + identity_prompt
            return f"Successfully created agent '{agent_name}'."
        except Exception as e:
            return f"Failed to create agent '{agent_name}': {e}\n\nTraceback:\n{traceback.format_exc()}"


class ListAgentsTool(Tool):
    name = "list_agents"
    description = "List all currently registered subagents."
    inputs = {}
    output_type = "string"

    def __init__(self, agents_registry, **kwargs):
        super().__init__(**kwargs)
        self._registry = agents_registry

    def forward(self) -> str:
        agents = [name for name in self._registry.keys() if name != "default"]
        if not agents:
            return "No subagents are currently registered."
        return "Registered subagents: " + ", ".join(agents)


class DelegateToAgentTool(Tool):
    name = "delegate_to_agent"
    description = "Delegate a task to a specific subagent and return its response. The subagent will use its own tools and brain to complete the task."
    inputs = {
        "agent_name": {"type": "string", "description": "Name of the subagent to delegate to."},
        "task": {"type": "string", "description": "The task or prompt to send to the subagent."},
    }
    output_type = "string"

    def __init__(self, agents_registry, memory, mlx_model, shared_tools, **kwargs):
        super().__init__(**kwargs)
        self._registry = agents_registry
        self._memory = memory
        self._model = mlx_model
        self._shared_tools = shared_tools

    def forward(self, agent_name: str, task: str) -> str:
        try:
            if agent_name not in self._registry:
                return f"Error: Agent '{agent_name}' not found. Create it first with create_agent."

            brain_contents = self._memory.read_brain(agent_name)
            brain_context = f"\n\n--- PAST LEARNINGS (YOUR BRAIN) ---\n{brain_contents}\n-----------------------------------\n\n"

            system_prompt = self._registry[agent_name]
            full_prompt = f"System Instructions:\n{system_prompt}\n\n{brain_context}{task}"

            agent = CodeAgent(
                model=self._model,
                tools=self._shared_tools,
                add_base_tools=False
            )

            with redirect_stdout(sys.stderr):
                response = agent.run(full_prompt, max_steps=10)

            self._memory.flush_to_disk()
            return str(response)
        except Exception as e:
            return f"Error delegating to '{agent_name}': {e}\n\nTraceback:\n{traceback.format_exc()}"


class ShutdownAgentTool(Tool):
    name = "shutdown_agent"
    description = "Shut down a subagent, removing it from the registry and permanently deleting its workspace, brain, and scratch files."
    inputs = {
        "agent_name": {"type": "string", "description": "Name of the agent to shut down."},
    }
    output_type = "string"

    def __init__(self, agents_registry, memory, **kwargs):
        super().__init__(**kwargs)
        self._registry = agents_registry
        self._memory = memory

    def forward(self, agent_name: str) -> str:
        try:
            if agent_name not in self._registry:
                return f"Agent '{agent_name}' not found."

            del self._registry[agent_name]
            self._memory.delete_agent_workspace(agent_name)
            return f"Successfully shut down and deleted agent '{agent_name}' and its workspace."
        except Exception as e:
            return f"Error shutting down '{agent_name}': {e}\n\nTraceback:\n{traceback.format_exc()}"
