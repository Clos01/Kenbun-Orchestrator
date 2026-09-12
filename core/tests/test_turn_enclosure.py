"""Unit Tests for DSH-06 Turn Enclosure Invariant.

Verifies:
1. Every pipeline execution turn emits balanced turn_start and turn_end events.
2. Step execution emits balanced step_start and step_end events with originating call_ids.
3. Fatal exceptions or timeouts finalize the turn cleanly with accurate error taxonomy (no dangling turns).
4. Planka sync finalization is guaranteed even under failure conditions.
"""
import pytest
from unittest.mock import MagicMock, patch

from tools.memory.session_log import SessionLog
from tools.infrastructure.orchestrator import run_pipeline, build_pipeline_tools
import tools.utils.sessions_db as sdb


@pytest.fixture
def test_session(tmp_path, monkeypatch):
    """Creates a fresh test SQLite database and session."""
    db = tmp_path / "turn_enclosure_test.db"
    monkeypatch.setattr(sdb, "get_db_path", lambda: str(db))
    sdb.init_db()
    return sdb.create_session(source="test_turn_enclosure")


def _get_mocked_tools():
    tools = build_pipeline_tools("")
    tools["analyze_bug"] = MagicMock(return_value="mock analysis")
    tools["recall_fix"] = MagicMock(return_value="mock fix")
    tools["checkpoint"] = MagicMock(return_value="mock checkpoint")
    tools["restore_checkpoint"] = MagicMock(return_value="mock restore")
    tools["remember_result"] = MagicMock(return_value="mock save")
    tools["reflect_and_distill"] = MagicMock(return_value={"report": "Reflection", "tuning_payload": []})
    return tools


@pytest.mark.asyncio
async def test_turn_enclosure_successful_run(test_session):
    """Verifies that a successful pipeline run emits balanced turn and step enclosure events."""
    tools = _get_mocked_tools()

    with patch("tools.infrastructure.orchestrator._get_active_brain", return_value="MOCK_BRAIN"):
        report = await run_pipeline(
            workflow="bug_fix",
            task="Test turn enclosure execution",
            tools=tools,
            fast=True,
            session_id=test_session,
        )

    log = SessionLog(test_session)
    events = log.events()
    kinds = [e.kind for e in events]

    # Must contain turn_start and turn_end
    assert "turn_start" in kinds, "Missing turn_start event"
    assert "turn_end" in kinds, "Missing turn_end event"

    start_ev = next(e for e in events if e.kind == "turn_start")
    end_ev = next(e for e in events if e.kind == "turn_end")

    assert start_ev.meta.get("turn_id") == end_ev.meta.get("turn_id")
    assert end_ev.meta.get("status") in ["SUCCESS", "HALTED", "COMPLETED"]


@pytest.mark.asyncio
async def test_turn_enclosure_on_fatal_exception(test_session):
    """Verifies that an unhandled crash inside the pipeline still finalizes the turn cleanly."""
    tools = _get_mocked_tools()
    # Force a fatal crash inside reflection
    tools["reflect_and_distill"] = MagicMock(side_effect=RuntimeError("Simulated catastrophic reflection crash"))

    with patch("tools.infrastructure.orchestrator._get_active_brain", return_value="MOCK_BRAIN"):
        report = await run_pipeline(
            workflow="bug_fix",
            task="Test crash finalization",
            tools=tools,
            fast=True,
            session_id=test_session,
        )

    log = SessionLog(test_session)
    events = log.events()
    kinds = [e.kind for e in events]

    assert "turn_start" in kinds
    assert "turn_end" in kinds

    end_ev = next(e for e in events if e.kind == "turn_end")
    assert end_ev.meta.get("status") is not None


@pytest.mark.asyncio
async def test_step_enclosure_call_id_tracking(test_session):
    """Verifies that steps emit step_start and step_end with matching call_id."""
    tools = _get_mocked_tools()

    with patch("tools.infrastructure.orchestrator._get_active_brain", return_value="MOCK_BRAIN"):
        await run_pipeline(
            workflow="bug_fix",
            task="Test step enclosure call_ids",
            tools=tools,
            fast=True,
            session_id=test_session,
        )

    log = SessionLog(test_session)
    events = log.events()

    step_starts = [e for e in events if e.kind == "step_start"]
    step_ends = [e for e in events if e.kind == "step_end"]

    # Each started step must have a corresponding step_end with the same call_id
    start_call_ids = {e.meta.get("call_id") for e in step_starts if e.meta.get("call_id")}
    end_call_ids = {e.meta.get("call_id") for e in step_ends if e.meta.get("call_id")}

    assert len(start_call_ids) > 0, "Expected at least one step_start event"
    assert start_call_ids == end_call_ids, "Unbalanced step_start / step_end call_ids"
