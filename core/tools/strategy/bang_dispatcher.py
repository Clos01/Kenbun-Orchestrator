"""Universal Bang Command Dispatcher for Kenbun Sovereign Engine.

Provides single-token shorthand directives (!Supervisor, !Orchestrate, !timesfm,
!vcs_qa, !bug_fix, !fable, etc.) across CLI REPL, command arguments, and FastMCP.
"""

import shlex
from typing import Tuple, Dict, Any, Optional

BANG_DIRECTIVES = {
    "!supervisor": "consult_supervisor",
    "!orchestrate": "orchestrate",
    "!timesfm": "predictive_timesfm",
    "!vcs_qa": "vcs_qa",
    "!bug_fix": "bug_fix",
    "!fable": "fable_reasoning",
    "!code_review": "code_review",
    "!design_ui": "design_ui",
    "!wireframe": "wireframe",
    "!diagnose": "consult_code_diagnostician",
    "!code_diagnostician": "consult_code_diagnostician",
    "!mec": "consult_code_diagnostician",
    "!cluster": "consult_cluster_monitor",
    "!cluster_monitor": "consult_cluster_monitor",
    "!pit": "consult_cluster_monitor",
    "!perf": "consult_performance_tuner",
    "!performance": "consult_performance_tuner",
    "!performance_tuner": "consult_performance_tuner",
    "!dyno": "consult_performance_tuner",
    "!protocol": "consult_framing_sentinel",
    "!framing": "consult_framing_sentinel",
    "!framing_sentinel": "consult_framing_sentinel",
    "!wire": "consult_framing_sentinel",
    "!leak_audit": "consult_leak_sentinel",
    "!leak_sentinel": "consult_leak_sentinel",
    "!sec": "consult_leak_sentinel",
    "!history": "consult_memory_archivist",
    "!memory_archivist": "consult_memory_archivist",
    "!doc": "consult_memory_archivist",
    "!help": "help",
}

HELP_TEXT = """# ⚡ Kenbun Universal Bang Command Reference

Single-token directives to immediately invoke Kenbun core capabilities:

| Directive | Target Workflow / System | Example Usage |
|---|---|---|
| `!diagnose <issue> [file]` | System 2 Local Coder (Qwen 2.5 Coder 14B on LG 2025) | `!diagnose "Async race condition on shutdown"` |
| `!cluster` | Cluster Hardware Nodes & Background Task Monitor | `!cluster` |
| `!perf [tool]` | Bayesian Tool Confidence & Win-Rate Tuner | `!perf replace_file_content` |
| `!protocol` | FastMCP Protocol & Stdout Framing Isolation Auditor | `!protocol` |
| `!leak_audit [path]` | Zero-Leak Security & Secret Sentinel | `!leak_audit core/` |
| `!history <query>` | Post-Mortem & Hivemind Memory Archivist | `!history "telemetry"` |
| `!Supervisor <task> [code]` | System 2 Architecture & Audit | `!Supervisor "Audit connection pool" "with get_connection(): pass"` |
| `!Orchestrate <workflow> <task>` | Kenbun Pipeline Dispatch | `!Orchestrate bug_fix "Resolve memory leak"` |
| `!timesfm <task>` | Google TimesFM-3 Dynamic Predictive Pipeline | `!timesfm "Fix websocket timeout"` |
| `!vcs_qa <task>` | VCS & QA Sentinel Pipeline | `!vcs_qa "Audit recent git diff"` |
| `!bug_fix <task>` | Full Bug Fix Pipeline | `!bug_fix "Fix crash in postgres client"` |
| `!fable <task>` | Fable-Class Deep Reasoning Pipeline | `!fable "Design high-scale rate limiter"` |
| `!code_review <task>` | Multi-Pass Code Review Pipeline | `!code_review "Audit src/lib/auth.ts"` |
| `!design_ui <task>` | Strategic UI Design Pipeline | `!design_ui "Design contractor dashboard"` |
| `!wireframe <task>` | Deterministic Wireframe Engine | `!wireframe "Landing page with CTA hero"` |
| `!help` | Show this reference guide | `!help` |
"""


def is_bang_command(text: str) -> bool:
    """True if string starts with an exclamation point followed by a directive."""
    if not text or not isinstance(text, str):
        return False
    stripped = text.strip()
    return stripped.startswith("!") and len(stripped) > 1 and not stripped.startswith("!=" )


def parse_bang_command(cmd_str: str) -> Tuple[str, str, Dict[str, Any]]:
    """Parses a bang command into (directive, clean_payload, kwargs).

    Preserves multiline code blocks and inner quotes.
    """
    if not is_bang_command(cmd_str):
        return "", cmd_str, {}

    clean = cmd_str.strip()
    # Extract directive word (e.g. !Supervisor, !timesfm)
    parts = clean.split(maxsplit=1)
    raw_directive = parts[0].lower()
    payload = parts[1] if len(parts) > 1 else ""

    # Normalize directive
    directive = raw_directive if raw_directive in BANG_DIRECTIVES else ""
    return directive, payload.strip(), {}


