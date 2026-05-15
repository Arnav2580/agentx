from textual.widgets import Static


class AgentCard(Static):
    DEFAULT_CSS = """
    AgentCard {
        border: solid #1e293b;
        background: #0b1220;
        color: #e2e8f0;
        padding: 1;
        margin-bottom: 1;
        height: auto;
    }
    """

    def set_state(self, agent_name: str, verdict: str, issues: list[str] | None = None) -> None:
        icon = {"PASS": "PASS", "FAIL": "FAIL", "UNCERTAIN": "WAIT"}.get(verdict, "WAIT")
        body = [f"[b]{icon} {agent_name}[/b]", f"Verdict: {verdict}"]
        for issue in (issues or [])[:2]:
            body.append(f"- {issue}")
        self.update("\n".join(body))
