from rich.text import Text
from textual.widgets import DataTable


class HistoryTable(DataTable):
    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("Time", "Domain", "Verdict", "Fails", "Source")

    def add_history_row(self, timestamp: str, domain: str, verdict: str, fails: int, source: str) -> None:
        color = {"APPROVED": "green", "FLAGGED": "yellow", "BLOCKED": "red"}.get(verdict, "white")
        self.add_row(timestamp, domain, Text(verdict, style=f"bold {color}"), str(fails), source)
