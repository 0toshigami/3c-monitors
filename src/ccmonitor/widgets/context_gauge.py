"""Context window usage gauge widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ProgressBar, Static


class ContextGauge(Widget):
    """Visual gauge showing context window fill level."""

    DEFAULT_CSS = """
    ContextGauge {
        height: auto;
        padding: 0 2;
    }

    ContextGauge .gauge-title {
        text-style: bold;
        color: $text;
    }

    ContextGauge .gauge-bar {
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
            yield Label("Context Window Usage", classes="gauge-title")
            yield ProgressBar(total=100, show_eta=False, show_percentage=True, id="ctx-bar")
            yield Static("", id="ctx-details")

    def watch_context_used(self) -> None:
        self._update_display()

    def watch_context_total(self) -> None:
        self._update_display()

    def watch_model_name(self) -> None:
        self._update_display()

    def _update_display(self) -> None:
        try:
            bar = self.query_one("#ctx-bar", ProgressBar)
            details = self.query_one("#ctx-details", Static)
        except NoMatches:
            return

        pct = (self.context_used / self.context_total * 100) if self.context_total > 0 else 0
        pct = min(100.0, pct)
        bar.progress = pct

        used_k = self.context_used / 1000
        total_k = self.context_total / 1000
        remaining_k = max(0, total_k - used_k)

        model_str = f"  Model: {self.model_name}" if self.model_name else ""

        status = ""
        if pct >= 90:
            status = "  [CRITICAL]"
            details.set_classes("gauge-details gauge-danger")
        elif pct >= 70:
            status = "  [WARNING]"
            details.set_classes("gauge-details gauge-warning")
        else:
            details.set_classes("gauge-details")

        details.update(
            f"{used_k:,.1f}K / {total_k:,.1f}K tokens  |  "
            f"{remaining_k:,.1f}K remaining  |  "
            f"{pct:.1f}%{status}{model_str}"
        )
