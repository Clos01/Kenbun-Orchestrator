"""
OOM-Safe High-Efficiency Code Inspection & Background Task Harness
===================================================================
Provides memory-safe, sliding-window inspection, sub-second host regex
searching, and detached background process orchestration for Kenbun.

Prevents Out-Of-Memory (OOM) crashes and context window flooding by:
1. Delegating searches to host-level ripgrep/git-grep/grep with strict result caps.
2. Slicing file contents into small, line-numbered windows (default <= 200 lines).
3. Offloading long-running jobs (tests, builds) into detached background processes
   whose outputs stream to disk logs rather than flooding the agent reasoning buffer.
"""

import ast
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.registry import sovereign_tool
from tools.utils.helpers import silence_stdout
from tools.utils.path_utils import get_project_root
from tools.infrastructure.config import settings

logger = logging.getLogger("tools.oom_safe_harness")


def _get_tasks_dir() -> Path:
    """Returns the directory used for background task logs and state."""
    task_dir = settings.BRAIN_HEALTH_DIR / "tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


# ============================================================================
# 1. HOST-LEVEL REGEX SEARCH (RIPGREP / GIT-GREP / GREP / PYTHON SIMD FALLBACK)
# ============================================================================

DEFAULT_IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".ruff_cache", "dist", "build", ".idea", ".vscode"
}


def _run_ripgrep(
    query: str,
    search_path: Path,
    includes: Optional[str],
    case_insensitive: bool,
    max_results: int,
    is_regex: bool,
) -> Optional[List[Dict[str, Any]]]:
    """Attempts fast search via host `rg` binary."""
    rg_bin = shutil.which("rg")
    if not rg_bin:
        return None

    cmd = [
        rg_bin,
        "--line-number",
        "--color=never",
        "--no-heading",
        "--max-count", str(max_results),
    ]
    if case_insensitive:
        cmd.append("-i")
    if not is_regex:
        cmd.append("-F")
    if includes:
        for inc in includes.split(","):
            inc = inc.strip()
            if inc:
                cmd.extend(["-g", inc])

    for ig in DEFAULT_IGNORED_DIRS:
        cmd.extend(["-g", f"!{ig}"])

    cmd.extend(["--", query, str(search_path)])

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        results = []
        for line in proc.stdout.splitlines():
            if len(results) >= max_results:
                break
            # Format: <file>:<line>:<content>
            parts = line.split(":", 2)
            if len(parts) == 3:
                results.append({
                    "file": os.path.relpath(parts[0], str(search_path)),
                    "line": int(parts[1]),
                    "content": parts[2].strip(),
                })
        return results
    except Exception as e:
        logger.debug(f"ripgrep execution failed: {e}")
        return None


def _run_git_grep(
    query: str,
    search_path: Path,
    case_insensitive: bool,
    max_results: int,
    is_regex: bool,
) -> Optional[List[Dict[str, Any]]]:
    """Attempts fast search via `git grep` within repository root."""
    git_bin = shutil.which("git")
    if not git_bin:
        return None

    cmd = [git_bin, "-C", str(search_path), "grep", "-nI"]
    if case_insensitive:
        cmd.append("-i")
    if not is_regex:
        cmd.append("-F")
    else:
        cmd.append("-E")
    cmd.extend(["--", query])

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        if proc.returncode not in (0, 1):
            return None

        results = []
        for line in proc.stdout.splitlines():
            if len(results) >= max_results:
                break
            parts = line.split(":", 2)
            if len(parts) == 3:
                results.append({
                    "file": parts[0],
                    "line": int(parts[1]),
                    "content": parts[2].strip(),
                })
        return results
    except Exception as e:
        logger.debug(f"git grep failed: {e}")
        return None


def _run_python_search_fallback(
    query: str,
    search_path: Path,
    includes: Optional[str],
    case_insensitive: bool,
    max_results: int,
    is_regex: bool,
) -> List[Dict[str, Any]]:
    """Safe chunked Python regex scanner fallback if native tools are absent."""
    flags = re.IGNORECASE if case_insensitive else 0
    pattern = re.compile(query if is_regex else re.escape(query), flags)
    
    include_exts = None
    if includes:
        include_exts = {inc.strip().lower() for inc in includes.split(",") if inc.strip()}

    results = []
    for root, dirs, files in os.walk(str(search_path)):
        dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORED_DIRS and not d.startswith(".")]
        for file in files:
            if include_exts:
                if not any(file.lower().endswith(ext.lstrip("*")) for ext in include_exts):
                    continue

            full_path = Path(root) / file
            rel_file = os.path.relpath(str(full_path), str(search_path))
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, start=1):
                        if pattern.search(line):
                            results.append({
                                "file": rel_file,
                                "line": line_num,
                                "content": line.strip()[:300],
                            })
                            if len(results) >= max_results:
                                return results
            except Exception:
                continue

    return results


