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

    def show_status(self, message: str) -> None:
        self.update(f"[dim]{message}[/dim]")

    def show_error(self, message: str) -> None:
        self.update(f"[bold bright_red]{message}[/bold bright_red]")

    def set_verdict(self, verdict: str, fail_count: int, confidence: float) -> None:
        icons = {
            "APPROVED": "OK",
            "FLAGGED": "WARN",
            "BLOCKED": "BLOCK",
        }
        colors = {
            "APPROVED": "bright_green",
            "FLAGGED": "bright_yellow",
            "BLOCKED": "bright_red",
        }
        icon = icons.get(verdict, "INFO")
        color = colors.get(verdict, "white")
        label = f"{icon} VERDICT: {verdict} | Agents Failed: {fail_count}/5 | Confidence: {confidence:.0%}"
        self.update(f"[bold {color}]{label}[/bold {color}]")
