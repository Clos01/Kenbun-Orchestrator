"""Zero-Trust Prompt-to-Tool Compiler for Kenbun Sovereign Engine.

Translates natural language thoughts into automated Kenbun tool calls without the
operator needing to memorize tool names or manual syntax.

Strictly adheres to System 2 Supervisor Directives:
1. Green Zone (Read-Only): Auto-dispatched seamlessly to enrich prompts.
2. Yellow Zone (Mutation): Strictly gated behind confirmation tokens (kc_6f011e5928ed).
3. Privacy & Secret Defense: Zero raw prompt text in logs; SHA-256 non-reversible digests.
4. Log-Injection Defense: Parameterized logging without raw string interpolation.
5. Dynamic Configuration: Zero hardcoded fallback IPs; discovers endpoints via Cluster Mesh.
"""

import os
import re
import time
import hashlib
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger("kenbun.prompt_compiler")


class SecurityGateViolation(PermissionError):
    """Raised when a state-mutating action is attempted without explicit human confirmation."""
    pass


class RedZoneViolation(SecurityGateViolation):
    """Raised when an action violates non-negotiable system safety invariants."""
    pass


class ConfigurationError(RuntimeError):
    """Raised when required infrastructure endpoints are missing or unreachable."""
    pass


@dataclass
class CompiledPlan:
    """Represents a compiled tool execution plan."""
    action_type: str  # "READ_ONLY" | "MUTATION" | "PASSTHROUGH" | "PROHIBITED"
    tool_name: Optional[str]
    parameters: Dict[str, Any]
    requires_confirmation: bool
    audit_id: str
    prompt_hash: str
    explanation: str
    blast_radius: str = "LOW"  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    reversibility: str = "NON_MUTATING"  # "NON_MUTATING" | "ROLLBACK_SUPPORTED" | "IRREVERSIBLE"
    epistemic_downshifted: bool = False


