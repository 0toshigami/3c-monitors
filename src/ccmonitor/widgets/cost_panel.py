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
        height: 1fr;
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
            yield Label("[bold $primary]\u25b6[/] [bold]Usage Summary[/]", classes="cost-title")
            yield Static("$0.0000", id="cost-total", classes="cost-big")
            yield Static("", id="cost-details", classes="cost-details")

    def update_summary(self, summary: UsageSummary, session_cost: float = 0.0) -> None:
        total_label = self.query_one("#cost-total", Static)
        details = self.query_one("#cost-details", Static)

        total_label.update(f"[dim]Total:[/] [bold $success]${summary.total_cost_usd:.4f}[/]")

        models_str = ", ".join(sorted(summary.models_used)) if summary.models_used else "N/A"

        sep = "\u2500" * 20
        lines = [
            f"[dim]{sep}[/]",
            f"[bold]Sessions[/]  {summary.total_sessions}"
            f" [dim]([/]{summary.active_sessions} [#50FA7B]active[/][dim])[/]",
            f"[bold]Messages[/]  {summary.total_messages:,}",
            f"[bold]Input[/]     {summary.total_input_tokens:,} [dim]tokens[/]",
            f"[bold]Output[/]    {summary.total_output_tokens:,} [dim]tokens[/]",
            f"[bold]Cached[/]    {summary.total_cache_read_tokens:,} [dim]tokens[/]",
            f"[bold]Models[/]    {models_str}",
        ]

        if session_cost > 0:
            lines.append("")
            lines.append(f"[bold]Session[/]   [#FFB86C]${session_cost:.4f}[/]")

        details.update("\n".join(lines))
