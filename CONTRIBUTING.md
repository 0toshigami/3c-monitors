# Contributing to ccmonitor

Thanks for your interest in contributing! This document explains how to get started.

## Development Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/0toshigami/3c-monitors.git
   cd 3c-monitors
   ```

2. **Create a virtual environment and install**

   ```bash
   uv venv
   uv pip install -e ".[dev]"
   ```

   Or with pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

3. **Run the app**

   ```bash
   ccmonitor
   ```

## Code Quality

Before submitting a PR, please ensure your code passes these checks:

```bash
# Linting
uvx ruff check src/ tests/

# Formatting
uvx ruff format --check src/ tests/

# Type checking
uvx mypy src/

# Tests
pytest
```

## Project Structure

- `src/ccmonitor/` — main package
  - `collector.py` — data collection and API logic (most business logic lives here)
  - `app.py` — Textual TUI app and screen layout
  - `widgets/` — individual TUI widgets (gauge, sparkline, tables, etc.)
- `tests/` — test suite

## Submitting Changes

1. Fork the repository
2. Create a feature branch from `main`: `git checkout -b my-feature`
3. Make your changes
4. Run the linting and test checks above
5. Commit with a descriptive message (we loosely follow [Conventional Commits](https://www.conventionalcommits.org/)):
   - `feat: add export to CSV`
   - `fix: handle missing timestamp in session data`
   - `docs: update install instructions`
6. Push and open a Pull Request

## Reporting Issues

When filing a bug report, please include:

- Your OS and Python version
- Output of `ccmonitor --check-token` (redact any tokens)
- Steps to reproduce the issue
- Expected vs. actual behavior

## Adding a New Widget

1. Create a new file in `src/ccmonitor/widgets/`
2. Subclass `textual.widget.Widget`
3. Add CSS styles as `DEFAULT_CSS` in the class
4. Wire it into `app.py` — add it to `compose()` and update `_load_data()` / `_update_session_view()`
5. Add tests for any data processing logic
