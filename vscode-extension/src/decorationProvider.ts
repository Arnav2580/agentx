import * as vscode from "vscode";

import { VerificationResult } from "./jurorClient";

export class JurorDecorationProvider implements vscode.Disposable {
    private readonly blockedDecoration = vscode.window.createTextEditorDecorationType({
        isWholeLine: true,
        backgroundColor: "rgba(248, 113, 113, 0.08)",
        border: "1px solid rgba(248, 113, 113, 0.35)",
        overviewRulerColor: "rgba(248, 113, 113, 0.8)",
        overviewRulerLane: vscode.OverviewRulerLane.Right
    });

    private readonly flaggedDecoration = vscode.window.createTextEditorDecorationType({
        isWholeLine: true,
        backgroundColor: "rgba(251, 191, 36, 0.08)",
        border: "1px solid rgba(251, 191, 36, 0.35)",
        overviewRulerColor: "rgba(251, 191, 36, 0.8)",
        overviewRulerLane: vscode.OverviewRulerLane.Right
    });

    applyDecorations(editor: vscode.TextEditor, verdict: VerificationResult): void {
        editor.setDecorations(this.blockedDecoration, []);
        editor.setDecorations(this.flaggedDecoration, []);

        if (!verdict.issues_summary.length || verdict.final_verdict === "APPROVED") {
            return;
        }

        const ranges = verdict.issues_summary.slice(0, 3).map((issue, index) => {
            const line = Math.min(index, Math.max(0, editor.document.lineCount - 1));
            const range = editor.document.lineAt(line).range;
            return {
                range,
                hoverMessage: new vscode.MarkdownString(`**Juror warning**\n\n${issue}`)
            };
        });

        if (verdict.final_verdict === "BLOCKED") {
            editor.setDecorations(this.blockedDecoration, ranges);
        } else if (verdict.final_verdict === "FLAGGED") {
            editor.setDecorations(this.flaggedDecoration, ranges);
        }
    }

    dispose(): void {
        this.blockedDecoration.dispose();
        this.flaggedDecoration.dispose();
    }
}
