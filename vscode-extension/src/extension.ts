import * as vscode from "vscode";

import { JurorClient } from "./jurorClient";
import { JurorDecorationProvider } from "./decorationProvider";
import { JurorFileWatcher } from "./fileWatcher";
import { JurorSidebarProvider } from "./sidebarProvider";
import { createJurorStatusBar } from "./statusBar";

export function activate(context: vscode.ExtensionContext): void {
    const client = new JurorClient();
    const sidebarProvider = new JurorSidebarProvider(context.extensionUri, client);
    const decorationProvider = new JurorDecorationProvider();
    const fileWatcher = new JurorFileWatcher(client, sidebarProvider, decorationProvider);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider("juror.panel", sidebarProvider)
    );

    context.subscriptions.push(
        vscode.commands.registerCommand("juror.openPanel", async () => {
            await sidebarProvider.reveal();
        }),
        vscode.commands.registerCommand("juror.verifySelection", async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage("Juror: Open an editor first.");
                return;
            }

            const selection = editor.selection;
            const content = editor.document.getText(selection).trim();
            if (!content) {
                vscode.window.showWarningMessage("Juror: Select text to verify.");
                return;
            }

            await runVerification(editor, content, client, sidebarProvider, decorationProvider, "vscode-selection");
        }),
        vscode.commands.registerCommand("juror.verifyFile", async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage("Juror: Open a file first.");
                return;
            }

            const content = editor.document.getText();
            await runVerification(editor, content, client, sidebarProvider, decorationProvider, "vscode-file");
        })
    );

    if (vscode.workspace.getConfiguration("juror").get("autoVerify")) {
        fileWatcher.startWatching();
        context.subscriptions.push(fileWatcher);
    }

    context.subscriptions.push(decorationProvider);
    context.subscriptions.push(createJurorStatusBar());
}

export function deactivate(): void {
    return;
}

async function runVerification(
    editor: vscode.TextEditor,
    content: string,
    client: JurorClient,
    sidebarProvider: JurorSidebarProvider,
    decorationProvider: JurorDecorationProvider,
    source: string
): Promise<void> {
    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: "AI Hallucination Juror: Verifying...",
            cancellable: false
        },
        async () => {
            try {
                const verdict = await client.verify(content, source);
                await sidebarProvider.reveal();
                sidebarProvider.showVerdict(verdict);
                decorationProvider.applyDecorations(editor, verdict);

                if (verdict.final_verdict === "BLOCKED") {
                    void vscode.window.showWarningMessage("Juror blocked this output and generated a correction.");
                }
            } catch (error) {
                const message = error instanceof Error ? error.message : "Unknown Juror error";
                sidebarProvider.showError(message);
                void vscode.window.showErrorMessage(`Juror: ${message}`);
            }
        }
    );
}
