"""
Functional Specialist Pipelines for Kenbun Orchestrator
=======================================================
Enables:
- orchestrate("code_diagnosis", task="...")
- orchestrate("cluster_health", task="...")
- orchestrate("performance_tuning", task="...")
- orchestrate("protocol_framing", task="...")
- orchestrate("zero_leak_audit", task="...")
- orchestrate("memory_archive", task="...")
"""

from typing import Any, Dict, List


def build_code_diagnostician_pipeline(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "id": "code_diagnosis",
            "label": "🩺 System 2 Local Coder: Diagnosing code faults & prescribing surgical diff",
            "tool": tools.get("consult_code_diagnostician") or tools.get("consult_kenbun_mec"),
            "input": lambda s: {
                "issue": s["task"],
                "target_file": s.get("file_path") or None,
                "code_snippet": s.get("code_snippet") or None,
            },
            "output_key": "diagnosis_report",
        }
    ]


def build_cluster_monitor_pipeline(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "id": "cluster_health",
            "label": "🖥️ Probing cluster hardware nodes (LG 2025, Edge_Node, Mac) & background tasks",
            "tool": tools.get("consult_cluster_monitor") or tools.get("consult_kenbun_pit"),
            "input": lambda s: {"action": "status", "target": s.get("task") or None},
            "output_key": "cluster_report",
        }
    ]


def build_performance_tuner_pipeline(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "id": "performance_tuning",
            "label": "📊 Reading Bayesian win-rates & tool confidence distributions",
            "tool": tools.get("consult_performance_tuner") or tools.get("consult_kenbun_dyno"),
            "input": lambda s: {"metric": "status", "tool_name": s.get("task") if s.get("task") and not s.get("task").startswith("Run") else None},
            "output_key": "performance_report",
        }
    ]


def build_framing_sentinel_pipeline(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "id": "framing_check",
            "label": "🔌 Auditing FastMCP stdout protocol isolation & JSON-RPC framing",
            "tool": tools.get("consult_framing_sentinel") or tools.get("consult_kenbun_wire"),
            "input": lambda s: {"component": "fastmcp"},
            "output_key": "framing_report",
        }
    ]


def build_leak_sentinel_pipeline(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "id": "zero_leak_audit",
            "label": "🛡️ Scanning repository for token leaks, private home paths & keys",
            "tool": tools.get("consult_leak_sentinel") or tools.get("consult_kenbun_sec"),
            "input": lambda s: {"scan_type": "zero_leak", "target_dir": s.get("project_path") or None},
            "output_key": "leak_report",
        }
    ]


def build_memory_archivist_pipeline(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "id": "memory_archive",
            "label": "📜 Searching post-mortems, commit lineages & Hivemind memory",
            "tool": tools.get("consult_memory_archivist") or tools.get("consult_kenbun_doc"),
            "input": lambda s: {"query": s.get("task") or "post_mortem"},
            "output_key": "archive_report",
        }
    ]
