import { useRef, useEffect, useState } from "react";
import { TerminalIcon, ChevronDownIcon } from "./Icons";

interface StreamLogProps {
  logs: string;
}

export function StreamLog({ logs }: StreamLogProps) {
  const logRef = useRef<HTMLPreElement>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (!logRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = logRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 30;
    setAutoScroll(atBottom);
  };

  if (!logs) return null;

  return (
    <div className={`stream-log ${collapsed ? "collapsed" : ""}`}>
      <div className="stream-log-header" onClick={() => setCollapsed(!collapsed)}>
        <TerminalIcon size={12} />
        <span>Agent Logs</span>
        <ChevronDownIcon
          size={12}
          className={`chevron ${collapsed ? "rotated" : ""}`}
        />
      </div>
      {!collapsed && (
        <pre
          ref={logRef}
          className="stream-log-content"
          onScroll={handleScroll}
        >
          {logs}
        </pre>
      )}
    </div>
  );
}
