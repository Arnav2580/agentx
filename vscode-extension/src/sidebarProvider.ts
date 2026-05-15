import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

import { CommandCheckResult, JurorClient, VerificationResult } from "./jurorClient";

export class JurorSidebarProvider implements vscode.WebviewViewProvider {
    private view?: vscode.WebviewView;

    constructor(
        private readonly extensionUri: vscode.Uri,
        private readonly client: JurorClient
    ) {}

    public async reveal(): Promise<void> {
        if (this.view) {
            this.view.show?.(true);
            return;
        }
        await vscode.commands.executeCommand("workbench.view.extension.juror-sidebar");
    }

    public resolveWebviewView(webviewView: vscode.WebviewView): void {
        this.view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.extensionUri]
        };

        webviewView.webview.html = this.getHtml(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(async (message) => {
            if (message.command === "verify") {
                const editor = vscode.window.activeTextEditor;
                if (!editor) {
                    this.showError("Open a file or select text first.");
                    return;
                }

                const content = editor.document.getText(editor.selection) || editor.document.getText();
                try {
                    const verdict = await this.client.verify(content, "vscode-sidebar");
                    this.showVerdict(verdict);
                } catch (error) {
                    const messageText = error instanceof Error ? error.message : "Cannot connect to Juror server";
                    this.showError(messageText);
                }
                return;
            }

            if (message.command === "refreshCommands") {
                await this.postCommandHistory();
                return;
            }

            if (message.command === "checkCommand") {
                const command = await vscode.window.showInputBox({
                    prompt: "Enter a terminal command to inspect with Juror",
                    placeHolder: "npm install lodash"
                });
                if (!command?.trim()) {
                    return;
                }

                this.view?.webview.postMessage({ type: "command-check-loading", command });
                try {
                    const result = await this.client.checkCommand(command.trim(), "vscode_manual");
                    await this.postCommandCheck(command.trim(), result);
                    await this.postCommandHistory();
                } catch (error) {
                    const messageText = error instanceof Error ? error.message : "Cannot connect to Juror server";
                    this.view?.webview.postMessage({ type: "command-check-error", message: messageText });
                }
            }
        });

        void this.postHealth();
        void this.postCommandHistory();
    }

    public showVerdict(verdict: VerificationResult): void {
        this.view?.webview.postMessage({ type: "verdict", data: verdict });
    }

    public showLoading(message: string): void {
        this.view?.webview.postMessage({ type: "loading", message });
    }

    public showError(message: string): void {
        this.view?.webview.postMessage({ type: "error", message });
    }

    private async postHealth(): Promise<void> {
        const healthy = await this.client.checkHealth();
        this.view?.webview.postMessage({ type: "health", healthy });
    }

    private async postCommandHistory(): Promise<void> {
        try {
            const history = await this.client.getCommandHistory(8);
            this.view?.webview.postMessage({ type: "command-history", history: history.history });
        } catch {
            this.view?.webview.postMessage({ type: "command-history", history: [] });
        }
    }

    private async postCommandCheck(command: string, result: CommandCheckResult): Promise<void> {
        this.view?.webview.postMessage({ type: "command-check-result", command, data: result });
    }

    private getHtml(webview: vscode.Webview): string {
        const htmlPath = path.join(this.extensionUri.fsPath, "media", "sidebar.html");
        const htmlTemplate = fs.readFileSync(htmlPath, "utf-8");
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "media", "sidebar.css"));
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "media", "sidebar.js"));
        const nonce = String(Date.now());

        return htmlTemplate
            .replaceAll("{{styleUri}}", styleUri.toString())
            .replaceAll("{{scriptUri}}", scriptUri.toString())
            .replaceAll("{{cspSource}}", webview.cspSource)
            .replaceAll("{{nonce}}", nonce);
    }
}