@sovereign_tool(name="ripgrep_search", category="Execution")
def ripgrep_search(
    query: str,
    search_path: str = "",
    includes: Optional[str] = None,
    excludes: Optional[str] = None,
    case_insensitive: bool = True,
    max_results: int = 50,
    is_regex: bool = True,
) -> str:
    """
    Blazing fast host-level code search using Rust ripgrep / git-grep with memory-safe result capping.
    Scans entire codebases in milliseconds without loading files into LLM context window.

    Args:
        query: String or regex to match.
        search_path: Directory or file to search (defaults to Kenbun project root).
        includes: Comma-separated file extensions or glob patterns (e.g. '*.py,*.ts').
        excludes: Comma-separated directory names to skip.
        case_insensitive: Case-insensitive search (default True).
        max_results: Maximum results to return to protect LLM context (default 50).
        is_regex: Treat query as a regex expression (default True).
    """
    with silence_stdout():
        target_dir = Path(search_path).resolve() if search_path else get_project_root()
        if not target_dir.exists():
            return json.dumps({"error": f"Search path not found: {target_dir}", "results": []})

        engine = "ripgrep"
        results = _run_ripgrep(query, target_dir, includes, case_insensitive, max_results, is_regex)
        if results is None:
            engine = "git-grep"
            results = _run_git_grep(query, target_dir, case_insensitive, max_results, is_regex)
        if results is None:
            engine = "python-scanner"
            results = _run_python_search_fallback(query, target_dir, includes, case_insensitive, max_results, is_regex)

        capped = len(results) >= max_results
        return json.dumps({
            "query": query,
            "engine": engine,
            "count": len(results),
            "capped": capped,
            "results": results,
        }, indent=2)


# ============================================================================
# 2. SURGICAL SLIDING-WINDOW CODE VIEWER
# ============================================================================

