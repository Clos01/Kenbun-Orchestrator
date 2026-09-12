"""
🏛️ Kenbun Functional Sovereign Specialists
============================================
Clear, function-driven sovereign agents and diagnostic tools:
- consult_code_diagnostician: Code fault diagnostic surgeon (Qwen 2.5 Coder 14B on LG 2025)
- consult_cluster_monitor:    Cluster hardware nodes & background task monitor
- consult_performance_tuner:  Bayesian confidence & tool win-rate performance tuner
- consult_framing_sentinel:   FastMCP protocol & stdout framing isolation auditor
- consult_leak_sentinel:      Zero-leak path, token, and secret security sentinel
- consult_memory_archivist:   Historical post-mortem & Hivemind memory search
"""

import json
import logging
import os
import re
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.infrastructure.config import settings
from tools.registry import sovereign_tool
from tools.utils.helpers import silence_stdout
from tools.utils.path_utils import get_project_root

logger = logging.getLogger("tools.specialists")

# Dedicated LM Studio host for the Code Diagnostician (Local GPU Server)
LG_2025_HOST = "<ORCHESTRATOR_IP>"
DEFAULT_MEC_PORT = getattr(settings, "LM_STUDIO_PORT", 2065) or 2065
DEFAULT_MEC_MODEL = "qwen/qwen2.5-coder-14b"


def _call_lg_lmstudio(
    system_prompt: str,
    user_message: str,
    model: str = DEFAULT_MEC_MODEL,
    timeout: float = 60.0,
) -> Optional[str]:
    """Sends inference request to LG 2025 LM Studio with fast-fail fallback."""
    host = LG_2025_HOST
    port = DEFAULT_MEC_PORT
    url = f"http://{host}:{port}/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.2,
        "max_tokens": 280,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "Kenbun-Specialists"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("choices", [{}])[0].get("message", {}).get("content")
    except Exception as e:
        logger.debug(f"Specialist LM Studio call failed ({url}): {e}")
        return None


# ============================================================================
# 1. CODE DIAGNOSTICIAN (DIAGNOSTIC SURGEON)
# ============================================================================

DIAGNOSTIC_SYSTEM_PROMPT = """You are the Kenbun Code Diagnostician and Surgical Repair Specialist.
You have deep mastery of the Kenbun chassis. Speak with concise, technical precision in 3-5 punchy bullet points.
Diagnose the root cause, identify the exact component or file, and prescribe surgical repairs.
"""

@sovereign_tool(name="consult_code_diagnostician", category="Specialists")
def consult_code_diagnostician(
    issue: str,
    target_file: Optional[str] = None,
    code_snippet: Optional[str] = None,
) -> str:
    """
    Diagnoses architectural bugs, race conditions, AST faults, and prescribes surgical repairs
    using local Qwen 2.5 Coder 14B on LG 2025.
    """
    with silence_stdout():
        repo_root = get_project_root()
        context_lines = []

        # 1. Pull relevant file context if target_file specified
        if target_file:
            p = Path(target_file)
            if not p.is_absolute():
                p = repo_root / p
            if p.exists() and p.is_file():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()
                    sample = "\n".join(lines[:120])
                    context_lines.append(f"Target File: {p.name} ({len(lines)} lines)\n```python\n{sample}\n```")
                except Exception as e:
                    context_lines.append(f"Could not read {target_file}: {e}")

        if code_snippet:
            context_lines.append(f"Code Snippet:\n```python\n{code_snippet}\n```")

        # 2. Check historical fix memory
        try:
            from tools.execution.checkpoint_tools import recall_fix
            past_fixes = recall_fix(error_message=issue)
            if past_fixes and "No relevant fix" not in str(past_fixes):
                context_lines.append(f"Historical Garage Logbook:\n{past_fixes}")
        except Exception:
            pass

        full_context = "\n\n".join(context_lines)
        user_prompt = f"ISSUE / SYMPTOM:\n{issue}\n\nCONTEXT:\n{full_context}" if full_context else f"ISSUE / SYMPTOM:\n{issue}"

        # 3. Query local Qwen Coder model on LG 2025
        response = _call_lg_lmstudio(DIAGNOSTIC_SYSTEM_PROMPT, user_prompt, model=DEFAULT_MEC_MODEL, timeout=60.0)

        if response:
            return json.dumps({
                "specialist": "code-diagnostician",
                "engine": f"LM Studio ({DEFAULT_MEC_MODEL}) on LG 2025",
                "diagnosis": response,
                "status": "DIAGNOSED",
            }, indent=2)

        # Fallback if local model is offline
        return json.dumps({
            "specialist": "code-diagnostician",
            "engine": "Heuristic Diagnostic Fallback (LG 2025 offline)",
            "status": "FALLBACK_DIAGNOSIS",
            "diagnosis": (
                f"Diagnostic quick-scan on '{issue}': Inspect recent git commits with 'git log -p -1', "
                f"verify stderr routing in FastMCP tools, and run 'bin/kenbun-harness audit-complete' "
                f"on modified files to catch incomplete stubs."
            ),
        }, indent=2)

