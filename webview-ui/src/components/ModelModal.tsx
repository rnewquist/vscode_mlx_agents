import { useState } from "react";
import { XIcon, FolderIcon } from "./Icons";

interface ModelsConfig {
  [key: string]: { adapter_path: string };
}

interface ModelModalProps {
  mode: "add" | "manage" | "confirm" | null;
  modelsConfig: ModelsConfig;
  onClose: () => void;
  onAddModel: (modelId: string, adapterPath: string) => void;
  onRemoveModel: (modelId: string) => void;
  onUpdateModel: (modelId: string, adapterPath: string) => void;
  onPickFolder: () => void;
  onConfirmClear: () => void;
  pickedFolderPath: string;
  clearPickedFolder: () => void;
}

export function ModelModal({
  mode,
  modelsConfig,
  onClose,
  onAddModel,
  onRemoveModel,
  onUpdateModel,
  onPickFolder,
  onConfirmClear,
  pickedFolderPath,
  clearPickedFolder,
}: ModelModalProps) {
  const [customModel, setCustomModel] = useState("");
  const [editingModel, setEditingModel] = useState<{
    id: string;
    adapterPath: string;
  } | null>(null);

  if (!mode) return null;

  const handleAdd = () => {
    if (!customModel.trim()) return;
    onAddModel(customModel.trim(), pickedFolderPath);
    setCustomModel("");
    clearPickedFolder();
  };

  const handleSaveEdit = () => {
    if (!editingModel) return;
    onUpdateModel(editingModel.id, editingModel.adapterPath);
    setEditingModel(null);
  };

  if (mode === "confirm") {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-glass" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h3>Start New Session?</h3>
          </div>
          <div className="modal-body">
            <p className="modal-desc">
              This will clear all chat history and reset the model's memory.
            </p>
          </div>
          <div className="modal-footer">
            <button className="modal-btn modal-btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button
              className="modal-btn modal-btn-danger"
              onClick={() => {
                onConfirmClear();
                onClose();
              }}
            >
              Clear Everything
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (mode === "add") {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-glass" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h3>Add New Model</h3>
            <button className="modal-close-btn" onClick={onClose}>
              <XIcon size={14} />
            </button>
          </div>
          <div className="modal-body">
            <div className="modal-field">
              <label>Hugging Face Repo ID</label>
              <input
                type="text"
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                placeholder="e.g. mlx-community/Llama-3.1-8B-Instruct-4bit"
                onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              />
            </div>
            <div className="modal-field">
              <label>LoRA Adapter (optional)</label>
              <div className="modal-field-row">
                <input
                  type="text"
                  value={pickedFolderPath}
                  readOnly
                  placeholder="No adapter selected"
                />
                <button className="modal-pick-btn" onClick={onPickFolder}>
                  <FolderIcon size={13} />
                </button>
              </div>
            </div>
          </div>
          <div className="modal-footer">
            <button className="modal-btn modal-btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button
              className="modal-btn modal-btn-primary"
              onClick={handleAdd}
              disabled={!customModel.trim()}
            >
              Add &amp; Load
            </button>
          </div>
        </div>
      </div>
    );
  }

  // mode === "manage"
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-glass modal-wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Manage Models</h3>
          <button className="modal-close-btn" onClick={onClose}>
            <XIcon size={14} />
          </button>
        </div>
        <div className="modal-body">
          {Object.keys(modelsConfig).length === 0 ? (
            <div className="drawer-empty">No custom models saved.</div>
          ) : (
            <div className="model-list">
              {Object.entries(modelsConfig).map(([id, cfg]) => (
                <div key={id} className="model-item">
                  <div className="model-info">
                    <span className="model-id">{id}</span>
                    <span className="model-adapter-label">
                      {cfg.adapter_path || "No adapter"}
                    </span>
                  </div>
                  <div className="model-actions">
                    <button
                      className="model-action-btn"
                      onClick={() =>
                        setEditingModel({ id, adapterPath: cfg.adapter_path })
                      }
                    >
                      Edit
                    </button>
                    <button
                      className="model-action-btn danger"
                      onClick={() => onRemoveModel(id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {editingModel && (
            <div className="model-edit-section">
              <h4>Editing: {editingModel.id}</h4>
              <div className="modal-field-row">
                <input
                  type="text"
                  value={editingModel.adapterPath}
                  readOnly
                  placeholder="No adapter selected"
                />
                <button
                  className="modal-pick-btn"
                  onClick={() => {
                    onPickFolder();
                    // The picked path will arrive via pickedFolderPath
                  }}
                >
                  <FolderIcon size={13} />
                </button>
              </div>
              <div className="model-edit-actions">
                <button
                  className="modal-btn modal-btn-ghost"
                  onClick={() => setEditingModel(null)}
                >
                  Cancel
                </button>
                <button
                  className="modal-btn modal-btn-primary"
                  onClick={handleSaveEdit}
                >
                  Save
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
