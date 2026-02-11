"""CLI entry point for Claude Code Monitor."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
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
    parser.add_argument(
        "--check-token",
        action="store_true",
        help="Debug OAuth token discovery and exit",
    )

    args = parser.parse_args()

    if args.check_token:
        _check_token()
        return

    if args.snapshot:
        _print_snapshot(args.claude_dir)
        return

    from ccmonitor.app import ClaudeCodeMonitor

    app = ClaudeCodeMonitor(
        claude_dir=args.claude_dir,
        refresh_interval=args.refresh,
    )
    app.run()


def _check_token() -> None:
    """Debug OAuth token discovery."""
    import json
    import os
    from pathlib import Path as P
    from ccmonitor.collector import _find_oauth_token, _call_usage_api

    print("=== OAuth Token Discovery Debug ===\n")

    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or str(P.home() / ".claude")
    creds_path = P(config_dir) / ".credentials.json"
    print(f"Home directory:     {P.home()}")
    print(f"Config directory:   {config_dir}")
    print(f"Credentials path:   {creds_path}")
    print(f"Credentials exists: {creds_path.exists()}")

    if creds_path.exists():
        import json
        try:
            creds = json.loads(creds_path.read_text())
            print(f"Credentials keys:   {list(creds.keys())}")
            for key in ("accessToken", "access_token", "refreshToken", "refresh_token"):
                val = creds.get(key)
                if val:
                    print(f"  {key}: {val[:20]}...({len(val)} chars)")
                else:
                    print(f"  {key}: not present")
        except Exception as e:
            print(f"Error reading credentials: {e}")

    print()
    token, diag = _find_oauth_token()
    if token:
        print(f"Token found: {token[:20]}...({len(token)} chars)")
        print("\nTesting API call...")
        result = _call_usage_api(token)
        import urllib.error
        if isinstance(result, urllib.error.HTTPError):
            print(f"API error: {result.code} {result.reason}")
        else:
            print(f"API success: {json.dumps(result, indent=2)}")
    else:
        print(f"No token found.")
        print(f"Diagnostics: {diag}")


def _print_snapshot(claude_dir: Path | None) -> None:
    """Print a text-based snapshot of current usage."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    from ccmonitor.collector import collect_all_sessions, fetch_plan_usage, format_reset_time, summarize_usage

    console = Console()
    sessions = collect_all_sessions(claude_dir)
    summary = summarize_usage(sessions)

    console.print()
    console.print(
        Panel(
            "[bold]Claude Code Usage Snapshot[/bold]",
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

    # Plan usage
    plan = fetch_plan_usage()
    if plan.available:
        plan_table = Table(title="Plan Usage", show_lines=True)
        plan_table.add_column("Limit", style="cyan")
        plan_table.add_column("Usage", justify="right")
        plan_table.add_column("Resets In", style="yellow")

        for limit in [plan.five_hour, plan.seven_day, plan.seven_day_sonnet, plan.seven_day_opus]:
            if limit is not None:
                style = "green" if limit.utilization < 50 else "yellow" if limit.utilization < 80 else "red"
                plan_table.add_row(
                    limit.label,
                    f"[{style}]{limit.utilization:.0f}%[/{style}]",
                    format_reset_time(limit.resets_at),
                )

        console.print(plan_table)
    elif plan.error:
        console.print(f"[dim]Plan Usage: {plan.error}[/dim]")

    console.print()


if __name__ == "__main__":
    main()
