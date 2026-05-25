import { useState, useEffect, useRef } from "react";
import "highlight.js/styles/github-dark-dimmed.css";
import "./App.css";

import { ChatHeader } from "./components/ChatHeader";
import { WelcomeScreen } from "./components/WelcomeScreen";
import { MessageList } from "./components/MessageList";
import { InputArea } from "./components/InputArea";
import { DrawerPanel } from "./components/DrawerPanel";
import { ModelModal } from "./components/ModelModal";

// ── VS Code API ──
declare function acquireVsCodeApi(): any;
let vscodeApi: any = null;
try {
  vscodeApi = acquireVsCodeApi();
} catch {
  console.warn("acquireVsCodeApi unavailable (browser mode)");
}

const isBrowser = !vscodeApi;
const API_BASE = "";

const postToApi = async (endpoint: string, body: any) => {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return await res.json();
  } catch (err) {
    console.error(`API Error for ${endpoint}:`, err);
  }
};

// ── Types ──
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

type ModelsConfig = Record<string, { adapter_path: string }>;

// ── App ──
function App() {
  // State
  const [input, setInput] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [modelsConfig, setModelsConfig] = useState<ModelsConfig>({});
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState("");
  const [logs, setLogs] = useState("");
  const [pendingDiffs, setPendingDiffs] = useState<DiffRequest[]>([]);
  const [artifacts, setArtifacts] = useState<{ name: string; path: string }[]>([]);
  const [telemetry, setTelemetry] = useState<any>(null);
  const [serverStatus, setServerStatus] = useState<"disconnected" | "connecting" | "connected">("disconnected");
  const [activeTab, setActiveTab] = useState<"telemetry" | "artifacts" | null>(null);
  const [modalMode, setModalMode] = useState<"add" | "manage" | "confirm" | null>(null);
  const [pickedFolderPath, setPickedFolderPath] = useState("");
  const [isAddingModel, setIsAddingModel] = useState(false);
  const [pendingModelId, setPendingModelId] = useState("");

  // Refs for stale-closure safety
  const pendingModelIdRef = useRef("");
  const isAddingModelRef = useRef(false);

  useEffect(() => { pendingModelIdRef.current = pendingModelId; }, [pendingModelId]);
  useEffect(() => { isAddingModelRef.current = isAddingModel; }, [isAddingModel]);

  // ── Init ──
  useEffect(() => {
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "ready" });
      vscodeApi.postMessage({ type: "getModels" });
    } else {
      fetch(`${API_BASE}/api/get_models`)
        .then((r) => r.json())
        .then((config) => {
          setModelsConfig(config);
          const first = Object.keys(config)[0];
          if (first) {
            setSelectedModel(first);
            postToApi("/api/change_model", { modelId: first });
          }
        })
        .catch(console.error);
    }
  }, []);

  // ── Browser polling ──
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

        const currentThinking = !!data.status || data.serverStatus === "connecting";
        const newInterval = currentThinking ? 500 : 2000;
        if (newInterval !== pollInterval) {
          pollInterval = newInterval;
          clearInterval(timerId);
          timerId = setInterval(doPoll, pollInterval);
        }
      } catch {
        setServerStatus("disconnected");
      }
    };

    timerId = setInterval(doPoll, pollInterval);
    doPoll();
    return () => clearInterval(timerId);
  }, []);

  // ── VS Code message handler ──
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const msg = event.data;
      switch (msg.type) {
        case "response":
          setMessages((prev) => [...prev, { role: "assistant", text: msg.text, timestamp: Date.now() }]);
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
            if (prev.find((d) => d.id === msg.diff.id)) return prev;
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
          setServerStatus(msg.status);
          break;
        case "clearChat":
          setMessages([]);
          setLogs("");
          setArtifacts([]);
          break;
        case "modelsConfig": {
          const config = msg.config || {};
          setModelsConfig(config);
          const curPending = pendingModelIdRef.current;
          const curAdding = isAddingModelRef.current;
          if (curAdding && curPending && config[curPending]) {
            setSelectedModel(curPending);
            setIsAddingModel(false);
            setPendingModelId("");
            setModalMode(null);
            vscodeApi?.postMessage({ type: "changeModel", modelId: curPending });
          } else if (!selectedModel && Object.keys(config).length > 0) {
            const first = Object.keys(config)[0];
            setSelectedModel(first);
            vscodeApi?.postMessage({ type: "changeModel", modelId: first });
          }
          break;
        }
        case "folderPicked":
          setPickedFolderPath(msg.path);
          break;
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [selectedModel]);

  // ── Handlers ──
  const handleSend = () => {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { role: "user", text: input, timestamp: Date.now() }]);
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "sendMessage", text: input });
    } else {
      postToApi("/api/send_message", { text: input });
      setStatus("Thinking...");
    }
    setInput("");
  };

  const handleRetry = (text: string) => {
    if (status) return;
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "sendMessage", text });
    }
  };

  const handleInterrupt = () => {
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "interruptRun" });
    } else {
      postToApi("/api/stop_agent", {});
    }
  };

  const handleModelChange = (val: string) => {
    if (val === "add_new") {
      setModalMode("add");
    } else if (val === "manage") {
      setModalMode("manage");
    } else {
      setSelectedModel(val);
      if (vscodeApi) {
        vscodeApi.postMessage({ type: "changeModel", modelId: val });
      } else {
        postToApi("/api/change_model", { modelId: val });
      }
    }
  };

  const handleNewSession = () => {
    setModalMode("confirm");
  };

  const handleConfirmClear = () => {
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "clearHistory" });
    } else {
      postToApi("/api/clear_chat", {});
    }
    setMessages([]);
    setLogs("");
    setArtifacts([]);
  };

  const handleClearLogs = () => {
    setLogs("");
    setStatus("");
    setMessages((prev) => prev.filter((m) => m.role === "user" || m.role === "assistant"));
    if (!vscodeApi) postToApi("/api/clear_logs", {});
  };

  const handleAddModel = (modelId: string, adapterPath: string) => {
    setIsAddingModel(true);
    setPendingModelId(modelId);
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "addModel", modelId, adapterPath });
    } else {
      postToApi("/api/add_model", { modelId, adapterPath }).then((config) => {
        if (config) {
          setModelsConfig(config);
          setSelectedModel(modelId);
          setIsAddingModel(false);
          setPendingModelId("");
          setModalMode(null);
        }
      });
    }
  };

  const handleRemoveModel = (modelId: string) => {
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "removeModel", modelId });
    } else {
      postToApi("/api/remove_model", { modelId }).then((config) => {
        if (config) setModelsConfig(config);
      });
    }
  };

  const handleUpdateModel = (modelId: string, adapterPath: string) => {
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "updateModel", modelId, adapterPath });
    } else {
      postToApi("/api/update_model", { modelId, adapterPath }).then((config) => {
        if (config) setModelsConfig(config);
      });
    }
  };

  const handlePickFolder = () => {
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "pickFolder" });
    } else {
      const path = prompt("Enter adapter folder path:");
      if (path) setPickedFolderPath(path);
    }
  };

  const handleViewDiff = (diff: DiffRequest) => {
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "viewDiff", diff });
    } else {
      postToApi("/api/view_diff", { diff });
    }
  };

  const handleResolveDiff = (diffId: string, accept: boolean, feedback: string) => {
    setPendingDiffs((prev) => prev.filter((d) => d.id !== diffId));
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "resolveDiff", diffId, accept, feedback });
    } else {
      postToApi("/api/resolve_diff", { diffId, accept, feedback });
    }
  };

  const handleOpenArtifact = (path: string) => {
    if (vscodeApi) {
      vscodeApi.postMessage({ type: "openArtifact", path });
    } else {
      postToApi("/api/open_artifact", { path });
    }
  };

  const handleSuggestion = (text: string) => {
    setInput(text);
  };

  const toggleDrawer = (tab: "telemetry" | "artifacts") => {
    setActiveTab((prev) => (prev === tab ? null : tab));
  };

  return (
    <div className="app-container">
      <ChatHeader
        serverStatus={serverStatus}
        onNewSession={handleNewSession}
        onClearLogs={handleClearLogs}
      />

      <main className="main-content">
        {messages.length === 0 && !status ? (
          <WelcomeScreen onSuggestion={handleSuggestion} />
        ) : (
          <MessageList
            messages={messages}
            logs={logs}
            status={status}
            pendingDiffs={pendingDiffs}
            onRetry={handleRetry}
            onViewDiff={handleViewDiff}
            onResolveDiff={handleResolveDiff}
          />
        )}
      </main>

      <div style={{ position: "relative" }}>
        <DrawerPanel
          activeTab={activeTab}
          telemetry={telemetry}
          artifacts={artifacts}
          onClose={() => setActiveTab(null)}
          onOpenArtifact={handleOpenArtifact}
        />
        <InputArea
          input={input}
          setInput={setInput}
          selectedModel={selectedModel}
          modelsConfig={modelsConfig}
          status={status}
          activeTab={activeTab}
          onSend={handleSend}
          onInterrupt={handleInterrupt}
          onModelChange={handleModelChange}
          onToggleDrawer={toggleDrawer}
        />
      </div>

      <ModelModal
        mode={modalMode}
        modelsConfig={modelsConfig}
        onClose={() => setModalMode(null)}
        onAddModel={handleAddModel}
        onRemoveModel={handleRemoveModel}
        onUpdateModel={handleUpdateModel}
        onPickFolder={handlePickFolder}
        onConfirmClear={handleConfirmClear}
        pickedFolderPath={pickedFolderPath}
        clearPickedFolder={() => setPickedFolderPath("")}
      />

      {serverStatus === "connecting" && (
        <div className="loading-overlay">
          <div className="loading-spinner" />
          <div className="loading-text">Initializing MLX Server…</div>
          <div className="loading-subtext">This may take a moment on first load.</div>
        </div>
      )}
    </div>
  );
}

export default App;
