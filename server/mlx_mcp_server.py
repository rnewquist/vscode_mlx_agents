import os
import sys
import json
import logging
import traceback
import time
import threading
import gc
import io
import pickle
import uuid

# ── Stdout protection ──
# MCP uses stdio (stdout) for JSON-RPC. Any non-JSON output on stdout from
# rich, smolagents, or model libraries will corrupt the transport.
# We create a guarded stdout that ONLY allows writes from the MCP thread.
_real_stdout = sys.stdout
_real_stderr = sys.stderr

class _MCPGuardedStdout:
    """Stdout wrapper that redirects all writes to stderr unless
    the current thread is the designated MCP I/O thread."""
    def __init__(self, real_stdout, fallback):
        self._real = real_stdout
        self._fallback = fallback
        self._mcp_thread_id = None  # set once MCP starts

    def register_mcp_thread(self):
        self._mcp_thread_id = threading.current_thread().ident

    def write(self, data):
        if self._mcp_thread_id and threading.current_thread().ident == self._mcp_thread_id:
            return self._real.write(data)
        # Dynamically write to sys.stderr so it routes through StderrTee
        return sys.stderr.write(data)

    def flush(self):
        self._real.flush()
        self._fallback.flush()

    def fileno(self):
        return self._real.fileno()

    # Forward any other attribute access to the real stdout
    def __getattr__(self, name):
        return getattr(self._real, name)

class LogCapturingStream:
    """A thread-safe string stream that emulates terminal carriage returns (\r)
    in-place to prevent duplicate log bloat in UI stream logs."""
    def __init__(self, fallback_stream=None):
        self.lines = [""]
        self.fallback_stream = fallback_stream
        self._lock = threading.Lock()

    def write(self, s):
        if self.fallback_stream:
            self.fallback_stream.write(s)
            self.fallback_stream.flush()
        
        with self._lock:
            for char in s:
                if char == '\r':
                    self.lines[-1] = ""
                elif char == '\n':
                    self.lines.append("")
                else:
                    self.lines[-1] += char

    def flush(self):
        if self.fallback_stream:
            self.fallback_stream.flush()

    def getvalue(self):
        with self._lock:
            return "\n".join(self.lines)

class StderrTee:
    """A thread-local stderr multiplexer that writes to both the real stderr
    and a stack of registered callbacks (if set) for the current thread."""
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        self.thread_local = threading.local()

    def set_callback(self, callback):
        if not hasattr(self.thread_local, 'callbacks'):
            self.thread_local.callbacks = []
        self.thread_local.callbacks.append(callback)

    def clear_callback(self):
        if hasattr(self.thread_local, 'callbacks') and self.thread_local.callbacks:
            self.thread_local.callbacks.pop()

    def write(self, data):
        self.original_stderr.write(data)
        if hasattr(self.thread_local, 'callbacks') and self.thread_local.callbacks:
            callback = self.thread_local.callbacks[-1]
            if callback:
                try:
                    callback(data)
                except Exception:
                    pass

    def flush(self):
        self.original_stderr.flush()

    def fileno(self):
        return self.original_stderr.fileno()

    def isatty(self):
        return self.original_stderr.isatty()

    def __getattr__(self, name):
        return getattr(self.original_stderr, name)

_guarded_stdout = _MCPGuardedStdout(_real_stdout, _real_stderr)
sys.stdout = _guarded_stdout

_stderr_tee = StderrTee(_real_stderr)
sys.stderr = _stderr_tee

# Disable rich banners / color that corrupt the stdio JSON-RPC stream
os.environ["NO_COLOR"] = "1"
os.environ["TERM"] = "dumb"

import fastmcp
from smolagents import DuckDuckGoSearchTool
from smolagents.models import ChatMessage, MessageRole, TokenUsage, remove_content_after_stop_sequences
from smolagents import MLXModel as SmolMLXModel

_thread_context = threading.local()

