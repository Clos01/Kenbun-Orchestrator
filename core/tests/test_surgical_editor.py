"""Unit tests for Surgical Code Editor, Anti-Laziness Guardrail, and Ephemeral Isolation."""

import json
import subprocess
from pathlib import Path
import pytest

from tools.execution.surgical_editor import (
    replace_file_content,
    audit_execution_completeness,
    run_isolated_experiment,
)


def test_replace_file_content_exact_match(tmp_path):
    """Verifies that replace_file_content surgically modifies targeted lines without altering others."""
    f = tmp_path / "code.py"
    f.write_text("def alpha():\n    return 100\n\ndef beta():\n    return 200\n")

    res_raw = replace_file_content(
        file_path=str(f),
        target_content="    return 100",
        replacement_content="    return 999",
        create_backup=False,
    )
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert res["matches_replaced"] == 1

    content = f.read_text()
    assert "return 999" in content
    assert "return 100" not in content
    assert "def beta():\n    return 200" in content


def test_replace_file_content_with_line_range(tmp_path):
    """Verifies that line range restriction pinpoints the exact occurrence to modify."""
    f = tmp_path / "repeated.py"
    f.write_text(
        "val = 1\n"  # line 1
        "val = 1\n"  # line 2
        "val = 1\n"  # line 3
    )

    # Only replace line 2
    res_raw = replace_file_content(
        file_path=str(f),
        target_content="val = 1",
        replacement_content="val = 42",
        start_line=2,
        end_line=2,
        create_backup=False,
    )
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert res["matches_replaced"] == 1

    lines = f.read_text().splitlines()
    assert lines == ["val = 1", "val = 42", "val = 1"]


def test_replace_file_content_not_found(tmp_path):
    """Verifies error handling when target text is missing."""
    f = tmp_path / "sample.py"
    f.write_text("x = 10\n")

    res_raw = replace_file_content(
        file_path=str(f),
        target_content="x = 99",
        replacement_content="x = 100",
        create_backup=False,
    )
    res = json.loads(res_raw)
    assert res["status"] == "error"
    assert res["error_code"] == "TARGET_NOT_FOUND"


def test_replace_file_content_ambiguous_multiple_matches(tmp_path):
    """Verifies error when multiple matches exist without allow_multiple=True."""
    f = tmp_path / "multi.py"
    f.write_text("item = 1\nitem = 1\n")

    res_raw = replace_file_content(
        file_path=str(f),
        target_content="item = 1",
        replacement_content="item = 2",
        allow_multiple=False,
        create_backup=False,
    )
    res = json.loads(res_raw)
    assert res["status"] == "error"
    assert res["error_code"] == "AMBIGUOUS_MULTIPLE_MATCHES"


def test_replace_file_content_allow_multiple(tmp_path):
    """Verifies allow_multiple=True replaces all instances."""
    f = tmp_path / "multi.py"
    f.write_text("item = 1\nitem = 1\n")

    res_raw = replace_file_content(
        file_path=str(f),
        target_content="item = 1",
        replacement_content="item = 2",
        allow_multiple=True,
        create_backup=False,
    )
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert res["matches_replaced"] == 2
    assert f.read_text() == "item = 2\nitem = 2\n"


def test_replace_file_content_nonexistent_file():
    """Verifies safe error return when target file doesn't exist."""
    res_raw = replace_file_content(
        file_path="/tmp/nonexistent_surgical_test_file_xyz.py",
        target_content="foo",
        replacement_content="bar",
        create_backup=False,
    )
    res = json.loads(res_raw)
    assert res["status"] == "error"
    assert "File not found" in res["message"]


def test_audit_execution_completeness_approved():
    """Verifies that complete, fully-implemented code is approved."""
    clean_code = (
        "def compute_hash(data: str) -> str:\n"
        "    '''Computes SHA256 hex digest.'''\n"
        "    import hashlib\n"
        "    return hashlib.sha256(data.encode('utf-8')).hexdigest()\n"
    )
    res_raw = audit_execution_completeness(code_content=clean_code, task_objective="Implement hashing")
    res = json.loads(res_raw)
    assert res["verdict"] == "APPROVED"
    assert res["completeness_score"] == 1.0
    assert res["violations_count"] == 0


def test_audit_execution_completeness_catches_todo_and_stubs():
    """Verifies that lazy comments and stubs are flagged and blocked."""
    lazy_code = (
        "def process_payment(amount: float):\n"
        "    # TODO: implement real payment gateway integration later\n"
        "    # ... rest of code remains same\n"
        "    return True\n"
    )
    res_raw = audit_execution_completeness(code_content=lazy_code, task_objective="Process payment")
    res = json.loads(res_raw)
    assert res["verdict"] == "BLOCKED"
    assert res["violations_count"] >= 2
    reasons = [v["reason"] for v in res["violations"]]
    assert any("TODO" in r for r in reasons)
    assert any("Abbreviated" in r for r in reasons)


def test_audit_execution_completeness_catches_empty_pass():
    """Verifies that empty pass function bodies are blocked."""
    pass_code = (
        "def handle_webhook(event):\n"
        "    pass\n"
    )
    res_raw = audit_execution_completeness(code_content=pass_code)
    res = json.loads(res_raw)
    assert res["verdict"] == "BLOCKED"
    assert any("Empty function body" in v["reason"] for v in res["violations"])


def test_run_isolated_experiment_command():
    """Verifies that run_isolated_experiment executes commands in worktree and tears down."""
    res_raw = run_isolated_experiment(
        command="echo 'isolation_ok' > isolated_marker.txt && cat isolated_marker.txt",
        experiment_name="test_echo",
        auto_merge_on_success=False,
    )
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert res["exit_code"] == 0
    assert any("isolation_ok" in line for line in res["stdout_tail"])
    assert res["isolation_preserved"] is True


def test_replace_file_content_preserves_permissions(tmp_path):
    """Verifies that executable permissions are preserved after surgical replacement."""
    import os
    import stat

    script_file = tmp_path / "script.sh"
    script_file.write_text("#!/bin/bash\necho 'old_version'\n")
    # Make executable (0o755)
    script_file.chmod(0o755)

    res_raw = replace_file_content(
        file_path=str(script_file),
        target_content="old_version",
        replacement_content="new_version",
        create_backup=False,
    )
    res = json.loads(res_raw)
    assert res["status"] == "success"

    # Verify content and execution bit
    assert "new_version" in script_file.read_text()
    mode = script_file.stat().st_mode
    assert bool(mode & stat.S_IXUSR) is True

