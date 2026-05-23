import os
import sys
import logging
import traceback
import time
import threading
import gc
import io
import pickle
import uuid

# Immediately redirect stdout to stderr to prevent rogue prints (from imports or global code) 
# from corrupting the MCP JSON-RPC stream on stdout.
_real_stdout = sys.stdout
sys.stdout = sys.stderr

# Disable rich banners that corrupt the stdio JSON-RPC stream
os.environ["NO_COLOR"] = "1"
os.environ["TERM"] = "dumb"

import fastmcp
from smolagents import CodeAgent, MLXModel, DuckDuckGoSearchTool
try:
    import mlx.core as mx
except ImportError:
    mx = None

# ============================================================
# Initialize the FastMCP server
# ============================================================
mcp = fastmcp.FastMCP("mlx-local-router")

from tool.memory_manager import memory
import tool.diff_manager as diff_manager
import tool.artifact_manager as artifact_manager
import tool.telemetry_manager as telemetry_manager

# Registry to hold all our agents' system prompts (configurations)
agents_registry = {
    "default": "You are a helpful assistant."
}

_mlx_model_instance = None
_current_model_id = "mlx-community/Qwen3.6-35B-A3B-4bit"
_model_lock = threading.Lock()
_last_query_time = time.time()
_active_queries = 0
_IDLE_TIMEOUT_SECONDS = 300 # 5 minutes

_workspace_agents = {}

def _watchdog_loop():
    global _mlx_model_instance, _last_query_time
    while True:
        time.sleep(10)
        with _model_lock:
            if _active_queries == 0 and _mlx_model_instance is not None:
                if time.time() - _last_query_time > _IDLE_TIMEOUT_SECONDS:
                    sys.stderr.write("Model has been idle for 5 minutes. Unloading from unified memory to free up RAM...\n")
                    del _mlx_model_instance
                    _mlx_model_instance = None
                    
                    # Unload model from all cached agents
                    for agent in _workspace_agents.values():
                        agent.model = None
                        
                    gc.collect()
                    if mx:
                        try:
                            mx.clear_cache()
                        except AttributeError:
                            pass

watchdog_thread = threading.Thread(target=_watchdog_loop, daemon=True)
watchdog_thread.start()

def get_system_status_info():
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / 1024 / 1024
    except Exception:
        mem_mb = 0
    
    status = {
        "pid": os.getpid(),
        "ram_usage_mb": round(mem_mb, 2),
        "current_model_id": _current_model_id,
        "model_loaded": _mlx_model_instance is not None,
        "active_queries": _active_queries
    }
    return status

@mcp.tool()
def get_system_status() -> str:
    """Returns the current server status, including RAM usage and model info."""
    import json
    return json.dumps(get_system_status_info())

def get_mlx_model():
    global _mlx_model_instance, _current_model_id
    if _mlx_model_instance is None:
        status = get_system_status_info()
        sys.stderr.write(f"Server: Loading MLX model ({_current_model_id}). Current RAM: {status['ram_usage_mb']}MB\n")
        import os
        
        load_kwargs = {}
        models_config = memory.get_models_config()
        
        # Check if we have a custom adapter path for this model
        if _current_model_id in models_config:
            adapter_path = models_config[_current_model_id].get("adapter_path")
            if adapter_path and os.path.exists(adapter_path):
                sys.stderr.write(f"Loading LoRA adapter from {adapter_path}...\n")
                load_kwargs["adapter_path"] = adapter_path
        elif "Qwen" in _current_model_id:
            # Fallback to hardcoded path for Qwen if no config exists (backward compatibility)
            fallback_adapter_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qwen_lora", "adapters_hf")
            if os.path.exists(fallback_adapter_path):
                sys.stderr.write(f"Loading fallback LoRA adapter from {fallback_adapter_path}...\n")
                load_kwargs["adapter_path"] = fallback_adapter_path
            
        # Load the MLX model natively into your M5's unified memory.
        _mlx_model_instance = MLXModel(
            _current_model_id,
            load_kwargs=load_kwargs,
            max_tokens=4096
        )
        
        status = get_system_status_info()
        sys.stderr.write(f"MLXModel object created. RAM usage: {status['ram_usage_mb']}MB\n")
        
        # Force a tiny generation to ensure weights are actually mapped into RAM
        try:
            sys.stderr.write("Performing model warmup generation...\n")
            _mlx_model_instance([{"role": "user", "content": "Hi"}], max_new_tokens=1)
            status = get_system_status_info()
            sys.stderr.write(f"Warmup complete. Final RAM usage: {status['ram_usage_mb']}MB\n")
        except Exception as e:
            sys.stderr.write(f"Warmup failed (but model might still work): {e}\n")

    return _mlx_model_instance

