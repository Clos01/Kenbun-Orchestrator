"""
Agent Permission Governor.
Defines security presets, outside-of-folder access policies, and permission boundaries
for autonomous agents executing on the host.
"""
import os
import json
from pathlib import Path
from enum import Enum
from typing import Dict, List, Any, Optional

from tools.registry import sovereign_tool


class SecurityPreset(str, Enum):
    AUTONOMOUS_YOLO = "AUTONOMOUS_YOLO"  # Fast, eager execution with core system guardrails
    DEV_SANDBOXED = "DEV_SANDBOXED"      # Isolated within workspace sandbox
    READ_ONLY_AUDITOR = "READ_ONLY"      # Read & research only


class AgentPermissionGovernor:
    """
    Governs agent permissions, security presets, and file access policies.
    """

    CRITICAL_DENY_PATHS = [
        "/etc/shadow",
        "/etc/sudoers",
        "/etc/pam.d",
        "/boot",
        "/dev",
        "/proc/kcore",
        "/root",
    ]

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(os.path.expanduser("~/.gemini/config"))
        self.projects_dir = self.config_dir / "projects"

    def validate_file_access(
        self,
        file_path: str,
        project_root: str,
        outside_folders_policy: str = "ALLOW"
    ) -> Dict[str, Any]:
        """
        Validates whether an agent is authorized to access a given file path
        under the active Outside of Folders File Access Policy.
        """
        target = Path(file_path).expanduser().resolve()
        root = Path(project_root).expanduser().resolve()

        # Check absolute blacklisted system paths
        for deny_path in self.CRITICAL_DENY_PATHS:
            if str(target).startswith(deny_path):
                return {
                    "allowed": False,
                    "reason": f"Access to system-critical path '{deny_path}' is strictly blocked",
                    "severity": "CRITICAL"
                }

        # Check SSH private keys
        if ".ssh" in target.parts and any(target.name.startswith(p) for p in ["id_", "id_rsa", "id_ed25519"]):
            if not target.name.endswith(".pub"):
                return {
                    "allowed": False,
                    "reason": "Direct reading of private SSH keys is prohibited",
                    "severity": "CRITICAL"
                }

        is_inside = target.is_relative_to(root)
        if is_inside:
            return {"allowed": True, "reason": "Path is within active project workspace", "severity": "NONE"}

        # Outside folder access policy evaluation
        policy = outside_folders_policy.upper()
        if policy == "ALLOW":
            return {
                "allowed": True,
                "reason": "Access allowed under 'Outside of folders file access policy: Allow' (non-critical path)",
                "severity": "NONE"
            }
        elif policy == "DENY":
            return {
                "allowed": False,
                "reason": f"Path '{target}' is outside project root '{root}' and policy is DENY",
                "severity": "HIGH"
            }
        else:  # ASK
            return {
                "allowed": False,
                "reason": f"Path '{target}' requires operator confirmation under ASK policy",
                "severity": "MEDIUM"
            }

    def get_active_presets(self) -> Dict[str, Any]:
        """
        Reads registered project security presets from ~/.gemini/config/projects/.
        """
        presets = {}
        if self.projects_dir.exists():
            for proj_file in self.projects_dir.glob("*.json"):
                try:
                    with open(proj_file, "r") as f:
                        data = json.load(f)
                    presets[data.get("name", proj_file.stem)] = {
                        "id": data.get("id", proj_file.stem),
                        "settings": data.get("settings", {}),
                        "file": str(proj_file)
                    }
                except Exception as e:
                    presets[proj_file.stem] = {"error": str(e)}
        return presets

    def configure_preset(
        self,
        project_id: str,
        preset: SecurityPreset = SecurityPreset.AUTONOMOUS_YOLO
    ) -> Dict[str, Any]:
        """
        Applies a verified security preset to a project configuration file.
        """
        proj_file = self.projects_dir / f"{project_id}.json"
        if not proj_file.exists():
            return {"status": "ERROR", "message": f"Project {project_id} not found"}

        with open(proj_file, "r") as f:
            data = json.load(f)

        if "settings" not in data:
            data["settings"] = {}

        if preset == SecurityPreset.AUTONOMOUS_YOLO:
            data["settings"]["fileAccessPolicy"] = "AGENT_SETTING_POLICY_ALLOW"
            data["settings"]["autoExecutionPolicy"] = "CASCADE_COMMANDS_AUTO_EXECUTION_EAGER"
            data["settings"]["artifactReviewMode"] = "ARTIFACT_REVIEW_MODE_TURBO"
            data["settings"]["sandboxMode"] = False
        elif preset == SecurityPreset.DEV_SANDBOXED:
            data["settings"]["fileAccessPolicy"] = "AGENT_SETTING_POLICY_ASK"
            data["settings"]["autoExecutionPolicy"] = "CASCADE_COMMANDS_AUTO_EXECUTION_PROCEED_IN_SANDBOX"
            data["settings"]["sandboxMode"] = True
        elif preset == SecurityPreset.READ_ONLY_AUDITOR:
            data["settings"]["fileAccessPolicy"] = "AGENT_SETTING_POLICY_ASK"
            data["settings"]["autoExecutionPolicy"] = "CASCADE_COMMANDS_AUTO_EXECUTION_OFF"
            data["settings"]["sandboxMode"] = True

        with open(proj_file, "w") as f:
            json.dump(data, f, indent=2)

        return {
            "status": "SUCCESS",
            "project_id": project_id,
            "applied_preset": preset.value,
            "settings": data["settings"]
        }


@sovereign_tool()
def get_security_preset(project_name: str = "") -> str:
    """
    Returns the currently active security preset and outside-folder access policies.
    """
    governor = AgentPermissionGovernor()
    presets = governor.get_active_presets()
    lines = ["# 🛡️ Agent Security Presets & Permission Governance", ""]
    for name, info in presets.items():
        lines.append(f"### Project: `{name}`")
        if "settings" in info:
            for k, v in info["settings"].items():
                lines.append(f"- **{k}**: `{v}`")
        elif "error" in info:
            lines.append(f"- Error: {info['error']}")
        lines.append("")
    return "\n".join(lines)
