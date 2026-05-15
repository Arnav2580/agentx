import * as vscode from "vscode";

import { JurorDecorationProvider } from "./decorationProvider";
import { JurorClient } from "./jurorClient";
import { JurorSidebarProvider } from "./sidebarProvider";

export class JurorFileWatcher implements vscode.Disposable {
    private disposables: vscode.Disposable[] = [];
    private lastRun = 0;

    constructor(
        private readonly client: JurorClient,
        private readonly sidebarProvider: JurorSidebarProvider,
        private readonly decorationProvider: JurorDecorationProvider
    ) {}

    startWatching(): void {
        const saveDisposable = vscode.workspace.onDidSaveTextDocument(async (document) => {
            const now = Date.now();
            if (now - this.lastRun < 1500) {
                return;
            }
            this.lastRun = now;

            const text = document.getText();
            if (!text.trim() || text.length < 40) {
                return;
            }

            try {
                const verdict = await this.client.verify(text, "vscode-autoverify");
                this.sidebarProvider.showVerdict(verdict);

                const visibleEditor = vscode.window.visibleTextEditors.find(
                    (editor) => editor.document.uri.toString() === document.uri.toString()
                );
                if (visibleEditor) {
                    this.decorationProvider.applyDecorations(visibleEditor, verdict);
                }
            } catch {
                return;
            }
        });

        this.disposables.push(saveDisposable);
    }

    dispose(): void {
        this.disposables.forEach((disposable) => disposable.dispose());
        this.disposables = [];
    }
}
