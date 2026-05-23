import * as vscode from "vscode";

/**
 * Returns the full HTML for the MLX Chat webview panel,
 * loading the Vite/React frontend build from the dist directory.
 */
export function getChatHtml(webview: vscode.Webview, extensionUri: vscode.Uri): string {
    // Paths to the built assets
    const scriptUri = webview.asWebviewUri(
        vscode.Uri.joinPath(extensionUri, "webview-ui", "dist", "assets", "index.js")
    );
    const styleUri = webview.asWebviewUri(
        vscode.Uri.joinPath(extensionUri, "webview-ui", "dist", "assets", "index.css")
    );

    // Use a nonce to only allow specific scripts to run
    const nonce = getNonce();

    return /*html*/ `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <title>MLX Chat (Antigravity)</title>
    <link rel="stylesheet" type="text/css" href="${styleUri}">
</head>
<body>
    <div id="root"></div>
    <script type="module" nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
}

function getNonce() {
    let text = "";
    const possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
