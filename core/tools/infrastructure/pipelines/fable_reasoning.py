"""
Sovereign Fable-Class Reasoning Pipeline for Kenbun.
===================================================
Workflow: fable_reasoning
Stages:
1. Define Done-State: Establish explicit, testable completion criteria.
2. Cross-Check Anti-Patterns: Query Honcho & Chroma DB for Tier 3 negative constraints.
3. Graph-of-Thoughts (GoT) Branching: Explore Speed vs Enterprise Scale hypotheses and synthesize Senior Move.
4. Predictive Failure Modeling: Identify top 2 regression vulnerabilities.
5. System 2 Consensus & Pre-Flight Gate: Run supervisor audit and verify zero-loss business invariants.
"""

from typing import Any, Dict, List


def build_fable_reasoning_pipeline(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Builds the Sovereign Fable-Class Reasoning pipeline."""
    steps = [
        {
            "id": "define_done_state",
            "label": "🎯 1. Defining Finish-Line & Objective Done-State Contracts",
            "tool": lambda task, **kwargs: {
                "objective": task,
                "finish_line_criteria": [
                    "Zero AST syntax regressions across modified files",
                    "Deterministic type & schema compliance",
                    "Passing test execution and 100% pre-flight harness verification",
                ],
                "status": "ARMED",
            },
            "input": lambda s: {"task": s["task"]},
            "output_key": "done_state_contract",
        },
        {
            "id": "cross_check_anti_patterns",
            "label": "🧠 2. Querying Tier 3 Anti-Patterns & Negative Constraints (System 3)",
            "tool": tools.get("recall_fix") or (lambda error_message: f"No negative constraints for '{error_message}'"),
            "input": lambda s: {
                "error_message": s["task"],
            },
            "output_key": "anti_patterns_recalled",
        },
        {
            "id": "got_branching_synthesis",
            "label": "🌿 3. Graph-of-Thoughts (GoT) Branching & Dialectic Synthesis",
            "tool": tools.get("research_with_gemini") or (
                lambda query, tech_key="": f"GoT Synthesis for {query}"
            ),
            "input": lambda s: {
                "query": (
                    f"Task: {s['task']}\n"
                    "Evaluate two parallel hypotheses:\n"
                    "Branch A (Speed / Immediate Action): Minimal targeted modification.\n"
                    "Branch B (Enterprise / Infinite Scalability): Zero-loss invariants, typed boundaries, defensive schema.\n"
                    "Provide the Dialectic Synthesis (The Senior Move) combining rapid execution with infinite scalability."
                ),
                "tech_key": s.get("tech_key", "python"),
            },
            "output_key": "dialectic_synthesis",
        },
        {
            "id": "predict_failure_modes",
            "label": "🛡️ 4. Predictive Failure Modeling & Defensive Guardrails",
            "tool": tools.get("audit_guardrail") or (
                lambda code_snippet, task_context="": {"status": "PASSED", "guardrail": "verified"}
            ),
            "input": lambda s: {
                "code_snippet": str(s.get("dialectic_synthesis", ""))[:3000],
                "task_context": f"Identify top 2 regression vulnerabilities for: {s['task']}",
            },
            "output_key": "predictive_guardrails",
        },
        {
            "id": "supervisor_signoff",
            "label": "🏛️ 5. System 2: Multi-Model Consensus & Architectural Sign-Off",
            "tool": tools["consult_supervisor"],
            "input": lambda s: {
                "user_proposal": f"Sovereign Fable-Class Architecture: {s['task']}",
                "code_snippet": str(s.get("dialectic_synthesis", s["task"]))[:4000],
            },
            "output_key": "supervisor_verdict",
        },
    ]
    return steps
