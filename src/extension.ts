import * as vscode from "vscode";
import { McpClient } from "./mcpClient.js";
import { getChatHtml } from "./chatView.js";

const FALLBACK_MLX_ROOT = "/Users/rnewquist/Documents/mlx";

let mcpClient: McpClient | null = null;

interface ChatMessage {
    role: "user" | "assistant" | "system";
    text: string;
    timestamp: number;
}

export function activate(context: vscode.ExtensionContext) {
    McpClient.extensionPath = context.extensionPath;
    const provider = new MlxChatViewProvider(context);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider("mlxChatView", provider, {
            webviewOptions: { retainContextWhenHidden: true },
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand("mlx-chat.resetSystem", async () => {
            const client = getOrCreateClient();
            const result = await client.callTool("reset_system", {});
            vscode.window.showInformationMessage(`MLX: ${result}`);
        })
    );

    context.subscriptions.push({
        dispose: () => {
            mcpClient?.dispose();
            mcpClient = null;
        },
    });
}

function getOrCreateClient(): McpClient {
    if (!mcpClient) {
        mcpClient = new McpClient();
    }
    return mcpClient;
}

function resolveWorkspaceRoot(): string {
    const folders = vscode.workspace.workspaceFolders;
    if (folders && folders.length > 0) {
        return folders[0].uri.fsPath;
    }
    return ""; // Return empty if no workspace open
}

class MlxChatViewProvider implements vscode.WebviewViewProvider {
    private _view?: vscode.WebviewView;
    private _messages: ChatMessage[] = [];
    private readonly _stateKey: string;
    private _currentRunId: string | null = null;

    constructor(private readonly _context: vscode.ExtensionContext) {
        // Conversation key scoped to the workspace
        const wsRoot = resolveWorkspaceRoot();
        this._stateKey = `mlx-chat-history:${wsRoot}`;

        // Load persisted conversation
        const saved = this._context.workspaceState.get<ChatMessage[]>(this._stateKey);
        if (saved) {
            this._messages = saved;
        }
    }

    resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
        };

        webviewView.webview.html = getChatHtml(webviewView.webview, this._context.extensionUri);

        // Subscribe to server status changes
        const client = getOrCreateClient();
        client.setStatusCallback((status) => {
            console.log("Extension: Server status changed to", status);
            this._view?.webview.postMessage({ type: "serverStatus", status });
        });

        // Restore conversation history once the webview is ready
        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.type) {
                case "ready":
                    // Webview just loaded — send it the persisted history
                    this._view?.webview.postMessage({
                        type: "restoreHistory",
                        messages: this._messages,
                    });
                    break;
                case "sendMessage":
                    await this.handleUserMessage(message.text);
                    break;
                case "slashCommand":
                    await this.handleSlashCommand(message.command, message.args);
                    break;
                case "clearHistory":
                    this._messages = [];
                    this.persistMessages();
                    const client = getOrCreateClient();
                    // Optional: call backend to reset session if needed
                    await client.callTool("reset_system", {});
                    break;
                case "changeModel":
                    await this.handleChangeModel(message.modelId);
                    break;
                case "getModels":
                    await this.handleGetModels();
                    break;
                case "addModel":
                    await this.handleAddModel(message.modelId, message.adapterPath);
                    break;
                case "removeModel":
                    await this.handleRemoveModel(message.modelId);
                    break;
                case "updateModel":
                    await this.handleUpdateModel(message.modelId, message.adapterPath);
                    break;
                case "pickFolder":
                    await this.handlePickFolder();
                    break;
                case "resolveDiff":
                    await this.handleResolveDiff(message.diffId, message.accept, message.feedback);
                    break;
                case "viewDiff":
                    await this.handleViewDiff(message.diff);
                    break;
                case "interruptRun":
                    await this.handleInterruptRun();
                    break;
                case "openArtifact":
                    const uri = vscode.Uri.file(message.path);
                    vscode.window.showTextDocument(uri);
                    break;
            }
        });
    }

    private async handleGetModels() {
        console.log("Extension: handleGetModels triggered");
        try {
            const client = getOrCreateClient();
            const config = await client.callTool("get_models", {});
            console.log("Extension: get_models response:", config);
            this._view?.webview.postMessage({ type: "modelsConfig", config: JSON.parse(config) });
        } catch (err) {
            console.error("Extension: Error getting models:", err);
        }
    }

    private async handleAddModel(modelId: string, adapterPath: string) {
        console.log("Extension: handleAddModel triggered", { modelId, adapterPath });
        try {
            const client = getOrCreateClient();
            const configStr = await client.callTool("add_model", { model_id: modelId, adapter_path: adapterPath });
            console.log("Extension: add_model response:", configStr);
            vscode.window.showInformationMessage(`Model "${modelId}" added successfully.`);
            this._view?.webview.postMessage({ type: "modelsConfig", config: JSON.parse(configStr) });
        } catch (err) {
            console.error("Extension: Error adding model:", err);
            vscode.window.showErrorMessage(`Failed to add model: ${err}`);
        }
    }

    private async handleRemoveModel(modelId: string) {
        console.log("Extension: handleRemoveModel triggered", modelId);
        try {
            const client = getOrCreateClient();
            const configStr = await client.callTool("remove_model", { model_id: modelId });
            console.log("Extension: remove_model response:", configStr);
            vscode.window.showInformationMessage(`Model "${modelId}" removed.`);
            this._view?.webview.postMessage({ type: "modelsConfig", config: JSON.parse(configStr) });
        } catch (err) {
            console.error("Extension: Error removing model:", err);
            vscode.window.showErrorMessage(`Failed to remove model: ${err}`);
        }
    }

    private async handleUpdateModel(modelId: string, adapterPath: string) {
        console.log("Extension: handleUpdateModel triggered", { modelId, adapterPath });
        try {
            const client = getOrCreateClient();
            const configStr = await client.callTool("update_model", { model_id: modelId, adapter_path: adapterPath });
            console.log("Extension: update_model response:", configStr);
            vscode.window.showInformationMessage(`Model "${modelId}" updated.`);
            this._view?.webview.postMessage({ type: "modelsConfig", config: JSON.parse(configStr) });
        } catch (err) {
            console.error("Extension: Error updating model:", err);
            vscode.window.showErrorMessage(`Failed to update model: ${err}`);
        }
    }

    private async handlePickFolder() {
        console.log("Extension: handlePickFolder triggered");
        const options: vscode.OpenDialogOptions = {
            canSelectFiles: false,
            canSelectFolders: true,
            canSelectMany: false,
            openLabel: "Select Adapter Folder",
        };

        const folderUri = await vscode.window.showOpenDialog(options);
        if (folderUri && folderUri[0]) {
            console.log("Extension: folderPicked:", folderUri[0].fsPath);
            this._view?.webview.postMessage({ type: "folderPicked", path: folderUri[0].fsPath });
        }
    }

    private async handleViewDiff(diff: any) {
        try {
            // Write contents to temp files
            const os = require("os");
            const path = require("path");
            const fs = require("fs");
            
            const tmpDir = os.tmpdir();
            const originalPath = path.join(tmpDir, `original_${diff.id}.txt`);
            const modifiedPath = path.join(tmpDir, `modified_${diff.id}.txt`);
            
            fs.writeFileSync(originalPath, diff.original_content);
            fs.writeFileSync(modifiedPath, diff.new_content);
            
            const originalUri = vscode.Uri.file(originalPath);
            const modifiedUri = vscode.Uri.file(modifiedPath);
            
            await vscode.commands.executeCommand(
                "vscode.diff",
                originalUri,
                modifiedUri,
                `Review Patch: ${path.basename(diff.file_path)}`
            );
        } catch (err) {
            console.error("Failed to open diff view", err);
        }
    }

    private async handleResolveDiff(diffId: string, accept: boolean, feedback: string) {
        if (!this._view) return;
        try {
            const client = getOrCreateClient();
            await client.callTool("resolve_diff", { diff_id: diffId, accept, feedback });
            this.pushMessage("assistant", accept ? "✅ Changes accepted." : `❌ Changes rejected. Feedback: ${feedback}`);
            this.postResponse(accept ? "✅ Changes accepted." : `❌ Changes rejected. Feedback: ${feedback}`);
        } catch (err: unknown) {
            console.error("Error resolving diff", err);
        }
    }

    private async handleChangeModel(modelId: string) {
        if (!this._view) { return; }
        this.postStatus(`Loading model ${modelId}...`);
        try {
            const client = getOrCreateClient();
            const response = await client.callTool("change_model", { model_id: modelId });
            // Don't push these to history, just send to webview as a one-time response
            this.postResponse(response);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            this.postResponse(`❌ Failed to change model: ${msg}`);
        }
    }

    private pushMessage(role: ChatMessage["role"], text: string) {
        // Only persist actual user/assistant dialogue
        const dialogueFilters = [
            "Model changed to",
            "Checking model availability",
            "MLX Model loaded",
            "Successfully applied",
            "Resolved",
            "Changes accepted",
            "Changes rejected"
        ];
        
        if (role === "assistant") {
            if (dialogueFilters.some(filter => text.includes(filter))) {
                console.log("Extension: Filtering system message from history:", text);
                return;
            }
        }

        this._messages.push({ role, text, timestamp: Date.now() });
        this.persistMessages();
    }

    private persistMessages() {
        // Keep last 200 messages to avoid unbounded growth
        if (this._messages.length > 200) {
            this._messages = this._messages.slice(-200);
        }
        this._context.workspaceState.update(this._stateKey, this._messages);
    }

    private async handleUserMessage(text: string) {
        if (!this._view) { return; }

        if (text.startsWith("/")) {
            const parts = text.split(/\s+/);
            const cmd = parts[0].substring(1);
            const args = parts.slice(1).join(" ");
            await this.handleSlashCommand(cmd, args);
            return;
        }

        this.pushMessage("user", text);
        const client = getOrCreateClient();
        this.postStatus("Thinking...");

        try {
            const workspacePath = resolveWorkspaceRoot();
            const runId = await client.callTool("start_query", {
                prompt: text,
                workspace_path: workspacePath,
            });
            this._currentRunId = runId;

            if (runId === "cleared") {
                this._currentRunId = null;
                this.pushMessage("assistant", "Session history cleared.");
                this.postResponse("Session history cleared.");
                return;
            }

            // Start polling loop
            await this.pollRun(runId);
        } catch (err: unknown) {
            this._currentRunId = null;
            const msg = err instanceof Error ? err.message : String(err);
            const errText = `❌ **Error starting run:** ${msg}`;
            this.pushMessage("assistant", errText);
            this.postResponse(errText);
        }
    }

    private async handleInterruptRun() {
        if (!this._currentRunId) return;
        try {
            const client = getOrCreateClient();
            await client.callTool("interrupt_query", { run_id: this._currentRunId });
            this.pushMessage("assistant", "⚠️ Run interrupted by user.");
            this.postStatus("Interrupting...");
        } catch (err) {
            console.error("Failed to interrupt", err);
        }
    }

    private async pollRun(runId: string) {
        const client = getOrCreateClient();
        let isRunning = true;
        let lastLogLength = 0;

        while (isRunning) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            try {
                // Poll execution state
                const pollStr = await client.callTool("poll_query", { run_id: runId });
                const state = JSON.parse(pollStr);

                // Stream new logs to frontend status
                if (state.logs && state.logs.length > lastLogLength) {
                    const newLogs = state.logs.substring(lastLogLength);
                    // Send to webview to show in a streaming box (we'll implement this next)
                    this._view?.webview.postMessage({ type: "streamLog", text: newLogs });
                    lastLogLength = state.logs.length;
                }

                // Check for pending diffs to review
                const diffsStr = await client.callTool("get_pending_diffs", {});
                const diffs = JSON.parse(diffsStr);
                if (diffs && diffs.length > 0) {
                    for (const diff of diffs) {
                        this._view?.webview.postMessage({ type: "pendingDiff", diff });
                    }
                }

                // Poll artifacts and telemetry
                try {
                    const artifactsStr = await client.callTool("get_artifacts", {});
                    const telemetryStr = await client.callTool("get_telemetry_tree", {});
                    this._view?.webview.postMessage({ type: "artifacts", artifacts: JSON.parse(artifactsStr) });
                    this._view?.webview.postMessage({ type: "telemetry", tree: JSON.parse(telemetryStr) });
                } catch (e) {
                    // ignore if tools not ready
                }

                if (state.status === "completed" || state.status === "error") {
                    isRunning = false;
                    this._currentRunId = null;
                    const finalResponse = state.response || "Run finished with no output.";
                    this.pushMessage("assistant", finalResponse);
                    this.postResponse(finalResponse);
                }
            } catch (err) {
                console.error("Polling error", err);
                isRunning = false;
            }
        }
    }

    private async handleSlashCommand(command: string, args: string) {
        const client = getOrCreateClient();
        this.pushMessage("user", `/${command} ${args}`.trim());
        this.postStatus("Processing...");

        try {
            let result: string;
            switch (command) {
                case "agents":
                    result = await client.callTool("list_agents", {});
                    break;
                case "create": {
                    const parts = args.trim().split(/\s+/);
                    const name = parts[0];
                    const prompt = parts.slice(1).join(" ");
                    if (!name || !prompt) {
                        this.postResponse("⚠️ Usage: `/create <name> <system prompt>`");
                        return;
                    }
                    result = await client.callTool("create_agent", {
                        agent_name: name,
                        system_prompt: prompt,
                    });
                    break;
                }
                case "shutdown": {
                    if (!args.trim()) {
                        this.postResponse("⚠️ Usage: `/shutdown <agent_name>`");
                        return;
                    }
                    result = await client.callTool("shutdown_agent", { agent_name: args.trim() });
                    break;
                }
                case "reset":
                    result = await client.callTool("reset_system", {});
                    break;
                case "ask": {
                    const askParts = args.trim().split(/\s+/);
                    const agentName = askParts[0];
                    const task = askParts.slice(1).join(" ");
                    if (!agentName || !task) {
                        this.postResponse("⚠️ Usage: `/ask <agent_name> <prompt>`");
                        return;
                    }
                    result = await client.callTool("agent_query", {
                        prompt: task,
                        agent_name: agentName,
                    });
                    break;
                }
                case "clear":
                    this._messages = [];
                    this.persistMessages();
                    this._view?.webview.postMessage({ type: "clearChat" });
                    return;
                default:
                    this.postResponse(`Unknown command: \`/${command}\`. Try \`/agents\`, \`/create\`, \`/shutdown\`, \`/reset\`, \`/ask\`, \`/clear\`.`);
                    return;
            }
            this.pushMessage("assistant", result);
            this.postResponse(result);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            const errText = `❌ **Error:** ${msg}`;
            this.pushMessage("assistant", errText);
            this.postResponse(errText);
        }
    }

    private postResponse(text: string) {
        this._view?.webview.postMessage({ type: "response", text });
    }

    private postStatus(text: string) {
        this._view?.webview.postMessage({ type: "status", text });
    }
}

export function deactivate() {
    mcpClient?.dispose();
    mcpClient = null;
}
