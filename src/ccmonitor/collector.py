"""Data collector for Claude Code session files."""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# Known context window sizes per model family
MODEL_CONTEXT_WINDOWS = {
    "claude-opus-4": 200_000,
    "claude-sonnet-4": 200_000,
    "claude-haiku-4": 200_000,
    "claude-3-5-sonnet": 200_000,
    "claude-3-5-haiku": 200_000,
    "claude-3-opus": 200_000,
    "claude-3-sonnet": 200_000,
    "claude-3-haiku": 200_000,
}

# Pricing per million tokens (input, output) in USD
MODEL_PRICING = {
    "claude-opus-4": (15.0, 75.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-haiku-4": (0.80, 4.0),
    "claude-3-5-sonnet": (3.0, 15.0),
    "claude-3-5-haiku": (0.80, 4.0),
    "claude-3-opus": (15.0, 75.0),
    "claude-3-sonnet": (3.0, 15.0),
    "claude-3-haiku": (0.25, 1.25),
}

# Cache pricing per million tokens (write, read) in USD
CACHE_PRICING = {
    "claude-opus-4": (18.75, 1.50),
    "claude-sonnet-4": (3.75, 0.30),
    "claude-haiku-4": (1.00, 0.08),
    "claude-3-5-sonnet": (3.75, 0.30),
    "claude-3-5-haiku": (1.00, 0.08),
    "claude-3-opus": (18.75, 1.50),
    "claude-3-sonnet": (3.75, 0.30),
    "claude-3-haiku": (0.30, 0.03),
}


def _get_model_family(model_id: str) -> str:
    """Extract model family from a full model ID like 'claude-opus-4-6'."""
    for family in MODEL_CONTEXT_WINDOWS:
        if model_id.startswith(family):
            return family
    # Fallback: try stripping trailing version numbers
    parts = model_id.split("-")
    for length in range(len(parts), 1, -1):
        candidate = "-".join(parts[:length])
        if candidate in MODEL_CONTEXT_WINDOWS:
            return candidate
    return model_id


@dataclass
class MessageStats:
    """Stats for a single API message."""
    timestamp: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    message_type: str = ""


@dataclass
class SessionData:
    """Aggregated data for a single session."""
    session_id: str
    project_path: str
    model: str = ""
    started_at: str = ""
    last_activity: str = ""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0
    message_count: int = 0
    user_message_count: int = 0
    assistant_message_count: int = 0
    messages: list[MessageStats] = field(default_factory=list)
    latest_context_used: int = 0
    context_window_size: int = 200_000
    file_path: str = ""
    file_size: int = 0
    file_mtime: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def context_usage_pct(self) -> float:
        if self.context_window_size == 0:
            return 0.0
        return min(100.0, (self.latest_context_used / self.context_window_size) * 100)

    @property
    def estimated_cost_usd(self) -> float:
        family = _get_model_family(self.model)
        input_price, output_price = MODEL_PRICING.get(family, (3.0, 15.0))
        cache_write_price, cache_read_price = CACHE_PRICING.get(family, (3.75, 0.30))

        cost = (
            (self.total_input_tokens / 1_000_000) * input_price
            + (self.total_output_tokens / 1_000_000) * output_price
            + (self.total_cache_creation_tokens / 1_000_000) * cache_write_price
            + (self.total_cache_read_tokens / 1_000_000) * cache_read_price
        )
        return cost

    @property
    def tokens_per_minute(self) -> float:
        if not self.messages or len(self.messages) < 2:
            return 0.0
        try:
            first_ts = self.messages[0].timestamp
            last_ts = self.messages[-1].timestamp
            # Timestamps are ISO format
            from datetime import datetime
            t0 = datetime.fromisoformat(first_ts)
            t1 = datetime.fromisoformat(last_ts)
            elapsed_min = (t1 - t0).total_seconds() / 60
            if elapsed_min <= 0:
                return 0.0
            return self.total_tokens / elapsed_min
        except (ValueError, TypeError):
            return 0.0


def find_claude_dir() -> Path:
    """Find the Claude Code data directory."""
    # Check common locations
    candidates = [
        Path.home() / ".claude",
        Path("/root/.claude"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path.home() / ".claude"


def discover_sessions(claude_dir: Path | None = None) -> list[Path]:
    """Find all session JSONL files."""
    if claude_dir is None:
        claude_dir = find_claude_dir()

    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return []

    sessions = []
    for jsonl_file in projects_dir.rglob("*.jsonl"):
        # Skip subagent files
        if "subagents" in str(jsonl_file):
            continue
        sessions.append(jsonl_file)

    # Sort by modification time, newest first
    sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions


def parse_session(jsonl_path: Path) -> SessionData:
    """Parse a session JSONL file into SessionData."""
    session_id = jsonl_path.stem
    project_path = jsonl_path.parent.name

    session = SessionData(
        session_id=session_id,
        project_path=project_path,
        file_path=str(jsonl_path),
        file_size=jsonl_path.stat().st_size,
        file_mtime=jsonl_path.stat().st_mtime,
    )

    try:
        with open(jsonl_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = entry.get("type", "")
                timestamp = entry.get("timestamp", "")

                if not session.started_at and timestamp:
                    session.started_at = timestamp
                if timestamp:
                    session.last_activity = timestamp

                session.message_count += 1

                if msg_type == "user":
                    session.user_message_count += 1
                elif msg_type == "assistant":
                    session.assistant_message_count += 1
                    message = entry.get("message", {})
                    model = message.get("model", "")
                    usage = message.get("usage", {})

                    if model:
                        session.model = model
                        family = _get_model_family(model)
                        session.context_window_size = MODEL_CONTEXT_WINDOWS.get(
                            family, 200_000
                        )

                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                    cache_creation = usage.get("cache_creation_input_tokens", 0)
                    cache_read = usage.get("cache_read_input_tokens", 0)

                    session.total_input_tokens += input_tokens
                    session.total_output_tokens += output_tokens
                    session.total_cache_creation_tokens += cache_creation
                    session.total_cache_read_tokens += cache_read

                    # Track latest context usage (input + cache = context filled)
                    context_used = input_tokens + cache_creation + cache_read
                    session.latest_context_used = context_used

                    stats = MessageStats(
                        timestamp=timestamp,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cache_creation_tokens=cache_creation,
                        cache_read_tokens=cache_read,
                        message_type=msg_type,
                    )
                    session.messages.append(stats)
    except (OSError, PermissionError):
        pass

    return session


def collect_all_sessions(claude_dir: Path | None = None) -> list[SessionData]:
    """Collect and parse all sessions."""
    paths = discover_sessions(claude_dir)
    sessions = []
    for path in paths:
        session = parse_session(path)
        sessions.append(session)
    return sessions


@dataclass
class UsageSummary:
    """Aggregate usage summary across sessions."""
    total_sessions: int = 0
    active_sessions: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cost_usd: float = 0.0
    total_messages: int = 0
    models_used: set[str] = field(default_factory=set)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens


@dataclass
class PlanLimit:
    """A single plan usage limit."""
    label: str
    utilization: float  # percentage 0-100
    resets_at: str  # ISO timestamp


@dataclass
class PlanUsage:
    """Subscription plan usage data from the OAuth API."""
    five_hour: PlanLimit | None = None
    seven_day: PlanLimit | None = None
    seven_day_sonnet: PlanLimit | None = None
    seven_day_opus: PlanLimit | None = None
    error: str = ""

    @property
    def available(self) -> bool:
        return self.five_hour is not None or self.seven_day is not None


def _find_oauth_token() -> str | None:
    """Find the Claude Code OAuth/session token.

    Discovery order:
    1. CCMONITOR_OAUTH_TOKEN env var (explicit override)
    2. CLAUDE_SESSION_INGRESS_TOKEN_FILE env var (set by Claude Code remote)
    3. CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR (fd passed by Claude Code)
    4. ~/.claude/.credentials.json (local Claude Code installation on Linux/WSL)
    5. Session ingress token files (remote/container environments)
    """
    # 1. Explicit override
    explicit = os.environ.get("CCMONITOR_OAUTH_TOKEN")
    if explicit:
        return explicit.strip()

    # 2. Token file env var (set by Claude Code for child processes)
    token_file = os.environ.get("CLAUDE_SESSION_INGRESS_TOKEN_FILE")
    if token_file:
        try:
            return Path(token_file).read_text().strip()
        except OSError:
            pass

    # 3. File descriptor (set by Claude Code process)
    fd_str = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR")
    if fd_str:
        try:
            fd = int(fd_str)
            with os.fdopen(os.dup(fd), "r") as f:
                token = f.read().strip()
                if token:
                    return token
        except (ValueError, OSError):
            pass

    # 4. Local credentials file (Linux/WSL plaintext storage)
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    creds_path = Path(config_dir) / ".credentials.json"
    try:
        creds = json.loads(creds_path.read_text())
        token = creds.get("accessToken") or creds.get("access_token")
        if token:
            return token
    except (OSError, json.JSONDecodeError, KeyError):
        pass

    # 5. Remote/container session ingress token files
    candidates = [
        Path.home() / ".claude" / "remote" / ".session_ingress_token",
        Path("/home/claude/.claude/remote/.session_ingress_token"),
        Path("/root/.claude/remote/.session_ingress_token"),
    ]
    for path in candidates:
        try:
            token = path.read_text().strip()
            if token:
                return token
        except OSError:
            continue

    return None


def fetch_plan_usage() -> PlanUsage:
    """Fetch subscription plan usage from the Anthropic OAuth API."""
    token = _find_oauth_token()
    if not token:
        return PlanUsage(
            error="No OAuth token found — run from within a Claude Code session, "
            "or set CCMONITOR_OAUTH_TOKEN"
        )

    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    url = f"{base_url}/api/oauth/usage"

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        return PlanUsage(error=str(e))

    result = PlanUsage()

    if data.get("five_hour"):
        result.five_hour = PlanLimit(
            label="5-Hour Session",
            utilization=data["five_hour"].get("utilization", 0),
            resets_at=data["five_hour"].get("resets_at", ""),
        )

    if data.get("seven_day"):
        result.seven_day = PlanLimit(
            label="Weekly (All Models)",
            utilization=data["seven_day"].get("utilization", 0),
            resets_at=data["seven_day"].get("resets_at", ""),
        )

    if data.get("seven_day_sonnet"):
        result.seven_day_sonnet = PlanLimit(
            label="Weekly (Sonnet)",
            utilization=data["seven_day_sonnet"].get("utilization", 0),
            resets_at=data["seven_day_sonnet"].get("resets_at", ""),
        )

    if data.get("seven_day_opus"):
        result.seven_day_opus = PlanLimit(
            label="Weekly (Opus)",
            utilization=data["seven_day_opus"].get("utilization", 0),
            resets_at=data["seven_day_opus"].get("resets_at", ""),
        )

    return result


def format_reset_time(resets_at: str) -> str:
    """Format a reset timestamp into a human-readable string."""
    if not resets_at:
        return ""
    try:
        reset_dt = datetime.fromisoformat(resets_at)
        now = datetime.now(timezone.utc)
        delta = reset_dt - now
        total_seconds = int(delta.total_seconds())
        if total_seconds <= 0:
            return "resetting..."
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        if days > 0:
            return f"{days}d {hours}h"
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except (ValueError, TypeError):
        return ""


def summarize_usage(sessions: list[SessionData]) -> UsageSummary:
    """Create an aggregate summary from all sessions."""
    summary = UsageSummary()
    summary.total_sessions = len(sessions)

    now = time.time()
    for session in sessions:
        summary.total_input_tokens += session.total_input_tokens
        summary.total_output_tokens += session.total_output_tokens
        summary.total_cache_creation_tokens += session.total_cache_creation_tokens
        summary.total_cache_read_tokens += session.total_cache_read_tokens
        summary.total_cost_usd += session.estimated_cost_usd
        summary.total_messages += session.message_count

        if session.model:
            summary.models_used.add(session.model)

        # Consider sessions active if modified in last hour
        if session.file_mtime and (now - session.file_mtime) < 3600:
            summary.active_sessions += 1

    return summary
