import sqlite3

import pytest

from prompt_sentinel.audit import AuditStore
from prompt_sentinel.tool_policy import ToolPolicy, ToolRejected, ToolSpec


def test_allowlisted_tool_runs_and_audits_without_arguments(tmp_path):
    audit = AuditStore(tmp_path / "audit.db")
    executed = []
    registry = {
        "read_demo_page": ToolSpec(
            validate=lambda args: set(args) == {"page_id"} and args["page_id"] == "release_notes",
            execute=lambda args: executed.append(args["page_id"]) or "Page text",
        )
    }
    policy = ToolPolicy(frozenset({"read_demo_page"}), registry, audit)
    assert policy.run("read_demo_page", {"page_id": "release_notes"}, "request-1") == "Page text"
    assert executed == ["release_notes"]
    assert audit.tool_counts() == {"allow": 1}
    assert "release_notes" not in audit.path.read_bytes().decode("utf-8", errors="ignore")


def test_unknown_or_invalid_tool_never_executes(tmp_path):
    audit = AuditStore(tmp_path / "audit.db")
    executed = []
    registry = {
        "read_demo_page": ToolSpec(
            validate=lambda args: args == {"page_id": "release_notes"},
            execute=lambda args: executed.append(args) or "Page text",
        )
    }
    policy = ToolPolicy(frozenset({"read_demo_page"}), registry, audit)
    with pytest.raises(ToolRejected, match="tool_not_allowed"):
        policy.run("send_external", {"url": "https://example.org"}, "request-2")
    with pytest.raises(ToolRejected, match="invalid_arguments"):
        policy.run("read_demo_page", {"page_id": "../../secret"}, "request-2")
    assert executed == []
    assert audit.tool_counts() == {"deny": 2}


def test_existing_audit_database_is_migrated_without_removing_events(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.execute(
            """CREATE TABLE events (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL,
                request_id TEXT NOT NULL,
                source TEXT NOT NULL,
                provider TEXT NOT NULL,
                role TEXT NOT NULL,
                action TEXT NOT NULL,
                engines TEXT NOT NULL,
                rule_ids TEXT NOT NULL,
                similarity REAL,
                char_count INTEGER NOT NULL
            )"""
        )
        db.execute(
            """INSERT INTO events VALUES
            (1, '2026-01-01T00:00:00Z', 'old', 'demo', 'ollama', 'tool',
             'allow', '[]', '[]', NULL, 10)"""
        )
    audit = AuditStore(path)
    assert audit.recent()[0]["strategy"] == "both"
    assert audit.recent()[0]["checked_engines"] == []
    assert audit.counts() == {"allow": 1}
