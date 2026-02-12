"""Rate limit monitoring widget."""

from __future__ import annotations

import time as _time
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Label, ProgressBar, Static

from ccmonitor.collector import MessageStats


class RateMonitor(Widget):
    """Monitor and display API request rate and estimated limits."""

    DEFAULT_CSS = """
    RateMonitor {
        height: 1fr;
        padding: 0 2;
    }

    RateMonitor .rate-title {
        text-style: bold;
        color: $text;
    }

    RateMonitor .rate-ok {
        color: $success;
    }

    RateMonitor .rate-warn {
        color: $warning;
    }

    RateMonitor .rate-danger {
        color: $error;
    }

    RateMonitor .rate-details {
        color: $text-muted;
    }
    """

    # Known rate limits for Anthropic API (approximate)
    # These vary by tier; using reasonable defaults
    RPM_LIMIT = 50  # requests per minute
    TPM_INPUT_LIMIT = 40_000  # input tokens per minute
    TPM_OUTPUT_LIMIT = 8_000  # output tokens per minute

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._last_rate_alert: float = 0.0

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Rate Limits", classes="rate-title")
            yield Static("Requests/min", id="rpm-label")
            yield ProgressBar(total=100, show_eta=False, show_percentage=True, id="rpm-bar")
            yield Static("Input tokens/min", id="tpm-in-label")
            yield ProgressBar(total=100, show_eta=False, show_percentage=True, id="tpm-in-bar")
            yield Static("Output tokens/min", id="tpm-out-label")
            yield ProgressBar(total=100, show_eta=False, show_percentage=True, id="tpm-out-bar")
            yield Static("", id="rate-details", classes="rate-details")

    def update_rates(self, messages: list[MessageStats]) -> None:
        """Calculate current rates from recent messages."""
        rpm_bar = self.query_one("#rpm-bar", ProgressBar)
        tpm_in_bar = self.query_one("#tpm-in-bar", ProgressBar)
        tpm_out_bar = self.query_one("#tpm-out-bar", ProgressBar)
        details = self.query_one("#rate-details", Static)

        if not messages:
            rpm_bar.progress = 0
            tpm_in_bar.progress = 0
            tpm_out_bar.progress = 0
            details.update("  No recent activity")
            return

        # Analyze last 60 seconds of activity
        now = datetime.now()
        recent = []
        for m in reversed(messages):
            try:
                ts = datetime.fromisoformat(m.timestamp)
                if (now - ts).total_seconds() <= 60:
                    recent.append(m)
                else:
                    break
            except (ValueError, TypeError):
                continue

        rpm = len(recent)
        tpm_in = sum(m.input_tokens + m.cache_creation_tokens + m.cache_read_tokens for m in recent)
        tpm_out = sum(m.output_tokens for m in recent)

        rpm_pct = min(100, (rpm / self.RPM_LIMIT) * 100)
        tpm_in_pct = min(100, (tpm_in / self.TPM_INPUT_LIMIT) * 100)
        tpm_out_pct = min(100, (tpm_out / self.TPM_OUTPUT_LIMIT) * 100)

        rpm_bar.progress = rpm_pct
        tpm_in_bar.progress = tpm_in_pct
        tpm_out_bar.progress = tpm_out_pct

        # Update labels with current values
        rpm_label = self.query_one("#rpm-label", Static)
        tpm_in_label = self.query_one("#tpm-in-label", Static)
        tpm_out_label = self.query_one("#tpm-out-label", Static)

        rpm_label.update(f"Requests/min: {rpm}/{self.RPM_LIMIT}")
        tpm_in_label.update(f"Input tokens/min: {tpm_in:,}/{self.TPM_INPUT_LIMIT:,}")
        tpm_out_label.update(f"Output tokens/min: {tpm_out:,}/{self.TPM_OUTPUT_LIMIT:,}")

        max_pct = max(rpm_pct, tpm_in_pct, tpm_out_pct)
        if max_pct >= 80:
            status = "NEAR LIMIT - May experience throttling"
            cls = "rate-details rate-danger"
        elif max_pct >= 50:
            status = "Moderate usage"
            cls = "rate-details rate-warn"
        else:
            status = "Within limits"
            cls = "rate-details rate-ok"

        details.update(f"  {status}")
        details.set_classes(cls)

        # Proactive notification when near limits (once per minute max)
        now_ts = _time.time()
        if max_pct >= 80 and (now_ts - self._last_rate_alert) > 60:
            self._last_rate_alert = now_ts
            self.app.notify(
                "Rate limit warning: approaching API limits!",
                severity="warning",
                timeout=5,
            )