def _extract_ast_symbols(file_path: Path) -> List[Dict[str, Any]]:
    """Extracts high-level class and function signatures without full implementation code."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
        symbols = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                doc = ast.get_docstring(node) or ""
                symbols.append({
                    "name": node.name,
                    "kind": kind,
                    "line": getattr(node, "lineno", 0),
                    "docstring": doc.strip().split("\n")[0] if doc else "",
                })
        symbols.sort(key=lambda s: s["line"])
        return symbols
    except Exception as e:
        return [{"error": f"Failed to parse AST symbols: {e}"}]


@sovereign_tool(name="view_file", category="Execution")
def view_file(
    file_path: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
    max_lines: int = 200,
    symbols_only: bool = False,
) -> str:
    """
    Surgically inspects a bounded window of code with 1-based line numbers.
    Prevents Out-Of-Memory errors by capping line counts and avoiding full-file dumps.

    Args:
        file_path: Absolute or relative path to the target file.
        start_line: 1-indexed start line number (default 1).
        end_line: 1-indexed end line number (inclusive). If omitted, shows up to max_lines.
        max_lines: Maximum number of lines permitted per read (default 200).
        symbols_only: If True, returns class/function signatures only (outline mode).
    """
    with silence_stdout():
        p = Path(file_path)
        if not p.is_absolute():
            p = get_project_root() / p
        p = p.resolve()

        if not p.exists() or not p.is_file():
            return f"❌ File not found: {p}"

        if symbols_only:
            symbols = _extract_ast_symbols(p)
            return json.dumps({
                "file": str(p),
                "mode": "symbols_only",
                "symbols_count": len(symbols),
                "symbols": symbols,
            }, indent=2)

        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            return f"❌ Could not read file {p}: {e}"

        total_lines = len(lines)
        if total_lines == 0:
            return f"File {p.name} is empty (0 lines)."

        start = max(1, start_line)
        if end_line is None:
            end = min(total_lines, start + max_lines - 1)
        else:
            end = min(total_lines, max(start, end_line))

        # Enforce max window cap
        if end - start + 1 > max_lines:
            end = start + max_lines - 1

        selected = lines[start - 1:end]
        formatted = [
            f"File: {p}",
            f"Lines: {start} to {end} of {total_lines}",
            "---",
        ]
        for i, line in enumerate(selected, start=start):
            formatted.append(f"{i:4d}: {line.rstrip()}")

        if end < total_lines:
            formatted.append(f"--- ({total_lines - end} more lines remaining)")

        return "\n".join(formatted)


# ============================================================================
# 3. ATOMIC SAFE FILE WRITER
# ============================================================================

@sovereign_tool(name="write_to_file", category="Execution")
def write_to_file(
    file_path: str,
    content: str,
    overwrite: bool = True,
    create_backup: bool = True,
) -> str:
    """
    Atomically writes content to a file with automatic parent directory creation
    and optional safety backup checkpointing.

    Args:
        file_path: Absolute or relative path to the target file.
        content: String code content to write.
        overwrite: Overwrite if file already exists (default True).
        create_backup: Create a backup checkpoint before overwriting (default True).
    """
    with silence_stdout():
        p = Path(file_path)
        if not p.is_absolute():
            p = get_project_root() / p
        p = p.resolve()

        if p.exists() and not overwrite:
            return f"❌ Error: File {p} already exists and overwrite=False."

        p.parent.mkdir(parents=True, exist_ok=True)

        # Create backup if file exists
        if p.exists() and create_backup:
            try:
                from tools.execution.checkpoint_tools import save_checkpoint
                save_checkpoint(str(p), label="auto_pre_write")
            except Exception as e:
                logger.debug(f"Checkpoint creation skipped: {e}")

        # Atomic temp-write and replace
        temp_file = p.with_suffix(f".tmp_{uuid.uuid4().hex[:6]}")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            temp_file.replace(p)
            return json.dumps({
                "status": "success",
                "file": str(p),
                "bytes_written": len(content.encode("utf-8")),
                "lines": content.count("\n") + 1,
            })
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            return json.dumps({"status": "error", "message": f"Failed to write {p}: {e}"})


# ============================================================================
# 4. BACKGROUND SUBPROCESS PIPELINES & TASK MANAGER
# ============================================================================

@sovereign_tool(name="spawn_background_task", category="Execution")
def spawn_background_task(
    command: str,
    cwd: str = "",
    task_name: str = "",
) -> str:
    """
    Launches a long-running command (tests, builds, linter sweeps) as a detached
    background process. Streams outputs to disk logs instead of flooding LLM context.

    Args:
        command: Shell command string to execute.
        cwd: Working directory (defaults to Kenbun project root).
        task_name: Optional human-readable name for the task.
    """
    with silence_stdout():
        work_dir = Path(cwd).resolve() if cwd else get_project_root()
        tasks_dir = _get_tasks_dir()

        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        log_path = tasks_dir / f"{task_id}.log"
        meta_path = tasks_dir / f"{task_id}.json"

        # Open logfile for child stdout/stderr
        log_file = open(log_path, "w", encoding="utf-8")

        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=str(work_dir),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # Process group isolation
            )
        except Exception as e:
            log_file.close()
            return json.dumps({"status": "error", "message": f"Failed to spawn task: {e}"})

        meta = {
            "task_id": task_id,
            "task_name": task_name or command[:40],
            "command": command,
            "cwd": str(work_dir),
            "pid": proc.pid,
            "start_time": time.time(),
            "status": "RUNNING",
            "log_path": str(log_path),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return json.dumps({
            "status": "spawned",
            "task_id": task_id,
            "pid": proc.pid,
            "log_path": str(log_path),
            "command": command,
        }, indent=2)


def _is_process_active(pid: int) -> Tuple[bool, Optional[int]]:
    """Checks whether a process with given PID is still actively running (not zombie/dead)."""
    if pid <= 0:
        return False, None

    # 1. If direct child, check waitpid to reap and get exact exit code
    try:
        wpid, wstatus = os.waitpid(pid, os.WNOHANG)
        if wpid == pid:
            exit_code = os.waitstatus_to_exitcode(wstatus) if hasattr(os, "waitstatus_to_exitcode") else (wstatus >> 8)
            return False, exit_code
    except (ChildProcessError, OSError):
        pass

    # 2. Check via /proc/{pid}/status if available
    try:
        proc_status_path = Path(f"/proc/{pid}/status")
        if proc_status_path.exists():
            content = proc_status_path.read_text()
            for line in content.splitlines():
                if line.startswith("State:"):
                    if "Z" in line:
                        return False, 0
                    return True, None
    except Exception:
        pass

    # 3. Fallback check via signal 0
    try:
        os.kill(pid, 0)
        return True, None
    except (OSError, ProcessLookupError):
        return False, None


@sovereign_tool(name="get_background_task_status", category="Execution")
def get_background_task_status(task_id: str, tail_lines: int = 40) -> str:
    """
    Checks the execution status and retrieves tail logs for a background task.

    Args:
        task_id: The unique task identifier returned by spawn_background_task.
        tail_lines: Number of trailing log lines to retrieve (default 40).
    """
    with silence_stdout():
        tasks_dir = _get_tasks_dir()
        meta_path = tasks_dir / f"{task_id}.json"
        log_path = tasks_dir / f"{task_id}.log"

        if not meta_path.exists():
            return json.dumps({"error": f"Task '{task_id}' not found."})

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            return json.dumps({"error": f"Could not read task meta: {e}"})

        pid = meta.get("pid")
        is_active, detected_exit = _is_process_active(pid) if pid else (False, None)
        if detected_exit is not None and meta.get("exit_code") is None:
            meta["exit_code"] = detected_exit

        if not is_active:
            if meta.get("status") not in ("KILLED", "FAILED"):
                meta["status"] = "COMPLETED" if meta.get("exit_code", 0) == 0 else "FAILED"
        else:
            meta["status"] = "RUNNING"

        # Update saved meta state
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass

        # Read tail lines from log
        tail = []
        if log_path.exists():
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                    tail = [line.rstrip() for line in all_lines[-tail_lines:]]
            except Exception:
                tail = ["[Could not read log file]"]

        meta["log_tail"] = tail
        meta["duration_seconds"] = round(time.time() - meta.get("start_time", time.time()), 2)

        return json.dumps(meta, indent=2)


@sovereign_tool(name="kill_background_task", category="Execution")
def kill_background_task(task_id: str) -> str:
    """
    Terminates a running background task process group.

    Args:
        task_id: The unique task identifier to terminate.
    """
    with silence_stdout():
        tasks_dir = _get_tasks_dir()
        meta_path = tasks_dir / f"{task_id}.json"

        if not meta_path.exists():
            return json.dumps({"error": f"Task '{task_id}' not found."})

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            return json.dumps({"error": f"Could not read task meta: {e}"})

        pid = meta.get("pid")
        if not pid:
            return json.dumps({"status": "error", "message": "No PID found for task."})

        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
            time.sleep(0.05)
            try:
                os.kill(pid, 0)
                os.killpg(pgid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
            try:
                os.waitpid(pid, os.WNOHANG)
            except (ChildProcessError, OSError):
                pass
            meta["status"] = "KILLED"
            meta["exit_code"] = -9
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            return json.dumps({"status": "killed", "task_id": task_id, "pid": pid})
        except (OSError, ProcessLookupError):
            meta["status"] = "KILLED"
            meta["exit_code"] = -9
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            return json.dumps({"status": "already_stopped", "task_id": task_id, "pid": pid})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to kill PID {pid}: {e}"})


@sovereign_tool(name="list_background_tasks", category="Execution")
def list_background_tasks(limit: int = 10) -> str:
    """
    Lists recent background tasks, their active status, and log locations.

    Args:
        limit: Max number of recent tasks to return (default 10).
    """
    with silence_stdout():
        tasks_dir = _get_tasks_dir()
        meta_files = sorted(tasks_dir.glob("task_*.json"), key=os.path.getmtime, reverse=True)

        tasks = []
        for mf in meta_files[:limit]:
            try:
                with open(mf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Check live status
                pid = data.get("pid")
                if pid:
                    try:
                        os.kill(pid, 0)
                        data["status"] = "RUNNING"
                    except (OSError, ProcessLookupError):
                        if data.get("status") == "RUNNING":
                            data["status"] = "COMPLETED"
                tasks.append(data)
            except Exception:
                continue

        return json.dumps({"tasks": tasks, "total": len(tasks)}, indent=2)