@mcp.tool()
def get_models() -> str:
    """Returns the persistent configuration of models and their adapters."""
    import json
    config = memory.get_models_config()
    sys.stderr.write(f"Server: get_models returning: {config}\n")
    return json.dumps(config)

@mcp.tool()
def add_model(model_id: str, adapter_path: str = "") -> str:
    """Adds a model to the persistent configuration. Returns the updated config JSON."""
    sys.stderr.write(f"Server: add_model called with model_id={model_id}, adapter_path={adapter_path}\n")
    config = memory.get_models_config()
    config[model_id] = {"adapter_path": adapter_path}
    memory.save_models_config(config)
    return json.dumps(config)

@mcp.tool()
def remove_model(model_id: str) -> str:
    """Removes a model from the persistent configuration. Returns the updated config JSON."""
    sys.stderr.write(f"Server: remove_model called for {model_id}\n")
    config = memory.get_models_config()
    if model_id in config:
        del config[model_id]
        memory.save_models_config(config)
    return json.dumps(config)

@mcp.tool()
def update_model(model_id: str, adapter_path: str = "") -> str:
    """Updates the adapter path for an existing model configuration. Returns the updated config JSON."""
    sys.stderr.write(f"Server: update_model called for {model_id} with adapter_path={adapter_path}\n")
    config = memory.get_models_config()
    if model_id in config:
        config[model_id]["adapter_path"] = adapter_path
        memory.save_models_config(config)
    else:
        config[model_id] = {"adapter_path": adapter_path}
        memory.save_models_config(config)
    return json.dumps(config)

@mcp.tool()
def get_pending_diffs() -> str:
    """Returns a JSON string of all pending diff requests."""
    import json
    return json.dumps(diff_manager.get_all_pending())

@mcp.tool()
def resolve_diff(diff_id: str, accept: bool, feedback: str = "") -> str:
    """Resolves a pending diff request."""
    success = diff_manager.resolve(diff_id, accept, feedback)
    return "Resolved" if success else "Diff ID not found or already resolved."

@mcp.tool()
def get_artifacts() -> str:
    import json
    return json.dumps(artifact_manager.get_artifacts())

@mcp.tool()
def get_telemetry_tree() -> str:
    import json
    return json.dumps(telemetry_manager.get_tree())

def get_shared_tools(workspace_path=None):
    from tool.edit_file import EditFileTool
    from tool.write_file import WriteFileTool
    from tool.run_command import RunCommandTool
    from tool.shared_memory import AppendSharedMemoryTool, ReadSharedMemoryTool
    from tool.send_message import SendMessageTool
    from tool.update_brain import UpdateBrainTool
    from tool.view_file import ViewFileTool
    from tool.list_dir import ListDirTool
    from tool.grep_search import GrepSearchTool
    from tool.read_url_content import ReadUrlContentTool
    from tool.command_status import CommandStatusTool
    from tool.send_command_input import SendCommandInputTool

    return [
        EditFileTool(workspace_path=workspace_path),
        WriteFileTool(workspace_path=workspace_path),
        RunCommandTool(workspace_path=workspace_path),
        AppendSharedMemoryTool(),
        ReadSharedMemoryTool(),
        SendMessageTool(),
        UpdateBrainTool(),
        ViewFileTool(workspace_path=workspace_path),
        ListDirTool(workspace_path=workspace_path),
        GrepSearchTool(workspace_path=workspace_path),
        DuckDuckGoSearchTool(),
        ReadUrlContentTool(),
        CommandStatusTool(),
        SendCommandInputTool()
    ]

def get_management_tools(agents_registry, memory, workspace_path=None):
    from tool.agent_tools import CreateAgentTool, ListAgentsTool, DelegateToAgentTool, ShutdownAgentTool
    return [
        CreateAgentTool(agents_registry=agents_registry, memory=memory),
        ListAgentsTool(agents_registry=agents_registry),
        DelegateToAgentTool(
            agents_registry=agents_registry,
            memory=memory,
            mlx_model=get_mlx_model(),
            shared_tools=get_shared_tools(workspace_path=workspace_path)
        ),
        ShutdownAgentTool(agents_registry=agents_registry, memory=memory),
    ]

