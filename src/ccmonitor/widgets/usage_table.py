"""Token usage breakdown table widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Label, Static
from textual.containers import Vertical


class UsageTable(Widget):
    """Detailed token usage breakdown."""

    DEFAULT_CSS = """
    UsageTable {
        height: auto;
        padding: 1 2;
    }

    UsageTable .usage-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    UsageTable DataTable {
        height: auto;
        max-height: 12;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Token Usage Breakdown", classes="usage-title")
            yield DataTable(id="usage-dt")

    def on_mount(self) -> None:
        table = self.query_one("#usage-dt", DataTable)
        table.add_columns("Category", "Tokens", "Cost (USD)")
        table.cursor_type = "row"
        table.zebra_stripes = True

    def update_data(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_creation: int,
        cache_read: int,
        cost: float,
        model: str = "",
    ) -> None:
        table = self.query_one("#usage-dt", DataTable)
        table.clear()

        from ccmonitor.collector import _get_model_family, MODEL_PRICING, CACHE_PRICING

        family = _get_model_family(model) if model else ""
        input_price, output_price = MODEL_PRICING.get(family, (3.0, 15.0))
        cache_write_price, cache_read_price = CACHE_PRICING.get(family, (3.75, 0.30))

        input_cost = (input_tokens / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price
        cache_write_cost = (cache_creation / 1_000_000) * cache_write_price
        cache_read_cost = (cache_read / 1_000_000) * cache_read_price

        total_tokens = input_tokens + output_tokens + cache_creation + cache_read

        rows = [
            ("Input", f"{input_tokens:,}", f"${input_cost:.4f}"),
            ("Output", f"{output_tokens:,}", f"${output_cost:.4f}"),
            ("Cache Write", f"{cache_creation:,}", f"${cache_write_cost:.4f}"),
            ("Cache Read", f"{cache_read:,}", f"${cache_read_cost:.4f}"),
            ("", "", ""),
            ("TOTAL", f"{total_tokens:,}", f"${cost:.4f}"),
        ]

        for row in rows:
            table.add_row(*row)
