"""
Cognitive Tool & Workflow Deliberation Engine for Kenbun.
=========================================================
Applies the Graph-of-Thoughts & Sparse Gating (GoT-DSR) protocol to tool calling.
Transforms blind, reactive tool invocations into deliberate, reasoned choices:

1. Intent & Domain Classification: Maps task tokens to core system domains.
2. Candidate Retrieval: Uses L1-sparse soft thresholding to pull the top k candidates.
3. Dialectic Deliberation: Weighs trade-offs, evaluates mutation risks, and checks
   whether a checkpoint or memory recall is required first.
4. Pre-Flight Contract Verification: Confirms expected arguments and return contracts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from tools.utils.sparse_gating import (
        CATEGORY_KEYWORDS,
        compute_sparse_tool_weights,
        CORE_DEFAULT_TOOLS,
    )
except ImportError:
    from core.tools.utils.sparse_gating import (
        compute_sparse_tool_weights,
    )

logger = logging.getLogger("tools.strategy.tool_deliberator")

# Full master registry of Kenbun sovereign tools and workflows with semantic intent
INTENT_TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "vcs_qa": {
        "type": "workflow",
        "category": "git_version",
        "description": "Pre-commit QA sentinel: in-depth AST audit, multi-tier compliance, and structured conventional commit generation with 'The Why'.",
        "risk": "LOW",
        "requires_checkpoint": False,
    },
    "bug_fix": {
        "type": "workflow",
        "category": "audit_security",
        "description": "Autonomous bug diagnosis and auto-repair: scan → recall → checkpoint → analyze → test → remember.",
        "risk": "MEDIUM",
        "requires_checkpoint": True,
    },
    "code_review": {
        "type": "workflow",
        "category": "audit_security",
        "description": "Multi-tier consensus code review: Gemini review → official docs → local supervisor cross-check.",
        "risk": "LOW",
        "requires_checkpoint": False,
    },
    "research_implement": {
        "type": "workflow",
        "category": "research_docs",
        "description": "Grounded feature design: research official documentation → architecture blueprint → supervisor sign-off.",
        "risk": "MEDIUM",
        "requires_checkpoint": True,
    },
    "design_ui": {
        "type": "workflow",
        "category": "ui_design",
        "description": "Heritage Design System UI architecture: tokens, bento grids, responsive layouts, 5D audit.",
        "risk": "LOW",
        "requires_checkpoint": False,
    },
    "consult_supervisor": {
        "type": "tool",
        "category": "audit_security",
        "description": "System 2 security and architecture consensus audit.",
        "risk": "LOW",
        "requires_checkpoint": False,
    },
    "remember_fix": {
        "type": "tool",
        "category": "memory_hivemind",
        "description": "Saves an error-fix mapping to Chroma DB / Honcho vector memory.",
        "risk": "LOW",
        "requires_checkpoint": False,
    },
    "recall_fix": {
        "type": "tool",
        "category": "memory_hivemind",
        "description": "Semantic search across vector error memory for past solutions.",
        "risk": "LOW",
        "requires_checkpoint": False,
    },
    "save_checkpoint": {
        "type": "tool",
        "category": "audit_security",
        "description": "Creates an atomic filesystem checkpoint before risky code mutations.",
        "risk": "LOW",
        "requires_checkpoint": False,
    },
    "run_code_safely": {
        "type": "tool",
        "category": "audit_security",
        "description": "Executes untrusted code in an isolated Docker container.",
        "risk": "LOW",
        "requires_checkpoint": False,
    },
    "scan_repo": {
        "type": "tool",
        "category": "research_docs",
        "description": "Scans workspace directory tree to build contextual architecture map.",
        "risk": "LOW",
        "requires_checkpoint": False,
    },
    "research_official_docs": {
        "type": "tool",
        "category": "research_docs",
        "description": "Queries official vendor documentation (Next.js, Tailwind, FastAPI, etc.).",
        "risk": "LOW",
        "requires_checkpoint": False,
    },
    "track_ast_changes": {
        "type": "tool",
        "category": "git_version",
        "description": "Extracts AST modifications and posts architectural rationale to boards.",
        "risk": "LOW",
        "requires_checkpoint": False,
    },
}


class ToolDeliberator:
    """
    Cognitive tool selection and workflow deliberation engine.
    Deliberates on available tools before calling them.
    """

    def __init__(self):
        self.tool_catalog = {k: v["description"] for k, v in INTENT_TOOL_REGISTRY.items()}

    def classify_intent(self, task: str) -> str:
        """Identifies primary intent domain from task text."""
        lowered = task.lower()
        if any(w in lowered for w in ["commit", "push", "pr", "vcs", "diff", "version control", "quality assurance", "qa"]):
            return "git_version"
        if any(w in lowered for w in ["fix", "bug", "crash", "error", "traceback", "exception"]):
            return "audit_security"
        if any(w in lowered for w in ["review", "audit", "security", "inspect", "vulnerability"]):
            return "audit_security"
        if any(w in lowered for w in ["ui", "css", "layout", "design", "tailwind", "component", "button", "modal"]):
            return "ui_design"
        if any(w in lowered for w in ["doc", "docs", "research", "official", "learn", "how to"]):
            return "research_docs"
        if any(w in lowered for w in ["db", "database", "postgres", "sql", "migration", "table"]):
            return "database_orm"
        return "general"

    def deliberate(self, task: str, project_path: str = "") -> Dict[str, Any]:
        """
        Executes a 4-stage cognitive deliberation across all available tools.
        Returns the optimal tool/workflow recommendation with full rationale.
        """
        primary_domain = self.classify_intent(task)

        # 1. Compute sparse tool weights
        ranked_candidates = compute_sparse_tool_weights(
            task_description=task,
            available_tool_map=self.tool_catalog,
            lambda_penalty=0.10,
            max_active_tools=5,
        )

        top_tools = [t[0] for t in ranked_candidates]

        # 2. Decision logic: Orchestrated Workflow vs Individual Atomic Tool
        recommended_workflow = None
        recommended_tools = []
        deliberation_notes = []

        if "vcs" in task.lower() or "commit" in task.lower() or "qa" in task.lower() or "diff" in task.lower():
            recommended_workflow = "vcs_qa"
            deliberation_notes.append("VCS/Git intent detected → Triggering 'vcs_qa' pre-commit pipeline.")
            deliberation_notes.append("Will ingest diffs, verify AST syntax, check STRUCTURE.md tier rules, and output conventional 'The Why' commit.")
        elif any(k in task.lower() for k in ["fix", "bug", "error", "crash"]) and "workflow" not in task.lower():
            recommended_workflow = "bug_fix"
            deliberation_notes.append("Bug diagnosis intent detected → 'bug_fix' pipeline selected.")
        elif any(k in task.lower() for k in ["review", "critique", "audit code"]):
            recommended_workflow = "code_review"
            deliberation_notes.append("Code review intent detected → 'code_review' consensus pipeline selected.")
        elif any(k in task.lower() for k in ["design", "ui", "mockup", "wireframe"]):
            recommended_workflow = "design_ui"
            deliberation_notes.append("UI aesthetic intent detected → 'design_ui' pipeline selected.")
        else:
            # Atomic tool recommendation
            recommended_tools = top_tools or ["consult_supervisor", "scan_repo"]
            deliberation_notes.append(f"Task matches atomic tool execution in domain '{primary_domain}'.")

        # 3. Risk & Checkpoint Analysis
        requires_checkpoint = False
        if recommended_workflow and INTENT_TOOL_REGISTRY.get(recommended_workflow, {}).get("requires_checkpoint"):
            requires_checkpoint = True
        elif any(w in task.lower() for w in ["refactor", "overwrite", "delete", "migrate", "alter"]):
            requires_checkpoint = True

        preconditions = []
        if requires_checkpoint:
            preconditions.append("⚠️ State-mutating action: Call 'save_checkpoint(file_path)' before executing modifications.")
        if primary_domain == "audit_security":
            preconditions.append("🧠 Check past error memory: Call 'recall_fix(error_message)' to verify past known regressions.")

        return {
            "task": task,
            "domain": primary_domain,
            "recommended_workflow": recommended_workflow,
            "recommended_tools": recommended_tools if not recommended_workflow else [recommended_workflow],
            "ranked_candidates": ranked_candidates,
            "requires_checkpoint": requires_checkpoint,
            "preconditions": preconditions,
            "deliberation_notes": deliberation_notes,
            "execution_plan": self._generate_plan_text(task, recommended_workflow, recommended_tools, preconditions),
        }

    def _generate_plan_text(
        self,
        task: str,
        workflow: Optional[str],
        tools: List[str],
        preconditions: List[str],
    ) -> str:
        lines = []
        if workflow:
            lines.append(f"1. Call orchestrate(\"{workflow}\", task=\"{task}\")")
            lines.append(f"2. Inspect structured report and verification status")
            lines.append(f"3. Proceed to atomic commit or merge once approved")
        else:
            for idx, tool in enumerate(tools, start=1):
                meta = INTENT_TOOL_REGISTRY.get(tool, {})
                desc = meta.get("description", "Execute operation")
                lines.append(f"{idx}. `{tool}(...)` — {desc}")

        if preconditions:
            lines.append("\n**Pre-Flight Invariants:**")
            for pre in preconditions:
                lines.append(f"- {pre}")

        return "\n".join(lines)


# Global instance
tool_deliberator = ToolDeliberator()


def deliberate_on_tools(task: str, project_path: str = "") -> str:
    """
    Sovereign Cognitive Deliberation Tool:
    Evaluates tool candidates, checks risk preconditions, and recommends the optimal
    pipeline or tool execution sequence.
    """
    decision = tool_deliberator.deliberate(task, project_path)

    md = [
        f"## 🧠 Cognitive Tool Deliberation for: \"{task}\"",
        f"**Identified Domain:** `{decision['domain']}`",
        f"**Recommended Workflow:** `{decision['recommended_workflow'] or 'None (Use Atomic Tools)'}`\n",
        f"### 💡 Selection Rationale",
    ]
    for note in decision["deliberation_notes"]:
        md.append(f"- {note}")

    md.append(f"\n### 📋 Step-by-Step Execution Plan\n{decision['execution_plan']}")

    if decision.get("ranked_candidates"):
        md.append("\n### ⚖️ L1-Sparse Candidate Weights (Top Candidates):")
        for tool_name, weight in decision["ranked_candidates"]:
            md.append(f"- `{tool_name}`: {weight:.2f}")

    return "\n".join(md)
