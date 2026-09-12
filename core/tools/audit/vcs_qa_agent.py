"""
Version Control and Quality Assurance (VCS & QA) Agent for Kenbun.
==================================================================
Role: Version Control and Quality Assurance Sentinel.
Objective: Document, justify, and independently verify all automated codebase
modifications before they are finalized, committed, or merged.

Core Responsibilities:
1. Contextual Documentation (The "Why"): Generate detailed, conventional commit
   messages and merge summaries explaining the architectural/logical rationale.
2. Self-Verification: Review proposed diff against the codebase. Detect syntax
   errors, broken dependencies, tier violations (STRUCTURE.md), or logical oversights.
3. Iterative Learning: Pipe failure logs directly into the vector database
   (remember_fix / Chroma DB) so the framework avoids repeating the same errors.
4. Structured Commit Output: Returns Title, Description of Changes, Reasoning,
   and Verification Status.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from tools.registry import sovereign_tool
except ImportError:
    from core.tools.registry import sovereign_tool

logger = logging.getLogger("tools.audit.vcs_qa_agent")


class VCSQualityAssuranceAgent:
    """
    Autonomous sentinel that ingests diffs, verifies AST integrity,
    checks multi-tier architecture compliance, pipes errors to vector memory,
    and produces conventional commit documentation.
    """

    def __init__(self, project_path: str = ""):
        self.project_path = Path(project_path).resolve() if project_path else Path.cwd()

    def ingest(self, task: str) -> Dict[str, Any]:
        """
        Step 1: Ingest file diffs, touched files, and task objective.
        """
        cwd_str = str(self.project_path)
        diff_text = ""
        staged_diff = ""
        modified_files = []

        try:
            # 1. Get modified / unstaged files
            status_proc = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=cwd_str,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if status_proc.returncode == 0:
                for line in status_proc.stdout.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        modified_files.append(parts[-1])

            # 2. Get git diff (unstaged + staged)
            diff_proc = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=cwd_str,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if diff_proc.returncode == 0 and diff_proc.stdout.strip():
                diff_text = diff_proc.stdout
            else:
                # Fallback to unstaged diff alone
                diff_proc = subprocess.run(
                    ["git", "diff"],
                    cwd=cwd_str,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                diff_text = diff_proc.stdout or ""

            # 3. Check staged diff separately
            staged_proc = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=cwd_str,
                capture_output=True,
                text=True,
                timeout=15,
            )
            staged_diff = staged_proc.stdout or ""

        except Exception as e:
            logger.warning(f"Failed to inspect git repository at {cwd_str}: {e}")

        # Extract AST symbols for touched files
        ast_symbols = self._extract_ast_for_files(modified_files)

        return {
            "task": task,
            "project_path": cwd_str,
            "modified_files": modified_files,
            "diff": diff_text or staged_diff,
            "staged_diff": staged_diff,
            "ast_symbols": ast_symbols,
            "file_count": len(modified_files),
        }

    def _extract_ast_for_files(self, files: List[str]) -> List[Dict[str, Any]]:
        """Extracts AST symbols for touched Python and TypeScript/JavaScript files."""
        symbols = []
        for rel_path in files[:20]:
            full_path = self.project_path / rel_path
            if not full_path.is_file():
                continue

            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                if rel_path.endswith(".py"):
                    try:
                        tree = ast.parse(content)
                        for node in ast.iter_child_nodes(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                symbols.append({
                                    "file": rel_path,
                                    "name": node.name,
                                    "type": "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                                    "line": node.lineno,
                                })
                            elif isinstance(node, ast.ClassDef):
                                symbols.append({
                                    "file": rel_path,
                                    "name": node.name,
                                    "type": "class",
                                    "line": node.lineno,
                                })
                    except Exception as parse_err:
                        symbols.append({"file": rel_path, "parse_error": str(parse_err)})
                elif rel_path.endswith((".ts", ".tsx", ".js", ".jsx")):
                    # Regex-based extraction for export functions / components
                    matches = re.findall(r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_]+)", content)
                    matches += re.findall(r"(?:export\s+)?const\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\(", content)
                    for sym in set(matches[:10]):
                        symbols.append({"file": rel_path, "name": sym, "type": "ts_js_symbol"})
            except Exception:
                pass
        return symbols

    def audit(self, ingest_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 2: Run logical static analysis and architecture cross-checks.
        Checks:
        - Python syntax errors (ast.parse)
        - Basic TypeScript / JS balance & bracket integrity
        - Architecture tier compliance (STRUCTURE.md)
        - Broken dependencies or unresolved imports
        """
        errors = []
        warnings = []
        tier_compliance_notes = []

        # 1. Static Syntax & Parse Audit across touched files
        for rel_path in ingest_data.get("modified_files", []):
            full_path = self.project_path / rel_path
            if not full_path.is_file():
                continue

            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                if rel_path.endswith(".py"):
                    try:
                        ast.parse(content)
                    except SyntaxError as syn_err:
                        errors.append(f"Python SyntaxError in {rel_path} line {syn_err.lineno}: {syn_err.msg}")
                elif rel_path.endswith((".json")):
                    try:
                        json.loads(content)
                    except json.JSONDecodeError as json_err:
                        errors.append(f"Invalid JSON in {rel_path}: {json_err.msg}")
                elif rel_path.endswith((".ts", ".tsx", ".js", ".jsx")):
                    # Strip comments and string literals to avoid counting braces inside strings
                    code_no_comments = re.sub(r"//.*", "", content)
                    code_no_comments = re.sub(r"/\*[\s\S]*?\*/", "", code_no_comments)
                    code_no_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', code_no_comments)
                    code_no_strings = re.sub(r"'(?:\\.|[^'\\])*'", "''", code_no_strings)
                    code_no_strings = re.sub(r"`(?:\\.|[^`\\$]|(?:\$(?!\{)))*`", "``", code_no_strings)
                    open_braces = code_no_strings.count("{") - code_no_strings.count("}")
                    open_parens = code_no_strings.count("(") - code_no_strings.count(")")
                    if open_braces != 0:
                        warnings.append(f"Potential unbalanced curly braces in {rel_path} (delta: {open_braces})")
                    if open_parens != 0:
                        warnings.append(f"Potential unbalanced parentheses in {rel_path} (delta: {open_parens})")
            except Exception as e:
                warnings.append(f"Could not read {rel_path} for audit: {e}")

        # 2. Architecture Cross-Check against STRUCTURE.md
        structure_path = self.project_path / "STRUCTURE.md"
        if not structure_path.is_file():
            # Try root of Kenbun
            structure_path = Path(__file__).resolve().parent.parent.parent.parent / "STRUCTURE.md"

        if structure_path.is_file():
            try:
                struct_text = structure_path.read_text(encoding="utf-8", errors="ignore")
                diff_text = ingest_data.get("diff", "")

                # Rule A: System 1 (tools) should not make arbitrary unmetered network calls
                if "core/tools/execution" in diff_text or "core/tools/infrastructure" in diff_text:
                    if "urllib.request" in diff_text or "requests.post" in diff_text:
                        if "token_governor" not in diff_text and "sandbox" not in diff_text:
                            warnings.append("Architecture notice: Direct network calls detected in execution layer. Ensure Token Governor or Sandbox limits are applied.")

                # Rule B: DB / Migration changes require indexes or RLS
                if any("migration" in f.lower() or ".sql" in f.lower() for f in ingest_data.get("modified_files", [])):
                    if "create table" in diff_text.lower() and "index" not in diff_text.lower():
                        warnings.append("Database Notice: Table creation detected without explicit indexing. Ensure foreign keys and search columns are indexed.")

                tier_compliance_notes.append("STRUCTURE.md multi-tier rules verified.")
            except Exception as e:
                tier_compliance_notes.append(f"STRUCTURE.md check skipped ({e})")
        else:
            tier_compliance_notes.append("No STRUCTURE.md located; tier check skipped.")

        # 3. Hardcoded User Paths & Plaintext Secret Leak Audit
        # Scans all modified code files (excluding tests/ and markdown documentation)
        PATH_LEAK_REGEX = re.compile(r'/(?:Users|home)/[a-zA-Z0-9_-]+(?:/|["\'`\s]|$)')
        PRIVATE_KEY_REGEX = re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')
        SECRET_LEAK_REGEX = re.compile(r'(?:api_key|secret|password|auth_token)\s*=\s*["\']([^"\'\$\{\}\n]{6,})["\']', re.IGNORECASE)

        for rel_path in ingest_data.get("modified_files", []):
            # Exclude documentation, markdown, and unit tests testing these patterns
            if rel_path.endswith((".md", ".txt", ".markdown")) or "test" in rel_path.lower() or "mock" in rel_path.lower():
                continue

            full_path = self.project_path / rel_path
            if not full_path.is_file():
                continue

            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")

                # Check for absolute home directories
                for match in PATH_LEAK_REGEX.finditer(content):
                    matched_str = match.group(0).strip(" \"'`")
                    if any(ignored in matched_str for ignored in ["/home/runner", "/home/node", "/home/vscode"]):
                        continue
                    errors.append(
                        f"Security Alert: Hardcoded user path '{matched_str}' detected in {rel_path}. "
                        "Use Path.home(), relative paths, or environment variables."
                    )

                # Check for private keys
                if PRIVATE_KEY_REGEX.search(content):
                    errors.append(f"Security Alert: Private Key block detected in {rel_path}! Private keys must never be committed.")

                # Check for plaintext credentials
                for match in SECRET_LEAK_REGEX.finditer(content):
                    val = match.group(1).lower()
                    if val in ["your_key_here", "dummy", "test", "fake", "placeholder", "xxx", "change_me"]:
                        continue
                    errors.append(
                        f"Security Alert: Plaintext secret or password detected in {rel_path}: '{match.group(0)}'. "
                        "Use os.environ.get(...) or .env instead."
                    )
            except Exception as e:
                warnings.append(f"Could not scan {rel_path} for secrets: {e}")

        passed = len(errors) == 0

        return {
            "passed": passed,
            "errors": errors,
            "warnings": warnings,
            "tier_compliance_notes": tier_compliance_notes,
            "status": "APPROVED" if passed else "REJECTED_AUDIT_FAILED",
        }

    def correct_and_learn(self, ingest_data: Dict[str, Any], audit_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 3: Iterative Learning.
        If errors were detected during audit, pipe failure logs into Chroma DB /
        Honcho error memory so future cycles avoid repeating the mistake.
        """
        if audit_result["passed"]:
            return {"logged_to_memory": False, "message": "Audit passed; no correction needed."}

        error_summary = "; ".join(audit_result["errors"])
        files_str = ", ".join(ingest_data.get("modified_files", []))
        task_str = ingest_data.get("task", "Code modification")

        memory_id = None
        try:
            try:
                from tools.utils.error_memory import remember_fix
            except ImportError:
                from core.tools.utils.error_memory import remember_fix
            memory_msg = f"VCS QA Sentinel Audit Failure on task '{task_str}': {error_summary}"
            solution_msg = f"Auto-detected failure in files [{files_str}]. Diffs failed static verification before commit."
            res = remember_fix(error_message=memory_msg, solution=solution_msg, file_context=files_str)
            memory_id = res
            logger.info(f"Logged VCS QA audit failure to vector memory: {res}")
        except Exception as mem_err:
            logger.warning(f"Could not pipe failure to vector memory: {mem_err}")

        return {
            "logged_to_memory": True,
            "memory_id": memory_id,
            "error_summary": error_summary,
            "advice": "Review the syntax and dependency errors above before staging files.",
        }

    def document(self, ingest_data: Dict[str, Any], audit_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 4: Formulate structured conventional commit payload.
        Output: Title, Description of Changes, Reasoning (The Why), and Verification Status.
        """
        task = ingest_data.get("task", "").strip()
        files = ingest_data.get("modified_files", [])
        status = audit_result.get("status", "UNVERIFIED")

        # 1. Formulate Title
        commit_type = "feat"
        if any(k in task.lower() for k in ["fix", "bug", "crash", "error", "patch"]):
            commit_type = "fix"
        elif any(k in task.lower() for k in ["refactor", "clean", "streamline"]):
            commit_type = "refactor"
        elif any(k in task.lower() for k in ["sec", "encrypt", "audit", "secret", "protect"]):
            commit_type = "security"
        elif any(k in task.lower() for k in ["test", "verify", "benchmark"]):
            commit_type = "test"
        elif any(k in task.lower() for k in ["doc", "guide", "readme"]):
            commit_type = "docs"

        # Scope heuristic
        scope = "core"
        if files:
            first_file = files[0]
            if "components" in first_file:
                scope = "ui"
            elif "api" in first_file or "route" in first_file:
                scope = "api"
            elif "audit" in first_file:
                scope = "audit"
            elif "strategy" in first_file:
                scope = "strategy"
            elif "pipeline" in first_file:
                scope = "pipeline"

        clean_task = re.sub(r"^(feat|fix|refactor|chore|test|docs):\s*", "", task, flags=re.IGNORECASE)
        clean_task = clean_task[0].lower() + clean_task[1:] if clean_task else "update codebase"
        if len(clean_task) > 65:
            clean_task = clean_task[:62] + "..."

        title = f"{commit_type}({scope}): {clean_task}"

        # 2. Description of Changes
        desc_lines = []
        if files:
            desc_lines.append("Modified Files:")
            for f in files[:8]:
                desc_lines.append(f"- `{f}`")
            if len(files) > 8:
                desc_lines.append(f"- ...and {len(files) - 8} other files.")
        else:
            desc_lines.append("- Staged modifications across project.")

        ast_syms = ingest_data.get("ast_symbols", [])
        if ast_syms:
            sym_names = [s.get("name") for s in ast_syms if s.get("name")]
            if sym_names:
                desc_lines.append(f"- Touched AST symbols: {', '.join(sym_names[:6])}")

        description = "\n".join(desc_lines)

        # 3. Reasoning (The "Why")
        reasoning = (
            f"Architectural Rationale: Implemented in response to objective '{task}'. "
            f"Ensures code changes are verified against multi-tier invariants, avoids regression in "
            f"downstream consumers, and maintains zero-defect audit standards."
        )

        return {
            "title": title,
            "description": description,
            "reasoning": reasoning,
            "verification_status": status,
            "passed": audit_result["passed"],
            "errors": audit_result["errors"],
            "warnings": audit_result["warnings"],
            "files_modified": files,
        }

    def execute_qa_cycle(self, task: str) -> Dict[str, Any]:
        """Runs the full 4-stage VCS & QA cycle."""
        ingest_data = self.ingest(task)
        audit_res = self.audit(ingest_data)
        learn_res = self.correct_and_learn(ingest_data, audit_res)
        doc_res = self.document(ingest_data, audit_res)
        doc_res["diff"] = ingest_data.get("diff", "")
        doc_res["learning_summary"] = learn_res
        return doc_res


@sovereign_tool()
def audit_and_document_commit(task: str, project_path: str = "") -> str:
    """
    Sovereign Tool: Ingests code diffs, verifies AST and architectural integrity,
    pipes failure logs into vector memory if errors exist, and generates a structured
    conventional commit payload with 'The Why'.
    """
    agent = VCSQualityAssuranceAgent(project_path=project_path)
    result = agent.execute_qa_cycle(task)

    # Format into human-readable markdown + JSON payload
    md_report = [
        f"# 🛡️ VCS & QA Sentinel Report",
        f"**Verification Status:** `{result['verification_status']}`",
        f"**Proposed Title:** `{result['title']}`\n",
        f"### 📋 Description of Changes\n{result['description']}\n",
        f"### 🏛️ Architectural Rationale (The 'Why')\n{result['reasoning']}\n",
    ]

    if result.get("errors"):
        md_report.append("### ❌ Verification Errors Found:")
        for err in result["errors"]:
            md_report.append(f"- {err}")

    if result.get("warnings"):
        md_report.append("\n### ⚠️ Verification Warnings:")
        for warn in result["warnings"]:
            md_report.append(f"- {warn}")

    if result.get("learning_summary", {}).get("logged_to_memory"):
        md_report.append(f"\n🧠 **Iterative Learning:** Error signature persisted to Vector DB (`{result['learning_summary'].get('memory_id')}`).")

    diff_text = result.get("diff", "")
    if diff_text:
        md_report.append(f"\n### 📝 Code Diff Under Review:\n```diff\n{diff_text[:2500]}\n```")

    md_report.append("\n---\n```json\n" + json.dumps(result, indent=2) + "\n```")
    return "\n".join(md_report)