class MLXModel(SmolMLXModel):
    """Subclass of MLXModel that supports real-time cancellation during token generation."""
    def generate(self, messages, stop_sequences=None, response_format=None, tools_to_call_from=None, **kwargs):
        if response_format is not None:
            raise ValueError("MLX does not support structured outputs.")
        completion_kwargs = self._prepare_completion_kwargs(
            messages=messages,
            stop_sequences=stop_sequences,
            tools_to_call_from=tools_to_call_from,
            **kwargs,
        )
        messages = completion_kwargs.pop("messages")
        stops = completion_kwargs.pop("stop", [])
        tools = completion_kwargs.pop("tools", None)
        completion_kwargs.pop("tool_choice", None)

        prompt_ids = self.tokenizer.apply_chat_template(messages, tools=None, **self.apply_chat_template_kwargs)

        output_tokens = 0
        text = ""
        for response in self.stream_generate(self.model, self.tokenizer, prompt=prompt_ids, **completion_kwargs):
            # Check for real-time interruption!
            active_agent = getattr(_thread_context, "active_agent", None)
            if active_agent and getattr(active_agent, "interrupt_switch", False):
                _real_stderr.write("MLXModel: Generation interrupted in-loop by user request!\n")
                raise RuntimeError("Generation interrupted by user request.")

            output_tokens += 1
            text += response.text
            if any((stop_index := text.rfind(stop)) != -1 for stop in stops):
                text = text[:stop_index]
                break
        if stop_sequences is not None and not self.supports_stop_parameter:
            text = remove_content_after_stop_sequences(text, stop_sequences)
        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content=text,
            raw={"out": text, "completion_kwargs": completion_kwargs},
            token_usage=TokenUsage(
                input_tokens=len(prompt_ids),
                output_tokens=output_tokens,
            ),
        )

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

# ── Chat template fallbacks for models that don't ship with one ──

_CHATML_TEMPLATE = (
    "{% for message in messages %}"
    "{{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}"
    "{% endfor %}"
    "{% if add_generation_prompt %}"
    "{{'<|im_start|>assistant\n'}}"
    "{% endif %}"
)

_GEMMA_TEMPLATE = (
    "{% for message in messages %}"
    "{% if message['role'] == 'assistant' %}"
    "{{'<start_of_turn>model\n' + message['content'] + '<end_of_turn>\n'}}"
    "{% elif message['role'] == 'system' %}"
    "{{'<start_of_turn>user\n' + message['content'] + '<end_of_turn>\n'}}"
    "{% else %}"
    "{{'<start_of_turn>' + message['role'] + '\n' + message['content'] + '<end_of_turn>\n'}}"
    "{% endif %}"
    "{% endfor %}"
    "{% if add_generation_prompt %}"
    "{{'<start_of_turn>model\n'}}"
    "{% endif %}"
)

_LLAMA_TEMPLATE = (
    "{% for message in messages %}"
    "{% if message['role'] == 'system' %}"
    "{{'<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n' + message['content'] + '<|eot_id|>'}}"
    "{% elif message['role'] == 'user' %}"
    "{{'<|start_header_id|>user<|end_header_id|>\n\n' + message['content'] + '<|eot_id|>'}}"
    "{% else %}"
    "{{'<|start_header_id|>assistant<|end_header_id|>\n\n' + message['content'] + '<|eot_id|>'}}"
    "{% endif %}"
    "{% endfor %}"
    "{% if add_generation_prompt %}"
    "{{'<|start_header_id|>assistant<|end_header_id|>\n\n'}}"
    "{% endif %}"
)

def _pick_chat_template(model_id: str) -> tuple[str, str]:
    """Return (template_string, family_name) based on model ID heuristics."""
    mid = model_id.lower()
    if "gemma" in mid:
        return _GEMMA_TEMPLATE, "Gemma"
    if "llama" in mid:
        return _LLAMA_TEMPLATE, "Llama"
    return _CHATML_TEMPLATE, "ChatML"

def _get_model_family(model_id: str) -> str:
    mid = model_id.lower()
    if "gemma" in mid:
        return "gemma"
    if "llama" in mid:
        return "llama"
    if "qwen" in mid:
        return "qwen"
    return "unknown"

def _is_instruct_model(model_id: str) -> bool:
    """Check if model ID suggests an instruction-tuned variant."""
    mid = model_id.lower()
    instruct_markers = ["-it-", "-it.", "-instruct", "-chat", "instruct-"]
    return any(m in mid for m in instruct_markers)

