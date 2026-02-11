"""Session list sidebar widget."""

from __future__ import annotations

from datetime import datetime
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Label

from ccmonitor.collector import SessionData


class SessionList(Widget):
    """Sidebar showing available sessions."""

    DEFAULT_CSS = """
    SessionList {
        height: 1fr;
        padding: 1 1;
    }

    SessionList .session-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    SessionList DataTable {
        height: 1fr;
    }
    """

    class SessionSelected(Message):
        """Emitted when a session is selected."""
        def __init__(self, index: int) -> None:
            self.index = index
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._sessions: list[SessionData] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Sessions", classes="session-title")
            yield DataTable(id="session-dt")

    def on_mount(self) -> None:
        table = self.query_one("#session-dt", DataTable)
        table.add_columns("Project", "Model", "Messages", "Tokens", "Time")
        table.cursor_type = "row"
        table.zebra_stripes = True

    def update_sessions(self, sessions: list[SessionData]) -> None:
        self._sessions = sessions
        table = self.query_one("#session-dt", DataTable)
        table.clear()

        for session in sessions:
            project = session.project_path
            if project.startswith("-"):
                # Convert path format: -home-user-project -> ~/project
                parts = project.lstrip("-").split("-")
                if len(parts) >= 3 and parts[0] == "home":
                    project = "~/" + "-".join(parts[2:])
                else:
                    project = "/" + "/".join(parts)
            # Truncate
            if len(project) > 20:
                project = "..." + project[-17:]

            model = session.model
            if model:
                # Shorten: claude-opus-4-6 -> opus-4-6
                model = model.replace("claude-", "")
            if len(model) > 14:
                model = model[:14]

            msg_count = str(session.message_count)
            tokens = _format_tokens(session.total_tokens)

            time_str = ""
            if session.last_activity:
                try:
                    dt = datetime.fromisoformat(session.last_activity)
                    time_str = dt.strftime("%H:%M")
                except (ValueError, TypeError):
                    time_str = "?"

            table.add_row(project, model, msg_count, tokens, time_str)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.cursor_row < len(self._sessions):
            self.post_message(self.SessionSelected(event.cursor_row))


def _format_tokens(n: int) -> str:
    """Format token count for compact display."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)
