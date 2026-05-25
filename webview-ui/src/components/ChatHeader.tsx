import { PlusIcon, TrashIcon } from "./Icons";

interface ChatHeaderProps {
  serverStatus: "disconnected" | "connecting" | "connected";
  onNewSession: () => void;
  onClearLogs: () => void;
}

export function ChatHeader({ serverStatus, onNewSession, onClearLogs }: ChatHeaderProps) {
  const statusLabel = {
    disconnected: "Offline",
    connecting: "Connecting…",
    connected: "Connected",
  }[serverStatus];

  return (
    <header className="chat-header">
      <div className="header-left">
        <div className={`status-dot ${serverStatus}`} title={statusLabel} />
        <span className="header-title">MLX Agent</span>
        {serverStatus === "connecting" && (
          <span className="status-badge connecting">Starting…</span>
        )}
      </div>
      <div className="header-right">
        <button
          className="header-action-btn"
          onClick={onClearLogs}
          title="Clear Logs"
        >
          <TrashIcon size={14} />
        </button>
        <button
          className="header-action-btn"
          onClick={onNewSession}
          title="New Session"
        >
          <PlusIcon size={14} />
        </button>
      </div>
    </header>
  );
}
