"""
Kenbun Deterministic Diagnostic Error Taxonomy (KB-E000 Series).

Provides standardized, numbered error codes and defensive exception envelopes
across model inference, memory/vector stores, orchestration, and Hivemind sync.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class KenbunErrorCode(str, Enum):
    # --- 1. MODEL & INFERENCE (KB-E100 - KB-E199) ---
    MODEL_ENDPOINT_UNREACHABLE = "KB-E101"
    MODEL_TIMEOUT = "KB-E102"
    CONTEXT_WINDOW_EXCEEDED = "KB-E103"
    THINKING_MONOLOGUE_RUNAWAY = "KB-E104"
    SCHEMA_PARSE_FAILURE = "KB-E105"
    MODEL_SLOT_UNAVAILABLE = "KB-E106"
    RESOLVER_EXHAUSTED = "KB-E107"

    # --- 2. MEMORY & VECTOR STORES (KB-E200 - KB-E299) ---
    CHROMA_DISCONNECTED = "KB-E201"
    HONCHO_UNREACHABLE = "KB-E202"
    POSTGRES_CIRCUIT_OPEN = "KB-E203"
    SQLITE_LOCK_TIMEOUT = "KB-E204"
    SCHEMA_MIGRATION_MISMATCH = "KB-E205"
    COLLECTION_TOPIC_MISSING = "KB-E206"

    # --- 3. ORCHESTRATION & PIPELINES (KB-E300 - KB-E399) ---
    PREFLIGHT_LINTER_MISSING = "KB-E301"
    REVIEW_TARGET_NOT_FOUND = "KB-E302"
    ADVERSARIAL_COURT_HUNG_JURY = "KB-E303"
    PIPELINE_BUDGET_EXHAUSTED = "KB-E304"
    UNKNOWN_WORKFLOW = "KB-E305"
    WORKSPACE_GATE_ALERT_BLOCKED = "KB-E306"

    # --- 4. HIVEMIND SYNCHRONIZATION & STORAGE (KB-E400 - KB-E499) ---
    MASTER_HIVEMIND_UNREACHABLE = "KB-E401"
    SYNC_CHECKSUM_MISMATCH = "KB-E402"
    UNVERIFIED_BIN_PURGE_BLOCKED = "KB-E403"
    LOCAL_STAGING_DIRTY = "KB-E404"
    CONCEPT_CORRUPTED = "KB-E405"

    # --- 5. SECURITY & MARS BOUNDARY (KB-E500 - KB-E599) ---
    COMMAND_INJECTION_DETECTED = "KB-E501"
    HARDCODED_SECRET_LEAK = "KB-E502"
    PATH_TRAVERSAL_ATTEMPT = "KB-E503"
    PROBATION_TRIGGERED = "KB-E504"

    @property
    def category(self) -> str:
        code_int = int(self.value.replace("KB-E", ""))
        if 100 <= code_int < 200:
            return "Model & Inference"
        if 200 <= code_int < 300:
            return "Memory & Vector Stores"
        if 300 <= code_int < 400:
            return "Orchestration & Pipelines"
        if 400 <= code_int < 500:
            return "Hivemind Synchronization"
        if 500 <= code_int < 600:
            return "Security & MARS Boundary"
        return "General System"

    @property
    def description(self) -> str:
        descriptions = {
            "KB-E101": "Target LLM endpoint is unreachable, timed out, or refuses connections.",
            "KB-E102": "Model response exceeded the configured inference timeout limit.",
            "KB-E103": "Input tokens plus required completion tokens exceed model context limit.",
            "KB-E104": "Model entered unbounded reasoning stream; thinking monologue suppression active.",
            "KB-E105": "Structured JSON response from model failed schema validation or extraction.",
            "KB-E106": "Server slot allocation full or context slot busy under parallel=1.",
            "KB-E107": "All providers in CapabilityResolver ladder exhausted without valid response.",
            "KB-E201": "ChromaDB HTTP server unreachable or persistent client initialization failed.",
            "KB-E202": "Honcho API or Deriver service is offline or unreachable.",
            "KB-E203": "PostgreSQL circuit breaker active; fast-failing to local SQLite.",
            "KB-E204": "Local SQLite database locked by concurrent thread or process.",
            "KB-E205": "Incompatible schema version detected between local store and client.",
            "KB-E206": "Legacy ChromaDB collection schema missing topic column; local migration required.",
            "KB-E301": "Required linter binary (ruff, eslint) missing from environment PATH.",
            "KB-E302": "Review target file, snippet, or project repository could not be resolved.",
            "KB-E303": "Adversarial Court failed to achieve consensus between defense and prosecution.",
            "KB-E304": "Allocated dollar or turn budget exhausted for the active workflow.",
            "KB-E305": "Requested workflow pipeline is not registered in SovereignRegistry.",
            "KB-E306": "Global Workspace Gate blocked execution due to unresolved flagged alerts.",
            "KB-E401": "Master Hivemind on LG 2025 node is unreachable for synchronization.",
            "KB-E402": "Cryptographic checksum mismatch between local concept and transferred record.",
            "KB-E403": "Refused to purge local staging bin: unsynced or unverified records remain.",
            "KB-E404": "Local staging store contains pending mutations that must be committed or reviewed.",
            "KB-E405": "Concept payload corrupted, missing title, or malformed metadata.",
            "KB-E501": "Potential command injection or un-sanitized shell execution pattern flagged.",
            "KB-E502": "Secret, credential token, or private key detected in reviewable payload.",
            "KB-E503": "File path traversal outside allowed repository boundaries detected.",
            "KB-E504": "Provider probation active; cloud provider placed on cooldown.",
        }
        return descriptions.get(self.value, "General Kenbun operational error.")


class KenbunException(Exception):
    """Base defensive exception containing structured diagnostic code."""

    def __init__(
        self,
        code: KenbunErrorCode,
        details: str = "",
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        self.code = code
        self.details = details or code.description
        self.context = context or {}
        self.cause = cause
        super().__init__(f"[{self.code.value}] {self.code.name}: {self.details}")

    def to_dict(self) -> dict[str, Any]:
        res = {
            "error_code": self.code.value,
            "name": self.code.name,
            "category": self.code.category,
            "details": self.details,
            "context": self.context,
        }
        if self.cause:
            res["cause"] = f"{type(self.cause).__name__}: {self.cause!s}"
        return res


def format_error(
    code: KenbunErrorCode,
    details: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Helper to produce structured error envelopes for MCP and tool consumers."""
    return {
        "status": "error",
        "error_code": code.value,
        "name": code.name,
        "category": code.category,
        "message": f"[{code.value}] {code.name}: {details or code.description}",
        "context": context or {},
    }
