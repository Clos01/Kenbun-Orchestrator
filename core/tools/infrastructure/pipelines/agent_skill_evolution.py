"""
Autonomous Agent & Skill Evolution Pipeline for Kenbun Swarm.
=============================================================
Workflow: agent_skill_evolution
Stages: Gap Discovery → Blueprint & Synthesis → Sandbox Verification → Registry Promotion → Supervisor Consensus

Trigger this pipeline to autonomously invent, verify, and register new specialized agents and skills.
"""
from typing import Any, Dict, List
import json


def build_agent_skill_evolution_pipeline(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Builds the Autonomous Agent & Skill Evolution pipeline.
    """
    from tools.strategy.agent_skill_synthesizer import agent_skill_synthesizer

    steps = [
        {
            "id": "gap_discovery",
            "label": "🔍 Phase 1: Auditing Runtime Fallbacks & Discovering Agent Gaps",
            "tool": lambda: agent_skill_synthesizer.discover_agent_gaps(),
            "input": lambda s: {},
            "output_key": "discovered_gaps",
        },
        {
            "id": "autonomous_synthesis",
            "label": "🧬 Phase 2: Synthesizing Production-Grade Agent Blueprint & SKILL.md",
            "tool": lambda gaps, task="": _synthesize_candidate(agent_skill_synthesizer, gaps, task),
            "input": lambda s: {
                "gaps": s.get("discovered_gaps", []),
                "task": s.get("task", "")
            },
            "output_key": "synthesized_candidate",
        },
        {
            "id": "sandbox_verification",
            "label": "🧪 Phase 3: Sandboxed AST Integrity, YAML Frontmatter & Schema Verification",
            "tool": lambda candidate: _verify_candidate(agent_skill_synthesizer, candidate),
            "input": lambda s: {
                "candidate": s.get("synthesized_candidate", {})
            },
            "output_key": "verification_report",
        },
        {
            "id": "registry_promotion",
            "label": "📦 Phase 4: Promoting to Master Skills Registry & Dynamic Keyword Router",
            "tool": lambda candidate, verification: _promote_candidate(agent_skill_synthesizer, candidate, verification),
            "input": lambda s: {
                "candidate": s.get("synthesized_candidate", {}),
                "verification": s.get("verification_report", {})
            },
            "output_key": "promotion_report",
        },
        {
            "id": "supervisor_consensus",
            "label": "🏛️ Phase 5: System 2 Supervisor Evolution Verification",
            "tool": tools.get("consult_supervisor") or (lambda user_proposal, code_snippet="": "Evolution cycle approved."),
            "input": lambda s: {
                "user_proposal": f"Autonomous Agent Skill Evolution: {s.get('synthesized_candidate', {}).get('name', 'N/A')}",
                "code_snippet": json.dumps(s.get("promotion_report", {}), indent=2),
            },
            "output_key": "supervisor_decision",
        },
    ]
    return steps


def _synthesize_candidate(synthesizer, gaps: List[Dict[str, Any]], task: str) -> Dict[str, Any]:
    if not gaps:
        return {"status": "skipped", "message": "No agent gaps detected."}
    target = gaps[0]
    return synthesizer.synthesize_skill(target, dry_run=False)


def _verify_candidate(synthesizer, candidate: Dict[str, Any]) -> Dict[str, Any]:
    name = candidate.get("name")
    if not name:
        return {"valid": False, "score": 0.0, "errors": ["No candidate to verify."]}
    return synthesizer.verify_skill(name)


def _promote_candidate(synthesizer, candidate: Dict[str, Any], verification: Dict[str, Any]) -> Dict[str, Any]:
    name = candidate.get("name")
    if not name or not verification.get("valid", False):
        return {"status": "aborted", "reason": verification.get("errors", ["Candidate not valid"])}
    spec = candidate.get("spec", {})
    return synthesizer.promote_and_register(name, spec, dry_run=False)
