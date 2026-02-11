"""Main TUI application for Claude Code Monitor."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import DataTable, Footer, Static

from ccmonitor.collector import (
    PlanUsage,
    SessionData,
    collect_all_sessions,
    fetch_plan_usage,
    summarize_usage,
)
from ccmonitor.widgets.context_gauge import ContextGauge
from ccmonitor.widgets.cost_panel import CostPanel
from ccmonitor.widgets.plan_usage import PlanUsagePanel
from ccmonitor.widgets.rate_monitor import RateMonitor
from ccmonitor.widgets.session_list import SessionList
from ccmonitor.widgets.sparkline import TokenSparkline
from ccmonitor.widgets.usage_table import UsageTable


class HelpScreen(ModalScreen):
    """Help overlay showing keybindings."""

    BINDINGS = [  # noqa: RUF012
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Static {
        width: 50;
        height: auto;
        padding: 2 4;
        border: thick $primary;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]Claude Code Monitor - Help[/bold]\n"
            "\n"
            "  [bold]Key         Action[/bold]\n"
            "  q           Quit\n"
            "  r           Refresh data now\n"
            "  j / k       Navigate sessions\n"
            "  d           Toggle dark/light mode\n"
            "  ?           Show/close this help\n"
            "  Esc         Close this overlay\n"
            "\n"
            "  [bold]Session Filter[/bold]\n"
            "  Type in the filter box to search\n"
            "  sessions by project name or model.\n"
        )


class ClaudeCodeMonitor(App):
    """TUI for monitoring Claude Code context and usage limits."""

    TITLE = "Claude Code Monitor"
    SUB_TITLE = "Real-time context & usage tracking"

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 3;
        grid-columns: 1fr 2fr 1fr;
        grid-rows: auto 1fr auto;
        grid-gutter: 1;
    }

    #header-bar {
        column-span: 3;
        height: 3;
        background: $primary-background;
        color: $text;
        content-align: center middle;
        text-style: bold;
        padding: 1 2;
    }

    #sidebar-left {
        row-span: 1;
        border: solid $primary;
        height: 1fr;
    }

    #main-area {
        row-span: 1;
        border: solid $primary;
        height: 1fr;
    }

    #sidebar-right {
        row-span: 1;
        border: solid $primary;
        height: 1fr;
    }

    #footer-bar {
        column-span: 3;
        height: auto;
    }

    #ctx-gauge-box {
        height: 1fr;
        border-bottom: solid $primary;
    }

    #usage-table-box {
        height: 1fr;
        border-bottom: solid $primary;
    }

    #spark-box {
        height: 1fr;
    }

    #plan-box {
        height: auto;
        border-bottom: solid $primary;
    }

    #rate-box {
        height: auto;
        border-bottom: solid $primary;
    }

    #cost-box {
        height: auto;
    }

    #status-line {
        dock: bottom;
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 2;
    }
    """

    BINDINGS = [  # noqa: RUF012
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("j", "next_session", "Next Session"),
        Binding("k", "prev_session", "Prev Session"),
        Binding("d", "toggle_dark", "Toggle Dark"),
        Binding("question_mark", "show_help", "Help"),
    ]

    class PlanUsageLoaded(Message):
        """Posted when plan usage data is fetched from background thread."""

        def __init__(self, data: PlanUsage) -> None:
            self.data = data
            super().__init__()

    def __init__(self, claude_dir: Path | None = None, refresh_interval: float = 2.0):
        super().__init__()
        self.claude_dir = claude_dir
        self.refresh_interval = refresh_interval
        self._sessions: list[SessionData] = []
        self._selected_idx: int = 0
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Static(
            " Claude Code Monitor  |  Real-time Context & Usage Tracking",
            id="header-bar",
        )

        with Vertical(id="sidebar-left"):
            yield SessionList(id="session-list")

        with Vertical(id="main-area"):
            with Vertical(id="ctx-gauge-box"):
                yield ContextGauge(id="ctx-gauge")
            with Vertical(id="usage-table-box"):
                yield UsageTable(id="usage-table")
            with Vertical(id="spark-box"):
                yield TokenSparkline(id="sparkline")

        with VerticalScroll(id="sidebar-right"):
            with Vertical(id="plan-box"):
                yield PlanUsagePanel(id="plan-usage")
            with Vertical(id="rate-box"):
                yield RateMonitor(id="rate-monitor")
            with Vertical(id="cost-box"):
                yield CostPanel(id="cost-panel")

        yield Static("", id="status-line")
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()
        self._refresh_timer = self.set_interval(self.refresh_interval, self._auto_refresh)

    def _auto_refresh(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        """Load/reload all session data and update widgets."""
        # Remember selected session by ID so it survives reordering
        selected_session_id = None
        if self._sessions and self._selected_idx < len(self._sessions):
            selected_session_id = self._sessions[self._selected_idx].session_id

        self._sessions = collect_all_sessions(self.claude_dir)

        # Restore selection by session_id
        if selected_session_id:
            for i, s in enumerate(self._sessions):
                if s.session_id == selected_session_id:
                    self._selected_idx = i
                    break

        # Clamp index
        if self._sessions:
            self._selected_idx = min(self._selected_idx, len(self._sessions) - 1)

        # Update session list
        session_list = self.query_one("#session-list", SessionList)
        session_list.update_sessions(self._sessions, self._selected_idx)

        # Update summary
        summary = summarize_usage(self._sessions)
        cost_panel = self.query_one("#cost-panel", CostPanel)

        # Update selected session details
        if self._sessions and self._selected_idx < len(self._sessions):
            session = self._sessions[self._selected_idx]
            self._update_session_view(session)
            cost_panel.update_summary(summary, session.estimated_cost_usd)
        else:
            cost_panel.update_summary(summary)

        # Fetch plan usage in background (non-blocking)
        self._fetch_plan_usage_async()

        # Update status line
        status = self.query_one("#status-line", Static)
        status.update(
            f" {len(self._sessions)} sessions  |  "
            f"{summary.total_tokens:,} total tokens  |  "
            f"${summary.total_cost_usd:.4f}  |  "
            f"Auto-refresh: {self.refresh_interval}s"
        )

    def _update_session_view(self, session: SessionData) -> None:
        """Update all widgets for the selected session."""
        # Context gauge
        gauge = self.query_one("#ctx-gauge", ContextGauge)
        gauge.context_used = session.latest_context_used
        gauge.context_total = session.context_window_size
        gauge.model_name = session.model

        # Usage table
        usage_table = self.query_one("#usage-table", UsageTable)
        usage_table.update_data(
            input_tokens=session.total_input_tokens,
            output_tokens=session.total_output_tokens,
            cache_creation=session.total_cache_creation_tokens,
            cache_read=session.total_cache_read_tokens,
            cost=session.estimated_cost_usd,
            model=session.model,
        )

        # Sparkline
        sparkline = self.query_one("#sparkline", TokenSparkline)
        sparkline.update_data(session.messages)

        # Rate monitor
        rate_monitor = self.query_one("#rate-monitor", RateMonitor)
        rate_monitor.update_rates(session.messages)

    def on_session_list_session_selected(self, event: SessionList.SessionSelected) -> None:
        self._selected_idx = event.index
        if self._sessions and event.index < len(self._sessions):
            self._update_session_view(self._sessions[event.index])

    def action_refresh(self) -> None:
        self._load_data()
        self.notify("Data refreshed", timeout=1)

    def action_next_session(self) -> None:
        if self._sessions:
            self._selected_idx = (self._selected_idx + 1) % len(self._sessions)
            self._update_session_view(self._sessions[self._selected_idx])
            session_list = self.query_one("#session-list", SessionList)
            table = session_list.query_one("#session-dt", DataTable)
            table.move_cursor(row=self._selected_idx)

    def action_prev_session(self) -> None:
        if self._sessions:
            self._selected_idx = (self._selected_idx - 1) % len(self._sessions)
            self._update_session_view(self._sessions[self._selected_idx])
            session_list = self.query_one("#session-list", SessionList)
            table = session_list.query_one("#session-dt", DataTable)
            table.move_cursor(row=self._selected_idx)

    def action_toggle_dark(self) -> None:
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    @work(thread=True, exclusive=True, group="plan_usage")
    def _fetch_plan_usage_async(self) -> None:
        """Fetch plan usage in a background thread to avoid blocking the UI."""
        plan_data = fetch_plan_usage()
        self.post_message(self.PlanUsageLoaded(plan_data))

    def on_claude_code_monitor_plan_usage_loaded(self, event: PlanUsageLoaded) -> None:
        """Handle plan usage data arriving from background thread."""
        plan_usage_panel = self.query_one("#plan-usage", PlanUsagePanel)
        plan_usage_panel.update_usage(event.data)
