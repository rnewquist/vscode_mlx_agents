import type React from "react";
import { XIcon, FileIcon, ActivityIcon, ChevronRightIcon } from "./Icons";

interface DrawerPanelProps {
  activeTab: "telemetry" | "artifacts" | null;
  telemetry: any;
  artifacts: { name: string; path: string }[];
  onClose: () => void;
  onOpenArtifact: (path: string) => void;
}

export function DrawerPanel({
  activeTab,
  telemetry,
  artifacts,
  onClose,
  onOpenArtifact,
}: DrawerPanelProps) {
  if (!activeTab) return null;

  const renderTelemetryNode = (node: any): React.JSX.Element | null => {
    if (!node) return null;
    return (
      <div key={node.id} className="telem-node">
        <div className="telem-node-header">
          <span className={`telem-dot telem-${node.status}`} />
          <span className="telem-name">{node.name}</span>
          <span className="telem-status">{node.status}</span>
        </div>
        {node.children && node.children.length > 0 && (
          <div className="telem-children">
            {node.children.map(renderTelemetryNode)}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="drawer-overlay">
      <div className="drawer-panel-container">
        <div className="drawer-header">
          <div className="drawer-title">
            {activeTab === "telemetry" ? (
              <>
                <ActivityIcon size={14} /> Agent Telemetry
              </>
            ) : (
              <>
                <FileIcon size={14} /> Artifacts
              </>
            )}
          </div>
          <button className="drawer-close-btn" onClick={onClose}>
            <XIcon size={14} />
          </button>
        </div>
        <div className="drawer-body">
          {activeTab === "telemetry" && (
            <>
              {telemetry ? (
                renderTelemetryNode(telemetry)
              ) : (
                <div className="drawer-empty">No active agents.</div>
              )}
            </>
          )}
          {activeTab === "artifacts" && (
            <>
              {artifacts.length === 0 ? (
                <div className="drawer-empty">No files generated yet.</div>
              ) : (
                <ul className="artifact-list">
                  {[...artifacts].reverse().map((art, idx) => (
                    <li key={idx}>
                      <button
                        className="artifact-item"
                        onClick={() => onOpenArtifact(art.path)}
                      >
                        <FileIcon size={13} />
                        <div className="artifact-info">
                          <span className="artifact-name">{art.name}</span>
                          <span className="artifact-path">{art.path}</span>
                        </div>
                        <ChevronRightIcon size={12} className="artifact-chevron" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
