import { useState } from "react";
import { FileIcon, CheckIcon, XIcon } from "./Icons";

interface DiffRequest {
  id: string;
  file_path: string;
  original_content: string;
  new_content: string;
  tool_name: string;
}

interface DiffCardProps {
  diff: DiffRequest;
  onViewDiff: (diff: DiffRequest) => void;
  onResolve: (diffId: string, accept: boolean, feedback: string) => void;
}

export function DiffCard({ diff, onViewDiff, onResolve }: DiffCardProps) {
  const [showReject, setShowReject] = useState(false);
  const [feedback, setFeedback] = useState("");

  const fileName = diff.file_path.split("/").pop() || diff.file_path;

  const handleReject = () => {
    if (!showReject) {
      setShowReject(true);
      return;
    }
    onResolve(diff.id, false, feedback);
    setShowReject(false);
    setFeedback("");
  };

  return (
    <div className="diff-card">
      <div className="diff-card-header">
        <FileIcon size={14} />
        <span className="diff-file-name">{fileName}</span>
        <span className="diff-tool-badge">{diff.tool_name}</span>
      </div>
      <p className="diff-card-path">{diff.file_path}</p>

      {showReject && (
        <div className="diff-reject-input">
          <input
            type="text"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Why are you rejecting? (feedback for agent)"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") handleReject();
              if (e.key === "Escape") {
                setShowReject(false);
                setFeedback("");
              }
            }}
          />
        </div>
      )}

      <div className="diff-card-actions">
        <button className="diff-btn diff-btn-view" onClick={() => onViewDiff(diff)}>
          View Diff
        </button>
        <button
          className="diff-btn diff-btn-accept"
          onClick={() => onResolve(diff.id, true, "")}
        >
          <CheckIcon size={12} />
          Accept
        </button>
        <button className="diff-btn diff-btn-reject" onClick={handleReject}>
          <XIcon size={12} />
          {showReject ? "Confirm Reject" : "Reject"}
        </button>
      </div>
    </div>
  );
}
