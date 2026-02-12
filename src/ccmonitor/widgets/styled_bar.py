"""Custom styled progress bar using Unicode block characters."""

from __future__ import annotations

from rich.text import Text
from textual.app import RenderResult
from textual.reactive import reactive
from textual.widget import Widget

# Block characters for sub-cell resolution (empty to full)
FULL = "\u2588"
SEVEN_EIGHTHS = "\u2589"
THREE_QUARTERS = "\u258a"
FIVE_EIGHTHS = "\u258b"
HALF = "\u258c"
THREE_EIGHTHS = "\u258d"
QUARTER = "\u258e"
EIGHTH = "\u258f"
SHADE = "\u2591"

SUB_BLOCKS = [
    " ",
    EIGHTH,
    QUARTER,
    THREE_EIGHTHS,
    HALF,
    FIVE_EIGHTHS,
    THREE_QUARTERS,
    SEVEN_EIGHTHS,
    FULL,
]

# Default color stops: green -> amber -> red
DEFAULT_STOPS: list[tuple[float, str]] = [
    (0.0, "#50FA7B"),
    (50.0, "#50FA7B"),
    (70.0, "#FFB86C"),
    (90.0, "#FF5555"),
]

TRACK_COLOR = "#30363D"


class StyledBar(Widget):
    """A custom progress bar with color-shifting block characters."""

    DEFAULT_CSS = """
    StyledBar {
        height: 1;
        width: 1fr;
    }
    """

    percentage: reactive[float] = reactive(0.0)

    def __init__(
        self,
        color_stops: list[tuple[float, str]] | None = None,
        track_color: str = TRACK_COLOR,
        show_percentage: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._color_stops = color_stops or DEFAULT_STOPS
        self._track_color = track_color
        self._show_percentage = show_percentage

    def render(self) -> RenderResult:
        total_width = self.size.width
        if total_width <= 0:
            return ""

        pct = max(0.0, min(100.0, self.percentage))

        # Reserve space for percentage label if shown
        if self._show_percentage:
            pct_label = f" {pct:4.0f}%"
            bar_width = max(1, total_width - len(pct_label))
        else:
            pct_label = ""
            bar_width = total_width

        filled_exact = (pct / 100.0) * bar_width
        filled_full = int(filled_exact)
        remainder = filled_exact - filled_full
        sub_idx = int(remainder * 8)

        # Pick color based on percentage
        color = self._color_stops[0][1]
        for threshold, c in self._color_stops:
            if pct >= threshold:
                color = c

        text = Text()
        # Filled portion
        if filled_full > 0:
            text.append(FULL * filled_full, style=color)
        # Sub-block for fractional fill
        if sub_idx > 0 and filled_full < bar_width:
            text.append(SUB_BLOCKS[sub_idx], style=color)
            filled_full += 1
        # Track (unfilled)
        remaining = bar_width - filled_full
        if remaining > 0:
            text.append(SHADE * remaining, style=self._track_color)
        # Percentage label
        if self._show_percentage:
            text.append(pct_label, style="bold " + color)

        return text