def get_main_brain_tool(memory, workspace_path=""):
    from tool.main_brain_tool import UpdateMainBrainTool
    tool = UpdateMainBrainTool(memory=memory)
    if workspace_path:
        tool._workspace_path = workspace_path
    return tool

# Main Agent system prompt
MAIN_AGENT_SYSTEM_PROMPT = """You are MLX, a local AI assistant running on Apple Silicon. Be concise and helpful.
You can use tools to edit files, search the web, run commands, and manage subagents.
Use update_my_brain to remember important facts across sessions."""


def _get_workspace_agent(workspace_path: str, brain_context: str, clear_history: bool):
    global _workspace_agents
    
    session_file = os.path.join(workspace_path, ".gemini", "chat_session.pkl") if workspace_path else None
    
    if clear_history:
        if workspace_path in _workspace_agents:
            del _workspace_agents[workspace_path]
        if session_file and os.path.exists(session_file):
            try:
                os.remove(session_file)
            except OSError:
                pass
                
    # If the workspace agent exists but its model was unloaded, reload it
    if workspace_path in _workspace_agents:
        agent = _workspace_agents[workspace_path]
        if agent.model is None:
            agent.model = get_mlx_model()
        # Update system prompt in case brain changed
        agent.memory.system_prompt.system_prompt = f"{MAIN_AGENT_SYSTEM_PROMPT}\n\n{brain_context}"
        return agent

    # Initialize a new agent
    main_brain = get_main_brain_tool(memory, workspace_path)
    all_tools = get_shared_tools(workspace_path=workspace_path) + get_management_tools(agents_registry, memory, workspace_path=workspace_path) + [main_brain]

    agent = CodeAgent(
        model=get_mlx_model(),
        tools=all_tools,
        add_base_tools=False,
    )
    
    # Try to load memory from disk
    if session_file and os.path.exists(session_file):
        try:
            with open(session_file, "rb") as f:
                saved_memory = pickle.load(f)
                agent.memory = saved_memory
                sys.stderr.write(f"Successfully restored session memory from {session_file}\n")
        except Exception as e:
            sys.stderr.write(f"Failed to load session memory (likely corrupted): {e}\n")
            # If pickle is corrupted, we already have a fresh agent.memory from CodeAgent init
            try:
                os.remove(session_file)
                sys.stderr.write("Deleted corrupted session memory file.\n")
            except OSError:
                pass
            
    # Set the system prompt
    agent.memory.system_prompt.system_prompt = f"{MAIN_AGENT_SYSTEM_PROMPT}\n\n{brain_context}"
    
    _workspace_agents[workspace_path] = agent
    return agent


class AgentRunManager:
    def __init__(self):
        self.runs = {}
        self.lock = threading.Lock()

    def start_run(self, workspace_path: str, brain_context: str, prompt: str) -> str:
        run_id = str(uuid.uuid4())
        log_capture = io.StringIO()
        
        def _run_worker():
            telemetry_manager.update_node_status("root", "thinking")
            try:
                log_capture.write("Checking model availability and initializing MLX...\n")
                sys.stderr.write(f"Thread-{run_id}: Requesting MLX model...\n")
                
                agent = _get_workspace_agent(workspace_path, brain_context, clear_history=False)
                
                with self.lock:
                    self.runs[run_id]['agent'] = agent

                log_capture.write(f"MLX Model loaded. Starting generation...\n")
                sys.stderr.write(f"Thread-{run_id}: Starting agent.run()...\n")
                response = agent.run(prompt, max_steps=30, reset=False)                
                with self.lock:
                    self.runs[run_id]['status'] = "completed"
                    self.runs[run_id]['response'] = response
            except Exception as e:
                sys.stderr.write(f"Thread-{run_id} Error: {e}\n")
                traceback.print_exc(file=sys.stderr)
                with self.lock:
                    self.runs[run_id]['status'] = "error"
                    self.runs[run_id]['response'] = f"Error: {e}\n\nTraceback:\n{traceback.format_exc()}"
            finally:
                memory.flush_to_disk()
                telemetry_manager.update_node_status("root", "idle")
                
        thread = threading.Thread(target=_run_worker, daemon=True)
        
        with self.lock:
            self.runs[run_id] = {
                'thread': thread,
                'agent': None,
                'status': "running",
                'log_capture': log_capture,
                'response': None
            }
            
        thread.start()
        return run_id

    def poll_run(self, run_id: str) -> dict:
        with self.lock:
            if run_id not in self.runs:
                return {"status": "not_found"}
            
            run_data = self.runs[run_id]
            return {
                "status": run_data['status'],
                "logs": run_data['log_capture'].getvalue(),
                "response": run_data['response']
            }

    def interrupt_run(self, run_id: str):
        with self.lock:
            if run_id in self.runs and self.runs[run_id]['status'] == "running":
                agent = self.runs[run_id]['agent']
                # Try to forcefully interrupt smolagents (may take until next step)
                if agent and hasattr(agent, "interrupt"):
                    agent.interrupt()
                return "Interrupt signal sent."
        return "Run not found or already finished."

