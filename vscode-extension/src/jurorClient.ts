import * as vscode from "vscode";

export interface AgentResult {
    agent_id: number;
    agent_name: string;
    verdict: "PASS" | "FAIL" | "UNCERTAIN";
    confidence: number;
    issues: string[];
    reasoning: string;
}

export interface VerificationResult {
    request_id: string;
    domain: string;
    final_verdict: "APPROVED" | "FLAGGED" | "BLOCKED";
    overall_confidence: number;
    fail_count: number;
    agent_results: AgentResult[];
    issues_summary: string[];
    correction?: string;
    correction_diff?: string;
    execution_time_ms: number;
}

export class JurorClient {
    private get serverUrl(): string {
        return vscode.workspace.getConfiguration("juror").get<string>("serverUrl", "http://localhost:8000");
    }

    async verify(content: string, source = "vscode"): Promise<VerificationResult> {
        const response = await fetch(`${this.serverUrl}/verify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                content: content.substring(0, 8000),
                source
            })
        });

        if (!response.ok) {
            throw new Error(`Juror server error: ${response.status}`);
        }

        return response.json() as Promise<VerificationResult>;
    }

    async getHistory(limit = 10): Promise<{ history: unknown[]; count: number }> {
        const response = await fetch(`${this.serverUrl}/history?limit=${limit}`);
        if (!response.ok) {
            throw new Error(`Juror server error: ${response.status}`);
        }
        return response.json() as Promise<{ history: unknown[]; count: number }>;
    }

    async getStats(): Promise<Record<string, unknown>> {
        const response = await fetch(`${this.serverUrl}/stats`);
        if (!response.ok) {
            throw new Error(`Juror server error: ${response.status}`);
        }
        return response.json() as Promise<Record<string, unknown>>;
    }

    async checkHealth(): Promise<boolean> {
        try {
            const response = await fetch(`${this.serverUrl}/health`, {
                signal: AbortSignal.timeout(3000)
            });
            return response.ok;
        } catch {
            return false;
        }
    }
}
