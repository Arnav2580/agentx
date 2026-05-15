"""
Textual TUI dashboard for AI Hallucination Juror.
"""

from datetime import datetime

import httpx
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Label, RichLog

from .widgets.ai_output_panel import AIOutputPanel
from .widgets.history_table import HistoryTable
from .widgets.verdict_panel import VerdictPanel


JUROR_URL = "http://localhost:8000"

AGENT_COLORS = {
    1: "bright_cyan",
    2: "bright_red",
    3: "bright_magenta",
    4: "bright_yellow",
    5: "bright_green",
}


class JurorApp(App):
    CSS = """
    Screen {
        background: #060a0f;
        color: #e2e8f0;
    }
    #main-panels {
        height: 1fr;
    }
    #left-panel, #right-panel {
        width: 1fr;
        border: solid #1e293b;
        padding: 1;
    }
    #left-title, #right-title {
        color: #94a3b8;
        margin-bottom: 1;
    }
    #jury-log {
        background: #060a0f;
        color: #cbd5e1;
        border: solid #1e293b;
    }
    HistoryTable {
        height: 12;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            with Horizontal(id="main-panels"):
                with Vertical(id="left-panel"):
                    yield Label("AI OUTPUT STREAM", id="left-title")
                    yield AIOutputPanel(id="ai-output", highlight=True, markup=True)
                with Vertical(id="right-panel"):
                    yield Label("JURY PANEL", id="right-title")
                    yield RichLog(id="jury-log", highlight=True, markup=True)
            yield VerdictPanel(id="verdict-bar")
            yield HistoryTable(id="history-table")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(AIOutputPanel).show_placeholder()
        self.query_one("#jury-log", RichLog).write("[dim]Jury panel is ready. Verification results will stream here.[/dim]")
        self.query_one(VerdictPanel).show_status("Waiting for verification...")
        self.load_history()

    @work(exclusive=False)
    async def verify_content(self, content: str, domain: str | None = None, source: str = "terminal") -> None:
        ai_log = self.query_one("#ai-output", AIOutputPanel)
        jury_log = self.query_one("#jury-log", RichLog)
        verdict_bar = self.query_one("#verdict-bar", VerdictPanel)

        ai_log.show_content(content[:1200] + ("..." if len(content) > 1200 else ""))
        jury_log.clear()
        jury_log.write("[bold yellow]JURY CONVENING...[/bold yellow]")
        jury_log.write("[dim]Running 5 agents in parallel...[/dim]\n")

        for agent_id, name in {
            1: "Fact Verifier",
            2: "Math Validator",
            3: "Standards Checker",
            4: "Logic Auditor",
            5: "Domain Expert",
        }.items():
            color = AGENT_COLORS.get(agent_id, "white")
            jury_log.write(f"[{color}]Agent {agent_id} ({name}): FIRING...[/{color}]")

        verdict_bar.show_status("Verifying...")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{JUROR_URL}/verify",
                    json={"content": content, "domain": domain, "source": source},
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            jury_log.write(f"\n[bright_red]Error: {exc}[/bright_red]")
            verdict_bar.show_error("Error connecting to Juror server")
            return

        jury_log.clear()
        jury_log.write("[bold]JURY VERDICT READY[/bold]\n")

        for agent in data.get("agent_results", []):
            verdict = agent["verdict"]
            color = "bright_green" if verdict == "PASS" else "bright_red" if verdict == "FAIL" else "yellow"
            icon = "PASS" if verdict == "PASS" else "FAIL" if verdict == "FAIL" else "WAIT"
            jury_log.write(f"[{color}]{icon} Agent {agent['agent_id']} ({agent['agent_name']}): {verdict}[/{color}]")
            for issue in agent.get("issues", [])[:2]:
                jury_log.write(f"  [dim]- {issue}[/dim]")
            jury_log.write("")

        issues_summary = data.get("issues_summary", [])[:4]
        if issues_summary:
            jury_log.write("[bold]Summary[/bold]")
            for issue in issues_summary:
                jury_log.write(f"  [dim]- {issue}[/dim]")

        final = data.get("final_verdict", "UNKNOWN")
        fail_count = int(data.get("fail_count", 0))
        confidence = float(data.get("overall_confidence", 0))
        verdict_bar.set_verdict(final, fail_count, confidence)

        if final == "BLOCKED" and data.get("correction"):
            ai_log.write("\n[bold bright_green]Corrected output (Agent 6):[/bold bright_green]")
            ai_log.write(data["correction"][:1200])

        self.refresh_history_row(data)

    def refresh_history_row(self, data: dict) -> None:
        table = self.query_one("#history-table", HistoryTable)
        table.add_history_row(
            datetime.now().strftime("%H:%M:%S"),
            data.get("domain", "?"),
            data.get("final_verdict", "?"),
            int(data.get("fail_count", 0)),
            "terminal",
        )

    @work(exclusive=False)
    async def load_history(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{JUROR_URL}/history?limit=5")
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return

        table = self.query_one("#history-table", HistoryTable)
        for entry in payload.get("history", []):
            table.add_history_row(
                entry.get("timestamp", "")[:19],
                entry.get("domain", ""),
                entry.get("final_verdict", ""),
                int(entry.get("fail_count", 0)),
                entry.get("source", ""),
            )


def run_tui() -> None:
    app = JurorApp()
    app.run()
