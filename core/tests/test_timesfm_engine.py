"""Tests for Google TimesFM-3 Time-Series Predictive Engine."""

import pytest
from pathlib import Path
from tools.strategy.timesfm_engine import TimesFMEngine, get_timesfm_engine, forecast_tool_pipeline


def test_timesfm_engine_init(tmp_path):
    test_db = tmp_path / "test_telemetry.db"
    engine = TimesFMEngine(db_path=test_db)
    assert test_db.exists()

    # Record invocation
    engine.record_invocation("scan_repo", "success", 120.5)
    engine.record_invocation("recall_fix", "success", 45.0)
    engine.record_invocation("save_checkpoint", "failure", 300.0)

    history = engine.get_invocation_history()
    assert len(history) == 3
    assert history[0]["tool_name"] == "scan_repo"


def test_timesfm_hazard_rate(tmp_path):
    test_db = tmp_path / "test_telemetry.db"
    engine = TimesFMEngine(db_path=test_db)
    engine.record_invocation("flaky_tool", "failure", 50.0)
    engine.record_invocation("flaky_tool", "success", 50.0)

    hazard = engine.estimate_hazard_rate("flaky_tool")
    assert hazard == 0.5


def test_timesfm_forecast_trajectory(tmp_path):
    test_db = tmp_path / "test_telemetry.db"
    engine = TimesFMEngine(db_path=test_db)
    traj = engine.forecast_trajectory(current_tool="scan_repo", horizon=3)
    assert len(traj) == 3
    assert traj[0]["predicted_tool"] in ["recall_fix", "save_checkpoint", "consult_supervisor"]


def test_forecast_tool_pipeline_wrapper():
    res_md = forecast_tool_pipeline("Fix memory leak in websocket server")
    assert "Google TimesFM-3 Dynamic Predictive Pipeline" in res_md
    assert "Synthesized Sequential Execution Trajectory" in res_md
    assert "scan_repo" in res_md
