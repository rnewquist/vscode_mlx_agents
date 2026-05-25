import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { RetryIcon, CopyIcon, CheckIcon, BotIcon } from "./Icons";

interface MessageBubbleProps {
  role: string;
  text: string;
  timestamp?: number;
  isLastUser?: boolean;
  isIdle?: boolean;
  onRetry?: (text: string) => void;
  animationDelay?: number;
}

export function MessageBubble({
  role,
  text,
  timestamp,
  isLastUser,
  isIdle,
  onRetry,
  animationDelay = 0,
}: MessageBubbleProps) {
  const [copiedBlock, setCopiedBlock] = useState<number | null>(null);
  const showRetry = isLastUser && isIdle && role === "user";

  const handleCopy = (code: string, index: number) => {
    navigator.clipboard.writeText(code).then(() => {
      setCopiedBlock(index);
      setTimeout(() => setCopiedBlock(null), 2000);
    });
  };

  const formatTime = (ts?: number) => {
    if (!ts) return "";
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  let codeBlockIndex = 0;

  return (
    <div
      className={`msg-bubble msg-${role}`}
      style={{ animationDelay: `${animationDelay}ms` }}
    >
      {role === "assistant" && (
        <div className="msg-avatar">
          <BotIcon size={14} />
        </div>
      )}
      <div className="msg-content">
        <div className="msg-text">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeHighlight]}
            components={{
              pre({ children, ...props }) {
                const idx = codeBlockIndex++;
                // Extract raw text from the code element
                const codeEl = (children as any)?.[0];
                const rawText =
                  typeof codeEl?.props?.children === "string"
                    ? codeEl.props.children
                    : "";
                return (
                  <div className="code-block-wrapper">
                    <button
                      className="code-copy-btn"
                      onClick={() => handleCopy(rawText, idx)}
                      title="Copy code"
                    >
                      {copiedBlock === idx ? (
                        <CheckIcon size={12} />
                      ) : (
                        <CopyIcon size={12} />
                      )}
                    </button>
                    <pre {...props}>{children}</pre>
                  </div>
                );
              },
            }}
          >
            {text}
          </ReactMarkdown>
        </div>
        <div className="msg-meta">
          {timestamp && (
            <span className="msg-time">{formatTime(timestamp)}</span>
          )}
          {showRetry && onRetry && (
            <button
              className="msg-retry-btn"
              onClick={() => onRetry(text)}
              title="Retry this message"
            >
              <RetryIcon size={12} />
              <span>Retry</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