def dispatch_bang_command(cmd_str: str) -> str:
    """Executes a parsed bang directive and returns formatted string output."""
    directive, payload, _ = parse_bang_command(cmd_str)

    if not directive:
        if cmd_str.strip().startswith("!"):
            raw_dir = cmd_str.strip().split()[0]
            return f"⚠️ Unknown bang directive '{raw_dir}'. Type `!help` for available directives."
        return f"Not a bang command: {cmd_str}"

    if directive == "!help":
        return HELP_TEXT

    # 1. System 2 Supervisor Audit
    if directive == "!supervisor":
        try:
            from tools.strategy.orchestration_tools import consult_supervisor
            # Split into task and optional code if quotes are used
            task = payload
            code = ""
            if "```" in payload:
                # Code block detected
                p_parts = payload.split("```", 1)
                task = p_parts[0].strip()
                code = "```" + p_parts[1]
            elif payload.count('"') >= 4 or payload.count("'") >= 4:
                try:
                    split_args = shlex.split(payload)
                    if len(split_args) >= 2:
                        task = split_args[0]
                        code = split_args[1]
                except Exception:
                    pass
            return consult_supervisor(proposal=task, code_snippet=code)
        except Exception as e:
            return f"❌ !Supervisor dispatch failed: {e}"

    # 2. General Orchestrate
    if directive == "!orchestrate":
        try:
            from tools.infrastructure.orchestrator import orchestrate
            parts = payload.split(maxsplit=1)
            if not parts:
                return "⚠️ Usage: `!Orchestrate <workflow> <task>`"
            workflow = parts[0]
            task = parts[1] if len(parts) > 1 else "Run orchestrated workflow"
            return orchestrate(workflow=workflow, task=task)
        except Exception as e:
            return f"❌ !Orchestrate dispatch failed: {e}"

    # 3. Functional Specialists Direct Bang Execution
    if directive in ("!diagnose", "!code_diagnostician", "!mec"):
        try:
            from tools.specialists.pit_crew import consult_code_diagnostician
            parts = shlex.split(payload) if payload else []
            issue = parts[0] if parts else (payload or "General diagnostic request")
            target_file = parts[1] if len(parts) > 1 else None
            return consult_code_diagnostician(issue=issue, target_file=target_file)
        except Exception as e:
            return f"❌ {directive} dispatch failed: {e}"

    if directive in ("!cluster", "!cluster_monitor", "!pit"):
        try:
            from tools.specialists.pit_crew import consult_cluster_monitor
            return consult_cluster_monitor(action="status")
        except Exception as e:
            return f"❌ {directive} dispatch failed: {e}"

    if directive in ("!perf", "!performance", "!performance_tuner", "!dyno"):
        try:
            from tools.specialists.pit_crew import consult_performance_tuner
            target_tool = payload.strip() if payload else None
            return consult_performance_tuner(tool_name=target_tool)
        except Exception as e:
            return f"❌ {directive} dispatch failed: {e}"

    if directive in ("!protocol", "!framing", "!framing_sentinel", "!wire"):
        try:
            from tools.specialists.pit_crew import consult_framing_sentinel
            return consult_framing_sentinel()
        except Exception as e:
            return f"❌ {directive} dispatch failed: {e}"

    if directive in ("!leak_audit", "!leak_sentinel", "!sec"):
        try:
            from tools.specialists.pit_crew import consult_leak_sentinel
            target = payload.strip() if payload else None
            return consult_leak_sentinel(target_dir=target)
        except Exception as e:
            return f"❌ {directive} dispatch failed: {e}"

    if directive in ("!history", "!memory_archivist", "!doc"):
        try:
            from tools.specialists.pit_crew import consult_memory_archivist
            q = payload.strip() if payload else "post_mortem"
            return consult_memory_archivist(query=q)
        except Exception as e:
            return f"❌ {directive} dispatch failed: {e}"

    # 4. Direct Workflow Shortcuts
    workflow_map = {
        "!timesfm": "predictive_timesfm",
        "!vcs_qa": "vcs_qa",
        "!bug_fix": "bug_fix",
        "!fable": "fable_reasoning",
        "!code_review": "code_review",
        "!design_ui": "design_ui",
        "!wireframe": "wireframe",
    }

    if directive in workflow_map:
        target_workflow = workflow_map[directive]
        task_desc = payload if payload else f"Execute {target_workflow}"
        try:
            from tools.infrastructure.orchestrator import orchestrate
            return orchestrate(workflow=target_workflow, task=task_desc)
        except Exception as e:
            return f"❌ {directive} dispatch failed: {e}"

    return f"⚠️ Unhandled directive: {directive}"


def dispatch_natural_command(text: str, confirmation_token: Optional[str] = None) -> str:
    """Dispatches either an explicit bang command or natural language compiled command."""
    if is_bang_command(text):
        return dispatch_bang_command(text)

    try:
        from tools.strategy.prompt_compiler import compile_and_dispatch_prompt
        res = compile_and_dispatch_prompt(text, confirmation_token=confirmation_token)
        if res.get("status") == "success":
            return f"✅ [{res['tool_name']}] Auto-Dispatched:\n{res.get('result')}"
        elif res.get("status") == "passthrough":
            return text
        elif res.get("status") == "error":
            return f"⚠️ Auto-Tool Error: {res.get('error')}"
        return str(res)
    except Exception as e:
        return f"⚠️ Intent Compiler Notice: {e}"

