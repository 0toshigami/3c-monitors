"""Tests for ccmonitor.collector module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ccmonitor.collector import (
    MessageStats,
    SessionData,
    _get_model_family,
    discover_sessions,
    format_reset_time,
    parse_session,
    summarize_usage,
)

# --- _get_model_family ---


class TestGetModelFamily:
    def test_exact_family(self):
        assert _get_model_family("claude-opus-4") == "claude-opus-4"

    def test_versioned_model(self):
        assert _get_model_family("claude-opus-4-6") == "claude-opus-4"

    def test_sonnet(self):
        assert _get_model_family("claude-sonnet-4-5-20250929") == "claude-sonnet-4"

    def test_haiku(self):
        assert _get_model_family("claude-haiku-4-5-20251001") == "claude-haiku-4"

    def test_legacy_model(self):
        assert _get_model_family("claude-3-5-sonnet-20241022") == "claude-3-5-sonnet"

    def test_unknown_model_returns_as_is(self):
        assert _get_model_family("some-unknown-model") == "some-unknown-model"


# --- SessionData properties ---


class TestSessionData:
    def _make_session(self, **kwargs) -> SessionData:
        defaults = dict(
            session_id="test-123",
            project_path="-home-user-myproject",
            model="claude-sonnet-4-5-20250929",
            total_input_tokens=10_000,
            total_output_tokens=2_000,
            total_cache_creation_tokens=5_000,
            total_cache_read_tokens=3_000,
            latest_context_used=50_000,
            context_window_size=200_000,
        )
        defaults.update(kwargs)
        return SessionData(**defaults)

    def test_total_tokens(self):
        s = self._make_session()
        assert s.total_tokens == 12_000  # input + output

    def test_context_usage_pct(self):
        s = self._make_session(latest_context_used=100_000, context_window_size=200_000)
        assert s.context_usage_pct == 50.0

    def test_context_usage_pct_capped_at_100(self):
        s = self._make_session(latest_context_used=300_000, context_window_size=200_000)
        assert s.context_usage_pct == 100.0

    def test_context_usage_pct_zero_window(self):
        s = self._make_session(context_window_size=0)
        assert s.context_usage_pct == 0.0

    def test_estimated_cost_usd(self):
        s = self._make_session(
            model="claude-sonnet-4-5-20250929",
            total_input_tokens=1_000_000,
            total_output_tokens=1_000_000,
            total_cache_creation_tokens=0,
            total_cache_read_tokens=0,
        )
        # Sonnet 4: $3/M input + $15/M output = $18
        assert s.estimated_cost_usd == pytest.approx(18.0, rel=0.01)

    def test_tokens_per_minute_no_messages(self):
        s = self._make_session(messages=[])
        assert s.tokens_per_minute == 0.0

    def test_tokens_per_minute_single_message(self):
        s = self._make_session(
            messages=[MessageStats(timestamp="2025-01-01T00:00:00Z", model="claude-sonnet-4")]
        )
        assert s.tokens_per_minute == 0.0


# --- parse_session ---


class TestParseSession:
    def _write_session(self, tmp_dir: Path, lines: list[dict]) -> Path:
        projects = tmp_dir / "projects" / "-home-user-testproject"
        projects.mkdir(parents=True)
        jsonl_path = projects / "session-abc.jsonl"
        with open(jsonl_path, "w") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")
        return jsonl_path

    def test_parse_empty_session(self, tmp_path):
        jsonl_path = self._write_session(tmp_path, [])
        session = parse_session(jsonl_path)
        assert session.session_id == "session-abc"
        assert session.project_path == "-home-user-testproject"
        assert session.message_count == 0

    def test_parse_user_and_assistant_messages(self, tmp_path):
        lines = [
            {"type": "user", "timestamp": "2025-01-01T00:00:00Z"},
            {
                "type": "assistant",
                "timestamp": "2025-01-01T00:00:05Z",
                "message": {
                    "model": "claude-sonnet-4-5-20250929",
                    "usage": {
                        "input_tokens": 1000,
                        "output_tokens": 500,
                        "cache_creation_input_tokens": 200,
                        "cache_read_input_tokens": 100,
                    },
                },
            },
        ]
        jsonl_path = self._write_session(tmp_path, lines)
        session = parse_session(jsonl_path)

        assert session.message_count == 2
        assert session.user_message_count == 1
        assert session.assistant_message_count == 1
        assert session.total_input_tokens == 1000
        assert session.total_output_tokens == 500
        assert session.total_cache_creation_tokens == 200
        assert session.total_cache_read_tokens == 100
        assert session.model == "claude-sonnet-4-5-20250929"
        assert session.started_at == "2025-01-01T00:00:00Z"
        assert session.last_activity == "2025-01-01T00:00:05Z"
        assert len(session.messages) == 1  # only assistant messages tracked

    def test_parse_handles_malformed_json_lines(self, tmp_path):
        projects = tmp_path / "projects" / "-home-user-testproject"
        projects.mkdir(parents=True)
        jsonl_path = projects / "session-abc.jsonl"
        with open(jsonl_path, "w") as f:
            f.write('{"type": "user", "timestamp": "2025-01-01T00:00:00Z"}\n')
            f.write("this is not json\n")
            f.write('{"type": "user", "timestamp": "2025-01-01T00:01:00Z"}\n')

        session = parse_session(jsonl_path)
        assert session.message_count == 2  # skips bad line, counts the valid ones


# --- discover_sessions ---


class TestDiscoverSessions:
    def test_discover_sessions_empty(self, tmp_path):
        sessions = discover_sessions(tmp_path)
        assert sessions == []

    def test_discover_sessions_finds_jsonl(self, tmp_path):
        projects = tmp_path / "projects" / "myproject"
        projects.mkdir(parents=True)
        (projects / "session1.jsonl").write_text("")
        (projects / "session2.jsonl").write_text("")

        sessions = discover_sessions(tmp_path)
        assert len(sessions) == 2

    def test_discover_sessions_skips_subagents(self, tmp_path):
        projects = tmp_path / "projects" / "myproject"
        subagents = projects / "subagents"
        subagents.mkdir(parents=True)
        (projects / "session1.jsonl").write_text("")
        (subagents / "sub-session.jsonl").write_text("")

        sessions = discover_sessions(tmp_path)
        assert len(sessions) == 1


# --- summarize_usage ---


class TestSummarizeUsage:
    def test_empty_sessions(self):
        summary = summarize_usage([])
        assert summary.total_sessions == 0
        assert summary.total_tokens == 0

    def test_aggregates_tokens(self):
        sessions = [
            SessionData(
                session_id="a",
                project_path="p",
                total_input_tokens=100,
                total_output_tokens=50,
                message_count=5,
                model="claude-sonnet-4",
            ),
            SessionData(
                session_id="b",
                project_path="p",
                total_input_tokens=200,
                total_output_tokens=100,
                message_count=3,
                model="claude-opus-4",
            ),
        ]
        summary = summarize_usage(sessions)
        assert summary.total_sessions == 2
        assert summary.total_input_tokens == 300
        assert summary.total_output_tokens == 150
        assert summary.total_messages == 8
        assert summary.models_used == {"claude-sonnet-4", "claude-opus-4"}


# --- format_reset_time ---


class TestFormatResetTime:
    def test_empty_string(self):
        assert format_reset_time("") == ""

    def test_past_time(self):
        assert format_reset_time("2020-01-01T00:00:00+00:00") == "resetting..."

    def test_invalid_timestamp(self):
        assert format_reset_time("not-a-timestamp") == ""
