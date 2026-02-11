"""Session list sidebar widget."""

from __future__ import annotations

import time
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Input, Label

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

    SessionList Input {
        height: 3;
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
        self._filter_query: str = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Sessions (* = active)", classes="session-title")
            yield Input(placeholder="Filter sessions...", id="session-filter")
            yield DataTable(id="session-dt")

    def on_mount(self) -> None:
        table = self.query_one("#session-dt", DataTable)
        table.add_columns("Project", "Model", "Msgs", "Tokens", "Cost", "Time")
        table.cursor_type = "row"
        table.zebra_stripes = True

    def update_sessions(self, sessions: list[SessionData], selected_idx: int = 0) -> None:
        self._sessions = sessions
        self._rebuild_table(selected_idx)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter sessions as the user types."""
        self._filter_query = event.value.lower()
        self._rebuild_table()

    def _rebuild_table(self, selected_idx: int = 0) -> None:
        """Rebuild the session table, applying the current filter."""
        table = self.query_one("#session-dt", DataTable)
        table.clear()

        now = time.time()
        query = self._filter_query
        for session in self._sessions:
            # Apply filter
            if query and (
                query not in session.project_path.lower() and query not in session.model.lower()
            ):
                continue

            project = session.project_path
            if project.startswith("-"):
                # Convert path format: -home-user-project -> ~/project
                parts = project.lstrip("-").split("-")
                if len(parts) >= 3 and parts[0] == "home":
                    project = "~/" + "-".join(parts[2:])
                else:
                    project = "/" + "/".join(parts)
            # Truncate
            if len(project) > 19:
                project = "..." + project[-16:]

            # Active session indicator
            is_active = session.file_mtime and (now - session.file_mtime) < 3600
            if is_active:
                project = f"*{project}"

            model = session.model
            if model:
                # Shorten: claude-opus-4-6 -> opus-4-6
                model = model.replace("claude-", "")
            if len(model) > 14:
                model = model[:14]

            msg_count = str(session.message_count)
            tokens = _format_tokens(session.total_tokens)

            cost = session.estimated_cost_usd
            cost_str = f"${cost:.2f}" if cost >= 0.01 else f"${cost:.4f}"

            time_str = _format_local_time(session.last_activity) if session.last_activity else ""

            table.add_row(project, model, msg_count, tokens, cost_str, time_str)

        # Restore cursor position after rebuild
        if self._sessions and selected_idx < table.row_count:
            table.move_cursor(row=selected_idx)

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


def _format_local_time(iso_timestamp: str) -> str:
    """Format an ISO 8601 timestamp as local time."""
    try:
        # Python 3.10 fromisoformat() doesn't handle 'Z' suffix
        if iso_timestamp.endswith("Z"):
            iso_timestamp = iso_timestamp[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso_timestamp)
        dt = dt.astimezone()  # Convert to system local timezone
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OSError):
        return "?"
