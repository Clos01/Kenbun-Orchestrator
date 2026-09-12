#!/usr/bin/env python3
"""
DeepSeek Harness Upstream Sentinel (dsh_sentinel.py)
===================================================
Autonomous upstream tracking, delta analysis, and architectural porting engine.
Monitors upstream deepseek-ai/deepseek-harness releases, categorizes architectural
invariants (Session Log V3, Turn Enclosure, Durable Inbox, Landlock Sandbox), and
generates actionable porting plans for Kenbun's Python capability seams.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Defaults and Paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DSH_PATH = Path.home() / "Dev" / "deepseek-harness"
UPSTREAM_HTTPS_URL = "https://github.com/deepseek-ai/deepseek-harness.git"
STATUS_FILE = REPO_ROOT / "brain_health" / "dsh_upstream_status.json"
REPORT_FILE = REPO_ROOT / "brain_health" / "DSH_UPSTREAM_BRIEF.md"
DEFAULT_BASELINE_TAG = "dsh-v0.1.2-alpha.2"

# Color constants
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RED = "\033[31m"
RESET = "\033[0m"


class DSHSentinel:
    def __init__(self, dsh_path: Optional[Path] = None, upstream_url: str = UPSTREAM_HTTPS_URL):
        self.dsh_path = Path(os.environ.get("DSH_REPO_DIR", str(dsh_path or DEFAULT_DSH_PATH)))
        self.upstream_url = upstream_url
        self.repo_root = REPO_ROOT

    def is_repo_available(self) -> bool:
        return (self.dsh_path / ".git").exists()

    def fetch_upstream_tags(self, timeout_sec: int = 15) -> Tuple[bool, str]:
        """Fetch remote tags via HTTPS non-interactively without SSH hanging."""
        if not self.is_repo_available():
            return False, f"DSH repository not found at {self.dsh_path}"

        try:
            cmd = ["git", "fetch", self.upstream_url, "--tags", "--quiet"]
            res = subprocess.run(
                cmd,
                cwd=str(self.dsh_path),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            if res.returncode == 0:
                return True, "Tags fetched successfully from upstream"
            else:
                return False, f"Git fetch exited with code {res.returncode}: {res.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return False, f"Fetch timed out after {timeout_sec}s"
        except Exception as e:
            return False, str(e)

    def list_tags(self) -> List[str]:
        """List tags sorted by version descending."""
        if not self.is_repo_available():
            return []
        try:
            cmd = ["git", "tag", "-l", "--sort=-v:refname"]
            res = subprocess.run(cmd, cwd=str(self.dsh_path), capture_output=True, text=True)
            if res.returncode == 0:
                return [t.strip() for t in res.stdout.strip().splitlines() if t.strip()]
        except Exception:
            pass
        return []

    def get_latest_tag(self) -> Optional[str]:
        tags = self.list_tags()
        # Find highest dsh-v* tag
        for t in tags:
            if t.startswith("dsh-v"):
                return t
        return tags[0] if tags else None

    def get_tracked_baseline(self) -> str:
        """Read baseline from status JSON or fallback to default."""
        if STATUS_FILE.exists():
            try:
                with open(STATUS_FILE, "r") as f:
                    data = json.load(f)
                    if "tracked_baseline_tag" in data:
                        return data["tracked_baseline_tag"]
            except Exception:
                pass
        return DEFAULT_BASELINE_TAG

    def get_commit_delta(self, baseline: str, target: str) -> List[Dict[str, str]]:
        """Get git log commits between baseline and target."""
        if not self.is_repo_available():
            return []
        try:
            cmd = ["git", "log", "--format=%H|%s|%an|%cI", f"{baseline}..{target}"]
            res = subprocess.run(cmd, cwd=str(self.dsh_path), capture_output=True, text=True)
            if res.returncode != 0:
                return []
            commits = []
            for line in res.stdout.strip().splitlines():
                if not line.strip():
                    continue
                parts = line.strip().split("|", 3)
                if len(parts) == 4:
                    commits.append({
                        "hash": parts[0],
                        "subject": parts[1],
                        "author": parts[2],
                        "date": parts[3],
                    })
            return commits
        except Exception:
            return []

    def categorize_commits(self, commits: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
        """Categorize incoming commits into Kenbun architectural seams."""
        categories: Dict[str, List[Dict[str, str]]] = {
            "session_log_v3": [],
            "turn_enclosure": [],
            "durable_inbox": [],
            "sandbox_security": [],
            "subagent_runtime": [],
            "code_mode": [],
            "general_architecture": [],
        }

        for c in commits:
            subj = c["subject"].lower()
            if any(k in subj for k in ["session-log-v3", "session-format", "v2-to-v3", "persistence-sqlite", "persistence-jsonl", "system-prompt-as-surface-node", "canonical-envelope", "content-admission", "v3 migration", "session-persistence", "v3 release"]):
                categories["session_log_v3"].append(c)
            elif any(k in subj for k in ["turn-enclosure", "agent-loop", "failturn", "step-start", "turn balance"]):
                categories["turn_enclosure"].append(c)
            elif any(k in subj for k in ["inbox", "durable-inbox", "inbox-recovery", "session-projection"]):
                categories["durable_inbox"].append(c)
            elif any(k in subj for k in ["landlock", "sandbox", "flock", "pwsh"]):
                categories["sandbox_security"].append(c)
            elif any(k in subj for k in ["subagent", "runtime identity", "runtime parent", "claude-code", "codex"]):
                categories["subagent_runtime"].append(c)
            elif any(k in subj for k in ["code mode", "rfc 012", "code-dispatch"]):
                categories["code_mode"].append(c)
            else:
                categories["general_architecture"].append(c)

        return categories

    def generate_porting_recommendations(self, categories: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, Any]]:
        """Generate targeted recommendations for porting to Kenbun Python codebase."""
        recs = []

        # 1. Session Log V3 Recommendation
        if categories["session_log_v3"]:
            recs.append({
                "seam": "DSH-03 / Session Log V3",
                "priority": "HIGH",
                "impact": "Eliminates unlogged system prompts by treating them as surface nodes; enforces canonical envelope integrity.",
                "upstream_evidence": f"{len(categories['session_log_v3'])} commits in upstream (PR #3631, #3809)",
                "actionable_plan": [
                    "Migrate core/tools/utils/sessions_db.py and chat_history_manager.py to accept in-history system events.",
                    "Disallow request/header system prompt injection; enforce system messages as first-class surface nodes in replay.",
                    "Update 'model-visible <=> logged' invariant tests to check canonical V3 envelope format."
                ],
                "target_files": [
                    "core/tools/utils/sessions_db.py",
                    "core/tools/utils/chat_history_manager.py",
                    "core/tests/test_session_replay_evals.py"
                ]
            })

        # 2. Turn Enclosure Invariant
        if categories["turn_enclosure"]:
            recs.append({
                "seam": "DSH-06 / Turn Enclosure Invariant",
                "priority": "CRITICAL",
                "impact": "Guarantees that an open turn and step are ALWAYS finalized with a commit or error node, preventing dangling agent states on exception.",
                "upstream_evidence": f"{len(categories['turn_enclosure'])} commits in upstream (PR #22, #32, ADR-0016)",
                "actionable_plan": [
                    "Wrap agent loop iterations in try/finally blocks that emit turn/end and step/end even on crash.",
                    "Log tool/result explicitly under originating call_id so concurrent or interrupted tool executions never desync.",
                    "Add post-turn error taxonomy handling in orchestrator."
                ],
                "target_files": [
                    "core/tools/infrastructure/orchestrator.py",
                    "core/tools/strategy/capability_resolver.py"
                ]
            })

        # 3. Durable Inbox Projection
        if categories["durable_inbox"]:
            recs.append({
                "seam": "DSH-04 / Durable Inbox Projection",
                "priority": "MEDIUM",
                "impact": "Replaces fragile in-memory task queues with durable inbox projections derived directly from session history.",
                "upstream_evidence": f"{len(categories['durable_inbox'])} commits in upstream (xtr/durable-inbox-recovery)",
                "actionable_plan": [
                    "Allow subagent delegation queues to be completely reconstructed from recorded session events across process restarts.",
                    "Decouple inbox state from ephemeral memory so interrupted tasks resume seamlessly."
                ],
                "target_files": [
                    "core/tools/strategy/delegation_tool.py",
                    "core/tools/execution/claude_code_agent.py"
                ]
            })

        # 4. Code Mode Evaluation
        if categories["code_mode"]:
            recs.append({
                "seam": "DSH-CodeMode / RFC 012",
                "priority": "LOW",
                "impact": "Allows LLM to output small code dispatch scripts that combine multiple tool calls in one shot.",
                "upstream_evidence": f"{len(categories['code_mode'])} commits in upstream (RFC 012)",
                "actionable_plan": [
                    "Evaluate dispatching multi-tool workflows via python script runner.",
                    "Retain safe_exec boundary validation."
                ],
                "target_files": [
                    "core/tools/utils/safe_exec.py"
                ]
            })

        return recs

    def audit(self, fetch: bool = False) -> Dict[str, Any]:
        """Perform full upstream audit and return structured assessment."""
        fetch_status = {"attempted": fetch, "success": False, "message": "Skipped fetch"}
        if fetch:
            success, msg = self.fetch_upstream_tags()
            fetch_status = {"attempted": True, "success": success, "message": msg}

        baseline = self.get_tracked_baseline()
        latest = self.get_latest_tag() or baseline
        is_up_to_date = (baseline == latest)

        commits = self.get_commit_delta(baseline, latest) if not is_up_to_date else []
        categories = self.categorize_commits(commits)
        recommendations = self.generate_porting_recommendations(categories)

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repo_available": self.is_repo_available(),
            "repo_path": str(self.dsh_path),
            "fetch_status": fetch_status,
            "tracked_baseline_tag": baseline,
            "latest_upstream_tag": latest,
            "is_up_to_date": is_up_to_date,
            "total_new_commits": len(commits),
            "category_counts": {k: len(v) for k, v in categories.items()},
            "recommendations": recommendations,
            "recent_upstream_commits": commits[:10],
        }

        # Save telemetry
        try:
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass

        # Generate markdown report
        self.write_markdown_report(result)
        return result

    def write_markdown_report(self, result: Dict[str, Any]) -> None:
        """Render clean markdown summary for human and Nightwatch ingestion."""
        baseline = result["tracked_baseline_tag"]
        latest = result["latest_upstream_tag"]
        total = result["total_new_commits"]
        up_to_date = result["is_up_to_date"]
        time_str = result["timestamp"]

        status_badge = "🟢 ALIGNED" if up_to_date else f"🟡 DELTA DETECTED ({total} commits behind upstream)"

        lines = [
            f"# 📡 DeepSeek Harness Upstream Sentinel Dossier",
            f"**Generated:** {time_str}  ",
            f"**Tracked Baseline:** `{baseline}`  ",
            f"**Latest Upstream:** `{latest}`  ",
            f"**Alignment Status:** {status_badge}  \n",
            f"---",
            f"## 📊 Delta Breakdown",
            f"",
            f"| Architectural Dimension | Incoming Commits | Porting Seam |",
            f"|---|---|---|",
            f"| **Session Log V3 & Envelopes** | {result['category_counts'].get('session_log_v3', 0)} | `DSH-03` |",
            f"| **Turn Enclosure & Loop Balance** | {result['category_counts'].get('turn_enclosure', 0)} | `DSH-06` |",
            f"| **Durable Inbox Projections** | {result['category_counts'].get('durable_inbox', 0)} | `DSH-04` |",
            f"| **Sandbox & Native Landlock** | {result['category_counts'].get('sandbox_security', 0)} | `DSH-02` |",
            f"| **Subagent & Runtime Drivers** | {result['category_counts'].get('subagent_runtime', 0)} | `DSH-04` |",
            f"| **Code Mode (RFC 012)** | {result['category_counts'].get('code_mode', 0)} | `DSH-CodeMode` |",
            f"| **General Architecture & Hygiene** | {result['category_counts'].get('general_architecture', 0)} | Internal |",
            f"",
            f"---",
            f"## 🎯 Actionable Kenbun Porting Recommendations",
            f"",
        ]

        if result["recommendations"]:
            for i, rec in enumerate(result["recommendations"], 1):
                lines.append(f"### {i}. {rec['seam']} [{rec['priority']}]")
                lines.append(f"**Impact:** {rec['impact']}  ")
                lines.append(f"**Evidence:** {rec['upstream_evidence']}  ")
                lines.append(f"**Action Steps:**")
                for step in rec["actionable_plan"]:
                    lines.append(f"- {step}")
                lines.append(f"**Target Files:**")
                for tf in rec["target_files"]:
                    lines.append(f"- `{tf}`")
                lines.append("")
        else:
            lines.append("No critical architectural migrations pending. Kenbun capability seams are fully aligned.")

        lines.extend([
            f"---",
            f"## 📜 Recent Upstream Commits",
            f"",
        ])
        for c in result.get("recent_upstream_commits", []):
            lines.append(f"- `{c['hash'][:10]}` {c['subject']} ({c['author']})")

        try:
            with open(REPORT_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="DeepSeek Harness Upstream Sentinel for Kenbun")
    parser.add_argument("--check", action="store_true", help="Perform fast alignment check")
    parser.add_argument("--fetch", action="store_true", help="Fetch remote tags via HTTPS before checking")
    parser.add_argument("--report", action="store_true", help="Output full markdown report to terminal")
    parser.add_argument("--json", action="store_true", help="Output raw JSON telemetry")
    parser.add_argument("--set-baseline", type=str, help="Update Kenbun tracked baseline tag")

    args = parser.parse_args()
    sentinel = DSHSentinel()

    if args.set_baseline:
        baseline_tag = args.set_baseline.strip()
        data = {}
        if STATUS_FILE.exists():
            try:
                with open(STATUS_FILE, "r") as f:
                    data = json.load(f)
            except Exception:
                pass
        data["tracked_baseline_tag"] = baseline_tag
        with open(STATUS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"{GREEN}✓ Baseline updated to {baseline_tag}{RESET}")
        return

    result = sentinel.audit(fetch=args.fetch)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    baseline = result["tracked_baseline_tag"]
    latest = result["latest_upstream_tag"]
    total = result["total_new_commits"]
    is_aligned = result["is_up_to_date"]

    print(f"\n{BOLD}{MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"  📡 {BOLD}DEEPSEEK HARNESS UPSTREAM SENTINEL{RESET}")
    print(f"{BOLD}{MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"  Tracked Baseline : {CYAN}{baseline}{RESET}")
    print(f"  Latest Upstream  : {CYAN}{latest}{RESET}")

    if is_aligned:
        print(f"  Alignment Status : {GREEN}✓ Fully up to date with upstream release{RESET}")
    else:
        print(f"  Alignment Status : {YELLOW}⚠️ Upstream advanced by {total} commits ({latest}){RESET}")
        print(f"\n  {BOLD}Categorized Deltas:{RESET}")
        for cat, cnt in result["category_counts"].items():
            if cnt > 0:
                print(f"    • {cat.replace('_', ' ').title()}: {CYAN}{cnt}{RESET} commits")

        if result["recommendations"]:
            print(f"\n  {BOLD}Top Porting Priority:{RESET}")
            top_rec = result["recommendations"][0]
            print(f"    ⭐ {YELLOW}{top_rec['seam']}{RESET} [{top_rec['priority']}]")
            print(f"       ↳ {top_rec['impact']}")

    print(f"\n  Telemetry saved to: {BLUE}{STATUS_FILE}{RESET}")
    print(f"  Full brief saved to: {BLUE}{REPORT_FILE}{RESET}\n")

    if args.report:
        if REPORT_FILE.exists():
            with open(REPORT_FILE, "r") as f:
                print(f.read())


if __name__ == "__main__":
    main()
