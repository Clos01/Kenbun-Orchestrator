"""
VCS & Quality Assurance Pipeline for Kenbun.
============================================
Workflow: vcs_qa
Stages: Ingest Diffs → Static & AST Audit → Architecture Check → Supervisor Consensus → Vector Memory Learning → Structured Commit Documentation

Trigger this pipeline after automated code generation and prior to executing git commit/push.
"""

from typing import Any, Dict, List


def build_vcs_qa_pipeline(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Builds the VCS & Quality Assurance Sentinel pipeline.
    """
    steps = [
        {
            "id": "ingest_and_audit",
            "label": "🔍 Ingesting diffs and executing AST static analysis",
            "tool": tools.get("audit_and_document_commit") or (
                lambda task, project_path="": f"VCS QA Check on '{task}' at '{project_path}'"
            ),
            "input": lambda s: {
                "task": s["task"],
                "project_path": s.get("project_path") or ".",
            },
            "output_key": "vcs_qa_report",
        },
        {
            "id": "supervisor_signoff",
            "label": "🏛️ System 2: Verifying architecture compliance & security sign-off",
            "tool": tools["consult_supervisor"],
            "input": lambda s: {
                "user_proposal": f"VCS QA Pre-Commit Verification: {s['task']}",
                "code_snippet": str(s.get("vcs_qa_report", ""))[:4000],
            },
            "output_key": "supervisor_result",
        },
        {
            "id": "memory_sync",
            "label": "🧠 Syncing QA audit outcome to Vector Memory & Honcho",
            "tool": tools["remember_fix"],
            "input": lambda s: {
                "error_message": f"VCS QA Sentinel: {s['task']}",
                "solution": str(s.get("vcs_qa_report", ""))[:2000],
                "file_context": s.get("file_path") or "vcs_qa_pipeline",
            },
            "skip_if": lambda s: "REJECTED" not in str(s.get("vcs_qa_report", "")),
            "output_key": "memory_result",
        }
    ]
    return steps
