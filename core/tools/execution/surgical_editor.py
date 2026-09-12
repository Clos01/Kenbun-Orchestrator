"""
Surgical Code Editor & Execution Completeness Guardrail
======================================================
Provides Antigravity-grade surgical code replacement, anti-laziness guardrails,
and isolated git worktree experimentation for Kenbun.

Guarantees:
1. Surgical precision: Replaces targeted text blocks character-for-character without
   risking full-file deletion or hallucinated surrounding code removals.
2. Anti-laziness sentinel: Flags and rejects incomplete stubs, empty 'pass' placeholders,
   and '... rest of code remains same' comments.
3. Isolated experimentation: Runs risky refactors in disposable Git worktrees so failed
   experiments never corrupt the main working tree.
"""

import ast
import json
import logging
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.registry import sovereign_tool
from tools.utils.helpers import silence_stdout
from tools.utils.path_utils import get_project_root
from tools.infrastructure.config import settings

logger = logging.getLogger("tools.surgical_editor")


# ============================================================================
# 1. SURGICAL CODE REPLACEMENT
# ============================================================================

@sovereign_tool(name="replace_file_content", category="Execution")
def replace_file_content(
    file_path: str,
    target_content: str,
    replacement_content: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    allow_multiple: bool = False,
    create_backup: bool = True,
) -> str:
    """
    Surgically replaces a contiguous block of text inside a file with strict verification.
    Guarantees that surrounding code is untouched and fails fast if target does not match.

    Args:
        file_path: Absolute or relative path to the file.
        target_content: Exact string to replace (must match character-for-character).
        replacement_content: Complete replacement string.
        start_line: Optional 1-based start line to restrict search scope.
        end_line: Optional 1-based end line to restrict search scope.
        allow_multiple: If True, replaces all occurrences. If False, fails if >1 match found.
        create_backup: Take an automatic safety snapshot before modifying (default True).
    """
    with silence_stdout():
        p = Path(file_path)
        if not p.is_absolute():
            p = get_project_root() / p
        p = p.resolve()

        if not p.exists() or not p.is_file():
            return json.dumps({"status": "error", "message": f"File not found: {p}"})

        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                full_content = f.read()
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Could not read {p}: {e}"})

        lines = full_content.splitlines(keepends=True)
        total_lines = len(lines)

        # 1. Scope restriction by line numbers if provided
        if start_line is not None or end_line is not None:
            s_idx = max(0, (start_line or 1) - 1)
            e_idx = min(total_lines, end_line or total_lines)
            scope_text = "".join(lines[s_idx:e_idx])
            
            if target_content not in scope_text:
                return json.dumps({
                    "status": "error",
                    "error_code": "TARGET_NOT_FOUND_IN_RANGE",
                    "message": f"Target content was not found between lines {s_idx + 1} and {e_idx} of {p.name}. "
                               f"Use view_file to confirm the exact lines and whitespace.",
                    "scope_lines": [s_idx + 1, e_idx],
                })
            
            count_in_scope = scope_text.count(target_content)
            if count_in_scope > 1 and not allow_multiple:
                return json.dumps({
                    "status": "error",
                    "error_code": "AMBIGUOUS_MULTIPLE_MATCHES",
                    "message": f"Found {count_in_scope} occurrences of target content in lines {s_idx + 1}-{e_idx}. "
                               f"Narrow start_line/end_line range or set allow_multiple=True.",
                })
            
            replaced_scope = scope_text.replace(target_content, replacement_content, 1 if not allow_multiple else -1)
            new_content = "".join(lines[:s_idx]) + replaced_scope + "".join(lines[e_idx:])
            matches_replaced = count_in_scope if allow_multiple else 1
        else:
            # Full file scope
            if target_content not in full_content:
                return json.dumps({
                    "status": "error",
                    "error_code": "TARGET_NOT_FOUND",
                    "message": f"Target content was not found in {p.name}. Ensure indentation and characters match exactly.",
                })

            total_matches = full_content.count(target_content)
            if total_matches > 1 and not allow_multiple:
                return json.dumps({
                    "status": "error",
                    "error_code": "AMBIGUOUS_MULTIPLE_MATCHES",
                    "message": f"Found {total_matches} matches for target content across {p.name}. "
                               f"Specify start_line and end_line to pinpoint the edit or set allow_multiple=True.",
                })

            new_content = full_content.replace(target_content, replacement_content, 1 if not allow_multiple else -1)
            matches_replaced = total_matches if allow_multiple else 1

        # 2. Safety checkpoint backup
        if create_backup:
            try:
                from tools.execution.checkpoint_tools import save_checkpoint
                save_checkpoint(str(p), label="pre_surgical_replace")
            except Exception as e:
                logger.debug(f"Safety backup skipped: {e}")

        # 3. Atomic replacement via temporary file (preserving file permissions)
        orig_mode = p.stat().st_mode
        temp_path = p.with_suffix(f".tmp_{uuid.uuid4().hex[:6]}")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(new_content)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(temp_path, orig_mode)
            temp_path.replace(p)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            return json.dumps({"status": "error", "message": f"Failed to write replaced content: {e}"})

        return json.dumps({
            "status": "success",
            "file": str(p),
            "matches_replaced": matches_replaced,
            "bytes_delta": len(new_content) - len(full_content),
            "total_lines_now": new_content.count("\n") + 1,
        }, indent=2)


