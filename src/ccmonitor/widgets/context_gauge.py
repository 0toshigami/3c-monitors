"""Context window usage gauge widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from ccmonitor.widgets.styled_bar import StyledBar


class ContextGauge(Widget):
    """Visual gauge showing context window fill level."""

    DEFAULT_CSS = """
    ContextGauge {
        height: 1fr;
        padding: 0 2;
    }

    ContextGauge .gauge-title {
        text-style: bold;
        color: $text;
    }

    ContextGauge StyledBar {
        margin: 0 0 0 0;
    }

    ContextGauge .gauge-details {
        color: $text-muted;
    }

    ContextGauge .gauge-warning {
        color: $warning;
        text-style: bold;
    }

    ContextGauge .gauge-danger {
        color: $error;
        text-style: bold;
    }
    """

    context_used: reactive[int] = reactive(0)
    context_total: reactive[int] = reactive(200_000)
    model_name: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold $primary]\u25b6[/] [bold]Context Window[/]", classes="gauge-title")
            yield StyledBar(id="ctx-bar")
            yield Static("", id="ctx-details")

    def watch_context_used(self) -> None:
        self._update_display()

    def watch_context_total(self) -> None:
        self._update_display()

    def watch_model_name(self) -> None:
        self._update_display()

    def _update_display(self) -> None:
        try:
            bar = self.query_one("#ctx-bar", StyledBar)
            details = self.query_one("#ctx-details", Static)
        except NoMatches:
            return

        pct = (self.context_used / self.context_total * 100) if self.context_total > 0 else 0
        pct = min(100.0, pct)
        bar.percentage = pct

        used_k = self.context_used / 1000
        total_k = self.context_total / 1000
        remaining_k = max(0, total_k - used_k)

        model_str = f"  Model: {self.model_name}" if self.model_name else ""

        status = ""
        if pct >= 90:
            status = "  [bold #FF5555]\u26a0 CRITICAL[/]"
            details.set_classes("gauge-details gauge-danger")
        elif pct >= 70:
            status = "  [bold #FFB86C]\u25b2 WARNING[/]"
            details.set_classes("gauge-details gauge-warning")
        else:
            status = "  [#50FA7B]\u2713 OK[/]"
            details.set_classes("gauge-details")

        details.update(
            f"{used_k:,.1f}K / {total_k:,.1f}K tokens  |  "
            f"{remaining_k:,.1f}K remaining  |  "
            f"{pct:.1f}%{status}{model_str}"
        )