run_manager = AgentRunManager()

@mcp.tool()
def start_query(prompt: str, workspace_path: str = "", clear_history: bool = False) -> str:
    """Starts a non-blocking background run and returns a run_id."""
    global _active_queries, _last_query_time
    
    if clear_history:
        _get_workspace_agent(workspace_path, "", clear_history=True)
        return "cleared"
        
    try:
        brain_contents = memory.read_main_brain(workspace_path) if workspace_path else ""
        brain_context = f"\n\nYour memories:\n{brain_contents}\n\n" if brain_contents else ""

        with _model_lock:
            _active_queries += 1
            _last_query_time = time.time()

        return run_manager.start_run(workspace_path, brain_context, prompt)
    except Exception as e:
        return f"Error starting run: {e}"

@mcp.tool()
def poll_query(run_id: str) -> str:
    import json
    return json.dumps(run_manager.poll_run(run_id))

@mcp.tool()
def interrupt_query(run_id: str) -> str:
    return run_manager.interrupt_run(run_id)


@mcp.tool()
def change_model(model_id: str) -> str:
    """
    Changes the underlying MLX model used by the agents.
    Does not load the model immediately; loading happens on the first query.
    
    Args:
        model_id: The Hugging Face repo ID or local path of the model.
    """
    global _mlx_model_instance, _current_model_id
    with _model_lock:
        if _active_queries > 0:
            return "Cannot change model while queries are active."
        
        try:
            sys.stderr.write(f"Server: Switching model ID to {model_id}. Unloading previous instance...\n")
            _current_model_id = model_id
            if _mlx_model_instance is not None:
                del _mlx_model_instance
                _mlx_model_instance = None
                
            for agent in _workspace_agents.values():
                agent.model = None
                
            gc.collect()
            if mx:
                try:
                    mx.clear_cache()
                except AttributeError:
                    pass
                
            return f"Model changed to {model_id}. It will be loaded into unified memory upon the next query."
        except Exception as e:
            return f"Failed to switch model ID to {model_id}: {e}\n\nTraceback:\n{traceback.format_exc()}"

@mcp.tool()
def create_agent(agent_name: str, system_prompt: str) -> str:
    """
    Creates a new custom subagent on demand with a specific personality and tools.

    Args:
        agent_name: The unique identifier/name for the new agent.
        system_prompt: The specific instructions or personality for the agent.
    """
    if agent_name in agents_registry:
        return f"Agent '{agent_name}' already exists."

    # Setup isolated folder structure
    scratch_dir = memory.setup_agent_workspace(agent_name)

    # Inject identity into the system prompt
    identity_prompt = f"\n\nIMPORTANT: Your agent name is '{agent_name}'. You share RAM memory with other agents via 'append_shared_memory' and 'read_shared_memory'. You can update your permanent knowledge by calling 'update_brain' using your name. Your personal scratch space for temporary files, notes, and scratchpads is located at: '{scratch_dir}'."
    full_system_prompt = system_prompt + identity_prompt

    try:
        agents_registry[agent_name] = full_system_prompt
        return f"Successfully created agent '{agent_name}'."
    except Exception as e:
        return f"Failed to create agent '{agent_name}': {e}\n\nTraceback:\n{traceback.format_exc()}"

@mcp.tool()
def list_agents() -> str:
    """
    Lists all available subagents in the system.
    """
    return "Available agents: " + ", ".join(agents_registry.keys())

@mcp.tool()
def shutdown_agent(agent_name: str) -> str:
    """
    Shuts down an agent, removing it from the registry and permanently deleting its workspace, brain, and scratch files.

    Args:
        agent_name: The name of the agent to shut down.
    """
    if agent_name not in agents_registry:
        return f"Agent '{agent_name}' not found."

    del agents_registry[agent_name]
    memory.delete_agent_workspace(agent_name)
    return f"Successfully shut down and deleted agent '{agent_name}' and its workspace."

