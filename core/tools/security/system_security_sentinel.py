"""
System Security Sentinel.
Provides deterministic host security auditing, agent permission boundaries,
network exposure analysis, and automated permission hardening for the Edge_Node node.
"""
import os
import re
import stat
import glob
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

from tools.infrastructure.config import settings
from tools.registry import sovereign_tool


class SystemSecuritySentinel:
    """
    Audits and hardens host system security, agent execution boundaries,
    and credential exposure.
    """

    # High-risk system directories that agents must never mutate directly
    PROTECTED_SYSTEM_DIRS = [
        "/etc",
        "/boot",
        "/sys",
        "/proc",
        "/dev",
        "/root",
        "/usr/bin",
        "/usr/sbin",
        "/var/log",
    ]

    # Dangerous command regex patterns that must be blocked in agent execution
    DESTRUCTIVE_COMMAND_PATTERNS = [
        r"(?i)\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f*|-f[a-zA-Z]*r[a-zA-Z]*)\s+(/|/\*|~|~\*|/etc|/boot|/usr|/var)(\s|$|/)",
        r"(?i)\bmkfs(\.|\s)",
        r"(?i)\bfdisk\b",
        r"(?i)\bdd\s+if=/dev/(zero|urandom)\s+of=/dev/",
        r":\(\)\s*\{\s*:\|:&\s*\};:",
        r"(?i)\bchmod\s+(-R\s+)?(777|666)\s+/(?!home/user/Dev)",
        r"(?i)\bchown\s+(-R\s+)?root\b",
        r"(?i)\b(curl|wget)\b.*\|\s*(bash|sh)\b",
        r"(?i)\bcat\s+~?/\.ssh/id_[a-zA-Z0-9_-]+\b.*\b(curl|nc|ncat|netcat|wget)\b",
    ]

    def __init__(self, home_dir: Optional[Path] = None):
        self.home_dir = home_dir or Path(os.path.expanduser("~"))
        self.ssh_dir = self.home_dir / ".ssh"

    def audit_host_credentials(self) -> Dict[str, Any]:
        """
        Audits file permissions on ~/.ssh and cryptographic keys.
        """
        findings = []
        status = "SECURE"

        if self.ssh_dir.exists():
            ssh_mode = stat.S_IMODE(self.ssh_dir.stat().st_mode)
            # ~/.ssh should be 0700
            if ssh_mode & 0o077 != 0:
                status = "VULNERABLE"
                findings.append({
                    "target": str(self.ssh_dir),
                    "current_mode": oct(ssh_mode),
                    "expected_mode": "0700",
                    "issue": "SSH directory is accessible by group/others",
                    "severity": "HIGH",
                    "remediation": f"chmod 700 {self.ssh_dir}"
                })

            # Check individual private keys
            for key_file in self.ssh_dir.glob("id_*"):
                if not key_file.name.endswith(".pub"):
                    mode = stat.S_IMODE(key_file.stat().st_mode)
                    if mode & 0o077 != 0:
                        status = "VULNERABLE"
                        findings.append({
                            "target": str(key_file),
                            "current_mode": oct(mode),
                            "expected_mode": "0600",
                            "issue": "Private key has loose permissions",
                            "severity": "CRITICAL",
                            "remediation": f"chmod 600 {key_file}"
                        })
        else:
            findings.append({
                "target": str(self.ssh_dir),
                "issue": "SSH directory does not exist",
                "severity": "INFO",
            })

        return {
            "category": "host_credentials",
            "status": status,
            "findings": findings,
            "checked_items": len(list(self.ssh_dir.glob("*"))) if self.ssh_dir.exists() else 0
        }

    def audit_sensitive_env_files(self, search_roots: Optional[List[Path]] = None) -> Dict[str, Any]:
        """
        Audits environment files (.env*) across Dev and project folders to ensure
        they are not world-readable.
        """
        if not search_roots:
            search_roots = [
                self.home_dir / "Dev",
                self.home_dir / "dev",
            ]

        findings = []
        status = "SECURE"
        scanned_count = 0

        for root in search_roots:
            if not root.exists():
                continue
            for env_path in root.rglob(".env*"):
                if any(part in env_path.parts for part in [".venv", "node_modules", ".git"]):
                    continue
                scanned_count += 1
                try:
                    mode = stat.S_IMODE(env_path.stat().st_mode)
                    if mode & 0o004 != 0:
                        status = "WARNING"
                        findings.append({
                            "target": str(env_path),
                            "current_mode": oct(mode),
                            "expected_mode": "0600",
                            "issue": "Environment file is readable by others",
                            "severity": "MEDIUM",
                            "remediation": f"chmod 600 {env_path}"
                        })
                except (OSError, PermissionError) as e:
                    findings.append({
                        "target": str(env_path),
                        "issue": f"Could not inspect file mode: {e}",
                        "severity": "LOW"
                    })

        return {
            "category": "env_files",
            "status": status,
            "findings": findings,
            "scanned_count": scanned_count
        }

    def audit_network_exposure(self) -> Dict[str, Any]:
        """
        Audits active listening TCP/UDP sockets to detect public interface bindings (0.0.0.0).
        """
        findings = []
        listening_services = []

        try:
            res = subprocess.run(
                ["ss", "-tulpn"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 5:
                        proto = parts[0]
                        local_addr = parts[4]
                        if ":" in local_addr:
                            host, port = local_addr.rsplit(":", 1)
                            is_wildcard = host in ["*", "0.0.0.0", "::"]
                            sensitive_ports = {"5432": "PostgreSQL", "6379": "Redis", "27017": "MongoDB"}
                            
                            listening_services.append({
                                "proto": proto,
                                "host": host,
                                "port": port,
                                "public": is_wildcard
                            })

                            if is_wildcard and port in sensitive_ports:
                                findings.append({
                                    "service": sensitive_ports[port],
                                    "port": port,
                                    "host": host,
                                    "issue": f"{sensitive_ports[port]} is bound to wildcard 0.0.0.0",
                                    "severity": "HIGH",
                                    "recommendation": "Bind service strictly to 127.0.0.1 or Tailscale IP"
                                })
        except Exception as e:
            findings.append({
                "issue": f"Network socket inspection failed: {e}",
                "severity": "LOW"
            })

        status = "SECURE" if not findings else "WARNING"
        return {
            "category": "network_exposure",
            "status": status,
            "findings": findings,
            "listening_services": listening_services[:15]
        }

    def audit_agent_command(self, command: str) -> Dict[str, Any]:
        """
        Inspects an agent proposed command string for dangerous / destructive patterns.
        """
        for pattern in self.DESTRUCTIVE_COMMAND_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return {
                    "allowed": False,
                    "matched_pattern": pattern,
                    "reason": "Command matches prohibited destructive host pattern",
                    "severity": "CRITICAL"
                }

        for s_dir in self.PROTECTED_SYSTEM_DIRS:
            pattern = rf"(?i)\b(rm|mv|cp|tee|cat\s*>)\b.*\s+{re.escape(s_dir)}(/|\b|\s|$)"
            if re.search(pattern, command):
                return {
                    "allowed": False,
                    "matched_pattern": s_dir,
                    "reason": f"Direct write or removal targeting system directory '{s_dir}' blocked",
                    "severity": "HIGH"
                }

        return {
            "allowed": True,
            "reason": "Command verified safe against host protection policy",
            "severity": "NONE"
        }

    def harden_host(self) -> Dict[str, Any]:
        """
        Applies automated hardening to SSH keys and sensitive environment files.
        """
        remediated = []

        if self.ssh_dir.exists():
            try:
                os.chmod(self.ssh_dir, 0o700)
                remediated.append("chmod 700 ~/.ssh")
                for key_file in self.ssh_dir.glob("id_*"):
                    if not key_file.name.endswith(".pub"):
                        os.chmod(key_file, 0o600)
                        remediated.append(f"chmod 600 ~/.ssh/{key_file.name}")
            except Exception as e:
                remediated.append(f"Failed to harden SSH: {e}")

        dev_dir = self.home_dir / "Dev"
        env_count = 0
        if dev_dir.exists():
            for env_path in dev_dir.rglob(".env*"):
                if any(p in env_path.parts for p in [".venv", "node_modules", ".git"]):
                    continue
                try:
                    os.chmod(env_path, 0o600)
                    env_count += 1
                except Exception as e:
                    remediated.append(f"Failed to chmod {env_path.name}: {e}")

        if env_count > 0:
            remediated.append(f"chmod 600 applied across {env_count} sensitive .env files in ~/Dev")

        return {
            "remediated_count": len(remediated),
            "actions": remediated,
            "status": "SUCCESS"
        }


@sovereign_tool()
def audit_system_security() -> str:
    """
    Audits the host machine (Edge_Node) for credential exposure, loose file permissions,
    and open network socket vulnerabilities.
    """
    sentinel = SystemSecuritySentinel()
    ssh_report = sentinel.audit_host_credentials()
    env_report = sentinel.audit_sensitive_env_files()
    net_report = sentinel.audit_network_exposure()

    total_findings = len(ssh_report["findings"]) + len(env_report["findings"]) + len(net_report["findings"])
    overall_status = "SECURE" if total_findings == 0 else ("CRITICAL" if any(f.get("severity") == "CRITICAL" for rep in [ssh_report, env_report, net_report] for f in rep["findings"]) else "WARNING")

    lines = [
        "# 🛡️ System Security Sentinel Audit Report",
        f"**Overall Node Status:** {overall_status}",
        f"**Total Findings:** {total_findings}",
        "",
        "### 1. Host Credentials (~/.ssh)",
        f"- Status: {ssh_report['status']}",
        f"- Items Checked: {ssh_report['checked_items']}",
    ]
    for f in ssh_report["findings"]:
        lines.append(f"  - ⚠️ [{f.get('severity', 'WARN')}] {f.get('target', '')}: {f.get('issue', '')} -> `{f.get('remediation', '')}`")

    lines.extend([
        "",
        "### 2. Sensitive Environment Files (.env*)",
        f"- Status: {env_report['status']}",
        f"- Scanned Files: {env_report['scanned_count']}",
    ])
    for f in env_report["findings"]:
        lines.append(f"  - ⚠️ [{f.get('severity', 'WARN')}] {f.get('target', '')}: {f.get('issue', '')} -> `{f.get('remediation', '')}`")

    lines.extend([
        "",
        "### 3. Network Socket Exposure",
        f"- Status: {net_report['status']}",
    ])
    for f in net_report["findings"]:
        lines.append(f"  - 🚨 [{f.get('severity', 'WARN')}] {f.get('service', '')} on port {f.get('port', '')}: {f.get('issue', '')}")

    return "\n".join(lines)


@sovereign_tool()
def harden_system_security() -> str:
    """
    Autonomously remediates loose permissions on SSH keys and workspace environment files.
    """
    sentinel = SystemSecuritySentinel()
    result = sentinel.harden_host()
    action_lines = "\n".join(f"  - {a}" for a in result["actions"])
    return f"✅ Host Hardened: {result['remediated_count']} security permissions enforced.\n{action_lines}"

