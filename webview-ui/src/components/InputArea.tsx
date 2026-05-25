import { useState, useRef, useEffect } from "react";
import {
  SendIcon,
  StopIcon,
  ActivityIcon,
  FileIcon,
  SlashIcon,
} from "./Icons";

interface InputAreaProps {
  input: string;
  setInput: (val: string) => void;
  selectedModel: string;
  modelsConfig: Record<string, { adapter_path: string }>;
  status: string;
  activeTab: "telemetry" | "artifacts" | null;
  onSend: () => void;
  onInterrupt: () => void;
  onModelChange: (val: string) => void;
  onToggleDrawer: (tab: "telemetry" | "artifacts") => void;
}

const SLASH_COMMANDS = [
  { cmd: "/agents", desc: "List active agents" },
  { cmd: "/create", desc: "Create a new agent" },
  { cmd: "/ask", desc: "Query a specific agent" },
  { cmd: "/shutdown", desc: "Shutdown an agent" },
  { cmd: "/reset", desc: "Reset the system" },
  { cmd: "/clear", desc: "Clear chat history" },
];

export function InputArea({
  input,
  setInput,
  selectedModel,
  modelsConfig,
  status,
  activeTab,
  onSend,
  onInterrupt,
  onModelChange,
  onToggleDrawer,
}: InputAreaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [slashFilter, setSlashFilter] = useState("");
  const [selectedSlashIdx, setSelectedSlashIdx] = useState(0);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }, [input]);

  // Slash command detection
  useEffect(() => {
    if (input.startsWith("/")) {
      const filter = input.slice(1).toLowerCase();
      setSlashFilter(filter);
      setShowSlashMenu(true);
      setSelectedSlashIdx(0);
    } else {
      setShowSlashMenu(false);
    }
  }, [input]);

  const filteredCommands = SLASH_COMMANDS.filter((c) =>
    c.cmd.slice(1).startsWith(slashFilter)
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showSlashMenu && filteredCommands.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedSlashIdx((prev) =>
          Math.min(prev + 1, filteredCommands.length - 1)
        );
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedSlashIdx((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey)) {
        e.preventDefault();
        const selected = filteredCommands[selectedSlashIdx];
        setInput(selected.cmd + " ");
        setShowSlashMenu(false);
        return;
      }
      if (e.key === "Escape") {
        setShowSlashMenu(false);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const isThinking = !!status;
  const canSend = input.trim().length > 0 && !isThinking && !!selectedModel;

  return (
    <footer className="input-area">
      {showSlashMenu && filteredCommands.length > 0 && (
        <div className="slash-menu">
          {filteredCommands.map((c, i) => (
            <button
              key={c.cmd}
              className={`slash-item ${i === selectedSlashIdx ? "selected" : ""}`}
              onMouseDown={(e) => {
                e.preventDefault();
                setInput(c.cmd + " ");
                setShowSlashMenu(false);
                textareaRef.current?.focus();
              }}
            >
              <SlashIcon size={12} />
              <span className="slash-cmd">{c.cmd}</span>
              <span className="slash-desc">{c.desc}</span>
            </button>
          ))}
        </div>
      )}

      <div className={`input-container ${isThinking ? "thinking" : ""}`}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isThinking ? "Agent is thinking…" : "Message MLX…"}
          rows={1}
          disabled={isThinking}
        />
        <div className="input-toolbar">
          <div className="toolbar-left">
            <select
              value={selectedModel}
              onChange={(e) => onModelChange(e.target.value)}
              className="model-select-chip"
            >
              {Object.keys(modelsConfig).length === 0 ? (
                <option value="" disabled>
                  No models
                </option>
              ) : (
                Object.keys(modelsConfig).map((id) => (
                  <option key={id} value={id}>
                    {id.split("/").pop()}
                  </option>
                ))
              )}
              <option disabled>───</option>
              <option value="add_new">+ Add Model…</option>
              {Object.keys(modelsConfig).length > 0 && (
                <option value="manage">Manage…</option>
              )}
            </select>

            <button
              className={`toolbar-btn ${activeTab === "telemetry" ? "active" : ""}`}
              onClick={() => onToggleDrawer("telemetry")}
              title="Agent Telemetry"
            >
              <ActivityIcon size={14} />
            </button>
            <button
              className={`toolbar-btn ${activeTab === "artifacts" ? "active" : ""}`}
              onClick={() => onToggleDrawer("artifacts")}
              title="Artifacts"
            >
              <FileIcon size={14} />
            </button>
          </div>

          <div className="toolbar-right">
            {isThinking ? (
              <button
                className="action-btn stop-btn"
                onClick={onInterrupt}
                title="Interrupt Agent"
              >
                <StopIcon size={14} />
              </button>
            ) : (
              <button
                className="action-btn send-btn"
                disabled={!canSend}
                onClick={onSend}
                title="Send (Enter)"
              >
                <SendIcon size={14} />
              </button>
            )}
          </div>
        </div>
      </div>
      <div className="input-hint">
        <kbd>Enter</kbd> send · <kbd>Shift+Enter</kbd> newline · <kbd>/</kbd>{" "}
        commands
      </div>
    </footer>
  );
}