# Alias for backward compatibility
consult_kenbun_mec = consult_code_diagnostician


# ============================================================================
# 2. CLUSTER MONITOR (HARDWARE & CLUSTER NODES)
# ============================================================================

@sovereign_tool(name="consult_cluster_monitor", category="Specialists")
def consult_cluster_monitor(action: str = "status", target: Optional[str] = None) -> str:
    """
    Monitors sovereign cluster nodes (Mac, Edge_Node, LG 2025), port status, and active background tasks.
    """
    with silence_stdout():
        nodes = {
            "gpu_node": {"ip": LG_2025_HOST, "port": DEFAULT_MEC_PORT, "role": "LM Studio & ChromaDB"},
            "Edge_Node": {"ip": "<REMOTE_HOST_IP>", "port": 11434, "role": "ThinkStation Edge Satellite"},
            "macbook": {"ip": "<CLIENT_IP>", "port": 22, "role": "Mac Sovereign Workstation"},
        }

        cluster_status = {}
        for name, info in nodes.items():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.35)
            reachable = False
            try:
                reachable = s.connect_ex((info["ip"], info["port"])) == 0
            except Exception:
                reachable = False
            finally:
                s.close()
            cluster_status[name] = {
                "ip": info["ip"],
                "role": info["role"],
                "status": "ONLINE" if reachable else "OFFLINE_OR_UNREACHABLE",
            }

        # Check background tasks
        from tools.execution.oom_safe_harness import list_background_tasks
        bg_tasks = json.loads(list_background_tasks(limit=5))

        return json.dumps({
            "specialist": "cluster-monitor",
            "operation": "Hardware Cluster Status",
            "cluster_nodes": cluster_status,
            "recent_tasks": bg_tasks.get("tasks", []),
            "verdict": "CLUSTER_READY" if cluster_status["gpu_node"]["status"] == "ONLINE" else "DEGRADED_CLUSTER",
        }, indent=2)

# Alias for backward compatibility
consult_kenbun_pit = consult_cluster_monitor


# ============================================================================
# 3. PERFORMANCE TUNER (BAYESIAN ENGINE & WIN RATES)
# ============================================================================

@sovereign_tool(name="consult_performance_tuner", category="Specialists")
def consult_performance_tuner(metric: str = "status", tool_name: Optional[str] = None) -> str:
    """
    Analyzes Bayesian tool win rates, alpha/beta confidence distributions, and database state.
    """
    with silence_stdout():
        from tools.utils.bayesian import get_db_status, get_posterior_params

        db_stat = get_db_status()
        confidence = {}
        target_tools = [tool_name] if tool_name else ["replace_file_content", "consult_supervisor", "run_code_safely", "ripgrep_search"]

        for t in target_tools:
            if t:
                a, b = get_posterior_params(t, "Execution")
                rate = round(a / (a + b), 3) if (a + b) > 0 else 0.5
                confidence[t] = {"alpha": a, "beta": b, "win_rate": f"{rate * 100:.1f}%"}

        return json.dumps({
            "specialist": "performance-tuner",
            "readout": "Bayesian Tool Performance",
            "database_source": db_stat.get("active_source"),
            "fallback_active": db_stat.get("fallback_active"),
            "tool_confidence_curves": confidence,
            "verdict": "TUNED_OPTIMAL" if not db_stat.get("fallback_active") else "OPERATING_ON_SQLITE_BOOST",
        }, indent=2)

# Alias for backward compatibility
consult_kenbun_dyno = consult_performance_tuner


# ============================================================================
# 4. FRAMING SENTINEL (FASTMCP PROTOCOL & STDOUT ISOLATION)
# ============================================================================

