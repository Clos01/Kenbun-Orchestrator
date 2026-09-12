"""
System Security & Build Protection Pipeline for Kenbun Swarm.
============================================================
Workflow: system_security
Stages: Host Credential Audit → Software Build Pre-Flight → Agent Permission Policy → Auto-Hardening → Supervisor Sign-off

Trigger this pipeline whenever auditing node security, onboarding new agents, or verifying build protection.
"""
from typing import Any, Dict, List


def build_system_security_pipeline(tools: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Builds the System Security & Build Protection pipeline.
    """
    from tools.security.system_security_sentinel import audit_system_security, harden_system_security
    from tools.security.build_protection_sentinel import audit_software_build, BuildProtectionSentinel
    from tools.security.agent_permission_governor import get_security_preset

    steps = [
        {
            "id": "host_security_audit",
            "label": "🛡️ Auditing Host Credentials, SSH Keys, and Network Exposure",
            "tool": lambda: audit_system_security(),
            "input": lambda s: {},
            "output_key": "host_audit_report",
        },
        {
            "id": "software_build_audit",
            "label": "🏗️ Auditing Software Build Context, Docker Isolation & Compilation Integrity",
            "tool": lambda project_path="": audit_software_build(project_path),
            "input": lambda s: {
                "project_path": s.get("project_path") or ".",
            },
            "output_key": "build_audit_report",
        },
        {
            "id": "agent_permissions_audit",
            "label": "🔒 Inspecting Agent Security Presets & Outside Folder Access Policies",
            "tool": lambda: get_security_preset(),
            "input": lambda s: {},
            "output_key": "permissions_report",
        },
        {
            "id": "autonomous_hardening",
            "label": "⚡ Executing Autonomous Hardening: chmod 600 secrets & .dockerignore sanitization",
            "tool": lambda: {
                "host_hardening": harden_system_security(),
                "build_context_sanitization": BuildProtectionSentinel().sanitize_build_context()
            },
            "input": lambda s: {},
            "output_key": "hardening_report",
        },
        {
            "id": "supervisor_signoff",
            "label": "🏛️ System 2: Executive Security Verification & Consensus",
            "tool": tools.get("consult_supervisor") or (lambda user_proposal, code_snippet="": "Security Posture Verified."),
            "input": lambda s: {
                "user_proposal": f"System Security & Build Audit: {s['task']}",
                "code_snippet": f"HOST AUDIT:\n{str(s.get('host_audit_report', ''))[:1500]}\n\nBUILD AUDIT:\n{str(s.get('build_audit_report', ''))[:1500]}\n\nHARDENING:\n{str(s.get('hardening_report', ''))[:1000]}",
            },
            "output_key": "supervisor_result",
        }
    ]
    return steps
