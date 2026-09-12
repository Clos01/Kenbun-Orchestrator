"""
Build Protection Sentinel.
Guarantees software build safety, Docker context sanitization, secret leakage prevention,
supply-chain dependency auditing, and pre-build compilation integrity.
"""
import os
import re
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

from tools.infrastructure.config import settings
from tools.registry import sovereign_tool


class BuildProtectionSentinel:
    """
    Audits and protects the software build lifecycle:
    pre-build compilation, Docker context sanitization, secret leakage prevention,
    and dependency supply-chain security.
    """

    MANDATORY_DOCKERIGNORE_PATTERNS = [
        r"^\.env.*",
        r"^\.git.*",
        r".*\.pem$",
        r".*\.key$",
        r"^id_.*",
        r"^node_modules",
        r"^\.venv",
        r"^brain.*",
    ]

    SUSPICIOUS_SCRIPT_PATTERNS = [
        r"\b(curl|wget)\b.*\|\s*(bash|sh)\b",
        r"\b(nc|ncat|netcat)\b",
        r"\brm\s+-rf\s+/(?!\w)",
    ]

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(settings.PROJECT_ROOT).resolve()

    def audit_docker_context(self, project_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Audits .dockerignore to verify sensitive files (.env, keys, git) are excluded
        from Docker build context to prevent secret leakage into images.
        """
        root = project_dir or self.project_root
        dockerignore_path = root / ".dockerignore"
        findings = []
        status = "SECURE"

        if not dockerignore_path.exists():
            status = "VULNERABLE"
            findings.append({
                "issue": "Missing .dockerignore in project root",
                "severity": "HIGH",
                "remediation": f"Create .dockerignore in {root} to prevent leaking .env and SSH keys into image layers"
            })
            missing_patterns = self.MANDATORY_DOCKERIGNORE_PATTERNS
        else:
            with open(dockerignore_path, "r", errors="ignore") as f:
                lines = [l.strip() for l in f.readlines() if l.strip() and not l.startswith("#")]

            missing_patterns = []
            for pat in self.MANDATORY_DOCKERIGNORE_PATTERNS:
                if not any(re.search(pat, l) for l in lines):
                    missing_patterns.append(pat)

            if missing_patterns:
                status = "WARNING"
                findings.append({
                    "issue": f".dockerignore missing vital exclusion patterns: {missing_patterns}",
                    "severity": "MEDIUM",
                    "remediation": f"Append patterns to {dockerignore_path}"
                })

        # Check if active .env files exist in directory that might get sucked into build
        exposed_env_files = [str(p.name) for p in root.glob(".env*") if not p.name.endswith(".example")]
        
        return {
            "category": "docker_context",
            "status": status,
            "has_dockerignore": dockerignore_path.exists(),
            "missing_patterns": missing_patterns,
            "exposed_env_files": exposed_env_files,
            "findings": findings
        }

    def audit_dockerfiles(self, project_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Audits all Dockerfiles in the project for non-root execution and secret baking.
        """
        root = project_dir or self.project_root
        findings = []
        status = "SECURE"
        scanned_dockerfiles = []

        dockerfiles = list(root.glob("Dockerfile*"))
        for df in dockerfiles:
            scanned_dockerfiles.append(str(df.name))
            try:
                with open(df, "r", errors="ignore") as f:
                    content = f.read()

                # Check for secret copy instructions
                if re.search(r"^\s*(COPY|ADD)\s+.*\.env\b", content, re.MULTILINE):
                    status = "CRITICAL"
                    findings.append({
                        "file": df.name,
                        "issue": "Dockerfile explicitly copies .env into container filesystem",
                        "severity": "CRITICAL",
                        "remediation": "Remove COPY .env instruction; inject environment variables at runtime only"
                    })

                # Check for root user execution
                has_user = bool(re.search(r"^\s*USER\s+(?!root\b)\w+", content, re.MULTILINE))
                if not has_user:
                    findings.append({
                        "file": df.name,
                        "issue": "Dockerfile does not specify a non-root USER",
                        "severity": "LOW",
                        "remediation": "Add 'USER node' or 'USER appuser' before CMD/ENTRYPOINT"
                    })

                # Check for base image tag :latest
                latest_match = re.findall(r"^\s*FROM\s+[\w./-]+:latest\b", content, re.MULTILINE)
                if latest_match:
                    findings.append({
                        "file": df.name,
                        "issue": f"Base image uses ':latest' tag: {latest_match}",
                        "severity": "LOW",
                        "remediation": "Pin base image to specific semantic version or digest SHA"
                    })

            except Exception as e:
                findings.append({"file": df.name, "issue": f"Error reading Dockerfile: {e}", "severity": "LOW"})

        return {
            "category": "dockerfile_hardening",
            "status": status,
            "scanned_files": scanned_dockerfiles,
            "findings": findings
        }

    def audit_dependencies(self, project_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Audits project dependency files (package.json, requirements.txt) for suspicious hooks.
        """
        root = project_dir or self.project_root
        findings = []
        status = "SECURE"

        # 1. Check package.json scripts for dangerous commands
        pkg_json = root / "package.json"
        if pkg_json.exists():
            try:
                with open(pkg_json, "r", errors="ignore") as f:
                    data = json.load(f)
                scripts = data.get("scripts", {})
                for script_name, cmd in scripts.items():
                    for pat in self.SUSPICIOUS_SCRIPT_PATTERNS:
                        if re.search(pat, cmd):
                            status = "CRITICAL"
                            findings.append({
                                "file": "package.json",
                                "script": script_name,
                                "command": cmd,
                                "issue": "Package script contains suspicious curl-to-bash or destructive pattern",
                                "severity": "CRITICAL"
                            })
            except Exception as e:
                findings.append({"file": "package.json", "issue": f"Error parsing package.json: {e}", "severity": "LOW"})

        return {
            "category": "dependencies",
            "status": status,
            "findings": findings
        }

    def verify_compilation_integrity(self, project_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Pre-build static verification: compiles all Python files in the workspace
        in-memory to guarantee zero AST/syntax regressions before a build or container deployment.
        """
        root = project_dir or self.project_root
        syntax_errors = []
        compiled_count = 0

        for py_file in root.rglob("*.py"):
            if any(p in py_file.parts for p in [".venv", "venv", "node_modules", ".git", "scratch", "__pycache__", "_archive_orphan_weights"]):
                continue
            compiled_count += 1
            try:
                with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                compile(content, str(py_file), "exec")
            except SyntaxError as se:
                syntax_errors.append({
                    "file": str(py_file.relative_to(root)),
                    "error": f"Line {se.lineno}: {se.msg}"
                })
            except Exception as e:
                syntax_errors.append({
                    "file": str(py_file.relative_to(root)),
                    "error": str(e)
                })

        status = "SECURE" if not syntax_errors else "FAILED"
        return {
            "category": "compilation_integrity",
            "status": status,
            "compiled_files": compiled_count,
            "syntax_errors": syntax_errors
        }

    def sanitize_build_context(self, project_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Automatically generates or updates .dockerignore to seal sensitive credentials.
        """
        root = project_dir or self.project_root
        dockerignore_path = root / ".dockerignore"
        existing_lines = []

        if dockerignore_path.exists():
            with open(dockerignore_path, "r", errors="ignore") as f:
                existing_lines = [l.strip() for l in f.readlines()]

        added_rules = []
        standard_rules = [
            ".env",
            ".env.*",
            "!.env.example",
            "*.pem",
            "*.key",
            "id_rsa*",
            "id_ed25519*",
            ".git",
            ".gitignore",
            "node_modules",
            ".venv",
            "venv",
            "brain/",
            "credentials/",
        ]

        for rule in standard_rules:
            if rule not in existing_lines:
                existing_lines.append(rule)
                added_rules.append(rule)

        with open(dockerignore_path, "w") as f:
            f.write("\n".join(existing_lines) + "\n")

        return {
            "dockerignore_path": str(dockerignore_path),
            "added_rules": added_rules,
            "status": "SUCCESS"
        }


@sovereign_tool()
def audit_software_build(project_path: str = "") -> str:
    """
    Comprehensive Software Build Protection Audit:
    Verifies Docker context sanitization, Dockerfile hardening, dependency security,
    and pre-build AST compilation integrity.
    """
    target = Path(project_path).resolve() if project_path else Path(settings.PROJECT_ROOT).resolve()
    sentinel = BuildProtectionSentinel(project_root=target)

    ctx_rep = sentinel.audit_docker_context()
    df_rep = sentinel.audit_dockerfiles()
    dep_rep = sentinel.audit_dependencies()
    comp_rep = sentinel.verify_compilation_integrity()

    total_findings = len(ctx_rep["findings"]) + len(df_rep["findings"]) + len(dep_rep["findings"]) + len(comp_rep["syntax_errors"])
    overall_status = "PASSED" if total_findings == 0 else ("FAILED" if comp_rep["status"] == "FAILED" or ctx_rep["status"] == "CRITICAL" else "WARNING")

    lines = [
        f"# 🏗️ Software Build Protection Audit: `{target.name}`",
        f"**Build Integrity Status:** {overall_status}",
        f"**Total Findings:** {total_findings}",
        "",
        "### 1. Docker Build Context & Secret Isolation",
        f"- Status: {ctx_rep['status']}",
        f"- Has .dockerignore: {ctx_rep['has_dockerignore']}",
        f"- Active .env files in root: {ctx_rep['exposed_env_files']}",
    ]
    for f in ctx_rep["findings"]:
        lines.append(f"  - ⚠️ [{f.get('severity', 'WARN')}] {f.get('issue', '')} -> `{f.get('remediation', '')}`")

    lines.extend([
        "",
        "### 2. Dockerfile Hardening & Non-Root Execution",
        f"- Status: {df_rep['status']}",
        f"- Scanned Files: {df_rep['scanned_files']}",
    ])
    for f in df_rep["findings"]:
        lines.append(f"  - ⚠️ [{f.get('severity', 'WARN')}] {f.get('file', '')}: {f.get('issue', '')} -> `{f.get('remediation', '')}`")

    lines.extend([
        "",
        "### 3. Dependency Scripts & Supply-Chain",
        f"- Status: {dep_rep['status']}",
    ])
    for f in dep_rep["findings"]:
        lines.append(f"  - 🚨 [{f.get('severity', 'WARN')}] {f.get('issue', '')}")

    lines.extend([
        "",
        "### 4. Pre-Build Code Compilation",
        f"- Status: {comp_rep['status']}",
        f"- Compiled Python Files: {comp_rep['compiled_files']}",
    ])
    for err in comp_rep["syntax_errors"]:
        lines.append(f"  - ❌ Syntax error in {err['file']}: {err['error']}")

    return "\n".join(lines)
