"""Subscription plan usage widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Label, ProgressBar, Static

from ccmonitor.collector import PlanLimit, PlanUsage, format_reset_time


class PlanUsagePanel(Widget):
    """Display Claude Max subscription plan usage limits."""

    DEFAULT_CSS = """
    PlanUsagePanel {
        height: 1fr;
        padding: 0 2;
    }

    PlanUsagePanel .plan-title {
        text-style: bold;
        color: $text;
    }

    PlanUsagePanel .plan-label {
    }

    PlanUsagePanel .plan-reset {
        color: $text-muted;
    }

    PlanUsagePanel .plan-ok {
        color: $success;
    }

    PlanUsagePanel .plan-warn {
        color: $warning;
    }

    PlanUsagePanel .plan-danger {
        color: $error;
    }

    PlanUsagePanel .plan-error {
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Plan Usage", classes="plan-title")

            yield Static("5-Hour Session", id="plan-5h-label", classes="plan-label")
            yield ProgressBar(total=100, show_eta=False, show_percentage=True, id="plan-5h-bar")
            yield Static("", id="plan-5h-reset", classes="plan-reset")

            yield Static("Weekly (All Models)", id="plan-7d-label", classes="plan-label")
            yield ProgressBar(total=100, show_eta=False, show_percentage=True, id="plan-7d-bar")
            yield Static("", id="plan-7d-reset", classes="plan-reset")

            yield Static("Weekly (Sonnet)", id="plan-sonnet-label", classes="plan-label")
            yield ProgressBar(total=100, show_eta=False, show_percentage=True, id="plan-sonnet-bar")
            yield Static("", id="plan-sonnet-reset", classes="plan-reset")

            yield Static("Weekly (Opus)", id="plan-opus-label", classes="plan-label")
            yield ProgressBar(total=100, show_eta=False, show_percentage=True, id="plan-opus-bar")
            yield Static("", id="plan-opus-reset", classes="plan-reset")

            yield Static("", id="plan-status", classes="plan-error")

    def update_usage(self, usage: PlanUsage) -> None:
        """Update the plan usage display."""
        status = self.query_one("#plan-status", Static)

        if usage.error:
            status.update(f"  [dim]{usage.error}[/dim]")
            return

        if not usage.available:
            status.update("  No plan data available")
            return

        status.update("")

        self._update_limit(
            usage.five_hour,
            "#plan-5h-label",
            "#plan-5h-bar",
            "#plan-5h-reset",
        )
        self._update_limit(
            usage.seven_day,
            "#plan-7d-label",
            "#plan-7d-bar",
            "#plan-7d-reset",
        )

        self._update_limit(
            usage.seven_day_sonnet,
            "#plan-sonnet-label",
            "#plan-sonnet-bar",
            "#plan-sonnet-reset",
        )
        self._update_limit(
            usage.seven_day_opus,
            "#plan-opus-label",
            "#plan-opus-bar",
            "#plan-opus-reset",
        )

    def _update_limit(
        self,
        limit: PlanLimit | None,
        label_id: str,
        bar_id: str,
        reset_id: str,
    ) -> None:
        label = self.query_one(label_id, Static)
        bar = self.query_one(bar_id, ProgressBar)
        reset_label = self.query_one(reset_id, Static)

        if limit is None:
            bar.progress = 0
            reset_label.update("")
            return

        pct = min(100.0, limit.utilization)
        label.update(f"{limit.label}: {pct:.0f}%")
        bar.progress = pct

        reset_str = format_reset_time(limit.resets_at)
        if reset_str:
            reset_label.update(f"  Resets in {reset_str}")
        else:
            reset_label.update("")

        # Color the label based on usage
        if pct >= 80:
            label.set_classes("plan-label plan-danger")
        elif pct >= 50:
            label.set_classes("plan-label plan-warn")
        else:
            label.set_classes("plan-label plan-ok")
