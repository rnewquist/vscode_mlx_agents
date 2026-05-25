import { useRef, useEffect } from "react";
import { MessageBubble } from "./MessageBubble";
import { StreamLog } from "./StreamLog";
import { DiffCard } from "./DiffCard";

interface ChatMessage {
  role: string;
  text: string;
  timestamp?: number;
  id?: string;
}

interface DiffRequest {
  id: string;
  file_path: string;
  original_content: string;
  new_content: string;
  tool_name: string;
}

interface MessageListProps {
  messages: ChatMessage[];
  logs: string;
  status: string;
  pendingDiffs: DiffRequest[];
  onRetry: (text: string) => void;
  onViewDiff: (diff: DiffRequest) => void;
  onResolveDiff: (diffId: string, accept: boolean, feedback: string) => void;
}

/**
 * Deduplicates consecutive messages from the same role with the same text.
 * Returns a new array with `repeatCount` appended where duplicates were found.
 */
function deduplicateMessages(
  msgs: ChatMessage[]
): (ChatMessage & { repeatCount?: number })[] {
  const result: (ChatMessage & { repeatCount?: number })[] = [];
  for (const msg of msgs) {
    // Skip empty/whitespace-only messages
    if (!msg.text.trim()) continue;

    const last = result[result.length - 1];
    if (last && last.role === msg.role && last.text === msg.text) {
      last.repeatCount = (last.repeatCount || 1) + 1;
    } else {
      result.push({ ...msg, repeatCount: undefined });
    }
  }
  return result;
}

export function MessageList({
  messages,
  logs,
  status,
  pendingDiffs,
  onRetry,
  onViewDiff,
  onResolveDiff,
}: MessageListProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, logs, pendingDiffs, status]);

  const dedupedMessages = deduplicateMessages(messages);

  // Find the index of the last user message
  const lastUserIdx = dedupedMessages
    .map((m, i) => (m.role === "user" ? i : -1))
    .filter((i) => i !== -1)
    .pop();

  return (
    <div className="message-list">
      {dedupedMessages.map((msg, i) => (
        <div key={msg.id || i} className="message-entry">
          <MessageBubble
            role={msg.role}
            text={msg.text}
            timestamp={msg.timestamp}
            isLastUser={i === lastUserIdx}
            isIdle={!status}
            onRetry={onRetry}
          />
          {msg.repeatCount && msg.repeatCount > 1 && (
            <span className="repeat-badge">repeated ×{msg.repeatCount}</span>
          )}
        </div>
      ))}

      <StreamLog logs={logs} />

      {pendingDiffs.map((diff) => (
        <DiffCard
          key={diff.id}
          diff={diff}
          onViewDiff={onViewDiff}
          onResolve={onResolveDiff}
        />
      ))}

      {status && (
        <div className="thinking-indicator">
          <div className="thinking-dots">
            <span />
            <span />
            <span />
          </div>
          <span className="thinking-text">{status}</span>
        </div>
      )}

      <div ref={endRef} />
    </div>
  );
}
