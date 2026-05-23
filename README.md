# 🤖 MLX Chat — Local AI Assistant for VS Code

[![VS Code Extension](https://img.shields.io/badge/VS%20Code-Extension-blue.svg)](https://code.visualstudio.com/)
[![Local AI](https://img.shields.io/badge/Local%20AI-Unified%20Memory-orange.svg)](https://github.com/ml-explore/mlx)
[![Built with FastMCP](https://img.shields.io/badge/MCP-FastMCP-green.svg)](https://modelcontextprotocol.io/)

A state-of-the-art, zero-latency, local AI pair-programming assistant in VS Code. It communicates directly with local LLMs (like Qwen 35B) running on **Apple Silicon** using an embedded **MLX Local Router MCP Server**.

---

## 🌟 Key Features

1. **Embedded Zero-Config Server**: The VS Code extension automatically manages, spawns, and connects to the local Python MCP server.
2. **Unified Apple Silicon Performance**: Harnesses MLX and Apple Silicon Unified Memory for extremely fast tokens-per-second generation.
3. **Advanced Local Agents**: Create, manage, and delegate tasks to custom subagents (using the dynamic Orchestrator Protocol).
4. **Local Telemetry & Diff Reviews**: View internal thoughts, step telemetry logs, and accept/reject code patches interactively directly inside the panel.

---

## 📦 How to Install (Hands-Free VSIX)

You don't need to build, compile, or run the extension from source. Simply download the pre-packaged installer:

1. Go to the **[GitHub Releases](https://github.com/rnewquist/mlx/releases)** page.
2. Download the latest `mlx-chat-0.2.0.vsix` package asset.
3. In VS Code, open the Extensions view (`Cmd+Shift+X` on Mac / `Ctrl+Shift+X` on Windows).
4. Click the `...` (More Actions) menu in the top-right corner of the Extensions panel.
5. Select **Install from VSIX...**.
6. Choose the downloaded `mlx-chat-0.2.0.vsix` file.
7. Click **Reload** to activate the **MLX Chat** sidebar panel!

---

## 🛠️ Developer Setup & Architecture

For developers looking to run or modify the codebase, the project is divided into two parts:

### 1. VS Code Extension (Root Directory)
Written in TypeScript and React. To make edits:
```bash
# Install extension packages
npm install

# Compile TypeScript
npm run compile
```

### 2. Python MCP Server (`server/`)
Consolidated under the `server/` directory, the backend is a FastMCP server driving `smolagents` and `MLXModel` integrations.

To set up or refresh your local server environment:
```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## ⚙️ Configuration & Models
The extension automatically looks for an active virtual environment in the `server/.venv/` directory.

- **Defaults**: The server defaults to the Apple Silicon-optimized `mlx-community/Qwen3.6-35B-A3B-4bit` model.
- **Model Registry**: You can dynamically add, update, remove, or switch Hugging Face models and custom LoRA adapters directly through the chat input interface.