def get_mlx_model(log_fn=None):
    """Load (or return cached) MLX model. log_fn(msg) is called with progress strings."""
    global _mlx_model_instance, _current_model_id

    def _log(msg):
        _real_stderr.write(msg + "\n")
        if log_fn:
            log_fn(msg + "\n")

    if _mlx_model_instance is None:
        if log_fn:
            sys.stderr.set_callback(log_fn)
        try:
            status = get_system_status_info()
            _log(f"Loading MLX model: {_current_model_id}  (RAM: {status['ram_usage_mb']}MB)")

            family = _get_model_family(_current_model_id)

            # Warn about base (non-instruct) models
            if not _is_instruct_model(_current_model_id):
                _log("⚠ WARNING: This appears to be a base model (not instruction-tuned).")
                _log("  Base models may produce incoherent or runaway output.")
                _log("  Recommended: use an '-it-' or '-Instruct' variant instead.")

            load_kwargs = {}
            models_config = memory.get_models_config()

            # Check if we have a custom adapter path for this model
            if _current_model_id in models_config:
                adapter_path = models_config[_current_model_id].get("adapter_path")
                if adapter_path and os.path.exists(adapter_path):
                    _log(f"Loading LoRA adapter from {adapter_path}...")
                    load_kwargs["adapter_path"] = adapter_path
            elif "Qwen" in _current_model_id:
                fallback_adapter_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qwen_lora", "adapters_hf")
                if os.path.exists(fallback_adapter_path):
                    _log(f"Loading fallback LoRA adapter from {fallback_adapter_path}...")
                    load_kwargs["adapter_path"] = fallback_adapter_path

            _log("Downloading/loading model weights into unified memory...")

            # Build model-family-specific kwargs
            chat_template_kwargs = {"add_generation_prompt": True}

            # Load the MLX model natively into unified memory.
            _mlx_model_instance = MLXModel(
                _current_model_id,
                load_kwargs=load_kwargs,
                apply_chat_template_kwargs=chat_template_kwargs,
                max_tokens=4096
            )

            # Fix models that ship without a chat_template
            try:
                tokenizer = _mlx_model_instance.tokenizer
                if not getattr(tokenizer, "chat_template", None):
                    template, tpl_name = _pick_chat_template(_current_model_id)
                    _log(f"⚠ Tokenizer has no chat_template — applying {tpl_name} template.")
                    tokenizer.chat_template = template
            except Exception as e:
                _log(f"Warning: could not inspect tokenizer chat_template: {e}")

            # Ensure proper EOS tokens for the model family
            try:
                tokenizer = _mlx_model_instance.tokenizer
                if family == "gemma":
                    # Gemma uses <end_of_turn> as its stop token
                    eos_token = "<end_of_turn>"
                    eos_id = tokenizer.convert_tokens_to_ids(eos_token)
                    if eos_id and eos_id != tokenizer.unk_token_id:
                        tokenizer.eos_token = eos_token
                        tokenizer.eos_token_id = eos_id
                        _log(f"Set EOS token to {eos_token} (id={eos_id})")
            except Exception as e:
                _log(f"Warning: could not set model-specific EOS token: {e}")

            status = get_system_status_info()
            _log(f"Model object created. RAM usage: {status['ram_usage_mb']}MB")

            # Force a tiny generation to ensure weights are actually mapped into RAM
            try:
                _log("Running warmup generation...")
                _mlx_model_instance([{"role": "user", "content": [{"type": "text", "text": "Hi"}]}], max_tokens=1)
                status = get_system_status_info()
                _log(f"✓ Warmup complete. Final RAM: {status['ram_usage_mb']}MB")
            except Exception as e:
                _log(f"⚠ Warmup failed (model might still work): {e}")
        finally:
            if log_fn:
                sys.stderr.clear_callback()

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
MAIN_AGENT_SYSTEM_PROMPT = """You are MLX, a local AI assistant running natively on Apple Silicon.
Be concise and helpful. You have access to tools for file editing, web search, terminal commands,
and multi-agent delegation. Use update_my_brain to remember important facts across sessions.
When the user asks a simple question, answer directly using final_answer.
For complex tasks, break them into steps and use your tools."""


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
    # Use ToolCallingAgent instead of CodeAgent — it works reliably across model
    # families (Gemma, Llama, Qwen) without requiring models to produce exact
    # <code>...</code> block formatting that many local models get wrong.
    from smolagents import ToolCallingAgent

    main_brain = get_main_brain_tool(memory, workspace_path)
    all_tools = get_shared_tools(workspace_path=workspace_path) + get_management_tools(agents_registry, memory, workspace_path=workspace_path) + [main_brain]

    agent = ToolCallingAgent(
        model=get_mlx_model(),
        tools=all_tools,
    )
    
    # Try to load memory from disk
    if session_file and os.path.exists(session_file):
        try:
            with open(session_file, "rb") as f:
                saved_memory = pickle.load(f)
                agent.memory = saved_memory
                _real_stderr.write(f"Successfully restored session memory from {session_file}\n")
        except Exception as e:
            _real_stderr.write(f"Failed to load session memory (likely corrupted): {e}\n")
            # If pickle is corrupted, we already have a fresh agent.memory from CodeAgent init
            try:
                os.remove(session_file)
                _real_stderr.write("Deleted corrupted session memory file.\n")
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
        log_capture = LogCapturingStream()
        
        def _run_worker():
            telemetry_manager.update_node_status("root", "thinking")
            sys.stderr.set_callback(log_capture.write)
            agent = None
            try:
                log_capture.write("Initializing MLX model...\n")
                sys.stderr.write(f"Thread-{run_id}: Requesting MLX model...\n")
                
                # Pre-load model with progress piped to the webview
                get_mlx_model(log_fn=log_capture.write)
                
                log_capture.write("Creating agent session...\n")
                agent = _get_workspace_agent(workspace_path, brain_context, clear_history=False)
                
                # Store active agent in thread context for dynamic interruption
                _thread_context.active_agent = agent
                
                with self.lock:
                    self.runs[run_id]['agent'] = agent

                log_capture.write("Starting generation...\n")
                sys.stderr.write(f"Thread-{run_id}: Starting agent.run()...\n")
                response = agent.run(prompt, max_steps=30, reset=False)                
                with self.lock:
                    self.runs[run_id]['status'] = "completed"
                    self.runs[run_id]['response'] = response
            except Exception as e:
                is_interrupted = False
                if agent and getattr(agent, "interrupt_switch", False):
                    is_interrupted = True
                
                if is_interrupted:
                    sys.stderr.write(f"Thread-{run_id}: Run interrupted by user.\n")
                    with self.lock:
                        self.runs[run_id]['status'] = "completed"
                        self.runs[run_id]['response'] = "Generation interrupted by user."
                else:
                    sys.stderr.write(f"Thread-{run_id} Error: {e}\n")
                    traceback.print_exc(file=sys.stderr)
                    with self.lock:
                        self.runs[run_id]['status'] = "error"
                        self.runs[run_id]['response'] = f"Error: {e}\n\nTraceback:\n{traceback.format_exc()}"
            finally:
                # Clear thread context and stderr callback
                if hasattr(_thread_context, "active_agent"):
                    del _thread_context.active_agent
                sys.stderr.clear_callback()
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
        from smolagents import ToolCallingAgent
        agent = ToolCallingAgent(
            model=get_mlx_model(),
            tools=get_shared_tools(workspace_path=None),
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
        # Register this thread as the sole MCP I/O thread
        # Only this thread's writes will reach the real stdout
        _guarded_stdout.register_mcp_thread()

        # Force rich's default console to stderr (belt + suspenders)
        try:
            import rich.console
            rich.console.Console._default_file = _real_stderr
        except Exception:
            pass
        try:
            from rich.console import Console
            # Monkey-patch the default console used by smolagents/rich
            import rich
            rich.get_console = lambda: Console(file=_real_stderr, force_terminal=False)
        except Exception:
            pass

        # FastMCP handles the stdio transport layer automatically
        mcp.run(transport='stdio', show_banner=False)
    except Exception as e:
        _real_stderr.write(f"MCP Server crashed: {e}\n")
        traceback.print_exc(file=_real_stderr)
    finally:
        # Clean up PID file if we are the ones who wrote it
        try:
            with open(pid_file, "r") as f:
                if f.read().strip() == str(my_pid):
                    os.remove(pid_file)
        except Exception:
            pass