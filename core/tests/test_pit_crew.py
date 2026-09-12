"""Unit tests for Kenbun Sovereign Pit Crew Specialists."""

import json
from unittest.mock import patch, MagicMock
import pytest

from tools.specialists.pit_crew import (
    consult_kenbun_mec,
    consult_kenbun_pit,
    consult_kenbun_dyno,
    consult_kenbun_wire,
    consult_kenbun_sec,
    consult_kenbun_doc,
)
from tools.infrastructure.agents import PERSONAS


def test_pit_crew_personas_registered():
    """Verifies that all 6 Pit Crew specialist personas are registered in the swarm."""
    expected_ids = ["kenbun-mec", "kenbun-pit", "kenbun-dyno", "kenbun-wire", "kenbun-sec", "kenbun-doc"]
    for pid in expected_ids:
        assert pid in PERSONAS
        p = PERSONAS[pid]
        assert p.id == pid
        assert len(p.allowed_tools) > 0
        assert len(p.system_prompt) > 0


def test_consult_kenbun_mec_with_mocked_llm():
    """Verifies that consult_kenbun_mec formats input, queries LM Studio, and returns structured diagnosis."""
    mock_response = "Root cause: tensioner pulley race condition on line 42."
    with patch("tools.specialists.pit_crew._call_lg_lmstudio", return_value=mock_response):
        res_raw = consult_kenbun_mec("Async worker hangs on shutdown")
        res = json.loads(res_raw)
        assert res["specialist"] == "kenbun-mec"
        assert res["status"] == "DIAGNOSED"
        assert "qwen2.5-coder-14b" in res["engine"]
        assert "line 42" in res["diagnosis"]


def test_consult_kenbun_mec_fallback_when_offline():
    """Verifies graceful fallback when LG 2025 is unreachable."""
    with patch("tools.specialists.pit_crew._call_lg_lmstudio", return_value=None):
        res_raw = consult_kenbun_mec("Database lock contention")
        res = json.loads(res_raw)
        assert res["specialist"] == "kenbun-mec"
        assert res["status"] == "FALLBACK_DIAGNOSIS"
        assert "Mechanic quick-scan" in res["diagnosis"]


def test_consult_kenbun_pit():
    """Verifies that consult_kenbun_pit reports cluster node states and recent background jobs."""
    res_raw = consult_kenbun_pit()
    res = json.loads(res_raw)
    assert res["specialist"] == "kenbun-pit"
    assert "cluster_nodes" in res
    assert "gpu_node" in res["cluster_nodes"]
    assert "Edge_Node" in res["cluster_nodes"]
    assert "macbook" in res["cluster_nodes"]
    assert "verdict" in res


def test_consult_kenbun_dyno():
    """Verifies that consult_kenbun_dyno reports Bayesian confidence and horsepower."""
    res_raw = consult_kenbun_dyno(tool_name="replace_file_content")
    res = json.loads(res_raw)
    assert res["specialist"] == "kenbun-dyno"
    assert "tool_confidence_curves" in res
    assert "replace_file_content" in res["tool_confidence_curves"]
    curve = res["tool_confidence_curves"]["replace_file_content"]
    assert "win_rate" in curve
    assert "alpha" in curve
    assert "beta" in curve


def test_consult_kenbun_wire():
    """Verifies that consult_kenbun_wire scans for FastMCP stdout framing isolation."""
    res_raw = consult_kenbun_wire()
    res = json.loads(res_raw)
    assert res["specialist"] == "kenbun-wire"
    assert "framing_check" in res
    assert "stray_stdout_prints" in res


def test_consult_kenbun_sec():
    """Verifies that consult_kenbun_sec checks Zero-Leak status."""
    res_raw = consult_kenbun_sec()
    res = json.loads(res_raw)
    assert res["specialist"] == "kenbun-sec"
    assert "zero_leak_status" in res
    assert "verdict" in res


def test_consult_kenbun_doc():
    """Verifies that consult_kenbun_doc queries post-mortems and archive."""
    res_raw = consult_kenbun_doc("telemetry")
    res = json.loads(res_raw)
    assert res["specialist"] == "kenbun-doc"
    assert "query" in res
    assert "verdict" in res
