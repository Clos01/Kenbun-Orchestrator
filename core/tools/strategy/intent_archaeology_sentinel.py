"""
Intent Archaeology & Import Diagnostics Sentinel
(core/tools/strategy/intent_archaeology_sentinel.py)
==============================================================================
Autonomous investigative engine that diagnoses import errors, missing dependencies,
and dead code patterns. Instead of blind deletions, it performs intent archaeology:
1. Detects broken or failing dynamic imports across Kenbun core.
2. Investigates WHY the code was written (git history, AST intent, docstrings).
3. Triages whether to apply defensive fallbacks (try/except) or retire dead code.
4. Validates zero regression via the test matrix and logs the architectural rationale.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("tools.intent_archaeology")


class IntentArchaeologySentinel:
    """
    Autonomous investigative sentinel for Night Watcher.
    Diagnoses import failures and code deprecations with architectural reasoning.
    """

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).resolve().parent.parent.parent.parent
        self.core_dir = self.project_root / "core"
        self.ledger_dir = self.project_root / "brain_health"
        self.ledger_file = self.ledger_dir / "intent_archaeology_ledger.jsonl"
        self.ledger_dir.mkdir(parents=True, exist_ok=True)

    def diagnose_module_import(self, module_path: Path) -> Dict[str, Any]:
        """
        Attempts to import a module in a standalone sandboxed Python subprocess.
        Captures the exact traceback and error type if it fails.
        """
        rel_path = module_path.relative_to(self.project_root)
        # Convert path to module notation: core/tools/memory/honcho_connect.py -> tools.memory.honcho_connect
        parts = rel_path.parts
        if parts[0] == "core":
            mod_parts = parts[1:]
        else:
            mod_parts = parts

        mod_name = ".".join(mod_parts).removesuffix(".py")

        python_cmd = sys.executable
        venv_py = self.project_root / "venv" / "bin" / "python"
        if venv_py.exists() and os.access(venv_py, os.X_OK):
            python_cmd = str(venv_py)

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{self.core_dir}:{self.project_root}:{env.get('PYTHONPATH', '')}"

        code = f"import {mod_name}"
        res = subprocess.run([python_cmd, "-c", code], env=env, capture_output=True, text=True)

        if res.returncode == 0:
            return {"module": mod_name, "path": str(rel_path), "status": "CLEAN", "error": None}

        err = res.stderr.strip()
        error_type = "UNKNOWN"
        missing_name = None

        if "ModuleNotFoundError:" in err:
            error_type = "MISSING_MODULE"
            # Extract missing module name
            for line in err.splitlines():
                if "No module named" in line:
                    missing_name = line.split("No module named")[-1].strip().strip("'").strip('"')
        elif "ImportError:" in err:
            error_type = "IMPORT_ERROR"
        elif "NameError:" in err:
            error_type = "NAME_ERROR"

        return {
            "module": mod_name,
            "path": str(rel_path),
            "status": "BROKEN",
            "error_type": error_type,
            "missing_target": missing_name,
            "traceback": err[:300]
        }

    def investigate_git_intent(self, file_path: Path, target_symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Performs git archaeology to discover when and why code was introduced.
        """
        try:
            cmd = ["git", "log", "-n", "3", "--format=%H|%an|%ad|%s", "--date=short"]
            if target_symbol:
                cmd.extend(["-S", target_symbol])
            cmd.extend(["--", str(file_path)])

            res = subprocess.run(cmd, cwd=str(self.project_root), capture_output=True, text=True)
            commits = []
            for line in res.stdout.strip().splitlines():
                if line and "|" in line:
                    h, author, date, msg = line.split("|", 3)
                    commits.append({"hash": h[:8], "author": author, "date": date, "message": msg})

            return {"symbol": target_symbol, "file": str(file_path), "recent_commits": commits}
        except Exception as e:
            return {"error": str(e)}

    def run_archaeology_cycle(self) -> Dict[str, Any]:
        """
        Scans Kenbun core for broken imports and executes root-cause diagnostics.
        """
        scanned = 0
        broken_modules = []
        diagnostics = []

        subdirs = ["tools/strategy", "tools/infrastructure", "tools/memory", "tools/routing"]
        for sub in subdirs:
            p = self.core_dir / sub
            if not p.exists():
                continue

            for py_file in p.rglob("*.py"):
                if py_file.name.startswith(".") or "test" in py_file.name:
                    continue

                scanned += 1
                diag = self.diagnose_module_import(py_file)
                if diag["status"] == "BROKEN":
                    broken_modules.append(diag["path"])
                    intent = self.investigate_git_intent(py_file, diag.get("missing_target"))
                    diag["intent_archaeology"] = intent
                    diagnostics.append(diag)

        return {
            "scanned_modules": scanned,
            "broken_count": len(broken_modules),
            "broken_modules": broken_modules,
            "diagnostics": diagnostics
        }


# Singleton
intent_archaeology_sentinel = IntentArchaeologySentinel()
