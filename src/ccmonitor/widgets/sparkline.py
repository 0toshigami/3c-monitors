"""Token usage sparkline/bar chart widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Label, Static

from ccmonitor.collector import MessageStats

# Unicode block characters for bar rendering
BLOCKS = " \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"

# Color gradients for sparklines (threshold, hex_color)
INPUT_GRADIENT: list[tuple[float, str]] = [
    (0.0, "#30363D"),
    (0.15, "#00D4AA"),
    (0.6, "#FFB86C"),
    (0.85, "#FF6AC1"),
]

OUTPUT_GRADIENT: list[tuple[float, str]] = [
    (0.0, "#30363D"),
    (0.15, "#7B61FF"),
    (0.6, "#FF79C6"),
    (0.85, "#FF5555"),
]


class TokenSparkline(Widget):
    """Sparkline visualization of token usage over messages."""

    DEFAULT_CSS = """
    TokenSparkline {
        height: 1fr;
        padding: 0 2;
    }

    TokenSparkline .spark-title {
        text-style: bold;
        color: $text;
    }

    TokenSparkline .spark-input {
    }

    TokenSparkline .spark-output {
    }

    TokenSparkline .spark-legend {
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._chart_width: int = 60

    def on_resize(self, event) -> None:
        # Leave room for "  IN  " / "  OUT " prefix (6 chars) + padding (4 chars)
        self._chart_width = max(10, event.size.width - 10)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold $primary]\u25b6[/] [bold]Token History[/]", classes="spark-title")
            yield Static("", id="spark-input", classes="spark-input")
            yield Static("", id="spark-output", classes="spark-output")
            yield Static("", id="spark-legend", classes="spark-legend")

    def update_data(self, messages: list[MessageStats], width: int | None = None) -> None:
        width = width if width is not None else self._chart_width
        input_label = self.query_one("#spark-input", Static)
        output_label = self.query_one("#spark-output", Static)
        legend = self.query_one("#spark-legend", Static)

        if not messages:
            input_label.update("  [dim]No data yet[/]")
            output_label.update("")
            legend.update("")
            return

        # Get input and output token sequences
        input_vals = [
            m.input_tokens + m.cache_creation_tokens + m.cache_read_tokens for m in messages
        ]
        output_vals = [m.output_tokens for m in messages]

        # Downsample if needed
        input_vals = _downsample(input_vals, width)
        output_vals = _downsample(output_vals, width)

        input_spark = "  [bold #00D4AA]IN [/] " + _render_sparkline(input_vals, INPUT_GRADIENT)
        output_spark = "  [bold #7B61FF]OUT[/] " + _render_sparkline(output_vals, OUTPUT_GRADIENT)

        input_label.update(input_spark)
        output_label.update(output_spark)

        max_in = max(input_vals) if input_vals else 0
        max_out = max(output_vals) if output_vals else 0
        legend.update(
            f"  [#00D4AA]\u25a0[/] IN peak: {max_in:,}"
            f"  [#7B61FF]\u25a0[/] OUT peak: {max_out:,}"
            f"  [dim]{len(messages)} calls[/]"
        )


def _render_sparkline(
    values: list[int],
    gradient: list[tuple[float, str]] | None = None,
) -> str:
    """Render a list of values as a colorized sparkline string using Rich markup."""
    if not values:
        return ""
    max_val = max(values)
    if max_val == 0:
        color = gradient[0][1] if gradient else "#30363D"
        return f"[{color}]" + BLOCKS[0] * len(values) + "[/]"

    if gradient is None:
        gradient = INPUT_GRADIENT

    result = []
    for v in values:
        ratio = v / max_val
        idx = int(ratio * (len(BLOCKS) - 1))
        idx = min(idx, len(BLOCKS) - 1)

        # Pick color from gradient based on value ratio
        color = gradient[0][1]
        for threshold, c in gradient:
            if ratio >= threshold:
                color = c

        result.append(f"[{color}]{BLOCKS[idx]}[/]")

    return "".join(result)


def _downsample(values: list[int], target_len: int) -> list[int]:
    """Downsample a list of values to fit target length."""
    if len(values) <= target_len:
        return values

    step = len(values) / target_len
    result = []
    for i in range(target_len):
        start = int(i * step)
        end = int((i + 1) * step)
        chunk = values[start:end]
        result.append(max(chunk) if chunk else 0)
    return result