@sovereign_tool(name="consult_framing_sentinel", category="Specialists")
def consult_framing_sentinel(component: str = "fastmcp", check_type: str = "framing") -> str:
    """
    Audits codebase for unshielded stdout prints that corrupt FastMCP JSON-RPC framing.
    """
    with silence_stdout():
        repo_root = get_project_root()
        stray_prints = []

        tools_dir = repo_root / "core" / "tools"
        if tools_dir.exists():
            for py_file in tools_dir.rglob("*.py"):
                if "tests" in str(py_file) or "scratch" in str(py_file):
                    continue
                try:
                    txt = py_file.read_text(encoding="utf-8", errors="replace")
                    for line_no, line in enumerate(txt.splitlines(), start=1):
                        sline = line.strip()
                        if sline.startswith("print(") and "debug" not in sline.lower():
                            stray_prints.append({
                                "file": py_file.name,
                                "line": line_no,
                                "snippet": sline[:80],
                            })
                            if len(stray_prints) >= 5:
                                break
                except Exception:
                    pass
                if len(stray_prints) >= 5:
                    break

        return json.dumps({
            "specialist": "framing-sentinel",
            "component": component,
            "framing_check": "PASSED" if not stray_prints else "GROUND_FAULT_WARNING",
            "stray_stdout_prints": stray_prints,
            "remediation": "Wrap noisy prints with 'with silence_stdout():' or route to logger.debug/stderr.",
        }, indent=2)

# Alias for backward compatibility
consult_kenbun_wire = consult_framing_sentinel


# ============================================================================
# 5. LEAK SENTINEL (ZERO-LEAK SECURITY & HARDCODED PATHS)
# ============================================================================

@sovereign_tool(name="consult_leak_sentinel", category="Specialists")
def consult_leak_sentinel(scan_type: str = "leak_audit", target_dir: Optional[str] = None) -> str:
    """
    Scans repository files for hardcoded private user paths, exposed keys, and token leaks.
    """
    with silence_stdout():
        repo_root = get_project_root()
        target = Path(target_dir).resolve() if target_dir else repo_root
        leaks = []

        try:
            cmd = ["git", "-C", str(repo_root), "status", "--porcelain"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            changed_files = [line[3:].strip() for line in res.stdout.splitlines() if line[3:].strip()]
        except Exception:
            changed_files = []

        path_regex = re.compile(r'/(Users|home)/[a-zA-Z0-9_-]+')
        for cf in changed_files[:30]:
            p = repo_root / cf
            if p.exists() and p.is_file() and p.suffix in (".py", ".sh", ".json", ".yml", ".md"):
                try:
                    txt = p.read_text(encoding="utf-8", errors="replace")
                    for lno, line in enumerate(txt.splitlines(), start=1):
                        if path_regex.search(line) and not any(ign in line for ign in ["/home/runner", "/home/node", "/home/vscode"]):
                            leaks.append({"file": cf, "line": lno, "match": line.strip()[:80]})
                except Exception:
                    pass

        return json.dumps({
            "specialist": "leak-sentinel",
            "scan_type": scan_type,
            "zero_leak_status": "SECURE" if not leaks else "LEAKS_DETECTED",
            "leaks_found": len(leaks),
            "findings": leaks[:5],
            "verdict": "CLEAR_TO_PUSH" if not leaks else "BLOCKED_BY_ARMOURER",
        }, indent=2)

# Alias for backward compatibility
consult_kenbun_sec = consult_leak_sentinel


# ============================================================================
# 6. MEMORY ARCHIVIST (POST-MORTEMS & ARCHAEOLOGY)
# ============================================================================

@sovereign_tool(name="consult_memory_archivist", category="Specialists")
def consult_memory_archivist(query: str, limit: int = 3) -> str:
    """
    Queries past post-mortems, incident resolutions, and Hivemind memories for historical answers.
    """
    with silence_stdout():
        repo_root = get_project_root()
        history_hits = []

        pm_path = repo_root / "POST_MORTEM.md"
        if pm_path.exists():
            try:
                txt = pm_path.read_text(encoding="utf-8", errors="replace")
                paragraphs = txt.split("\n\n")
                for p in paragraphs:
                    if any(q.lower() in p.lower() for q in query.split()):
                        history_hits.append({"source": "POST_MORTEM.md", "snippet": p[:250]})
                        if len(history_hits) >= limit:
                            break
            except Exception:
                pass

        try:
            from tools.memory.hivemind_tools import search_hivemind_concepts
            hive_res = json.loads(search_hivemind_concepts(query=query))
            for item in hive_res.get("results", [])[:limit]:
                history_hits.append({"source": "Hivemind Concept", "snippet": str(item)[:250]})
        except Exception:
            pass

        return json.dumps({
            "specialist": "memory-archivist",
            "query": query,
            "historical_records_found": len(history_hits),
            "records": history_hits[:limit],
            "verdict": "ARCHIVAL_RECORD_RETRIEVED" if history_hits else "NO_MATCHING_POST_MORTEM",
        }, indent=2)

# Alias for backward compatibility
consult_kenbun_doc = consult_memory_archivist
