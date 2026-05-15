from textual.widgets import Static


class VerdictPanel(Static):
    DEFAULT_CSS = """
    VerdictPanel {
        height: 5;
        border: solid #1e293b;
        background: #08111d;
        content-align: center middle;
        color: #cbd5e1;
        padding: 1;
    }
    """

    def set_verdict(self, verdict: str, fail_count: int, confidence: float) -> None:
        label = f"VERDICT: {verdict} | Agents Failed: {fail_count}/5 | Confidence: {confidence:.0%}"
        self.update(f"[b]{label}[/b]")