# ============================================================================
# 2. ANTI-LAZINESS & COMPLETION VERIFICATION GUARDRAIL
# ============================================================================

LAZY_PATTERNS = [
    (r"#\s*TODO\b", "Unresolved TODO marker detected."),
    (r"//\s*TODO\b", "Unresolved TODO marker detected."),
    (r"#\s*FIXME\b", "Unresolved FIXME marker detected."),
    (r"//\s*FIXME\b", "Unresolved FIXME marker detected."),
    (r"(#|//)\s*\.\.\.\s*(rest of|remaining|existing)\b", "Abbreviated code stub ('rest of code remains') detected."),
    (r"(#|//)\s*implement (this|later|here)\b", "Deferred implementation stub detected."),
    (r"raise\s+NotImplementedError\b", "NotImplementedError stub detected."),
]


@sovereign_tool(name="audit_execution_completeness", category="Audit")
def audit_execution_completeness(
    file_path: Optional[str] = None,
    code_content: Optional[str] = None,
    task_objective: str = "",
) -> str:
    """
    Enforces the Zero-Laziness Guardrail. Inspects modified files or code snippets
    to ensure the agent did not skip hard parts, leave placeholder stubs, or truncate code.

    Args:
        file_path: Optional path to inspect on disk.
        code_content: Optional raw code string to inspect.
        task_objective: Description of the task being verified.
    """
    with silence_stdout():
        content = ""
        source_label = "snippet"

        if file_path:
            p = Path(file_path)
            if not p.is_absolute():
                p = get_project_root() / p
            p = p.resolve()
            if not p.exists():
                return json.dumps({"verdict": "ERROR", "message": f"File not found: {p}"})
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                source_label = str(p)
            except Exception as e:
                return json.dumps({"verdict": "ERROR", "message": f"Failed reading {p}: {e}"})
        elif code_content:
            content = code_content
        else:
            return json.dumps({"verdict": "ERROR", "message": "Either file_path or code_content must be provided."})

        violations = []
        for line_num, line in enumerate(content.splitlines(), start=1):
            for pattern, reason in LAZY_PATTERNS:
                if re.search(pattern, line, flags=re.IGNORECASE):
                    violations.append({
                        "line": line_num,
                        "code": line.strip()[:120],
                        "reason": reason,
                    })

        # Python AST check: check for empty function bodies containing only 'pass'
        if source_label.endswith(".py") or not file_path:
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # If body is just a pass or docstring + pass
                        body = node.body
                        if len(body) == 1 and isinstance(body[0], ast.Pass):
                            violations.append({
                                "line": node.lineno,
                                "code": f"def {node.name}(...): pass",
                                "reason": "Empty function body containing only 'pass'.",
                            })
                        elif len(body) == 2 and isinstance(body[0], ast.Expr) and isinstance(body[1], ast.Pass):
                            violations.append({
                                "line": node.lineno,
                                "code": f"def {node.name}(...): [docstring]; pass",
                                "reason": "Function stub contains only docstring and 'pass'.",
                            })
            except Exception:
                pass

        if violations:
            return json.dumps({
                "verdict": "BLOCKED",
                "completeness_score": round(max(0.0, 1.0 - (len(violations) * 0.25)), 2),
                "task_objective": task_objective or "Unspecified task",
                "source": source_label,
                "violations_count": len(violations),
                "violations": violations,
                "remediation": "Replace all placeholder stubs and TODO markers with fully realized, working logic.",
            }, indent=2)

        return json.dumps({
            "verdict": "APPROVED",
            "completeness_score": 1.0,
            "task_objective": task_objective or "Verified task",
            "source": source_label,
            "violations_count": 0,
            "message": "Execution completeness verified. Zero lazy stubs or truncated sections detected.",
        }, indent=2)


