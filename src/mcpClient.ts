import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import * as path from "path";

export type McpStatus = "disconnected" | "connecting" | "connected";

/**
 * Singleton MCP Client that manages the stdio connection to mlx_mcp_server.py.
 * The server is spawned as a child process and communicates over JSON-RPC.
 */
export class McpClient {
    private client: Client | null = null;
    private transport: StdioClientTransport | null = null;
    private connectionPromise: Promise<void> | null = null;
    private status: McpStatus = "disconnected";
    private onStatusChange: ((status: McpStatus) => void) | null = null;

    // Track the extension path dynamically set at activation
    public static extensionPath: string = "";

    private get serverRoot(): string {
        return McpClient.extensionPath || path.join(__dirname, "..");
    }

    private get serverScriptPath(): string {
        return path.join(this.serverRoot, "server", "mlx_mcp_server.py");
    }

    private get pythonPath(): string {
        return path.join(this.serverRoot, "server", ".venv", "bin", "python");
    }

    private get pythonPathEnv(): string {
        return path.join(this.serverRoot, "server");
    }

    constructor() {}

    public setStatusCallback(callback: (status: McpStatus) => void) {
        this.onStatusChange = callback;
        callback(this.status);
    }

    private updateStatus(newStatus: McpStatus) {
        this.status = newStatus;
        this.onStatusChange?.(newStatus);
    }

    /**
     * Connect to the MCP server by spawning the Python process.
     * Reuses existing connection if already connected.
     */
    async connect(): Promise<void> {
        if (this.connectionPromise) {
            return this.connectionPromise;
        }

        this.updateStatus("connecting");
        this.connectionPromise = (async () => {
            console.log("Connecting to MCP server at", this.serverScriptPath);
            try {
                this.transport = new StdioClientTransport({
                    command: this.pythonPath,
                    args: [this.serverScriptPath],
                    env: {
                        ...process.env,
                        "PYTHONPATH": this.pythonPathEnv,
                        "NO_COLOR": "1",
                        "TERM": "dumb"
                    }
                });

                // Capture stderr from the server process
                this.transport.onerror = (error) => {
                    console.error("MCP Transport Error:", error);
                    this.updateStatus("disconnected");
                };

                this.client = new Client(
                    { name: "mlx-chat-vscode", version: "0.1.0" },
                    { capabilities: {} }
                );

                await this.client.connect(this.transport);
                console.log("Successfully connected to MCP server.");
                this.updateStatus("connected");
            } catch (err) {
                console.error("Failed to connect to MCP server:", err);
                this.client = null;
                this.transport = null;
                this.connectionPromise = null;
                this.updateStatus("disconnected");
                throw err;
            }
        })();

        return this.connectionPromise;
    }

    /**
     * Call an MCP tool by name with the given arguments.
     * Automatically connects if not already connected.
     */
    async callTool(name: string, args: Record<string, unknown>, retries = 2): Promise<string> {
        try {
            await this.connect();

            if (!this.client) {
                throw new Error("MCP client failed to initialize");
            }

            const result = await this.client.callTool({ name, arguments: args });

            // Extract text content from the MCP response
            if (result.content && Array.isArray(result.content)) {
                return (result.content as Array<{ type: string; text?: string }>)
                    .filter((c) => c.type === "text")
                    .map((c) => c.text ?? "")
                    .join("\n");
            }

            return String(result.content ?? "No response");
        } catch (err: any) {
            console.error(`Error calling tool '${name}':`, err);
            
            // If we are "Not connected", it might be because the server restarted
            // Clear the connection and retry
            if (retries > 0 && (err.message?.includes("Not connected") || err.message?.includes("closed"))) {
                console.log(`Retrying tool call '${name}' (${retries} retries left)...`);
                await this.dispose();
                return this.callTool(name, args, retries - 1);
            }
            throw err;
        }
    }

    /**
     * List all available tools on the MCP server.
     */
    async listTools(retries = 2): Promise<string[]> {
        try {
            await this.connect();

            if (!this.client) {
                throw new Error("MCP client failed to initialize");
            }

            const result = await this.client.listTools();
            return result.tools.map((t) => t.name);
        } catch (err: any) {
            if (retries > 0 && (err.message?.includes("Not connected") || err.message?.includes("closed"))) {
                await this.dispose();
                return this.listTools(retries - 1);
            }
            throw err;
        }
    }

    /**
     * Gracefully disconnect from the MCP server.
     */
    async dispose(): Promise<void> {
        const client = this.client;
        const transport = this.transport;
        
        this.client = null;
        this.transport = null;
        this.connectionPromise = null;
        this.updateStatus("disconnected");

        if (client) {
            try {
                await client.close();
            } catch (e) {}
        }
        if (transport) {
            try {
                await transport.close();
            } catch (e) {}
        }
    }
}
