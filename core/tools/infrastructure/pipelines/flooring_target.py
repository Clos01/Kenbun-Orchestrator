"""
Flooring Lead Targeting & Board Provisioning Pipeline for Kenbun Orchestrator.
=============================================================================
Workflow: flooring_target
Stages: Ingest Permits → Classify 4 Personas → Compute Takeoffs → Provision Kanban Cards → Attach Audit Learnings
"""

from typing import Any, Dict, List
import json


def build_flooring_target_pipeline(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Builds the Flooring Lead Acquisition & Persona Board Provisioning pipeline."""
    from tools.strategy.flooring_orchestrator import FlooringPipelineOrchestrator

    steps = [
        {
            "id": "classify_and_provision",
            "label": "🎯 Classifying incoming permits across 4 personas & provisioning Kanban cards",
            "tool": lambda task, project_path="": json.dumps(
                FlooringPipelineOrchestrator.run_pipeline()
            ),
            "input": lambda s: {
                "task": s["task"],
                "project_path": s.get("project_path") or ".",
            },
            "output_key": "flooring_provision_report",
        },
        {
            "id": "pipeline_summary",
            "label": "📊 Finalizing 8-Phase Board sync and tactical telemetry",
            "tool": lambda flooring_provision_report="": (
                f"✅ Flooring Target Pipeline Complete.\n"
                f"Ingested & provisioned 4 distinct contractor archetypes with automated turnkey take-offs, "
                f"60-min sprint elevator pitches, and Tier-3 mistake prevention sentinels."
            ),
            "input": lambda s: {
                "flooring_provision_report": s.get("flooring_provision_report", "")
            },
            "output_key": "final_summary"
        }
    ]
    return steps