# ============================================================================
# 3. EPHEMERAL WORKTREE / EXPERIMENTAL ISOLATION
# ============================================================================

@sovereign_tool(name="run_isolated_experiment", category="Execution")
def run_isolated_experiment(
    command: str,
    experiment_name: str = "",
    auto_merge_on_success: bool = False,
    timeout: int = 120,
) -> str:
    """
    Executes a risky command/refactor in an isolated temporary Git branch/worktree.
    If the experiment fails, the isolated branch is immediately deleted with zero
    risk of breaking the developer's working directory.

    Args:
        command: Shell command to execute inside the isolated worktree.
        experiment_name: Optional label for the experiment.
        auto_merge_on_success: If True, merges clean changes back into current branch.
        timeout: Execution timeout in seconds (default 120).
    """
    with silence_stdout():
        repo_root = get_project_root()
        exp_id = f"exp_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        branch_name = f"sandbox/{experiment_name or exp_id}"
        worktree_dir = repo_root / ".git" / "worktrees" / exp_id

        # 1. Create worktree
        try:
            create_cmd = ["git", "-C", str(repo_root), "worktree", "add", "-b", branch_name, str(worktree_dir)]
            res = subprocess.run(create_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            if res.returncode != 0:
                return json.dumps({"status": "error", "message": f"Failed creating isolated worktree: {res.stderr}"})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Worktree initialization failed: {e}"})

        # 2. Run command in isolated worktree
        start_time = time.time()
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(worktree_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            success = proc.returncode == 0
            stdout_sample = proc.stdout.splitlines()[-30:]
            stderr_sample = proc.stderr.splitlines()[-30:]
        except subprocess.TimeoutExpired:
            success = False
            stdout_sample = []
            stderr_sample = [f"Experiment timed out after {timeout} seconds."]
        except Exception as e:
            success = False
            stdout_sample = []
            stderr_sample = [f"Experiment execution error: {e}"]

        duration = round(time.time() - start_time, 2)

        # 3. Handle outcome & cleanup
        merge_status = "not_requested"
        if success and auto_merge_on_success:
            try:
                # Commit any changes inside worktree
                subprocess.run(["git", "-C", str(worktree_dir), "add", "."], check=False)
                subprocess.run(["git", "-C", str(worktree_dir), "commit", "-m", f"feat(experiment): {experiment_name or exp_id}"], check=False)
                # Merge into current branch
                merge_res = subprocess.run(
                    ["git", "-C", str(repo_root), "merge", "--no-ff", branch_name, "-m", f"merge: {experiment_name or exp_id}"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                merge_status = "merged_successfully" if merge_res.returncode == 0 else f"merge_conflict: {merge_res.stderr}"
            except Exception as e:
                merge_status = f"merge_failed: {e}"

        # Clean up worktree and branch
        try:
            subprocess.run(["git", "-C", str(repo_root), "worktree", "remove", "--force", str(worktree_dir)], check=False)
            if not (success and auto_merge_on_success and "merged_successfully" in merge_status):
                subprocess.run(["git", "-C", str(repo_root), "branch", "-D", branch_name], check=False)
        except Exception:
            pass

        return json.dumps({
            "status": "success" if success else "failed",
            "experiment_id": exp_id,
            "duration_seconds": duration,
            "exit_code": proc.returncode if "proc" in locals() else -1,
            "merge_status": merge_status,
            "stdout_tail": stdout_sample,
            "stderr_tail": stderr_sample,
            "isolation_preserved": True,
        }, indent=2)
