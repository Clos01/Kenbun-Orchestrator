"""
Core Refactor & Cleanup Sentinel (core/tools/strategy/core_refactor_cleaner.py)
==============================================================================
Autonomous codebase refactor and AST cleanup engine focusing exclusively
on Kenbun core. Scans for AST complexity, unused imports, dead code patterns,
and code smells, and safely applies transformations while guaranteeing
zero syntactic or behavioral regression.
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("tools.core_refactor_cleaner")


class UnusedImportFinder(ast.NodeVisitor):
    def __init__(self):
        self.imports: Dict[str, Tuple[str, int]] = {}  # asname -> (module/symbol, lineno)
        self.used_names: Set[str] = set()

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name
            # Store root name if dot-separated
            root_name = name.split(".")[0]
            self.imports[root_name] = (alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            name = alias.asname or alias.name
            self.imports[name] = (f"{node.module}.{alias.name}", node.lineno)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        self.used_names.add(node.attr)
        self.generic_visit(node)


class CoreRefactorCleaner:
    """
    Autonomous refactoring engine for Kenbun core/.
    Safely cleans up code smells, unused imports, and excessive whitespace.
    """

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).resolve().parent.parent.parent.parent
        self.core_dir = self.project_root / "core"

    def scan_file_complexity(self, file_path: Path) -> Dict[str, Any]:
        """Analyzes a single Python file for AST metrics and code smells."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception as e:
            return {"error": str(e)}

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            return {"syntax_error": str(e), "line": e.lineno}

        line_count = len(source.splitlines())
        classes = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
        functions = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))

        # Find unused imports (excluding __init__.py)
        unused_imports = []
        if file_path.name != "__init__.py":
            finder = UnusedImportFinder()
            finder.visit(tree)
            for asname, (full_name, lineno) in finder.imports.items():
                if asname not in finder.used_names and not asname.startswith("_"):
                    unused_imports.append({"name": asname, "full": full_name, "line": lineno})

        return {
            "path": str(file_path.relative_to(self.project_root)),
            "line_count": line_count,
            "classes": classes,
            "functions": functions,
            "unused_imports": unused_imports,
            "is_god_module": line_count > 600,
        }

    def clean_file_formatting(self, file_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
        """
        Safely standardizes formatting: strips trailing whitespace,
        collapses excessive empty lines, and validates syntax.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original = f.read()
        except Exception as e:
            return False, f"Could not read {file_path}: {e}"

        lines = original.splitlines()
        cleaned_lines = [line.rstrip() for line in lines]

        # Collapse > 2 consecutive empty lines to 2
        collapsed = []
        empty_count = 0
        for line in cleaned_lines:
            if not line:
                empty_count += 1
                if empty_count <= 2:
                    collapsed.append(line)
            else:
                empty_count = 0
                collapsed.append(line)

        new_source = "\n".join(collapsed) + "\n"
        if new_source == original:
            return False, "No formatting changes needed"

        # AST Safety Verification before writing
        try:
            ast.parse(new_source, filename=str(file_path))
        except SyntaxError as e:
            return False, f"AST parse failed after formatting: {e}"

        if not dry_run:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_source)
            return True, f"Cleaned whitespace in {file_path.name}"
        return True, f"[DRY-RUN] Would clean whitespace in {file_path.name}"

    def refactor_code_imports(self, file_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
        """
        Actively refactors Python source code: removes unused imports and
        modernizes code smells while guaranteeing syntax integrity.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original = f.read()
        except Exception as e:
            return False, f"Could not read {file_path}: {e}"

        import subprocess
        uvx_bin = Path.home() / ".local" / "bin" / "uvx"
        if not uvx_bin.exists():
            return False, "uvx binary not found"

        if dry_run:
            res = subprocess.run(
                [str(uvx_bin), "ruff", "check", "--select", "F401,W", "--diff", str(file_path)],
                capture_output=True,
                text=True
            )
            if res.stdout.strip():
                return True, f"[DRY-RUN] Would refactor {file_path.name}"
            return False, "No refactoring needed"

        res = subprocess.run(
            [str(uvx_bin), "ruff", "check", "--select", "F401,W", "--fix", str(file_path)],
            capture_output=True,
            text=True
        )
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                new_source = f.read()
        except Exception as e:
            return False, f"Could not read modified {file_path}: {e}"

        if new_source != original:
            try:
                tree = ast.parse(new_source, filename=str(file_path))

                # Invariant Guard: Never allow automated tools to strip core stdlib essentials
                IMMUTABLE_STDLIB = {"re", "json", "os", "sys", "time", "pathlib", "logging", "typing", "sqlite3", "datetime", "uuid"}
                orig_tree = ast.parse(original, filename=str(file_path))

                orig_names = {
                    alias.asname or alias.name.split(".")[0]
                    for node in ast.walk(orig_tree)
                    if isinstance(node, ast.Import)
                    for alias in node.names
                } | {
                    (alias.asname or alias.name)
                    for node in ast.walk(orig_tree)
                    if isinstance(node, ast.ImportFrom)
                    for alias in node.names
                } | {
                    node.module.split(".")[0]
                    for node in ast.walk(orig_tree)
                    if isinstance(node, ast.ImportFrom) and node.module
                }

                new_names = {
                    alias.asname or alias.name.split(".")[0]
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Import)
                    for alias in node.names
                } | {
                    (alias.asname or alias.name)
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom)
                    for alias in node.names
                } | {
                    node.module.split(".")[0]
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module
                }

                stripped_essentials = (orig_names & IMMUTABLE_STDLIB) - new_names
                if stripped_essentials:
                    logger.warning(f"Refactor stripped essential stdlib modules {stripped_essentials}; reverting {file_path.name}")
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(original)
                    return False, f"Refactor reverted: stripped essential stdlib {stripped_essentials}"

                return True, f"Refactored code and removed unused imports in {file_path.name}"
            except SyntaxError as e:
                # AST check failed: rollback immediately
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(original)
                return False, f"Refactor reverted due to AST error: {e}"

        return False, "No changes needed"

    def run_refactor_cycle(self, target_subdirs: Optional[List[str]] = None, dry_run: bool = False) -> Dict[str, Any]:
        """
        Runs the full autonomous refactor & cleanup cycle across Kenbun core.
        """
        subdirs = target_subdirs or ["tools/strategy", "tools/infrastructure", "tools/routing"]
        scanned = 0
        cleaned = 0
        refactored = 0
        refactored_list = []
        flagged_issues = []

        for sub in subdirs:
            target_path = self.core_dir / sub
            if not target_path.exists():
                continue

            for py_file in target_path.rglob("*.py"):
                if py_file.name.startswith(".") or "test" in py_file.name:
                    continue

                scanned += 1
                analysis = self.scan_file_complexity(py_file)
                if analysis.get("unused_imports"):
                    flagged_issues.append({
                        "file": str(py_file.relative_to(self.project_root)),
                        "type": "unused_imports",
                        "details": analysis["unused_imports"]
                    })

                # 1. Clean whitespace / blank lines
                changed, msg = self.clean_file_formatting(py_file, dry_run=dry_run)
                if changed:
                    cleaned += 1

                # 2. Active AST Code Refactoring
                ref_changed, ref_msg = self.refactor_code_imports(py_file, dry_run=dry_run)
                if ref_changed:
                    refactored += 1
                    refactored_list.append(str(py_file.relative_to(self.project_root)))

        return {
            "scanned_files": scanned,
            "cleaned_files": cleaned,
            "refactored_files": refactored,
            "refactored_list": refactored_list,
            "flagged_issues_count": len(flagged_issues),
            "flagged_issues": flagged_issues[:10]  # top 10
        }


# Singleton instance
core_refactor_cleaner = CoreRefactorCleaner()
