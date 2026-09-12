"""Unit tests for Kenbun OOM-Safe High-Efficiency Code Inspection & Task Harness."""

import json
import time
from pathlib import Path
import pytest

from tools.execution.oom_safe_harness import (
    ripgrep_search,
    view_file,
    write_to_file,
    spawn_background_task,
    get_background_task_status,
    kill_background_task,
    list_background_tasks,
)


def test_ripgrep_search_finds_query(tmp_path):
    """Verifies that ripgrep_search correctly searches files and returns structured matches."""
    sample_file = tmp_path / "sample.py"
    sample_file.write_text("def hello_world():\n    return 'secret_omega_token'\n")

    res_raw = ripgrep_search("secret_omega_token", search_path=str(tmp_path))
    res = json.loads(res_raw)

    assert res["count"] == 1
    assert "secret_omega_token" in res["results"][0]["content"]
    assert res["results"][0]["line"] == 2


def test_ripgrep_search_case_insensitivity(tmp_path):
    """Verifies case-insensitive matching."""
    sample_file = tmp_path / "case.txt"
    sample_file.write_text("HELLO CASE INSENSITIVE\n")

    res = json.loads(ripgrep_search("hello case", search_path=str(tmp_path), case_insensitive=True))
    assert res["count"] == 1


def test_ripgrep_search_missing_dir():
    """Verifies nonexistent path returns error dictionary safely without raising."""
    res = json.loads(ripgrep_search("anything", search_path="/nonexistent/random/path"))
    assert "error" in res


def test_view_file_slice(tmp_path):
    """Verifies surgical sliding-window line slicing."""
    test_file = tmp_path / "lines.txt"
    lines = [f"line number {i}" for i in range(1, 51)]
    test_file.write_text("\n".join(lines))

    out = view_file(str(test_file), start_line=10, end_line=15)
    assert "Lines: 10 to 15 of 50" in out
    assert "  10: line number 10" in out
    assert "  15: line number 15" in out
    assert "line number 9" not in out
    assert "line number 16" not in out


def test_view_file_max_lines_capping(tmp_path):
    """Verifies max_lines prevents dumping oversized chunks into context."""
    test_file = tmp_path / "huge.txt"
    lines = [f"entry {i}" for i in range(1, 200)]
    test_file.write_text("\n".join(lines))

    out = view_file(str(test_file), start_line=1, end_line=100, max_lines=20)
    assert "Lines: 1 to 20 of 199" in out


def test_view_file_symbols_only(tmp_path):
    """Verifies AST symbols extraction for outline mode."""
    py_file = tmp_path / "symbols.py"
    py_file.write_text(
        "class ModelGovernor:\n"
        "    '''Manages models.'''\n"
        "    def route(self):\n"
        "        pass\n\n"
        "def standalone_func():\n"
        "    '''Does something.'''\n"
        "    return 1\n"
    )

    out = json.loads(view_file(str(py_file), symbols_only=True))
    assert out["mode"] == "symbols_only"
    names = [s["name"] for s in out["symbols"]]
    assert "ModelGovernor" in names
    assert "route" in names
    assert "standalone_func" in names


def test_write_to_file_atomic(tmp_path):
    """Verifies write_to_file writes content atomically with directory creation."""
    dest = tmp_path / "sub" / "deep" / "output.txt"
    res = json.loads(write_to_file(str(dest), "hello world\nsecond line"))
    assert res["status"] == "success"
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == "hello world\nsecond line"


def test_spawn_and_poll_background_task(tmp_path, monkeypatch):
    """Verifies background subprocess spawning, logging, and status polling."""
    from tools.infrastructure.config import settings
    monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)

    spawn_res = json.loads(spawn_background_task("echo 'unit test harness task done'"))
    assert spawn_res["status"] == "spawned"
    task_id = spawn_res["task_id"]

    # Wait briefly for process to finish
    time.sleep(0.3)

    status_res = json.loads(get_background_task_status(task_id))
    assert status_res["status"] == "COMPLETED"
    assert any("unit test harness task done" in line for line in status_res.get("log_tail", []))


def test_kill_background_task(tmp_path, monkeypatch):
    """Verifies killing a running background task."""
    from tools.infrastructure.config import settings
    monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)

    spawn_res = json.loads(spawn_background_task("sleep 30"))
    task_id = spawn_res["task_id"]

    kill_res = json.loads(kill_background_task(task_id))
    assert kill_res["status"] in ("killed", "already_stopped")

    status_res = json.loads(get_background_task_status(task_id))
    assert status_res["status"] in ("KILLED", "COMPLETED")


def test_list_background_tasks(tmp_path, monkeypatch):
    """Verifies listing background tasks."""
    from tools.infrastructure.config import settings
    monkeypatch.setattr(settings, "BRAIN_HEALTH_DIR", tmp_path)

    spawn_background_task("echo 'task 1'")
    spawn_background_task("echo 'task 2'")
    time.sleep(0.2)

    list_res = json.loads(list_background_tasks(limit=5))
    assert list_res["total"] >= 2
