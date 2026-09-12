"""Unit tests for Kenbun Functional Sovereign Specialists."""

import json
from unittest.mock import patch
import pytest

from tools.specialists.pit_crew import (
    consult_code_diagnostician,
    consult_cluster_monitor,
    consult_performance_tuner,
    consult_framing_sentinel,
    consult_leak_sentinel,
    consult_memory_archivist,
)
from tools.infrastructure.agents import PERSONAS


def test_specialist_personas_registered():
    """Verifies that all functional specialist personas are registered in the swarm."""
    expected_ids = [
        "code-diagnostician",
        "cluster-monitor",
        "performance-tuner",
        "framing-sentinel",
        "leak-sentinel",
        "memory-archivist",
    ]
    for pid in expected_ids:
        assert pid in PERSONAS
        p = PERSONAS[pid]
        assert p.id == pid
        assert len(p.allowed_tools) > 0
        assert len(p.system_prompt) > 0


def test_consult_code_diagnostician_with_mocked_llm():
    """Verifies that consult_code_diagnostician formats input, queries LM Studio, and returns structured diagnosis."""
    mock_response = "Root cause: tensioner race condition on line 42."
    with patch("tools.specialists.pit_crew._call_lg_lmstudio", return_value=mock_response):
        res_raw = consult_code_diagnostician("Async worker hangs on shutdown")
        res = json.loads(res_raw)
        assert res["specialist"] == "code-diagnostician"
        assert res["status"] == "DIAGNOSED"
        assert "qwen2.5-coder-14b" in res["engine"]
        assert "line 42" in res["diagnosis"]


def test_consult_code_diagnostician_fallback_when_offline():
    """Verifies graceful fallback when LG 2025 is unreachable."""
    with patch("tools.specialists.pit_crew._call_lg_lmstudio", return_value=None):
        res_raw = consult_code_diagnostician("Database lock contention")
        res = json.loads(res_raw)
        assert res["specialist"] == "code-diagnostician"
        assert res["status"] == "FALLBACK_DIAGNOSIS"
        assert "Diagnostic quick-scan" in res["diagnosis"]


def test_consult_cluster_monitor():
    """Verifies that consult_cluster_monitor reports cluster node states and recent background jobs."""
    res_raw = consult_cluster_monitor()
    res = json.loads(res_raw)
    assert res["specialist"] == "cluster-monitor"
    assert "cluster_nodes" in res
    assert "gpu_node" in res["cluster_nodes"]
    assert "Edge_Node" in res["cluster_nodes"]
    assert "macbook" in res["cluster_nodes"]
    assert "verdict" in res


def test_consult_performance_tuner():
    """Verifies that consult_performance_tuner reports Bayesian confidence and horsepower."""
    res_raw = consult_performance_tuner(tool_name="replace_file_content")
    res = json.loads(res_raw)
    assert res["specialist"] == "performance-tuner"
    assert "tool_confidence_curves" in res
    assert "replace_file_content" in res["tool_confidence_curves"]
    curve = res["tool_confidence_curves"]["replace_file_content"]
    assert "win_rate" in curve
    assert "alpha" in curve
    assert "beta" in curve


def test_consult_framing_sentinel():
    """Verifies that consult_framing_sentinel scans for FastMCP stdout framing isolation."""
    res_raw = consult_framing_sentinel()
    res = json.loads(res_raw)
    assert res["specialist"] == "framing-sentinel"
    assert "framing_check" in res
    assert "stray_stdout_prints" in res


def test_consult_leak_sentinel():
    """Verifies that consult_leak_sentinel checks Zero-Leak status."""
    res_raw = consult_leak_sentinel()
    res = json.loads(res_raw)
    assert res["specialist"] == "leak-sentinel"
    assert "zero_leak_status" in res
    assert "verdict" in res


def test_consult_memory_archivist():
    """Verifies that consult_memory_archivist queries post-mortems and archive."""
    res_raw = consult_memory_archivist("telemetry")
    res = json.loads(res_raw)
    assert res["specialist"] == "memory-archivist"
    assert "query" in res
    assert "verdict" in res


def test_specialists_bang_dispatcher():
    """Verifies that all 6 functional specialist directives dispatch cleanly via ! commands."""
    from tools.strategy.bang_dispatcher import dispatch_bang_command

    # 1. !diagnose
    with patch("tools.specialists.pit_crew._call_lg_lmstudio", return_value="Mocked diagnosis"):
        res = dispatch_bang_command("!diagnose 'WebSocket EOF race condition'")
        parsed = json.loads(res)
        assert parsed["specialist"] == "code-diagnostician"
        assert parsed["status"] == "DIAGNOSED"

    # 2. !cluster
    res = dispatch_bang_command("!cluster")
    parsed = json.loads(res)
    assert parsed["specialist"] == "cluster-monitor"
    assert "cluster_nodes" in parsed

    # 3. !perf
    res = dispatch_bang_command("!perf replace_file_content")
    parsed = json.loads(res)
    assert parsed["specialist"] == "performance-tuner"

    # 4. !protocol
    res = dispatch_bang_command("!protocol")
    parsed = json.loads(res)
    assert parsed["specialist"] == "framing-sentinel"

    # 5. !leak_audit
    res = dispatch_bang_command("!leak_audit")
    parsed = json.loads(res)
    assert parsed["specialist"] == "leak-sentinel"

    # 6. !history
    res = dispatch_bang_command("!history telemetry")
    parsed = json.loads(res)
    assert parsed["specialist"] == "memory-archivist"


def test_specialists_pipeline_registry():
    """Verifies that all functional specialist pipelines and aliases are registered in the orchestrator."""
    from tools.infrastructure.orchestrator import registry

    expected_pipelines = [
        "code_diagnosis", "diagnose",
        "cluster_health", "cluster",
        "performance_tuning", "performance", "perf",
        "protocol_framing", "protocol",
        "zero_leak_audit", "leak_audit",
        "memory_archive", "history",
    ]
    registered = registry.get_all_pipelines()
    for name in expected_pipelines:
        assert name in registered, f"Pipeline '{name}' not found in orchestrator registry"


def test_specialists_dynamic_configuration(monkeypatch):
    """Verifies that host and port configuration dynamically responds to environment variables."""
    monkeypatch.setenv("P330_IP_ADDRESS", "192.168.1.99")
    monkeypatch.setenv("P330_OLLAMA_PORT", "11435")
    monkeypatch.setenv("MACBOOK_IP", "192.168.1.88")

    res_raw = consult_cluster_monitor()
    res = json.loads(res_raw)
    assert res["cluster_nodes"]["Edge_Node"]["ip"] == "192.168.1.99"
    assert res["cluster_nodes"]["macbook"]["ip"] == "192.168.1.88"

