from textual.widgets import RichLog


class AIOutputPanel(RichLog):
    DEFAULT_CSS = """
    AIOutputPanel {
        background: #060a0f;
        color: #cbd5e1;
        border: solid #1e293b;
    }
    """

    def show_content(self, content: str) -> None:
        self.clear()
        self.write("[bold cyan]Content to verify:[/bold cyan]\n")
        self.write(content)