@mcp.tool()
def reset_system() -> str:
    """
    Clears all shared memory, removes all active subagents, deletes all persistent brains, and stops background processes.
    Returns the system to a clean, factory-reset state.
    NOTE: The Main Agent's workspace-scoped brain is NOT cleared — it is owned by the workspace, not the server.
    """
    agents_registry.clear()
    agents_registry["default"] = "You are a helpful assistant."
    memory.clear_all()
    return "System reset complete. All memory, agents, background processes, and brains have been permanently cleared. Main Agent brain is preserved."

@mcp.tool()
def agent_query(prompt: str, agent_name: str = "default", max_tokens: int = 1024) -> str:
    """
    Offload a specific task to a subagent.
    Use this to route packaged requests to specific custom agents.

    Args:
        prompt: The task or query to run.
        agent_name: The name of the agent to route to (default: "default").
        max_tokens: Maximum tokens for the response.
    """
    if agent_name not in agents_registry:
        return f"Error: Agent '{agent_name}' not found. Please create it first using the create_agent tool."

    # Read the agent's brain and inject it into the task context
    brain_contents = memory.read_brain(agent_name)
    brain_context = f"\n\n--- PAST LEARNINGS (YOUR BRAIN) ---\n{brain_contents}\n-----------------------------------\n\n"
    # Instantiate the agent dynamically so it lives only for the duration of this task
    system_prompt = agents_registry[agent_name]
    full_prompt = f"System Instructions:\n{system_prompt}\n\n" + brain_context + prompt

    global _active_queries, _last_query_time
    with _model_lock:
        _active_queries += 1
        _last_query_time = time.time()

    try:
        from smolagents import CodeAgent
        agent = CodeAgent(
            model=get_mlx_model(),
            # For subagent queries, we don't have a specific workspace_path context easily available,
            # but we can try to infer it or just pass None to be safe.
            # Actually, we should probably pass the same workspace context as the main agent.
            # For now, let's keep it restricted by default.
            tools=get_shared_tools(workspace_path=None), 
            add_base_tools=True
        )

        log_capture = io.StringIO()
        with redirect_stdout(log_capture):
            response = agent.run(full_prompt)

        # Flush RAM to disk safely after the task completes
        memory.flush_to_disk()

        logs = log_capture.getvalue().strip()
        if logs:
            return f"### Agent '{agent_name}' Internal Monologue & Actions:\n```text\n{logs}\n```\n\n### Subagent Response:\n{response}"
        return str(response)
    finally:
        with _model_lock:
            _active_queries -= 1
            _last_query_time = time.time()

if __name__ == "__main__":
    import signal
    import time
    
    # Configure logging to go to stderr so it doesn't interfere with stdout (MCP protocol)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stderr
    )
    # Silence third-party loggers that might talk on stdout
    logging.getLogger("fastmcp").setLevel(logging.WARNING)
    
    # Enforce a singleton instance to prevent multiple 18GB MLX models from running
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pid_file = os.path.join(base_dir, ".gemini", "mlx_mcp_server.pid")
    
    my_pid = os.getpid()
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                content = f.read().strip()
                if content:
                    old_pid = int(content)
                    if old_pid != my_pid:
                        try:
                            # Check if the old process is still running
                            os.kill(old_pid, 0)
                            sys.stderr.write(f"Found existing MCP server running with PID {old_pid}. Terminating it to free up RAM...\n")
                            os.kill(old_pid, signal.SIGTERM)
                            # Give it a moment to release unified memory
                            for _ in range(10):
                                time.sleep(0.2)
                                try:
                                    os.kill(old_pid, 0)
                                except OSError:
                                    break
                            else:
                                sys.stderr.write(f"Force killing PID {old_pid}...\n")
                                os.kill(old_pid, signal.SIGKILL)
                        except OSError:
                            # Process doesn't exist
                            pass
        except (ValueError, OSError) as e:
            sys.stderr.write(f"Error checking PID file: {e}\n")
            
    # Write the new PID
    os.makedirs(os.path.dirname(pid_file), exist_ok=True)
    with open(pid_file, "w") as f:
        f.write(str(my_pid))

    try:
        # FastMCP handles the stdio transport layer automatically
        # Restore stdout just before running the server
        sys.stdout = _real_stdout
        mcp.run(transport='stdio', show_banner=False)
    except Exception as e:
        sys.stderr.write(f"MCP Server crashed: {e}\n")
        traceback.print_exc(file=sys.stderr)
    finally:
        # Clean up PID file if we are the ones who wrote it
        try:
            with open(pid_file, "r") as f:
                if f.read().strip() == str(my_pid):
                    os.remove(pid_file)
        except Exception:
            pass