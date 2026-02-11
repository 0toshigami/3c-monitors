"""CLI entry point for Claude Code Monitor."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_REQUIRED_PACKAGES = {"textual": "textual>=1.0.0", "rich": "rich>=13.0.0"}


def _check_deps() -> None:
    """Check for required dependencies and offer to install them."""
    missing = []
    for module, pkg in _REQUIRED_PACKAGES.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)

    if not missing:
        return

    print(f"Missing dependencies: {', '.join(missing)}")
    print()
    install_cmd = [sys.executable, "-m", "pip", "install"] + missing
    print(f"Install with:\n  {' '.join(install_cmd)}")
    print()

    try:
        answer = input("Install now? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)

    if answer in ("", "y", "yes"):
        subprocess.check_call(install_cmd)
        print()
    else:
        sys.exit(1)


def main() -> None:
    _check_deps()
    parser = argparse.ArgumentParser(
        prog="ccmonitor",
        description="TUI for real-time monitoring of Claude Code context and usage limits",
    )
    parser.add_argument(
        "--claude-dir",
        type=Path,
        default=None,
        help="Path to Claude Code data directory (default: ~/.claude)",
    )
    parser.add_argument(
        "--refresh",
        type=float,
        default=2.0,
        help="Auto-refresh interval in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Print a one-time usage snapshot to stdout instead of launching TUI",
    )

    args = parser.parse_args()

    if args.snapshot:
        _print_snapshot(args.claude_dir)
        return

    from ccmonitor.app import ClaudeCodeMonitor

    app = ClaudeCodeMonitor(
        claude_dir=args.claude_dir,
        refresh_interval=args.refresh,
    )
    app.run()


def _print_snapshot(claude_dir: Path | None) -> None:
    """Print a text-based snapshot of current usage."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns

    from ccmonitor.collector import collect_all_sessions, summarize_usage

    console = Console()
    sessions = collect_all_sessions(claude_dir)
    summary = summarize_usage(sessions)

    console.print()
    console.print(
        Panel(
            f"[bold]Claude Code Usage Snapshot[/bold]",
            style="blue",
        )
    )

    # Summary table
    summary_table = Table(title="Overall Summary", show_lines=True)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")

    summary_table.add_row("Total Sessions", str(summary.total_sessions))
    summary_table.add_row("Active Sessions", str(summary.active_sessions))
    summary_table.add_row("Total Messages", f"{summary.total_messages:,}")
    summary_table.add_row("Input Tokens", f"{summary.total_input_tokens:,}")
    summary_table.add_row("Output Tokens", f"{summary.total_output_tokens:,}")
    summary_table.add_row("Cache Write", f"{summary.total_cache_creation_tokens:,}")
    summary_table.add_row("Cache Read", f"{summary.total_cache_read_tokens:,}")
    summary_table.add_row("Estimated Cost", f"${summary.total_cost_usd:.4f}")
    summary_table.add_row("Models", ", ".join(sorted(summary.models_used)) or "N/A")

    console.print(summary_table)
    console.print()

    # Per-session table
    if sessions:
        session_table = Table(title="Sessions", show_lines=True)
        session_table.add_column("Project", style="cyan")
        session_table.add_column("Model", style="yellow")
        session_table.add_column("Messages")
        session_table.add_column("Input", justify="right")
        session_table.add_column("Output", justify="right")
        session_table.add_column("Context %", justify="right")
        session_table.add_column("Cost", justify="right", style="green")

        for s in sessions:
            project = s.project_path
            if project.startswith("-"):
                parts = project.lstrip("-").split("-")
                if len(parts) >= 3 and parts[0] == "home":
                    project = "~/" + "-".join(parts[2:])

            session_table.add_row(
                project,
                s.model.replace("claude-", "") if s.model else "?",
                str(s.message_count),
                f"{s.total_input_tokens:,}",
                f"{s.total_output_tokens:,}",
                f"{s.context_usage_pct:.1f}%",
                f"${s.estimated_cost_usd:.4f}",
            )

        console.print(session_table)

    console.print()


if __name__ == "__main__":
    main()
