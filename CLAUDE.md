# CLAUDE.md

Project context for AI-assisted development.

## What is this?

`ccmonitor` is a Python TUI (built with [Textual](https://textual.textualize.io/)) that monitors Claude Code sessions in real time. It reads JSONL session files from `~/.claude/projects/` and displays context usage, token consumption, costs, and subscription plan limits.

## Tech Stack

- **Python 3.10+**
- **Textual** — TUI framework
- **Rich** — terminal rendering (used in snapshot mode)
- **uv** — package manager
- **Hatchling** — build backend

## Key Files

- `src/ccmonitor/collector.py` — Core data logic: session parsing, cost calculation, OAuth token discovery, plan usage API calls. Most business logic lives here.
- `src/ccmonitor/app.py` — Main Textual app with grid layout, keybindings, and data refresh loop.
- `src/ccmonitor/widgets/` — One file per widget. Each widget is self-contained with its own CSS.
- `src/ccmonitor/__main__.py` — CLI entry point with argparse.

## Commands

```bash
# Run the app
ccmonitor

# Lint
uvx ruff check src/ tests/

# Format
uvx ruff format src/ tests/

# Type check
uvx mypy src/

# Run tests
pytest
```

## Conventions

- Use `ruff` for linting and formatting (config in `pyproject.toml`, line-length 100)
- Type hints encouraged but `disallow_untyped_defs` is off in mypy
- Widgets go in `src/ccmonitor/widgets/`, one per file
- Model pricing/context windows are defined as constants at the top of `collector.py`
- OAuth token discovery follows a specific priority order — see `_find_oauth_token()` docstring
- Session files are JSONL format located in `~/.claude/projects/<project-name>/<session-id>.jsonl`

## Architecture Notes

- The TUI uses a 3-column grid layout: session list (left), main metrics (center), plan/rate/cost (right)
- Data refresh happens on a timer (`set_interval`); plan usage is fetched in a background thread to avoid blocking the UI
- Cost estimates use published Anthropic pricing stored in `MODEL_PRICING` and `CACHE_PRICING` dicts
- The `_get_model_family()` function maps full model IDs (e.g., `claude-opus-4-6`) to pricing families (e.g., `claude-opus-4`)
