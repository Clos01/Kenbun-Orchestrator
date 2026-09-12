#!/usr/bin/env python3
"""
Tests for DeepSeek Harness Upstream Sentinel (dsh_sentinel.py)
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools.dsh.dsh_sentinel import DSHSentinel, DEFAULT_BASELINE_TAG


def test_dsh_sentinel_init():
    sentinel = DSHSentinel()
    assert sentinel.repo_root.exists()
    assert sentinel.get_tracked_baseline() is not None


def test_categorize_commits():
    sentinel = DSHSentinel()
    sample_commits = [
        {"hash": "abc1", "subject": "fix(session): audit historical carriers before V3 migration", "author": "Alice", "date": "2026-09-08"},
        {"hash": "abc2", "subject": "feat(agent-loop): turn-enclosure invariant + post-turn error model", "author": "Bob", "date": "2026-09-08"},
        {"hash": "abc3", "subject": "refactor(agent): back Inbox with a durable projection", "author": "Charlie", "date": "2026-09-08"},
        {"hash": "abc4", "subject": "feat(sandbox): native landlock support v0.1.2", "author": "Dave", "date": "2026-09-08"},
        {"hash": "abc5", "subject": "docs: add RFC 012 optional Code Mode for all tools", "author": "Eve", "date": "2026-09-08"},
        {"hash": "abc6", "subject": "refactor(agent): make runtime identity explicit", "author": "Frank", "date": "2026-09-08"},
        {"hash": "abc7", "subject": "chore: clean up trailing whitespace in readme", "author": "Grace", "date": "2026-09-08"},
    ]

    cats = sentinel.categorize_commits(sample_commits)
    assert len(cats["session_log_v3"]) == 1
    assert len(cats["turn_enclosure"]) == 1
    assert len(cats["durable_inbox"]) == 1
    assert len(cats["sandbox_security"]) == 1
    assert len(cats["code_mode"]) == 1
    assert len(cats["subagent_runtime"]) == 1
    assert len(cats["general_architecture"]) == 1


def test_generate_porting_recommendations():
    sentinel = DSHSentinel()
    sample_categories = {
        "session_log_v3": [{"hash": "1", "subject": "V3"}],
        "turn_enclosure": [{"hash": "2", "subject": "turn"}],
        "durable_inbox": [{"hash": "3", "subject": "inbox"}],
        "sandbox_security": [],
        "subagent_runtime": [],
        "code_mode": [{"hash": "4", "subject": "code mode"}],
        "general_architecture": [],
    }

    recs = sentinel.generate_porting_recommendations(sample_categories)
    assert len(recs) == 4
    seams = [r["seam"] for r in recs]
    assert any("Session Log V3" in s for s in seams)
    assert any("Turn Enclosure" in s for s in seams)
    assert any("Durable Inbox" in s for s in seams)
    assert any("CodeMode" in s for s in seams)


def test_audit_flow(tmp_path):
    sentinel = DSHSentinel(dsh_path=tmp_path)
    # If repo doesn't exist, audit should handle gracefully
    result = sentinel.audit(fetch=False)
    assert result["repo_available"] is False
    assert result["is_up_to_date"] is True
    assert result["total_new_commits"] == 0
