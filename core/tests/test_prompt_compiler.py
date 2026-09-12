"""Unit Tests for Zero-Trust Prompt-to-Tool Compiler.

Verifies:
1. Intent classification (READ_ONLY vs MUTATION vs PASSTHROUGH).
2. System 2 confirmation gate enforcement (SecurityGateViolation on unconfirmed mutations).
3. Valid confirmation token approval flow.
4. Two-phase audit logging and SHA-256 PII protection.
5. Fail-safe configuration error on missing endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from tools.strategy.prompt_compiler import (
    PromptToToolCompiler,
    SecurityGateViolation,
    RedZoneViolation,
    ConfigurationError,
    CompiledPlan,
)


@pytest.fixture
def compiler():
    """Returns a test compiler with an explicit test endpoint."""
    return PromptToToolCompiler(endpoint_url="http://test-endpoint:2065")


def test_read_only_intent_compilation(compiler):
    """Verifies that diagnostic and query intents compile to safe READ_ONLY plans."""
    plan = compiler.compile("How is our cluster brain health and routing accuracy?")
    assert plan.action_type == "READ_ONLY"
    assert plan.tool_name == "get_brain_health"
    assert plan.requires_confirmation is False
    assert len(plan.prompt_hash) == 16
    assert plan.audit_id.startswith("audit_")


def test_recall_fix_intent_compilation(compiler):
    """Verifies that historical bug recall compiles to safe READ_ONLY plans."""
    plan = compiler.compile("How did we fix the tailscale route collision?")
    assert plan.action_type == "READ_ONLY"
    assert plan.tool_name == "recall_fix"
    assert plan.requires_confirmation is False


def test_mutation_intent_compilation(compiler):
    """Verifies that rules and preferences compile to gated MUTATION plans."""
    plan = compiler.compile("Remember that we never use float for currency")
    assert plan.action_type == "MUTATION"
    assert plan.tool_name == "remember_preference"
    assert plan.requires_confirmation is True
    assert "never use float for currency" in plan.parameters["preference"]


def test_mutation_blocked_without_token(compiler):
    """Verifies that executing a MUTATION without a confirmation token raises SecurityGateViolation."""
    plan = compiler.compile("Always use Framer Motion for scroll reveals")
    assert plan.requires_confirmation is True

    # Attempt execution without token
    with pytest.raises(SecurityGateViolation) as exc_info:
        compiler.execute(plan, confirmation_token=None)
    assert "blocked by System 2 gate" in str(exc_info.value)

    # Attempt execution with invalid token format
    with pytest.raises(SecurityGateViolation):
        compiler.execute(plan, confirmation_token="invalid_token")


def test_mutation_allowed_with_valid_token(compiler):
    """Verifies that a valid CONFIRM_ token allows mutation execution."""
    plan = compiler.compile("Never use raw any in TypeScript")
    assert plan.requires_confirmation is True

    with patch.object(compiler, "_dispatch_tool", return_value="Recorded preference successfully"):
        res = compiler.execute(plan, confirmation_token="CONFIRM_CLI_TEST")
        assert res["status"] == "success"
        assert res["tool_name"] == "remember_preference"
        assert res["result"] == "Recorded preference successfully"


def test_passthrough_conversational(compiler):
    """Verifies that casual conversation passes through with no tool invocation."""
    plan = compiler.compile("Hey how is your morning going?")
    assert plan.action_type == "PASSTHROUGH"
    assert plan.tool_name is None
    assert plan.requires_confirmation is False

    res = compiler.execute(plan)
    assert res["status"] == "passthrough"
    assert res["tool_name"] is None


def test_zero_pii_in_audit_ledger(compiler):
    """Verifies that raw prompt text is replaced with non-reversible SHA-256 hashes."""
    secret_prompt = "Remember that the secret admin api key is sk_live_998877665544"
    plan = compiler.compile(secret_prompt)

    # The plan's prompt_hash must be a 16-character hex digest, not the raw secret
    assert len(plan.prompt_hash) == 16
    assert "sk_live" not in plan.prompt_hash
    assert plan.audit_id.startswith("audit_")


def test_empty_prompt_validation(compiler):
    """Verifies that empty or whitespace prompts raise ValueError."""
    with pytest.raises(ValueError):
        compiler.compile("")
    with pytest.raises(ValueError):
        compiler.compile("   ")


def test_configuration_error_when_unresolved():
    """Verifies that missing configuration and failed mesh resolution raises ConfigurationError."""
    with patch.dict("os.environ", {}, clear=True), \
         patch("tools.infrastructure.dynamic_cluster_mesh.resolve_cluster_endpoints", side_effect=RuntimeError("Mesh down")):
        with pytest.raises(ConfigurationError) as exc:
            PromptToToolCompiler(endpoint_url=None)
        assert "LM_STUDIO_URL must be explicitly configured" in str(exc.value)


def test_red_zone_prohibited_action(compiler):
    """Verifies that catastrophic destructive commands compile to PROHIBITED with CRITICAL blast radius."""
    plan = compiler.compile("Please run rm -rf / to clear out all cache files")
    assert plan.action_type == "PROHIBITED"
    assert plan.tool_name is None
    assert plan.blast_radius == "CRITICAL"
    assert plan.reversibility == "IRREVERSIBLE"
    assert plan.requires_confirmation is False


def test_red_zone_cannot_be_bypassed_with_token(compiler):
    """Verifies that Red Zone actions raise RedZoneViolation even if confirmation token is provided."""
    plan = compiler.compile("git push origin main --force")
    assert plan.action_type == "PROHIBITED"

    with pytest.raises(RedZoneViolation) as exc_info:
        compiler.execute(plan, confirmation_token="CONFIRM_BYPASS_TOKEN")
    assert "RED ZONE BLOCKED" in str(exc_info.value)


def test_epistemic_downshifting_on_ambiguity(compiler):
    """Verifies that operator uncertainty ('I don't know') downshifts mutations to Green-Zone read/search."""
    # Ambiguous preference mutation downshifted to concept search
    plan_pref = compiler.compile("I don't know, maybe remember that we should test caching")
    assert plan_pref.action_type == "READ_ONLY"
    assert plan_pref.tool_name == "search_hivemind_concepts"
    assert plan_pref.epistemic_downshifted is True
    assert plan_pref.blast_radius == "LOW"
    assert plan_pref.requires_confirmation is False

    # Ambiguous bug fix mutation downshifted to fix recall
    plan_fix = compiler.compile("Not sure, the fix was restarting redis")
    assert plan_fix.action_type == "READ_ONLY"
    assert plan_fix.tool_name == "recall_fix"
    assert plan_fix.epistemic_downshifted is True
    assert plan_fix.blast_radius == "LOW"


def test_blast_radius_and_reversibility_metadata(compiler):
    """Verifies that blast radius and reversibility contracts are consistently populated across plans."""
    read_plan = compiler.compile("How is brain health?")
    assert read_plan.blast_radius == "LOW"
    assert read_plan.reversibility == "NON_MUTATING"

    mutation_plan = compiler.compile("Remember that all endpoints require rate limiting")
    assert mutation_plan.blast_radius == "MEDIUM"
    assert mutation_plan.reversibility == "ROLLBACK_SUPPORTED"

