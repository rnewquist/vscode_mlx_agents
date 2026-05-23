import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";

declare function acquireVsCodeApi(): any;
let vscodeApi: any = null;
try {
  vscodeApi = acquireVsCodeApi();
} catch (e) {
  // acquireVsCodeApi can only be called once
  console.warn("acquireVsCodeApi failed or already called", e);
}

const isBrowser = !vscodeApi;
const API_BASE = "";

const postToApi = async (endpoint: string, body: any) => {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    return await res.json();
  } catch (err) {
    console.error(`API Error for ${endpoint}:`, err);
  }
};


interface DiffRequest {
  id: string;
  file_path: string;
  original_content: string;
  new_content: string;
  tool_name: string;
}

// --- Icons ---
const SendIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13"></line>
    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
  </svg>
);

const StopIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
  </svg>
);

const ActivityIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
  </svg>
);

const FileIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
    <polyline points="13 2 13 9 20 9"></polyline>
  </svg>
);

const TrashIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 3 21 3 21 6"></polyline>
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
  </svg>
);

const PlusIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19"></line>
    <line x1="5" y1="12" x2="19" y2="12"></line>
  </svg>
);

function App() {
  const [input, setInput] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [customModelAdapterPath, setCustomModelAdapterPath] = useState("");
  const [modelsConfig, setModelsConfig] = useState<Record<string, { adapter_path: string }>>({});
  const [showModelManager, setShowModelManager] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showConfirmNewSession, setShowConfirmNewSession] = useState(false);
  const [isAddingModel, setIsAddingModel] = useState(false);
  const [pendingModelId, setPendingModelId] = useState("");
  const [editingModel, setEditingModel] = useState<{ id: string, adapterPath: string } | null>(null);
  
  const [messages, setMessages] = useState<{ role: string; text: string }[]>([]);
  const [status, setStatus] = useState("");
  const [logs, setLogs] = useState("");
  const [pendingDiffs, setPendingDiffs] = useState<DiffRequest[]>([]);
  const [artifacts, setArtifacts] = useState<{name: string, path: string}[]>([]);
  const [telemetry, setTelemetry] = useState<any>(null);
  const [serverStatus, setServerStatus] = useState<"disconnected" | "connecting" | "connected">("disconnected");

  const [activeTab, setActiveTab] = useState<"telemetry" | "artifacts" | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Use refs for values needed in message handlers to avoid stale closures
  const pendingModelIdRef = useRef("");
  const isAddingModelRef = useRef(false);

  useEffect(() => {
    pendingModelIdRef.current = pendingModelId;
  }, [pendingModelId]);

  useEffect(() => {
    isAddingModelRef.current = isAddingModel;
  }, [isAddingModel]);

  useEffect(() => {
    if (vscodeApi) {
      console.log("Webview: Sending init messages");
      vscodeApi.postMessage({ type: "ready" });
      vscodeApi.postMessage({ type: "getModels" });
    } else {
      fetch(`${API_BASE}/api/get_models`)
        .then(res => res.json())
        .then(config => {
          setModelsConfig(config);
          if (Object.keys(config).length > 0) {
            const firstModel = Object.keys(config)[0];
            setSelectedModel(firstModel);
            postToApi("/api/change_model", { modelId: firstModel });
          }
        })
        .catch(err => console.error("Error fetching models:", err));
    }
  }, []); // Run ONCE on mount

  useEffect(() => {
    if (!isBrowser) return;

    let pollInterval = 1000;
    let timerId: any = null;

    const doPoll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/status`);
        const data = await res.json();
        
        if (data.messages !== undefined) setMessages(data.messages);
        if (data.status !== undefined) setStatus(data.status);
        if (data.logs !== undefined) setLogs(data.logs);
        if (data.pendingDiffs !== undefined) setPendingDiffs(data.pendingDiffs);
        if (data.artifacts !== undefined) setArtifacts(data.artifacts);
        if (data.telemetry !== undefined) setTelemetry(data.telemetry);
        if (data.serverStatus !== undefined) setServerStatus(data.serverStatus);
        if (data.modelsConfig !== undefined) setModelsConfig(data.modelsConfig);
        
        // Adjust poll rate based on activity
        const currentThinking = !!data.status || data.serverStatus === "connecting";
        const newInterval = currentThinking ? 500 : 2000;
        if (newInterval !== pollInterval) {
          pollInterval = newInterval;
          clearInterval(timerId);
          timerId = setInterval(doPoll, pollInterval);
        }
      } catch (err) {
        console.error("Polling error:", err);
        setServerStatus("disconnected");
      }
    };

    timerId = setInterval(doPoll, pollInterval);
    doPoll(); // immediate first run

    return () => clearInterval(timerId);
  }, []);


  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const msg = event.data;
      console.log("Webview: Received message", msg.type, msg);
      
      switch (msg.type) {
        case "response":
          setMessages((prev) => [...prev, { role: "assistant", text: msg.text }]);
          setStatus("");
          setLogs("");
          break;
        case "status":
          setStatus(msg.text);
          break;
        case "restoreHistory":
          if (msg.messages) setMessages(msg.messages);
          break;
        case "streamLog":
          setLogs((prev) => prev + msg.text);
          break;
        case "pendingDiff":
          setPendingDiffs((prev) => {
            if (prev.find(d => d.id === msg.diff.id)) return prev;
            return [...prev, msg.diff];
          });
          break;
        case "artifacts":
          setArtifacts(msg.artifacts || []);
          break;
        case "telemetry":
          setTelemetry(msg.tree);
          break;
        case "serverStatus":
          console.log("Webview: Server status update", msg.status);
          setServerStatus(msg.status);
          break;
        case "clearChat":
          setMessages([]);
          setLogs("");
          setArtifacts([]);
          break;
        case "modelsConfig":
          console.log("Webview: Updating modelsConfig", msg.config);
          const config = msg.config || {};
          setModelsConfig(config);
          
          const currentPending = pendingModelIdRef.current;
          const currentAdding = isAddingModelRef.current;
          
          if (currentAdding && currentPending && config[currentPending]) {
            console.log("Webview: Add flow confirmed by backend for", currentPending);
            setSelectedModel(currentPending);
            setIsAddingModel(false);
            setPendingModelId("");
            setShowAddModal(false);
            // Confirm the selection with the backend, but don't force a load yet
            vscodeApi.postMessage({ type: "changeModel", modelId: currentPending });
          } else if (!selectedModel && Object.keys(config).length > 0) {
            console.log("Webview: Initializing selection to", Object.keys(config)[0]);
            const firstModel = Object.keys(config)[0];
            setSelectedModel(firstModel);
            // Tell backend about the current selected model ID
            vscodeApi.postMessage({ type: "changeModel", modelId: firstModel });
          }
          break;
        case "folderPicked":
          if (editingModel) {
            setEditingModel({ ...editingModel, adapterPath: msg.path });
          } else {
            setCustomModelAdapterPath(msg.path);
          }
          break;
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [editingModel, selectedModel]); // selectedModel here is fine for the confirm flow check

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, logs, pendingDiffs]);

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (val === "add_new") {
      setShowAddModal(true);
    } else if (val === "manage") {
      setShowModelManager(true);
    } else {
      setSelectedModel(val);
      if (vscodeApi) {
        vscodeApi.postMessage({ type: "changeModel", modelId: val });
      } else {
        postToApi("/api/change_model", { modelId: val });
      }
    }
  };

  const submitAddModel = () => {
    console.log("Webview: submitAddModel", customModel);
    if (!customModel) return;
    
    if (vscodeApi) {
      const modelId = customModel;
      const adapterPath = customModelAdapterPath;
      
      setIsAddingModel(true);
      setPendingModelId(modelId);
      
      vscodeApi.postMessage({ 
        type: "addModel", 
        modelId, 
        adapterPath 
      });

      // Clear local form state
      setCustomModel("");
      setCustomModelAdapterPath("");
    } else {
      const modelId = customModel;
      const adapterPath = customModelAdapterPath;
      setIsAddingModel(true);
      setPendingModelId(modelId);
      postToApi("/api/add_model", { modelId, adapterPath }).then(config => {
        if (config) {
          setModelsConfig(config);
          setSelectedModel(modelId);
          setIsAddingModel(false);
          setPendingModelId("");
          setShowAddModal(false);
        }
      });
      setCustomModel("");
      setCustomModelAdapterPath("");
    }
  };

  const pickFolder = () => {
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "pickFolder" });
    } else {
      const path = prompt("Enter custom LoRA adapter folder path:");
      if (path) {
        if (editingModel) {
          setEditingModel({ ...editingModel, adapterPath: path });
        } else {
          setCustomModelAdapterPath(path);
        }
      }
    }
  };

  const deleteModel = (id: string) => {
    if (confirm(`Are you sure you want to delete model "${id}"?`)) {
      if (vscodeApi) {
        vscodeApi.postMessage({ type: "removeModel", modelId: id });
      } else {
        postToApi("/api/remove_model", { modelId: id }).then(config => {
          if (config) setModelsConfig(config);
        });
      }
    }
  };

  const startEditModel = (id: string, adapterPath: string) => {
    setEditingModel({ id, adapterPath });
  };

  const saveEditModel = () => {
    if (editingModel) {
      if (vscodeApi) {
        vscodeApi.postMessage({ 
          type: "updateModel", 
          modelId: editingModel.id, 
          adapterPath: editingModel.adapterPath 
        });
      } else {
        postToApi("/api/update_model", { 
          modelId: editingModel.id, 
          adapterPath: editingModel.adapterPath 
        }).then(config => {
          if (config) setModelsConfig(config);
        });
      }
      setEditingModel(null);
    }
  };

  const handleSend = () => {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { role: "user", text: input }]);
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "sendMessage", text: input });
    } else {
      postToApi("/api/send_message", { text: input });
      setStatus("Thinking...");
    }
    setInput("");
  };

  const handleClearWorkspace = () => {
    setLogs("");
    setStatus("");
    // Also remove any remaining system/status artifacts from the message list if they exist
    setMessages(prev => prev.filter(m => m.role === 'user' || m.role === 'assistant'));
    if (!vscodeApi) {
      postToApi("/api/clear_logs", {});
    }
  };

  const handleNewSession = () => {
    setShowConfirmNewSession(true);
  };

  const confirmNewSession = () => {
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "clearHistory" });
      setMessages([]);
      setLogs("");
      setArtifacts([]);
    } else {
      postToApi("/api/clear_chat", {});
      setMessages([]);
      setLogs("");
      setArtifacts([]);
    }
    setShowConfirmNewSession(false);
  };

  const handleRetry = (text: string) => {
    if (status) return;
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "sendMessage", text: text });
    }
  };

  const resolveDiff = (diffId: string, accept: boolean) => {
    const feedback = accept ? "" : prompt("Why are you rejecting this change? (Feedback for the agent):", "");
    if (!accept && feedback === null) return;
    
    setPendingDiffs((prev) => prev.filter(d => d.id !== diffId));
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "resolveDiff", diffId, accept, feedback });
    } else {
      postToApi("/api/resolve_diff", { diffId, accept, feedback });
    }
  };

  const viewDiff = (diff: DiffRequest) => {
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "viewDiff", diff });
    } else {
      postToApi("/api/view_diff", { diff });
      alert(`Diff for ${diff.file_path}:\n\nTool: ${diff.tool_name}\n\nReview the changes directly in your editor.`);
    }
  };

  const handleInterrupt = () => {
    const promptFeedback = prompt("Enter instructions to correct the agent's course:");
    if (promptFeedback === null) return;
    
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "interruptRun" });
      if (promptFeedback) {
        setMessages((prev) => [...prev, { role: "user", text: promptFeedback }]);
        vscodeApi.postMessage({ type: "sendMessage", text: promptFeedback });
      }
    } else {
      postToApi("/api/stop_agent", {});
      if (promptFeedback) {
        setMessages((prev) => [...prev, { role: "user", text: promptFeedback }]);
        postToApi("/api/send_message", { text: promptFeedback });
        setStatus("Thinking...");
      }
    }
  };

  const renderNode = (node: any) => {
    if (!node) return null;
    return (
      <div key={node.id} className="telemetry-node">
        <span className={`status-indicator ${node.status}`}></span>
        <strong>{node.name}</strong> ({node.status})
        {node.children && node.children.length > 0 && (
          <div className="telemetry-children">
            {node.children.map(renderNode)}
          </div>
        )}
      </div>
    );
  };

  const toggleDrawer = (tab: "telemetry" | "artifacts") => {
    if (activeTab === tab) setActiveTab(null);
    else setActiveTab(tab);
  };

  return (
    <div className="app-container">
      <header className="header">
        <div className="header-actions">
          <button className="icon-btn header-btn" onClick={handleNewSession} title="New Session">
            <PlusIcon />
          </button>
          <button className="icon-btn header-btn" onClick={handleClearWorkspace} title="Clear Logs & Status">
            <TrashIcon />
          </button>
        </div>
        <span className="dot"></span>
        <span className="title">MLX Agent</span>
        {serverStatus === "connecting" && <span className="status-badge">Server Loading...</span>}
      </header>

      <main className="messages">
        {showConfirmNewSession && (
          <div className="modal-overlay">
            <div className="modal-content" style={{ textAlign: 'center', padding: '24px' }}>
              <h3>Start New Session?</h3>
              <p style={{ fontSize: '12px', margin: '16px 0', opacity: 0.8 }}>This will clear all current chat history and reset the model's memory.</p>
              <div style={{ display: 'flex', gap: '8px', justifyContent: 'center' }}>
                <button className="reject" onClick={confirmNewSession} style={{ padding: '6px 20px', borderRadius: '4px', border: 'none', cursor: 'pointer', background: '#da3633', color: 'white' }}>Clear Everything</button>
                <button onClick={() => setShowConfirmNewSession(false)} style={{ padding: '6px 20px', borderRadius: '4px', border: 'none', cursor: 'pointer', background: 'transparent', color: 'var(--foreground)' }}>Cancel</button>
              </div>
            </div>
          </div>
        )}
        {serverStatus === "connecting" && (
          <div className="modal-overlay">
            <div className="modal-content loading-modal" style={{ textAlign: 'center', padding: '32px' }}>
              <div className="spinner"></div>
              <h3 style={{ marginTop: '16px' }}>Initializing MLX Server...</h3>
              <p style={{ fontSize: '11px', color: '#888' }}>This may take a moment on first load.</p>
            </div>
          </div>
        )}
        
        {showModelManager && (
          <div className="modal-overlay">
            <div className="modal-content">
              <div className="modal-header">
                <h3>Manage Models & Adapters</h3>
                <button className="icon-btn" onClick={() => setShowModelManager(false)}>✖</button>
              </div>
              <div className="model-list">
                {Object.entries(modelsConfig).map(([id, cfg]) => (
                  <div key={id} className="model-item">
                    <div className="model-info">
                      <div className="model-id">{id}</div>
                      <div className="model-adapter">Adapter: {cfg.adapter_path || "None"}</div>
                    </div>
                    <div className="model-actions">
                      <button onClick={() => startEditModel(id, cfg.adapter_path)}>Edit</button>
                      <button onClick={() => deleteModel(id)} className="reject">Delete</button>
                    </div>
                  </div>
                ))}
                {Object.keys(modelsConfig).length === 0 && <p className="empty-text">No custom models saved.</p>}
              </div>
              {editingModel && (
                <div className="edit-section">
                  <h4>Editing {editingModel.id}</h4>
                  <div className="input-group">
                    <input type="text" value={editingModel.adapterPath} readOnly placeholder="No adapter selected" />
                    <button onClick={pickFolder}>Pick Folder</button>
                  </div>
                  <div className="edit-actions">
                    <button onClick={saveEditModel} className="accept">Save</button>
                    <button onClick={() => setEditingModel(null)}>Cancel</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {showAddModal && (
          <div className="modal-overlay">
            <div className="modal-content">
              <div className="modal-header">
                <h3>Add New MLX Model</h3>
                <button className="icon-btn" onClick={() => { console.log("Close clicked"); setShowAddModal(false); }}>✖</button>
              </div>
              <div className="modal-body">
                <div className="input-field">
                  <label>Hugging Face Repo ID</label>
                  <input 
                    type="text" 
                    value={customModel} 
                    onChange={(e) => setCustomModel(e.target.value)} 
                    placeholder="e.g. mlx-community/Llama-3.1-8B-Instruct-4bit"
                  />
                </div>
                <div className="input-field">
                  <label>Optional LoRA Adapter</label>
                  <div className="input-group">
                    <input 
                      type="text" 
                      value={customModelAdapterPath} 
                      readOnly 
                      placeholder="Select adapter folder..." 
                    />
                    <button onClick={() => { console.log("Pick folder clicked"); pickFolder(); }}>📁</button>
                  </div>
                </div>
              </div>
              <div className="modal-actions">
                <button 
                  onClick={() => { console.log("Add & Load clicked"); submitAddModel(); }} 
                  className="accept"
                >
                  Add & Load
                </button>
                <button 
                  onClick={() => { console.log("Cancel clicked"); setShowAddModal(false); }} 
                  className="cancel-btn"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {messages.length === 0 && (
          <div className="welcome">
            <h2>🤖 MLX Chat (Antigravity UI)</h2>
            <p>Talk directly to your local model running on Apple Silicon.</p>
          </div>
        )}

        {messages.map((msg, i) => {
          const lastUserIndex = [...messages].map((m, idx) => m.role === 'user' ? idx : -1).filter(idx => idx !== -1).pop();
          const isRetryVisible = msg.role === 'user' && i === lastUserIndex && !status;

          return (
            <div key={i} className={`message ${msg.role}`}>
              <div className="message-text">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.text}
                </ReactMarkdown>
              </div>
              {isRetryVisible && (
                <button className="retry-inline-btn" onClick={() => handleRetry(msg.text)}>
                  ↻ Retry
                </button>
              )}
            </div>
          );
        })}

        {logs && (
          <div className="message log-box">
            <pre>{logs}</pre>
          </div>
        )}

        {pendingDiffs.map(diff => (
          <div key={diff.id} className="message diff-card">
            <h4>Review Required: {diff.file_path}</h4>
            <p>Agent wants to apply a {diff.tool_name} operation.</p>
            <div className="diff-actions">
              <button onClick={() => viewDiff(diff)} style={{ background: '#007acc' }}>View Diff</button>
              <button onClick={() => resolveDiff(diff.id, true)} className="accept">Accept</button>
              <button onClick={() => resolveDiff(diff.id, false)} className="reject">Reject</button>
            </div>
          </div>
        ))}

        {status && <div className="message status">{status}</div>}
        <div ref={messagesEndRef} />
      </main>

      <footer className="input-area-wrapper">
        {activeTab && (
          <div className="drawer-popup">
            {activeTab === "telemetry" && (
              <div className="drawer-panel">
                <div className="drawer-header">
                  <h3>Agent Telemetry</h3>
                  <button className="icon-btn close-btn" onClick={() => setActiveTab(null)}>✖</button>
                </div>
                <div className="drawer-content">
                  {telemetry ? renderNode(telemetry) : <span className="empty-text">No active agents.</span>}
                </div>
              </div>
            )}
            {activeTab === "artifacts" && (
              <div className="drawer-panel">
                <div className="drawer-header">
                  <h3>Artifacts</h3>
                  <button className="icon-btn close-btn" onClick={() => setActiveTab(null)}>✖</button>
                </div>
                <div className="drawer-content">
                  {artifacts.length === 0 ? <span className="empty-text">No files generated yet.</span> : (
                    <ul className="artifact-list">
                      {[...artifacts].reverse().map((art, idx) => (
                        <li key={idx}>
                          <a href="#" onClick={(e) => { 
                            e.preventDefault(); 
                            if (vscodeApi) {
                              vscodeApi.postMessage({ type: 'openArtifact', path: art.path }); 
                            } else {
                              postToApi("/api/open_artifact", { path: art.path });
                            }
                          }}>
                            📄 {art.name}
                            <span className="artifact-path" style={{ display: 'block', fontSize: '9px', opacity: 0.5, marginLeft: '18px' }}>{art.path}</span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="unified-input-container">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Message MLX..."
            rows={1}
          />
          <div className="unified-input-toolbar">
            <div className="toolbar-left">
              <select value={selectedModel} onChange={handleModelChange} className="inline-model-select">
                {Object.keys(modelsConfig).length === 0 ? (
                  <option value="" disabled>No models added</option>
                ) : (
                  Object.keys(modelsConfig).map(id => (
                    <option key={id} value={id}>{id}</option>
                  ))
                )}
                <option disabled>──────────</option>
                <option value="add_new">+ Add New Model...</option>
                {Object.keys(modelsConfig).length > 0 && (
                  <option value="manage">Manage Saved Models...</option>
                )}
              </select>
              
              <button 
                className={`icon-btn toggle-btn ${activeTab === 'telemetry' ? 'active' : ''}`} 
                onClick={() => toggleDrawer("telemetry")}
                title="Agent Telemetry"
              >
                <ActivityIcon />
              </button>
              <button 
                className={`icon-btn toggle-btn ${activeTab === 'artifacts' ? 'active' : ''}`} 
                onClick={() => toggleDrawer("artifacts")}
                title="Artifacts"
              >
                <FileIcon />
              </button>
            </div>

            <div className="toolbar-right">
              {status && (
                <button className="icon-btn interrupt-btn" onClick={handleInterrupt} title="Interrupt Agent">
                  <StopIcon />
                </button>
              )}
              <button 
                className="icon-btn send-btn" 
                disabled={!input.trim() || !!status || !selectedModel} 
                onClick={handleSend}
                title="Send Message"
              >
                <SendIcon />
              </button>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
