import * as vscode from "vscode";

export function createJurorStatusBar(): vscode.StatusBarItem {
    const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    item.text = "$(shield) Juror";
    item.command = "juror.openPanel";
    item.tooltip = "AI Hallucination Juror";
    item.show();
    return item;
}