class PromptToToolCompiler:
    """Autonomous intent classifier and zero-trust auto-tool compiler."""

    SAFE_READ_TOOLS: set[str] = {
        "get_brain_health",
        "telemetry_integrity_audit",
        "search_hivemind_concepts",
        "recall_fix",
        "profile_database_performance",
    }

    GATED_MUTATION_TOOLS: set[str] = {
        "remember_preference",
        "remember_fix",
        "save_checkpoint",
        "run_code_safely",
        "execute_code",
    }

    # Red Zone: Non-negotiable destructive invariants that are blocked outright
    RED_ZONE_PATTERNS: list[str] = [
        r"rm\s+-rf\s+[/~]",
        r"git\s+push\s+.*--force",
        r"drop\s+database",
        r"drop\s+table",
        r"truncate\s+table",
        r"chmod\s+777",
        r"mkfs",
        r":\(\)\{\s*:\|:&\s*\};:",
    ]

    # Epistemic Ambiguity: Detects when the operator expresses uncertainty
    AMBIGUITY_TRIGGERS: list[str] = [
        "i don't know", "i dont know", "not sure", "not certain",
        "what should i do", "what do you think", "maybe we should", "uncertain"
    ]

    def __init__(self, endpoint_url: Optional[str] = None) -> None:
        """Initializes the compiler with dynamic cluster endpoint discovery."""
        self.endpoint_url: str = self._resolve_endpoint(endpoint_url)

    def _resolve_endpoint(self, override_url: Optional[str]) -> str:
        """Resolves the AI endpoint dynamically without hardcoded fallback IPs."""
        if override_url:
            return override_url

        env_url = os.environ.get("LM_STUDIO_URL")
        if env_url:
            return env_url

        try:
            from tools.infrastructure.dynamic_cluster_mesh import resolve_cluster_endpoints
            endpoints = resolve_cluster_endpoints()
            lm_info = endpoints.get("lm_studio", {})
            if lm_info.get("host") and lm_info.get("port"):
                return f"http://{lm_info['host']}:{lm_info['port']}"
        except Exception:
            pass

        raise ConfigurationError(
            "LM_STUDIO_URL must be explicitly configured in environment or discoverable via dynamic_cluster_mesh."
        )

    def _hash_payload(self, text: str) -> str:
        """Generates a non-reversible SHA-256 digest to prevent PII and secret leaks in logs."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _audit_pre(self, action_type: str, tool_name: Optional[str], prompt_hash: str, length: int) -> str:
        """Records Phase-1 pre-execution audit state with parameterized logging."""
        audit_id = f"audit_{int(time.time() * 1000)}_{action_type.lower()}"
        logger.info(
            "🛡️ [AUDIT-PRE] id=%s action=%s tool=%s hash=%s len=%d",
            audit_id,
            action_type,
            str(tool_name),
            prompt_hash,
            length,
        )
        return audit_id

    def _audit_post(self, audit_id: str, status: str, elapsed_ms: float) -> None:
        """Records Phase-2 post-execution audit state with parameterized logging."""
        logger.info(
            "🛡️ [AUDIT-POST] id=%s status=%s elapsed_ms=%.2f",
            audit_id,
            status,
            elapsed_ms,
        )

    def classify_intent(self, prompt: str) -> Dict[str, Any]:
        """Maps natural language prompts into structured tool directives."""
        clean = prompt.strip()
        lower = clean.lower()

        # 0. Prohibited Invariant Violations (RED ZONE -> Blocked outright)
        for pattern in self.RED_ZONE_PATTERNS:
            if re.search(pattern, clean, re.IGNORECASE):
                return {
                    "action_type": "PROHIBITED",
                    "tool_name": None,
                    "parameters": {"rejected_pattern": pattern},
                    "requires_confirmation": False,
                    "explanation": f"Prohibited destructive action detected matching Red-Zone invariant '{pattern}'. Execution permanently blocked.",
                    "blast_radius": "CRITICAL",
                    "reversibility": "IRREVERSIBLE",
                    "epistemic_downshifted": False,
                }

        # Epistemic Ambiguity: Detect if operator expresses uncertainty ("I don't know")
        is_ambiguous = any(trig in lower for trig in self.AMBIGUITY_TRIGGERS)

        # 1. Preference / Standard Capture Intent (MUTATION -> Gated)
        pref_triggers = ["never use", "always use", "remember that", "rule:", "preference:", "standard:"]
        if any(trig in lower for trig in pref_triggers):
            if is_ambiguous:
                return {
                    "action_type": "READ_ONLY",
                    "tool_name": "search_hivemind_concepts",
                    "parameters": {"query": clean, "top_k": 3},
                    "requires_confirmation": False,
                    "explanation": "Operator expressed ambiguity ('I don't know'). Downshifted from mutation to Green-Zone Socratic exploration.",
                    "blast_radius": "LOW",
                    "reversibility": "NON_MUTATING",
                    "epistemic_downshifted": True,
                }
            return {
                "action_type": "MUTATION",
                "tool_name": "remember_preference",
                "parameters": {"preference": clean, "context": "Operator Dictated Rule"},
                "requires_confirmation": True,
                "explanation": "Detected new operator preference/standard requiring permanent Honcho persistence.",
                "blast_radius": "MEDIUM",
                "reversibility": "ROLLBACK_SUPPORTED",
                "epistemic_downshifted": False,
            }

        # 2. Bug Fix Memorization Intent (MUTATION -> Gated)
        if any(trig in lower for trig in ["remember fix", "save fix", "the fix was", "the bug was caused by"]):
            if is_ambiguous:
                return {
                    "action_type": "READ_ONLY",
                    "tool_name": "recall_fix",
                    "parameters": {"error_message": clean},
                    "requires_confirmation": False,
                    "explanation": "Operator expressed ambiguity. Downshifted from fix recording to Green-Zone historical fix recall.",
                    "blast_radius": "LOW",
                    "reversibility": "NON_MUTATING",
                    "epistemic_downshifted": True,
                }
            return {
                "action_type": "MUTATION",
                "tool_name": "remember_fix",
                "parameters": {"error_message": clean, "solution": clean},
                "requires_confirmation": True,
                "explanation": "Detected bug-fix resolution requiring vector memory persistence.",
                "blast_radius": "MEDIUM",
                "reversibility": "ROLLBACK_SUPPORTED",
                "epistemic_downshifted": False,
            }

        # 3. Brain / System Health Intent (READ_ONLY -> Auto-Dispatched)
        if any(trig in lower for trig in ["brain health", "system health", "cluster health", "routing accuracy"]):
            return {
                "action_type": "READ_ONLY",
                "tool_name": "get_brain_health",
                "parameters": {},
                "requires_confirmation": False,
                "explanation": "Checking real-time cluster routing accuracy and cognitive health.",
                "blast_radius": "LOW",
                "reversibility": "NON_MUTATING",
                "epistemic_downshifted": False,
            }

        # 4. Telemetry Integrity Intent (READ_ONLY -> Auto-Dispatched)
        if any(trig in lower for trig in ["telemetry audit", "tool audit", "audit telemetry"]):
            return {
                "action_type": "READ_ONLY",
                "tool_name": "telemetry_integrity_audit",
                "parameters": {"post_alert": False},
                "requires_confirmation": False,
                "explanation": "Auditing tool telemetry and execution integrity across the cluster.",
                "blast_radius": "LOW",
                "reversibility": "NON_MUTATING",
                "epistemic_downshifted": False,
            }

        # 5. Past Fix Recall Intent (READ_ONLY -> Auto-Dispatched)
        if any(trig in lower for trig in ["how did we fix", "past fix for", "have we seen this error", "recall fix"]):
            return {
                "action_type": "READ_ONLY",
                "tool_name": "recall_fix",
                "parameters": {"error_message": clean},
                "requires_confirmation": False,
                "explanation": "Searching vector memory for historical error resolutions.",
                "blast_radius": "LOW",
                "reversibility": "NON_MUTATING",
                "epistemic_downshifted": False,
            }

        # 6. Memory / Concept Search Intent (READ_ONLY -> Auto-Dispatched)
        if any(trig in lower for trig in ["what did we decide", "search memory", "hivemind", "what is our rule"]):
            return {
                "action_type": "READ_ONLY",
                "tool_name": "search_hivemind_concepts",
                "parameters": {"query": clean, "top_k": 3},
                "requires_confirmation": False,
                "explanation": "Retrieving architectural concepts and guidelines from Honcho.",
                "blast_radius": "LOW",
                "reversibility": "NON_MUTATING",
                "epistemic_downshifted": False,
            }

        # 7. Conversational Passthrough (No Tool Needed)
        return {
            "action_type": "PASSTHROUGH",
            "tool_name": None,
            "parameters": {},
            "requires_confirmation": False,
            "explanation": "General conversational query; no tool invocation required.",
            "blast_radius": "LOW",
            "reversibility": "NON_MUTATING",
            "epistemic_downshifted": False,
        }

    def compile(self, prompt: str) -> CompiledPlan:
        """Compiles a user prompt into an audited execution plan."""
        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string.")

        clean_prompt = prompt.strip()
        p_hash = self._hash_payload(clean_prompt)
        intent = self.classify_intent(clean_prompt)

        audit_id = self._audit_pre(
            action_type=intent["action_type"],
            tool_name=intent["tool_name"],
            prompt_hash=p_hash,
            length=len(clean_prompt),
        )

        return CompiledPlan(
            action_type=intent["action_type"],
            tool_name=intent["tool_name"],
            parameters=intent["parameters"],
            requires_confirmation=intent["requires_confirmation"],
            audit_id=audit_id,
            prompt_hash=p_hash,
            explanation=intent["explanation"],
            blast_radius=intent.get("blast_radius", "LOW"),
            reversibility=intent.get("reversibility", "NON_MUTATING"),
            epistemic_downshifted=intent.get("epistemic_downshifted", False),
        )

    def execute(self, plan: CompiledPlan, confirmation_token: Optional[str] = None) -> Dict[str, Any]:
        """Executes a compiled plan enforcing strict confirmation gates and two-phase audit."""
        t0 = time.time()

        if plan.action_type == "PROHIBITED":
            elapsed_ms = (time.time() - t0) * 1000
            self._audit_post(plan.audit_id, "BLOCKED_RED_ZONE_INVARIANT", elapsed_ms)
            raise RedZoneViolation(
                f"🚨 [RED ZONE BLOCKED]: Operation violates sovereign system safety invariants ({plan.explanation}). "
                f"Action is strictly prohibited and cannot be confirmed."
            )

        if plan.requires_confirmation:
            if not confirmation_token or not str(confirmation_token).startswith("CONFIRM_"):
                elapsed_ms = (time.time() - t0) * 1000
                self._audit_post(plan.audit_id, "BLOCKED_CONFIRMATION_REQUIRED", elapsed_ms)
                raise SecurityGateViolation(
                    f"Mutation tool '{plan.tool_name}' blocked by System 2 gate. "
                    f"Requires explicit confirmation token."
                )

        if plan.action_type == "PASSTHROUGH" or not plan.tool_name:
            elapsed_ms = (time.time() - t0) * 1000
            self._audit_post(plan.audit_id, "PASSTHROUGH_COMPLETED", elapsed_ms)
            return {
                "status": "passthrough",
                "tool_name": None,
                "result": None,
                "audit_id": plan.audit_id,
                "elapsed_ms": elapsed_ms,
            }

        # Dispatch tool execution
        tool_res: Any = None
        try:
            tool_res = self._dispatch_tool(plan.tool_name, plan.parameters)
            elapsed_ms = (time.time() - t0) * 1000
            self._audit_post(plan.audit_id, "EXECUTED_SUCCESS", elapsed_ms)
            return {
                "status": "success",
                "tool_name": plan.tool_name,
                "result": tool_res,
                "audit_id": plan.audit_id,
                "elapsed_ms": elapsed_ms,
            }
        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            self._audit_post(plan.audit_id, f"EXECUTION_FAILED: {type(e).__name__}", elapsed_ms)
            logger.error("Tool dispatch failure: %s", e)
            return {
                "status": "error",
                "tool_name": plan.tool_name,
                "error": str(e),
                "audit_id": plan.audit_id,
                "elapsed_ms": elapsed_ms,
            }

    def _dispatch_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Invokes the mapped tool from the Kenbun codebase."""
        if tool_name == "get_brain_health":
            from tools.strategy.orchestration_tools import get_brain_health
            return get_brain_health()

        if tool_name == "telemetry_integrity_audit":
            from tools.strategy.orchestration_tools import telemetry_integrity_audit
            return telemetry_integrity_audit(post_alert=params.get("post_alert", False))

        if tool_name == "search_hivemind_concepts":
            from tools.memory.hivemind_tools import search_hivemind_concepts
            return search_hivemind_concepts(query=params["query"], top_k=params.get("top_k", 3))

        if tool_name == "recall_fix":
            from tools.execution.checkpoint_tools import recall_fix
            return recall_fix(error_message=params["error_message"])

        if tool_name == "remember_preference":
            from tools.memory.hivemind_tools import remember_preference
            return remember_preference(preference=params["preference"], context=params.get("context", "General"))

        if tool_name == "remember_fix":
            from tools.execution.checkpoint_tools import remember_fix
            return remember_fix(error_message=params["error_message"], solution=params["solution"])

        raise NotImplementedError(f"Tool '{tool_name}' has no registered dispatch executor.")

    def compile_and_dispatch(
        self, prompt: str, confirmation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Single-entry convenience wrapper to compile and dispatch a prompt."""
        plan = self.compile(prompt)
        return self.execute(plan, confirmation_token=confirmation_token)


# Singleton factory helper
_compiler_instance: Optional[PromptToToolCompiler] = None


def get_prompt_compiler() -> PromptToToolCompiler:
    """Returns a singleton PromptToToolCompiler instance."""
    global _compiler_instance
    if _compiler_instance is None:
        _compiler_instance = PromptToToolCompiler()
    return _compiler_instance


def compile_and_dispatch_prompt(prompt: str, confirmation_token: Optional[str] = None) -> Dict[str, Any]:
    """Public helper function to compile and execute a natural language prompt."""
    compiler = get_prompt_compiler()
    return compiler.compile_and_dispatch(prompt, confirmation_token=confirmation_token)
