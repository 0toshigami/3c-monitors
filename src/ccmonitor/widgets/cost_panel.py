"""Cost and summary panel widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Label, Static

from ccmonitor.collector import UsageSummary


class CostPanel(Widget):
    """Panel showing cost estimates and aggregate stats."""

    DEFAULT_CSS = """
    CostPanel {
        height: auto;
        padding: 0 2;
    }

    CostPanel .cost-title {
        text-style: bold;
        color: $text;
    }

    CostPanel .cost-value {
        color: $success;
        text-style: bold;
        text-align: center;
    }

    CostPanel .cost-big {
        color: $success;
        text-style: bold;
        text-align: center;
    }

    CostPanel .cost-details {
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Usage Summary", classes="cost-title")
            yield Static("$0.0000", id="cost-total", classes="cost-big")
            yield Static("", id="cost-details", classes="cost-details")

    def update_summary(self, summary: UsageSummary, session_cost: float = 0.0) -> None:
        total_label = self.query_one("#cost-total", Static)
        details = self.query_one("#cost-details", Static)

        total_label.update(f"Total: ${summary.total_cost_usd:.4f}")

        models_str = ", ".join(sorted(summary.models_used)) if summary.models_used else "N/A"

        lines = [
            f"Sessions:  {summary.total_sessions} ({summary.active_sessions} active)",
            f"Messages:  {summary.total_messages:,}",
            f"Input:     {summary.total_input_tokens:,} tokens",
            f"Output:    {summary.total_output_tokens:,} tokens",
            f"Cached:    {summary.total_cache_read_tokens:,} tokens",
            f"Models:    {models_str}",
        ]

        if session_cost > 0:
            lines.append("")
            lines.append(f"Session:   ${session_cost:.4f}")

        details.update("\n".join(lines))
