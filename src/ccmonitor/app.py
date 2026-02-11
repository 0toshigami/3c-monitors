"""Main TUI application for Claude Code Monitor."""

from __future__ import annotations

from pathlib import Path
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.timer import Timer
from textual.widgets import Footer, Header, Static

from ccmonitor.collector import (
    SessionData,
    collect_all_sessions,
    fetch_plan_usage,
    find_claude_dir,
    summarize_usage,
)
from ccmonitor.widgets.context_gauge import ContextGauge
from ccmonitor.widgets.cost_panel import CostPanel
from ccmonitor.widgets.rate_monitor import RateMonitor
from ccmonitor.widgets.session_list import SessionList
from ccmonitor.widgets.sparkline import TokenSparkline
from ccmonitor.widgets.plan_usage import PlanUsagePanel
from ccmonitor.widgets.usage_table import UsageTable


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
        border: solid $primary;
        height: auto;
    }

    #usage-table-box {
        border: solid $primary;
        height: auto;
    }

    #spark-box {
        border: solid $primary;
        height: auto;
    }

    #rate-box {
        border: solid $primary;
        height: auto;
    }

    #cost-box {
        border: solid $primary;
        height: auto;
    }

    #plan-box {
        border: solid $primary;
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

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("j", "next_session", "Next Session"),
        Binding("k", "prev_session", "Prev Session"),
        Binding("d", "toggle_dark", "Toggle Dark"),
    ]

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

        with VerticalScroll(id="main-area"):
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
        self._refresh_timer = self.set_interval(
            self.refresh_interval, self._auto_refresh
        )

    def _auto_refresh(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        """Load/reload all session data and update widgets."""
        self._sessions = collect_all_sessions(self.claude_dir)

        # Update session list
        session_list = self.query_one("#session-list", SessionList)
        session_list.update_sessions(self._sessions)

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

        # Update plan usage
        plan_usage_panel = self.query_one("#plan-usage", PlanUsagePanel)
        plan_data = fetch_plan_usage()
        plan_usage_panel.update_usage(plan_data)

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

    def action_prev_session(self) -> None:
        if self._sessions:
            self._selected_idx = (self._selected_idx - 1) % len(self._sessions)
            self._update_session_view(self._sessions[self._selected_idx])

    def action_toggle_dark(self) -> None:
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"
